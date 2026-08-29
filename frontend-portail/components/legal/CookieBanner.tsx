'use client';

/**
 * Bannière de consentement cookies (P5.2, CNIL) — affichée tant qu'aucune
 * décision n'est stockée (voir lib/consent.ts). Boutons "Refuser" / "Accepter"
 * à prominence strictement égale (taille, couleur de fond pleine pour les
 * deux) : la CNIL sanctionne un refus rendu plus difficile que l'acceptation.
 */
import Link from 'next/link';

import { setConsent } from '@/lib/consent';

export function CookieBanner() {
  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Consentement cookies"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 bg-white p-4 shadow-[0_-4px_16px_rgba(0,0,0,0.08)] sm:p-5"
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-600">
          Nous utilisons des cookies de mesure d'audience et publicitaires (Meta, TikTok, Google
          Analytics) pour comprendre l'origine de nos visiteurs. Vous pouvez les refuser sans
          impact sur votre estimation.{' '}
          <Link href="/politique-confidentialite" className="underline hover:text-slate-800">
            En savoir plus
          </Link>
          .
        </p>
        <div className="flex shrink-0 gap-3">
          <button
            type="button"
            onClick={() => setConsent(false)}
            className="flex-1 rounded-xl border-2 border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 sm:flex-none"
          >
            Refuser
          </button>
          <button
            type="button"
            onClick={() => setConsent(true)}
            className="flex-1 rounded-xl bg-sky-600 px-5 py-3 text-sm font-semibold text-white hover:bg-sky-700 sm:flex-none"
          >
            Accepter
          </button>
        </div>
      </div>
    </div>
  );
}
