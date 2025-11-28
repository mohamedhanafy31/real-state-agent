#!/bin/bash
# Setup script for nginx reverse proxy with ngrok

set -e

echo "🚀 Setting up nginx reverse proxy for ngrok..."

# Check if nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "📦 Installing nginx..."
    sudo apt-get update
    sudo apt-get install -y nginx
fi

# Copy nginx config
NGINX_CONF="/etc/nginx/sites-available/real-state-proxy"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📝 Creating nginx configuration..."
sudo cp "$PROJECT_ROOT/nginx.conf" "$NGINX_CONF"

# Create symlink to enable site
echo "🔗 Enabling nginx site..."
sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/real-state-proxy

# Remove default nginx site if it exists
if [ -f /etc/nginx/sites-enabled/default ]; then
    echo "🗑️  Removing default nginx site..."
    sudo rm /etc/nginx/sites-enabled/default
fi

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
sudo nginx -t

# Reload nginx
echo "🔄 Reloading nginx..."
sudo systemctl reload nginx

echo ""
echo "✅ Nginx setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Stop current ngrok (if running): pkill -f 'ngrok http 3000'"
echo "   2. Start ngrok pointing to nginx: ngrok http 8080"
echo "   3. Access your app via the ngrok URL"
echo "   4. WebSocket will work because nginx proxies /ws/voice to orchestrator"
echo ""
echo "🔍 Check nginx status: sudo systemctl status nginx"
echo "📝 View nginx logs: sudo tail -f /var/log/nginx/error.log"

