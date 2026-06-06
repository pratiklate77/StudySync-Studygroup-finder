# StudySync — Microservices Guide

## Overview

StudySync is composed of **9 independent microservices**, each following the Database-per-Service pattern. This guide provides detailed information about each service, its responsibilities, APIs, dependencies, and configuration.

---

## 1. Identity Service (Port 8000)

### Purpose
Authentication, user management, JWT lifecycle, and tutor profile management. The single source of truth for user identity.

### Responsibilities
- User registration with email/password authentication
- JWT access token issuance and refresh token rotation
- Refresh token revocation via Redis JTI (JWT ID) store
- User profile management with location tracking
- Tutor profile creation, update, soft-delete
- Tutor search with expertise/rating/verified filters
- Top tutor leaderboard with Redis caching
- Tutor verification via admin API key (legacy flow)
- Tutor application with document upload (new flow via Identity Service)
- Rating event consumption → updates tutor rating_sum/total_reviews
- Email verification (token-based)

### Database
- **PostgreSQL**: `identity_db` — `users`, `tutor_profiles`
- **Redis DB 0**: Refresh tokens (`refresh:{jti}`), top tutors cache (`marketplace:top_tutors`)

### Dependencies
- PostgreSQL (identity_db)
- Redis
- Kafka

### Kafka Topics
- **Produces**: `USER_EVENTS` (USER_CREATED, TUTOR_VERIFIED, EMAIL_VERIFICATION_SENT), `VERIFICATION_EVENTS` (TUTOR_APPLICATION_SUBMITTED)
- **Consumes**: `RATING_EVENTS` (RATING_SUBMITTED, SESSION_RATED), `USER_EVENTS` (TUTOR_VERIFIED, TUTOR_REJECTED, TUTOR_SUSPENDED)

### Key Events
| Event | Topic | Trigger |
|-------|-------|---------|
| USER_CREATED | USER_EVENTS | User registration |
| TUTOR_VERIFIED | USER_EVENTS | Admin verifies tutor |
| TUTOR_APPLICATION_SUBMITTED | VERIFICATION_EVENTS | Tutor applies with documents |

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/v1/auth/register | None | Register user |
| POST | /api/v1/auth/login | None | Login |
| POST | /api/v1/auth/refresh | None | Refresh tokens |
| POST | /api/v1/auth/logout | None | Logout |
| GET | /api/v1/auth/profile | JWT | Get profile |
| PATCH | /api/v1/auth/profile | JWT | Update profile |
| POST | /api/v1/tutors/become | JWT | Become tutor |
| POST | /api/v1/tutors/apply | JWT | Apply with documents |
| GET | /api/v1/tutors/leaderboard | None | Top tutors |
| GET | /api/v1/tutors/search | JWT | Search tutors |
| PATCH | /api/v1/tutors/profile | JWT | Update tutor profile |
| DELETE | /api/v1/tutors/profile | JWT | Delete tutor profile |
| GET | /api/v1/tutors/{id} | JWT | Get tutor |
| GET | /api/v1/tutors/{id}/stats | JWT | Tutor stats |
| GET | /health | None | Health check |

---

## 2. Session Service (Port 8001)

### Purpose
Study session lifecycle management, geospatial discovery, participant management, and ratings.

### Responsibilities
- Session CRUD (free and paid types)
- Geospatial nearby search using MongoDB 2dsphere index
- Participant join/leave
- Session status transitions (scheduled → active → completed → cancelled)
- Rating submission with duplicate detection
- Kafka event publishing on rating submission
- Verified tutor read model (consumes TUTOR_VERIFIED from Kafka)
- Standalone mode for development (disables auth/Kafka)

### Database
- **MongoDB**: `session_db` — `sessions` (with 2dsphere index), `ratings`, `verified_tutors`
- **Redis DB 1**: Nearby sessions cache, verified tutor lookups

### Dependencies
- MongoDB
- Redis
- Kafka (optional)

