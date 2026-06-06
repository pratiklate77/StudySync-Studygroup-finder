# StudySync — Database Design

## Overview

StudySync employs a **polyglot persistence** architecture with PostgreSQL for relational data, MongoDB for document/geospatial data, and Redis for caching/tokens. Each microservice owns its database exclusively (Database-per-Service pattern).

---

## Architecture Principles

1. **Database-per-Service** — No shared databases between services
2. **No Cross-Service Foreign Keys** — Referential integrity maintained via application logic and Kafka events
3. **Soft Deletes** — `is_active` flags used instead of hard deletes for audit trail
4. **Async Access** — All database access is async (asyncpg + Motor)
5. **Schema Migrations** — Alembic for PostgreSQL, runtime index creation for MongoDB

---

## Database Inventory

| Service | Database | Type | Host Port | Docker Hostname | Migration |
|---------|----------|------|-----------|----------------|-----------|
| Identity | identity_db | PostgreSQL 16 | 5442 | postgres | Alembic |
| Group | group_db | PostgreSQL 16 | 5433 | postgres_group | Alembic |
| Admin | admin_db | PostgreSQL 16 | 5437 | postgres_admin | Alembic |
| Payment | payment_db | PostgreSQL 16 | 5445 | postgres_payment | Alembic |
| Verification | verification_db | PostgreSQL 16 | 5446 | postgres_verification | Alembic |
| Notification | notification_db | PostgreSQL 16 | 5447 | postgres_notification | Alembic |
| Recommendation | recommendation_db | PostgreSQL 16 | 5448 | postgres_recommendation | Alembic |
| Session | session_db | MongoDB 7 | 27017 | mongo | Runtime indexes |
| Chat | chat_db | MongoDB 7 | 27017 | mongo | Runtime indexes |
| Cache | (Redis DB 0–8) | Redis 7 | 6379 | redis | N/A |

---

## PostgreSQL Schemas

### 1. Identity Service — `identity_db`

#### Table: `users`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique user identifier |
| email | VARCHAR(320) | UNIQUE, NOT NULL, INDEX | User email address |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt password hash |
| role | ENUM('user','tutor') | NOT NULL, DEFAULT 'user' | User role |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft delete flag |
| is_email_verified | BOOLEAN | NOT NULL, DEFAULT false | Email verification status |
| is_verified_tutor | BOOLEAN | NULLABLE | Verified tutor flag |
| last_known_latitude | FLOAT | NULLABLE | User's last known latitude |
| last_known_longitude | FLOAT | NULLABLE | User's last known longitude |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |

**Relationships:** Has one `TutorProfile` (uselist=False)

**Indexes:**
- `ix_users_email` — UNIQUE on email
- PK on id

#### Table: `tutor_profiles`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique profile identifier |
| user_id | UUID | UNIQUE, NOT NULL, FK→users.id, INDEX | User who owns profile |
| bio | TEXT | NULLABLE | Tutor biography |
| expertise | VARCHAR(128)[] | NOT NULL | Array of expertise tags |
| hourly_rate | NUMERIC(12,2) | NOT NULL, DEFAULT 0 | Hourly rate in currency units |
| rating_sum | INTEGER | NOT NULL, DEFAULT 0 | Sum of all rating scores |
| total_reviews | INTEGER | NOT NULL, DEFAULT 0 | Total number of reviews |
| is_verified | BOOLEAN | NOT NULL, DEFAULT false | Verification status |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft delete flag |

**Indexes:**
- UNIQUE on user_id
- INDEX on user_id

---

### 2. Group Service — `group_db`

#### Table: `groups`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique group identifier |
| name | VARCHAR(200) | NOT NULL, INDEX | Group name |
| description | TEXT | NULLABLE | Group description |
| owner_id | UUID | NOT NULL, INDEX | User who created the group |
| is_private | BOOLEAN | NOT NULL, DEFAULT false | Private group flag |
| max_members | INTEGER | NOT NULL, DEFAULT 50 | Maximum members allowed |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft delete flag |
| chat_enabled | BOOLEAN | NOT NULL, DEFAULT true | Chat enabled flag |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |

**Relationships:** Has many `GroupMember` (cascade delete)

#### Table: `group_members`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique membership identifier |
| group_id | UUID | NOT NULL, FK→groups.id, INDEX | Group reference |
| user_id | UUID | NOT NULL, INDEX | User reference |
| role | ENUM('admin','member') | NOT NULL, DEFAULT 'member' | Member role |
| joined_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Join timestamp |

**Constraints:** UNIQUE(group_id, user_id)

**Indexes:**
- INDEX on group_id
- INDEX on user_id
- UNIQUE INDEX on (group_id, user_id)

---

### 3. Admin Service — `admin_db`

