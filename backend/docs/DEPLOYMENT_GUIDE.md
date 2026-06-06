# StudySync — Deployment Guide

## Overview

StudySync is deployed as a Docker Compose stack with 9 microservices and supporting infrastructure. This guide covers local development, Docker deployment, and production recommendations.

---

## Local Development Setup

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- PostgreSQL client (optional, for direct DB access)
- MongoDB Shell (optional, for direct DB access)

### Step 1: Clone and Configure

```bash
git clone <repository-url>
cd studysync

# Copy environment files
cp identity_service/.env.example identity_service/.env
cp group_service/.env.example group_service/.env
cp session_service/.env.example session_service/.env
cp admin_service/.env.example admin_service/.env
cp payment_service/.env.example payment_service/.env
cp verification_service/.env.example verification_service/.env
cp notification_service/.env.example notification_service/.env
cp recommendation_service/.env.example recommendation_service/.env
```

### Step 2: Set JWT Secret

Ensure `JWT_SECRET_KEY` is identical across all service `.env` files:

```bash
# Generate a secure key
openssl rand -hex 32
```

### Step 3: Start Infrastructure

```bash
docker compose up -d postgres postgres_group postgres_admin postgres_payment \
  postgres_verification postgres_notification postgres_recommendation \
  mongo redis zookeeper kafka
```

### Step 4: Run Database Migrations

```bash
cd identity_service && alembic upgrade head && cd ..
cd group_service && alembic upgrade head && cd ..
cd admin_service && alembic upgrade head && cd ..
cd payment_service && alembic upgrade head && cd ..
cd verification_service && alembic upgrade head && cd ..
cd notification_service && alembic upgrade head && cd ..
cd recommendation_service && alembic upgrade head && cd ..
```

### Step 5: Start Services

```bash
# Start each service in a separate terminal, or use Docker Compose
docker compose up -d
```

Or run services locally:

```bash
cd identity_service && uvicorn app.main:app --reload --port 8000 &
cd session_service && uvicorn app.main:app --reload --port 8001 &
cd group_service && uvicorn app.main:app --reload --port 8002 &
cd chat_service && uvicorn app.main:app --reload --port 8003 &
cd admin_service && uvicorn app.main:app --reload --port 8004 &
cd payment_service && uvicorn app.main:app --reload --port 8005 &
cd verification_service && uvicorn app.main:app --reload --port 8006 &
cd notification_service && uvicorn app.main:app --reload --port 8007 &
cd recommendation_service && uvicorn app.main:app --reload --port 8008 &
```

---

## Docker Deployment

### Full Stack Deployment

```bash
# Build and start all services
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### Service Startup Order

```
1. Zookeeper → Kafka
2. PostgreSQL instances (all 7)
3. MongoDB instances (2)
4. Redis
5. Identity Service
6. Session Service
7. Group Service
8. Chat Service
9. Admin Service
10. Payment Service
11. Verification Service
12. Notification Service
13. Recommendation Service
```

### Docker Compose Structure

```yaml
# Key infrastructure services
services:
  postgres:           # Identity Service DB
  postgres_group:     # Group Service DB
  postgres_admin:     # Admin Service DB
  postgres_payment:   # Payment Service DB
  postgres_verification:  # Verification Service DB
  postgres_notification:  # Notification Service DB
  postgres_recommendation: # Recommendation Service DB
  mongo:              # Session & Chat Service DB
  redis:              # All services cache
  zookeeper:          # Kafka coordinator
  kafka:              # Event bus

  # Application services
  identity_service:   # Auth, users, tutors (port 8000)
  session_service:    # Sessions, ratings (port 8001)
  group_service:      # Groups, memberships (port 8002)
  chat_service:       # Real-time messaging (port 8003)
  admin_service:      # Platform administration (port 8004)
  payment_service:    # Payments, wallets (port 8005)
  verification_service: # Tutor KYC (port 8006)
  notification_service: # Notifications (port 8007)
  recommendation_service: # Tutor rankings (port 8008)
```

### Session Service Only Development

```bash
# Start only session service with its dependencies
docker compose -f docker-compose.yml up -d mongo redis zookeeper kafka session_service
```

---

## Production Deployment

### Architecture Recommendations

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Load       │     │  Load       │     │  Load       │
│  Balancer   │────▶│  Balancer   │────▶│  Balancer   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Identity     │   │ Session      │   │ Group        │
│ Service xN   │   │ Service xN   │   │ Service xN   │
└──────────────┘   └──────────────┘   └──────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Kafka       │
                    │  Cluster x3  │
                    └──────────────┘
```

### Infrastructure Requirements

| Component | Production Sizing | Notes |
|-----------|-----------------|-------|
| PostgreSQL | HA cluster (Patroni) or RDS/Aurora | 7 databases, each needs primary + replica |
| MongoDB | Replica set (3 nodes) | Session, Chat services |
| Redis | Sentinel or Cluster mode | 8 logical databases |
| Kafka | 3+ brokers, replication factor 3 | Partitioned topics |
| API Services | 2-3 instances each | Stateless, horizontally scalable |

