#!/bin/bash

echo "🚀 Running Milvus Search Analysis..."
echo "======================================"

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
echo "🔧 Running the fixed Milvus search analyzer..."
python3 milvus_search_fixed.py

echo ""
echo "✅ Analysis complete! Check the generated JSON file for detailed results."