#### Table: `admin_user`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique admin identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | Admin email |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt password hash |
| full_name | VARCHAR(255) | NOT NULL | Admin full name |
| role | VARCHAR(50) | NOT NULL, DEFAULT 'admin' | Admin role (super_admin, admin, moderator) |
| permissions | JSONB | NOT NULL, DEFAULT [] | Array of permission strings |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |
| last_login | TIMESTAMPTZ | NULLABLE | Last login timestamp |
| login_count | INTEGER | NOT NULL, DEFAULT 0 | Login counter |
| notes | TEXT | NULLABLE | Admin notes |

**Indexes:** UNIQUE on email

#### Table: `admin_action`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique action identifier |
| admin_id | UUID | NOT NULL, FK→admin_user.id, INDEX | Admin who performed action |
| action | VARCHAR(100) | NOT NULL, INDEX | Action type (suspend, approve, etc.) |
| target_type | VARCHAR(50) | NULLABLE, INDEX | Entity type (user, tutor, session) |
| target_id | VARCHAR(255) | NULLABLE, INDEX | Entity identifier |
| details | JSONB | NOT NULL, DEFAULT {} | Action details/metadata |
| reason | TEXT | NULLABLE | Reason for action |
| ip_address | VARCHAR(45) | NULLABLE | Admin IP address |
| user_agent | TEXT | NULLABLE | Browser/client info |

#### Table: `platform_setting`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique setting identifier |
| key | VARCHAR(100) | UNIQUE, NOT NULL, INDEX | Setting key name |
| value | TEXT | NOT NULL | Setting value |
| description | TEXT | NULLABLE | Description |
| category | VARCHAR(50) | NOT NULL, DEFAULT 'general', INDEX | Setting category |
| is_public | BOOLEAN | NOT NULL, DEFAULT false | Public visibility flag |
| updated_by | UUID | NULLABLE | Admin who last updated |

---

### 4. Payment Service — `payment_db`

#### Table: `payments`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique payment identifier |
| user_id | UUID | NOT NULL | Student who paid |
| tutor_id | UUID | NOT NULL | Tutor receiving payment |
| session_id | UUID | NOT NULL | Session being paid for |
| amount | DECIMAL(10,2) | NOT NULL | Payment amount |
| platform_fee | DECIMAL(10,2) | NOT NULL | Platform commission |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | Payment status |
| payment_method | VARCHAR(50) | NOT NULL | Payment method |
| provider_id | VARCHAR(255) | NULLABLE | External provider reference |
| created_at | TIMESTAMPTZ | DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Last update timestamp |

**Statuses:** pending, completed, failed, refunded

#### Table: `wallets`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique wallet identifier |
| user_id | UUID | UNIQUE, NOT NULL | Wallet owner |
| balance | DECIMAL(10,2) | NOT NULL, DEFAULT 0.00 | Current balance |
| created_at | TIMESTAMPTZ | DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Last update timestamp |

**Relationships:** Has many `Transaction`

#### Table: `transactions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique transaction identifier |
| wallet_id | UUID | NOT NULL, FK→wallets.id | Wallet reference |
| payment_id | UUID | NULLABLE | Payment reference |
| type | VARCHAR(20) | NOT NULL | Transaction type (credit, debit, payment, refund) |
| amount | DECIMAL(10,2) | NOT NULL | Transaction amount |
| description | VARCHAR(512) | NULLABLE | Description |
| created_at | TIMESTAMPTZ | DEFAULT now() | Creation timestamp |

---

### 5. Verification Service — `verification_db`

#### Table: `tutor_verification_requests`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique request identifier |
| user_id | UUID | NOT NULL, INDEX | Applicant user ID |
| status | ENUM | NOT NULL, DEFAULT 'PENDING' | Verification status |
| bio | TEXT | NULLABLE | Tutor biography |
| subjects | VARCHAR | NULLABLE | CSV list of subjects |
| experience_years | INTEGER | NULLABLE | Years of experience |
| hourly_rate | FLOAT | NULLABLE | Desired hourly rate |
| reviewed_by | UUID | NULLABLE | Admin who reviewed |
| reviewed_at | TIMESTAMPTZ | NULLABLE | Review timestamp |
| rejection_reason | TEXT | NULLABLE | Rejection reason |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |

**Statuses:** PENDING, UNDER_REVIEW, VERIFIED, REJECTED, SUSPENDED

**Relationships:** Has many `VerificationDocument` (cascade delete)

#### Table: `verification_documents`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique document identifier |
| request_id | UUID | NOT NULL, FK→tutor_verification_requests.id, INDEX | Parent request |
| file_name | VARCHAR(255) | NOT NULL | Original filename |
| file_url | VARCHAR(500) | NOT NULL | Storage path |
| document_type | VARCHAR(50) | NOT NULL | IDENTITY_PROOF, HIGHEST_DEGREE, CERTIFICATE |
| uploaded_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Upload timestamp |

