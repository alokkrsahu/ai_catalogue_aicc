#!/bin/bash

# AI Catalogue - SSL Certificate Renewal Script
# Uses the host-installed certbot (same version as the Docker image).
# Authenticator: standalone — briefly stops nginx to free port 80 for the ACME
# challenge, then starts it again.  A deploy_hook in the renewal config
# automatically copies the renewed cert to nginx/ssl/ and reloads nginx.
#
# Run as: sudo ./scripts/renew-ssl.sh
# (sudo required because standalone needs to bind port 80)

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

# Renew certificates using host certbot.
# --force-renewal bypasses the "cert still has >30 days" skip guard so the
# command can be tested manually; remove that flag for automated cron use.
echo "📜 Renewing SSL certificates..."
certbot renew \
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
