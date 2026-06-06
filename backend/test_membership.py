#!/usr/bin/env python3
"""
Diagnostic script to test chat service membership verification with fallback.
"""
import requests
import json
from uuid import uuid4
import time

BASE_URL = "http://localhost:8000"  # Identity service
GROUP_URL = "http://localhost:8002"  # Group service
CHAT_URL = "http://localhost:8003"   # Chat service

# Test data
TEST_USER_1_ID = "user1@example.com"
TEST_USER_2_ID = "user2@example.com"
GROUP_NAME = f"Test Group {uuid4().hex[:8]}"

def get_or_create_token(user_id: str):
    """Get or create a token for a user."""
    print(f"\n🔑 Getting token for {user_id}...")
    
    # Register/login user
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={"email": user_id, "password": "testpass123"}
    )
    
    if response.status_code == 409:
        # User already exists, try login
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": user_id, "password": "testpass123"}
        )
    
    if response.status_code not in [200, 201]:
        print(f"   ❌ Failed to get token: {response.status_code}")
        print(f"   Response: {response.text}")
        return None
    
    token = response.json().get("access_token")
    print(f"   ✅ Got token: {token[:20]}...")
    return token

def create_group(token: str, owner_id: str):
    """Create a group."""
    print(f"\n📝 Creating group '{GROUP_NAME}'...")
    
    response = requests.post(
        f"{GROUP_URL}/api/v1/groups/",
        json={
            "name": GROUP_NAME,
            "description": "Test group for membership verification",
            "is_private": False,
            "max_members": 10,
            "chat_enabled": True
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 201:
        print(f"   ❌ Failed to create group: {response.status_code}")
        print(f"   Response: {response.text}")
        return None
    
    group_id = response.json().get("id")
    print(f"   ✅ Created group: {group_id}")
    return group_id

def join_group(token: str, group_id: str):
    """Join a group."""
    print(f"\n👥 Joining group {group_id}...")
    
    response = requests.post(
        f"{GROUP_URL}/api/v1/groups/{group_id}/join",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code not in [200, 201]:
        print(f"   ❌ Failed to join group: {response.status_code}")
        print(f"   Response: {response.text}")
        return False
    
    print(f"   ✅ Joined group successfully")
    return True

def check_membership_via_group_service(token: str, group_id: str, user_id: str):
    """Check membership directly via group_service internal API."""
    print(f"\n🔍 Checking membership via group_service internal API...")
    
    # This mimics what the fallback client does
    response = requests.get(
        f"{GROUP_URL}/api/v1/internal/groups/{group_id}/members/{user_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"   Response code: {response.status_code}")
    print(f"   Response: {response.json()}")
    return response.json()

def send_message(token: str, group_id: str, content: str):
    """Send a message to a group."""
    print(f"\n💬 Sending message to group {group_id}...")
    print(f"   Content: '{content}'")
    
    response = requests.post(
        f"{CHAT_URL}/api/v1/groups/{group_id}/messages",
        json={"content": content},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"   Response code: {response.status_code}")
    if response.status_code == 201:
        msg = response.json()
        print(f"   ✅ Message sent: {msg.get('id')}")
        return True
    else:
        print(f"   ❌ Failed to send message")
        print(f"   Response: {response.json()}")
        return False

def get_messages(token: str, group_id: str):
    """Get messages from a group."""
    print(f"\n📖 Getting messages from group {group_id}...")
    
    response = requests.get(
        f"{CHAT_URL}/api/v1/groups/{group_id}/messages",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    print(f"   Response code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        messages = data.get("messages", [])
        print(f"   ✅ Got {len(messages)} messages")
        for msg in messages:
            print(f"      - {msg.get('sender_id')}: {msg.get('content')}")
        return messages
    else:
        print(f"   ❌ Failed to get messages")
        print(f"   Response: {response.json()}")
        return []

def main():
    print("\n" + "="*60)
    print("CHAT SERVICE MEMBERSHIP VERIFICATION TEST")
    print("="*60)
    
    # Step 1: Get tokens for 2 users
    token1 = get_or_create_token(TEST_USER_1_ID)
    token2 = get_or_create_token(TEST_USER_2_ID)
    
    if not token1 or not token2:
        print("\n❌ Failed to get tokens")
        return
    
    # Step 2: User 1 creates a group
    group_id = create_group(token1, TEST_USER_1_ID)
    if not group_id:
        print("\n❌ Failed to create group")
        return
    
    # Step 3: User 2 joins the group
    if not join_group(token2, group_id):
        print("\n❌ Failed to join group")
        return
    
    # Wait a moment for Kafka events to propagate
    print("\n⏳ Waiting for Kafka events to propagate (2 seconds)...")
    time.sleep(2)
    
    # Step 4: Check membership via group_service internal API
    check_membership_via_group_service(token1, group_id, TEST_USER_2_ID)
    
    # Step 5: User 2 tries to send a message
    success = send_message(token2, group_id, "Hello from User 2!")
    
    if not success:
        print("\n⚠️  ISSUE: User couldn't send message even though they joined the group")
        print("   This might indicate:")
        print("   1. Kafka consumer hasn't processed the join event yet")
        print("   2. Fallback to group_service isn't working")
        print("   3. Internal API endpoint returned incorrect data")
    else:
        # Step 6: User 1 tries to get messages
        get_messages(token1, group_id)
        print("\n✅ SUCCESS: Membership verification is working!")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
