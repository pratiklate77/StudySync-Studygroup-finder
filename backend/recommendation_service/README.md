# StudySync Recommendation Service

The Recommendation Service ranks tutors using stored tutor metrics, subject scores, trending scores, and Redis-cached query results. It exposes top, trending, subject, search, nearby, personalized, similar tutor, metrics, and admin recalculation/cache endpoints. PostgreSQL stores recommendation read models and Redis stores API cache entries.

## Features

- Top-ranked tutor recommendations.
- Trending tutors.
- Subject-based recommendations.
- Search/filter by subject, rating, and verification.
- Nearby tutor lookup using SQL Haversine distance calculation.
- Personalized recommendations fallback to global top tutors.
- Similar tutor lookup.
- Admin score recalculation and cache refresh endpoints.
- Redis caching for top/trending/subject queries.

## Tech Stack

FastAPI, PostgreSQL, Async SQLAlchemy, Redis, JWT decode helper, Docker.

## Project Structure

```text
app/
├── api/              # recommendation routes and dependencies
├── core/             # settings, database, Redis
├── models/           # tutor metrics, subject scores, trending tutors
├── services/         # recommendation scoring, search, cache logic
└── main.py           # startup and health
```

## Database Design

PostgreSQL database: `recommendation_db`.

| Table | Purpose | Important fields |
| --- | --- | --- |
| `tutor_metrics` | Main ranking input/read model. | `tutor_id` PK, `average_rating`, `total_reviews`, `total_sessions`, `sessions_completed`, `is_verified`, `subjects` JSONB, `activity_score`, `latitude`, `longitude`, `recommendation_score` indexed, `last_activity`, `updated_at` |
| `recommendation_scores` | Subject-specific score/rank. | Composite PK `tutor_id`, `subject`, `score` indexed, `rank`, `updated_at` |
| `trending_tutors` | Trending read model. | `tutor_id` PK, `growth_rate`, `trend_score` indexed, `calculated_at` |

## API Documentation

Base URL in Docker: `http://localhost:8008`. API prefix: `/api/v1/recommendations`.

| Method | Endpoint | Auth | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/top` | Public | Top tutors by `recommendation_score`. | `limit` query. | List of tutor score objects |
| `GET` | `/trending` | Public | Top trending tutors by `trend_score`. | None. | List with `tutor_id`, `trend_score` |
| `GET` | `/subject/{subject}` | Public | Tutors matching a subject. | `subject` path. | List with `tutor_id`, `score` |
| `GET` | `/search` | Public | Filter tutors. | `subjects`, `min_rating`, `is_verified`, `page`, `per_page`. | List with tutor id, score, rating |
| `GET` | `/nearby` | Public | Tutors within radius using lat/lon. | `lat`, `lon`, `radius_km`. | List with tutor id and subjects |
| `GET` | `/user/{user_id}` | Bearer JWT | Personalized recommendations; only same user allowed. | `user_id` path. | Top tutor fallback list |
| `GET` | `/tutor/{tutor_id}/similar` | Public | Similar tutors by subjects/rating. | `limit`. | List with tutor id and score |
| `GET` | `/tutor/{tutor_id}` | Public | Raw tutor metrics. | `tutor_id`. | `TutorMetric` object or null |
| `GET` | `/health` | Public | API health. | None. | Status dict |
| `GET` | `/health/ready` | Public | Checks PostgreSQL and Redis. | None. | Readiness dict |
| `POST` | `/admin/recalculate` | Public in current code | Recompute scores for all or one tutor. | Optional `tutor_id`. | Accepted/status dict |
| `POST` | `/admin/cache/refresh` | Public in current code | Clear recommendation cache keys. | `target`, default `all`. | Message with cleared count |

Operations outside API router: `GET /health`, `GET /docs`.

## Authentication Flow

Only `/user/{user_id}` declares the JWT dependency. It decodes the Bearer token and prevents a user from requesting another user's recommendations. Admin endpoints are named `/admin/...` but do not currently enforce admin authentication or role checks.

## Kafka Integration

Settings define:

- `KAFKA_TUTOR_EVENTS_TOPIC=TUTOR_EVENTS`
- `KAFKA_SESSION_EVENTS_TOPIC=SESSION_EVENTS`
- `KAFKA_CONSUMER_GROUP=recommendation-service-group`

The current visible implementation does not start Kafka consumers in `main.py`. Recommendation tables are therefore populated by database writes, migrations/seed data, or future event consumers.

## Redis Usage

| Key pattern | Purpose | TTL |
| --- | --- | --- |
| `rec:top:{limit}` | Top ranked tutors. | `RECOMMENDATION_CACHE_TTL` |
| `rec:trending` | Trending tutors. | 3600 seconds |
| `rec:subject:{subject}` | Subject recommendations. | `RECOMMENDATION_CACHE_TTL` |
| `rec:*` | Cache refresh/delete namespace. | N/A |

## Inter-Service Communication

Settings include Identity and Session service URLs, but the current service implementation does not call them directly. It depends on upstream systems to maintain `tutor_metrics`, `recommendation_scores`, and `trending_tutors`.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL URL for `recommendation_db`. |
| `REDIS_URL` | Redis URL, DB 8 in compose. |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker list. |
| `KAFKA_CONSUMER_GROUP` | Recommendation consumer group setting. |
| `KAFKA_TUTOR_EVENTS_TOPIC` | Intended tutor-events topic. |
| `KAFKA_SESSION_EVENTS_TOPIC` | Intended session-events topic. |
| `JWT_SECRET_KEY` | JWT secret used by user recommendation endpoint. |
| `JWT_ALGORITHM` | JWT algorithm. |
| `IDENTITY_SERVICE_URL` | Identity base URL. |
| `SESSION_SERVICE_URL` | Session base URL. |
| `RECOMMENDATION_CACHE_TTL` | Cache TTL for top/subject recommendations. |

## Docker and Startup

The Dockerfile exposes `8008` and starts Uvicorn on `0.0.0.0:8008`. Compose waits for `postgres_recommendation`, Redis, and Kafka.

```bash
docker compose up -d --build recommendation_service
docker compose logs -f recommendation_service
```

## Running Locally

```bash
cd recommendation_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8008
```

## Testing Guide

- Seed `tutor_metrics` rows and call `/top`, `/search`, and `/nearby`.
- Verify Redis cache keys with `redis-cli -n 8 keys 'rec:*'`.
- Call `/admin/recalculate` and confirm `recommendation_score` changes.
- Use `/health/ready` to verify PostgreSQL and Redis connectivity.

## Known Limitations

- Kafka topics are configured but no consumer is currently wired into startup.
- Admin endpoints are not protected by admin auth.
- Personalized recommendations currently fall back to global top tutors.
- Trending read model has fields but no scheduled calculation worker in the visible implementation.
