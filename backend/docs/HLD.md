# StudySync — High Level Design

## 1. System Overview

StudySync is a microservices-based educational platform where users can discover tutors, join or host study sessions, chat in groups, and make payments. Every service owns its own database and communicates either through the BFF (synchronous HTTP) or Kafka (asynchronous events).

---

## 2. Architecture Diagram

```
                        ┌─────────────────────────────────────────┐
                        │           React + TypeScript SPA         │
                        │           (Vite, port 5173)              │
                        └──────────────────┬──────────────────────┘
                                           │  All API calls
                                           ▼
                        ┌─────────────────────────────────────────┐
                        │         Node.js BFF Gateway              │
                        │         (Express, port 3000)             │
                        │                                          │
                        │  Routes by path prefix:                  │
                        │  /api/v1/auth        → :8000             │
                        │  /api/v1/tutors      → :8000             │
                        │  /api/v1/sessions    → :8001             │
                        │  /api/v1/groups      → :8002             │
                        │  /api/v1/groups/*/messages → :8003       │
                        │  /api/v1/admin/verification → :8006      │
                        │  /api/v1/admin       → :8004             │
                        │  /api/v1/payments    → :8005             │
                        │  /api/v1/wallet      → :8005             │
                        │  /api/v1/verification → :8006            │
                        │  /api/v1/notifications → :8007           │
                        │  /api/v1/recommendations → :8008         │
                        └──────────────────┬──────────────────────┘
                                           │
          ┌──────────────┬─────────────────┼──────────────┬──────────────────┐
          │              │                 │              │                  │
          ▼              ▼                 ▼              ▼                  ▼
    ┌──────────┐  ┌──────────┐    ┌──────────────┐ ┌──────────┐    ┌──────────────┐
    │ Identity │  │ Session  │    │    Group     │ │  Chat    │    │    Admin     │
    │ Service  │  │ Service  │    │   Service    │ │ Service  │    │   Service    │
    │  :8000   │  │  :8001   │    │    :8002     │ │  :8003   │    │    :8004     │
    └──────────┘  └──────────┘    └──────────────┘ └──────────┘    └──────────────┘

    ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐
    │ Payment  │  │Verification  │  │  Notification    │  │  Recommendation      │
    │ Service  │  │  Service     │  │    Service       │  │     Service          │
    │  :8005   │  │   :8006      │  │     :8007        │  │      :8008           │
    └──────────┘  └──────────────┘  └──────────────────┘  └──────────────────────┘
```

---

## 3. Service → Database Ownership

Each service owns exactly one database. No service touches another service's database.

```
┌─────────────────────┬──────────────────────┬────────────────────────────────────────┐
│ Service             │ Database             │ Collections / Tables                   │
├─────────────────────┼──────────────────────┼────────────────────────────────────────┤
│ Identity Service    │ PostgreSQL            │ users, tutor_profiles                  │
│                     │ (identity_db :5442)   │                                        │
├─────────────────────┼──────────────────────┼────────────────────────────────────────┤
│ Session Service     │ MongoDB               │ sessions, ratings, verified_tutors     │
│                     │ (session_db :27017)   │                                        │
├─────────────────────┼──────────────────────┼────────────────────────────────────────┤
│ Group Service       │ PostgreSQL            │ groups, group_members                  │
│                     │ (group_db :5433)      │                                        │
├─────────────────────┼──────────────────────┼────────────────────────────────────────┤
│ Chat Service        │ MongoDB               │ messages, group_memberships            │
│                     │ (session_db :27017)   │ (read-model mirror of group members)   │
├─────────────────────┼──────────────────────┼────────────────────────────────────────┤
│ Admin Service       │ PostgreSQL            │ admins                                 │
│                     │ (admin_db :5437)      │                                        │
├─────────────────────┼──────────────────────┼────────────────────────────────────────┤
│ Payment Service     │ PostgreSQL            │ payments, wallets, transactions        │
│                     │ (payment_db :5445)    │                                        │
├─────────────────────┼──────────────────────┼────────────────────────────────────────┤
│ Verification Service│ PostgreSQL            │ tutor_verification_requests,           │
│                     │ (verification_db      │ verification_documents                 │
│                     │  :5446)               │                                        │
├─────────────────────┼──────────────────────┼────────────────────────────────────────┤
│ Notification Service│ PostgreSQL            │ notifications, failed_events           │
│                     │ (notification_db      │                                        │
│                     │  :5447)               │                                        │
├─────────────────────┼──────────────────────┼────────────────────────────────────────┤
│ Recommendation      │ PostgreSQL            │ tutor_metrics                          │
│ Service             │ (recommendation_db    │                                        │
│                     │  :5448)               │                                        │
└─────────────────────┴──────────────────────┴────────────────────────────────────────┘

Shared Infrastructure:
  Redis (single instance :6379)
    DB 0 → Identity Service  (top tutors cache, email verification tokens)
    DB 1 → Session Service   (nearby sessions cache)
    DB 2 → Group Service     (group cache)
    DB 3 → Chat Service      (online presence, read receipts)
    DB 4 → Payment Service   (wallet balance cache)
    DB 5 → Recommendation    (rating dedup keys)
    DB 6 → Notification      (dedup / idempotency)
```

