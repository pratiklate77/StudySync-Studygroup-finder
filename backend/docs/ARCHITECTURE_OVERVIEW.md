# StudySync — Architecture Overview

## Project Overview

**StudySync** is a distributed microservices learning platform that connects students with tutors, enables collaborative study groups, and provides real-time communication. The platform supports session discovery, tutor verification, payments, notifications, and AI-driven recommendations.

### Business Problem

Traditional tutoring platforms are monolithic, lack real-time collaboration features, and don't support the flexibility of both free community-led study groups and paid professional tutoring sessions. Students struggle to find nearby study partners, and tutors lack a streamlined platform to offer their services.

### Solution Overview

StudySync provides:
- **Free study sessions** hosted by any user
- **Paid tutoring sessions** hosted by verified tutors
- **Geospatial discovery** of nearby sessions
- **Real-time group chat** with WebSocket messaging
- **Event-driven architecture** for scalable inter-service communication
- **Document-based KYC** for tutor verification
- **AI-driven recommendations** for tutor discovery

### Key Features

| Feature | Description |
|---------|-------------|
| User Management | Registration, JWT auth, profile management, email verification |
| Tutor Onboarding | Document upload, admin verification workflow, KYC |
| Session Management | CRUD, geospatial nearby search, join/leave, status transitions |
| Study Groups | Create/manage groups, membership, role-based permissions |
| Real-time Chat | WebSocket messaging, online presence, read receipts |
| Payments & Wallets | Payment intents, wallet management, refunds |
| Recommendations | Top ranked, trending, subject-based, nearby, similar tutors |
| Notifications | Event-driven, preferences, templates, WebSocket delivery |
| Platform Admin | Admin RBAC, moderation, analytics, audit trail, system settings |

### System Flow

```
User → HTTP/WebSocket → Microservices → PostgreSQL/MongoDB/Redis
                                     ↓
                              Kafka Event Bus
                                     ↓
                   Notification Service → WebSocket/Email
```

---

## Technology Stack

### Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API Framework | FastAPI (Python 3.12) | Async REST API framework |
| Relational DB | PostgreSQL 16 (7 instances) | ACID-compliant persistence per service |
| Document DB | MongoDB 7 (2 instances) | Flexible schemas, geospatial queries |
| Cache & Locks | Redis 7 | Caching, tokens, presence, idempotency |
| Message Broker | Apache Kafka 7.5 + Zookeeper | Async event bus |
| ORM/ODM | SQLAlchemy 2.0 async + Motor | Database access |
| Migrations | Alembic | PostgreSQL schema migrations |
| File Validation | python-magic + aiofiles | Document upload validation |

### Frontend (separate)

| Component | Technology |
|-----------|-----------|
| Framework | React + TypeScript |
| Build Tool | Vite |
| BFF | Node.js (Express) |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Containerization | Docker + Docker Compose |
| Service Network | Bridge network with service discovery |
| Health Checks | HTTP health endpoints per service |
| Monitoring | Structured logging, readiness probes |

---

## Microservice Inventory

| # | Service | Port | Database | Purpose |
|---|---------|------|----------|---------|
| 1 | Identity Service | 8000 | PostgreSQL (identity_db) | Auth, JWT, users, tutor profiles |
| 2 | Session Service | 8001 | MongoDB (session_db) | Sessions, ratings, geospatial search |
| 3 | Group Service | 8002 | PostgreSQL (group_db) | Groups, memberships, permissions |
| 4 | Chat Service | 8003 | MongoDB (chat_db) | Real-time messaging, WebSocket |
| 5 | Admin Service | 8004 | PostgreSQL (admin_db) | Platform administration |
| 6 | Payment Service | 8005 | PostgreSQL (payment_db) | Payments, wallets |
| 7 | Verification Service | 8006 | PostgreSQL (verification_db) | Tutor KYC, documents |
| 8 | Notification Service | 8007 | PostgreSQL (notification_db) | In-app notifications |
| 9 | Recommendation Service | 8008 | PostgreSQL (recommendation_db) | Tutor rankings |

---

## Communication Patterns

| Pattern | Mechanism | Use Case |
|---------|-----------|----------|
| Synchronous REST | HTTP/JSON (FastAPI) | Client ↔ Service communication |
| Event-Driven Async | Kafka Topics | Inter-service state propagation |
| Real-time | WebSocket | Chat messaging, notification push |
| Service-to-Service | HTTP (httpx) | Group → Session proxy calls |
| Shared Auth | JWT (HS256) | Single sign-on across services |

