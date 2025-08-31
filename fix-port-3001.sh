#!/bin/bash

# Port 3001 conflict resolution script

echo "🔍 Checking what's using port 3001..."

# Check what's using port 3001
PORT_USER=$(lsof -ti :3001 2>/dev/null)

if [ -n "$PORT_USER" ]; then
    echo "📋 Port 3001 is being used by process ID(s): $PORT_USER"
    
    # Get process details
    echo ""
    echo "Process details:"
    lsof -P -i :3001
    
    echo ""
    echo "🛑 Options to free port 3001:"
    echo "   1. Kill the process(es) automatically"
    echo "   2. Show me the processes so I can decide manually"
    echo "   3. Cancel and use a different port"
    echo ""
    
    read -p "Choose option (1/2/3): " choice
    
    case $choice in
        1)
            echo "🔄 Killing processes using port 3001..."
            kill -9 $PORT_USER
            sleep 2
            
            # Verify port is free
            NEW_CHECK=$(lsof -ti :3001 2>/dev/null)
            if [ -z "$NEW_CHECK" ]; then
                echo "✅ Port 3001 is now free!"
            else
                echo "⚠️ Port 3001 is still in use. You may need to manually stop the service."
                exit 1
            fi
            ;;
        2)
            echo "📋 Here are the processes using port 3001:"
            ps -p $PORT_USER -o pid,ppid,command
            echo ""
            echo "💡 To kill them manually, run: kill -9 $PORT_USER"
            echo "Then re-run this script or start the containers manually."
            exit 0
            ;;
        3)
            echo "❌ Cancelled. Consider updating docker-compose.yml to use a different port."
            exit 0
            ;;
        *)
            echo "❌ Invalid choice. Exiting."
            exit 1
            ;;
    esac
else
    echo "✅ Port 3001 is available!"
fi

echo ""
echo "🧹 Now cleaning up Docker containers and restarting..."

# Stop all containers
docker-compose -f docker-compose.yml -f docker-compose.override.yml down --remove-orphans

# Remove any existing Attu container
docker rm -f ai_catalogue_attu 2>/dev/null || true

# Clean up
docker container prune -f

echo ""
echo "🚀 Starting containers with Attu on port 3001..."
./scripts/start-dev.sh
