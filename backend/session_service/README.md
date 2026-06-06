# StudySync Session Service

The Session Service owns learning sessions and ratings. It stores sessions, participants, nearby-search data, local verified tutor read models, and session ratings in MongoDB. It validates JWTs statelessly, caches geospatial search results in Redis, consumes payment and tutor verification events, and publishes rating events to Kafka.

## Features

- Create, update, cancel, join, leave, and inspect sessions.
- Nearby session discovery using MongoDB GeoJSON coordinates and Redis caching.
- Free-session participation management.
- Session status transitions: `scheduled`, `active`, `completed`, `cancelled`.
- Ratings with one rating per student per session.
- Kafka producer for `SESSION_RATED`.
- Kafka consumers for `PAYMENT_SUCCESS` and `TUTOR_VERIFIED`.
- Optional standalone/auth-disabled flags for development.

## Tech Stack

FastAPI, MongoDB Motor, Redis, Kafka, PyJWT, Pydantic, Docker.

## Project Structure

```text
app/
├── api/              # session and rating routes plus JWT dependency
├── core/             # settings, Mongo, Redis, JWT helpers
├── events/           # Kafka consumers/producers
├── kafka/            # resilient producer and retry infrastructure
├── models/           # Mongo document models
├── repositories/     # Mongo collection access
├── schemas/          # request/response schemas
├── services/         # session, rating, nearby-cache logic
├── utils/            # document mapping helpers
└── main.py           # startup, health, router registration
```

## Database Design

MongoDB database: `session_db`.

| Collection        | Purpose                                 | Important fields/indexes                                                                                                                                                                                                                               |
| ----------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `sessions`        | Session documents.                      | `id`, `host_id`, `title`, `description`, `session_type`, `price`, `max_participants`, `participants`, `status`, `scheduled_time`, `location` GeoJSON `[longitude, latitude]`, `subject_tags`, timestamps. `location` is intended for 2dsphere queries. |
| `ratings`         | Student ratings for completed sessions. | `id`, `session_id`, `tutor_id`, `student_id`, `score`, `comment`, timestamps. Composite unique index on `(session_id, student_id)` is documented in the model.                                                                                         |
| `verified_tutors` | Local read model from Kafka.            | `id`, `tutor_id`, `is_verified`, timestamps. Used to allow paid session creation for verified tutors.                                                                                                                                                  |

## API Documentation

Base URL in Docker: `http://localhost:8001`. API prefix: `/api/v1`.

### Sessions

| Method  | Endpoint                              | Auth       | Purpose                                 | Request/params                                                                                                     | Response              |
| ------- | ------------------------------------- | ---------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | --------------------- |
| `POST`  | `/sessions/`                          | Bearer JWT | Create a session owned by current user. | `SessionCreate`: title, description, type, price, max participants, scheduled time, location, tags.                | `SessionRead`         |
| `GET`   | `/sessions/nearby`                    | Bearer JWT | Search sessions near coordinates.       | `longitude`, `latitude`, `radius_km`, `limit`, `offset`, `session_type`, `min_price`, `max_price`, `subject_tags`. | List of `SessionRead` |
| `GET`   | `/sessions/my`                        | Bearer JWT | List sessions hosted by current user.   | Authorization header.                                                                                              | List of `SessionRead` |
| `GET`   | `/sessions/{session_id}`              | Bearer JWT | Read a session.                         | `session_id` path.                                                                                                 | `SessionRead`         |
| `PATCH` | `/sessions/{session_id}`              | Bearer JWT | Update session owned by requester.      | `SessionUpdate`.                                                                                                   | `SessionRead`         |
| `PATCH` | `/sessions/{session_id}/cancel`       | Bearer JWT | Cancel session owned by requester.      | `session_id` path.                                                                                                 | `SessionRead`         |
| `PATCH` | `/sessions/{session_id}/status`       | Bearer JWT | Update status.                          | `SessionStatusUpdate.status`.                                                                                      | `SessionRead`         |
| `POST`  | `/sessions/{session_id}/join`         | Bearer JWT | Join a free session.                    | `session_id` path.                                                                                                 | `SessionRead`         |
| `POST`  | `/sessions/{session_id}/leave`        | Bearer JWT | Leave a session.                        | `session_id` path.                                                                                                 | `SessionRead`         |
| `GET`   | `/sessions/{session_id}/participants` | Bearer JWT | List participants for a session.        | `session_id` path.                                                                                                 | List of UUIDs         |

### Ratings

