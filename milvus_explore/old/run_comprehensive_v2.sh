#!/bin/bash

echo "🚀 Running COMPREHENSIVE Milvus Search Features Exploration (v2.3.3 Compatible)..."
echo "================================================================================"

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
echo "🔧 Running the COMPREHENSIVE Milvus features explorer (v2.3.3 Compatible)..."
echo "   This version works within Milvus v2.3.3 constraints and will test:"
echo ""
echo "   📊 Index Types & Metrics:"
echo "      • FLAT, IVF_FLAT, IVF_SQ8, IVF_PQ, HNSW, SCANN, AUTOINDEX"
echo "      • L2, IP, COSINE (float vectors) + HAMMING, JACCARD (binary vectors)"
echo ""
echo "   🎯 Advanced Search Features:"
echo "      • Parameter tuning (nprobe, ef, search_k variations)"
echo "      • Range search (radius, range_filter)"
echo "      • Comprehensive filtering (30+ expression types)"
echo "      • Binary vector search (separate collection)"
echo "      • Partition operations (single & multi-partition)"
echo "      • Batch search & pagination"
echo "      • Collection statistics & metadata"
echo ""
echo "   🏗️ Architecture Details:"
echo "      • Separate collections for float vs binary vectors"
echo "      • 2000 entities per collection with comprehensive schema"
echo "      • All supported scalar field types (INT8, INT16, INT32, INT64, FLOAT, DOUBLE, BOOL, VARCHAR)"
echo ""
echo "⏰ This comprehensive analysis will take 3-5 minutes..."
echo ""

python3 milvus_comprehensive_explorer_v2.py

echo ""
echo "✅ COMPREHENSIVE analysis complete!"
echo "📊 This analysis tested 80+ different Milvus features within v2.3.3 constraints."
echo "🔍 Check the generated JSON file for exhaustive results and capability matrix."