### Environment Variables

All services require the following environment variables. Use a secrets manager in production.

#### Core Variables (All Services)

| Variable | Description | Example |
|----------|-------------|---------|
| `JWT_SECRET_KEY` | HMAC signing key | `openssl rand -hex 32` |
| `JWT_ALGORITHM` | Signing algorithm | `HS256` |

#### Per-Service Variables

**Identity Service** (`identity_service/.env`):
```env
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/identity_db
REDIS_URL=redis://redis:6379/0
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
KAFKA_CLIENT_ID=identity-service
JWT_SECRET_KEY=<shared-secret>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
TOP_TUTORS_CACHE_TTL_SECONDS=300
ADMIN_API_KEY=<admin-key>
```

**Session Service** (`session_service/.env`):
```env
MONGODB_URL=mongodb://mongo:27017
MONGODB_DB_NAME=session_db
REDIS_URL=redis://redis:6379/1
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
JWT_SECRET_KEY=<shared-secret>
AUTH_ENABLED=true
KAFKA_ENABLED=true
STANDALONE_MODE=false
```

**Group Service** (`group_service/.env`):
```env
DATABASE_URL=postgresql+asyncpg://user:pass@postgres_group:5432/group_db
REDIS_URL=redis://redis:6379/2
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
JWT_SECRET_KEY=<shared-secret>
SESSION_SERVICE_URL=http://session_service:8001
```

**Chat Service** (`chat_service/.env`):
```env
MONGODB_URL=mongodb://mongo:27017
MONGODB_DB_NAME=chat_db
REDIS_URL=redis://redis:6379/3
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
JWT_SECRET_KEY=<shared-secret>
```

**Admin Service** (`admin_service/.env`):
```env
DATABASE_URL=postgresql+asyncpg://user:pass@postgres_admin:5432/admin_db
REDIS_URL=redis://redis:6379/6
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
JWT_SECRET_KEY=<admin-secret>
IDENTITY_SERVICE_URL=http://identity_service:8000
GROUP_SERVICE_URL=http://group_service:8002
```

**Payment Service** (`payment_service/.env`):
```env
DATABASE_URL=postgresql+asyncpg://user:pass@postgres_payment:5432/payment_db
REDIS_URL=redis://redis:6379/6
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
```

**Verification Service** (`verification_service/.env`):
```env
DATABASE_URL=postgresql+asyncpg://user:pass@postgres_verification:5432/verification_db
REDIS_URL=redis://redis:6379/0
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
JWT_SECRET_KEY=<shared-secret>
```

**Notification Service** (`notification_service/.env`):
```env
DATABASE_URL=postgresql+asyncpg://user:pass@postgres_notification:5432/notification_db
REDIS_URL=redis://redis:6379/7
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
```

**Recommendation Service** (`recommendation_service/.env`):
```env
DATABASE_URL=postgresql+asyncpg://user:pass@postgres_recommendation:5432/recommendation_db
REDIS_URL=redis://redis:6379/8
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
```

### Health Checks

Every service exposes health check endpoints:

```bash
# Service health
curl http://localhost:8000/health     # Identity Service
curl http://localhost:8001/health     # Session Service
curl http://localhost:8002/health     # Group Service
curl http://localhost:8003/health     # Chat Service
curl http://localhost:8004/health     # Admin Service
curl http://localhost:8005/health     # Payment Service
curl http://localhost:8006/health     # Verification Service
curl http://localhost:8007/health     # Notification Service
curl http://localhost:8008/health     # Recommendation Service

# Readiness checks
curl http://localhost:8001/health/ready  # Session Service ready
```

### Docker Health Check Configuration

```yaml
# Example from docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## Scaling

### Horizontal Scaling

All services are stateless and can be scaled horizontally:

```bash
docker compose up -d --scale identity_service=3 --scale session_service=2
```

### Scaling Considerations

| Service | Scaling Notes |
|---------|--------------|
| Identity Service | Stateless. Scale horizontally. |
| Session Service | Stateless. MongoDB is bottleneck. Consider read replicas. |
| Group Service | Stateless. PostgreSQL is bottleneck. Consider read replicas. |
| Chat Service | WebSocket connection manager is in-memory. Multi-instance requires Redis Pub/Sub for broadcast. |
| Admin Service | Stateless. Low traffic. 1-2 instances sufficient. |
| Payment Service | Stateless. Payment operations are I/O bound. |
| Verification Service | Stateless. File storage is local volume. Use shared filesystem. |
| Notification Service | Redis Pub/Sub enables multi-instance WebSocket delivery. |
| Recommendation Service | Stateless. Redis cache reduces DB load. |

### Chat Service Scaling

For multi-instance Chat Service deployment:
1. Replace in-memory `ConnectionManager` with Redis Pub/Sub
2. Use Redis for WebSocket broadcast across instances
3. Configure sticky sessions or use shared session store

---

## Backup Strategy

### Database Backups

```bash
# PostgreSQL backups
docker exec studysync-postgres pg_dump -U studysync identity_db > backup_identity.sql
docker exec studysync-postgres-group pg_dump -U studysync group_db > backup_group.sql

