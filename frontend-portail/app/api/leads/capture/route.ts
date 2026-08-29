/**
 * Proxy same-origin vers le backend FastAPI — évite d'exposer BACKEND_URL au client
 * et permet d'ajouter côté serveur des vérifications (IP réelle via x-forwarded-for,
 * User-Agent, rate limiting supplémentaire au niveau Next).
 *
 * Aligné sur le pattern déjà en place dans frontend-conseiller/app/api/backend/[...path]/route.ts.
 */
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Récupération de l'IP réelle derrière un reverse proxy (Vercel, Nginx, Cloudflare)
    const ip =
      request.headers.get('x-forwarded-for')?.split(',')[0].trim() ||
      request.headers.get('x-real-ip') ||
      'unknown';

    const res = await fetch(`${BACKEND_URL}/public/leads/capture`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Forwarded-For': ip,
        'User-Agent': request.headers.get('user-agent') || 'unknown',
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      { detail: err.message || 'Erreur serveur' },
      { status: 500 }
    );
  }
}
