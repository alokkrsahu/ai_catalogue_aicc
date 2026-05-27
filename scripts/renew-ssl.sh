#!/bin/bash

# AI Catalogue - SSL Certificate Renewal Script
# Uses the host-installed certbot (same version as the Docker image).
# Authenticator: standalone — briefly stops nginx to free port 80 for the ACME
# challenge, then starts it again.  A deploy_hook in the renewal config
# automatically copies the renewed cert to nginx/ssl/ and reloads nginx.
#
# Can be run as a normal user — the script calls sudo internally for the
# certbot step (standalone needs root to bind port 80).

set -e

echo "🔄 AI Catalogue SSL Certificate Renewal"
echo "Domain: aicc.uksouth.cloudapp.azure.com"
echo ""

# Change to project directory
cd /home/alokkrsahu/ai_catalogue

# Load environment variables
if [ -f .env ]; then
    source .env
fi

# Renew certificates using host certbot (sudo required for standalone + root-
# owned log/work dirs left by previous Docker-based runs).
echo "📜 Renewing SSL certificates..."
sudo certbot renew \
    --config-dir /home/alokkrsahu/ai_catalogue/certbot/certs \
    --work-dir   /home/alokkrsahu/ai_catalogue/certbot/work \
    --logs-dir   /home/alokkrsahu/ai_catalogue/certbot/logs

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo "✅ Certificate renewal successful (or cert still valid — no action needed)."
    echo "📅 Next renewal check in ~60 days"
else
    echo "❌ Certificate renewal failed (exit code $RESULT)"
    echo "🔍 Check the output above for details"
    exit 1
fi
