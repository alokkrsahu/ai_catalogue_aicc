#!/bin/bash
# Extract Claude request and response details from recent execution
CONTAINER="${1:-ai_catalogue_backend}"
MINUTES="${2:-10}"

echo "🔍 Extracting Claude request/response details from last $MINUTES minutes..."
echo ""

echo "=== CLAUDE REQUEST DETAILS ==="
docker logs "$CONTAINER" --since "${MINUTES}m" 2>&1 | grep -E "(CLAUDE REQUEST|🔍 CLAUDE)" | tail -50

echo ""
echo "=== CLAUDE RESPONSE DETAILS ==="
docker logs "$CONTAINER" --since "${MINUTES}m" 2>&1 | grep -E "(CLAUDE RESPONSE|⚠️ CLAUDE RESPONSE)" | tail -30

echo ""
echo "=== FULL RESPONSE WHEN EMPTY ==="
docker logs "$CONTAINER" --since "${MINUTES}m" 2>&1 | grep -A 20 "⚠️ CLAUDE RESPONSE: Empty content" | tail -50
