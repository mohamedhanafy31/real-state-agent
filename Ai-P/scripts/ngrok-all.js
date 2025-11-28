#!/usr/bin/env node

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const FRONTEND_PORT = parseInt(process.argv[2] || process.env.FRONTEND_PORT || 3000, 10);
const ORCHESTRATOR_PORT = parseInt(process.env.ORCHESTRATOR_PORT || 8040, 10);
const RAG_PORT = parseInt(process.env.RAG_PORT || 8000, 10);

const TUNNELS_FILE = path.join(__dirname, '../.ngrok-tunnels.json');

// Clean up function
function cleanup() {
  console.log('\n\nShutting down all ngrok tunnels...');
  if (fs.existsSync(TUNNELS_FILE)) {
    try {
      fs.unlinkSync(TUNNELS_FILE);
    } catch (err) {
      // Ignore
    }
  }
  process.exit(0);
}

process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);

async function startNgrokTunnel(name, port) {
  return new Promise((resolve, reject) => {
    console.log(`Starting ngrok tunnel for ${name} on port ${port}...`);
    
    const ngrok = spawn('ngrok', ['http', port.toString(), '--log=stdout'], {
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let output = '';
    let url = null;
    let resolved = false;

    const timeout = setTimeout(() => {
      if (!resolved) {
        ngrok.kill();
        reject(new Error(`Timeout waiting for ${name} ngrok tunnel`));
      }
    }, 10000);

    ngrok.stdout.on('data', (data) => {
      output += data.toString();
      // Try to extract URL from ngrok output or API
      if (!url) {
        // Check ngrok API after a short delay
        setTimeout(async () => {
          try {
            const response = await fetch('http://127.0.0.1:4040/api/tunnels');
            const data = await response.json();
            const tunnel = data.tunnels?.find(t => 
              t.config?.addr?.includes(`:${port}`) || 
              t.public_url?.includes('ngrok')
            );
            if (tunnel && !resolved) {
              url = tunnel.public_url;
              resolved = true;
              clearTimeout(timeout);
              resolve({ name, port, url, process: ngrok });
            }
          } catch (err) {
            // Keep waiting
          }
        }, 2000);
      }
    });

    ngrok.stderr.on('data', (data) => {
      const error = data.toString();
      if (error.includes('ERROR') || error.includes('error')) {
        console.error(`Error starting ${name} tunnel:`, error);
      }
    });

    ngrok.on('error', (err) => {
      if (!resolved) {
        resolved = true;
        clearTimeout(timeout);
        reject(err);
      }
    });

    // Fallback: try to get URL from API after 3 seconds
    setTimeout(async () => {
      if (!url && !resolved) {
        try {
          const response = await fetch('http://127.0.0.1:4040/api/tunnels');
          const data = await response.json();
          const tunnel = data.tunnels?.find(t => 
            t.config?.addr?.includes(`:${port}`)
          );
          if (tunnel) {
            url = tunnel.public_url;
            resolved = true;
            clearTimeout(timeout);
            resolve({ name, port, url, process: ngrok });
          }
        } catch (err) {
          // Keep waiting or will timeout
        }
      }
    }, 3000);
  });
}

async function getTunnelUrl(port) {
  try {
    const response = await fetch('http://127.0.0.1:4040/api/tunnels');
    const data = await response.json();
    const tunnel = data.tunnels?.find(t => 
      t.config?.addr?.includes(`:${port}`) ||
      t.config?.addr?.endsWith(`:${port}`)
    );
    return tunnel?.public_url || null;
  } catch (err) {
    return null;
  }
}

async function main() {
  console.log('🚀 Starting ngrok tunnels for all services...\n');
  
  const tunnels = {};
  
  // Start tunnels sequentially to avoid port conflicts
  try {
    // Frontend
    console.log(`📱 Starting frontend tunnel (port ${FRONTEND_PORT})...`);
    const frontendUrl = await getTunnelUrl(FRONTEND_PORT);
    if (frontendUrl) {
      tunnels.frontend = { port: FRONTEND_PORT, url: frontendUrl };
      console.log(`✅ Frontend tunnel: ${frontendUrl}`);
    } else {
      const frontend = await startNgrokTunnel('frontend', FRONTEND_PORT);
      tunnels.frontend = { port: frontend.port, url: frontend.url };
      console.log(`✅ Frontend tunnel: ${frontend.url}`);
      await new Promise(resolve => setTimeout(resolve, 2000)); // Wait between tunnels
    }

    // Orchestrator
    console.log(`\n🎛️  Starting orchestrator tunnel (port ${ORCHESTRATOR_PORT})...`);
    const orchestratorUrl = await getTunnelUrl(ORCHESTRATOR_PORT);
    if (orchestratorUrl) {
      tunnels.orchestrator = { port: ORCHESTRATOR_PORT, url: orchestratorUrl };
      console.log(`✅ Orchestrator tunnel: ${orchestratorUrl}`);
    } else {
      const orchestrator = await startNgrokTunnel('orchestrator', ORCHESTRATOR_PORT);
      tunnels.orchestrator = { port: orchestrator.port, url: orchestrator.url };
      console.log(`✅ Orchestrator tunnel: ${orchestrator.url}`);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    // RAG
    console.log(`\n📚 Starting RAG tunnel (port ${RAG_PORT})...`);
    const ragUrl = await getTunnelUrl(RAG_PORT);
    if (ragUrl) {
      tunnels.rag = { port: RAG_PORT, url: ragUrl };
      console.log(`✅ RAG tunnel: ${ragUrl}`);
    } else {
      const rag = await startNgrokTunnel('rag', RAG_PORT);
      tunnels.rag = { port: rag.port, url: rag.url };
      console.log(`✅ RAG tunnel: ${rag.url}`);
    }

    // Save tunnel URLs to file
    fs.writeFileSync(TUNNELS_FILE, JSON.stringify(tunnels, null, 2));

    console.log('\n' + '='.repeat(60));
    console.log('✅ All ngrok tunnels established!');
    console.log('='.repeat(60));
    console.log(`\n🌐 Frontend URL:    ${tunnels.frontend.url}`);
    console.log(`🎛️  Orchestrator URL: ${tunnels.orchestrator.url.replace('https://', 'wss://')}/ws/voice`);
    console.log(`📚 RAG URL:         ${tunnels.rag.url}`);
    console.log(`\n📊 Dashboard: http://127.0.0.1:4040`);
    console.log('\n💡 Tip: Set these environment variables in your .env.local:');
    console.log(`   NEXT_PUBLIC_ORCHESTRATOR_WS_URL=${tunnels.orchestrator.url.replace('https://', 'wss://')}/ws/voice`);
    console.log(`   ORCHESTRATOR_BASE_URL=${tunnels.orchestrator.url}`);
    console.log(`   NEXT_PUBLIC_RAG_URL=${tunnels.rag.url}`);
    console.log('\nPress Ctrl+C to stop all tunnels.\n');

  } catch (error) {
    console.error('❌ Error starting tunnels:', error.message);
    cleanup();
    process.exit(1);
  }
}

main();

