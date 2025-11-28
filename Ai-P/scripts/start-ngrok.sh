#!/bin/bash

# Script to start ngrok tunnels for all services
# Usage: ./scripts/start-ngrok.sh [frontend_port] [orchestrator_port] [rag_port]

FRONTEND_PORT=${1:-3000}
ORCHESTRATOR_PORT=${2:-8040}
RAG_PORT=${3:-8000}

TUNNELS_FILE=".ngrok-tunnels.json"

echo "🚀 Starting ngrok tunnels for all services..."
echo ""

# Function to get tunnel URL from ngrok API
get_tunnel_url() {
    local api_port=$1
    local target_port=$2
    sleep 2
    curl -s http://127.0.0.1:$api_port/api/tunnels 2>/dev/null | \
        python3 -c "import sys, json; data = json.load(sys.stdin); tunnels = data.get('tunnels', []); tunnel = next((t for t in tunnels if ':$target_port' in t.get('config', {}).get('addr', '')), None); print(tunnel['public_url'] if tunnel else '')" 2>/dev/null
}

# Start frontend tunnel (uses default API port 4040)
echo "📱 Starting frontend tunnel (port $FRONTEND_PORT)..."
ngrok http $FRONTEND_PORT --log=stdout > /tmp/ngrok-frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 4
FRONTEND_URL=$(get_tunnel_url 4040 $FRONTEND_PORT)

# Start orchestrator tunnel (uses API port 4041)
echo "🎛️  Starting orchestrator tunnel (port $ORCHESTRATOR_PORT)..."
ngrok http $ORCHESTRATOR_PORT --web-addr=127.0.0.1:4041 --log=stdout > /tmp/ngrok-orchestrator.log 2>&1 &
ORCHESTRATOR_PID=$!
sleep 4
ORCHESTRATOR_URL=$(get_tunnel_url 4041 $ORCHESTRATOR_PORT)

# Start RAG tunnel (uses API port 4042)
echo "📚 Starting RAG tunnel (port $RAG_PORT)..."
ngrok http $RAG_PORT --web-addr=127.0.0.1:4042 --log=stdout > /tmp/ngrok-rag.log 2>&1 &
RAG_PID=$!
sleep 4
RAG_URL=$(get_tunnel_url 4042 $RAG_PORT)

# Save tunnel URLs
cat > $TUNNELS_FILE <<EOF
{
  "frontend": {
    "port": $FRONTEND_PORT,
    "url": "$FRONTEND_URL"
  },
  "orchestrator": {
    "port": $ORCHESTRATOR_PORT,
    "url": "$ORCHESTRATOR_URL"
  },
  "rag": {
    "port": $RAG_PORT,
    "url": "$RAG_URL"
  }
}
EOF

echo ""
echo "============================================================"
echo "✅ All ngrok tunnels established!"
echo "============================================================"
echo ""
echo "🌐 Frontend URL:    $FRONTEND_URL"
echo "🎛️  Orchestrator URL: $ORCHESTRATOR_URL"
echo "📚 RAG URL:         $RAG_URL"
echo ""
echo "📊 Dashboard: http://127.0.0.1:4040"
echo ""
echo "💡 Add these to your .env.local:"
echo "   NEXT_PUBLIC_ORCHESTRATOR_WS_URL=$(echo $ORCHESTRATOR_URL | sed 's|https://|wss://|')/ws/voice"
echo "   ORCHESTRATOR_BASE_URL=$ORCHESTRATOR_URL"
echo "   NEXT_PUBLIC_RAG_URL=$RAG_URL"
echo ""
echo "Press Ctrl+C to stop all tunnels."

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down all ngrok tunnels..."
    kill $FRONTEND_PID $ORCHESTRATOR_PID $RAG_PID 2>/dev/null
    rm -f $TUNNELS_FILE
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for user interrupt
wait

