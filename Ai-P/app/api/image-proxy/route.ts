import { NextResponse } from 'next/server';

const ALLOWED_PROTOCOLS = new Set(['http:', 'https:']);
const MAX_URL_LENGTH = 2048;

export async function GET(request: Request) {
    const url = new URL(request.url);
    const targetUrl = url.searchParams.get('url');

    if (!targetUrl) {
        return NextResponse.json({ error: 'Missing url parameter' }, { status: 400 });
    }

    if (targetUrl.length > MAX_URL_LENGTH) {
        return NextResponse.json({ error: 'URL too long' }, { status: 400 });
    }

    let parsedTarget: URL;
    try {
        parsedTarget = new URL(targetUrl);
    } catch {
        return NextResponse.json({ error: 'Invalid URL' }, { status: 400 });
    }

    if (!ALLOWED_PROTOCOLS.has(parsedTarget.protocol)) {
        return NextResponse.json({ error: 'Unsupported protocol' }, { status: 400 });
    }

    try {
        const upstreamResponse = await fetch(parsedTarget, {
            // Never reuse cached responses so we always reflect current listings
            cache: 'no-store',
            // Prevent the upstream from inferring our origin
            headers: {
                // Stripping Accept headers keeps the request generic and avoids negotiated formats we can’t serve
                Accept: 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            },
        });

        if (!upstreamResponse.ok || !upstreamResponse.body) {
            return NextResponse.json(
                { error: `Upstream request failed (${upstreamResponse.status})` },
                { status: upstreamResponse.status === 200 ? 502 : upstreamResponse.status },
            );
        }

        const contentType = upstreamResponse.headers.get('content-type') ?? 'application/octet-stream';

        return new NextResponse(upstreamResponse.body, {
            status: 200,
            headers: {
                'content-type': contentType,
                // Cache for one hour; browsers revalidate via the proxy so backend load stays reasonable
                'cache-control': 'public, max-age=3600',
            },
        });
    } catch (error) {
        console.error('[ImageProxy] Failed to proxy image', {
            error,
            targetUrl,
        });
        return NextResponse.json({ error: 'Failed to fetch upstream image' }, { status: 502 });
    }
}

