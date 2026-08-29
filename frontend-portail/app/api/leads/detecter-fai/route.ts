/**
 * Proxy same-origin vers le backend FastAPI (/public/leads/detecter-fai) —
 * transmet l'IP réelle du visiteur (via x-forwarded-for) pour que le backend
 * puisse deviner son FAI actuel (voir backend/services/geo_ip.py).
 */
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  const ip =
    request.headers.get('x-forwarded-for')?.split(',')[0].trim() ||
    request.headers.get('x-real-ip') ||
    'unknown';

  try {
    const res = await fetch(`${BACKEND_URL}/public/leads/detecter-fai`, {
      headers: {
        'X-Forwarded-For': ip,
        'User-Agent': request.headers.get('user-agent') || 'unknown',
      },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message || 'Erreur serveur' }, { status: 500 });
  }
}
