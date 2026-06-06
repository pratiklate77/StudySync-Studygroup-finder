# StudySync — Event Catalog

## Overview

This catalog documents every event produced and consumed across the StudySync platform. Events flow through Apache Kafka topics, enabling asynchronous communication between microservices.

---

## Event Index

| # | Event Name | Topic | Publisher | Subscribers |
|---|-----------|-------|-----------|-------------|
| 1 | USER_CREATED | USER_EVENTS | Identity Service | Notification Service |
| 2 | EMAIL_VERIFICATION_SENT | USER_EVENTS | Identity Service | (Future) |
| 3 | TUTOR_VERIFIED | USER_EVENTS | Identity Service, Verification Service | Identity Service, Session Service, Notification Service, Recommendation Service |
| 4 | TUTOR_REJECTED | USER_EVENTS | Verification Service | Identity Service, Session Service, Notification Service, Recommendation Service |
| 5 | TUTOR_SUSPENDED | USER_EVENTS | (Future) | Identity Service, Session Service |
| 6 | RATING_SUBMITTED | RATING_EVENTS | Session Service | Identity Service, Recommendation Service, Notification Service |
| 7 | SESSION_RATED | RATING_EVENTS | Session Service | Identity Service, Recommendation Service |
| 8 | GROUP_CREATED | GROUP_EVENTS | Group Service | Chat Service, Notification Service |
| 9 | GROUP_DELETED | GROUP_EVENTS | Group Service | Chat Service |
| 10 | USER_JOINED_GROUP | GROUP_EVENTS | Group Service | Chat Service, Notification Service |
| 11 | USER_LEFT_GROUP | GROUP_EVENTS | Group Service | Chat Service |
| 12 | PAYMENT_SUCCESS | PAYMENT_EVENTS | Payment Service | Session Service, Notification Service |
| 13 | PAYMENT_FAILED | PAYMENT_EVENTS | Payment Service | Notification Service |
| 14 | TUTOR_APPLICATION_SUBMITTED | VERIFICATION_EVENTS | Identity Service | Verification Service, Session Service |
| 15 | VERIFICATION_SUBMITTED | VERIFICATION_EVENTS | Verification Service | Notification Service |
| 16 | VERIFICATION_APPROVED | VERIFICATION_EVENTS | Verification Service | Notification Service |
| 17 | VERIFICATION_REJECTED | VERIFICATION_EVENTS | Verification Service | Notification Service |
| 18 | CHAT_MESSAGE_SENT | CHAT_EVENTS | Chat Service | Notification Service |
| 19 | CHAT_MESSAGE_DELETED | CHAT_EVENTS | Chat Service | (Future) |
| 20 | ADMIN_EVENTS | ADMIN_EVENTS | Admin Service | (Future) |

---

## Event Details

### 1. USER_CREATED

| Property | Value |
|----------|-------|
| **Topic** | USER_EVENTS |
| **Publisher** | Identity Service |
| **Subscribers** | Notification Service |
| **Trigger** | User successfully registers via POST /api/v1/auth/register |

**Payload:**
```json
{
  "event_type": "USER_CREATED",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "role": "user"
}
```

**Kafka Key:** user_id (as bytes)

**Retry Strategy:** Circuit breaker → InMemoryFallbackStore → RetryWorker (exponential backoff 2s-30s)

**Failure Handling:** Event remains in fallback store until Kafka is available. Logged on failure.

---

### 2. EMAIL_VERIFICATION_SENT

| Property | Value |
|----------|-------|
| **Topic** | USER_EVENTS |
| **Publisher** | Identity Service |
| **Subscribers** | Not consumed by any current service (Future: Email Service) |
| **Trigger** | User requests email verification resend |

