#!/bin/bash

echo "🔀 Running Fixed Hybrid Search Test..."
echo "====================================="

cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/milvus_explore

# Activate virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    source /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/venv/bin/activate
fi

echo "🔧 Testing the fixed hybrid search implementation..."
python3 hybrid_search_fixer.py

echo ""
echo "✅ Hybrid Search fix test completed!"
