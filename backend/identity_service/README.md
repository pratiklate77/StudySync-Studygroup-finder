# StudySync Identity Service

The Identity Service owns user accounts, authentication tokens, tutor profiles, tutor marketplace search, and tutor verification state. It is the source of truth for `users` and `tutor_profiles`, issues JWT access/refresh tokens, stores refresh-token revocation state in Redis, publishes user lifecycle events to Kafka, and consumes rating events to update tutor reputation.

## Features

- User registration, login, token refresh, logout, profile read/update.
- Tutor onboarding, tutor profile update/deactivation, tutor search, and top tutor leaderboard.
- Admin-key protected tutor verification endpoint.
- JWT access tokens signed with the shared `JWT_SECRET_KEY`.
- Redis-backed refresh-token allowlist/revocation and top tutor cache.
- Kafka producer for `USER_CREATED` and `TUTOR_VERIFIED`.
- Kafka consumer for `RATING_SUBMITTED` to update tutor rating aggregates.
- Async SQLAlchemy with Alembic migrations.

## Tech Stack

FastAPI, PostgreSQL, Async SQLAlchemy, Alembic, Redis, Kafka, PyJWT, Passlib/bcrypt, Docker.

## Project Structure

```text
app/
├── api/              # FastAPI routers and auth dependencies
├── core/             # settings, database, Redis, security helpers
├── events/           # domain Kafka producer/consumer adapters
├── kafka/            # resilient producer, circuit breaker, fallback queue
├── models/           # SQLAlchemy user and tutor models
├── repositories/     # persistence abstractions
├── schemas/          # Pydantic request/response models
├── services/         # auth, tutor, and cache business logic
├── utils/            # rating helper utilities
└── main.py           # application factory, lifespan, health endpoints
```

## Database Design

PostgreSQL database: `identity_db`.

| Table | Purpose | Important fields |
| --- | --- | --- |
| `users` | Account identity and auth subject. | `id`, `email` unique/indexed, `password_hash`, `role` (`user`, `tutor`), `is_active`, `last_known_latitude`, `last_known_longitude`, `created_at` |
| `tutor_profiles` | Tutor marketplace profile linked 1:1 to a user. | `id`, `user_id` unique FK to `users.id`, `bio`, `expertise` PostgreSQL array, `hourly_rate`, `rating_sum`, `total_reviews`, `is_verified`, `is_active` |

Relationship: `User.tutor_profile` is one-to-one with cascade delete from `users` to `tutor_profiles`.

## API Documentation

Base URL in Docker: `http://localhost:8000`. API prefix: `/api/v1`.

### Auth

| Method | Endpoint | Auth | Purpose | Request | Response |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/auth/register` | Public | Create a user account and publish `USER_CREATED`. | `UserRegister` with `email`, `password`, optional location fields. | `UserRead` |
| `POST` | `/auth/login` | Public | Verify password and issue access/refresh tokens. | `UserLogin` with `email`, `password`. | `Token` with `access_token`, `refresh_token`, `token_type` |
| `POST` | `/auth/refresh` | Public | Rotate a valid refresh token. | `RefreshRequest.refresh_token`. | New `Token` |
| `POST` | `/auth/logout` | Public | Revoke refresh token in Redis. | `RefreshRequest.refresh_token`. | `204 No Content` |
| `GET` | `/auth/profile` | Bearer JWT | Read current user's profile. | Authorization header. | `UserProfileRead` |
| `PATCH` | `/auth/profile` | Bearer JWT | Update current user's profile/location fields. | `UserProfileUpdate`. | `UserProfileRead` |

### Tutors

| Method | Endpoint | Auth | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/tutors/become` | Bearer JWT | Create tutor profile for current user. | `TutorBecome`: `bio`, `expertise`, `hourly_rate`. | `TutorProfileRead` |
| `GET` | `/tutors/leaderboard` | Public | Return top tutors by rating, using Redis cache. | `limit` query, 1-50. | List of `TutorProfileRead` |
| `GET` | `/tutors/search` | Bearer JWT | Search active tutor profiles. | `expertise`, `min_rating`, `verified_only`, `limit`, `offset`. | List of `TutorProfileRead` |
| `PATCH` | `/tutors/profile` | Bearer JWT | Update current tutor profile. | `TutorProfileUpdate`. | `TutorProfileRead` |
| `DELETE` | `/tutors/profile` | Bearer JWT | Soft deactivate current tutor profile. | Authorization header. | `TutorProfileRead` |
| `GET` | `/tutors/{tutor_id}/stats` | Bearer JWT | Fetch tutor aggregate rating stats. | `tutor_id` path. | `TutorStatsRead` |
| `GET` | `/tutors/{tutor_id}` | Bearer JWT | Fetch tutor by profile id. | `tutor_id` path. | `TutorProfileRead` |
| `POST` | `/tutors/{user_id}/verify` | `X-Admin-API-Key` | Mark a user's tutor profile as verified and publish `TUTOR_VERIFIED`. | `user_id` path. | `TutorProfileRead` |

