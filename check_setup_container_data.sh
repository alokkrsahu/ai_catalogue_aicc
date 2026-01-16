#!/bin/bash

# Check if setup_container_data ran and what it did

echo "🔍 Checking setup_container_data execution..."
echo "============================================="
echo ""

echo "1️⃣ Checking for setup_container_data in startup logs..."
echo "-------------------------------------------------------"
docker logs ai_catalogue_backend 2>&1 | grep -E "(setup_container|Setting up container|embedding model|📦 Setting up)" | tail -30
echo ""

echo "2️⃣ Checking full startup sequence..."
echo "------------------------------------"
docker logs ai_catalogue_backend 2>&1 | grep -E "(collectstatic|migrate|setup_container|runserver)" | head -10
echo ""

echo "3️⃣ Testing setup_container_data command manually..."
echo "--------------------------------------------------"
docker exec ai_catalogue_backend python manage.py setup_container_data --verify-only 2>&1
echo ""

echo "4️⃣ Running setup_container_data to see what happens..."
echo "-----------------------------------------------------"
echo "⚠️  This will actually run the setup (may take a few minutes if model needs download)..."
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker exec ai_catalogue_backend python manage.py setup_container_data 2>&1 | tail -50
else
    echo "Skipped."
fi
