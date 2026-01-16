#!/bin/bash

# Extract Claude-specific logs from Docker
# Usage: ./extract_claude_logs.sh [container_name] [minutes]

CONTAINER="${1:-ai_catalogue_backend}"
MINUTES="${2:-10}"

echo "🔍 Extracting Claude API logs from last $MINUTES minutes..."
echo "📦 Container: $CONTAINER"
echo ""

echo "=== CLAUDE API REQUESTS ==="
docker logs "$CONTAINER" --since "${MINUTES}m" 2>&1 | grep -E "(CLAUDE|anthropic|Anthropic)" | tail -50

echo ""
echo "=== CLAUDE PARSE ERRORS ==="
docker logs "$CONTAINER" --since "${MINUTES}m" 2>&1 | grep -E "(❌ CLAUDE|⚠️ CLAUDE|CLAUDE PARSE|CLAUDE STREAM)" | tail -50

echo ""
echo "=== FULL CLAUDE RESPONSE DATA ==="
docker logs "$CONTAINER" --since "${MINUTES}m" 2>&1 | grep -A 5 -B 5 "CLAUDE PARSE.*Full response data" | tail -100

echo ""
echo "=== CLAUDE API ERROR RESPONSES ==="
docker logs "$CONTAINER" --since "${MINUTES}m" 2>&1 | grep -E "(CLAUDE.*error|Anthropic.*error|anthropic.*error)" -i | tail -30

echo ""
echo "=== RECENT WORKFLOW EXECUTIONS WITH CLAUDE ==="
docker logs "$CONTAINER" --since "${MINUTES}m" 2>&1 | grep -E "(AI Assistant 2|anthropic provider|claude)" -i | tail -30