---

## 4. Kafka Topics & Event Flow

All async communication goes through Kafka. Below is every topic, who publishes to it, and who consumes from it.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Apache Kafka                                        │
│                                                                                  │
│  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────────────────┐  │
│  │  USER_EVENTS    │   │ VERIFICATION_    │   │     PAYMENT_EVENTS           │  │
│  │                 │   │ EVENTS           │   │                              │  │
│  │ Published by:   │   │                  │   │ Published by:                │  │
│  │  Identity Svc   │   │ Published by:    │   │  Payment Service             │  │
│  │  Verification   │   │  Identity Svc    │   │                              │  │
│  │  Svc            │   │  Verification    │   │ Events:                      │  │
│  │                 │   │  Svc             │   │  PAYMENT_SUCCESS             │  │
│  │ Events:         │   │                  │   │                              │  │
│  │  USER_CREATED   │   │ Events:          │   │ Consumed by:                 │  │
│  │  EMAIL_VERIF..  │   │  TUTOR_APP_      │   │  Session Service             │  │
│  │  TUTOR_VERIFIED │   │  SUBMITTED       │   │   → add student to           │  │
│  │  TUTOR_REJECTED │   │  VERIF_SUBMITTED │   │     participants[]           │  │
│  │  TUTOR_SUSPENDED│   │  VERIF_APPROVED  │   │  Notification Service        │  │
│  │                 │   │  VERIF_REJECTED  │   │   → payment notification     │  │
│  │ Consumed by:    │   │                  │   └──────────────────────────────┘  │
│  │  Identity Svc   │   │ Consumed by:     │                                     │
│  │   → update role │   │  Verification    │   ┌──────────────────────────────┐  │
│  │     & profile   │   │  Svc             │   │     RATING_EVENTS            │  │
│  │  Session Svc    │   │   → create       │   │                              │  │
│  │   → verified_   │   │     review req   │   │ Published by:                │  │
│  │     tutors coll │   │  Session Svc     │   │  Session Service             │  │
│  │  Recommendation │   │   → upsert       │   │                              │  │
│  │  Svc            │   │     pending      │   │ Events:                      │  │
│  │   → tutor_      │   │     tutor record │   │  SESSION_RATED               │  │
│  │     metrics     │   │  Notification    │   │                              │  │
│  │  Notification   │   │  Svc             │   │ Consumed by:                 │  │
│  │  Svc            │   │   → verif notif  │   │  Identity Service            │  │
│  │   → tutor notif │   └──────────────────┘   │   → update rating_sum        │  │
│  └─────────────────┘                          │     total_reviews            │  │
│                                               │  Recommendation Svc          │  │
│  ┌─────────────────┐   ┌──────────────────┐   │   → update tutor_metrics     │  │
│  │  GROUP_EVENTS   │   │  SESSION_EVENTS  │   │  Notification Svc            │  │
│  │                 │   │                  │   │   → rating notification      │  │
│  │ Published by:   │   │ Published by:    │   └──────────────────────────────┘  │
│  │  Group Service  │   │  Session Service │                                     │
│  │                 │   │                  │   ┌──────────────────────────────┐  │
│  │ Events:         │   │ Events:          │   │     CHAT_EVENTS              │  │
│  │  GROUP_CREATED  │   │  SESSION_ENROLLED│   │                              │  │
│  │  USER_JOINED_   │   │  SESSION_STARTED │   │ Published by:                │  │
│  │  GROUP          │   │  SESSION_STATUS_ │   │  Chat Service                │  │
│  │  USER_LEFT_     │   │  CHANGED         │   │                              │  │
│  │  GROUP          │   │                  │   │ Events:                      │  │
│  │  GROUP_DELETED  │   │ Consumed by:     │   │  CHAT_MESSAGE_SENT           │  │
│  │                 │   │  Notification    │   │  CHAT_MESSAGE_DELETED        │  │
│  │ Consumed by:    │   │  Svc             │   │                              │  │
│  │  Chat Service   │   │   → session notif│   │ Consumed by:                 │  │
│  │   → mirror      │   └──────────────────┘   │  Notification Svc            │  │
│  │     membership  │                          │   → chat notification        │  │
│  │  Notification   │                          └──────────────────────────────┘  │
│  │  Svc            │                                                             │
│  │   → group notif │                                                             │
│  └─────────────────┘                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Service-to-Service Communication Map