### Operations

| Method | Endpoint | Purpose | Response |
| --- | --- | --- | --- |
| `GET` | `/health` | Basic process health. | `{"status": "ok"}` |
| `GET` | `/health/kafka` | Kafka producer and circuit breaker status. | Producer connectivity details |
| `GET` | `/docs` | Swagger UI. | OpenAPI UI |

## Authentication Flow

Passwords are hashed with bcrypt via Passlib. Login creates short-lived access tokens and refresh tokens. Access tokens include `sub`, `exp`, and `type=access`. Refresh tokens include `sub`, `exp`, `type=refresh`, and `jti`; the `jti` is stored in Redis so logout and rotation can revoke tokens. Protected routes decode the Bearer token and load the active user from PostgreSQL.

The tutor verification endpoint does not use a JWT. It requires `X-Admin-API-Key` and is disabled unless `ADMIN_API_KEY` is configured.

## Kafka Integration

| Direction | Topic | Events | Trigger/consumer |
| --- | --- | --- | --- |
| Produce | `USER_EVENTS` | `USER_CREATED` | Successful registration |
| Produce | `USER_EVENTS` | `TUTOR_VERIFIED` | Admin-key tutor verification |
| Consume | `RATING_EVENTS` | `RATING_SUBMITTED` | Updates `rating_sum` and `total_reviews` for the tutor profile |

Kafka publishing uses the resilient producer in `app/kafka`: startup retries, circuit breaker, and in-memory fallback queue with retry worker.

## Redis Usage

| Key/purpose | Description | TTL |
| --- | --- | --- |
| Refresh token JTI keys | Tracks valid or revoked refresh tokens. | Based on refresh token expiry |
| `marketplace:top_tutors` | Cached leaderboard response. | `TOP_TUTORS_CACHE_TTL_SECONDS` |

## Inter-Service Communication

Identity is the issuer of JWTs used by other services. Other services validate tokens with the same shared secret but do not call Identity on every request. Session consumes tutor verification events. Notification consumes user and tutor events. Admin reads Identity database/service data for management workflows.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL URL for `identity_db`. |
| `REDIS_URL` | Redis connection URL, normally DB 0. |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker list. |
| `KAFKA_CLIENT_ID` | Kafka client id, default `identity-service`. |
| `KAFKA_USER_EVENTS_TOPIC` | Topic for user lifecycle events. |
| `KAFKA_RATING_EVENTS_TOPIC` | Topic consumed for ratings. |
| `KAFKA_CONSUMER_GROUP` | Rating consumer group. |
| `JWT_SECRET_KEY` | Shared signing secret; must match dependent services. |
| `JWT_ALGORITHM` | JWT algorithm, default `HS256`. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime. |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime. |
| `TOP_TUTORS_CACHE_KEY` | Redis key for leaderboard cache. |
| `TOP_TUTORS_CACHE_TTL_SECONDS` | Leaderboard cache TTL. |
| `ADMIN_API_KEY` | Enables admin-key tutor verification. |

## Docker and Startup

The Dockerfile installs Python dependencies, copies Alembic and application code, exposes `8000`, runs `alembic upgrade head`, then starts Uvicorn on `0.0.0.0:8000`.

```bash
docker compose up -d --build identity_service
docker compose logs -f identity_service
```

## Running Locally

```bash
cd identity_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Use host-local infrastructure URLs in `.env`: PostgreSQL on `localhost:5442`, Redis on `localhost:6379`, Kafka on `localhost:9092`.

## Testing Guide

- Open `http://localhost:8000/docs` and exercise registration/login first.
- Use the returned access token in Swagger Authorize or `Authorization: Bearer <token>`.
- Verify Redis token state with `docker exec -it studysync-redis redis-cli -n 0 keys '*'`.
- Verify Kafka output with `docker exec -it studysync-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic USER_EVENTS --from-beginning`.
- Run migrations before endpoint tests that touch PostgreSQL.

## Known Limitations

- JWT auth is shared-secret based and does not use asymmetric keys or JWKS rotation.
- Admin tutor verification uses an API key rather than a full service-to-service auth flow.
- Kafka fallback queue is in-memory, so unsent events are lost if the process exits before retry.
