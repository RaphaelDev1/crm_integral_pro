'use client';

/**
 * TurnstileWidget — captcha invisible Cloudflare Turnstile (P3.3). Charge le
 * script officiel à la demande (comme CalBooking.tsx le fait pour Cal.com —
 * pas de dépendance npm), rendu en mode "invisible" (pas de coche à cocher).
 *
 * Config : NEXT_PUBLIC_TURNSTILE_SITE_KEY. Vide = composant inerte (ne rend
 * rien, `onToken` n'est jamais appelé) — le formulaire reste soumissible sans
 * captcha, la vérification backend est elle aussi désactivée dans ce cas
 * (voir backend/services/captcha.py).
 */
import { useEffect, useRef } from 'react';

declare global {
  interface Window {
    turnstile?: {
      render: (container: string | HTMLElement, options: Record<string, unknown>) => string;
      reset: (widgetId?: string) => void;
    };
  }
}

const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js';

function loadTurnstileScript(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined') return resolve();
    if (window.turnstile) return resolve();
    const existing = document.querySelector(`script[src="${SCRIPT_SRC}"]`);
    if (existing) {
      existing.addEventListener('load', () => resolve());
      return;
    }
    const script = document.createElement('script');
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve();
    document.head.appendChild(script);
  });
}

export function TurnstileWidget({ onToken }: { onToken: (token: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!SITE_KEY || !containerRef.current) return;
    let cancelled = false;
    loadTurnstileScript().then(() => {
      if (cancelled || !containerRef.current || !window.turnstile) return;
      widgetIdRef.current = window.turnstile.render(containerRef.current, {
        sitekey: SITE_KEY,
        size: 'invisible',
        callback: (token: string) => onToken(token),
      });
    });
    return () => {
      cancelled = true;
    };
  }, [onToken]);

  if (!SITE_KEY) return null;

  return <div ref={containerRef} />;
}