### Kafka Topics
- **Produces**: `RATING_EVENTS` (RATING_SUBMITTED, SESSION_RATED)
- **Consumes**: `PAYMENT_EVENTS` (PAYMENT_SUCCESS), `USER_EVENTS` (TUTOR_VERIFIED, TUTOR_REJECTED, TUTOR_SUSPENDED), `VERIFICATION_EVENTS` (TUTOR_APPLICATION_SUBMITTED)

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/v1/sessions/ | JWT | Create session |
| GET | /api/v1/sessions/ | JWT | List all sessions |
| GET | /api/v1/sessions/nearby | JWT | Nearby search |
| GET | /api/v1/sessions/my | JWT | My sessions |
| GET | /api/v1/sessions/{id} | JWT | Get session |
| PATCH | /api/v1/sessions/{id} | JWT | Update session |
| PATCH | /api/v1/sessions/{id}/cancel | JWT | Cancel session |
| PATCH | /api/v1/sessions/{id}/status | JWT | Update status |
| POST | /api/v1/sessions/{id}/join | JWT | Join session |
| POST | /api/v1/sessions/{id}/leave | JWT | Leave session |
| GET | /api/v1/sessions/{id}/participants | JWT | List participants |
| POST | /api/v1/sessions/{id}/ratings | JWT | Submit rating |
| GET | /api/v1/sessions/{id}/ratings | JWT | Get ratings |
| GET | /health | None | Health check |
| GET | /health/ready | None | Readiness check |

---

## 3. Group Service (Port 8002)

### Purpose
Study group lifecycle, membership management, role-based permissions, and group-session linking.

### Responsibilities
- Group CRUD with ownership tracking
- Member management (join, leave, kick, promote, demote)
- Role-based permissions (admin/moderator/member)
- Internal membership/permission check endpoints (consumed by Chat Service)
- Proxy to Session Service for group-session linking
- Kafka event publishing on group changes

### Database
- **PostgreSQL**: `group_db` — `groups`, `group_members`
- **Redis DB 2**: Reserved for future caching

### Dependencies
- PostgreSQL (group_db)
- Kafka
- Session Service (HTTP proxy)

### Kafka Topics
- **Produces**: `GROUP_EVENTS` (GROUP_CREATED, GROUP_DELETED, USER_JOINED_GROUP, USER_LEFT_GROUP)

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/v1/groups/ | JWT | Create group |
| GET | /api/v1/groups/ | JWT | List groups |
| GET | /api/v1/groups/{id} | JWT | Get group |
| PATCH | /api/v1/groups/{id} | JWT | Update group (owner) |
| DELETE | /api/v1/groups/{id} | JWT | Delete group (owner) |
| POST | /api/v1/groups/{id}/join | JWT | Join group |
| POST | /api/v1/groups/{id}/leave | JWT | Leave group |
| GET | /api/v1/groups/{id}/members | JWT | List members |
| POST | /api/v1/groups/{id}/kick | JWT | Kick member (admin) |
| POST | /api/v1/groups/{id}/promote | JWT | Promote to admin |
| POST | /api/v1/groups/{id}/demote | JWT | Demote to member |
| GET | /api/v1/internal/groups/{id}/members/{uid} | Internal | Membership check |
| GET | /api/v1/internal/groups/{id}/permissions/{uid} | Internal | Permissions check |
| GET | /api/v1/internal/groups/{id}/sessions | Internal | Proxy to Session |
| POST | /api/v1/internal/groups/{id}/sessions/{sid} | Internal | Proxy to Session |
| GET | /health | None | Health check |

---

## 4. Chat Service (Port 8003)

### Purpose
Real-time group messaging with WebSocket, message history, online presence, and group membership mirroring.

### Responsibilities
- Message CRUD (send, edit, soft-delete)
- WebSocket endpoint for real-time push
- Online presence tracking (Redis TTL)
- Unread message counts per user
- Read receipts
- Group membership mirror via Kafka GROUP_EVENTS consumer
- Recent message cache (Redis)

### Database
- **MongoDB**: `chat_db` — `messages`, `group_memberships`
- **Redis DB 3**: Recent messages cache, online presence

### Dependencies
- MongoDB
- Redis
- Kafka

### Kafka Topics
- **Produces**: `CHAT_EVENTS` (CHAT_MESSAGE_SENT)
- **Consumes**: `GROUP_EVENTS` (GROUP_CREATED, GROUP_DELETED, USER_JOINED_GROUP, USER_LEFT_GROUP)

