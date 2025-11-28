#!/bin/bash
# Manual nginx startup script (runs nginx directly without systemd)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NGINX_CONF="$PROJECT_ROOT/nginx.conf"
NGINX_PID_FILE="$PROJECT_ROOT/nginx.pid"
NGINX_LOG_DIR="$PROJECT_ROOT/nginx-logs"

echo "🚀 Starting nginx manually..."

# Create log directory
mkdir -p "$NGINX_LOG_DIR"

# Check if nginx is already running
if [ -f "$NGINX_PID_FILE" ]; then
    OLD_PID=$(cat "$NGINX_PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️  Nginx is already running (PID: $OLD_PID)"
        echo "   To stop it: kill $OLD_PID"
        exit 1
    else
        echo "🧹 Removing stale PID file..."
        rm "$NGINX_PID_FILE"
    fi
fi

# Check if nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "❌ Nginx is not installed!"
    echo ""
    echo "📦 Install nginx with:"
    echo "   sudo apt-get update"
    echo "   sudo apt-get install -y nginx"
    echo ""
    echo "Or run the setup script:"
    echo "   ./setup-nginx.sh"
    exit 1
fi

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
nginx -t -c "$NGINX_CONF" -p "$PROJECT_ROOT" 2>&1 || {
    echo "❌ Nginx configuration test failed!"
    exit 1
}

# Start nginx
echo "✅ Starting nginx on port 8080..."
nginx -c "$NGINX_CONF" -p "$PROJECT_ROOT"

sleep 1

# Check if nginx started successfully
if [ -f "$NGINX_PID_FILE" ]; then
    PID=$(cat "$NGINX_PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ Nginx started successfully (PID: $PID)"
        echo ""
        echo "📋 Next steps:"
        echo "   1. Start ngrok: ngrok http 8080"
        echo "   2. Access your app via the ngrok URL"
        echo ""
        echo "🔍 Check nginx status: ps aux | grep nginx"
        echo "📝 View logs: tail -f $NGINX_LOG_DIR/error.log"
        echo "🛑 Stop nginx: kill $PID"
    else
        echo "❌ Nginx failed to start. Check logs:"
        echo "   tail -f $NGINX_LOG_DIR/error.log"
        exit 1
    fi
else
    echo "❌ Nginx failed to start. Check logs:"
    echo "   tail -f $NGINX_LOG_DIR/error.log"
    exit 1
fi

