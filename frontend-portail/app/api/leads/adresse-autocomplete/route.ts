/**
 * Proxy same-origin vers le backend FastAPI (/public/leads/adresse-autocomplete)
 * — même pattern que app/api/leads/capture/route.ts.
 */
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get('q') || '';
  try {
    const res = await fetch(
      `${BACKEND_URL}/public/leads/adresse-autocomplete?q=${encodeURIComponent(q)}`,
      { headers: { 'User-Agent': request.headers.get('user-agent') || 'unknown' } }
    );
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ detail: err.message || 'Erreur serveur' }, { status: 500 });
  }
}