**Payload:**
```json
{
  "event_type": "EMAIL_VERIFICATION_SENT",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Kafka Key:** user_id (as bytes)

---

### 3. TUTOR_VERIFIED

| Property | Value |
|----------|-------|
| **Topic** | USER_EVENTS |
| **Publisher** | Identity Service (legacy admin API key flow), Verification Service (new admin review flow) |
| **Subscribers** | Identity Service, Session Service, Notification Service, Recommendation Service |
| **Trigger** | Admin approves tutor verification request |

**Payload:**
```json
{
  "event_type": "TUTOR_VERIFIED",
  "event": "TUTOR_VERIFIED",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "verificationRequestId": "uuid",
  "status": "VERIFIED",
  "timestamp": "2026-05-28T20:00:00Z"
}
```

**Kafka Key:** user_id (as bytes)

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Identity Service | Sets role=tutor, is_verified_tutor=True, profile.is_verified=True |
| Session Service | Upserts verified_tutors (is_verified=true, status=active) |
| Notification Service | Creates approval notification |
| Recommendation Service | Sets is_verified=True in tutor_metrics |

**Retry Strategy:** Circuit breaker → InMemoryFallbackStore → RetryWorker

**Failure Handling:** Idempotent — consumer checks for existing verified state before updating. Redis deduplication (24h TTL on event_id).

---

### 4. TUTOR_REJECTED

| Property | Value |
|----------|-------|
| **Topic** | USER_EVENTS |
| **Publisher** | Verification Service |
| **Subscribers** | Identity Service, Session Service, Notification Service, Recommendation Service |
| **Trigger** | Admin rejects tutor verification request |

**Payload:**
```json
{
  "event_type": "TUTOR_REJECTED",
  "event": "TUTOR_REJECTED",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "verificationRequestId": "uuid",
  "reason": "Documents did not meet requirements",
  "status": "REJECTED",
  "timestamp": "2026-05-28T20:00:00Z"
}
```

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Identity Service | Sets is_verified_tutor=False (logs rejection, no role change) |
| Session Service | Marks verified_tutors (status=rejected) |
| Notification Service | Creates rejection notification |
| Recommendation Service | Sets is_verified=False, recommendation_score=-1.0 |

---

### 5. TUTOR_SUSPENDED

| Property | Value |
|----------|-------|
| **Topic** | USER_EVENTS |
| **Publisher** | Not implemented — Future scope |
| **Subscribers** | Identity Service, Session Service |
| **Trigger** | Admin suspends verified tutor |

**Payload:**
```json
{
  "event_type": "TUTOR_SUSPENDED",
  "user_id": "uuid"
}
```

---

### 6. RATING_SUBMITTED

| Property | Value |
|----------|-------|
| **Topic** | RATING_EVENTS |
| **Publisher** | Session Service |
| **Subscribers** | Identity Service, Recommendation Service, Notification Service |
| **Trigger** | Student submits rating for a completed study session |

**Payload:**
```json
{
  "event_type": "RATING_SUBMITTED",
  "session_id": "uuid",
  "tutor_id": "uuid",
  "tutorId": "uuid",
  "student_id": "uuid",
  "studentId": "uuid",
  "score": 5,
  "rating": 5
}
```

**Kafka Key:** tutor_id (as bytes)

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Identity Service | UPDATE tutor_profiles SET rating_sum += score, total_reviews += 1. Invalidates top_tutors Redis cache. |
| Recommendation Service | Updates average_rating, recalculates recommendation score |
| Notification Service | Creates notification about new rating for tutor |

**Duplicate Detection:** Redis `rating_event:{session_id}:{student_id}` — 24h TTL. MongoDB unique index on (session_id, student_id).

**Retry Strategy:** Circuit breaker → InMemoryFallbackStore → RetryWorker (exponential backoff 2s-30s)

---

### 7. SESSION_RATED

Alias for RATING_SUBMITTED. Same payload and behavior.

---

### 8. GROUP_CREATED

| Property | Value |
|----------|-------|
| **Topic** | GROUP_EVENTS |
| **Publisher** | Group Service |
| **Subscribers** | Chat Service, Notification Service |
| **Trigger** | User creates a study group |

**Payload:**
```json
{
  "event_type": "GROUP_CREATED",
  "group_id": "uuid",
  "owner_id": "uuid",
  "name": "Calculus Study Group"
}
```

**Kafka Key:** group_id (as bytes)

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Chat Service | Upserts owner as admin in local MongoDB membership mirror |
| Notification Service | Creates notification about new group |

---

### 9. GROUP_DELETED

| Property | Value |
|----------|-------|
| **Topic** | GROUP_EVENTS |
| **Publisher** | Group Service |
| **Subscribers** | Chat Service |
| **Trigger** | Owner deletes group |

**Payload:**
```json
{
  "event_type": "GROUP_DELETED",
  "group_id": "uuid"
}
```

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Chat Service | Deactivates all memberships for the group in local MongoDB mirror |

---

### 10. USER_JOINED_GROUP

| Property | Value |
|----------|-------|
| **Topic** | GROUP_EVENTS |
| **Publisher** | Group Service |
| **Subscribers** | Chat Service, Notification Service |
| **Trigger** | User joins a study group |

**Payload:**
```json
{
  "event_type": "USER_JOINED_GROUP",
  "group_id": "uuid",
  "user_id": "uuid",
  "role": "member"
}
```

**Kafka Key:** group_id (as bytes)

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Chat Service | Upserts membership in local MongoDB mirror |
| Notification Service | Creates group join notification |

---

### 11. USER_LEFT_GROUP

| Property | Value |
|----------|-------|
| **Topic** | GROUP_EVENTS |
| **Publisher** | Group Service |
| **Subscribers** | Chat Service |
| **Trigger** | User leaves a study group |

**Payload:**
```json
{
  "event_type": "USER_LEFT_GROUP",
  "group_id": "uuid",
  "user_id": "uuid"
}
```

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Chat Service | Deactivates membership in local MongoDB mirror |

---

### 12. PAYMENT_SUCCESS

| Property | Value |
|----------|-------|
| **Topic** | PAYMENT_EVENTS |
| **Publisher** | Payment Service |
| **Subscribers** | Session Service, Notification Service |
| **Trigger** | Payment is confirmed successfully |

**Payload:**
```json
{
  "event_type": "PAYMENT_SUCCESS",
  "payment_id": "uuid",
  "session_id": "uuid",
  "student_id": "uuid",
  "tutor_id": "uuid",
  "amount": 50.00
}
```

**Kafka Key:** session_id (as bytes)

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Session Service | Appends student_id to session.participants array in MongoDB |
| Notification Service | Creates payment confirmation notification |

**Duplicate Detection:** MongoDB `$addToSet` — naturally idempotent.

---

### 13. PAYMENT_FAILED

| Property | Value |
|----------|-------|
| **Topic** | PAYMENT_EVENTS |
| **Publisher** | Payment Service |
| **Subscribers** | Notification Service |
| **Trigger** | Payment processing fails |

**Payload:**
```json
{
  "event_type": "PAYMENT_FAILED",
  "payment_id": "uuid",
  "session_id": "uuid",
  "student_id": "uuid",
  "reason": "Insufficient funds"
}
```

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Notification Service | Creates payment failure notification |

---

### 14. TUTOR_APPLICATION_SUBMITTED

| Property | Value |
|----------|-------|
| **Topic** | VERIFICATION_EVENTS |
| **Publisher** | Identity Service |
| **Subscribers** | Verification Service, Session Service |
| **Trigger** | Tutor submits application with documents via POST /api/v1/tutors/apply |

**Payload:**
```json
{
  "event": "TUTOR_APPLICATION_SUBMITTED",
  "userId": "uuid",
  "user_id": "uuid",
  "bio": "Experienced math tutor with 5 years...",
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

**Kafka Key:** user_id (as bytes)

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Verification Service | Creates TutorVerificationRequest (status=PENDING) and VerificationDocument records |
| Session Service | Upserts pending record for allowing free session creation |

---

### 15. VERIFICATION_SUBMITTED

| Property | Value |
|----------|-------|
| **Topic** | VERIFICATION_EVENTS |
| **Publisher** | Verification Service |
| **Subscribers** | Notification Service |
| **Trigger** | Verification request submitted |

---

### 16. VERIFICATION_APPROVED

| Property | Value |
|----------|-------|
| **Topic** | VERIFICATION_EVENTS |
| **Publisher** | Verification Service |
| **Subscribers** | Notification Service |
| **Trigger** | Admin approves a verification request |

---

### 17. VERIFICATION_REJECTED

| Property | Value |
|----------|-------|
| **Topic** | VERIFICATION_EVENTS |
| **Publisher** | Verification Service |
| **Subscribers** | Notification Service |
| **Trigger** | Admin rejects a verification request |

---

### 18. CHAT_MESSAGE_SENT

| Property | Value |
|----------|-------|
| **Topic** | CHAT_EVENTS |
| **Publisher** | Chat Service |
| **Subscribers** | Notification Service |
| **Trigger** | Message sent in a group chat |

**Payload:**
```json
{
  "event_type": "CHAT_MESSAGE_SENT",
  "group_id": "uuid",
  "sender_id": "uuid",
  "content": "Hello everyone!"
}
```

**Consumer Actions:**
| Consumer | Action |
|----------|--------|
| Notification Service | Creates notification for offline group members |

---

### 19. CHAT_MESSAGE_DELETED

| Property | Value |
|----------|-------|
| **Topic** | CHAT_EVENTS |
| **Publisher** | Chat Service |
| **Subscribers** | Not consumed by any current service — Future scope |
| **Trigger** | Message deleted |

---

### 20. ADMIN_EVENTS

| Property | Value |
|----------|-------|
| **Topic** | ADMIN_EVENTS |
| **Publisher** | Admin Service |
| **Subscribers** | Not consumed by any current service — Future scope |
| **Trigger** | Various admin lifecycle actions |

---

## Event Flow Diagrams

### Key Event Chains

```
1. User Registration Chain:
   Register → USER_CREATED → Notification Service (welcome notification)

2. Tutor Verification Chain:
   Admin Approve → TUTOR_VERIFIED (USER_EVENTS) 
     → Identity Service: role=tutor
     → Session Service: create verified_tutors record
     → Notification Service: approval notification
     → Recommendation Service: is_verified=True

3. Rating Chain:
   Submit Rating → RATING_SUBMITTED (RATING_EVENTS)
     → Identity Service: update rating_sum/total_reviews
     → Recommendation Service: recalculate score
     → Notification Service: rating notification

4. Group Join Chain:
   Join Group → USER_JOINED_GROUP (GROUP_EVENTS)
     → Chat Service: sync membership mirror
     → Notification Service: group join notification

5. Payment Chain:
   Confirm Payment → PAYMENT_SUCCESS (PAYMENT_EVENTS)
     → Session Service: add participant
     → Notification Service: payment confirmation
```

---

## Event Naming Conventions

- **Snake Case**: `RATING_SUBMITTED`, `TUTOR_VERIFIED`, `USER_CREATED`
- **Camel Case (legacy)**: Some events use both `camelCase` and `snake_case` fields in the same payload (e.g., `userId` and `user_id`)
- **Format**: `{NOUN}_{ACTION}` — describes what happened to what entity
- **Topic Names**: `SCREAMING_SNAKE_CASE` — plural nouns indicating event category