### Synchronous (HTTP via BFF)

The BFF is the only entry point from the frontend. Services do not call each other over HTTP except for one case:

```
Session Service ──HTTP GET──► Identity Service
  /api/v1/auth/users/{user_id}
  (fetches user email when a student joins a free session,
   needed to publish SESSION_ENROLLED with email)
```

### Asynchronous (Kafka)

```
Identity Service
  PUBLISHES → USER_EVENTS        (USER_CREATED, EMAIL_VERIFICATION_SENT,
                                  TUTOR_VERIFIED)
  PUBLISHES → VERIFICATION_EVENTS (TUTOR_APPLICATION_SUBMITTED)
  CONSUMES  ← USER_EVENTS        (TUTOR_VERIFIED, TUTOR_REJECTED,
                                  TUTOR_SUSPENDED → update own DB)
  CONSUMES  ← RATING_EVENTS      (SESSION_RATED → update rating_sum,
                                  total_reviews)

Session Service
  PUBLISHES → SESSION_EVENTS     (SESSION_ENROLLED, SESSION_STARTED,
                                  SESSION_STATUS_CHANGED)
  PUBLISHES → RATING_EVENTS      (SESSION_RATED)
  CONSUMES  ← PAYMENT_EVENTS     (PAYMENT_SUCCESS → add student to
                                  participants[])
  CONSUMES  ← USER_EVENTS        (TUTOR_VERIFIED, TUTOR_REJECTED,
                                  TUTOR_SUSPENDED → update
                                  verified_tutors collection)
  CONSUMES  ← VERIFICATION_EVENTS (TUTOR_APPLICATION_SUBMITTED →
                                   upsert pending tutor record)

Group Service
  PUBLISHES → GROUP_EVENTS       (GROUP_CREATED, USER_JOINED_GROUP,
                                  USER_LEFT_GROUP, GROUP_DELETED)

Chat Service
  PUBLISHES → CHAT_EVENTS        (CHAT_MESSAGE_SENT, CHAT_MESSAGE_DELETED)
  CONSUMES  ← GROUP_EVENTS       (GROUP_CREATED, USER_JOINED_GROUP,
                                  USER_LEFT_GROUP, GROUP_DELETED →
                                  mirror membership locally)

Payment Service
  PUBLISHES → PAYMENT_EVENTS     (PAYMENT_SUCCESS)

Verification Service
  PUBLISHES → USER_EVENTS        (TUTOR_VERIFIED, TUTOR_REJECTED,
                                  TUTOR_SUSPENDED)
  PUBLISHES → VERIFICATION_EVENTS (VERIFICATION_SUBMITTED,
                                   VERIFICATION_APPROVED,
                                   VERIFICATION_REJECTED)
  CONSUMES  ← VERIFICATION_EVENTS (TUTOR_APPLICATION_SUBMITTED →
                                   create TutorVerificationRequest)

Recommendation Service
  CONSUMES  ← USER_EVENTS        (TUTOR_VERIFIED → mark is_verified=true,
                                  TUTOR_REJECTED → set score=-1)
  CONSUMES  ← RATING_EVENTS      (SESSION_RATED → update tutor_metrics)

Notification Service
  CONSUMES  ← USER_EVENTS
  CONSUMES  ← SESSION_EVENTS
  CONSUMES  ← GROUP_EVENTS
  CONSUMES  ← PAYMENT_EVENTS
  CONSUMES  ← VERIFICATION_EVENTS
  CONSUMES  ← CHAT_EVENTS
  CONSUMES  ← RATING_EVENTS
  (All events → create in-app notification for the relevant user)
```

---

## 6. Key User Flows

### 6.1 Tutor Onboarding & Verification

