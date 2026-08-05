#!/bin/bash

# AI Catalogue - Local Development Startup Script
# This script starts the containerized AI Catalogue application for local development
# with optimized settings for local development workflow

set -e

echo "🏠 Starting AI Catalogue in Local Development Mode..."

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env file with your configuration before running again."
    echo "🔑 Especially set your API keys and database credentials!"
    echo ""
    echo "💡 For local development, you can use simplified credentials:"
    echo "   DB_PASSWORD=localdev123"
    echo "   MILVUS_ROOT_USER=root"
    echo "   MILVUS_ROOT_PASSWORD=Milvus"
    echo "   MINIO_ROOT_USER=minioadmin"
    echo "   MINIO_ROOT_PASSWORD=minioadmin"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Set local development mode
export DEVELOPMENT_MODE=true
export DJANGO_DEBUG=true

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p ./volumes/postgres
mkdir -p ./volumes/milvus
mkdir -p ./volumes/etcd
mkdir -p ./volumes/minio
mkdir -p ./logs

# Check for existing containers and stop them if running
echo "🧹 Cleaning up existing containers..."
docker compose down --remove-orphans || true

# Build local development images (without cache for fresh builds)
echo "🔨 Building local development images..."
docker compose build --no-cache

# Start services optimized for local development
echo ""
echo "🏗️  Starting Local Development Environment..."

echo "🗄️  Step 1: Starting PostgreSQL database..."
docker compose up -d postgres

echo "⏳ Waiting for PostgreSQL to be ready..."
until docker compose exec postgres pg_isready -U ${DB_USER:-ai_catalogue_user} -d ${DB_NAME:-ai_catalogue_db} > /dev/null 2>&1; do
    echo "   📋 Waiting for PostgreSQL..."
    sleep 2
done
echo "✅ PostgreSQL is ready!"

echo "🔧 Step 2: Starting etcd and MinIO..."
docker compose up -d etcd minio

echo "⏳ Waiting for etcd and MinIO..."
sleep 15

echo "🔍 Step 3: Starting Milvus..."
docker compose up -d milvus

echo "⏳ Waiting for Milvus to initialize..."
MILVUS_TIMEOUT=120  # 2 minutes for local development
MILVUS_COUNTER=0
MILVUS_HEALTHY=false

while [ $MILVUS_COUNTER -lt $MILVUS_TIMEOUT ]; do
    if curl -f -s http://localhost:9091/healthz > /dev/null 2>&1; then
        echo "✅ Milvus is healthy and ready!"
        MILVUS_HEALTHY=true
        break
    fi
    
    if [ $((MILVUS_COUNTER % 10)) -eq 0 ]; then
        echo "   ⏱️  Milvus initializing... ($MILVUS_COUNTER/${MILVUS_TIMEOUT}s)"
    fi
    
    sleep 5
    MILVUS_COUNTER=$((MILVUS_COUNTER + 5))
done

if [ "$MILVUS_HEALTHY" = "false" ]; then
    echo "⚠️  Milvus health check timed out. Continuing with startup..."
    echo "   💡 Check logs: docker compose logs milvus"
fi

echo "🐍 Step 5: Starting Django backend..."
docker compose up -d backend

echo "⏳ Waiting for Django backend..."
BACKEND_TIMEOUT=45
BACKEND_COUNTER=0
while [ $BACKEND_COUNTER -lt $BACKEND_TIMEOUT ]; do
    if curl -f -s http://localhost:8000/admin/ > /dev/null 2>&1; then
        echo "✅ Django backend is ready!"
        break
    fi
    sleep 2
    BACKEND_COUNTER=$((BACKEND_COUNTER + 2))
done

echo "⚛️  Step 6: Starting SvelteKit frontend..."
docker compose up -d frontend-dev

echo "🌐 Step 7: Starting Nginx reverse proxy..."
docker compose up -d nginx

echo "🎛️  Step 8: Starting management tools..."
docker compose up -d pgadmin attu

# Show status
echo ""
echo "🎉 AI Catalogue Local Development Environment Started!"
echo ""
echo "📊 Container Status:"
docker compose ps

echo ""
echo "🌟 Local Development Access URLs:"
echo "   📱 Application: http://localhost"
echo "   🔥 Frontend Dev: http://localhost:5173 (hot reload)"
echo "   🐍 Backend API: http://localhost:8000"
echo "   🔧 Django Admin: http://localhost:8000/admin/"
echo "   🗄️  PgAdmin: http://localhost:8080"
echo "   🔍 Attu (Milvus): http://localhost:3001"

echo ""
echo "🔐 Quick Login Info:"
echo "   PgAdmin: ${PGADMIN_EMAIL:-admin@example.com} / ${PGADMIN_PASSWORD:-admin123}"
if [ "$MILVUS_HEALTHY" = "true" ]; then
    echo "   Attu/Milvus: ${MILVUS_ROOT_USER:-root} / [check .env file]"
fi

echo ""
echo "💻 Local Development Features:"
echo "   🔥 Hot reload for frontend and backend"
echo "   🐛 Debug mode enabled"
echo "   📋 Local file watching"
echo "   🔄 Automatic restart on code changes"

echo ""
echo "📋 Common Development Commands:"
echo "   View logs: docker compose logs -f"
echo "   Backend logs: docker compose logs -f backend"
echo "   Frontend logs: docker compose logs -f frontend-dev"
echo "   Restart service: docker compose restart <service>"
echo "   Stop all: docker compose down"
echo ""
echo "🎯 Ready for local development! Start coding! 🚀"