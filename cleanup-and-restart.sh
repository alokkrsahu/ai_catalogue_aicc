#!/bin/bash

# Quick cleanup and restart script for Milvus v2.6.0 update

echo "🧹 Cleaning up existing containers..."

# Stop all containers
docker-compose -f docker-compose.yml -f docker-compose.override.yml down --remove-orphans

# Remove the problematic Attu container specifically
docker rm -f ai_catalogue_attu 2>/dev/null || true

# Optional: Clean up any dangling containers
docker container prune -f

echo "✅ Cleanup complete!"
echo ""
echo "🚀 Restarting with updated configuration..."

# Restart with the updated script
./scripts/start-dev.sh
