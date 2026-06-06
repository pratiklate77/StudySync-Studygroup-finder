# StudySync Chat Service

The Chat Service owns group messages and realtime group chat. It stores messages and a local group-membership read model in MongoDB, validates JWTs, checks membership with Group Service, publishes chat events to Kafka, consumes group events to keep membership synchronized, and uses Redis for recent-message cache and online presence helpers.

## Features

- Send, list, edit, and soft delete group messages.
- WebSocket endpoint for realtime group chat.
- Online-user count and read/unread helpers.
- Local `group_memberships` read model synchronized from `GROUP_EVENTS`.
- HTTP membership verification against Group Service.
- Redis recent message cache and online presence keys.
- Kafka producer for chat message events.

## Tech Stack

FastAPI, WebSockets, MongoDB Motor, Redis, Kafka, HTTPX, PyJWT, Pydantic, Docker.

## Project Structure

```text
app/
├── api/              # REST message routes, WebSocket route, dependencies
├── core/             # settings, Mongo, Redis, JWT, connection manager
├── events/           # GROUP_EVENTS consumer and CHAT_EVENTS producer
├── kafka/            # resilient producer, circuit breaker, retry worker
├── models/           # Mongo message and membership documents
├── repositories/     # Mongo persistence
├── schemas/          # message request/response models
├── services/         # message logic and Redis cache
└── main.py           # application startup and health
```

## Database Design

MongoDB database: `chat_db`.

| Collection | Purpose | Important fields/indexes |
| --- | --- | --- |
| `messages` | Group chat messages. | `id`, `group_id`, `sender_id`, `content`, `is_deleted`, `is_edited`, timestamps |
| `group_memberships` | Local mirror of Group Service membership. | `id`, `group_id`, `user_id`, `role`, `chat_enabled`, `is_active`, timestamps; unique `(group_id, user_id)` documented in model |

## API Documentation

Base URL in Docker: `http://localhost:8003`. API prefix: `/api/v1`.

| Method | Endpoint | Auth | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/groups/{group_id}/messages` | Bearer JWT | Send a group message. | `MessageCreate.content`. | `MessageRead` |
| `GET` | `/groups/{group_id}/messages` | Bearer JWT | List recent messages for a group. | Pagination params from route/service. | `MessageListResponse` |
| `DELETE` | `/messages/{message_id}` | Bearer JWT | Soft delete a message. | `message_id` path. | `204 No Content` |
| `PATCH` | `/messages/{message_id}` | Bearer JWT | Edit a message. | `MessageUpdate.content`. | `MessageRead` |
| `GET` | `/groups/{group_id}/online` | Bearer JWT | Return online count for group. | `group_id` path. | `{ "online_count": int }` |
| `POST` | `/groups/{group_id}/read` | Bearer JWT | Mark group as read for current user. | `group_id` path. | `204 No Content` |
| `GET` | `/groups/{group_id}/unread-count` | Bearer JWT | Return unread count for current user. | `group_id` path. | `{ "unread_count": int }` |
| `WEBSOCKET` | `/groups/{group_id}/ws?token=...` | JWT query token | Realtime group chat socket. | Path `group_id`, query `token`. | JSON messages over WebSocket |

Operations: `GET /health`, `GET /docs`.

## Authentication Flow

REST routes use Bearer JWTs. The WebSocket route accepts a JWT in the `token` query parameter, decodes it with the shared secret, and rejects unauthenticated clients. Message operations verify group access using the local membership read model and/or Group Service internal checks.

## Kafka Integration

| Direction | Topic | Events | Purpose |
| --- | --- | --- | --- |
| Consume | `GROUP_EVENTS` | `GROUP_CREATED`, `GROUP_DELETED`, `USER_JOINED_GROUP`, `USER_LEFT_GROUP` | Maintains `group_memberships`. |
| Produce | `CHAT_EVENTS` | `CHAT_MESSAGE_SENT`, `CHAT_MESSAGE_DELETED` | Feeds notifications, moderation, and analytics. |

## Redis Usage

| Key pattern | Purpose | TTL |
| --- | --- | --- |
| `chat:recent:{group_id}` | Recent message cache for faster group reads. | `RECENT_MESSAGES_CACHE_TTL_SECONDS` |
| `chat:online:{group_id}:{user_id}` | Online presence marker. | Managed by WebSocket connect/disconnect flow |

## Inter-Service Communication

- Calls Group Service using `GROUP_SERVICE_URL` to verify membership/permissions.
- Consumes Group Service Kafka events as the preferred membership synchronization path.
- Publishes chat events consumed by Notification Service.
- Uses JWTs issued by Identity.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `MONGODB_URL` | MongoDB URL. |
| `MONGODB_DB_NAME` | Mongo database name, default `chat_db`. |
| `REDIS_URL` | Redis URL, normally DB 3. |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker list. |
| `KAFKA_CLIENT_ID` | Kafka client id. |
| `KAFKA_GROUP_EVENTS_TOPIC` | Topic consumed for group membership events. |
| `KAFKA_CHAT_EVENTS_TOPIC` | Topic produced for chat events. |
| `KAFKA_CONSUMER_GROUP` | Chat consumer group. |
| `JWT_SECRET_KEY` | Shared JWT secret. |
| `JWT_ALGORITHM` | JWT algorithm. |
| `RECENT_MESSAGES_CACHE_TTL_SECONDS` | Recent cache TTL. |
| `RECENT_MESSAGES_CACHE_LIMIT` | Recent cache message limit. |
| `GROUP_SERVICE_URL` | Group Service base URL. |

## Docker and Startup

The Dockerfile exposes `8003` and starts Uvicorn. Compose waits for MongoDB, Redis, and Kafka.

```bash
docker compose up -d --build chat_service
docker compose logs -f chat_service
```

## Running Locally

```bash
cd chat_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8003
```

## Testing Guide

- Create a group in Group Service and ensure membership exists.
- Send messages via REST, then read them back with pagination.
- Connect to `ws://localhost:8003/api/v1/groups/{group_id}/ws?token=<jwt>`.
- Inspect `CHAT_EVENTS` and `GROUP_EVENTS` with Kafka console tools.
- Check Redis online keys with `redis-cli -n 3 keys 'chat:*'`.

## Known Limitations

- Online presence is Redis-assisted but not a full distributed WebSocket gateway.
- WebSocket auth uses query-token style, which should be hardened for production clients.
- Durable event fallback is in-memory only.
