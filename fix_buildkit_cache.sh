#!/bin/bash

# Script to fix Docker BuildKit cache corruption issues
# Run this if you see "parent snapshot does not exist" errors

echo "🔧 Fixing Docker BuildKit Cache Corruption"
echo "=========================================="
echo ""

echo "1️⃣ Pruning BuildKit cache..."
docker builder prune -af --filter "until=24h" 2>&1 | head -10
echo ""

echo "2️⃣ Removing dangling build cache..."
docker builder prune -f 2>&1 | head -10
echo ""

echo "3️⃣ Checking Docker system..."
docker system df
echo ""

echo "4️⃣ Recommendations:"
echo "   ✅ BuildKit cache pruned"
echo "   💡 If issue persists, try:"
echo "      - Restart Docker Desktop"
echo "      - Rebuild with: docker compose build --no-cache --pull"
echo "      - Or: docker system prune -a (WARNING: removes all unused images)"
echo ""

echo "5️⃣ Ready to rebuild..."
echo "   Run: ./scripts/start-dev.sh"
echo ""
