# StudySync Notification Service

The Notification Service centralizes in-app notifications, preferences, templates, delivery logs, and realtime notification dispatch. It stores notifications in PostgreSQL, caches unread counts and preferences in Redis, consumes domain events from multiple Kafka topics, and provides a Redis-backed WebSocket broadcast manager for scalable realtime delivery.

## Features

- List, read, bulk-read, and delete user notifications.
- User notification preferences.
- Notification template listing/creation/fetch by event type.
- Kafka consumer across user, session, group, payment, verification, chat, and recommendation topics.
- In-app notification creation from templates/event payloads.
- Redis cached unread counts/preferences.
- WebSocket manager with Redis pub/sub channel `notification_ws_broadcast`.
- Delivery log model for channel attempts.

## Tech Stack

FastAPI, PostgreSQL, Async SQLAlchemy, Alembic, Redis, Kafka, WebSockets, PyJWT helpers, Docker.

## Project Structure

```text
app/
├── api/              # notifications, preferences, templates, deps
├── core/             # settings, database, Redis, security, websocket manager
├── events/           # Kafka consumer
├── models/           # Notification, Template, DeliveryLog, Preference
├── repositories/     # notification persistence
├── schemas/          # notification/preference/template schemas
├── services/         # notification creation and delivery logic
├── utils/            # default template helpers
└── main.py           # startup and health
```

## Database Design

PostgreSQL database: `notification_db`.

| Table | Purpose | Important fields |
| --- | --- | --- |
| `notifications` | User notification records. | `id`, `user_id` indexed, `type`, `title`, `message`, `context` JSONB, `priority`, `is_read`, `created_at`, `read_at`, `expires_at`, `source_event_id` unique/indexed |
| `notification_templates` | Event templates. | `id`, `event_type` unique, `title_template`, `message_template`, `is_active` |
| `notification_delivery_logs` | Delivery attempt log. | `id`, `notification_id` FK, `channel`, `status`, `error_details`, `attempt`, `created_at` |
| `notification_preferences` | Per-user channel/type preferences. | `user_id` PK, `email_enabled`, `push_enabled`, `in_app_enabled`, `notification_types` JSONB |

## API Documentation

Base URL in Docker: `http://localhost:8007`. API prefix: `/api/v1`.

### Notifications

| Method | Endpoint | Auth | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/notifications` | Bearer JWT | List notifications for current user. | Pagination/filter params from route. | `NotificationListResponse` |
| `GET` | `/notifications/unread` | Bearer JWT | Get unread count. | Current user. | `UnreadCountResponse` |
| `PATCH` | `/notifications/{notification_id}/read` | Bearer JWT | Mark one notification read. | `notification_id`. | `204 No Content` |
| `PATCH` | `/notifications/read` | Bearer JWT | Mark all current user's notifications read. | Current user. | `{ updated_count: int }` |
| `DELETE` | `/notifications/{notification_id}` | Bearer JWT | Delete notification. | `notification_id`. | `204 No Content` |

### Preferences

| Method | Endpoint | Auth | Purpose | Request | Response |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/preferences` | Bearer JWT | Read current preferences. | Current user. | `NotificationPreferenceResponse` |
| `PUT` | `/preferences` | Bearer JWT | Upsert preferences. | Preference update schema. | `NotificationPreferenceResponse` |

### Templates

| Method | Endpoint | Auth | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/templates` | Bearer JWT/current dependency | List templates. | None. | List of `TemplateRead` |
| `POST` | `/templates` | Bearer JWT/current dependency | Create template. | Template create schema. | `TemplateRead` |
| `GET` | `/templates/{event_type}` | Bearer JWT/current dependency | Fetch active template by event type. | `event_type`. | `TemplateRead` |

Operations: `GET /health`, `GET /docs`.

## Authentication Flow

API dependencies decode Bearer JWTs with `JWT_SECRET_KEY` and use the token subject as the user id. The service currently exposes WebSocket manager infrastructure but does not register a public WebSocket route in `main.py`.

## Kafka Integration

The consumer subscribes to:

- `USER_EVENTS`
- `SESSION_EVENTS`
- `GROUP_EVENTS`
- `PAYMENT_EVENTS`
- `VERIFICATION_EVENTS`
- `CHAT_EVENTS`
- `RECOMMENDATION_EVENTS`

Recognized event types include `USER_CREATED`, `USER_REGISTERED`, `SESSION_CREATED`, `SESSION_CANCELLED`, `SESSION_REMINDER`, `GROUP_CREATED`, `GROUP_JOINED`, `PAYMENT_SUCCESS`, `PAYMENT_FAILED`, `TUTOR_VERIFIED`, `TUTOR_REJECTED`, `CHAT_MESSAGE_SENT`, and `TUTOR_RECOMMENDED`. Matching events are converted into notification records and may be dispatched over WebSocket.

## Redis Usage

| Key/channel | Purpose | TTL |
| --- | --- | --- |
| `unread_count:{user_id}` | Cached unread count. | `UNREAD_COUNT_CACHE_TTL_SECONDS` |
| Preference/cache keys in service layer | Preference and notification caching. | `PREFERENCES_CACHE_TTL_SECONDS`, `NOTIFICATION_CACHE_TTL_SECONDS` |
| `notification_ws_broadcast` | Redis pub/sub channel for WebSocket fanout. | N/A |

## Inter-Service Communication

Notification primarily communicates through Kafka. Service URLs for Identity, Session, Group, Payment, and Verification are configured for future enrichment or direct calls.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL URL for `notification_db`. |
| `REDIS_URL` | Redis URL, DB 7 in compose. |
| `NOTIFICATION_CACHE_TTL_SECONDS` | Notification cache TTL. |
| `UNREAD_COUNT_CACHE_TTL_SECONDS` | Unread count TTL. |
| `PREFERENCES_CACHE_TTL_SECONDS` | Preference cache TTL. |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker list. |
| `KAFKA_CLIENT_ID` | Kafka client id. |
| `KAFKA_CONSUMER_GROUP` | Consumer group. |
| `KAFKA_*_EVENTS_TOPIC` | Topic names for user/session/group/payment/verification/chat/recommendation/notification events. |
| `JWT_SECRET_KEY` | Shared JWT secret. |
| `JWT_ALGORITHM` | JWT algorithm. |
| `IDENTITY_SERVICE_URL`, `SESSION_SERVICE_URL`, `GROUP_SERVICE_URL`, `PAYMENT_SERVICE_URL`, `VERIFICATION_SERVICE_URL` | Service base URLs. |

## Docker and Startup

The Dockerfile exposes `8007` and starts Uvicorn. Compose waits for `postgres_notification`, Redis, and Kafka.

```bash
docker compose up -d --build notification_service
docker compose logs -f notification_service
```

## Running Locally

```bash
cd notification_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8007
```

## Testing Guide

- Publish a sample `CHAT_MESSAGE_SENT` or `PAYMENT_SUCCESS` event to Kafka and verify notification rows.
- Call `/notifications/unread`, then mark notifications read and verify Redis invalidation.
- Create a template, then fetch it by `event_type`.
- Inspect Kafka consumer logs with `docker compose logs -f notification_service`.

## Known Limitations

- WebSocket manager exists, but no public WebSocket route is currently registered.
- Email/push delivery is represented by preferences/log models; actual provider integrations are not implemented.
- Event-to-user targeting depends on the payload shape provided by upstream services.
