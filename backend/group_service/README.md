# StudySync Group Service

The Group Service owns study groups and group membership. It stores groups in PostgreSQL, validates JWTs issued by Identity, exposes internal membership/permission endpoints for Chat, publishes group events to Kafka, and calls Session Service for group-session associations.

## Features

- Create, list, read, update, and soft delete groups.
- Join/leave groups, list members, kick members, promote/demote admins.
- Owner/admin permission enforcement.
- Internal membership and permission checks for other services.
- Internal group-session association endpoints.
- Kafka events for group creation, deletion, joins, and leaves.
- Async SQLAlchemy with Alembic migrations.

## Tech Stack

FastAPI, PostgreSQL, Async SQLAlchemy, Alembic, Redis client dependency, Kafka, HTTPX, PyJWT, Docker.

## Project Structure

```text
app/
├── api/              # group, member, and internal routes
├── core/             # settings, database, JWT security
├── events/           # group event publisher
├── kafka/            # resilient Kafka producer stack
├── models/           # Group and GroupMember SQLAlchemy models
├── repositories/     # database access
├── schemas/          # group/member request and response models
├── services/         # business rules and permissions
├── utils/            # permission helpers
└── main.py           # application startup and health
```

## Database Design

PostgreSQL database: `group_db`.

| Table | Purpose | Important fields |
| --- | --- | --- |
| `groups` | Group metadata and ownership. | `id`, `name` indexed, `description`, `owner_id` indexed, `is_private`, `max_members`, `is_active`, `chat_enabled`, `created_at` |
| `group_members` | Membership records. | `id`, `group_id` FK indexed, `user_id` indexed, `role` (`admin`, `member`), `joined_at`; unique `(group_id, user_id)` |

Relationship: `Group.members` cascades deletes to `GroupMember`.

## API Documentation

Base URL in Docker: `http://localhost:8002`. API prefix: `/api/v1`.

### Groups

| Method | Endpoint | Auth | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/groups/` | Bearer JWT | Create a group; creator becomes owner/admin. | `GroupCreate`. | `GroupRead` |
| `GET` | `/groups/` | Bearer JWT | List active groups. | `limit`, `offset`, optional search filters from schema/service. | List of `GroupRead` |
| `GET` | `/groups/{group_id}` | Bearer JWT | Read one group. | `group_id` path. | `GroupRead` |
| `PATCH` | `/groups/{group_id}` | Bearer JWT | Update a group as owner/admin. | `GroupUpdate`. | `GroupRead` |
| `DELETE` | `/groups/{group_id}` | Bearer JWT | Soft delete/deactivate group. | `group_id` path. | `204 No Content` |

### Members

| Method | Endpoint | Auth | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/groups/{group_id}/join` | Bearer JWT | Join a group and publish `USER_JOINED_GROUP`. | `group_id` path. | `MemberRead` |
| `POST` | `/groups/{group_id}/leave` | Bearer JWT | Leave a group and publish `USER_LEFT_GROUP`. | `group_id` path. | `204 No Content` |
| `GET` | `/groups/{group_id}/members` | Bearer JWT | List group members. | `limit`, `offset`. | List of `MemberRead` |
| `POST` | `/groups/{group_id}/kick` | Bearer JWT | Remove another member. | Query/body user id as implemented by route. | `204 No Content` |
| `POST` | `/groups/{group_id}/promote` | Bearer JWT | Promote member to admin. | Target user id. | `MemberRead` |
| `POST` | `/groups/{group_id}/demote` | Bearer JWT | Demote admin to member. | Target user id. | `MemberRead` |

### Internal

| Method | Endpoint | Auth | Purpose | Response |
| --- | --- | --- | --- | --- |
| `GET` | `/internal/groups/{group_id}/members/{user_id}` | Bearer JWT currently | Membership check used by Chat. | `MembershipCheck` |
| `GET` | `/internal/groups/{group_id}/permissions/{user_id}` | Bearer JWT currently | Permission check used by Chat. | `PermissionsCheck` |
| `GET` | `/internal/groups/{group_id}/sessions` | Bearer JWT currently | Fetch sessions associated with group. | Service-defined dict/list |
| `POST` | `/internal/groups/{group_id}/sessions/{session_id}` | Bearer JWT currently | Associate session with group. | Status dict |

### Operations

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Basic service health. |
| `GET` | `/docs` | Swagger UI. |

## Authentication Flow

Routes use Bearer JWTs signed by Identity. The dependency decodes `sub` as the current user UUID. Group and member services then apply ownership/admin/member rules based on database membership records.

## Kafka Integration

| Direction | Topic | Events |
| --- | --- | --- |
| Produce | `GROUP_EVENTS` | `GROUP_CREATED`, `GROUP_DELETED`, `USER_JOINED_GROUP`, `USER_LEFT_GROUP` |

Chat consumes `GROUP_EVENTS` to maintain its local `group_memberships` collection.

## Redis Usage

`REDIS_URL` exists in settings for ecosystem consistency, but the current Group implementation does not expose a domain cache like nearby sessions or notification counts.

## Inter-Service Communication

- Chat calls internal membership and permission endpoints before message reads/writes and WebSocket joins.
- Group can call Session Service via `SESSION_SERVICE_URL` for group-session workflows.
- Identity provides JWTs; Group validates them locally.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL URL for `group_db`. |
| `REDIS_URL` | Redis URL. |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker list. |
| `KAFKA_CLIENT_ID` | Kafka client id. |
| `KAFKA_GROUP_EVENTS_TOPIC` | Topic for group events. |
| `JWT_SECRET_KEY` | Shared JWT secret. |
| `JWT_ALGORITHM` | JWT algorithm. |
| `SESSION_SERVICE_URL` | Session Service base URL. |
| `SESSION_SERVICE_TIMEOUT_SECONDS` | HTTP timeout for Session calls. |

## Docker and Startup

The Dockerfile exposes `8002`, runs Alembic migrations, and starts Uvicorn. Compose waits for `postgres_group`, Redis, and Kafka.

```bash
docker compose up -d --build group_service
docker compose logs -f group_service
```

## Running Locally

```bash
cd group_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

## Testing Guide

- Register/login in Identity and use the access token.
- Create a group, join with another user, then verify `/groups/{group_id}/members`.
- Consume `GROUP_EVENTS` to verify group event publication.
- Test Chat membership integration through `/internal/groups/{group_id}/members/{user_id}`.

## Known Limitations

- Internal endpoints currently use the same Bearer JWT style rather than dedicated service credentials.
- Redis is configured but not heavily used by current group business logic.
- Group-session association is present, but broader product flow depends on Session Service integration.