---

## Kafka Event Topics

| Topic | Producer Services | Consumer Services | Events |
|-------|------------------|------------------|--------|
| USER_EVENTS | Identity, Verification | Identity, Session, Notification, Recommendation | TUTOR_VERIFIED, TUTOR_REJECTED, USER_CREATED |
| RATING_EVENTS | Session | Identity, Session, Recommendation | RATING_SUBMITTED, SESSION_RATED |
| GROUP_EVENTS | Group | Chat, Notification | GROUP_CREATED, USER_JOINED_GROUP, USER_LEFT_GROUP, GROUP_DELETED |
| PAYMENT_EVENTS | Payment | Session, Notification | PAYMENT_SUCCESS, PAYMENT_FAILED |
| VERIFICATION_EVENTS | Identity, Verification | Verification, Notification | TUTOR_APPLICATION_SUBMITTED, VERIFICATION_APPROVED, VERIFICATION_REJECTED |
| CHAT_EVENTS | Chat | Notification | CHAT_MESSAGE_SENT |
| ADMIN_EVENTS | Admin | (Future) | Admin lifecycle events |

---

## Data Architecture

### Polyglot Persistence

```
PostgreSQL (7 instances)        MongoDB (2 instances)         Redis (8 databases)
├── identity_db: users,         ├── session_db: sessions,     ├── DB 0: Identity cache
│   tutor_profiles              │    ratings, verified_tutors │         tokens, leaderboard
├── group_db: groups,           └── chat_db: messages,        ├── DB 1: Session nearby cache
│   group_members                    group_memberships        ├── DB 2: Group (reserved)
├── admin_db: admin_users,                                  ├── DB 3: Chat recent messages
│   admin_actions, settings                                    │         online presence
├── payment_db: payments,                                    ├── DB 6: Admin + Payment
│   wallets, transactions                                    ├── DB 7: Notification unread
├── verification_db: verification_requests,                   │         pub/sub, preferences
│   verification_documents                                   └── DB 8: Recommendation caches
├── notification_db: notifications,
│   templates, preferences
└── recommendation_db: tutor_metrics,
    recommendation_scores, trending_tutors
```

### Database-per-Service

Every service owns its database exclusively. No cross-service foreign keys. Inter-service data consistency is maintained through Kafka event propagation.

---

## Resilience Patterns

### Kafka Resilience (Circuit Breaker + Fallback + Retry)

All Kafka-producing services implement:
1. **Circuit Breaker** — prevents cascading failures when Kafka is unavailable
2. **In-Memory Fallback Store** — queues events when circuit is open
3. **Retry Worker** — background task with exponential backoff (2s base, 30s max)
4. **Graceful Degradation** — services start and operate without Kafka

### Startup Resilience

- All services handle Kafka startup failures gracefully
- Session Service supports `STANDALONE_MODE` for development
- Health endpoints report Kafka connectivity status
- Services continue operating in degraded mode when dependencies are unavailable

---

## Security Architecture

- **JWT Access Tokens** — 15-1440 min TTL, HS256 signed, validated locally
- **JWT Refresh Tokens** — 7 day TTL, stored in Redis with JTI, rotation on use
- **Admin Authentication** — Separate admin JWT flow with RBAC (super_admin, admin, moderator)
- **Admin API Key** — Constant-time comparison for tutor verification
- **File Validation** — MIME type checking, file size limits (5MB)
- **Soft Deletes** — `is_active` flags preserve data integrity
- **Rate Limiting** — Security middleware on Admin Service

---

## Deployment Architecture

### Docker Compose

The entire stack runs via Docker Compose with:
- 9 microservices (ports 8000-8008)
- 7 PostgreSQL instances
- 2 MongoDB instances
- 1 Redis instance
- 1 Kafka + 1 Zookeeper instance
- Health-checked dependencies
- Named volumes for persistence
- Bridge network for service discovery

### Startup Order

```
Zookeeper → Kafka
         → PostgreSQL instances → Microservices
         → MongoDB instances
         → Redis
```

### Scaling Notes

- All services are stateless and horizontally scalable
- Chat Service WebSocket connection manager is in-memory (single instance); multi-instance requires Redis Pub/Sub
- Kafka allows consumer group scaling across service instances