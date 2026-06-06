# StudySync — Microservices Documentation

> **A comprehensive documentation hub for the StudySync microservices backend platform.**

## Overview

StudySync is a distributed, event-driven microservices platform for collaborative learning. It connects students with tutors, enables study group discovery, provides real-time chat, and supports payment processing, tutor verification, notifications, and AI-driven recommendations.

**9 microservices** | **7 PostgreSQL + 2 MongoDB + Redis** | **Kafka Event Bus** | **Docker Compose**

## Documentation Index

All documentation is organized under `backend/docs/`.

### Architecture

| Document | Description |
|----------|-------------|
| [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) | High-level system architecture, technology stack, communication patterns |
| [MICROSERVICES_GUIDE.md](MICROSERVICES_GUIDE.md) | Detailed breakdown of all 9 microservices |
| [HLD.md](HLD.md) | High-Level Design document |
| [LLD.md](LLD.md) | Low-Level Design document |

### API & Events

| Document | Description |
|----------|-------------|
| [API_REFERENCE.md](API_REFERENCE.md) | Complete API endpoint reference for all services |
| [EVENT_CATALOG.md](EVENT_CATALOG.md) | All Kafka events with payloads, producers, consumers |
| [KAFKA_ARCHITECTURE.md](KAFKA_ARCHITECTURE.md) | Kafka architecture, resilience patterns, topic inventory |

### Data & Security

| Document | Description |
|----------|-------------|
| [DATABASE_DESIGN.md](DATABASE_DESIGN.md) | Complete database schemas, relationships, migrations |
| [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) | JWT flow, authentication, authorization, security risks |

### Deployment

| Document | Description |
|----------|-------------|
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Local dev setup, Docker deployment, production guide |

### Diagrams & Decisions

| Document | Description |
|----------|-------------|
| [SEQUENCE_DIAGRAMS.md](SEQUENCE_DIAGRAMS.md) | Mermaid sequence diagrams for all key workflows |
| [SERVICE_COMMUNICATION_MATRIX.md](SERVICE_COMMUNICATION_MATRIX.md) | All inter-service communication flows |

### Architecture Decision Records

| Document | Decision |
|----------|----------|
| [adr/ADR-001-why-fastapi.md](adr/ADR-001-why-fastapi.md) | Why FastAPI for all services |
| [adr/ADR-002-why-kafka.md](adr/ADR-002-why-kafka.md) | Why Apache Kafka for event bus |
| [adr/ADR-003-why-postgresql.md](adr/ADR-003-why-postgresql.md) | Why PostgreSQL as relational database |
| [adr/ADR-004-why-redis.md](adr/ADR-004-why-redis.md) | Why Redis for caching and presence |
| [adr/ADR-005-why-docker.md](adr/ADR-005-why-docker.md) | Why Docker for containerization |
| [adr/ADR-006-why-event-driven.md](adr/ADR-006-why-event-driven.md) | Why Event-Driven Architecture |

## Quick Links

- **Identity Service**: Port 8000 — Auth, JWT, users, tutors
- **Session Service**: Port 8001 — Sessions, ratings, geospatial
- **Group Service**: Port 8002 — Groups, memberships
- **Chat Service**: Port 8003 — Real-time messaging, WebSocket
- **Admin Service**: Port 8004 — Platform administration
- **Payment Service**: Port 8005 — Payments, wallets
- **Verification Service**: Port 8006 — Tutor KYC
- **Notification Service**: Port 8007 — In-app notifications
- **Recommendation Service**: Port 8008 — Tutor rankings

## Missing / Future Features

The following are documented as **Not Implemented** or **Future Scope**:
- API Gateway (direct service access currently)
- Transactional Outbox pattern for Kafka
- OAuth 2.0 / social login
- Email delivery service
- Elasticsearch search
- Rate limiting on auth endpoints
- HTTPS/TLS (reverse proxy needed)
- 2FA for admin accounts
- TUTOR_SUSPENDED event handler
- CHAT_MESSAGE_DELETED consumer