#!/bin/bash

# Script to fix Docker build network issues
# This helps diagnose and work around Debian repository connection problems

echo "🔧 Docker Network Issue Fixer"
echo "=============================="
echo ""

# Check Docker network connectivity
echo "1️⃣ Testing Docker network connectivity..."
docker run --rm curlimages/curl:latest curl -I https://deb.debian.org/debian/dists/bookworm/Release 2>&1 | head -5
echo ""

# Check DNS resolution
echo "2️⃣ Testing DNS resolution..."
docker run --rm --dns 8.8.8.8 curlimages/curl:latest nslookup deb.debian.org 2>&1 | head -5
echo ""

# Suggest buildkit
echo "3️⃣ Enabling Docker BuildKit for better network handling..."
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
echo "✅ BuildKit enabled"
echo ""

# Check if we should use a different DNS
echo "4️⃣ Docker DNS Configuration Options:"
echo "   Option A: Use Google DNS (recommended)"
echo "   Add to ~/.docker/daemon.json:"
echo "   {"
echo "     \"dns\": [\"8.8.8.8\", \"8.8.4.4\"]"
echo "   }"
echo ""
echo "   Option B: Build with custom DNS"
echo "   docker build --dns 8.8.8.8 --dns 8.8.4.4 -t <image> ."
echo ""

# Suggest retry with buildkit
echo "5️⃣ Recommended: Rebuild with BuildKit enabled"
echo "   Run: DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 ./scripts/start-dev.sh"
echo ""

# Alternative: Use build with network mode
echo "6️⃣ Alternative: Build with host network (if above doesn't work)"
echo "   This uses your host's network directly"
echo "   Note: This may have security implications"
echo ""

echo "=============================="
echo "💡 Quick Fix:"
echo "   export DOCKER_BUILDKIT=1"
echo "   export COMPOSE_DOCKER_CLI_BUILD=1"
echo "   ./scripts/start-dev.sh"
echo ""
