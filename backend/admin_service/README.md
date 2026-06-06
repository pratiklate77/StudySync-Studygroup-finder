# StudySync Admin Service

The Admin Service is the operational control plane for StudySync. It provides admin authentication, admin user management, user moderation, verification review surfaces, analytics, system settings, audit trails, maintenance controls, cache clearing, and broadcast notifications. It owns admin-specific PostgreSQL tables, reads Identity/Group/PostgreSQL and Session/MongoDB data for analytics and management views, uses Redis for admin operational state, and publishes admin events to Kafka.

## Features

- Admin login/profile/logout.
- Super-admin bootstrap on startup.
- Admin creation, listing, activation/deactivation, password change/reset.
- User, tutor, and student listing plus user suspend/activate workflows.
- Verification approval/rejection facade.
- Moderation endpoints for reports, chat messages, sessions, and bulk moderation.
- Analytics dashboards for users, sessions, revenue, and platform health.
- System settings, health, dependency checks, maintenance mode, backups, cache clearing, logs, audit trail, notification broadcast.
- Security middleware and CORS middleware.
- Kafka producer for `ADMIN_EVENTS`.

## Tech Stack

FastAPI, PostgreSQL, Async SQLAlchemy, MongoDB Motor for Session analytics, Redis, Kafka, HTTPX, PyJWT, Passlib/bcrypt, Docker.

## Project Structure

```text
app/
├── api/              # admin auth, management, users, verification, moderation, system, analytics
├── core/             # settings, DB sessions, Redis, internal clients, security middleware
├── kafka/            # admin Kafka producer, circuit breaker, fallback/retry
├── models/           # AdminUser, AdminAction, PlatformSetting
├── schemas/          # request/response schemas per admin domain
├── services/         # central AdminService business logic
└── main.py           # startup, super-admin bootstrap, health endpoints
```

## Database Design

Primary PostgreSQL database: `admin_db`.

| Table | Purpose | Important fields |
| --- | --- | --- |
| `admin_user` | Admin accounts. | `id`, `email` unique, `password_hash`, `full_name`, `role` (`super_admin`, `admin`, `moderator`), `permissions` JSONB, `is_active`, `last_login`, `login_count`, `notes`, timestamps |
| `admin_action` | Audit log. | `id`, `admin_id` FK, `action`, `target_type`, `target_id`, `details` JSONB, `reason`, `ip_address`, `user_agent`, timestamps |
| `platform_setting` | Admin-managed platform configuration. | `id`, `key` unique, `value`, `description`, `category`, `is_public`, `updated_by`, timestamps |

External data sources configured in settings:

- Identity PostgreSQL: `identity_db`.
- Group PostgreSQL: `group_db`.
- Session MongoDB: `session_db`.

## API Documentation

Base URL in Docker: `http://localhost:8004`. API prefix: `/api/v1`.

### Authentication

| Method | Endpoint | Auth | Purpose | Request | Response |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/auth/login` | Public | Authenticate admin and issue JWT. | Email/password schema. | `AdminLoginResponse` |
| `GET` | `/auth/profile` | Admin JWT | Current admin profile. | Bearer token. | `AdminProfile` |
| `POST` | `/auth/logout` | Admin JWT | Logout placeholder/stateless token flow. | Bearer token. | Message dict |

### Admin Management

All routes require admin JWT plus permission checks.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/admin-management/create` | Create admin user; super-admin restrictions apply. |
| `GET` | `/admin-management/list` | List admins with pagination. |
| `GET` | `/admin-management/{admin_id}` | Read admin by id. |
| `PUT` | `/admin-management/{admin_id}` | Update admin profile/role/permissions. |
| `POST` | `/admin-management/{admin_id}/deactivate` | Deactivate admin. |
| `POST` | `/admin-management/{admin_id}/activate` | Reactivate admin. |
| `POST` | `/admin-management/change-password` | Change current admin password. |
| `POST` | `/admin-management/{admin_id}/reset-password` | Reset admin password; super-admin only. |

### Users

| Method | Endpoint | Purpose | Query/body |
| --- | --- | --- | --- |
| `GET` | `/admin/users` | Paginated users. | `page`, `per_page`, `role`, `is_active`, `search` |
| `GET` | `/admin/users/{user_id}` | User details. | `user_id` |
| `POST` | `/admin/users/{user_id}/suspend` | Suspend user. | `UserActionRequest.reason` |
| `POST` | `/admin/users/{user_id}/activate` | Activate user. | `UserActionRequest.reason` |
| `GET` | `/admin/tutors` | Tutor list. | `page`, `per_page`, `is_verified`, `search` |
| `GET` | `/admin/students` | Student list. | `page`, `per_page`, `search` |

### Verification

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/verification/pending` | Pending tutor verifications. |
| `GET` | `/verification/stats` | Verification statistics. |
| `GET` | `/verification/{verification_id}` | Verification details. |
| `POST` | `/verification/{verification_id}/approve` | Approve verification. |
| `POST` | `/verification/{verification_id}/reject` | Reject verification with reason. |
| `GET` | `/verification/tutor/{tutor_id}/history` | Tutor verification history. |
| `POST` | `/verification/bulk-approve` | Bulk approve up to 50 ids. |

### Moderation

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/moderation/reports` | List reports. |
| `GET` | `/moderation/reports/stats` | Moderation stats. |
| `GET` | `/moderation/reports/{report_id}` | Report details. |
| `POST` | `/moderation/reports/{report_id}/resolve` | Resolve report. |
| `POST` | `/moderation/reports/{report_id}/dismiss` | Dismiss report. |
| `GET` | `/moderation/chat/messages` | Moderation view of chat messages. |
| `POST` | `/moderation/chat/messages/{message_id}/delete` | Delete moderated message. |
| `POST` | `/moderation/chat/messages/{message_id}/warn` | Warn user about message. |
| `GET` | `/moderation/sessions/reported` | Reported sessions. |
| `POST` | `/moderation/sessions/{session_id}/cancel` | Cancel reported session. |
| `POST` | `/moderation/bulk-moderate` | Bulk moderation action. |

