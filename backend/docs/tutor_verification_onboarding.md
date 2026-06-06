# Tutor Verification & Onboarding System

## Architecture Overview

The Tutor Verification system follows an event-driven architecture where the **Identity Service** is the single entry point for tutor applications, and the **Verification Service** handles admin review via event consumption.

```
User (Frontend)
  │
  ▼
POST /api/v1/tutors/apply  (multipart/form-data)
  │
  ▼
Identity Service
  │  ├── Validates JWT, extracts authenticated user
  │  ├── Validates required documents (identity_proof, highest_degree)
  │  ├── Validates MIME types & file sizes
  │  ├── Stores files to /app/verification-documents/{user_id}/{doc_type}/
  │  ├── Creates pending tutor_profile (is_verified=false)
  │  └── Publishes TUTOR_APPLICATION_SUBMITTED → VERIFICATION_EVENTS topic
  │       └── Payload includes: bio, subjects, hourly_rate, document paths
  │
  ▼
Verification Service (consumes VERIFICATION_EVENTS)
  │  └── VerificationEventsConsumer handles TUTOR_APPLICATION_SUBMITTED
  │       ├── Creates TutorVerificationRequest (status: PENDING)
  │       └── Creates VerificationDocument records for each uploaded file
  │
  ▼
Admin Review (via verification_service/admin APIs)
  │
  ├── POST /api/v1/admin/verification/{id}/review  → UNDER_REVIEW
  ├── POST /api/v1/admin/verification/{id}/approve  → VERIFIED
  └── POST /api/v1/admin/verification/{id}/reject   → REJECTED
       │
       ▼
  Kafka: USER_EVENTS topic
       │
       ├── TUTOR_VERIFIED
       │    ├── Identity Service: Updates role→tutor, is_verified_tutor→true, profile→verified
       │    ├── Session Service: Updates verified_tutors collection (already existing)
       │    ├── Recommendation Service: Marks tutor_metrics.is_verified→true
       │    └── Notification Service: Sends approval notification
       │
       └── TUTOR_REJECTED
            ├── Identity Service: Logs rejection (no role change)
            ├── Recommendation Service: Sets recommendation_score→-1 (excludes from recs)
            └── Notification Service: Sends rejection notification
```

## Event Flow

### Kafka Topics

| Topic | Publisher | Consumers | Events |
|-------|-----------|-----------|--------|
| `VERIFICATION_EVENTS` | Identity Service (tutor apply) | Verification Service (VerificationEventsConsumer) | `TUTOR_APPLICATION_SUBMITTED` |
| `VERIFICATION_EVENTS` | Verification Service (admin review) | Notification Service | `VERIFICATION_SUBMITTED`, `VERIFICATION_APPROVED`, `VERIFICATION_REJECTED` |
| `USER_EVENTS` | Verification Service (admin approval/rejection) | Identity Service, Session Service, Recommendation Service, Notification Service | `TUTOR_VERIFIED`, `TUTOR_REJECTED` |
| `RATING_EVENTS` | Session Service | Identity Service, Recommendation Service | `SESSION_RATED` |

### Event Payloads

#### TUTOR_APPLICATION_SUBMITTED (from Identity Service)
```json
{
  "event": "TUTOR_APPLICATION_SUBMITTED",
  "userId": "uuid",
  "bio": "Experienced math tutor...",
  "subjects": ["mathematics", "physics"],
  "hourly_rate": "25.00",
  "documents": [
    {
      "document_type": "IDENTITY_PROOF",
      "file_name": "passport.jpg",
      "file_url": "{user_id}/identity_proof/{uuid}.jpg"
    },
    {
      "document_type": "HIGHEST_DEGREE",
      "file_name": "degree.pdf",
      "file_url": "{user_id}/highest_degree/{uuid}.pdf"
    }
  ],
  "status": "PENDING"
}
```

#### TUTOR_VERIFIED
```json
{
  "event": "TUTOR_VERIFIED",
  "event_type": "TUTOR_VERIFIED",
  "userId": "uuid",
  "user_id": "uuid",
  "verificationRequestId": "uuid",
  "status": "VERIFIED",
  "timestamp": "2026-05-28T20:00:00Z"
}
```

