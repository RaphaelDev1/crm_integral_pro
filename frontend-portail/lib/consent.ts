/**
 * Consentement cookies (P5.2, CNIL) — bannière custom, pas d'outil tiers
 * (Tarteaucitron/Axeptio) pour rester cohérent avec le reste de la landing
 * (pixels.tsx, attribution.ts) qui est déjà 100% first-party/hand-rolled.
 *
 * Une seule catégorie non essentielle ici : "mesure" (Meta Pixel + TikTok
 * Pixel + GA4, tous chargés par lib/pixels.tsx::PixelsHead). Pas de cookies
 * techniques tiers en dehors de ça, donc pas besoin d'un système de
 * catégories multiples — juste accepter/refuser, à prominence égale
 * (obligation CNIL), + possibilité de revenir dessus à tout moment (lien
 * "Gérer mes cookies" en pied de page).
 */

export const CONSENT_KEY = 'ia_cookie_consent';
export const CONSENT_EVENT = 'ia-consent-changed';

export interface ConsentState {
  mesure: boolean;
  horodatage: string;
}

export function getConsent(): ConsentState | null {
  try {
    const raw = localStorage.getItem(CONSENT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return typeof parsed?.mesure === 'boolean' ? parsed : null;
  } catch {
    return null;
  }
}

export function setConsent(mesure: boolean): void {
  const state: ConsentState = { mesure, horodatage: new Date().toISOString() };
  try {
    localStorage.setItem(CONSENT_KEY, JSON.stringify(state));
  } catch {
    // Stockage indisponible (navigation privée, quota…) — la bannière
    // réapparaîtra à chaque visite, dégradation acceptable.
  }
  window.dispatchEvent(new CustomEvent(CONSENT_EVENT));
}

/** Efface la décision — rouvre la bannière (lien "Gérer mes cookies"). */
export function reinitialiserConsent(): void {
  try {
    localStorage.removeItem(CONSENT_KEY);
  } catch {
    // no-op
  }
  window.dispatchEvent(new CustomEvent(CONSENT_EVENT));
}
