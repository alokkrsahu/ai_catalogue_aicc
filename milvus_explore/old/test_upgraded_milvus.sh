#!/bin/bash

echo "🚀 Testing Upgraded Milvus 2.4+ Multi-Vector Capabilities..."
echo "============================================================="

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

# Check Milvus version
echo ""
echo "🔍 Checking your Milvus upgrade..."
python3 -c "
from pymilvus import connections, utility
try:
    connections.connect(host='localhost', port='19530')
    version = utility.get_server_version()
    print(f'📊 Milvus Version: {version}')
    if '2.4' in version or '2.5' in version or '2.6' in version:
        print('✅ Multi-vector features should be available!')
    elif '2.3' in version:
        print('⚠️  Still on 2.3.x - multi-vector features not available')
    else:
        print(f'🔍 Version {version} detected - testing compatibility...')
    connections.disconnect()
except Exception as e:
    print(f'❌ Cannot connect to Milvus: {e}')
" 2>/dev/null

echo ""
echo "🎯 Testing NEW Multi-Vector Features (2.4+):"
echo "   • ✨ Multiple vector fields per collection (4 vector types per entity)"
echo "   • 🔀 Hybrid search with automatic reranking"
echo "   • 📊 RRF (Reciprocal Rank Fusion) reranking strategy" 
echo "   • ⚖️ Weighted scoring reranking strategy"
echo "   • 🎯 Advanced filtering combined with hybrid search"
echo "   • 📈 Multi-vector collection statistics and analysis"
echo ""
echo "🏗️ Test Architecture:"
echo "   • Single collection with 4 vector fields:"
echo "     - title_embedding (paper titles)"
echo "     - abstract_embedding (paper abstracts)"  
echo "     - methodology_embedding (technical approach)"
echo "     - results_embedding (outcomes & performance)"
echo "   • 1000 entities with comprehensive metadata"
echo "   • Each entity = 4 different vector representations"
echo ""
echo "⏰ This will test the MAJOR upgrade benefits..."
echo ""

python3 milvus_multivector_explorer.py

echo ""
echo "✅ Multi-vector testing complete!"
echo ""
echo "📊 What was tested:"
echo "   🎯 Collection Creation: Multiple vector fields in single collection"
echo "   🔧 Index Management: Indexes on all 4 vector fields"
echo "   🔍 Individual Searches: Each vector field independently"  
echo "   🔀 RRF Hybrid Search: Automatic rank fusion across vectors"
echo "   ⚖️ Weighted Hybrid Search: Custom weights per vector field"
echo "   🎯 Filtered Hybrid Search: Combine vector search + metadata filtering"
echo "   📊 Architecture Analysis: Multi-vector collection statistics"
echo ""
echo "💡 Check the generated JSON file for detailed results!"
echo "🎉 If successful, your upgrade eliminated the single-vector constraint!"
