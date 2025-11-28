# Ngrok + Nginx Setup Guide

This setup allows you to expose only the frontend via ngrok while nginx proxies WebSocket connections to the local orchestrator.

## Architecture

```
Browser → ngrok (public URL) → nginx (port 8080) → {
    / → Next.js (port 3000)
    /ws/voice → Orchestrator (port 8040)
    /auth/* → Orchestrator (port 8040)
    /health → Orchestrator (port 8040)
}
```

## Setup Steps

### 1. Install and Configure Nginx

Run the setup script:
```bash
./setup-nginx.sh
```

Or manually:
```bash
# Install nginx
sudo apt-get update
sudo apt-get install -y nginx

# Copy config
sudo cp nginx.conf /etc/nginx/sites-available/real-state-proxy

# Enable site
sudo ln -s /etc/nginx/sites-available/real-state-proxy /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

### 2. Stop Current Ngrok

```bash
pkill -f "ngrok http 3000"
```

### 3. Start Ngrok Pointing to Nginx

```bash
cd Ai-P
ngrok http 8080
```

### 4. Access Your Application

- Use the ngrok public URL (e.g., `https://xxxxx.ngrok-free.app`)
- WebSocket connections will automatically use the same origin
- Nginx will proxy `/ws/voice` to `localhost:8040`

## How It Works

1. **Browser connects to ngrok URL** → ngrok forwards to nginx on port 8080
2. **Regular HTTP requests** → nginx proxies to Next.js on port 3000
3. **WebSocket connections to `/ws/voice`** → nginx proxies to orchestrator on port 8040
4. **Orchestrator API calls** → nginx proxies `/auth/*` and `/health` to orchestrator

## Benefits

✅ Only one ngrok tunnel needed (frontend only)  
✅ WebSocket works through nginx proxy  
✅ All services accessible via single public URL  
✅ Works with free ngrok account  

## Troubleshooting

### Check nginx status
```bash
sudo systemctl status nginx
```

### View nginx logs
```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Test nginx config
```bash
sudo nginx -t
```

### Restart nginx
```bash
sudo systemctl restart nginx
```

### Check if nginx is listening on port 8080
```bash
netstat -tlnp | grep 8080
# or
ss -tlnp | grep 8080
```

## Port Summary

- **8080**: Nginx (exposed via ngrok)
- **3000**: Next.js frontend (internal)
- **8040**: Orchestrator (internal)
- **8000**: RAG service (internal)