```
Frontend
  │
  ├─ POST /api/v1/tutors/apply (multipart)
  │         │
  │         ▼
  │   Identity Service
  │     - Creates tutor_profile (is_verified=false)
  │     - Stores documents to disk
  │     - PUBLISHES → VERIFICATION_EVENTS: TUTOR_APPLICATION_SUBMITTED
  │                │
  │                ├──► Verification Service (consumer)
  │                │      - Creates TutorVerificationRequest (PENDING)
  │                │      - Creates VerificationDocument records
  │                │
  │                └──► Session Service (consumer)
  │                       - upsert_pending() in verified_tutors
  │                         (allows tutor to create free sessions)
  │
  ├─ Admin reviews via POST /api/v1/admin/verification/{id}/approve
  │         │
  │         ▼
  │   Verification Service
  │     - Updates request status → VERIFIED
  │     - PUBLISHES → USER_EVENTS: TUTOR_VERIFIED
  │                │
  │                ├──► Identity Service (consumer)
  │                │      - Sets user.role = tutor
  │                │      - Sets tutor_profile.is_verified = true
  │                │
  │                ├──► Session Service (consumer)
  │                │      - upsert_verified() in verified_tutors
  │                │        (now allows paid sessions too)
  │                │
  │                ├──► Recommendation Service (consumer)
  │                │      - Sets tutor_metrics.is_verified = true
  │                │
  │                └──► Notification Service (consumer)
  │                       - Creates approval notification for tutor
```

### 6.2 Paid Session Booking

```
Student
  │
  ├─ POST /api/v1/payments/create
  │         │
  │         ▼
  │   Payment Service
  │     - Creates Payment (PENDING)
  │     - Returns payment_id
  │
  ├─ POST /api/v1/payments/{id}/confirm
  │         │
  │         ▼
  │   Payment Service
  │     - Marks Payment COMPLETED
  │     - Debits student wallet
  │     - Credits tutor wallet (amount - platform_fee)
  │     - PUBLISHES → PAYMENT_EVENTS: PAYMENT_SUCCESS
  │                │
  │                ├──► Session Service (consumer)
  │                │      - Adds student to session.participants[]
  │                │
  │                └──► Notification Service (consumer)
  │                       - Creates payment success notification
```

### 6.3 Session Rating

```
Student rates session
  │
  ├─ POST /api/v1/sessions/{id}/ratings
  │         │
  │         ▼
  │   Session Service
  │     - Stores rating in ratings collection
  │     - Updates session avg_rating, total_ratings
  │     - PUBLISHES → RATING_EVENTS: SESSION_RATED
  │                │
  │                ├──► Identity Service (consumer)
  │                │      - Increments tutor_profile.rating_sum
  │                │      - Increments tutor_profile.total_reviews
  │                │
  │                ├──► Recommendation Service (consumer)
  │                │      - Updates tutor_metrics score
  │                │
  │                └──► Notification Service (consumer)
  │                       - Creates rating notification for tutor
```

### 6.4 Group Chat

```
User joins group
  │
  ├─ POST /api/v1/groups/{id}/join
  │         │
  │         ▼
  │   Group Service
  │     - Adds group_member record
  │     - PUBLISHES → GROUP_EVENTS: USER_JOINED_GROUP
  │                │
  │                └──► Chat Service (consumer)
  │                       - Mirrors membership in group_memberships
  │                         (no HTTP call needed to check auth in chat)
  │
  ├─ WebSocket /api/v1/groups/{id}/ws
  │         │
  │         ▼
  │   Chat Service
  │     - Checks local group_memberships (no HTTP to Group Service)
  │     - Broadcasts messages via WebSocket ConnectionManager
  │     - PUBLISHES → CHAT_EVENTS: CHAT_MESSAGE_SENT
  │                │
  │                └──► Notification Service (consumer)
  │                       - Creates chat notification for group members
```

---

## 7. Infrastructure Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │  PostgreSQL  │  │   MongoDB    │  │      Redis        │ │
│  │  (×7 DBs)    │  │  (×1 shared) │  │  (×1 shared,      │ │
│  │              │  │              │  │   logical DBs 0-6)│ │
│  │ identity_db  │  │ session_db   │  │                   │ │
│  │ group_db     │  │  - sessions  │  │ Caching:          │ │
│  │ admin_db     │  │  - ratings   │  │  top tutors       │ │
│  │ payment_db   │  │  - verified_ │  │  nearby sessions  │ │
│  │ verification │  │    tutors    │  │  wallet balances  │ │
│  │ _db          │  │              │  │                   │ │
│  │ notification │  │ chat_db      │  │ Dedup:            │ │
│  │ _db          │  │  - messages  │  │  rating events    │ │
│  │ recommend-   │  │  - group_    │  │  notification     │ │
│  │ ation_db     │  │    memberships│  │  events           │ │
│  └──────────────┘  └──────────────┘  └───────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                Apache Kafka + Zookeeper               │  │
│  │                                                      │  │
│  │  Topics: USER_EVENTS, VERIFICATION_EVENTS,           │  │
│  │          SESSION_EVENTS, GROUP_EVENTS,               │  │
│  │          PAYMENT_EVENTS, RATING_EVENTS,              │  │
│  │          CHAT_EVENTS, RECOMMENDATION_EVENTS          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```
