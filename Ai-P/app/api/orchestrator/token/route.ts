import { NextResponse } from 'next/server';

const ORCHESTRATOR_BASE_URL =
  process.env.ORCHESTRATOR_BASE_URL ?? 'http://localhost:8040';
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