| Method | Endpoint                         | Auth       | Purpose                                    | Request/params                                   | Response             |
| ------ | -------------------------------- | ---------- | ------------------------------------------ | ------------------------------------------------ | -------------------- |
| `POST` | `/sessions/{session_id}/ratings` | Bearer JWT | Submit rating and publish `SESSION_RATED`. | `RatingSubmit`: `score` 1-5, optional `comment`. | `RatingRead`         |
| `GET`  | `/sessions/{session_id}/ratings` | Bearer JWT | List session ratings.                      | `limit`, `offset`.                               | List of `RatingRead` |

### Operations

| Method | Endpoint        | Purpose                             |
| ------ | --------------- | ----------------------------------- |
| `GET`  | `/health`       | Basic health check.                 |
| `GET`  | `/health/ready` | Checks MongoDB and Redis readiness. |
| `GET`  | `/docs`         | Swagger UI.                         |

## Authentication Flow

Routes use `HTTPBearer` and decode the JWT with `JWT_SECRET_KEY` and `JWT_ALGORITHM`. The dependency extracts `sub` as the user UUID and does not call Identity. Development flags in settings include `AUTH_ENABLED`, `STANDALONE_MODE`, and `TEST_USER_ID`.

## Kafka Integration

| Direction | Topic            | Events            | Purpose                                                        |
| --------- | ---------------- | ----------------- | -------------------------------------------------------------- |
| Produce   | `RATING_EVENTS`  | `SESSION_RATED`   | Allows Identity and Recommendation to update tutor aggregates. |
| Consume   | `USER_EVENTS`    | `TUTOR_VERIFIED`  | Maintains `verified_tutors` read model.                        |
| Consume   | `PAYMENT_EVENTS` | `PAYMENT_SUCCESS` | Intended to react to successful paid-session payments.         |

The service uses the same resilient Kafka producer pattern as Identity: startup retries, circuit breaker, fallback store, retry worker.

## Redis Usage

| Key/purpose           | Description                                  | TTL                                 |
| --------------------- | -------------------------------------------- | ----------------------------------- |
| Nearby sessions cache | Caches normalized nearby-search result sets. | `NEARBY_SESSIONS_CACHE_TTL_SECONDS` |

## Inter-Service Communication

Session relies on JWTs issued by Identity, consumes tutor verification events from Identity, consumes payment success events from Payment, and emits rating events consumed by Identity and Notification/Admin-style analytics flows.

## Environment Variables

| Variable                            | Purpose                                    |
| ----------------------------------- | ------------------------------------------ |
| `AUTH_ENABLED`                      | Enables JWT dependency behavior.           |
| `KAFKA_ENABLED`                     | Enables Kafka producer/consumers.          |
| `STANDALONE_MODE`                   | Development mode flag.                     |
| `TEST_USER_ID`                      | Development fallback user id.              |
| `MONGODB_URL`                       | MongoDB server URL.                        |
| `MONGODB_DB_NAME`                   | Mongo database name, default `session_db`. |
| `REDIS_URL`                         | Redis URL, normally DB 1 locally.          |
| `KAFKA_BOOTSTRAP_SERVERS`           | Kafka broker list.                         |
| `KAFKA_CLIENT_ID`                   | Kafka client id.                           |
| `KAFKA_PAYMENT_EVENTS_TOPIC`        | Consumed payment topic.                    |
| `KAFKA_USER_EVENTS_TOPIC`           | Consumed user topic.                       |
| `KAFKA_RATING_EVENTS_TOPIC`         | Produced rating topic.                     |
| `KAFKA_CONSUMER_GROUP`              | Consumer group.                            |
| `JWT_SECRET_KEY`                    | Shared JWT secret.                         |
| `JWT_ALGORITHM`                     | JWT algorithm.                             |
| `NEARBY_SESSIONS_CACHE_TTL_SECONDS` | Nearby cache TTL.                          |

## Docker and Startup

The Dockerfile exposes `8001` and starts Uvicorn on `0.0.0.0:8001`. Docker Compose starts it after MongoDB, Redis, and Kafka are healthy.

```bash
docker compose up -d --build session_service
docker compose logs -f session_service
```

## Running Locally

```bash
cd session_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Use `mongodb://localhost:27017`, `redis://localhost:6379/1`, and `localhost:9092` when running outside Docker.

## Testing Guide

- Authenticate through Identity, then call Session APIs with `Authorization: Bearer <token>`.
- Create a session, then call `/sessions/nearby` with matching coordinates.
- Submit a rating and consume `RATING_EVENTS` from Kafka to verify event publication.
- Inspect Mongo with `mongosh` in `session_db`.
- Inspect Redis nearby cache with `redis-cli -n 1 keys '*'`.

## Known Limitations

- Payment success handling is present as a consumer integration, but payment-to-session booking is not a complete end-to-end checkout workflow.
- JWT validation is stateless shared-secret validation, not centralized introspection.
- Kafka fallback is process-local and not durable across restarts.
