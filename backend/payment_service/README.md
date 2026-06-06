# StudySync Payment Service

The Payment Service manages payment records, wallet balances, wallet transactions, refunds, and payment events. It stores financial state in PostgreSQL, uses Redis for lightweight caching, and publishes payment outcomes to Kafka.

## Features

- Create payment intents with platform fee calculation.
- Confirm payments and publish `PAYMENT_SUCCESS`.
- Fetch payment records.
- Refund completed payments.
- Wallet balance, transaction history, add-money, and withdraw endpoints.
- Async SQLAlchemy persistence.
- Redis client initialized at startup.
- Kafka producer for payment events.

## Tech Stack

FastAPI, PostgreSQL, Async SQLAlchemy, Redis, Kafka, Pydantic, Docker.

## Project Structure

```text
app/
├── api/              # payment and wallet routes
├── core/             # settings, database, Redis
├── models/           # Payment, Wallet, Transaction tables
├── schemas/          # payment/wallet request and response models
├── services/         # payment business logic
└── main.py           # startup and health
```

## Database Design

PostgreSQL database: `payment_db`.

| Table | Purpose | Important fields |
| --- | --- | --- |
| `payments` | Payment lifecycle records. | `id`, `user_id`, `tutor_id`, `session_id`, `amount`, `platform_fee`, `status` (`pending`, `completed`, `failed`, `refunded`), `payment_method`, `provider_id`, timestamps |
| `wallets` | Per-user wallet balance. | `id`, `user_id` unique, `balance`, timestamps |
| `transactions` | Wallet ledger. | `id`, `wallet_id` FK, `payment_id`, `type` (`credit`, `debit`, `payment`, `refund`), `amount`, `description`, `created_at` |

## API Documentation

Base URL in Docker: `http://localhost:8005`. API prefix: `/api/v1`.

| Method | Endpoint | Auth | Purpose | Request/params | Response |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/payments/create-intent` | Current code reads user from request state if provided | Create pending payment and calculate platform fee. | `PaymentIntentRequest`: user/tutor/session/payment data. | `PaymentIntentResponse` |
| `POST` | `/payments/confirm` | Same as above | Confirm a pending payment. | `PaymentConfirmRequest`. | `PaymentResponse` |
| `GET` | `/payments/{payment_id}` | Same as above | Fetch payment by id. | `payment_id` path. | `PaymentResponse` |
| `POST` | `/payments/{payment_id}/refund` | Same as above | Refund a completed payment. | `payment_id`, optional reason/body per schema. | `PaymentResponse` |
| `GET` | `/wallet/balance` | Same as above | Return wallet balance for current/requested user. | User context/query as implemented. | `WalletBalanceResponse` |
| `GET` | `/wallet/transactions` | Same as above | List wallet transactions. | `limit`, `offset`. | `WalletTransactionsResponse` |
| `POST` | `/wallet/add-money` | Same as above | Credit wallet. | Amount request schema. | `WalletBalanceResponse` |
| `POST` | `/wallet/withdraw` | Same as above | Debit wallet. | Amount request schema. | `WalletBalanceResponse` |

Operations: `GET /health`, `GET /docs`.

## Authentication Flow

The current Payment API does not define a dedicated JWT dependency like Identity, Session, or Group. Several handlers use request context/service methods, so a production deployment should add explicit Bearer JWT validation and authorization around payment and wallet ownership before exposing this service externally.

## Kafka Integration

| Direction | Topic | Events | Purpose |
| --- | --- | --- | --- |
| Produce | `PAYMENT_EVENTS` | `PAYMENT_SUCCESS` | Notifies Session/Notification-style consumers that a payment completed. |

## Redis Usage

`REDIS_URL` is configured and a Redis client is initialized. `CACHE_TTL_SECONDS` is available for service-level caching. The visible implementation is primarily database-backed.

## Inter-Service Communication

Payment records reference `user_id`, `tutor_id`, and `session_id` owned by Identity and Session services. Payment emits Kafka events rather than directly updating Session.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async PostgreSQL URL for `payment_db`. |
| `REDIS_URL` | Redis URL, compose/local value currently overlaps admin DB 6. |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker list. |
| `KAFKA_PAYMENT_EVENTS_TOPIC` | Topic for payment events. |
| `PLATFORM_FEE_PERCENTAGE` | Fee percentage used when creating payment intents. |
| `CACHE_TTL_SECONDS` | Generic cache TTL. |

## Docker and Startup

The Dockerfile exposes `8005` and starts Uvicorn. Compose waits for `postgres_payment`, Redis, and Kafka.

```bash
docker compose up -d --build payment_service
docker compose logs -f payment_service
```

## Running Locally

```bash
cd payment_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8005
```

## Testing Guide

- Create a payment intent, confirm it, then fetch it by id.
- Verify wallet transaction rows after add/withdraw/refund operations.
- Consume `PAYMENT_EVENTS` from Kafka and confirm `PAYMENT_SUCCESS`.
- Use PostgreSQL queries against `payment_db` to verify ledger consistency.

## Known Limitations

- No explicit JWT dependency is currently wired into the routes.
- There is no external payment provider SDK integration; provider id is modeled but processing is local.
- No Alembic directory is present in this service, so schema creation/migration needs attention before production use.