#### TUTOR_REJECTED
```json
{
  "event": "TUTOR_REJECTED",
  "event_type": "TUTOR_REJECTED",
  "userId": "uuid",
  "user_id": "uuid",
  "verificationRequestId": "uuid",
  "reason": "Documents did not meet requirements",
  "status": "REJECTED",
  "timestamp": "2026-05-28T20:00:00Z"
}
```

## Database Schema Changes

### Verification Service Database

The verification service already contains the required tables:

**`tutor_verification_requests`** - Stores tutor application submissions

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Primary key |
| user_id | UUID (FK→users) | Applicant's user ID |
| status | Enum | PENDING, UNDER_REVIEW, VERIFIED, REJECTED, SUSPENDED |
| bio | TEXT | Tutor bio |
| subjects | VARCHAR | CSV list of subjects |
| experience_years | INTEGER | Years of experience |
| hourly_rate | FLOAT | Desired hourly rate |
| reviewed_by | UUID (nullable) | Admin who reviewed |
| reviewed_at | TIMESTAMP (nullable) | Review timestamp |
| rejection_reason | TEXT (nullable) | Rejection reason |
| created_at | TIMESTAMP | Creation timestamp |

**`verification_documents`** - Stores uploaded documents

| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Primary key |
| request_id | UUID (FK→tutor_verification_requests) | Parent request |
| file_name | VARCHAR(255) | Original filename |
| file_url | VARCHAR(500) | Relative storage path |
| document_type | VARCHAR(50) | IDENTITY_PROOF, HIGHEST_DEGREE, CERTIFICATE |
| uploaded_at | TIMESTAMP | Upload timestamp |

### Identity Service Database

**`users`** - Existing table with added fields already present

| Column | Type | Description |
|--------|------|-------------|
| role | Enum(user, tutor) | User role |
| is_verified_tutor | BOOLEAN (nullable) | Whether user is a verified tutor |

**`tutor_profiles`** - Existing table

| Column | Type | Description |
|--------|------|-------------|
| is_verified | BOOLEAN | Whether profile is verified |
| is_active | BOOLEAN | Whether profile is active |

### Recommendation Service Database

**`tutor_metrics`** - Existing table

| Column | Type | Description |
|--------|------|-------------|
| is_verified | BOOLEAN | Whether tutor is verified |
| recommendation_score | FLOAT | Used for ranking; -1 excludes from results |

### Session Service Database (MongoDB)

**`verified_tutors`** - Existing collection (read-model)

| Field | Type | Description |
|-------|------|-------------|
| tutor_id | UUID | User ID from Identity Service |
| is_verified | BOOLEAN | Always true when present |
| updated_at | TIMESTAMP | Last update time |

## API Endpoints

### Identity Service (port 8000) — Application Entry Point

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| **POST** | **`/api/v1/tutors/apply`** | **Submit tutor application with documents (file upload)** | **JWT (user)** |
| POST | `/api/v1/tutors/become` | Direct tutor creation (legacy) | JWT (user) |
| GET | `/api/v1/tutors/leaderboard` | Top tutors leaderboard | None |
| GET | `/api/v1/tutors/search` | Search tutors | JWT (user) |
| PATCH | `/api/v1/tutors/profile` | Update own profile | JWT (user) |
| DELETE | `/api/v1/tutors/profile` | Delete own profile | JWT (user) |
| GET | `/api/v1/tutors/{id}` | Get tutor by ID | JWT (user) |
| GET | `/api/v1/tutors/{id}/stats` | Get tutor stats | JWT (user) |

### Verification Service (port 8006) — Admin Review

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/admin/verification/` | List all verification requests | JWT (admin) |
| GET | `/api/v1/admin/verification/pending` | List pending requests | JWT (admin) |
| GET | `/api/v1/admin/verification/{id}` | Get request detail with documents | JWT (admin) |
| POST | `/api/v1/admin/verification/{id}/review` | Mark as under review | JWT (admin) |
| POST | `/api/v1/admin/verification/{id}/approve` | Approve (publishes TUTOR_VERIFIED) | JWT (admin) |
| POST | `/api/v1/admin/verification/{id}/reject` | Reject (publishes TUTOR_REJECTED) | JWT (admin) |

### Session Service (port 8001)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/sessions/` | Create session (validates verified tutor for paid) | JWT (user) |

