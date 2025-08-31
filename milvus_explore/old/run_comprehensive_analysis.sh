#!/bin/bash

echo "🚀 Running COMPREHENSIVE Milvus Search Features Exploration..."
echo "=============================================================="

# Change to the correct directory
cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/milvus_explore

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
else
    echo "⚠️  No virtual environment detected. Activating the one from your ai_catalogue project..."
    source /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend/venv/bin/activate
fi

# Check if required packages are installed
echo "🔍 Checking dependencies..."
python3 -c "import pymilvus, numpy; print('✅ Dependencies satisfied')" 2>/dev/null || {
    echo "❌ Missing dependencies. Installing..."
    pip install pymilvus numpy
}

echo ""
echo "🔧 Running the COMPREHENSIVE Milvus features explorer..."
echo "   This will test ALL available Milvus search capabilities:"
echo "   • All index types (FLAT, IVF_FLAT, IVF_SQ8, IVF_PQ, HNSW, SCANN, AUTOINDEX)"
echo "   • All distance metrics (L2, IP, COSINE)"
echo "   • Advanced search parameters (nprobe, ef, search_k)"
echo "   • Range search capabilities"
echo "   • Complex filtering expressions"
echo "   • Binary vector search"
echo "   • Partition-based search"
echo "   • Aggregation functions"
echo "   • Iterator/pagination features"
echo ""
echo "⏰ This comprehensive analysis may take 2-3 minutes..."
echo ""

python3 milvus_comprehensive_explorer.py

echo ""
echo "✅ COMPREHENSIVE analysis complete! Check the generated JSON file for exhaustive results."
echo "📊 This analysis tested 50+ different Milvus features and capabilities."