### WebSocket Protocol
- Endpoint: `/api/v1/groups/{group_id}/ws?token=<jwt>`
- JWT validated on connect
- Membership checked via local MongoDB mirror (no HTTP call to Group Service)
- Heartbeat: server sends `{"event":"ping"}` every 20s, client responds `{"event":"pong"}`
- Messages sent via REST POST; WebSocket is push-only (server → client)

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/v1/groups/{id}/messages | JWT | Send message |
| GET | /api/v1/groups/{id}/messages | JWT | Get messages |
| DELETE | /api/v1/messages/{id} | JWT | Delete message |
| PATCH | /api/v1/messages/{id} | JWT | Edit message |
| GET | /api/v1/groups/{id}/online | JWT | Online count |
| POST | /api/v1/groups/{id}/read | JWT | Mark read |
| GET | /api/v1/groups/{id}/unread-count | JWT | Unread count |
| WS | /api/v1/groups/{id}/ws?token= | JWT | WebSocket |
| GET | /health | None | Health check |

---

## 5. Admin Service (Port 8004)

### Purpose
Platform administration, moderation, analytics, system settings, and audit trail.

### Responsibilities
- Admin authentication (separate JWT flow with RBAC)
- Admin user management (create, list, deactivate, password reset)
- Platform user management (list, suspend, activate)
- Tutor verification management (approve/reject)
- Content moderation
- System settings CRUD
- Analytics dashboard data
- Audit trail via AdminAction model
- Super admin auto-creation on startup

### Database
- **PostgreSQL**: `admin_db` — `admin_user`, `admin_action`, `platform_setting`
- **Redis DB 6**: Admin session cache

### Dependencies
- PostgreSQL (admin_db)
- Redis
- Kafka
- Identity Service (HTTP health check)
- Group Service (HTTP health check)

### Kafka Topics
- **Produces**: `ADMIN_EVENTS`

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/v1/admin/create | JWT (super_admin) | Create admin |
| GET | /api/v1/admin/list | JWT (admin) | List admins |
| GET | /api/v1/admin/{id} | JWT (admin) | Get admin |
| PUT | /api/v1/admin/{id} | JWT (admin) | Update admin |
| POST | /api/v1/admin/{id}/deactivate | JWT (admin) | Deactivate admin |
| POST | /api/v1/admin/{id}/activate | JWT (admin) | Activate admin |
| POST | /api/v1/admin/change-password | JWT | Change password |
| POST | /api/v1/admin/{id}/reset-password | JWT (super_admin) | Reset password |
| GET | /api/v1/analytics/overview | JWT (admin) | Analytics overview |
| GET | /api/v1/users/ | JWT (admin) | List users |
| POST | /api/v1/moderation/suspend/{id} | JWT (admin) | Suspend user |
| GET | /api/v1/system/settings | JWT (admin) | List settings |
| PUT | /api/v1/system/settings/{key} | JWT (admin) | Update setting |
| GET | /health | None | Health check |

---

## 6. Payment Service (Port 8005)

### Purpose
Payment processing, wallet management, and transaction history.

### Responsibilities
- Payment intent creation and confirmation
- Payment history and details retrieval
- Refund processing
- Wallet balance management
- Wallet top-up and withdrawal
- Transaction history
- Platform fee calculation
- Kafka event publishing on payment success/failure

### Database
- **PostgreSQL**: `payment_db` — `payments`, `wallets`, `transactions`
- **Redis DB 6**: Idempotency keys, payment locks

### Dependencies
- PostgreSQL (payment_db)
- Redis
- Kafka

### Kafka Topics
- **Produces**: `PAYMENT_EVENTS` (PAYMENT_SUCCESS, PAYMENT_FAILED)

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/v1/payments/create-intent | None | Create payment intent |
| POST | /api/v1/payments/confirm | None | Confirm payment |
| GET | /api/v1/payments/{id} | None | Get payment |
| POST | /api/v1/payments/{id}/refund | None | Refund payment |
| GET | /api/v1/wallet/balance | None | Wallet balance |
| GET | /api/v1/wallet/transactions | None | Transaction history |
| POST | /api/v1/wallet/add-money | None | Add money |
| POST | /api/v1/wallet/withdraw | None | Withdraw |
| GET | /api/v1/payments/admin/earnings | None | Admin earnings |
| GET | /api/v1/payments/tutor/{id}/earnings | None | Tutor earnings |
| GET | /health | None | Health check |