# MongoDB backups
docker exec studysync-mongo mongodump --out /data/backup/

# Redis persistence (AOF enabled)
# Backup /data/dump.rdb or replay AOF file
```

### Recommended Backup Schedule

| Data | Frequency | Retention |
|------|-----------|-----------|
| PostgreSQL (all DBs) | Daily full backup | 30 days |
| MongoDB | Daily full backup | 30 days |
| Kafka logs | Based on retention policy | 7 days |
| File uploads (verification docs) | Daily incremental | 90 days |
| Redis | AOF persistence | N/A (replay from DB if needed) |

---

## Disaster Recovery

### Recovery Steps

1. **Infrastructure Recovery**:
   ```bash
   docker compose up -d postgres postgres_group mongo redis zookeeper kafka
   ```

2. **Database Restoration**:
   ```bash
   # PostgreSQL
   docker exec -i studysync-postgres psql -U studysync -d identity_db < backup_identity.sql

   # MongoDB
   docker exec studysync-mongo mongorestore /data/backup/
   ```

3. **Application Recovery**:
   ```bash
   docker compose up -d --build
   ```

4. **Verification**:
   ```bash
   # Check all health endpoints
   ./check_services_health.sh
   ```

### RTO/RPO Targets

| Metric | Target |
|--------|--------|
| Recovery Time Objective (RTO) | < 30 minutes |
| Recovery Point Objective (RPO) | < 24 hours (configurable based on backup frequency) |

---

## Monitoring & Observability

### Health Endpoints Summary

| Endpoint | Services | Response |
|----------|----------|----------|
| GET /health | All | `{"status": "ok"}` |
| GET /health/ready | Session Service | Readiness with auth/kafka/standalone status |
| GET /health/kafka | Identity, Admin, Verification | Circuit breaker state, fallback queue size |
| GET /health/dependencies | Admin Service | Dependent service health |

### Logging

All services use Python's `logging` module with structured log messages:

```python
# Log format
"%(name)s - %(levelname)s - %(message)s"
```

Key log categories:
- Startup/shutdown events
- Kafka producer/consumer connectivity
- Event processing success/failure
- Database operations
- Authentication attempts

---

## Network Configuration

### Docker Network

```
Network: studysync (bridge)
Subnet: 172.x.x.x/16 (Docker default)
```

### Port Mapping

| Port | Service | Protocol |
|------|---------|----------|
| 8000 | Identity Service | HTTP |
| 8001 | Session Service | HTTP |
| 8002 | Group Service | HTTP |
| 8003 | Chat Service | HTTP + WebSocket |
| 8004 | Admin Service | HTTP |
| 8005 | Payment Service | HTTP |
| 8006 | Verification Service | HTTP |
| 8007 | Notification Service | HTTP |
| 8008 | Recommendation Service | HTTP |
| 5432-5448 | PostgreSQL instances | PostgreSQL |
| 27017 | MongoDB | MongoDB |
| 6379 | Redis | Redis |
| 9092 | Kafka | Kafka |
| 2181 | Zookeeper | Zookeeper |

### Internal DNS (Docker Compose)

```
postgres:5432          → Identity PostgreSQL
postgres_group:5432    → Group PostgreSQL
postgres_admin:5432    → Admin PostgreSQL
postgres_payment:5432  → Payment PostgreSQL
postgres_verification:5432 → Verification PostgreSQL
postgres_notification:5432 → Notification PostgreSQL
postgres_recommendation:5432 → Recommendation PostgreSQL
mongo:27017            → MongoDB
redis:6379             → Redis
kafka:29092            → Kafka (internal)
zookeeper:2181         → Zookeeper
```

---

## Verification Checklist

### Pre-Deployment

- [ ] All `.env` files exist with correct values
- [ ] `JWT_SECRET_KEY` is identical across all services
- [ ] Database URLs match runtime mode (localhost vs Docker hostnames)
- [ ] Kafka bootstrap servers match runtime mode
- [ ] `SESSION_SERVICE_URL` in Group Service is correct
- [ ] PostgreSQL migrations have been run
- [ ] MongoDB indexes will be created on startup

### Post-Deployment

- [ ] All health endpoints return `{"status": "ok"}`
- [ ] User registration and login work
- [ ] Session creation and nearby search work
- [ ] Group creation and membership work
- [ ] Chat messaging works
- [ ] Payment flow works (if payment service is active)
- [ ] Tutor verification flow works
- [ ] Notifications are delivered
- [ ] Recommendations are returned