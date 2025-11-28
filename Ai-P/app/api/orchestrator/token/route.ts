import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

// Get orchestrator URL, checking for ngrok if accessed via ngrok
function getOrchestratorUrl(): string {
  // If explicitly set via env var, use it
  if (process.env.ORCHESTRATOR_BASE_URL) {
    return process.env.ORCHESTRATOR_BASE_URL;
  }

  // For Cloud Run, try to construct from NEXT_PUBLIC_ORCHESTRATOR_URL if available
  // This is set at build time or runtime
  if (process.env.NEXT_PUBLIC_ORCHESTRATOR_URL) {
    return process.env.NEXT_PUBLIC_ORCHESTRATOR_URL;
  }

  // When using nginx proxy, orchestrator is accessible via same origin
  // Check if we're running in a server context (Next.js API route)
  // The request will come through nginx, so we can use relative URL or localhost
  // Since this is server-side, we can always use localhost
  // Nginx will handle the proxying from the public URL to localhost:8040

  // Default to localhost (nginx will proxy /auth/* to localhost:8040)
  return 'http://localhost:8040';
}

const ORCHESTRATOR_BASE_URL = getOrchestratorUrl();
const SERVICE_KEY = process.env.ORCHESTRATOR_SERVICE_KEY;
const TOKEN_REFRESH_BUFFER_MS = 15_000; // refresh 15s before expiry

type TokenResponse = {
  token: string;
  expires_at: string;
  ttl_seconds?: number;
};

let cachedToken: { token: string; expiresAt: number } | null = null;

export async function GET() {
  if (!SERVICE_KEY) {
    return NextResponse.json(
      { error: 'ORCHESTRATOR_SERVICE_KEY is not configured' },
      { status: 500 },
    );
  }

  const now = Date.now();
  if (
    cachedToken &&
    cachedToken.expiresAt - now > TOKEN_REFRESH_BUFFER_MS
  ) {
    return NextResponse.json({
      token: cachedToken.token,
      expires_at: new Date(cachedToken.expiresAt).toISOString(),
    });
  }

  const response = await fetch(`${ORCHESTRATOR_BASE_URL}/auth/token`, {
    method: 'POST',
    headers: {
      'X-Service-Key': SERVICE_KEY,
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const errorText = await response.text();
    return NextResponse.json(
      {
        error: 'Failed to obtain orchestrator token',
        status: response.status,
        detail: errorText,
      },
      { status: 502 },
    );
  }

  const data = (await response.json()) as TokenResponse;
  const expiresAt = new Date(data.expires_at).getTime();
  cachedToken = {
    token: data.token,
    expiresAt,
  };

  return NextResponse.json(data);
}

