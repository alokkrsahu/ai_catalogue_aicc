#!/bin/bash

echo "🔀 Running Hybrid Search Fix for Milvus..."
echo "============================================"

# Change to the correct directory
cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/milvus_explore

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
else
    echo "⚠️  No virtual environment detected. Activating..."
    source /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/venv/bin/activate
fi

echo ""
echo "🔧 Running the Hybrid Search Fix..."
echo "   This will:"
echo "   • Create a multi-vector collection with 3 vector fields"
echo "   • Test RRF (Reciprocal Rank Fusion) reranking"
echo "   • Test WeightedRanker with corrected parameter format"
echo "   • Test hybrid search with filtering"
echo "   • Demonstrate all working hybrid search patterns"
echo ""

python3 hybrid_search_fixer.py

echo ""
echo "✅ Hybrid Search fix test complete!"
echo "Check the output above to see the working hybrid search configurations."