---

## 7. Verification Service (Port 8006)

### Purpose
Tutor document verification, KYC workflow, and admin review process.

### Responsibilities
- Verification request management
- Document storage with MIME type validation
- Admin review workflow (pending → under_review → verified/rejected)
- Kafka event publishing for verification state changes
- User events consumption for profile state tracking
- Verification status cache (Redis)

### Database
- **PostgreSQL**: `verification_db` — `tutor_verification_requests`, `verification_documents`
- **Redis DB 0**: Verification status cache

### Dependencies
- PostgreSQL (verification_db)
- Redis
- Kafka

### Kafka Topics
- **Produces**: `VERIFICATION_EVENTS` (VERIFICATION_SUBMITTED, VERIFICATION_APPROVED, VERIFICATION_REJECTED), `USER_EVENTS` (TUTOR_VERIFIED, TUTOR_REJECTED)
- **Consumes**: `VERIFICATION_EVENTS` (TUTOR_APPLICATION_SUBMITTED)

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/v1/verification/status | JWT | Get verification status |
| GET | /api/v1/verification/history | JWT | Get history |
| GET | /api/v1/admin/verification/ | JWT (admin) | List requests |
| GET | /api/v1/admin/verification/pending | JWT (admin) | Pending requests |
| GET | /api/v1/admin/verification/{id} | JWT (admin) | Request detail |
| POST | /api/v1/admin/verification/{id}/review | JWT (admin) | Mark under review |
| POST | /api/v1/admin/verification/{id}/approve | JWT (admin) | Approve |
| POST | /api/v1/admin/verification/{id}/reject | JWT (admin) | Reject |
| GET | /health | None | Health check |

---

## 8. Notification Service (Port 8007)

### Purpose
Event-driven in-app notification system with preferences, templates, and WebSocket delivery.

### Responsibilities
- Event-driven notification creation from all Kafka topics
- Notification preferences per user (opt-in/out per event type)
- Notification templates per event type (configurable via API)
- Unread count caching (Redis)
- WebSocket pub/sub for real-time notification delivery
- Failed event recording for observability
- Email verification worker integration

### Database
- **PostgreSQL**: `notification_db` — `notifications`, `notification_templates`, `notification_preferences`, `notification_delivery_logs`
- **Redis DB 7**: Unread counts, pub/sub, preferences

### Dependencies
- PostgreSQL (notification_db)
- Redis
- Kafka (8 topics consumed)
- WebSocket Manager

### Kafka Topics Consumed
- `USER_EVENTS` — USER_CREATED, TUTOR_VERIFIED, USER_REGISTERED
- `SESSION_EVENTS` — SESSION_CREATED, SESSION_CANCELLED, SESSION_REMINDER, SESSION_STATUS_CHANGED, SESSION_STARTED, SESSION_ENROLLED
- `GROUP_EVENTS` — GROUP_JOINED, GROUP_CREATED
- `PAYMENT_EVENTS` — PAYMENT_SUCCESS, PAYMENT_FAILED
- `VERIFICATION_EVENTS` — VERIFICATION_SUBMITTED, VERIFICATION_APPROVED, VERIFICATION_REJECTED
- `CHAT_EVENTS` — CHAT_MESSAGE_SENT
- `RECOMMENDATION_EVENTS` — TUTOR_RECOMMENDED
- `RATING_EVENTS` — SESSION_RATED, RATING_SUBMITTED

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/v1/notifications | JWT | List notifications |
| GET | /api/v1/notifications/unread | JWT | Unread count |
| PATCH | /api/v1/notifications/{id}/read | JWT | Mark read |
| PATCH | /api/v1/notifications/read | JWT | Mark all read |
| DELETE | /api/v1/notifications/{id} | JWT | Delete notification |
| GET | /api/v1/preferences | JWT | Get preferences |
| PUT | /api/v1/preferences | JWT | Update preferences |
| GET | /api/v1/templates | JWT | List templates |
| POST | /api/v1/templates | JWT | Create template |
| GET | /api/v1/templates/{event_type} | JWT | Get template |
| GET | /health | None | Health check |

