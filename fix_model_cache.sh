#!/bin/bash

# Force download the model to cache

echo "🔧 Force downloading SentenceTransformer model to cache..."
echo "========================================================="
echo ""

echo "1️⃣ Setting environment variable..."
docker exec -e HF_HUB_DOWNLOAD_TIMEOUT=300 ai_catalogue_backend bash -c "export HF_HUB_DOWNLOAD_TIMEOUT=300 && echo 'HF_HUB_DOWNLOAD_TIMEOUT set to: \$HF_HUB_DOWNLOAD_TIMEOUT'"
echo ""

echo "2️⃣ Running download_embedder_model command..."
echo "---------------------------------------------"
docker exec -e HF_HUB_DOWNLOAD_TIMEOUT=300 ai_catalogue_backend python manage.py download_embedder_model --model all-MiniLM-L6-v2 2>&1
echo ""

echo "3️⃣ Verifying model is cached..."
echo "--------------------------------"
docker exec ai_catalogue_backend bash -c "
from pathlib import Path
cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
model_path = cache_dir / 'all-MiniLM-L6-v2'
if model_path.exists() and any(model_path.iterdir()):
    print('✅ Model is cached at:', model_path)
    print('✅ Files found:', len(list(model_path.iterdir())), 'items')
else:
    print('❌ Model is NOT cached')
" 2>&1 || docker exec ai_catalogue_backend python -c "
from pathlib import Path
cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
model_path = cache_dir / 'all-MiniLM-L6-v2'
if model_path.exists() and any(model_path.iterdir()):
    print('✅ Model is cached at:', model_path)
    print('✅ Files found:', len(list(model_path.iterdir())), 'items')
else:
    print('❌ Model is NOT cached')
"
echo ""

echo "4️⃣ Testing model loading from cache..."
echo "--------------------------------------"
docker exec -e HF_HUB_DOWNLOAD_TIMEOUT=300 ai_catalogue_backend python -c "
import os
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '300')
from pathlib import Path
from sentence_transformers import SentenceTransformer

cache_dir = Path.home() / '.cache' / 'torch' / 'sentence_transformers'
model_cache_path = cache_dir / 'all-MiniLM-L6-v2'

if model_cache_path.exists() and any(model_cache_path.iterdir()):
    print('✅ Loading from cache...')
    model = SentenceTransformer('all-MiniLM-L6-v2', cache_folder=str(cache_dir))
    test_emb = model.encode('test')
    print(f'✅ Model loaded successfully! Dimension: {len(test_emb)}')
else:
    print('❌ Model not found in cache')
" 2>&1
echo ""

echo "========================================================="
echo "✅ Model download attempt completed!"
echo ""
echo "💡 If model is still not cached, check:"
echo "   1. Internet connectivity in container: docker exec ai_catalogue_backend curl -I https://huggingface.co"
echo "   2. Disk space: docker exec ai_catalogue_backend df -h"
echo "   3. Permissions: docker exec ai_catalogue_backend ls -la ~/.cache/torch/"
