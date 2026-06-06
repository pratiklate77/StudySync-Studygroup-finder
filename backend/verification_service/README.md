# StudySync Verification Service

The Verification Service owns tutor/KYC-style verification requests and uploaded document metadata. It stores verification workflows in PostgreSQL, caches user verification status in Redis, validates JWTs through middleware, exposes user and admin review APIs, publishes verification lifecycle events, and consumes user events for cross-service awareness.

## Features

- Submit verification requests for authenticated users.
- Upload document metadata to active verification requests.
- Read current verification status, history, and documents.
- Admin list/detail/review/approve/reject workflow.
- Role-based admin guard for `admin` and `super_admin`.
- Redis status cache with invalidation on changes.
- Kafka producer for submitted/approved/rejected verification events.
- Kafka consumer for `USER_EVENTS`.
- Async SQLAlchemy with Alembic migrations.

## Tech Stack

FastAPI, PostgreSQL, Async SQLAlchemy, Alembic, Redis, Kafka, PyJWT middleware, Docker.

## Project Structure

```text
app/
├── api/              # user verification and admin verification routes
├── core/             # settings, database, Redis, JWT middleware/security
├── events/           # Kafka consumer and verification producer
├── kafka/            # resilient producer wrapper
├── models/           # VerificationRequest and Document tables
├── schemas/          # verification request/response schemas
├── services/         # user and admin verification business logic
└── main.py           # middleware, startup, health
```

## Database Design

PostgreSQL database: `verification_db`.

| Table | Purpose | Important fields |
| --- | --- | --- |
| `verification_requests` | Verification workflow record. | `id`, `user_id` indexed, `request_type`, `status` (`pending`, `approved`, `rejected`, `under_review`), `admin_notes`, `reviewed_by`, `submitted_at`, `reviewed_at`, timestamps |
| `documents` | Metadata for uploaded verification documents. | `id`, `verification_request_id` FK/indexed, `file_name`, `file_url`, `document_type`, `uploaded_at`, timestamps |

Relationship: `VerificationRequest.documents` cascades delete-orphan to `Document`.

## API Documentation

Base URL in Docker: `http://localhost:8006`. API prefix: `/api/v1`.

### User Verification

| Method | Endpoint | Auth | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/verification/submit` | Bearer JWT | Create a pending verification request. | `VerificationRequestCreate` with `request_type`. | `VerificationRequestResponse` |
| `POST` | `/verification/documents` | Bearer JWT | Attach document metadata to active request. | `DocumentCreate`: `request_type`, `file_name`, `file_url`, `document_type`. | `DocumentResponse` |
| `GET` | `/verification/status` | Bearer JWT | Get latest status, using Redis cache. | Current user. | `VerificationStatusResponse` |
| `GET` | `/verification/history` | Bearer JWT | List all user's verification requests. | Current user. | `VerificationHistoryResponse` |
| `GET` | `/verification/documents` | Bearer JWT | List documents for latest request. | Current user. | List of `DocumentResponse` |

### Admin Verification

Admin routes require a JWT whose decoded `role` is `admin` or `super_admin`.

| Method | Endpoint | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/verification/` | List requests with optional status filter. | `status`, pagination. | `AdminVerificationListResponse` |
| `GET` | `/admin/verification/pending` | List pending requests. | Pagination. | `AdminVerificationListResponse` |
| `GET` | `/admin/verification/{request_id}` | Detailed request with documents. | `request_id`. | `AdminVerificationDetail` |
| `POST` | `/admin/verification/{request_id}/review` | Mark request under review. | `AdminReviewRequest.admin_notes`. | Detail/response dict |
| `POST` | `/admin/verification/{request_id}/approve` | Approve and publish event. | `AdminReviewRequest.admin_notes`. | Detail/response dict |
| `POST` | `/admin/verification/{request_id}/reject` | Reject and publish event. | `RejectRequest.reason`. | Detail/response dict |

Operations outside prefix: `GET /health`, `GET /health/kafka`, `GET /docs`.

## Authentication Flow

`JWTAuthMiddleware` runs on each request except public paths and decodes `Authorization: Bearer <token>`. It sets `request.state.user_id` and `request.state.user_role`. User routes require `user_id`; admin routes call `_require_admin` and allow only `admin` or `super_admin`.

## Kafka Integration

| Direction | Topic | Events | Purpose |
| --- | --- | --- | --- |
| Produce | `VERIFICATION_EVENTS` | `VERIFICATION_SUBMITTED` | Emitted when user submits a request. |
| Produce | `VERIFICATION_EVENTS` | `VERIFICATION_APPROVED` | Emitted when admin approves. |
| Produce | `VERIFICATION_EVENTS` | `VERIFICATION_REJECTED` | Emitted when admin rejects. |
| Consume | `USER_EVENTS` | `TUTOR_VERIFIED` | Logs/reacts to tutor verification events from Identity. |

## Redis Usage

| Key pattern | Purpose | TTL |
| --- | --- | --- |
| `verification:status:{user_id}` | Cached latest verification status. | `REDIS_CACHE_TTL_SECONDS` |

The key is invalidated on submit, review, approve, and reject.

## Inter-Service Communication

Verification relies on Identity-issued JWTs and emits verification events that Notification/Admin-style services can consume. Identity also has a separate admin-key tutor verification endpoint; a production flow should decide whether Verification approval directly calls Identity or whether another event consumer updates Identity.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `SERVICE_NAME` | Service label. |
| `DATABASE_URL` | Async PostgreSQL URL for `verification_db`. |
| `REDIS_URL` | Redis URL. |
| `REDIS_CACHE_TTL_SECONDS` | Verification status cache TTL. |
| `JWT_SECRET_KEY` | Shared JWT secret. |
| `JWT_ALGORITHM` | JWT algorithm. |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker list. |
| `KAFKA_CLIENT_ID` | Kafka client id. |
| `KAFKA_VERIFICATION_EVENTS_TOPIC` | Produced verification topic. |
| `KAFKA_USER_EVENTS_TOPIC` | Consumed user topic. |
| `MAX_DOCUMENTS_PER_REQUEST` | Document limit per request. |
| `ALLOWED_DOCUMENT_TYPES` | Allowed request/document type list. |

## Docker and Startup

The Dockerfile exposes `8006` and starts Uvicorn. Compose waits for `postgres_verification`, Redis, and Kafka.

```bash
docker compose up -d --build verification_service
docker compose logs -f verification_service
```

## Running Locally

```bash
cd verification_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8006
```

## Testing Guide

- Login through Identity and use the JWT to submit a verification request.
- Upload documents, then call `/verification/status` twice and inspect Redis cache.
- Use an admin-role JWT to approve/reject requests.
- Consume `VERIFICATION_EVENTS` to confirm lifecycle events.

## Known Limitations

- Document upload stores metadata URLs; file storage itself is not implemented.
- Approval emits Kafka events but does not directly update Identity's `tutor_profiles.is_verified`.
- Redis and Kafka defaults differ between local `.env.example` and Docker `.env`; keep broker host/port aligned.