### System and Analytics

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/analytics/overview` | Dashboard overview. |
| `GET` | `/analytics/users` | User analytics. |
| `GET` | `/analytics/sessions` | Session analytics. |
| `GET` | `/analytics/revenue` | Revenue analytics. |
| `GET` | `/analytics/platform-health` | Platform health summary. |
| `GET` | `/system/settings` | Platform settings. |
| `PUT` | `/system/settings` | Update platform settings. |
| `GET` | `/system/health` | System health response. |
| `GET` | `/system/services` | Dependency service statuses. |
| `GET` | `/system/stats` | System statistics. |
| `POST` | `/system/maintenance` | Enable maintenance mode in Redis. |
| `DELETE` | `/system/maintenance` | Disable maintenance mode. |
| `POST` | `/system/backup` | Create backup metadata/stub. |
| `GET` | `/system/backups` | List backups. |
| `POST` | `/system/cache/clear` | Clear `admin:*` Redis keys. |
| `GET` | `/system/logs` | Return system logs/stub data. |
| `GET` | `/system/audit-trail` | Read `admin_action` records. |
| `POST` | `/system/notifications/broadcast` | Publish admin broadcast event. |

Operations outside API prefix: `GET /health`, `GET /health/kafka`, `GET /health/dependencies`, `GET /docs`.

## Authentication and Authorization Flow

Admin login verifies bcrypt password hashes and returns a JWT signed with `JWT_SECRET_KEY`. Protected routes call `get_current_admin`, load the admin profile, ensure it is active, and apply `require_permission`. `super_admin` bypasses permission checks. Role-based permissions are defined in `AdminPermissions`, and custom permissions may be stored on each admin.

## Kafka Integration

| Direction | Topic | Events |
| --- | --- | --- |
| Produce | `ADMIN_EVENTS` | Admin lifecycle actions, maintenance/cache/backup audit events, broadcast notification events |

The producer uses retries, circuit breaker, fallback queue, and retry worker.

## Redis Usage

| Key pattern | Purpose |
| --- | --- |
| `admin:maintenance:enabled` | Maintenance flag. |
| `admin:maintenance:message` | Maintenance message. |
| `admin:*` | Cache namespace cleared by `/system/cache/clear`. |

Settings also define analytics and user-list TTLs.

## Inter-Service Communication

Admin uses configured Identity and Group URLs for dependency health. It also has direct database URLs for Identity and Group PostgreSQL and a MongoDB URL for Session analytics. Several moderation/verification methods are implemented as service-layer stubs or facades and should be connected to the owning services for production-grade side effects.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Admin PostgreSQL URL. |
| `IDENTITY_DB_URL` | Identity PostgreSQL URL for reads/management. |
| `GROUP_DB_URL` | Group PostgreSQL URL. |
| `SESSION_MONGODB_URL` | Session MongoDB URL. |
| `SESSION_MONGODB_DB_NAME` | Session Mongo database name. |
| `REDIS_URL` | Redis URL, DB 6 in compose. |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker list. |
| `KAFKA_CLIENT_ID` | Kafka client id. |
| `KAFKA_ADMIN_EVENTS_TOPIC` | Admin events topic. |
| `IDENTITY_SERVICE_URL` | Identity health/API URL. |
| `GROUP_SERVICE_URL` | Group health/API URL. |
| `JWT_SECRET_KEY` | Admin JWT secret. |
| `JWT_ALGORITHM` | JWT algorithm. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Admin token lifetime. |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token setting. |
| `SUPER_ADMIN_EMAIL` | Bootstrap super admin email. |
| `SUPER_ADMIN_PASSWORD` | Bootstrap super admin password. |
| `ANALYTICS_CACHE_TTL_SECONDS` | Analytics cache TTL. |
| `USER_LIST_CACHE_TTL_SECONDS` | User list cache TTL. |

## Docker and Startup

The Dockerfile exposes `8004`, runs Alembic migrations, and starts Uvicorn. Compose waits for `postgres_admin`, Redis, and Kafka.

```bash
docker compose up -d --build admin_service
docker compose logs -f admin_service
```

## Running Locally

```bash
cd admin_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8004
```

## Testing Guide

- Login with `SUPER_ADMIN_EMAIL` and `SUPER_ADMIN_PASSWORD`.
- Use the admin JWT for all protected endpoints.
- Verify audit rows in `admin_action` after admin-management actions.
- Toggle maintenance mode and inspect Redis DB 6 keys.
- Check `/health/kafka` and consume `ADMIN_EVENTS`.

## Known Limitations

- Several moderation, backup, log, and verification methods are implemented as scaffold/stub operations.
- Admin reads multiple data stores directly, which is practical for dashboards but couples it to schemas owned by other services.
- Default super-admin password must be changed before any real deployment.
