/**
 * Attribution multi-touch "légère" (P4.3, first-party, sans outil tiers) —
 * conserve un historique local (localStorage) des visites trackées (UTM
 * présent dans l'URL) avant conversion, envoyé avec le payload de
 * POST /api/leads/capture (voir components/landing/EstimationForm.tsx) et
 * persisté côté backend dans la table `touchpoints`
 * (backend/routers/leads_public.py, backend/models/touchpoint.py).
 *
 * Le dashboard conseiller (backend/routers/dashboard_utm.py::attribution_multi_touch)
 * calcule ensuite premier contact vs dernier contact à partir de cet
 * historique — pas de modélisation pondérée (Markov, Shapley…), volontairement
 * hors scope (voir roadmap V3 P4.3 : "outil tiers ou custom léger").
 *
 * Distinct de la clé localStorage `ia_utm` (EstimationForm.tsx) qui ne garde
 * que l'UTM courant pour pré-remplir le payload de capture.
 */

export interface UtmParams {
  source?: string;
  medium?: string;
  campaign?: string;
  content?: string;
  term?: string;
}

export interface Touchpoint {
  utm: UtmParams;
  referrer?: string;
  landing_page?: string;
  horodatage?: string;
}

const STORAGE_KEY = 'ia_touchpoints';
// Au-delà, on ne garde que le tout premier contact (le plus utile pour
// l'attribution) et les plus récents — voir appendTouchpoint.
const MAX_TOUCHPOINTS = 10;

function memeUtm(a: UtmParams, b: UtmParams): boolean {
  return a.source === b.source && a.medium === b.medium && a.campaign === b.campaign;
}

export function getStoredTouchpoints(): Touchpoint[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function sauvegarder(touchpoints: Touchpoint[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(touchpoints));
  } catch {
    // Stockage indisponible (navigation privée, quota…) — l'attribution
    // multi-touch dégrade silencieusement vers un simple last-touch (le champ
    // `utm` toujours envoyé séparément par EstimationForm reste fiable).
  }
}

/**
 * À appeler à chaque chargement de la landing où un UTM est présent dans
 * l'URL (visite issue d'un clic pub) — ignore les rechargements de la même
 * visite (UTM identique au dernier point enregistré) pour ne pas gonfler
 * artificiellement la chaîne d'attribution.
 */
export function enregistrerTouchpoint(utm: UtmParams): void {
  if (!utm.source) return;
  const touchpoints = getStoredTouchpoints();
  const dernier = touchpoints[touchpoints.length - 1];
  if (dernier && memeUtm(dernier.utm, utm)) return;

  touchpoints.push({
    utm,
    referrer: typeof document !== 'undefined' ? document.referrer || undefined : undefined,
    landing_page: typeof window !== 'undefined' ? window.location.pathname : undefined,
    horodatage: new Date().toISOString(),
  });

  // Garde le premier contact (indice 0) — le plus structurant pour
  // l'attribution — et les plus récents, plutôt que de tronquer bêtement en
  // tête ce qui ferait perdre le tout premier point de contact.
  while (touchpoints.length > MAX_TOUCHPOINTS) {
    touchpoints.splice(1, 1);
  }
  sauvegarder(touchpoints);
}

/** Appelé après une capture de lead réussie — repart d'un historique propre. */
export function reinitialiserTouchpoints(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // no-op
  }
}