---

### 6. Notification Service — `notification_db`

#### Table: `notifications`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique notification identifier |
| user_id | UUID | NOT NULL, INDEX | Notification recipient |
| type | VARCHAR(50) | NOT NULL | Notification type |
| title | VARCHAR(255) | NOT NULL | Notification title |
| message | VARCHAR(1000) | NOT NULL | Notification message |
| context | JSONB | NOT NULL, DEFAULT '{}' | Additional context data |
| priority | VARCHAR(20) | NOT NULL, DEFAULT 'normal' | low, normal, high, urgent |
| is_read | BOOLEAN | NOT NULL, DEFAULT false | Read status |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| read_at | TIMESTAMPTZ | NULLABLE | Read timestamp |
| expires_at | TIMESTAMPTZ | NULLABLE | Expiration timestamp |
| source_event_id | VARCHAR(255) | UNIQUE, INDEX | Source event dedup key |

#### Table: `notification_templates`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique template identifier |
| event_type | VARCHAR(50) | UNIQUE, NOT NULL | Event type |
| title_template | VARCHAR(255) | NOT NULL | Title template string |
| message_template | TEXT | NOT NULL | Message template string |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |

#### Table: `notification_delivery_logs`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, default uuid4 | Unique log identifier |
| notification_id | UUID | NOT NULL, FK→notifications.id | Notification reference |
| channel | VARCHAR(20) | NOT NULL | Delivery channel (email, websocket, push) |
| status | VARCHAR(20) | NOT NULL | Delivery status (sent, delivered, failed) |
| error_details | TEXT | NULLABLE | Error details |
| attempt | INTEGER | NOT NULL, DEFAULT 1 | Delivery attempt number |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Log timestamp |

---

### 7. Recommendation Service — `recommendation_db`

#### Table: `tutor_metrics`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| tutor_id | UUID | PK | Tutor identifier |
| average_rating | FLOAT | NOT NULL, DEFAULT 0.0 | Average rating score |
| total_reviews | INTEGER | NOT NULL, DEFAULT 0 | Total review count |
| total_sessions | INTEGER | NOT NULL, DEFAULT 0 | Total session count |
| sessions_completed | INTEGER | NOT NULL, DEFAULT 0 | Completed session count |
| is_verified | BOOLEAN | NOT NULL, DEFAULT false | Verification status |
| subjects | JSONB | NOT NULL, DEFAULT [] | Subject tags |
| activity_score | FLOAT | NOT NULL, DEFAULT 0.0 | Activity metric |
| latitude | FLOAT | NULLABLE | Tutor location latitude |
| longitude | FLOAT | NULLABLE | Tutor location longitude |
| recommendation_score | FLOAT | NOT NULL, DEFAULT 0.0, INDEX | Computed recommendation score |
| last_activity | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last activity timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

#### Table: `recommendation_scores`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| tutor_id | UUID | PK | Tutor identifier |
| subject | VARCHAR(100) | PK, INDEX | Subject category |
| score | FLOAT | NOT NULL, DEFAULT 0.0, INDEX | Subject-specific score |
| rank | INTEGER | NULLABLE | Rank within subject |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

**Constraint:** Composite PK (tutor_id, subject)

#### Table: `trending_tutors`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| tutor_id | UUID | PK | Tutor identifier |
| growth_rate | FLOAT | NOT NULL, DEFAULT 0.0 | Growth in sessions/ratings |
| trend_score | FLOAT | NOT NULL, DEFAULT 0.0, INDEX | Computed trend score |
| calculated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Calculation timestamp |

---

## MongoDB Schemas

### 8. Session Service — `session_db`

#### Collection: `sessions`

| Field | Type | Description |
|-------|------|-------------|
| _id | UUID | Unique session identifier |
| host_id | UUID (string) | Tutor's user ID |
| title | string | Session title |
| description | string (nullable) | Session description |
| session_type | string | 'free' or 'paid' |
| price | float | 0.0 for free sessions |
| max_participants | int | Max participants (default 50) |
| participants | UUID[] | Array of participant user IDs |
| status | string | scheduled, active, completed, cancelled |
| scheduled_time | datetime | Scheduled start time |
| location | GeoJSON Point | 2dsphere-indexed geolocation |
| address | string | Physical address or room |
| subject_tags | string[] | Subject categories |
| avg_rating | float | Computed average rating |
| total_ratings | int | Total rating count |

**Indexes:**
- `sessions_location_2dsphere` — 2dsphere index on location
- `sessions_status_idx` — on status field

#### Collection: `ratings`

| Field | Type | Description |
|-------|------|-------------|
| _id | UUID | Unique rating identifier |
| session_id | UUID | Session reference |
| tutor_id | UUID | Tutor being rated |
| student_id | UUID | Student who submitted rating |
| score | int | Rating score (1-5) |
| comment | string (nullable) | Review text |

