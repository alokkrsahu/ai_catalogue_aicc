#!/bin/bash

echo "🚀 Comprehensive Milvus Search Techniques Investigation..."
echo "=========================================================="

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
echo "🎯 COMPREHENSIVE SEARCH TECHNIQUES INVESTIGATION:"
echo "This will systematically test ALL available search methods in Milvus 2.4.9:"
echo ""
echo "📊 INDEX TYPES & PARAMETERS:"
echo "   • FLAT, IVF_FLAT, IVF_SQ8, IVF_PQ, HNSW, SCANN, AUTOINDEX"
echo "   • GPU indexes: GPU_IVF_FLAT, GPU_IVF_PQ, CAGRA"
echo "   • Binary indexes: BIN_FLAT, BIN_IVF_FLAT"
echo "   • Sparse vector indexes (if supported)"
echo "   • All distance metrics: L2, IP, COSINE, HAMMING, JACCARD"
echo ""
echo "⚙️ SEARCH PARAMETERS:"
echo "   • nprobe variations (1, 4, 8, 16, 32, 64, 128)"
echo "   • ef variations for HNSW (16, 64, 128, 256)"
echo "   • search_width for CAGRA"
echo "   • Different result limits (1, 5, 10, 20, 50, 100, 200, 500)"
echo ""
echo "📏 RANGE SEARCH:"
echo "   • Distance range filtering [min, max]"
echo "   • Radius-based search (distance <= radius)"  
echo "   • Minimum distance filtering (distance >= threshold)"
echo "   • Various range configurations and constraints"
echo ""
echo "🔀 HYBRID SEARCH:"
echo "   • Multi-vector hybrid search with RRF reranking"
echo "   • Weighted scoring with custom weights"
echo "   • 2-vector, 3-vector, and multi-vector combinations"
echo "   • Performance comparison of reranking strategies"
echo ""
echo "🎯 ADVANCED FILTERING:"
echo "   • 30+ filter expression types"
echo "   • Basic comparisons: >, >=, <, <=, ==, !="
echo "   • String operations: exact match, LIKE patterns"
echo "   • Boolean logic: AND, OR, NOT, complex nesting"
echo "   • IN operations: field in [list]"
echo "   • Mathematical expressions: rating * 2 > 15.0"
echo "   • String functions: contains, prefix, suffix matching"
echo ""
echo "📈 PERFORMANCE ANALYSIS:"
echo "   • Search speed vs result set size"
echo "   • Precision vs speed tradeoffs (nprobe effects)"
echo "   • Filtered vs unfiltered search performance"
echo "   • Statistical analysis with multiple iterations"
echo ""
echo "🏗️ TEST ARCHITECTURE:"
echo "   • Float vector collection: 2000 entities, 128D vectors"
echo "   • Binary vector collection: 1000 entities"
echo "   • Sparse vector collection: 500 entities (if supported)"
echo "   • Multi-vector collection: 500 entities with 3 vector fields"
echo "   • Comprehensive metadata: strings, numbers, booleans"
echo ""
echo "⏰ Expected Duration: 10-15 minutes for complete investigation"
echo "📊 Output: Detailed JSON report with all results and timings"
echo ""
echo "🔬 Starting comprehensive investigation..."
echo ""

python3 comprehensive_search_explorer.py

echo ""
echo "✅ COMPREHENSIVE INVESTIGATION COMPLETE!"
echo ""
echo "📋 INVESTIGATION SUMMARY:"
echo "   🔧 All index types and parameters tested"
echo "   ⚙️ Search parameter effects analyzed"
echo "   📏 Range search capabilities validated"
echo "   🔀 Hybrid search strategies explored"
echo "   🎯 Advanced filtering expressions verified"
echo "   📈 Performance characteristics measured"
echo ""
echo "💾 Check the generated JSON file for:"
echo "   • Detailed results for every technique tested"
echo "   • Performance metrics and timing data"
echo "   • Success/failure status for each method"
echo "   • Parameter recommendations"
echo "   • Optimal configuration suggestions"
echo ""
echo "🎯 This gives you the COMPLETE picture of your Milvus capabilities!"
