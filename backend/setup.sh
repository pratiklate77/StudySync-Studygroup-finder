#!/bin/bash
# Run this once after cloning the repo.
# Copies .env.example files and sets a shared JWT secret across all services.

set -e

echo "Copying .env files from examples..."
for service in identity_service session_service group_service chat_service admin_service payment_service verification_service notification_service recommendation_service; do
    if [ -f "$service/.env.example" ]; then
        cp "$service/.env.example" "$service/.env"
    fi
done

echo "Generating shared JWT secret..."
SECRET=$(openssl rand -hex 32)

for service in identity_service session_service group_service chat_service admin_service payment_service verification_service notification_service recommendation_service; do
    if [ -f "$service/.env" ]; then
        sed -i "s|JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$SECRET|g" "$service/.env"
    fi
done

echo "Ensuring scripts are executable..."
chmod +x start_services.sh check_services_health.sh

echo ""
echo "Done. All 9 services configured with matching JWT_SECRET_KEY."
echo "Run: ./start_services.sh"
