# StudySync — Microservices Learning Platform

> **A production-grade distributed backend ecosystem for collaborative learning, tutoring, sessions, group chat, payments, verification, notifications, recommendations, and platform administration.**

StudySync is built as **nine independently deployable FastAPI microservices** coordinated through PostgreSQL, MongoDB, Redis, Kafka (event-driven communication), JWT authentication, and WebSocket real-time messaging. The system is containerized via Docker Compose with health checks, service discovery, and resilient Kafka producers featuring circuit breakers, fallback queues, and retry workers.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Services Overview](#3-services-overview)
4. [Complete API Documentation](#4-complete-api-documentation)
5. [Database Documentation](#5-database-documentation)
6. [Kafka Architecture](#6-kafka-architecture)
7. [Tutor Verification Workflow](#7-tutor-verification-workflow)
8. [Session & Rating Workflow](#8-session--rating-workflow)
9. [Recommendation System](#9-recommendation-system)
10. [Authentication & Authorization](#10-authentication--authorization)
11. [Docker & Infrastructure](#11-docker--infrastructure)
12. [Environment Variables](#12-environment-variables)
13. [Local Development Setup](#13-local-development-setup)
14. [Troubleshooting Guide](#14-troubleshooting-guide)
15. [Testing](#15-testing)
16. [Production Recommendations](#16-production-recommendations)
17. [Project Folder Structure](#17-project-folder-structure)

---

## 1. Project Overview

### What is StudySync?

StudySync is a **distributed microservices platform** that enables collaborative learning through:
- **Tutor marketplace** — verified tutors create profiles, set hourly rates, offer expertise-based sessions
- **Session booking** — students discover and join free/paid study sessions with geospatial nearby search
- **Study groups** — create/manage study groups with membership controls and role-based permissions
- **Real-time chat** — WebSocket-powered group messaging with online presence tracking
- **Payments & wallets** — payment intents, wallet management, transaction history, refunds
- **Tutor verification** — document-based KYC workflow with admin approval/rejection
- **Recommendations** — AI-driven tutor ranking, trending, subject-based, and nearby recommendations
- **Notifications** — in-app notification system with preferences, templates, and WebSocket delivery
- **Platform administration** — admin RBAC, user management, moderation, analytics, audit trail, system settings

### Platform Capabilities

| Capability | Description |
|---|---|
| **User Management** | Registration, login, JWT access/refresh tokens, profile management |
| **Tutor Onboarding** | Document upload (identity proof, degrees, certificates), admin verification, KYC |
| **Session Management** | CRUD, geospatial nearby search, join/leave, status transitions |
| **Ratings & Reviews** | Post-session rating (1–5 scale), duplicate detection, event-driven propagation |
| **Study Groups** | Create/join/leave, role-based access (admin/moderator/member), kick/promote/demote |
| **Real-time Chat** | WebSocket messaging, group membership mirroring, online presence, message history |
| **Payments** | Create payment intent, confirm, refund, wallet top-up/withdraw, platform fee |
| **Notifications** | Event-driven in-app notifications, preferences, templates, WebSocket pub/sub |
| **Recommendations** | Top-ranked, trending, subject-based, nearby (Haversine), similar tutors, personalized |
| **Admin Operations** | Admin CRUD, user suspension, verification management, moderation, analytics, system settings |

### Technology Stack

| Component | Technology |
|---|---|
| **API Framework** | FastAPI (Python 3.12) |
| **Relational DB** | PostgreSQL 16 (7 dedicated instances) |
| **Document DB** | MongoDB 7 (2 instances) |
| **Cache** | Redis 7 (8 databases used across services) |
| **Message Broker** | Apache Kafka 7.5 (Confluent) + Zookeeper |
| **Containerization** | Docker Compose with health checks |
| **Authentication** | JWT (HS256) with refresh token rotation |
| **Real-time** | WebSocket via FastAPI WebSockets |
| **ORM/ODM** | SQLAlchemy 2.0 (async) + Motor (async MongoDB) |
| **Migrations** | Alembic (PostgreSQL) |
| **File Validation** | python-magic + aiofiles |
| **Kafka Resilience** | Custom circuit breaker, in-memory fallback queue, retry worker with exponential backoff |

---

## 2. System Architecture

### Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                              │
│         HTTP/JWT + WebSocket (Authorization: Bearer <token>)       │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────────────────────┐
│                    API GATEWAY / DIRECT SERVICE ACCESS              │
│         Services run on ports 8000–8008 on studysync bridge        │
└───┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬───────┘
    │      │      │      │      │      │      │      │      │
    ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
│IDNTY│ │SESSN│ │GROUP│ │CHAT │ │ADMIN│ │PAYMT│ │VERIF│ │NOTIF│ │RECMD│
│:8000│ │:8001│ │:8002│ │:8003│ │:8004│ │:8005│ │:8006│ │:8007│ │:8008│
└──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘
   │       │       │       │       │       │       │       │       │
   │  ┌────┘       │       │       │       │       │       │       │
   │  │   ┌────────┘       │       │       │       │       │       │
   │  │   │   ┌────────────┘       │       │       │       │       │
   │  │   │   │   ┌────────────────┘       │       │       │       │
   ▼  ▼   ▼   ▼   ▼                        ▼       ▼       ▼       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       KAFKA (Event Bus)                            │
│ Topics: USER_EVENTS, RATING_EVENTS, GROUP_EVENTS, CHAT_EVENTS,    │
│         PAYMENT_EVENTS, VERIFICATION_EVENTS, ADMIN_EVENTS          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐ ┌──────────┐ ┌─────────────────────────────────────────┐
│PostgreSQL│ │PostgreSQL│ │            REDIS (7 databases)          │
│ ×7 DBs   │ │ ×7 inst. │ │  DB0: Token/Identity                    │
│          │ │          │ │  DB1: Session nearby cache              │
│  7 DBs:  │ │          │ │  DB2: Group (configured)                │
│ identity │ │          │ │  DB3: Chat recent/presence              │
│ group    │ │          │ │  DB6: Admin + Payment                   │
│ admin    │ │          │ │  DB7: Notification unread/prefs/pub-sub │
│ payment  │ │  MONGO   │ │  DB8: Recommendation caches             │
│verificatn│ │  ×2 DBs  │ └─────────────────────────────────────────┘
│notificatn│ │          │
│recommend │ │ session  │
└──────────┘ │ chat     │
             └──────────┘
```

### Communication Patterns

| Pattern | Mechanism | Example |
|---|---|---|
| **REST API** | HTTP/JSON | Client ↔ Service |
| **Event-Driven** | Kafka Topics | Service → Kafka → Service |
| **WebSocket** | Persistent TCP | Chat Service ↔ Client |
| **Service Proxy** | HTTP (httpx) | Group → Session via internal endpoint |
| **Shared JWT** | HS256 encoded | Identity issues, all services validate |

### Data Ownership Model

| Storage | Owned By | Data |
|---|---|---|
| PostgreSQL `identity_db` | Identity Service | Users, tutor profiles |
| PostgreSQL `group_db` | Group Service | Groups, group members |
| PostgreSQL `admin_db` | Admin Service | Admin users, actions, settings |
| PostgreSQL `payment_db` | Payment Service | Payments, wallets, transactions |
| PostgreSQL `verification_db` | Verification Service | Verification requests, documents |
| PostgreSQL `notification_db` | Notification Service | Notifications, templates, preferences |
| PostgreSQL `recommendation_db` | Recommendation Service | Tutor metrics, scores, trending |
| MongoDB `session_db` | Session Service | Sessions, ratings, verified tutors |
| MongoDB `chat_db` | Chat Service | Messages, group memberships (mirror) |
| Redis DB 0–8 | Various | Tokens, caches, presence, flags |

---

## 3. Services Overview

### 3.1 Identity Service (`:8000`)

**Purpose:** Authentication, user management, tutor profiles, JWT issuance

**Technologies:** FastAPI, PostgreSQL (`identity_db`), Redis DB 0, Kafka

**Responsibilities:**
- User registration (email + bcrypt password)
- JWT access/refresh token issuance and rotation
- Refresh token revocation via Redis JTI store
- Tutor profile management (create, update, soft-delete)
- Tutor verification via admin API key
- Leaderboard with Redis cache
- Tutor search with expertise/rating/verified filters
- Rating event consumption → updates `rating_sum`/`total_reviews`

**Kafka Events Produced:**
| Event | Topic | When |
|---|---|---|
| `USER_CREATED` | `USER_EVENTS` | User registration |
| `TUTOR_VERIFIED` | `USER_EVENTS` | Admin verifies tutor |
| `TUTOR_APPLICATION_SUBMITTED` | `VERIFICATION_EVENTS` | Tutor applies |

**Kafka Events Consumed:**
| Event | Topic | Action |
|---|---|---|
| `RATING_SUBMITTED` / `SESSION_RATED` | `RATING_EVENTS` | Updates tutor rating_sum/total_reviews |
| `TUTOR_VERIFIED` | `USER_EVENTS` | Sets role=tutor, is_verified_tutor=True |
| `TUTOR_REJECTED` | `USER_EVENTS` | Logs rejection |

**APIs:** See [Section 4.1](#41-identity-service)

---

### 3.2 Session Service (`:8001`)

**Purpose:** Session lifecycle, geospatial search, participant management, ratings

**Technologies:** FastAPI, MongoDB (`session_db`), Redis DB 1, Kafka

**Responsibilities:**
- Session CRUD (free/paid types)
- Geospatial nearby search (MongoDB `2dsphere` index)
- Participant join/leave (free sessions via API, paid via Kafka payment events)
- Session status transitions (scheduled → active → completed / cancelled)
- Rating submission with duplicate detection (Redis)
- Rating event publishing to Kafka
- Verified tutor read model (consumes TUTOR_VERIFIED)
- Configurable standalone mode (auth + Kafka disabled)

**Kafka Events Produced:**
| Event | Topic | When |
|---|---|---|
| `RATING_SUBMITTED` / `SESSION_RATED` | `RATING_EVENTS` | Student submits rating |

**Kafka Events Consumed:**
| Event | Topic | Action |
|---|---|---|
| `PAYMENT_SUCCESS` | `PAYMENT_EVENTS` | Adds participant to paid session |
| `TUTOR_VERIFIED` | `USER_EVENTS` | Upserts verified_tutors (is_verified=true, status=active) |
| `TUTOR_REJECTED` | `USER_EVENTS` | Marks verified_tutors (is_verified=false, status=rejected) |
| `TUTOR_SUSPENDED` | `USER_EVENTS` | Marks verified_tutors (is_verified=false, status=suspended) |

**APIs:** See [Section 4.2](#42-session-service)

---

### 3.3 Group Service (`:8002`)

**Purpose:** Study group management, membership, permissions, group-session linking

**Technologies:** FastAPI, PostgreSQL (`group_db`), Redis DB 2, Kafka

**Responsibilities:**
- Group CRUD with ownership tracking
- Member management (join, leave, kick, promote/demote)
- Role-based permissions (admin/moderator/member)
- Internal membership/permission check endpoints (consumed by Chat Service)
- Proxy to Session Service for group-session linking
- Kafka event publishing on group changes

**Kafka Events Produced:**
| Event | Topic | When |
|---|---|---|
| `GROUP_CREATED` | `GROUP_EVENTS` | Group creation |
| `GROUP_DELETED` | `GROUP_EVENTS` | Group deletion |
| `USER_JOINED_GROUP` | `GROUP_EVENTS` | User joins group |
| `USER_LEFT_GROUP` | `GROUP_EVENTS` | User leaves group |

**APIs:** See [Section 4.3](#43-group-service)

---

### 3.4 Chat Service (`:8003`)

**Purpose:** Real-time group messaging, WebSocket delivery, online presence

**Technologies:** FastAPI, MongoDB (`chat_db`), Redis DB 3, Kafka, WebSocket

**Responsibilities:**
- Message CRUD (send, edit, soft-delete)
- WebSocket endpoint for real-time messaging (`/groups/{group_id}/ws?token=<jwt>`)
- Online presence tracking (Redis)
- Unread message counts per user
- Read receipts
- Group membership mirror via Kafka GROUP_EVENTS consumer
- Recent message cache (Redis)
- JWT authentication + membership validation on WebSocket connect

**Kafka Events Produced:**
| Event | Topic | When |
|---|---|---|
| `CHAT_MESSAGE_SENT` | `CHAT_EVENTS` | Message sent |
| `CHAT_MESSAGE_DELETED` | `CHAT_EVENTS` | Message deleted |

**Kafka Events Consumed:**
| Event | Topic | Action |
|---|---|---|
| `GROUP_CREATED` | `GROUP_EVENTS` | Creates group membership mirror |
| `GROUP_DELETED` | `GROUP_EVENTS` | Removes group membership mirror |
| `USER_JOINED_GROUP` | `GROUP_EVENTS` | Adds user to membership mirror |
| `USER_LEFT_GROUP` | `GROUP_EVENTS` | Removes user from membership mirror |

**APIs:** See [Section 4.4](#44-chat-service)

---

### 3.5 Admin Service (`:8004`)

**Purpose:** Platform administration, moderation, analytics, settings, audit trail

**Technologies:** FastAPI, PostgreSQL (`admin_db`), Redis DB 6, Kafka, MongoDB (reads session_db)

**Responsibilities:**
- Admin authentication (separate JWT flow from user auth)
- Admin user management (create, list, deactivate, password reset)
- Platform user management (list, suspend, activate students/tutors)
- Tutor verification management (list pending, approve/reject, bulk approve)
- Content moderation (reports, chat message moderation, session moderation)
- System management (settings CRUD, maintenance mode, health checks, cache management, backups, audit log, broadcast)
- Analytics (overview, users, sessions, revenue, platform health)
- Direct read access to identity_db and group_db via configured URLs
- Direct read access to session MongoDB
- Security middleware with rate limiting
- Super admin auto-creation on startup

**Kafka Events Produced:**
| Event | Topic | When |
|---|---|---|
| `ADMIN_EVENTS` (lifecycle/maintenance/cache/backup/broadcast) | `ADMIN_EVENTS` | Various admin actions |

**APIs:** See [Section 4.5](#45-admin-service)

---

### 3.6 Payment Service (`:8005`)

**Purpose:** Payment processing, wallet management, transactions, refunds

**Technologies:** FastAPI, PostgreSQL (`payment_db`), Redis DB 6, Kafka

**Responsibilities:**
- Payment intent creation
- Payment confirmation
- Payment history and details
- Refund processing
- Wallet balance management
- Wallet top-up and withdrawal
- Transaction history
- Platform fee calculation (configurable percentage)
- Kafka event publishing on payment success/failure

**Kafka Events Produced:**
| Event | Topic | When |
|---|---|---|
| `PAYMENT_SUCCESS` | `PAYMENT_EVENTS` | Payment confirmed |
| `PAYMENT_FAILED` | `PAYMENT_EVENTS` | Payment failed |

**APIs:** See [Section 4.6](#46-payment-service)

---

### 3.7 Verification Service (`:8006`)

**Purpose:** Tutor document verification, KYC, admin review workflow

**Technologies:** FastAPI, PostgreSQL (`verification_db`), Redis DB 0, Kafka

**Responsibilities:**
- Verification request submission with document upload
- Document storage with MIME type validation (image/jpeg, image/png, application/pdf)
- File size validation (max 5MB per file)
- Admin review workflow (pending → under_review → verified / rejected)
- Tutor application endpoint (bio, subjects, experience, identity_proof, degree, certificates)
- Verification status cache (Redis, TTL 1 hour)
- Kafka event publishing for verification state changes
- User events consumer for profile state tracking

**Kafka Events Produced:**
| Event | Topic | When |
|---|---|---|
| `VERIFICATION_SUBMITTED` | `VERIFICATION_EVENTS` | Request submitted |
| `VERIFICATION_APPROVED` | `VERIFICATION_EVENTS` | Admin approves |
| `VERIFICATION_REJECTED` | `VERIFICATION_EVENTS` | Admin rejects |
| `TUTOR_VERIFIED` | `USER_EVENTS` | Admin approves tutor |
| `TUTOR_REJECTED` | `USER_EVENTS` | Admin rejects tutor |
| `TUTOR_APPLICATION_SUBMITTED` | `VERIFICATION_EVENTS` | Tutor application |

**Kafka Events Consumed:**
| Event | Topic | Action |
|---|---|---|
| `USER_EVENTS` | `USER_EVENTS` | Tracks user profile state |

**APIs:** See [Section 4.7](#47-verification-service)

---

### 3.8 Notification Service (`:8007`)

**Purpose:** In-app notification system with preferences, templates, WebSocket delivery

**Technologies:** FastAPI, PostgreSQL (`notification_db`), Redis DB 7, Kafka, WebSocket

**Responsibilities:**
- Event-driven notification creation from all upstream Kafka topics
- Notification preferences per user (opt-in/out per event type)
- Notification templates per event type
- Unread count caching (Redis, TTL 60s)
- WebSocket pub/sub for real-time notification delivery
- Scalable WebSocket manager with Redis pub/sub

**Kafka Events Consumed:** (8 topics)
| Topic | Events Consumed |
|---|---|
| `USER_EVENTS` | USER_CREATED, TUTOR_VERIFIED, USER_REGISTERED |
| `SESSION_EVENTS` | Session lifecycle events |
| `GROUP_EVENTS` | Group lifecycle events |
| `PAYMENT_EVENTS` | Payment lifecycle events |
| `VERIFICATION_EVENTS` | Verification lifecycle events |
| `CHAT_EVENTS` | CHAT_MESSAGE_SENT, CHAT_MESSAGE_DELETED |
| `RECOMMENDATION_EVENTS` | TUTOR_RECOMMENDED |
| `RATING_EVENTS` | Rating lifecycle events |

**APIs:** See [Section 4.8](#48-notification-service)

---

### 3.9 Recommendation Service (`:8008`)

**Purpose:** Tutor ranking, search, trending, nearby, subject-based, similar, personalized recommendations

**Technologies:** FastAPI, PostgreSQL (`recommendation_db`), Redis DB 8, Kafka

**Responsibilities:**
- Top ranked tutors by recommendation score
- Trending tutors by trend/growth score
- Subject-based filtering with score ordering
- Geospatial nearby search (Haversine formula in SQL — no PostGIS required)
- Similar tutors based on subject overlap and rating proximity
- Personalized recommendations (currently falls back to global top)
- Tutor metric management (average rating, sessions completed, activity score)
- Score calculation: `Score = (0.7 × avg_rating / 5.0) + (0.3 × activity_score)`
- Redis caching for all recommendation endpoints (configurable TTL, default 600s)
- Admin recalculation endpoint (trigger score recomputation for specific/all tutors)
- Admin cache refresh endpoint (clear Redis cache keys)
- Readiness health check (PostgreSQL + Redis connectivity)
- Rating event consumption → updates tutor metrics and scores
- User event consumption → marks tutors as verified/rejected in metrics

**Kafka Events Consumed:**
| Event | Topic | Action |
|---|---|---|
| `RATING_SUBMITTED` / `SESSION_RATED` | `RATING_EVENTS` | Updates average_rating, recalculates score |
| `TUTOR_VERIFIED` | `USER_EVENTS` | Sets is_verified=True in tutor_metrics |
| `TUTOR_REJECTED` | `USER_EVENTS` | Sets is_verified=False, score=-1.0 |

**APIs:** See [Section 4.9](#49-recommendation-service)

---

## 4. Complete API Documentation

### 4.1 Identity Service

**Base URL:** `http://localhost:8000/api/v1`

#### Authentication

---

##### `POST /auth/register`

Register a new user.

**Authentication:** None

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```
**Validation:** `password` min 8, max 128 characters. `email` must be valid email format.

**Response `201`:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "role": "user",
  "is_active": true,
  "last_known_latitude": null,
  "last_known_longitude": null,
  "created_at": "2026-04-12T10:00:00Z"
}
```

**Kafka Effect:** Publishes `USER_CREATED` to `USER_EVENTS`.

---

##### `POST /auth/login`

Authenticate and receive JWT tokens.

**Authentication:** None

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response `200`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Behavior:** Access token TTL = `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`. Refresh token stored in Redis with JTI for revocation.

---

##### `POST /auth/refresh`

Refresh an expired access token using a refresh token.

**Authentication:** None

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response `200`:** Returns new `access_token` and `refresh_token` (rotation).

---

##### `POST /auth/logout`

Revoke refresh token.

**Authentication:** None

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response:** `204 No Content`

---

##### `GET /auth/profile`

Get current authenticated user profile with tutor info.

**Authentication:** JWT required

**Response `200`:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "role": "tutor",
  "is_active": true,
  "last_known_latitude": 40.7128,
  "last_known_longitude": -74.006,
  "created_at": "2026-04-12T10:00:00Z",
  "tutor_profile": {
    "id": "uuid",
    "bio": "Experienced math tutor",
    "expertise": ["Mathematics", "Physics"],
    "hourly_rate": 25.0,
    "is_verified": true,
    "rating_sum": 45,
    "total_reviews": 12
  }
}
```

---

##### `PATCH /auth/profile`

Update user profile (location).

**Authentication:** JWT required

**Request Body:**
```json
{
  "last_known_latitude": 40.7128,
  "last_known_longitude": -74.006
}
```

**Response `200`:** Returns updated `UserProfileRead`.

#### Tutors

---

##### `POST /tutors/become`

Become a tutor (creates tutor profile, updates user role to tutor).

**Authentication:** JWT required

**Request Body:**
```json
{
  "bio": "Experienced in Mathematics and Physics",
  "expertise": ["Mathematics", "Physics"],
  "hourly_rate": 25.0
}
```
**Validation:** `expertise` max 50 tags, each max 128 chars. `hourly_rate` ge 0.

**Response `201`:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "bio": "Experienced in Mathematics and Physics",
  "expertise": ["Mathematics", "Physics"],
  "hourly_rate": 25.0,
  "rating_sum": 0,
  "total_reviews": 0,
  "is_verified": false
}
```

---

##### `POST /tutors/apply`

Submit a tutor application with document uploads (for verification flow). Accepts multipart form data.

**Authentication:** JWT required

**Form Fields:**
- `bio` (str, required)
- `subjects` (str, comma-separated, required)
- `hourly_rate` (float, required)
- `identity_proof` (file, required) — JPEG/PNG/PDF, max 5MB
- `highest_degree` (file, required) — JPEG/PNG/PDF, max 5MB
- `extra_certificates` (file[], optional) — JPEG/PNG/PDF, max 5MB each

**Response `202`:**
```json
{
  "success": true,
  "message": "Tutor application submitted successfully",
  "verification_status": "PENDING"
}
```

**Kafka Effect:** Publishes `TUTOR_APPLICATION_SUBMITTED` to `VERIFICATION_EVENTS`.

---

##### `GET /tutors/leaderboard`

Get top ranked tutors.

**Authentication:** None

**Query Parameters:** `limit` (int, default 20, max 50)

**Response `200`:**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "bio": "...",
    "expertise": ["Mathematics"],
    "hourly_rate": 30.0,
    "rating_sum": 85,
    "total_reviews": 20,
    "is_verified": true
  }
]
```

---

##### `GET /tutors/search`

Search tutors with filters.

**Authentication:** JWT required

**Query Parameters:**
- `expertise` (string[], optional) — filter by expertise tags
- `min_rating` (float, 0–5, optional)
- `verified_only` (bool, default false)
- `limit` (int, default 20, max 100)
- `offset` (int, default 0)

---

##### `PATCH /tutors/profile`

Update own tutor profile.

**Authentication:** JWT required

**Request Body:**
```json
{
  "bio": "Updated bio",
  "expertise": ["Mathematics", "Chemistry"],
  "hourly_rate": 30.0
}
```

---

##### `DELETE /tutors/profile`

Soft-delete own tutor profile.

**Authentication:** JWT required

---

##### `GET /tutors/{tutor_id}`

Get specific tutor profile by ID.

**Authentication:** JWT required

---

##### `GET /tutors/{tutor_id}/stats`

Get tutor statistics with computed average rating.

**Authentication:** JWT required

**Response `200`:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "bio": "...",
  "expertise": ["Mathematics"],
  "hourly_rate": 25.0,
  "is_verified": true,
  "average_rating": 4.2,
  "total_reviews": 12,
  "rating_sum": 50
}
```

---

##### `POST /tutors/{user_id}/verify`

Admin verifies a tutor. Requires `X-Admin-API-Key` header.

**Authentication:** X-Admin-API-Key header (not JWT)

**Response `200`:** Returns verified `TutorProfileRead`.

**Kafka Effect:** Publishes `TUTOR_VERIFIED` to `USER_EVENTS`.

#### Health

---

##### `GET /health`

```json
{"status": "ok"}
```

##### `GET /health/kafka`

```json
{
  "circuit_breaker": "closed",
  "fallback_queue_size": 0
}
```

---

### 4.2 Session Service

**Base URL:** `http://localhost:8001/api/v1`

#### Sessions

---

##### `POST /sessions/`

Create a new session.

**Authentication:** JWT required

**Request Body:**
```json
{
  "title": "Calculus Study Session",
  "description": "Group study for Calculus II",
  "session_type": "free",
  "price": 0,
  "max_participants": 10,
  "scheduled_time": "2026-05-01T14:00:00Z",
  "latitude": 40.7128,
  "longitude": -74.006,
  "subject_tags": ["Mathematics", "Calculus"]
}
```

**Response `201`:** Returns `SessionRead`.

---

##### `GET /sessions/nearby`

Find sessions near a location.

**Authentication:** JWT required

**Query Parameters:**
- `latitude` (float, required, -90 to 90)
- `longitude` (float, required, -180 to 180)
- `radius_km` (float, default 10, max 100)
- `limit` (int, default 20, max 100)
- `offset` (int, default 0)
- `session_type` ("free" | "paid", optional)
- `min_price` / `max_price` (float, optional)
- `subject_tags` (string[], optional)

---

##### `GET /sessions/my`

List sessions hosted by current user.

**Authentication:** JWT required

---

##### `GET /sessions/{session_id}`

Get session details.

**Authentication:** JWT required

---

##### `PATCH /sessions/{session_id}`

Update session details.

**Authentication:** JWT required (host only)

---

##### `PATCH /sessions/{session_id}/cancel`

Cancel a session.

**Authentication:** JWT required (host only)

---

##### `PATCH /sessions/{session_id}/status`

Update session status.

**Authentication:** JWT required (host only)

**Request Body:**
```json
{
  "status": "completed"
}
```

Valid statuses: `scheduled`, `active`, `completed`, `cancelled`.

---

##### `POST /sessions/{session_id}/join`

Join a free session.

**Authentication:** JWT required

**Behavior:** Adds user to participants list. For paid sessions, use Payment Service and Kafka.

---

##### `POST /sessions/{session_id}/leave`

Leave a session.

**Authentication:** JWT required

---

##### `GET /sessions/{session_id}/participants`

List session participants.

**Authentication:** JWT required

#### Ratings

---

##### `POST /sessions/{session_id}/ratings`

Submit a rating for a session.

**Authentication:** JWT required (student must be participant, session must be completed)

**Request Body:**
```json
{
  "score": 5,
  "comment": "Excellent session!"
}
```

**Validation:** `score` 1–5. Duplicate ratings detected via Redis + unique MongoDB index.

**Kafka Effect:** Publishes `RATING_SUBMITTED` to `RATING_EVENTS`.

---

##### `GET /sessions/{session_id}/ratings`

List ratings for a session.

**Authentication:** JWT required

**Query Parameters:** `limit` (default 50, max 100), `offset` (default 0)

#### Health

---

##### `GET /health`

```json
{"status": "ok"}
```

##### `GET /health/ready`

```json
{
  "status": "ready",
  "auth_enabled": true,
  "kafka_enabled": true,
  "standalone_mode": false,
  "test_user_id": "not-set"
}
```

---

### 4.3 Group Service

**Base URL:** `http://localhost:8002/api/v1`

#### Groups

---

##### `POST /groups/`

Create a study group.

**Authentication:** JWT required

**Request Body:**
```json
{
  "name": "Calculus Study Group",
  "description": "Group for studying Calculus II",
  "is_private": false,
  "max_members": 50
}
```

**Kafka Effect:** Publishes `GROUP_CREATED` to `GROUP_EVENTS`.

---

##### `GET /groups/`

List groups with search.

**Authentication:** JWT required

**Query Parameters:** `limit` (default 20, max 100), `offset` (default 0), `search` (string, optional)

---

##### `GET /groups/{group_id}`

Get group details.

**Authentication:** JWT required

---

##### `PATCH /groups/{group_id}`

Update group details.

**Authentication:** JWT required (owner only)

---

##### `DELETE /groups/{group_id}`

Delete a group.

**Authentication:** JWT required (owner only)

**Kafka Effect:** Publishes `GROUP_DELETED` to `GROUP_EVENTS`.

#### Members

---

##### `POST /groups/{group_id}/join`

Join a group.

**Authentication:** JWT required

**Kafka Effect:** Publishes `USER_JOINED_GROUP` to `GROUP_EVENTS`.

---

##### `POST /groups/{group_id}/leave`

Leave a group.

**Authentication:** JWT required

**Kafka Effect:** Publishes `USER_LEFT_GROUP` to `GROUP_EVENTS`.

---

##### `GET /groups/{group_id}/members`

List group members.

**Authentication:** JWT required

**Query Parameters:** `limit` (default 50, max 100), `offset` (default 0)

---

##### `POST /groups/{group_id}/kick`

Kick a member from group.

**Authentication:** JWT required (admin/moderator role)

**Request Body:**
```json
{
  "user_id": "uuid"
}
```

---

##### `POST /groups/{group_id}/promote`

Promote member to moderator.

**Authentication:** JWT required (admin role)

**Request Body:**
```json
{
  "user_id": "uuid"
}
```

---

##### `POST /groups/{group_id}/demote`

Demote moderator to member.

**Authentication:** JWT required (admin role)

**Request Body:**
```json
{
  "user_id": "uuid"
}
```

#### User-scoped

---

##### `GET /users/me/groups`

List groups the current user belongs to.

**Authentication:** JWT required

#### Internal (Service-to-Service)

---

##### `GET /internal/groups/{group_id}/members/{user_id}`

Check if user is a group member.

**Authentication:** None (internal)

**Response:**
```json
{
  "is_member": true,
  "role": "member"
}
```

---

##### `GET /internal/groups/{group_id}/permissions/{user_id}`

Check user permissions in group.

**Authentication:** None (internal)

---

##### `GET /internal/groups/{group_id}/sessions`

Proxy to Session Service — get sessions tagged with this group.

---

##### `POST /internal/groups/{group_id}/sessions/{session_id}`

Proxy to Session Service — attach session to group.

#### Health

---

##### `GET /health`

```json
{"status": "ok"}
```

---

### 4.4 Chat Service

**Base URL:** `http://localhost:8003/api/v1`

#### Messages

---

##### `POST /groups/{group_id}/messages`

Send a message to a group.

**Authentication:** JWT required (validated membership)

**Request Body:**
```json
{
  "content": "Hello everyone!",
  "message_type": "text"
}
```

**Response:** Returns created message.

**Kafka Effect:** Publishes `CHAT_MESSAGE_SENT` to `CHAT_EVENTS`.

---

##### `GET /groups/{group_id}/messages`

Get message history for a group.

**Authentication:** JWT required

**Query Parameters:** `limit`, `offset`, `before` (timestamp)

---

##### `DELETE /messages/{message_id}`

Soft-delete a message.

**Authentication:** JWT required (sender or admin)

---

##### `PATCH /messages/{message_id}`

Edit a message.

**Authentication:** JWT required (sender only)

#### Presence & Read

---

##### `GET /groups/{group_id}/online`

Get online users in a group.

**Authentication:** JWT required

---

##### `POST /groups/{group_id}/read`

Mark messages as read. Returns updated unread count.

---

##### `GET /groups/{group_id}/unread-count`

Get unread message count for user in group.

#### WebSocket

---

##### `WS /groups/{group_id}/ws?token=<jwt>`

WebSocket endpoint for real-time messaging.

**Authentication:** JWT token as query parameter. Validates membership via Group Service internal endpoint.

**Behavior:** On connect, user is added to online presence. On disconnect, user is removed. Messages received are broadcast to all connected clients in the same group.

#### Health

---

##### `GET /health`

```json
{"status": "ok"}
```

---

### 4.5 Admin Service

**Base URL:** `http://localhost:8004/api/v1`

#### Authentication

---

##### `POST /auth/login`

Admin login.

**Authentication:** None

**Response:** Returns JWT access + refresh tokens (admin-specific).

---

##### `GET /auth/profile`

Get admin profile.

**Authentication:** Admin JWT required

---

##### `POST /auth/logout`

Admin logout.

#### Admin Management

---

- `POST /admin-management/create` — Create admin user
- `GET /admin-management/list` — List admin users
- `GET /admin-management/{admin_id}` — Get admin details
- `POST /admin-management/{admin_id}/deactivate` — Deactivate admin
- `POST /admin-management/{admin_id}/activate` — Activate admin
- `POST /admin-management/change-password` — Change own password
- `POST /admin-management/{admin_id}/reset-password` — Reset another admin's password

#### User Management

---

- `GET /admin/users` — List platform users (with filters)
- `GET /admin/users/{user_id}` — Get user details
- `POST /admin/users/{user_id}/suspend` — Suspend user
- `POST /admin/users/{user_id}/activate` — Activate user
- `GET /admin/tutors` — List tutors
- `GET /admin/students` — List students

#### Verification Management

---

- `GET /verification/pending` — List pending verification requests
- `GET /verification/stats` — Verification statistics
- `GET /verification/{verification_id}` — Get verification detail
- `POST /verification/{verification_id}/approve` — Approve verification
- `POST /verification/{verification_id}/reject` — Reject verification
- `GET /verification/tutor/{tutor_id}/history` — Tutor verification history
- `POST /verification/bulk-approve` — Bulk approve verifications

#### Moderation

---

- Reports management
- Chat message moderation
- Session moderation
- Bulk moderation actions

#### System

---

- Settings management (CRUD platform settings)
- Health checks (own + dependency service health)
- Service status monitoring
- Platform statistics
- Maintenance mode toggling
- Backup management
- Cache management (clear Redis caches)
- Audit log viewing
- Broadcast messaging

#### Analytics

---

- `GET /analytics/overview` — Platform overview metrics
- `GET /analytics/users` — User analytics
- `GET /analytics/sessions` — Session analytics
- `GET /analytics/revenue` — Revenue analytics
- `GET /analytics/platform-health` — Platform health metrics

#### Health

---

##### `GET /health`

```json
{"status": "ok"}
```

##### `GET /health/kafka`

```json
{
  "circuit_breaker": "closed",
  "fallback_queue_size": 0
}
```

##### `GET /health/dependencies`

```json
{
  "admin_db": "ok",
  "identity_service": "ok",
  "group_service": "ok"
}
```

---

### 4.6 Payment Service

**Base URL:** `http://localhost:8005/api/v1`

#### Payments

---

##### `POST /payments/create-intent`

Create a payment intent.

**Request Body:**
```json
{
  "amount": 25.0,
  "currency": "USD",
  "session_id": "uuid"
}
```

---

##### `POST /payments/confirm`

Confirm a payment.

**Request Body:**
```json
{
  "payment_intent_id": "uuid"
}
```

---

##### `GET /payments/{payment_id}`

Get payment details.

---

##### `POST /payments/{payment_id}/refund`

Refund a payment.

#### Wallet

---

##### `GET /wallet/balance`

Get wallet balance.

---

##### `GET /wallet/transactions`

Get transaction history.

---

##### `POST /wallet/add-money`

Add money to wallet.

---

##### `POST /wallet/withdraw`

Withdraw money from wallet.

#### Health

---

##### `GET /health`

```json
{"status": "ok"}
```

---

### 4.7 Verification Service

**Base URL:** `http://localhost:8006/api/v1`

#### User Verification

---

##### `POST /verification/submit`

Submit a verification request.

**Authentication:** JWT required

**Request Body:**
```json
{
  "request_type": "tutor_application"
}
```

**Response `201`:** Returns verification request with status `pending`.

---

##### `POST /verification/documents`

Upload document to active verification request.

**Authentication:** JWT required

**Form Data:** `file` (UploadFile), `document_type` (str)

---

##### `GET /verification/status`

Get latest verification status (cached in Redis).

**Authentication:** JWT required

---

##### `GET /verification/history`

Get all past verification requests.

**Authentication:** JWT required

---

##### `GET /verification/documents`

Get documents from latest verification request.

**Authentication:** JWT required

#### Tutor Application

---

##### `POST /verification/tutor-application`

Submit a complete tutor onboarding application (multipart form).

**Authentication:** JWT required

**Form Fields:**
- `bio` (str, required)
- `subjects` (str, comma-separated, required)
- `experience_years` (int, required)
- `hourly_rate` (float, required)
- `identity_proof` (file, required) — JPEG/PNG/PDF, max 5MB
- `highest_degree` (file, required) — JPEG/PNG/PDF, max 5MB
- `extra_certificates` (file[], optional) — JPEG/PNG/PDF, max 5MB each

**Response `202`:**
```json
{
  "success": true,
  "message": "Tutor application submitted successfully",
  "verification_status": "PENDING"
}
```

**Kafka Effect:** Publishes `TUTOR_APPLICATION_SUBMITTED` to `VERIFICATION_EVENTS`.

#### Admin Verification

---

##### `GET /admin/verification/`

List all verification requests (admin).

**Authentication:** Admin JWT required

**Query Parameters:** `page`, `per_page`, `status` filter

---

##### `GET /admin/verification/pending`

List pending requests.

---

##### `GET /admin/verification/{request_id}`

Get verification detail with documents.

---

##### `POST /admin/verification/{request_id}/review`

Mark as under review.

---

##### `POST /admin/verification/{request_id}/approve`

Approve verification. Publishes `TUTOR_VERIFIED` to `USER_EVENTS`.

---

##### `POST /admin/verification/{request_id}/reject`

Reject verification with reason. Publishes `TUTOR_REJECTED` to `USER_EVENTS`.

#### Health

---

##### `GET /health`

```json
{"status": "ok"}
```

##### `GET /health/kafka`

```json
{
  "connected": true,
  "status": "ok"
}
```

---

### 4.8 Notification Service

**Base URL:** `http://localhost:8007/api/v1`

#### Notifications

---

##### `GET /notifications`

List notifications for current user.

**Authentication:** JWT required

---

##### `GET /notifications/unread`

Get unread notifications.

---

##### `PATCH /notifications/{notification_id}/read`

Mark single notification as read.

---

##### `PATCH /notifications/read`

Mark all notifications as read.

---

##### `DELETE /notifications/{notification_id}`

Delete a notification.

#### Preferences

---

##### `GET /preferences`

Get notification preferences.

---

##### `PUT /preferences`

Update notification preferences (opt-in/out per event type).

#### Templates

---

##### `GET /templates`

List notification templates.

---

##### `POST /templates`

Create a notification template.

---

##### `GET /templates/{event_type}`

Get template for a specific event type.

#### Health

---

##### `GET /health`

```json
{"status": "ok"}
```

---

### 4.9 Recommendation Service

**Base URL:** `http://localhost:8008/api/v1/recommendations`

#### Public Endpoints

---

##### `GET /top`

Get top ranked tutors.

**Query Parameters:** `limit` (int, default 10, max 50)

**Response:**
```json
[
  {
    "tutor_id": "uuid",
    "score": 0.85,
    "subjects": ["Mathematics", "Physics"]
  }
]
```

**Cache:** Redis key `rec:top:{limit}`, TTL 600s.

---

##### `GET /trending`

Get trending tutors.

**Response:**
```json
[
  {
    "tutor_id": "uuid",
    "trend_score": 0.92
  }
]
```

**Cache:** Redis key `rec:trending`, TTL 3600s.

---

##### `GET /subject/{subject}`

Get recommendations by subject.

**Cache:** Redis key `rec:subject:{subject}`, TTL 600s.

---

##### `GET /search`

Search and filter recommendations.

**Query Parameters:**
- `subjects` (string[], optional)
- `min_rating` (float, 0–5, optional)
- `is_verified` (bool, optional)
- `page` (int, default 1)
- `per_page` (int, default 20, max 100)

---

##### `GET /nearby`

Get nearby tutors (Haversine distance).

**Query Parameters:** `lat` (float), `lon` (float), `radius` (int, km, default 10)

---

##### `GET /user/{user_id}`

Get personalized recommendations (currently falls back to top-ranked).

**Authentication:** JWT required (user_id must match token sub)

---

##### `GET /tutor/{tutor_id}/similar`

Get similar tutors.

**Query Parameters:** `limit` (int, default 5, max 20)

---

##### `GET /tutor/{tutor_id}`

Get tutor metrics.

#### Admin Endpoints

---

##### `POST /admin/recalculate`

Trigger score recalculation.

**Query Parameters:** `tutor_id` (UUID, optional — if omitted, recalculates all)

---

##### `POST /admin/cache/refresh`

Clear recommendation caches.

**Query Parameters:** `target` ("top", "trending", or "all", required)

#### Health

---

##### `GET /health`

```json
{"status": "ok"}
```

##### `GET /health/ready`

Deep health check:
```json
{
  "postgres": "healthy",
  "redis": "healthy",
  "status": "ok"
}
```

---

## 5. Database Documentation

### 5.1 PostgreSQL Schemas

#### Identity Database (`identity_db`)

**Table: `users`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | User identifier |
| `email` | VARCHAR(320) | UNIQUE, NOT NULL, INDEX | User email |
| `password_hash` | VARCHAR(255) | NOT NULL | bcrypt hash |
| `role` | VARCHAR(20) | NOT NULL, default 'user' | `user` or `tutor` |
| `is_active` | BOOLEAN | NOT NULL, default true | Account active flag |
| `is_verified_tutor` | BOOLEAN | nullable | Tutor verification flag |
| `last_known_latitude` | FLOAT | nullable | User's last known lat |
| `last_known_longitude` | FLOAT | nullable | User's last known lng |
| `created_at` | TIMESTAMPTZ | NOT NULL, server default now() | Record creation time |

**Table: `tutor_profiles`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Profile identifier |
| `user_id` | UUID | FK → users.id (CASCADE), UNIQUE, INDEX | User reference |
| `bio` | TEXT | nullable | Tutor biography |
| `expertise` | VARCHAR(128)[] | NOT NULL | Array of expertise tags |
| `hourly_rate` | NUMERIC(12,2) | NOT NULL, default 0 | Hourly rate in currency |
| `rating_sum` | INTEGER | NOT NULL, default 0 | Sum of all ratings |
| `total_reviews` | INTEGER | NOT NULL, default 0 | Total review count |
| `is_verified` | BOOLEAN | NOT NULL, default false | Admin verification flag |
| `is_active` | BOOLEAN | NOT NULL, default true | Soft delete flag |

**Relationships:**
- `users` 1:1 `tutor_profiles` (via `user_id` FK)

---

#### Group Database (`group_db`)

**Table: `groups`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Group identifier |
| `name` | VARCHAR(200) | NOT NULL, INDEX | Group name |
| `description` | TEXT | nullable | Group description |
| `owner_id` | UUID | NOT NULL, INDEX | Creator's user ID |
| `is_private` | BOOLEAN | NOT NULL, default false | Private group flag |
| `max_members` | INTEGER | NOT NULL, default 50 | Maximum members |
| `is_active` | BOOLEAN | NOT NULL, default true | Active flag |
| `chat_enabled` | BOOLEAN | NOT NULL, default true | Chat feature flag |
| `created_at` | TIMESTAMPTZ | NOT NULL, server default now() | Creation time |

**Table: `group_members`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Member record identifier |
| `group_id` | UUID | FK → groups.id (CASCADE), INDEX | Group reference |
| `user_id` | UUID | NOT NULL, INDEX | User reference |
| `role` | VARCHAR(20) | NOT NULL, default 'member' | `admin`, `moderator`, `member` |
| `joined_at` | TIMESTAMPTZ | NOT NULL, server default now() | Join time |

**Constraints:** UNIQUE (`group_id`, `user_id`)

---

#### Admin Database (`admin_db`)

**Table: `admin_user`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Admin identifier |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | Admin email |
| `password_hash` | VARCHAR(255) | NOT NULL | bcrypt hash |
| `full_name` | VARCHAR(255) | NOT NULL | Admin full name |
| `role` | VARCHAR(50) | NOT NULL | `admin` or `super_admin` |
| `permissions` | JSONB | NOT NULL | Permissions array |
| `is_active` | BOOLEAN | NOT NULL | Active flag |
| `last_login` | TIMESTAMPTZ | nullable | Last login time |
| `login_count` | INTEGER | NOT NULL, default 0 | Login counter |
| `notes` | TEXT | nullable | Admin notes |
| `created_at` | TIMESTAMPTZ | NOT NULL, server default now() | Creation time |
| `updated_at` | TIMESTAMPTZ | NOT NULL, server default now() | Update time |

**Table: `admin_action`** (Audit trail)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Action identifier |
| `admin_id` | UUID | FK → admin_user.id, INDEX | Admin reference |
| `action` | VARCHAR(100) | NOT NULL, INDEX | Action type |
| `target_type` | VARCHAR(50) | INDEX, nullable | Target entity type |
| `target_id` | VARCHAR(255) | INDEX, nullable | Target entity ID |
| `details` | JSONB | NOT NULL | Action details |
| `reason` | TEXT | nullable | Reason for action |
| `ip_address` | VARCHAR(45) | nullable | Request IP |
| `user_agent` | TEXT | nullable | Request user agent |
| `created_at` | TIMESTAMPTZ | NOT NULL, server default now() | Action time |

**Table: `platform_setting`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Setting identifier |
| `key` | VARCHAR(100) | UNIQUE, NOT NULL, INDEX | Setting key |
| `value` | TEXT | NOT NULL | Setting value |
| `description` | TEXT | nullable | Setting description |
| `category` | VARCHAR(50) | NOT NULL, INDEX | Setting category |
| `is_public` | BOOLEAN | NOT NULL | Public visibility |
| `updated_by` | UUID | nullable, FK → admin_user.id | Last updater |
| `created_at` | TIMESTAMPTZ | NOT NULL | Creation time |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Update time |

---

#### Payment Database (`payment_db`)

**Tables:** `payments`, `wallets`, `transactions` (defined in code)

| Table | Fields |
|---|---|
| `payments` | id, user_id, session_id, amount, currency, status, payment_intent_id, created_at |
| `wallets` | id, user_id, balance, currency, created_at, updated_at |
| `transactions` | id, wallet_id, type (credit/debit), amount, reference_type, reference_id, description, created_at |

---

#### Verification Database (`verification_db`)

**Table: `verification_requests`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | Request identifier |
| `user_id` | UUID | NOT NULL, INDEX | User reference |
| `request_type` | VARCHAR(50) | NOT NULL | `identity`, `education`, `background_check` |
| `status` | VARCHAR(20) | NOT NULL, default 'pending' | `pending`, `approved`, `rejected`, `under_review` |
| `admin_notes` | VARCHAR(1000) | nullable | Admin review notes |
| `reviewed_by` | UUID | nullable | Admin who reviewed |
| `submitted_at` | DATETIME | NOT NULL | Submission time |
| `reviewed_at` | DATETIME | nullable | Review completion time |
| `created_at` | DATETIME | auto | Record creation |
| `updated_at` | DATETIME | auto | Record update |

**Table: `verification_documents`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Document identifier |
| `request_id` | UUID | FK → verification_requests.id (CASCADE), INDEX | Request reference |
| `file_name` | VARCHAR(255) | NOT NULL | Original filename |
| `file_url` | VARCHAR(500) | NOT NULL | Relative file path |
| `document_type` | VARCHAR(50) | NOT NULL | Type identifier |
| `uploaded_at` | DATETIME | NOT NULL | Upload time |

**Table: `tutor_verification_requests`** (separate model for tutor applications)

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Request identifier |
| `user_id` | UUID, NOT NULL, INDEX | User reference |
| `bio` | TEXT | Tutor biography |
| `subjects` | TEXT | Comma-separated subjects |
| `experience_years` | INTEGER | Years of experience |
| `hourly_rate` | FLOAT | Desired hourly rate |
| `status` | ENUM | PENDING, UNDER_REVIEW, VERIFIED, REJECTED, SUSPENDED |
| `created_at` | DATETIME | Request creation |
| `reviewed_by` | UUID, nullable | Admin who reviewed |
| `reviewed_at` | DATETIME, nullable | Review timestamp |
| `rejection_reason` | TEXT, nullable | Rejection reason |

**Table: `verification_documents`** (for tutor applications)

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Document identifier |
| `request_id` | UUID, FK → tutor_verification_requests.id | Request reference |
| `file_name` | VARCHAR(255) | Original filename |
| `file_url` | VARCHAR(500) | Relative storage path |
| `document_type` | VARCHAR(50) | IDENTITY_PROOF, HIGHEST_DEGREE, CERTIFICATE |
| `uploaded_at` | DATETIME | Upload timestamp |

**Document Types (Enum):** `IDENTITY_PROOF`, `HIGHEST_DEGREE`, `CERTIFICATE`

**Verification Status (Enum):** `PENDING`, `UNDER_REVIEW`, `VERIFIED`, `REJECTED`, `SUSPENDED`

---

#### Notification Database (`notification_db`)

**Tables:** `notifications`, `notification_templates`, `notification_preferences`, `notification_delivery_logs`

| Table | Fields |
|---|---|
| `notifications` | id, user_id, event_type, title, body, is_read, created_at |
| `notification_templates` | id, event_type, title_template, body_template, created_at |
| `notification_preferences` | id, user_id, event_type, email_enabled, push_enabled, in_app_enabled |
| `notification_delivery_logs` | id, notification_id, channel, status, delivered_at |

---

#### Recommendation Database (`recommendation_db`)

**Table: `tutor_metrics`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `tutor_id` | UUID | PK | Tutor identifier (maps to user.id) |
| `average_rating` | FLOAT | default 0.0 | Computed average rating |
| `total_reviews` | INTEGER | default 0 | Total review count |
| `total_sessions` | INTEGER | default 0 | Total session count |
| `sessions_completed` | INTEGER | default 0 | Completed session count |
| `is_verified` | BOOLEAN | default false | Verification status |
| `subjects` | JSONB | default [] | Subject expertise tags |
| `activity_score` | FLOAT | default 0.0 | Activity level score |
| `latitude` | FLOAT | nullable | Tutor's location |
| `longitude` | FLOAT | nullable | Tutor's location |
| `recommendation_score` | FLOAT | default 0.0, INDEX | Computed recommendation score |
| `last_activity` | TIMESTAMPTZ | server default now() | Last activity timestamp |
| `updated_at` | TIMESTAMPTZ | server default now(), onupdate | Record update time |

**Table: `recommendation_scores`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `tutor_id` | UUID | PK (composite) | Tutor identifier |
| `subject` | VARCHAR(100) | PK (composite), INDEX | Subject name |
| `score` | FLOAT | default 0.0, INDEX | Per-subject score |
| `rank` | INTEGER | nullable | Subject-specific rank |
| `updated_at` | TIMESTAMPTZ | server default now() | Update time |

**Table: `trending_tutors`**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `tutor_id` | UUID | PK | Tutor identifier |
| `growth_rate` | FLOAT | default 0.0 | Growth rate metric |
| `trend_score` | FLOAT | default 0.0, INDEX | Trending score |
| `calculated_at` | TIMESTAMPTZ | server default now() | Calculation time |

---

### 5.2 MongoDB Collections

#### Session Database (`session_db`)

**Collection: `sessions`**

```json
{
  "_id": ObjectId,
  "id": UUID,
  "host_id": UUID,
  "title": "string",
  "description": "string | null",
  "session_type": "free" | "paid",
  "price": 0.0,
  "max_participants": 50,
  "participants": [UUID, ...],
  "status": "scheduled" | "active" | "completed" | "cancelled",
  "scheduled_time": ISODate,
  "location": { "type": "Point", "coordinates": [lng, lat] },
  "subject_tags": ["string", ...],
  "avg_rating": 0.0,
  "total_ratings": 0
}
```

**Indexes:**
- `location`: `2dsphere` (geospatial)
- `status`: ascending

**Collection: `ratings`**

```json
{
  "_id": ObjectId,
  "id": UUID,
  "session_id": UUID,
  "tutor_id": UUID,
  "student_id": UUID,
  "score": 1–5,
  "comment": "string | null",
  "is_deleted": false,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:** Unique compound index on `(session_id, student_id)`.

**Collection: `verified_tutors`** (read model mirror)

```json
{
  "_id": ObjectId,
  "user_id": UUID,
  "verified_at": ISODate
}
```

#### Chat Database (`chat_db`)

**Collection: `messages`**

```json
{
  "_id": ObjectId,
  "id": UUID,
  "group_id": UUID,
  "sender_id": UUID,
  "content": "string",
  "message_type": "text" | "system",
  "is_deleted": false,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
- Compound `(group_id, created_at)` ascending
- Compound `(group_id, is_deleted)` ascending

**Collection: `group_memberships`** (read model mirror from Group Service)

```json
{
  "_id": ObjectId,
  "group_id": UUID,
  "user_id": UUID,
  "is_active": true
}
```

**Indexes:**
- Unique compound `(group_id, user_id)`
- Compound `(group_id, is_active)`

---

### 5.3 Redis Usage

| Database | Service | Keys | Description |
|---|---|---|---|
| **DB 0** | Identity | `refresh:{jti}` | Refresh token JTI store (TTL = refresh token expiry) |
| DB 0 | Identity | `marketplace:top_tutors` | Cached top tutor leaderboard (TTL 300s) |
| DB 0 | Identity | `rating_event:{session_id}:{student_id}` | Duplicate rating detection (TTL 24h) |
| **DB 0** | Verification | `verification:status:{user_id}` | Cached verification status (TTL 3600s) |
| **DB 1** | Session | `nearby:sessions:{hash}` | Nearby sessions cache (TTL 60s) |
| DB 1 | Session | `rating_event:{id}` | Duplicate rating detection (TTL 24h) |
| **DB 2** | Group | (configured, light usage) | Generic group cache |
| **DB 3** | Chat | `recent:messages:{group_id}` | Recent message cache (TTL 600s, limit 50) |
| DB 3 | Chat | `online:{group_id}` | Online presence set |
| DB 3 | Chat | `unread:{user_id}:{group_id}` | Unread count per user/group |
| **DB 6** | Admin | `admin:*` | Admin cache namespace |
| DB 6 | Payment | `payment:*` | Generic payment cache (TTL 60s) |
| **DB 7** | Notification | `notif:unread:{user_id}` | Unread notification count (TTL 60s) |
| DB 7 | Notification | `notif:prefs:{user_id}` | Preferences cache (TTL 600s) |
| DB 7 | Notification | `pubsub:*` | WebSocket pub/sub channels |
| **DB 8** | Recommendation | `rec:top:{limit}` | Top tutors cache (TTL 600s) |
| DB 8 | Recommendation | `rec:trending` | Trending tutors cache (TTL 3600s) |
| DB 8 | Recommendation | `rec:subject:{subject}` | Subject-based cache (TTL 600s) |

---

## 6. Kafka Architecture

### 6.1 Infrastructure

- **Broker:** Confluent Kafka 7.5 (single broker for development)
- **Zookeeper:** Confluent Zookeeper 7.5
- **Listeners:** PLAINTEXT on port 29092 (Docker internal), PLAINTEXT_HOST on port 9092 (host)
- **Topic Replication Factor:** 1 (development)
- **Message Format:** JSON (UTF-8 encoded)
- **Producer:** `aiokafka` with gzip compression, idempotence, `acks=all`
- **Consumer:** `aiokafka` with `enable_auto_commit=True`, `auto_offset_reset="earliest"`

### 6.2 Topics Overview

| Topic | Partitions | Producers | Consumers | Event Types |
|---|---|---|---|---|
| `USER_EVENTS` | 1 | Identity, Verification | Identity, Session, Notification, Recommendation | `USER_CREATED`, `TUTOR_VERIFIED`, `TUTOR_REJECTED`, `USER_REGISTERED` |
| `RATING_EVENTS` | 1 | Session | Identity, Recommendation | `RATING_SUBMITTED`, `SESSION_RATED` |
| `GROUP_EVENTS` | 1 | Group | Chat, Notification | `GROUP_CREATED`, `GROUP_DELETED`, `USER_JOINED_GROUP`, `USER_LEFT_GROUP` |
| `CHAT_EVENTS` | 1 | Chat | Notification | `CHAT_MESSAGE_SENT`, `CHAT_MESSAGE_DELETED` |
| `PAYMENT_EVENTS` | 1 | Payment | Session, Notification | `PAYMENT_SUCCESS`, `PAYMENT_FAILED` |
| `VERIFICATION_EVENTS` | 1 | Verification, Identity | Notification | `VERIFICATION_SUBMITTED`, `VERIFICATION_APPROVED`, `VERIFICATION_REJECTED`, `TUTOR_APPLICATION_SUBMITTED` |
| `ADMIN_EVENTS` | 1 | Admin | (future) | Admin lifecycle, maintenance, cache, backup, broadcast |
| `RECOMMENDATION_EVENTS` | 1 | (future) | Notification | `TUTOR_RECOMMENDED` (configured) |

### 6.3 Event Payload Structures

**USER_CREATED** (Identity → UserEvents)
```json
{
  "event_type": "USER_CREATED",
  "user_id": "uuid",
  "email": "user@example.com",
  "role": "user"
}
```

**TUTOR_VERIFIED** (Verification → UserEvents)
```json
{
  "event": "TUTOR_VERIFIED",
  "event_type": "TUTOR_VERIFIED",
  "userId": "uuid",
  "user_id": "uuid",
  "verificationRequestId": "uuid",
  "status": "VERIFIED",
  "timestamp": "2026-04-12T10:00:00"
}
```

**TUTOR_REJECTED** (Verification → UserEvents)
```json
{
  "event": "TUTOR_REJECTED",
  "event_type": "TUTOR_REJECTED",
  "userId": "uuid",
  "user_id": "uuid",
  "verificationRequestId": "uuid",
  "reason": "Insufficient documentation",
  "status": "REJECTED",
  "timestamp": "2026-04-12T10:00:00"
}
```

**RATING_SUBMITTED** (Session → RatingEvents)
```json
{
  "event": "SESSION_RATED",
  "event_type": "RATING_SUBMITTED",
  "tutorId": "uuid",
  "tutor_id": "uuid",
  "rating": 5,
  "score": 5,
  "sessionId": "uuid",
  "studentId": "uuid",
  "event_id": "uuid"
}
```

**GROUP_CREATED** (Group → GroupEvents)
```json
{
  "event_type": "GROUP_CREATED",
  "group_id": "uuid",
  "owner_id": "uuid",
  "name": "Calculus Study Group"
}
```

**USER_JOINED_GROUP** (Group → GroupEvents)
```json
{
  "event_type": "USER_JOINED_GROUP",
  "group_id": "uuid",
  "user_id": "uuid"
}
```

**PAYMENT_SUCCESS** (Payment → PaymentEvents)
```json
{
  "event_type": "PAYMENT_SUCCESS",
  "session_id": "uuid",
  "student_id": "uuid",
  "amount": 25.0
}
```

**CHAT_MESSAGE_SENT** (Chat → ChatEvents)
```json
{
  "event_type": "CHAT_MESSAGE_SENT",
  "group_id": "uuid",
  "sender_id": "uuid",
  "message_id": "uuid",
  "content": "Hello!"
}
```

**VERIFICATION_SUBMITTED** (Verification → VerificationEvents)
```json
{
  "event_type": "VERIFICATION_SUBMITTED",
  "request_id": "uuid",
  "user_id": "uuid",
  "request_type": "tutor_application",
  "document_count": 3,
  "timestamp": "2026-04-12T10:00:00"
}
```

**TUTOR_APPLICATION_SUBMITTED** (Identity → VerificationEvents)
```json
{
  "event": "TUTOR_APPLICATION_SUBMITTED",
  "userId": "uuid",
  "documents": [
    {"document_type": "IDENTITY_PROOF", "file_name": "passport.jpg", "file_url": "..."},
    {"document_type": "HIGHEST_DEGREE", "file_name": "diploma.pdf", "file_url": "..."}
  ],
  "status": "PENDING"
}
```

### 6.4 Resilience Architecture

```
                ┌──────────────────┐
                │  Publish Request │
                └────────┬─────────┘
                         │
                    ┌────▼────┐
                    │ Circuit │
                    │ Breaker │
                    └────┬────┘
                    ┌────┴────┐
                    │  ALLOW? │
                    └────┬────┘
               YES        │        NO
           ┌──────────────┴──────────────┐
           │                             │
     ┌─────▼─────┐              ┌────────▼────────┐
     │  Publish   │              │  Store in       │
     │  to Kafka  │              │  Fallback Queue │
     └─────┬─────┘              └────────┬────────┘
           │                             │
     ┌─────▼─────┐              ┌────────▼────────┐
     │  Success?  │              │  Retry Worker   │
     └─────┬─────┘              │  (async loop)   │
      YES    NO                 └────────┬────────┘
       │      │                          │
       │  ┌───▼────┐            ┌────────▼────────┐
       │  │Circuit │            │  Dequeue Event  │
       │  │ Failure│            │  Retry Publish  │
       │  │Counter │            └────────┬────────┘
       │  └────────┘                     │
       │                           ┌─────▼─────┐
       │                           │  Success?  │
       │                           └─────┬─────┘
       │                            YES     NO
       │                             │      │
       │                             │  ┌───▼───────────┐
       │                             │  │ Exponential   │
       │                             │  │ Backoff Sleep │
       │                             │  │ Requeue to    │
       │                             │  │ Fallback Queue│
       │                             │  └───────────────┘
       │                             │  (repeat)
       ▼                             ▼
   [Done]                       [Retrying]
```

**Circuit Breaker Properties:**
- States: CLOSED → OPEN → HALF_OPEN → CLOSED
- Failure threshold: 3 failures (configurable)
- Recovery timeout: 30 seconds (configurable)
- Half-open: allows 1 probe request to test recovery

**Fallback Queue:**
- In-memory `deque` with asyncio condition
- Not durable across process restarts
- Events stored with metadata: `event_id`, `topic`, `key`, `value`, `retry_count`, `created_at`

**Retry Worker:**
- Asyncio background task
- Exponential backoff: `base_delay × 2^(retry_count-1)`, capped at `max_delay`
- Default base delay: 2s, max delay: 30s

**Consumer Retry:**
- All consumers retry startup 5 times with 3s delay between attempts
- Startup timeout per attempt: 10 seconds
- Duplicate event detection via Redis (24h TTL) for rating events

### 6.5 Startup Ordering

Kafka consumers and producers start independently with retries, allowing services to come up even when Kafka is not yet available. This is by design — services continue in "fallback mode" and process events once Kafka becomes available.

```
Service Startup Sequence:
1. Initialize DB connection
2. Initialize Redis
3. Initialize Kafka producer (with retries + circuit breaker)
4. Start fallback retry worker
5. Initialize Kafka consumers (with retries)
6. Declare service ready (even if Kafka unavailable)
```

---

## 7. Tutor Verification Workflow

### Complete Flow Diagram

```
TUTOR                        IDENTITY                    VERIFICATION                  ADMIN                     KAFKA EVENTS
 │                            │                            │                            │
 ├─ POST /tutors/apply ──────►│                            │                            │
 │  (bio, subjects,           │  Validate + save files     │                            │
 │   hourly_rate,             │  Create pending profile    │                            │
 │   identity_proof,          │                            │                            │
 │   highest_degree,          ├────────────────────────────► TUTOR_APPLICATION_SUBMITTED │
 │   certificates)            │                            │                            │
 │                            │                            │                            │
 │   202 ACCEPTED ◄───────────┤                            │                            │
 │                            │                            ├─ POST /tutor-application ─►│
 │                            │                            │  (same data, verification  │
 │                            │                            │   service route)           │
 │                            │                            │                            │
 │                            │                            │   202 ACCEPTED ◄───────────┤
 │                            │                            │                            │
 │                            │                            ├──►  VERIFICATION_EVENTS ───┤
 │                            │                            │   TUTOR_APPLICATION_SUBMITTED │
 │                            │                            │                            │
 │                            │       ┌────────────────────┴────────────┐               │
 │                            │       │  Status: PENDING               │               │
 │                            │       │  Docs: Identity Proof          │               │
 │                            │       │        Highest Degree          │               │
 │                            │       │        Certificates (opt)     │               │
 │                            │       └────────────────────────────────┘               │
 │                            │                            │                            │
 │                            │                            │   ◄── Admin views ───────┤
 │                            │                            │   GET /admin/verification/│
 │                            │                            │   GET /admin/verification/│
 │                            │                            │       /pending            │
 │                            │                            │                            │
 │                            │    ◄── Admin reviews ──────┤                            │
 │                            │    POST /admin/verification│                            │
 │                            │    /{id}/review            │                            │
 │                            │    → Status: UNDER_REVIEW  │                            │
 │                            │                            │                            │
 │    ┌───────────────────────┬┴───────────────────────────┬┴───────────────────────────┤
 │    │ APPROVE               │                            │                            │
 │    │                       │                            │                            │
 │    │                       │   POST {id}/approve ──────►│                            │
 │    │                       │                            ├──► USER_EVENTS ───────────►│
 │    │                       │                            │   TUTOR_VERIFIED           │
 │    │                       │                            │                            │
 │    │                       │◄── TUTOR_VERIFIED ─────────┤                            │
 │    │                       │   (consumed by             │                            │
 │    │                       │    UserEventsConsumer)     │                            │
 │    │                       │                            │                            │
 │    │                       │   Update user role → tutor │                            │
 │    │                       │   Set is_verified_tutor→T  │                            │
 │    │                       │   Set tutor profile→verified│                           │
 │    │                       │                            │                            │
 │    │                       ├── TUTOR_VERIFIED ─────────►┤ TUTOR_VERIFIED ───────────►│
 │    │                       │   (via publish_tutor_       │  Session: upsert          │
 │    │                       │    verified in TutorService)│  verified_tutors          │
 │    │                       │                            │                            │
 │    │                       │                            ├── TUTOR_VERIFIED ─────────►│
 │    │                       │                            │  Recommendation:           │
 │    │                       │                            │  is_verified=True          │
 │    │                       │                            │                            │
 │    │                       │                            ├── VERIFICATION_EVENTS ────►│
 │    │                       │                            │  Notification: creates     │
 │    │                       │                            │  "tutor approved" notif    │
 │    │                       │                            │                            │
 │    └── REJECT ─────────────┼────────────────────────────┤                            │
 │                            │                            │                            │
 │                            │   POST {id}/reject ───────►│                            │
 │                            │                            ├── USER_EVENTS ───────────►│
 │                            │                            │   TUTOR_REJECTED           │
 │                            │                            │                            │
 │                            │◄── TUTOR_REJECTED ─────────┤                            │
 │                            │                            ├── VERIFICATION_EVENTS ────►│
 │                            │                            │  Notification: creates     │
 │                            │                            │  "tutor rejected" notif   │
 │                            │                            │                            │
 │                            │                            ├── USER_EVENTS ───────────►│
 │                            │                            │  Recommendation:           │
 │                            │                            │  score=-1.0, exclude      │
```

### Document Requirements

| Document | Required? | Type | Max Size | Allowed Types |
|---|---|---|---|---|
| Identity Proof | ✅ Required | IDENTITY_PROOF | 5MB | JPEG, PNG, PDF |
| Highest Degree | ✅ Required | HIGHEST_DEGREE | 5MB | JPEG, PNG, PDF |
| Extra Certificates | ❌ Optional | CERTIFICATE | 5MB each | JPEG, PNG, PDF |

### Approval States

| Status | Description |
|---|---|
| `PENDING` | Submitted, awaiting admin review |
| `UNDER_REVIEW` | Admin is reviewing the application |
| `VERIFIED` | Approved — user becomes tutor, profile activated |
| `REJECTED` | Denied — reason stored in `rejection_reason` |
| `SUSPENDED` | Previously verified tutor suspended |

### Notification Events Triggered

| Verification Event | Notification Event |
|---|---|
| `TUTOR_VERIFIED` | "Your tutor application has been approved" |
| `TUTOR_REJECTED` | "Your tutor application has been rejected: {reason}" |

---

### 7.5 Verified Tutor Architecture (Event-Driven Authorization)

The Session Service enforces that **only verified tutors** can create sessions. This authorization is implemented via an **event-driven local read model** — no synchronous HTTP calls to Identity or Verification services occur during session creation.

#### Architecture

```
Verification Service (Admin approves/rejects/suspends)
        │
        ▼ publishes to USER_EVENTS topic
   ┌────────────┐
   │   Kafka    │
   │ USER_EVENTS│
   └────────────┘
        │
        ▼ consumed by UserEventsConsumer
   ┌────────────────────┐
   │ Session Service    │
   │ verified_tutors    │
   │ (MongoDB collection)│
   └────────────────────┘
        │
        ▼ local read model lookup
   Session creation authorization
```

#### Kafka Events Consumed (Session Service)

| Event | Handler | Read Model Effect |
|-------|---------|-------------------|
| `TUTOR_VERIFIED` | `_handle_tutor_verified()` | Upserts: `is_verified=true`, `status=active`, `verified_at=now` |
| `TUTOR_REJECTED` | `_handle_tutor_rejected()` | Sets: `is_verified=false`, `status=rejected` |
| `TUTOR_SUSPENDED` | `_handle_tutor_suspended()` | Sets: `is_verified=false`, `status=suspended` |

#### Events Produced by Other Services

**Verification Service** (`verification_service/app/events/kafka_producer.py`):
- `publish_tutor_verified()` → `USER_EVENTS` (on admin approval)
- `publish_tutor_rejected()` → `USER_EVENTS` (on admin rejection)
- `publish_tutor_suspended()` → `USER_EVENTS` (on admin suspension)

**Identity Service** (`identity_service/app/events/kafka_producer.py`):
- `publish_tutor_verified()` → `USER_EVENTS` (alternative admin verify path)

#### Verified Tutors Read Model

**Collection:** `verified_tutors` (in `session_db` MongoDB)

**Document Schema:**
```json
{
  "_id": ObjectId,
  "id": UUID,
  "user_id": UUID,           // user_id from Identity Service
  "is_verified": true,        // false for rejected/suspended
  "status": "active",         // "active" | "rejected" | "suspended"
  "verified_at": ISODate,     // null for rejected/suspended
  "subjects": ["Math"],       // subjects from verification
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
| Field | Index Type | Name |
|-------|------------|------|
| `user_id` | Unique ascending | `vt_user_id_idx` |
| `status` | Ascending | `vt_status_idx` |

#### Session Creation Authorization Flow

```
Client → POST /api/v1/sessions/ (JWT + SessionCreate body)
  │
  ├─ 1. get_current_user_id() → extracts user_id from JWT
  │
  ├─ 2. VerifiedTutorRepository.is_verified(user_id)
  │       │
  │       └── db.verified_tutors.find_one({
  │             "user_id": str(user_id),
  │             "is_verified": true,
  │             "status": "active"
  │           })
  │
  ├─ [Not Found] → 403 Forbidden
  │     { "detail": "Only verified tutors can create sessions" }
  │
  └─ [Found] → 201 Created
        Session document saved to MongoDB
```

**Authorization Conditions** (ALL must be true):
1. Authenticated user (valid JWT)
2. Role = tutor (set during verification workflow)
3. Verified tutor (`is_verified=true`)
4. Active tutor (`status=active`)
5. Not suspended (`status != suspended`)

#### Event-Driven Synchronization

The `verified_tutors` collection is **never written to directly** via REST APIs. It is synchronized purely through Kafka events:

| Trigger | Event | Consumer Action |
|---------|-------|----------------|
| Admin approves verification | `TUTOR_VERIFIED` → `USER_EVENTS` | `upsert_verified()` |
| Admin rejects verification | `TUTOR_REJECTED` → `USER_EVENTS` | `mark_rejected()` |
| Admin suspends tutor | `TUTOR_SUSPENDED` → `USER_EVENTS` | `mark_suspended()` |

**Eventual Consistency Guarantee:** There is a small delay between the admin action and when the Session Service read model is updated. During this window, a newly verified tutor may briefly receive a 403. The consumer processes events within milliseconds under normal conditions.

#### Security Rules

- No synchronous HTTP calls to Identity/Verification Service during session creation
- Local read model ensures low-latency authorization (single MongoDB query)
- JWT is validated locally (shared secret, decode-only)
- 403 response is uniform: `{ "detail": "Only verified tutors can create sessions" }`
- Verified/rejected/suspended states are mutually exclusive

#### Sequence Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Admin/Verif │     │    Kafka     │     │  Session Service │     │      Client      │
│   Service    │     │ USER_EVENTS  │     │                  │     │                  │
└──────┬───────┘     └──────┬───────┘     └────────┬─────────┘     └────────┬─────────┘
       │                    │                       │                        │
       │  TUTOR_VERIFIED ───►────► UserEventsConsumer                       │
       │                    │     .upsert_verified()                       │
       │                    │     (is_verified=true, status=active)        │
       │                    │                       │                        │
       │  TUTOR_REJECTED ───►────► UserEventsConsumer                       │
       │                    │     .mark_rejected()                         │
       │                    │     (is_verified=false, status=rejected)     │
       │                    │                       │                        │
       │  TUTOR_SUSPENDED ──►────► UserEventsConsumer                       │
       │                    │     .mark_suspended()                        │
       │                    │     (is_verified=false, status=suspended)    │
       │                    │                       │                        │
       │                    │                       │  POST /sessions/       │
       │                    │                       │◄───────────────────────┤
       │                    │                       │                        │
       │                    │                       │  is_verified(user_id) │
       │                    │                       │  ─────► MongoDB       │
       │                    │                       │  ◄───── found/not     │
       │                    │                       │                        │
       │                    │                       │  403 / 201            │
       │                    │                       │────────────────────────►│
```

---

## 8. Session & Rating Workflow

### Session Lifecycle

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────────┐
│ SCHEDULED│───►│  ACTIVE  │───►│COMPLETED │───►│  CANCELLED │
└──────────┘    └──────────┘    └──────────┘    └────────────┘
      │               │               │
      │               │               │
      ▼               ▼               ▼
   Created        Started by      Host marks
   by host        host            as completed
```

### Session Creation Flow

```
1. Host → POST /sessions/ (with title, type, time, location, subjects)
2. Session Service creates MongoDB document
3. For paid sessions: host sets price > 0

Session Join (Free):
1. Student → POST /sessions/{id}/join
2. Validates session is not full
3. Validates session is scheduled/active
4. Adds student to participants array

Session Join (Paid):
1. Student → Payment Service → POST /payments/create-intent
2. Student → POST /payments/confirm
3. Payment Service → Kafka → PAYMENT_SUCCESS
4. Session Service consumes PAYMENT_SUCCESS
5. SessionRepository.add_participant(session_id, student_id)
```


### Rating Flow

```
1. Session host sets status to "completed"
2. Student → POST /sessions/{id}/ratings
   Body: { "score": 4, "comment": "Great session" }
3. RatingService validates:
   a. Student is participant in session
   b. Session status is "completed"
   c. No duplicate rating (Redis + MongoDB unique index)
4. Creates Rating document in MongoDB
5. Updates session avg_rating/total_ratings
6. Publishes RATING_SUBMITTED to RATING_EVENTS

RATING_EVENTS consumed by:

Identity Service:
  - Updates tutor_profiles.rating_sum += score
  - Updates tutor_profiles.total_reviews += 1
  - Invalidates leaderboard cache

Recommendation Service:
  - Updates tutor_metrics.average_rating
  - Updates tutor_metrics.sessions_completed
  - Recalculates recommendation_score
  - Invalidates Redis caches
```

### Rating Validation Rules

| Rule | Enforcement |
|---|---|
| Must be participant | Check participants array |
| Session must be completed | Check status === 'completed' |
| One rating per student per session | MongoDB unique index + Redis 24h TTL |
| Score 1–5 only | Pydantic validation |

---

## 9. Recommendation System

### Scoring Formula

```
recommendation_score = MIN(1.0, rating_component + activity_component)
                     = MIN(1.0, (0.7 × avg_rating / 5.0) + (0.3 × activity_score))
```

Where:
- `avg_rating`: Current average rating from completed sessions
- `activity_score`: Computed from session completion frequency and recent activity
- Score is capped at 1.0 (100%)

### Tutor Eligibility

| Criteria | Included | Excluded |
|---|---|---|
| Verified | ✅ Score ≥ 0 | ❌ Score set to -1.0 |
| Has profile | ✅ Listed in tutor_metrics | ❌ Not in tutor_metrics |
| Has rating data | ✅ Included in ranking | ❌ Score defaults to 0.0 |

### Event-Driven Updates

```
┌─────────────────────────────────────────────────────────────────┐
│                   EVENT-DRIVEN UPDATE PIPELINE                   │
│                                                                  │
│  RATING_EVENTS: SESSION_RATED                                    │
│       │                                                          │
│       ▼                                                          │
│  RecommendationService.apply_session_rating_event()              │
│       │                                                          │
│       ├── NEW tutor: Creates TutorMetric with initial data       │
│       │      average_rating = score                              │
│       │      total_reviews = 1                                   │
│       │      sessions_completed = 1                              │
│       │      recommendation_score = calc_score()                 │
│       │                                                          │
│       └── EXISTING tutor: Updates rolling average               │
│              total_reviews += 1                                  │
│              sessions_completed += 1                             │
│              average_rating = new weighted average               │
│              recommendation_score = recalc()                     │
│                                                                  │
│  USER_EVENTS: TUTOR_VERIFIED                                     │
│       │                                                          │
│       ▼                                                          │
│  Creates TutorMetric (if not exists) with is_verified=True       │
│                                                                  │
│  USER_EVENTS: TUTOR_REJECTED                                     │
│       │                                                          │
│       ▼                                                          │
│  Sets is_verified=False, recommendation_score=-1.0 (excluded)   │
└─────────────────────────────────────────────────────────────────┘
```

### Recommendation Endpoints Data Flow

```
┌─────────────┐     ┌─────────────────┐     ┌────────────────┐
│  Client     │────►│  Recommendation │────►│  Redis Cache   │
│  Request    │     │  Service        │     │  (rec:* keys)  │
└─────────────┘     └────────┬────────┘     └───────┬────────┘
                             │                      │
                     CACHE HIT?              CACHE MISS
                             │                      │
                         (return              ┌──────▼──────┐
                          cached)             │  PostgreSQL │
                                              │  Query      │
                                              └──────┬──────┘
                                                     │
                                              ┌──────▼──────┐
                                              │  Update     │
                                              │  Redis      │
                                              │  Cache      │
                                              └──────┬──────┘
                                                     │
                                              ┌──────▼──────┐
                                              │  Return     │
                                              │  Response   │
                                              └─────────────┘
```

### Cache Strategy

| Endpoint | Cache Key | TTL | Invalidation |
|---|---|---|---|
| `/top` | `rec:top:{limit}` | 600s | `POST /admin/cache/refresh?target=top` |
| `/trending` | `rec:trending` | 3600s | `POST /admin/cache/refresh?target=trending` |
| `/subject/{subj}` | `rec:subject:{subject}` | 600s | `POST /admin/cache/refresh?target=all` |
| `/search` | Not cached | — | — |
| `/nearby` | Not cached | — | — |

---

## 10. Authentication & Authorization

### 10.1 JWT Architecture

```
┌──────────────────┐         ┌──────────────────┐
│   Identity       │         │  Other Services   │
│   Service        │         │  (Session, Chat,  │
│   (Token Issuer) │         │  Group, Admin,    │
└────────┬─────────┘         │  Payment, etc.)   │
         │                   └────────┬──────────┘
         │                            │
    ┌────▼────┐                  ┌────▼────┐
    │ JWT     │                  │ JWT     │
    │ Creation│                  │ Decode  │
    │ HS256   │                  │ + Verify│
    └─────────┘                  └─────────┘
         │                            │
         │    Shared JWT_SECRET_KEY   │
         └────────────────────────────┘
```

### 10.2 Token Structure

**Access Token:**
```json
{
  "sub": "uuid",
  "exp": 1681315200,
  "type": "access"
}
```

**Refresh Token:**
```json
{
  "sub": "uuid",
  "exp": 1681920000,
  "type": "refresh",
  "jti": "uuid"
}
```

### 10.3 Authentication Flow

```
1. Client → POST /auth/register (email, password)
2. Identity Service:
   a. Hash password with bcrypt
   b. Create user in PostgreSQL
   c. Publish USER_CREATED to Kafka
   d. Return UserRead

3. Client → POST /auth/login (email, password)
4. Identity Service:
   a. Verify password with bcrypt
   b. Create access_token (default 15 min TTL)
   c. Create refresh_token with JTI
   d. Store JTI in Redis: SETEX refresh:{jti} TTL user_id
   e. Return { access_token, refresh_token }

5. Client → Service with Authorization: Bearer <access_token>
6. Service:
   a. Decode JWT with shared secret
   b. Extract sub = user UUID
   c. Load user from database
   d. Use current_user dependency

7. Token Refresh:
   a. Client → POST /auth/refresh { refresh_token }
   b. Identity validates JWT, checks JTI in Redis
   c. Revokes old JTI (deletes from Redis)
   d. Issues NEW access + refresh tokens (rotation)

8. Logout:
   a. Client → POST /auth/logout { refresh_token }
   b. Identity deletes JTI from Redis (revokes refresh token)
   c. Access token expires naturally
```

### 10.4 Role System

| Role | Description | Authorized Actions |
|---|---|---|
| `user` | Default registered user | Create sessions, join groups, send messages, rate sessions |
| `tutor` | Verified tutor | All user actions + tutor profile management, host sessions |
| `admin` | Platform admin | All verification management, user management, moderation |
| `super_admin` | Super administrator | Admin CRUD, system settings, all administrative actions |

### 10.5 Protected Endpoints

**JWT Required (most endpoints):**
- All Identity Service endpoints (except register/login)
- All Session Service endpoints (when `AUTH_ENABLED=true`)
- All Group Service endpoints
- All Chat Service endpoints
- All Payment Service endpoints (should be enforced — see limitations)
- All Verification Service endpoints (via JWTAuthMiddleware)
- All Notification Service endpoints
- Recommendation `/user/{user_id}` endpoint

**Admin-Only (role check):**
- Verification Service `/admin/verification/*` endpoints
- Admin Service all endpoints

**X-Admin-API-Key Authentication:**
- Identity Service `POST /tutors/{user_id}/verify`
- Verification Service `require_admin_key` dependency

### 10.6 Auth Middleware

**Verification Service** uses a `JWTAuthMiddleware` that runs on every request except public paths. All other services use per-route `Depends(get_current_user())`.

### 10.7 Admin Service Authentication

Admin Service has a **separate authentication flow** from user services:
- Admin users stored in `admin_db.admin_user` table
- Separate login endpoint returns admin-specific JWT
- Admin RBAC with role + permissions stored in JSONB
- Super admin auto-created on startup if not exists
- Security middleware with rate limiting

---

## 11. Docker & Infrastructure

### 11.1 Container Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   studysync bridge network                       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │ Zookeeper │  │  Kafka   │  │  Redis   │  │     MongoDB      ││
│  │ :2181     │  │ :9092    │  │ :6379    │  │ :27017           ││
│  │           │  │ :29092   │  │          │  │                  ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘│
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │PostgreSQL│  │PostgreSQL│  │PostgreSQL│  │  PostgreSQL      ││
│  │ identity │  │  group   │  │  admin   │  │  payment         ││
│  │ :5432    │  │ :5432    │  │ :5432    │  │ :5432            ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘│
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │PostgreSQL│  │PostgreSQL│  │PostgreSQL│  │                  ││
│  │verificatn│  │notificatn│  │recommend │  │                  ││
│  │ :5432    │  │ :5432    │  │ :5432    │  │                  ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘│
│                                                                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌─────┐│
│  │IDENT │ │SESSN │ │GROUP │ │CHAT  │ │ADMIN │ │PAYMT │ │VERIF││
│  │:8000 │ │:8001 │ │:8002 │ │:8003 │ │:8004 │ │:8005 │ │:8006││
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └─────┘│
│  ┌──────┐ ┌──────┐                                              │
│  │NOTIF │ │RECMD │                                              │
│  │:8007 │ │:8008 │                                              │
│  └──────┘ └──────┘                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 Container Dependencies

```
postgres         ─► identity_service ─► (depends on healthy postgres, redis, kafka)
postgres_group   ─► group_service
postgres_admin   ─► admin_service
postgres_payment ─► payment_service
postgres_verification ─► verification_service
postgres_notification ─► notification_service
postgres_recommendation ─► recommendation_service
redis            ─► ALL services
mongo            ─► session_service, chat_service, admin_service
zookeeper        ─► kafka
kafka            ─► ALL services
```

### 11.3 Healthcheck Configuration

All infrastructure containers have health checks with retries/timeouts. Services `depends_on` with `condition: service_healthy` ensures proper startup ordering.

### 11.4 Host Port Mapping

| Service | Host Port | Container Port |
|---|---|---|
| Identity | 8000 | 8000 |
| Session | 8001 | 8001 |
| Group | 8002 | 8002 |
| Chat | 8003 | 8003 |
| Admin | 8004 | 8004 |
| Payment | 8005 | 8005 |
| Verification | 8006 | 8006 |
| Notification | 8007 | 8007 |
| Recommendation | 8008 | 8008 |
| PostgreSQL (identity) | 5432 | 5432 |
| PostgreSQL (group) | 5433 | 5432 |
| PostgreSQL (admin) | 5437 | 5432 |
| PostgreSQL (payment) | 5445 | 5432 |
| PostgreSQL (verification) | 5446 | 5432 |
| PostgreSQL (notification) | 5447 | 5432 |
| PostgreSQL (recommendation) | 5448 | 5432 |
| MongoDB | 27017 | 27017 |
| Redis | 6379 | 6379 |
| Kafka | 9092 | 9092 |
| Zookeeper | 2181 | 2181 |

---

## 12. Environment Variables

### 12.1 Identity Service

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://studysync:studysync_dev@postgres:5432/identity_db` | Async PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string (DB 0) |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka bootstrap servers |
| `KAFKA_CLIENT_ID` | `identity-service` | Kafka client ID |
| `KAFKA_USER_EVENTS_TOPIC` | `USER_EVENTS` | User events topic |
| `KAFKA_RATING_EVENTS_TOPIC` | `RATING_EVENTS` | Rating events topic |
| `KAFKA_CONSUMER_GROUP` | `identity-service-ratings` | Rating consumer group |
| `JWT_SECRET_KEY` | `change-me-in-production-use-openssl-rand-hex-32` | Secret for JWT signing/validation |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Access token TTL in minutes |
| `TOP_TUTORS_CACHE_KEY` | `marketplace:top_tutors` | Redis cache key for leaderboard |
| `TOP_TUTORS_CACHE_TTL_SECONDS` | `300` | Leaderboard cache TTL |
| `ADMIN_API_KEY` | (empty) | Admin API key for tutor verification |

### 12.2 Session Service

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB_NAME` | `session_db` | MongoDB database name |
| `REDIS_URL` | `redis://localhost:6379/1` | Redis connection string (DB 1) |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka bootstrap servers |
| `KAFKA_PAYMENT_EVENTS_TOPIC` | `PAYMENT_EVENTS` | Payment events topic |
| `KAFKA_USER_EVENTS_TOPIC` | `USER_EVENTS` | User events topic |
| `KAFKA_RATING_EVENTS_TOPIC` | `RATING_EVENTS` | Rating events topic |
| `JWT_SECRET_KEY` | `change-me-in-production-use-openssl-rand-hex-32` | Must match Identity Service |
| `JWT_ALGORITHM` | `HS256` | Must match Identity Service |
| `AUTH_ENABLED` | `true` | Enable/disable JWT auth |
| `KAFKA_ENABLED` | `true` | Enable/disable Kafka |
| `STANDALONE_MODE` | `false` | Run without Kafka/auth dependencies |
| `NEARBY_SESSIONS_CACHE_TTL_SECONDS` | `60` | Nearby sessions cache TTL |

### 12.3 Group Service

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://studysync:studysync_dev@localhost:5433/group_db` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/2` | Redis connection (DB 2) |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka bootstrap servers |
| `KAFKA_GROUP_EVENTS_TOPIC` | `GROUP_EVENTS` | Group events topic |
| `JWT_SECRET_KEY` | `change-me-in-production-use-openssl-rand-hex-32` | Must match Identity |
| `SESSION_SERVICE_URL` | `http://localhost:8001` | Internal Session Service URL |
| `SESSION_SERVICE_TIMEOUT_SECONDS` | `5.0` | HTTP timeout for Session proxy |

### 12.4 Chat Service

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URL` | `mongodb://mongo:27017` | MongoDB connection |
| `MONGODB_DB_NAME` | `chat_db` | MongoDB database name |
| `REDIS_URL` | `redis://redis:6379/3` | Redis connection (DB 3) |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka bootstrap servers |
| `KAFKA_GROUP_EVENTS_TOPIC` | `GROUP_EVENTS` | Group events topic |
| `KAFKA_CHAT_EVENTS_TOPIC` | `CHAT_EVENTS` | Chat events topic |
| `JWT_SECRET_KEY` | `change-me-in-production-use-openssl-rand-hex-32` | Must match Identity |
| `GROUP_SERVICE_URL` | `http://group_service:8002` | Internal Group Service URL |

### 12.5 Admin Service

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://studysync:studysync_dev@postgres_admin:5432/admin_db` | Admin PostgreSQL |
| `IDENTITY_DB_URL` | `postgresql+asyncpg://studysync:studysync_dev@postgres:5432/identity_db` | Identity DB (read) |
| `GROUP_DB_URL` | `postgresql+asyncpg://studysync:studysync_dev@postgres_group:5432/group_db` | Group DB (read) |
| `SESSION_MONGODB_URL` | `mongodb://mongo:27017` | Session MongoDB (read) |
| `SESSION_MONGODB_DB_NAME` | `session_db` | Session DB name |
