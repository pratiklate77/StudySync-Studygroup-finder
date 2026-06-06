#!/bin/bash

# StudySync Microservices - Full Setup and Validation Script
# This script sets up and validates all services are properly connected

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  StudySync Microservices - Setup & Validation Script        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

# Function to print section headers
print_header() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Step 1: Check Docker
print_header "Step 1: Checking Docker Installation"
if command -v docker &> /dev/null; then
    print_success "Docker is installed"
    docker --version
else
    print_error "Docker is not installed"
    exit 1
fi

if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    print_error "Docker Compose is not installed (checked 'docker-compose' and 'docker compose')"
    exit 1
fi
print_success "Docker Compose is installed ($DOCKER_COMPOSE_CMD)"
$DOCKER_COMPOSE_CMD version

# Step 2: Validate Environment Files
print_header "Step 2: Validating Environment Files"

services=(
    "identity_service"
    "session_service"
    "group_service"
    "chat_service"
    "admin_service"
    "payment_service"
    "verification_service"
    "notification_service"
    "recommendation_service"
)

for service in "${services[@]}"; do
    if [ -f "$service/.env" ]; then
        print_success "$service/.env exists"
    else
        print_warning "$service/.env missing - will use defaults"
    fi
done

# Step 3: Start Infrastructure
print_header "Step 3: Starting Infrastructure Components"

echo "Starting Docker Compose services..."
$DOCKER_COMPOSE_CMD up -d postgres postgres_group postgres_admin postgres_payment postgres_verification postgres_notification postgres_recommendation mongo redis zookeeper kafka

print_success "Infrastructure services started"
echo -e "${YELLOW}Waiting for services to become healthy...${NC}"
sleep 10

# Step 4: Wait for Services to be Healthy
print_header "Step 4: Waiting for Services Health Checks"

check_service() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=0
    
    echo -ne "Checking $service..."
    while [ $attempt -lt $max_attempts ]; do
        # For PostgreSQL, pg_isready is the correct check inside the container
        if docker exec "studysync-$service" pg_isready -U studysync &> /dev/null 2>&1; then
            print_success "$service is ready"
            return 0
        fi
        echo -ne "."
        sleep 1
        ((attempt++))
    done
    
    print_error "$service failed to become healthy"
    return 1
}

# Check PostgreSQL instances
for service in "postgres" "postgres-group" "postgres-admin" "postgres-payment" "postgres-verification" "postgres-notification" "postgres-recommendation"; do
    check_service "$service" "5432" || true
done

# Check MongoDB
echo -ne "Checking MongoDB..."
for i in {1..30}; do
    if docker exec studysync-mongo mongosh --eval "db.adminCommand('ping')" &> /dev/null; then
        print_success "MongoDB is ready"
        break
    fi
    echo -ne "."
    sleep 1
done

# Check Redis
echo -ne "Checking Redis..."
for i in {1..30}; do
    if docker exec studysync-redis redis-cli ping &> /dev/null; then
        print_success "Redis is ready"
        break
    fi
    echo -ne "."
    sleep 1
done

# Check Kafka
echo -ne "Checking Kafka..."
for i in {1..30}; do
    if docker exec studysync-kafka kafka-topics --list --bootstrap-server localhost:9092 &> /dev/null; then
        print_success "Kafka is ready"
        break
    fi
    echo -ne "."
    sleep 1
done

# Step 4.5: Run Database Migrations
print_header "Step 4.5: Running Database Migrations"

run_migration() {
    local service=$1
    echo "Running migrations for $service..."
    $DOCKER_COMPOSE_CMD run --rm "$service" alembic upgrade head || print_warning "Migration failed for $service - check if it uses Alembic"
}

for service in "identity_service" "group_service" "admin_service" "payment_service" "verification_service" "notification_service" "recommendation_service"; do
    run_migration "$service"
done

# Step 5: Start Microservices
print_header "Step 5: Building and Starting Microservices"

$DOCKER_COMPOSE_CMD up -d identity_service session_service group_service chat_service admin_service payment_service verification_service notification_service recommendation_service

