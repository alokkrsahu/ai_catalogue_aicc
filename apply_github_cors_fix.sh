#!/bin/bash

# Apply CORS fix for GitHub Pages integration
# This script updates nginx configuration to allow GitHub Pages origin

set -e  # Exit on any error

echo "🔧 Applying GitHub Pages CORS Fix..."

# Check if we're in the right directory
if [ ! -f "nginx/nginx.conf" ]; then
    echo "❌ Error: nginx/nginx.conf not found. Please run this from the project root directory."
    exit 1
fi

# Make sure Docker is running
if ! docker compose ps >/dev/null 2>&1; then
    echo "❌ Error: Docker Compose is not running or not accessible."
    exit 1
fi

# Backup current nginx configuration
echo "📋 Backing up current nginx configuration..."
cp nginx/nginx.conf nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)

# Apply the CORS fix
echo "🚀 Applying CORS fix configuration..."
cp nginx/nginx_cors_final_fix.conf nginx/nginx.conf

# Test nginx configuration before restarting
echo "🧪 Testing nginx configuration..."
if ! docker compose exec nginx nginx -t 2>/dev/null; then
    echo "❌ Nginx configuration has errors! Rolling back..."
    # Find the most recent backup
    BACKUP_FILE=$(ls -t nginx/nginx.conf.backup.* 2>/dev/null | head -n 1)
    if [ -n "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" nginx/nginx.conf
        echo "🔄 Rolled back to previous configuration"
    fi
    exit 1
fi

# Restart nginx to apply changes
echo "🔄 Restarting nginx..."
docker compose restart nginx

# Wait a moment for nginx to restart
sleep 5

# Verify nginx is running
if docker compose ps nginx | grep -q "Up"; then
    echo "✅ Nginx restarted successfully!"
else
    echo "⚠️ Nginx may not have restarted properly. Check status with: docker compose ps nginx"
fi

echo ""
echo "🎉 CORS fix applied successfully!"
echo ""
echo "✅ Specific Configuration Applied:"
echo "   • GitHub Pages URL: https://oxfordcompetencycenters.github.io"
echo "   • Streaming API CORS headers configured"
echo "   • Cache-Control header included for streaming"
echo "   • Preflight requests properly handled at nginx level"
echo "   • Multiple localhost ports supported for development"
echo ""
echo "🧪 Test your GitHub Pages chatbot now with:"
echo "   fetch('https://aicc.uksouth.cloudapp.azure.com/api/public-chatbot/health/')"
echo ""
echo "📋 If you need to rollback:"
echo "   ls nginx/nginx.conf.backup.*  # List available backups"
echo "   cp nginx/nginx.conf.backup.YYYYMMDD_HHMMSS nginx/nginx.conf"
echo "   docker compose restart nginx"
echo ""
echo "📊 Monitor nginx logs with:"
echo "   docker compose logs -f nginx"
echo ""
echo "🔍 Check CORS headers with:"
echo "   curl -H 'Origin: https://oxfordcompetencycenters.github.io' \\"
echo "        -H 'Access-Control-Request-Method: POST' \\"
echo "        -H 'Access-Control-Request-Headers: Content-Type' \\"
echo "        -X OPTIONS https://aicc.uksouth.cloudapp.azure.com/api/public-chatbot/health/"