**Indexes:**
- `ratings_session_student_unique` — UNIQUE on (session_id, student_id)

#### Collection: `verified_tutors`

| Field | Type | Description |
|-------|------|-------------|
| _id | UUID | Unique record identifier |
| user_id | UUID | User ID from Identity Service |
| is_verified | bool | Verification status (default true) |
| status | string | active, rejected, suspended |
| verified_at | datetime (nullable) | Verification timestamp |
| subjects | string[] | Subject expertise |

**Indexes:**
- `vt_user_id_idx` — UNIQUE on user_id
- `vt_status_idx` — on status

### 9. Chat Service — `chat_db`

#### Collection: `messages`

| Field | Type | Description |
|-------|------|-------------|
| _id | UUID | Unique message identifier |
| group_id | UUID | Group reference |
| sender_id | UUID | Message sender |
| content | string | Message content |
| is_deleted | bool | Soft delete flag |
| is_edited | bool | Edit flag |
| created_at | datetime | Message timestamp (auto) |

**Indexes:**
- `messages_group_time_idx` — on (group_id, created_at)
- `messages_group_deleted_idx` — on (group_id, is_deleted)

#### Collection: `group_memberships`

| Field | Type | Description |
|-------|------|-------------|
| _id | UUID | Unique membership identifier |
| group_id | UUID | Group reference |
| user_id | UUID | User reference |
| role | string | admin or member |
| chat_enabled | bool | Chat permission flag |
| is_active | bool | Active status (false = left group) |

**Indexes:**
- `memberships_group_user_unique` — UNIQUE on (group_id, user_id)
- `memberships_group_active_idx` — on (group_id, is_active)

---

## Redis Usage

| DB | Service | Usage | Key Pattern(s) | TTL |
|----|---------|-------|---------------|-----|
| 0 | Identity Service | Refresh tokens, top tutors cache | `refresh:{jti}`, `marketplace:top_tutors` | 7d / 300s |
| 1 | Session Service | Nearby sessions cache, verified tutors | `nearby:{hash}`, `vt:*` | 60s / variable |
| 2 | Group Service | Reserved | — | — |
| 3 | Chat Service | Recent messages, online presence | `recent:{group_id}`, `online:{gid}:{uid}` | 600s / ~40s |
| 6 | Admin + Payment | Admin sessions, payment locks | `lock:payment:{key}` | variable |
| 7 | Notification Service | Unread counts, pub/sub, preferences | `unread:{uid}`, `prefs:{uid}` | 60s / variable |
| 8 | Recommendation Service | Recommendation caches | `rec:top`, `rec:trending`, `rec:subject:{s}` | 600s |

---

## Migration Commands

### Identity Service
```bash
cd identity_service && alembic upgrade head
```

### Group Service
```bash
cd group_service && alembic upgrade head
```

### Admin Service
```bash
cd admin_service && alembic upgrade head
```

### Payment Service
```bash
cd payment_service && alembic upgrade head
```

### Verification Service
```bash
cd verification_service && alembic upgrade head
```

### Notification Service
```bash
cd notification_service && alembic upgrade head
```

### Recommendation Service
```bash
cd recommendation_service && alembic upgrade head
```

### Session Service (MongoDB — no Alembic)
```bash
# Indexes created at application startup
uvicorn app.main:app --reload
```

### Chat Service (MongoDB — no Alembic)
```bash
# Indexes created at application startup
uvicorn app.main:app --reload
```

---

## Connection Details

### Host-Local Development
| Database | Connection String |
|----------|------------------|
| Identity PostgreSQL | `postgresql+asyncpg://studysync:studysync_dev@localhost:5442/identity_db` |
| Group PostgreSQL | `postgresql+asyncpg://studysync:studysync_dev@localhost:5433/group_db` |
| Admin PostgreSQL | `postgresql+asyncpg://studysync:studysync_dev@localhost:5437/admin_db` |
| Payment PostgreSQL | `postgresql+asyncpg://studysync:studysync_dev@localhost:5445/payment_db` |
| Verification PostgreSQL | `postgresql+asyncpg://studysync:studysync_dev@localhost:5446/verification_db` |
| Notification PostgreSQL | `postgresql+asyncpg://studysync:studysync_dev@localhost:5447/notification_db` |
| Recommendation PostgreSQL | `postgresql+asyncpg://studysync:studysync_dev@localhost:5448/recommendation_db` |
| MongoDB | `mongodb://localhost:27017` |
| Redis | `redis://localhost:6379` |

### Docker-Internal Development
Replace `localhost` with Docker service names (e.g., `postgres`, `postgres_group`, `mongo`, `redis`).
PostgreSQL internal ports are always `5432` inside Docker.