/**
 * Feature flag A/B test — headline + CTA de la landing /economiser.
 *
 * Contrôlé par `NEXT_PUBLIC_LANDING_VARIANT` ("A" par défaut, ou "B").
 * Volontairement simple (env var, pas de split runtime par visiteur) :
 * on bascule la variable et on redéploie pour tourner un test A/B par
 * fenêtre temporelle, cf. roadmap V3 P1.4. Les impressions par variante
 * sont loguées côté GA4 (voir `firePixel('landing_variant_view', ...)`
 * dans EstimationForm.tsx) — les rapports natifs GA4 suffisent pour lire
 * le taux de conversion par variante au début.
 */
export type LandingVariant = 'A' | 'B';

export function getLandingVariant(): LandingVariant {
  return process.env.NEXT_PUBLIC_LANDING_VARIANT === 'B' ? 'B' : 'A';
}

type LandingCopy = {
  badge: string;
  titre: { ligne1: string; ligne2: string };
  accroche: string;
  ctaFinal: string;
};

export const LANDING_COPY: Record<LandingVariant, LandingCopy> = {
  A: {
    badge: 'Estimation gratuite · 60 secondes · Sans engagement',
    titre: {
      ligne1: 'Vos abonnements vous coûtent trop cher.',
      ligne2: 'On vous montre combien vous pouvez économiser.',
    },
    accroche: 'Économie moyenne : 380€/an*',
    ctaFinal: 'Obtenir mon estimation 🎯',
  },
  B: {
    badge: '5 minutes chrono · Sans engagement',
    titre: {
      ligne1: '5 minutes pour économiser',
      ligne2: 'toute une année sur vos abonnements.',
    },
    accroche: 'Résultat immédiat, en moins de 5 minutes*',
    ctaFinal: 'Voir mon résultat en 5 min ⏱️',
  },
};
