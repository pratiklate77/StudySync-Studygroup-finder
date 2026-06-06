# ADR-001: Why FastAPI

**Status:** Accepted

**Context:** We needed an async Python web framework for building high-performance microservices with async I/O, auto-generated docs, and WebSocket support.

**Decision:** We chose FastAPI for all 9 microservices.

**Rationale:** Native async/await, auto OpenAPI docs via type hints, Pydantic validation, dependency injection, WebSocket support, top benchmarks.

**Consequences:** Consistent framework across services, auto docs at /docs, Python 3.12 required.