'use client';

/**
 * Point d'entrée unique du consentement cookies (P5.2) — remplace
 * `<PixelsHead />` directement dans la page. Charge les pixels uniquement
 * après consentement explicite, affiche la bannière tant qu'aucune décision
 * n'est stockée, et réagit en direct à un changement (bannière ou lien
 * "Gérer mes cookies", voir GererCookiesButton.tsx).
 */
import { useEffect, useState } from 'react';

import { CookieBanner } from '@/components/legal/CookieBanner';
import { CONSENT_EVENT, ConsentState, getConsent } from '@/lib/consent';
import { PixelsHead } from '@/lib/pixels';

export function ConsentManager() {
  const [consent, setConsentState] = useState<ConsentState | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setConsentState(getConsent());
    setHydrated(true);
    const onChange = () => setConsentState(getConsent());
    window.addEventListener(CONSENT_EVENT, onChange);
    return () => window.removeEventListener(CONSENT_EVENT, onChange);
  }, []);

  return (
    <>
      {consent?.mesure && <PixelsHead />}
      {hydrated && !consent && <CookieBanner />}
    </>
  );
}
