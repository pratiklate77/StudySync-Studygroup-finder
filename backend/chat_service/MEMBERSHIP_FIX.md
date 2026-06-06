# Chat Service Membership Verification Fix

## Problem

Users were getting "Not a member of this group" errors when trying to send or retrieve messages, even though they were actually members.

### Root Cause

The chat_service relies on a **Kafka consumer** to sync group membership from the group_service. The flow is:

1. User joins a group in **group_service** (stored in PostgreSQL)
2. group_service publishes `USER_JOINED_GROUP` event to Kafka topic `GROUP_EVENTS`
3. chat_service's `GroupEventsConsumer` should receive the event and store membership in local MongoDB
4. **Problem**: If the consumer fails, lags, or Kafka is down, the membership record doesn't exist locally
5. When user tries to send a message, chat_service queries local MongoDB, finds nothing, and rejects with 403 ❌

### Why This Happened

- **Single point of failure**: No fallback when local cache is out of sync
- **Eventual consistency issue**: Kafka events are asynchronous, there's a delay before membership appears locally
- **Consumer failures not handled**: If GroupEventsConsumer crashes, membership sync stops

## Solution

### New Fallback Mechanism

When membership is not found in local MongoDB, chat_service now **queries group_service directly** as a fallback.

**New file: `app/core/group_service_client.py`**

- Makes HTTP calls to group_service's internal APIs
- `GET /api/v1/internal/groups/{group_id}/members/{user_id}` - verify membership
- `GET /api/v1/internal/groups/{group_id}/permissions/{user_id}` - check send permissions
- Handles timeouts and errors gracefully
- Caches results back to local MongoDB for future requests

### Updated Components

1. **MembershipRepository** (`app/repositories/membership_repository.py`)
   - New method: `get_with_fallback()` - queries local cache first, falls back to group_service
   - Now accepts optional `GroupServiceClient` in constructor

2. **MessageService** (`app/services/message_service.py`)
   - Initializes `GroupServiceClient` from settings
   - All membership checks now use `get_with_fallback()` instead of local-only queries
   - Better error messages that explain the fallback attempt

### Flow with Fix

```
User sends message:
├─ send_message() called
├─ Query local MongoDB for membership (fast ✓)
├─ Found? → Use it
└─ Not found?
   ├─ Call group_service /internal/groups/{id}/members/{user}
   ├─ Success? → Cache it + use it ✓
   └─ Not found/Error? → Return 403 ❌
```

## Benefits

✅ **Resilience**: Works even if Kafka consumer is down
✅ **Sync recovery**: Automatically caches any membership discovered via fallback
✅ **Backward compatible**: Falls back gracefully if group_service is unavailable
✅ **Better debugging**: Error messages indicate which data source failed
✅ **No schema changes**: Uses existing group_service internal APIs

## Configuration

The fix uses `settings.group_service_url` which should be set in `.env`:

```
GROUP_SERVICE_URL=http://group_service:8002
```

Default fallback timeout: 5 seconds (configurable in `GroupServiceClient`)

## Testing

To verify the fix:

1. **Test with working Kafka:**
   - Create group → User joins → Send message ✓

2. **Test with broken Kafka:**
   - Stop Kafka consumer
   - Create group → User joins → Send message (will use fallback) ✓
   - Verify no "not a member" error

3. **Test timeout handling:**
   - Make group_service unavailable
   - Try to send message → Should get 403 with descriptive error

4. **Monitor logs:**
   - Look for "Fallback membership check succeeded" (indicates fallback was used)
   - Look for "Fallback permission check succeeded" (indicates permission fallback used)
   - Warnings if either service times out or errors

## Performance Notes

- **First request**: May be slower if using fallback (5s timeout + HTTP call)
- **Subsequent requests**: Fast (cached in MongoDB)
- **Best case**: All requests use local cache (no fallback needed)
- **Circuit breaker**: If group_service keeps failing, requests will timeout after 5s

## Future Improvements

1. Add metrics to track fallback usage
2. Implement exponential backoff for group_service calls
3. Add Redis caching layer for frequently accessed memberships
4. Monitor Kafka consumer lag and proactively refetch data
