#!/usr/bin/env node

const ngrok = require('ngrok');
const port = parseInt(process.argv[2] || process.env.PORT || 3000, 10);

(async function() {
  try {
    console.log(`Starting ngrok tunnel on port ${port}...`);
    
    const config = {
      addr: port,
    };
    
    // Add authtoken if provided
    if (process.env.NGROK_AUTHTOKEN) {
      config.authtoken = process.env.NGROK_AUTHTOKEN;
    }
    
    const url = await ngrok.connect(config);
    
    console.log('\n✅ ngrok tunnel established!');
    console.log(`🌐 Public URL: ${url}`);
    console.log(`📊 Dashboard: http://127.0.0.1:4040`);
    console.log('\nPress Ctrl+C to stop the tunnel.\n');
    
    // Handle graceful shutdown
    process.on('SIGINT', async () => {
      console.log('\n\nShutting down ngrok tunnel...');
      try {
        await ngrok.disconnect();
        await ngrok.kill();
      } catch (err) {
        // Ignore errors during shutdown
      }
      process.exit(0);
    });
    
    process.on('SIGTERM', async () => {
      try {
        await ngrok.disconnect();
        await ngrok.kill();
      } catch (err) {
        // Ignore errors during shutdown
      }
      process.exit(0);
    });
    
  } catch (error) {
    console.error('❌ Error starting ngrok:', error.message);
    console.error('\n💡 Tips:');
    console.error('   - Set NGROK_AUTHTOKEN environment variable for authenticated tunnels');
    console.error('   - Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken');
    console.error('   - Make sure your local server is running on port', port);
    console.error('   - Alternatively, install ngrok CLI and run: ngrok http', port, '\n');
    process.exit(1);
  }
})();