### Admin Service (port 8004)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/admin/verification/pending` | Get pending verifications | JWT (admin) |
| GET | `/api/v1/admin/verification/stats` | Verification stats | JWT (admin) |
| GET | `/api/v1/admin/verification/{id}` | Get verification details | JWT (admin) |
| POST | `/api/v1/admin/verification/{id}/approve` | Approve verification | JWT (admin) |
| POST | `/api/v1/admin/verification/{id}/reject` | Reject verification | JWT (admin) |
| GET | `/api/v1/admin/verification/tutor/{id}/history` | Tutor's verification history | JWT (admin) |

## File Storage

Documents are stored locally under `/app/verification-documents/` with the structure:

```
/app/verification-documents/
  └── {user_id}/
      ├── identity_proof/
      │   └── {uuid4}.{ext}
      ├── highest_degree/
      │   └── {uuid4}.{ext}
      └── certificate/
          └── {uuid4}.{ext}
```

### Validation Rules

- Allowed MIME types: `image/jpeg`, `image/png`, `application/pdf`
- Maximum file size: 5MB per file
- Identity Proof and Highest Degree are **mandatory**
- Extra certificates are **optional**

## Security

1. **JWT Authentication**: All endpoints require valid JWT token
2. **Admin Authorization**: Admin endpoints check for `admin` or `super_admin` role
3. **Duplicate Prevention**: Rejects if pending/under_review request already exists
4. **Idempotent Events**: Event consumers use database-level duplicate checks
5. **File Validation**: MIME type checking via `python-magic`, file size limits enforced

## Consumers

### Identity Service: `UserEventsConsumer`

File: `identity_service/app/events/user_events_consumer.py`

Consumes `USER_EVENTS` topic. On `TUTOR_VERIFIED`:
- Updates user role to `tutor`
- Sets `is_verified_tutor = True`
- Marks existing tutor profile as `is_verified = True`

### Verification Service: `VerificationEventsConsumer`

File: `verification_service/app/events/verification_events_consumer.py`

Consumes `VERIFICATION_EVENTS` topic. On `TUTOR_APPLICATION_SUBMITTED`:
- Creates a `TutorVerificationRequest` record (status: PENDING)
- Creates `VerificationDocument` records for each document in the event payload
- This populates the verification database so admin endpoints can list/review applications

### Recommendation Service: `UserEventsConsumer`

File: `recommendation_service/app/events/user_events_consumer.py`

Consumes `USER_EVENTS` topic. On `TUTOR_VERIFIED`:
- Creates/updates `TutorMetric` with `is_verified = True`

On `TUTOR_REJECTED`:
- Sets `recommendation_score = -1.0` (excludes from rankings)

## Validation Summary

| Check | Where | What |
|-------|-------|------|
| User is already a tutor? | `/api/v1/tutors/apply` | Returns 400 if role=tutor |
| Duplicate pending application? | `/api/v1/tutors/apply` | Returns 409 if PENDING/UNDER_REVIEW exists |
| Empty bio/subjects? | `/api/v1/tutors/apply` | Returns 400 |
| File MIME type? | File validation | Returns 415 for unsupported types |
| File size > 5MB? | File validation | Returns 413 |
| Verified tutor for paid sessions? | Session Service `create_session` | Returns 403 if not verified |
| Verified tutor for payouts? | Payment Service | Enforced via session validation upstream |
| Admin role for admin endpoints? | Admin deps | Returns 403 if not admin |

## Deployment

No new Docker services required. All changes are within existing services.
No new environment variables required. All topics (`USER_EVENTS`, `VERIFICATION_EVENTS`) already exist in configs.
No new databases. Verification Service already has its own PostgreSQL database.