---

## 9. Recommendation Service (Port 8008)

### Purpose
AI-driven tutor ranking, search, trending, subject-based, nearby, and personalized recommendations.

### Responsibilities
- Top ranked tutors by recommendation score
- Trending tutors by growth rate
- Subject-based filtering with score ordering
- Geospatial nearby search (Haversine formula)
- Similar tutors based on subject overlap and rating proximity
- Personalized recommendations (falls back to global top)
- Score calculation: `Score = (0.7 × avg_rating / 5.0) + (0.3 × activity_score)`
- Redis caching for all endpoints
- Admin recalculation and cache refresh endpoints
- Rating event consumption → updates metrics and scores
- User event consumption → marks verified/rejected

### Database
- **PostgreSQL**: `recommendation_db` — `tutor_metrics`, `recommendation_scores`, `trending_tutors`
- **Redis DB 8**: Recommendation caches (configurable TTL, default 600s)

### Dependencies
- PostgreSQL (recommendation_db)
- Redis
- Kafka

### Kafka Topics Consumed
- `RATING_EVENTS` — RATING_SUBMITTED, SESSION_RATED
- `USER_EVENTS` — TUTOR_VERIFIED, TUTOR_REJECTED

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/v1/recommendations/top | None | Top ranked tutors |
| GET | /api/v1/recommendations/trending | None | Trending tutors |
| GET | /api/v1/recommendations/subject/{subject} | None | By subject |
| GET | /api/v1/recommendations/search | None | Search with filters |
| GET | /api/v1/recommendations/nearby | None | Nearby tutors |
| GET | /api/v1/recommendations/user/{id} | JWT | Personalized |
| GET | /api/v1/recommendations/tutor/{id}/similar | None | Similar tutors |
| GET | /api/v1/recommendations/tutor/{id} | None | Tutor metrics |
| POST | /api/v1/recommendations/admin/recalculate | Admin | Trigger recalc |
| POST | /api/v1/recommendations/admin/cache/refresh | Admin | Clear cache |
| GET | /health | None | Health check |
| GET | /health/ready | None | Deep health check |

---

## Service Dependency Graph

```
                        ┌─────────────────┐
                        │  Identity       │
                        │  Service (:8000)│
                        └────────┬────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 │               │               │
                 ▼               ▼               ▼
        ┌────────────────┐ ┌──────────┐ ┌────────────────┐
        │  Session       │ │ Group    │ │  Verification  │
        │  Service (:8001)│ │ Service │ │  Service (:8006)│
        └────────┬───────┘ │ (:8002) │ └─────────────────┘
                 │          └────┬─────┘
                 │               │ HTTP proxy
                 │               ▼
                 │        ┌──────────┐
                 │        │ Session  │
                 │        │ Service  │
                 │        └──────────┘
                 │
                 ▼
        ┌────────────────┐
        │  Payment       │
        │  Service (:8005)│
        └────────────────┘

        ┌────────────────┐      ┌────────────────┐
        │  Chat          │──────│  Notification  │
        │  Service (:8003)│ Kafka│  Service (:8007)│
        └────────────────┘      └────────────────┘

        ┌────────────────┐
        │  Admin         │
        │  Service (:8004)│
        └────────────────┘

        ┌────────────────┐
        │  Recommendation│
        │  Service (:8008)│
        └────────────────┘
```

Kafka event flows:
- Identity ──TUTOR_VERIFIED──► Session, Notification, Recommendation
- Identity ──TUTOR_APPLICATION_SUBMITTED──► Verification
- Session ──RATING_SUBMITTED──► Identity, Notification, Recommendation
- Group ──GROUP_EVENTS──► Chat, Notification
- Payment ──PAYMENT_SUCCESS──► Session, Notification
- Verification ──TUTOR_VERIFIED/TUTOR_REJECTED──► USER_EVENTS topic
- Chat ──CHAT_EVENTS──► Notification