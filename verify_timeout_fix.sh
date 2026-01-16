#!/bin/bash

# Verification script for HuggingFace timeout fix
# This checks if HF_HUB_OFFLINE is being set and if timeout errors are eliminated

echo "🔍 Verifying HuggingFace Timeout Fix"
echo "====================================="
echo ""

echo "1️⃣ Checking for HF_HUB_OFFLINE environment variable usage..."
echo "------------------------------------------------------------"
docker logs ai_catalogue_backend 2>&1 | grep -E "(HF_HUB_OFFLINE|offline mode)" | tail -10
echo ""

echo "2️⃣ Checking for cache detection (should show 'Found cached model')..."
echo "--------------------------------------------------------------------"
docker logs ai_catalogue_backend 2>&1 | grep -E "(Found cached model|Found model in cache|CHROMA.*Found cached)" | tail -10
echo ""

echo "3️⃣ Checking for timeout errors (should be NONE after fix)..."
echo "------------------------------------------------------------"
TIMEOUT_COUNT=$(docker logs ai_catalogue_backend 2>&1 | grep -c "ReadTimeoutError.*huggingface.co" || echo "0")
if [ "$TIMEOUT_COUNT" -eq "0" ]; then
    echo "✅ No timeout errors found!"
else
    echo "⚠️  Found $TIMEOUT_COUNT timeout error(s):"
    docker logs ai_catalogue_backend 2>&1 | grep "ReadTimeoutError.*huggingface.co" | tail -5
fi
echo ""

echo "4️⃣ Checking for successful model loading..."
echo "-------------------------------------------"
docker logs ai_catalogue_backend 2>&1 | grep -E "(EMBEDDING.*Model loaded successfully|CHROMA.*Using SentenceTransformer|Successfully initialized DocumentEmbedder)" | tail -10
echo ""

echo "5️⃣ Testing model loading directly with offline mode..."
echo "------------------------------------------------------"
docker exec ai_catalogue_backend python -c "
import os
os.environ['HF_HUB_OFFLINE'] = '1'
from pathlib import Path
from sentence_transformers import SentenceTransformer
import time

cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
model_name = 'sentence-transformers/all-MiniLM-L6-v2'
new_format_path = cache_dir / f\"models--{model_name.replace('/', '--')}\"

print(f'Cache path: {new_format_path}')
print(f'Cache exists: {new_format_path.exists()}')
print(f'HF_HUB_OFFLINE: {os.environ.get(\"HF_HUB_OFFLINE\", \"NOT SET\")}')

if new_format_path.exists():
    print('\\n✅ Testing model load with offline mode...')
    start_time = time.time()
    try:
        model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
        load_time = time.time() - start_time
        test_emb = model.encode('test')
        print(f'✅ Model loaded successfully in {load_time:.2f}s')
        print(f'✅ Embedding dimension: {len(test_emb)}')
        print(f'✅ No network requests made (offline mode)')
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
else:
    print('❌ Cache not found - cannot test offline mode')
" 2>&1
echo ""

echo "6️⃣ Checking recent workflow execution logs..."
echo "--------------------------------------------"
docker logs ai_catalogue_backend 2>&1 | grep -E "(📊 EMBEDDING|✅ EMBEDDING|📚 DOCAWARE.*Query)" | tail -15
echo ""

echo "====================================="
echo "✅ Verification complete!"
echo ""
echo "💡 Expected results:"
echo "   - Should see 'offline mode' in logs"
echo "   - Should see 'Found cached model' messages"
echo "   - Should see ZERO timeout errors"
echo "   - Should see successful model loading"
echo "   - Model should load in < 5 seconds (no network delays)"
