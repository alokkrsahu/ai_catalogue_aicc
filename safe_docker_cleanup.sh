#!/bin/bash

# Safe Docker Cleanup Script - NEVER TOUCHES DATA VOLUMES
# This script only removes build artifacts and unused images
# It will NEVER delete any volumes to ensure 100% data safety

echo "=== SAFE Docker Cleanup Script ==="
echo "This script will clean Docker while NEVER touching volumes (your data)"
echo ""

# Function to show current disk usage
show_disk_usage() {
    echo "Current disk usage:"
    df -h /
    echo ""
    docker system df
    echo ""
}

echo "BEFORE cleanup:"
show_disk_usage

# CRITICAL: List volumes that will be preserved
echo "=== DATA VOLUMES THAT WILL BE PRESERVED ==="
echo "The following volumes contain your data and will NEVER be deleted:"
docker volume ls --format "table {{.Driver}}\t{{.Name}}"
echo ""
read -p "Press Enter to continue with cleanup (volumes will NOT be touched)..."

# 1. Remove only dangling/untagged images (safe - these are build artifacts)
echo "Step 1: Removing dangling images (build artifacts only)..."
docker image prune -f

# 2. Remove stopped containers (safe - no data loss, volumes remain)
echo "Step 2: Removing stopped containers (data volumes remain intact)..."
docker container prune -f

# 3. Remove unused networks (safe - will be recreated)
echo "Step 3: Removing unused networks (will be recreated automatically)..."
docker network prune -f

# 4. Remove build cache (safe - just build artifacts)
echo "Step 4: Removing build cache (build artifacts only)..."
docker builder prune -f

# 5. EXPLICITLY AVOID VOLUME OPERATIONS
echo "Step 5: VOLUME SAFETY CHECK"
echo "This script will NEVER run any 'docker volume' commands."
echo "Your data volumes remain 100% intact:"
docker volume ls --format "table {{.Driver}}\t{{.Name}}\t{{.Size}}"
echo ""

echo "AFTER cleanup:"
show_disk_usage

echo "=== Cleanup completed safely ==="
echo "✓ Removed: Dangling images, stopped containers, unused networks, build cache"
echo "✓ Preserved: ALL VOLUMES (your application data)"
echo ""
echo "Your data volumes are completely safe. When you rebuild containers,"
echo "they will automatically reconnect to these existing volumes."
echo ""
echo "WARNING: To remove unused images (not just dangling ones), you can run:"
echo "  docker image prune -a -f"
echo "But this will require rebuilding all images from scratch."