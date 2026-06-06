#!/bin/bash

# Quick Service Validation Script
# Checks if all services are running and connected

set -e

SERVICES=(
    "identity_service:8000"
    "session_service:8001"
    "group_service:8002"
    "chat_service:8003"
    "admin_service:8004"
    "payment_service:8005"
    "verification_service:8006"
)

echo "═══════════════════════════════════════════════════════════"
echo "  StudySync Microservices - Connection Check"
echo "═══════════════════════════════════════════════════════════"
echo ""

failed=0

for service in "${SERVICES[@]}"; do
    name="${service%:*}"
    port="${service#*:}"
    
    echo -n "Checking $name (port $port)..."
    
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        status=$(curl -s http://localhost:$port/health | grep -o '"status":"[^"]*"')
        echo " ✓ $status"
    else
        echo " ✗ FAILED (service not responding)"
        ((failed++))
    fi
done

echo ""
echo "─────────────────────────────────────────────────────────"
echo "Infrastructure Status:"
echo "─────────────────────────────────────────────────────────"

# Check Kafka
echo -n "Kafka (port 9092)..."
if nc -z localhost 9092 2>/dev/null; then
    echo " ✓ OK"
else
    echo " ✗ FAILED"
    ((failed++))
fi

# Check PostgreSQL
echo -n "PostgreSQL (port 5432)..."
if nc -z localhost 5432 2>/dev/null; then
    echo " ✓ OK"
else
    echo " ✗ FAILED"
    ((failed++))
fi

# Check MongoDB
echo -n "MongoDB (port 27017)..."
if nc -z localhost 27017 2>/dev/null; then
    echo " ✓ OK"
else
    echo " ✗ FAILED"
    ((failed++))
fi

# Check Redis
echo -n "Redis (port 6379)..."
if nc -z localhost 6379 2>/dev/null; then
    echo " ✓ OK"
else
    echo " ✗ FAILED"
    ((failed++))
fi

echo ""
echo "═══════════════════════════════════════════════════════════"

if [ $failed -eq 0 ]; then
    echo "✓ All services are running and connected!"
    exit 0
else
    echo "✗ $failed service(s) failed health check"
    echo ""
    echo "To start services, run:"
    echo "  bash start_services.sh"
    exit 1
fi
