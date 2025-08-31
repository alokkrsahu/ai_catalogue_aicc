#!/bin/bash

# Cleanup optional Django Milvus Search files
echo "🧹 Cleaning up optional Django Milvus Search files..."

cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend

# Create a backup directory for the files we're removing
mkdir -p deleted/milvus_helpers_backup_$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="deleted/milvus_helpers_backup_$(date +%Y%m%d_%H%M%S)"

echo "📦 Creating backup in: $BACKUP_DIR"

# Move optional files to backup
files_to_cleanup=(
    "django_milvus_search_fix.py"
    "django_milvus_integration_guide.py" 
    "EXPOSE_THESE_SCRIPTS.py"
    "custom_milvus_commands.py"
    "vector_search_integration.py"
    "verify_milvus_integration.py"
    "test_milvus_integration.sh"
    "test_milvus_functionality.sh"
)

for file in "${files_to_cleanup[@]}"; do
    if [ -f "$file" ]; then
        echo "🗂️  Moving $file to backup..."
        mv "$file" "$BACKUP_DIR/"
    fi
done

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "📁 KEPT (Essential files):"
echo "   ✅ django_milvus_search/ - Main Django app package"
echo "   ✅ diagnose_milvus_collections.py - Diagnostic tool"
echo ""
echo "🗂️  MOVED TO BACKUP (Optional files):"
for file in "${files_to_cleanup[@]}"; do
    if [ -f "$BACKUP_DIR/$file" ]; then
        echo "   📦 $file"
    fi
done
echo ""
echo "💡 The backup is in: $BACKUP_DIR"
echo "   You can safely delete this backup folder later if everything works."
echo ""
echo "🚀 Your Django Milvus Search package is now clean and ready to use!"
