'use client';

/** Lien "Gérer mes cookies" — efface la décision stockée pour rouvrir la
 * bannière (CookieBanner, via ConsentManager qui écoute CONSENT_EVENT). Utilisé
 * en pied de page publique (économiser, politique de confidentialité). */
import { reinitialiserConsent } from '@/lib/consent';

export function GererCookiesButton() {
  return (
    <button
      type="button"
      onClick={reinitialiserConsent}
      className="underline hover:text-slate-700"
    >
      Gérer mes cookies
    </button>
  );
}
