# ADR-006: Why Event-Driven Architecture

**Status:** Accepted

**Context:** We needed an architecture that decouples microservices, avoids distributed transactions (2PC), and enables easy extension with new services.

**Decision:** We chose Event-Driven Architecture using Apache Kafka as the message backbone.

**Rationale:** Service independence (no synchronous dependencies), no cascading failures, easy extensibility (subscribe without modifying producers), immutable audit trail, consumer group scalability.

**Trade-offs:** Eventual consistency window, Kafka operational overhead, consumer idempotency required, async debugging complexity.

**Consequences:** All services decoupled through Kafka topics, resilience layer (circuit breaker + fallback + retry), event catalog documents all events and schemas, all consumers must be idempotent.