#!/bin/bash

# Extract the most detailed Claude error from recent execution
# Usage: ./extract_detailed_claude_error.sh [container_name] [execution_id]

CONTAINER="${1:-ai_catalogue_backend}"
EXECUTION_ID="${2:-}"

echo "🔍 Extracting detailed Claude error..."
echo "📦 Container: $CONTAINER"
echo ""

if [ -n "$EXECUTION_ID" ]; then
    echo "🎯 Searching for execution: $EXECUTION_ID"
    docker logs "$CONTAINER" --since 30m 2>&1 | grep -A 20 -B 10 "$EXECUTION_ID" | grep -E "(CLAUDE|anthropic|AI Assistant 2)" -A 10 -B 5 | tail -100
else
    echo "📋 Most recent Claude error (last 30 minutes):"
    echo ""
    
    echo "=== ERROR CONTEXT ==="
    docker logs "$CONTAINER" --since 30m 2>&1 | grep -B 10 "CLAUDE PARSE.*Empty content" | tail -30
    
    echo ""
    echo "=== FULL RESPONSE DATA ==="
    docker logs "$CONTAINER" --since 30m 2>&1 | grep -A 2 "CLAUDE PARSE.*Full response data" | tail -20
    
    echo ""
    echo "=== REQUEST DETAILS (if logged) ==="
    docker logs "$CONTAINER" --since 30m 2>&1 | grep -E "(CLAUDE.*request|CLAUDE.*body|anthropic.*POST)" -i | tail -20
    
    echo ""
    echo "=== RECENT EXECUTION ID ==="
    docker logs "$CONTAINER" --since 30m 2>&1 | grep "exec_" | tail -5
fi
