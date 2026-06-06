#!/bin/bash
# Manual test script for membership verification

echo "========================================="
echo "Chat Service Membership Verification Test"
echo "========================================="

# Test 1: Check if chat service is running
echo -e "\n1️⃣  Checking chat service health..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8003/docs)
if [ "$HTTP_CODE" == "200" ]; then
    echo "   ✅ Chat service is running"
else
    echo "   ❌ Chat service not responding (code: $HTTP_CODE)"
    exit 1
fi

# Test 2: Check if group service is running
echo -e "\n2️⃣  Checking group service health..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/docs)
if [ "$HTTP_CODE" == "200" ]; then
    echo "   ✅ Group service is running"
else
    echo "   ❌ Group service not responding (code: $HTTP_CODE)"
    exit 1
fi

# Test 3: Check if identity service is running
echo -e "\n3️⃣  Checking identity service health..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)
if [ "$HTTP_CODE" == "200" ]; then
    echo "   ✅ Identity service is running"
else
    echo "   ❌ Identity service not responding (code: $HTTP_CODE)"
    exit 1
fi

echo -e "\n========================================="
echo "✅ All services are healthy!"
echo "========================================="
echo -e "\n📋 Next steps to test membership:"
echo "   1. Create a group via POST /api/v1/groups/"
echo "   2. Join the group via POST /api/v1/groups/{id}/join"
echo "   3. Send a message via POST /api/v1/groups/{id}/messages"
echo "   4. If step 3 fails with 403, the fallback isn't working"
echo -e "\n🔗 API Docs:"
echo "   Identity: http://localhost:8000/docs"
echo "   Group: http://localhost:8002/docs"
echo "   Chat: http://localhost:8003/docs"
echo "========================================="
