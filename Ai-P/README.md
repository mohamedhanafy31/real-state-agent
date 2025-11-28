This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Orchestrator authentication

The frontend now fetches a short-lived JWT from the orchestrator before opening the WebSocket.  
Configure these environment variables (server-only) in `.env.local`:

- `ORCHESTRATOR_BASE_URL` – e.g. `http://localhost:8040`
- `ORCHESTRATOR_SERVICE_KEY` – must match the orchestrator's `SERVICE_API_KEY`

At runtime the browser calls `/api/orchestrator/token`, which runs purely on the server, exchanges the service key for a JWT, caches it, and returns the token to the client.  
For debugging you can still set `NEXT_PUBLIC_ORCHESTRATOR_TOKEN` to bypass the fetch and send a fixed token, but this should only be used locally.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Public URL with ngrok

To expose your local development server and all backend services (orchestrator, RAG) to the internet using ngrok:

### Option 1: Start all services with ngrok (Recommended)

This will start ngrok tunnels for:
- Frontend (Next.js) on port 3000
- Orchestrator on port 8040
- RAG service on port 8000

```bash
npm run dev:ngrok-all
```

The script will display all public URLs. Add them to your `.env.local`:

```bash
NEXT_PUBLIC_ORCHESTRATOR_WS_URL=wss://your-orchestrator-url.ngrok-free.app/ws/voice
ORCHESTRATOR_BASE_URL=https://your-orchestrator-url.ngrok-free.app
NEXT_PUBLIC_RAG_URL=https://your-rag-url.ngrok-free.app
```

### Option 2: Run Next.js and ngrok together (Frontend only)

```bash
npm run dev:tunnel
```

This will start both the Next.js dev server and ngrok tunnel for the frontend only.

### Option 3: Run ngrok separately

If your Next.js server is already running:

```bash
npm run dev:ngrok
```

Or specify a custom port:

```bash
npm run dev:ngrok 3000
```

### Option 4: For production build

If you're running the production build (`npm run start`), use:

```bash
npm run start:ngrok
```

### Configuration

For authenticated ngrok tunnels (recommended for production use), set the `NGROK_AUTHTOKEN` environment variable:

```bash
export NGROK_AUTHTOKEN=your_authtoken_here
```

Get your authtoken from [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken).

The ngrok web interface (for inspecting requests) will be available at [http://127.0.0.1:4040](http://127.0.0.1:4040).

**Note:** The Next.js cross-origin warning for ngrok has been fixed. The app will automatically detect when accessed via ngrok and use the correct WebSocket URLs.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
