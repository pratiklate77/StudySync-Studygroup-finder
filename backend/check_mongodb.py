#!/usr/bin/env python3
"""
Check MongoDB state to diagnose membership sync issues.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from uuid import UUID

async def check_mongodb():
    """Check what's in MongoDB."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["chat_db"]
    
    # Check group_memberships
    col = db["group_memberships"]
    
    print("\n" + "="*60)
    print("MONGODB STATE CHECK")
    print("="*60)
    
    count = await col.count_documents({})
    print(f"\n📊 Total group_memberships in MongoDB: {count}")
    
    if count > 0:
        print("\n📋 Recent memberships:")
        async for doc in col.find().limit(10):
            print(f"  - Group: {doc.get('group_id')}, User: {doc.get('user_id')}, Role: {doc.get('role')}, Active: {doc.get('is_active')}")
    else:
        print("\n⚠️  No memberships found in MongoDB!")
        print("    This means:")
        print("    1. No users have joined groups yet")
        print("    2. Or GROUP_EVENTS consumer hasn't processed join events")
        print("    3. Or group owner wasn't added as member on group creation")
    
    # Check messages
    msg_col = db["messages"]
    msg_count = await msg_col.count_documents({})
    print(f"\n💬 Total messages in MongoDB: {msg_count}")
    
    # Check if there are any Kafka consumer offsets/commits
    print(f"\n🔍 Checking Kafka topics in MongoDB...")
    try:
        offsets_col = db["__consumer_offsets"]
        offsets_count = await offsets_col.count_documents({})
        print(f"   Kafka offsets stored: {offsets_count}")
    except Exception as e:
        print(f"   (Not found or error: {e})")
    
    client.close()
    print("\n" + "="*60)

if __name__ == "__main__":
    asyncio.run(check_mongodb())