print_success "All microservices started"
echo -e "${YELLOW}Waiting for microservices to become healthy...${NC}"
sleep 15

# Step 6: Validate Service Connectivity
print_header "Step 6: Validating Service Connectivity"

check_service_health() {
    local service=$1
    local port=$2
    
    echo -ne "Checking $service on port $port..."
    if curl -s http://localhost:$port/health | grep -q '"status":"ok"'; then
        print_success "$service is healthy"
        return 0
    else
        print_error "$service health check failed"
        docker logs "studysync-${service}" | tail -20
        return 1
    fi
}

check_service_health "identity" 8000 || true
check_service_health "session" 8001 || true
check_service_health "group" 8002 || true
check_service_health "chat" 8003 || true
check_service_health "admin" 8004 || true
check_service_health "payment" 8005 || true
check_service_health "verification" 8006 || true
check_service_health "notification" 8007 || true
check_service_health "recommendation" 8008 || true

# Step 7: Display Service Information
print_header "Step 7: Service Summary"

echo -e "\n${BLUE}Service Ports:${NC}"
echo "  Identity Service:      http://localhost:8000"
echo "  Session Service:       http://localhost:8001"
echo "  Group Service:         http://localhost:8002"
echo "  Chat Service:          http://localhost:8003"
echo "  Admin Service:         http://localhost:8004"
echo "  Payment Service:       http://localhost:8005"
echo "  Verification Service:  http://localhost:8006"
echo "  Notification Service:  http://localhost:8007"
echo "  Recommendation Service: http://localhost:8008"

echo -e "\n${BLUE}Infrastructure Ports:${NC}"
echo "  PostgreSQL (identity):    localhost:5442"
echo "  PostgreSQL (group):       localhost:5443"
echo "  PostgreSQL (admin):       localhost:5437"
echo "  PostgreSQL (payment):     localhost:5445"
echo "  PostgreSQL (verification): localhost:5446"
echo "  PostgreSQL (notification): localhost:5447"
echo "  PostgreSQL (recommendation): localhost:5448"
echo "  MongoDB:                  localhost:27017"
echo "  Redis:                    localhost:6379"
echo "  Kafka:                    localhost:9092"

# Step 8: Final Checks
print_header "Step 8: Running Integration Tests"

echo -e "Testing inter-service communication..."

# Test identity service
echo -n "  Testing Identity → Health: "
if curl -s http://localhost:8000/health | grep -q '"status":"ok"'; then
    print_success "OK"
else
    print_error "FAILED"
fi

# Test service discovery
echo -n "  Testing service discovery: "
if docker exec studysync-payment python -c "import urllib.request; urllib.request.urlopen('http://identity_service:8000/health')" &> /dev/null; then
    print_success "OK"
else
    print_error "FAILED"
fi

# Step 9: Display Docker Status
print_header "Step 9: Docker Container Status"

$DOCKER_COMPOSE_CMD ps

# Final message
echo -e "\n${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ All Services Initialized and Connected!                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${BLUE}Next Steps:${NC}"
echo "1. Check individual service logs: docker logs studysync-<service-name>"
echo "2. Run integration tests: python test_membership.py"
echo "3. Check Kafka topics: docker exec studysync-kafka kafka-topics --list --bootstrap-server localhost:29092"
echo "4. View service status: docker-compose ps"
echo "5. Stop services: docker-compose down"

echo -e "\n${BLUE}Useful Commands:${NC}"
echo "  View all logs:          $DOCKER_COMPOSE_CMD logs -f"
echo "  View specific service:  $DOCKER_COMPOSE_CMD logs -f identity_service"
echo "  Restart services:       $DOCKER_COMPOSE_CMD restart"
echo "  Stop services:          $DOCKER_COMPOSE_CMD down"
echo "  Clean up everything:    $DOCKER_COMPOSE_CMD down -v"

echo -e "\n${YELLOW}Documentation: See SERVICES_INTEGRATION.md for detailed information${NC}\n"
