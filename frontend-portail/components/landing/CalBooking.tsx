'use client';

/**
 * CalBooking — modale de prise de rendez-vous Cal.com, ouverte depuis l'écran
 * de résultat (étape 4) de EstimationForm. Utilise le "vanilla embed" officiel
 * de Cal.com (script chargé à la demande, pas de dépendance npm) plutôt que
 * @calcom/embed-react, pour ne rien ajouter au bundle des visiteurs qui ne
 * cliquent jamais sur "Choisir un créneau".
 *
 * Config : NEXT_PUBLIC_CALCOM_LINK (ex. "iaconseil/estimation-gratuite").
 * Vide = fonctionnalité désactivée (bouton masqué côté EstimationForm).
 */
import { useEffect, useRef } from 'react';

declare global {
  interface Window {
    Cal?: any;
  }
}

const CALCOM_LINK = process.env.NEXT_PUBLIC_CALCOM_LINK;

export function calBookingEnabled(): boolean {
  return Boolean(CALCOM_LINK);
}

function loadCalEmbed() {
  if (typeof window === 'undefined' || window.Cal) return;
  (function (C: any, A: string, L: string) {
    const p = (a: any, ar: any) => a.q.push(ar);
    const d = C.document;
    C.Cal = C.Cal
      || function (...args: any[]) {
        const cal = C.Cal;
        if (!cal.loaded) {
          cal.ns = {};
          cal.q = cal.q || [];
          d.head.appendChild(d.createElement('script')).src = A;
          cal.loaded = true;
        }
        if (args[0] === L) {
          const api: any = (...apiArgs: any[]) => p(api, apiArgs);
          const namespace = args[1];
          api.q = api.q || [];
          if (typeof namespace === 'string') {
            cal.ns[namespace] = cal.ns[namespace] || api;
            p(cal.ns[namespace], args);
            p(cal, ['initNamespace', namespace]);
          } else {
            p(cal, args);
          }
          return;
        }
        p(cal, args);
      };
  })(window, 'https://app.cal.com/embed/embed.js', 'init');
}

export function CalBooking({
  prenom,
  telephone,
  email,
  onClose,
}: {
  prenom?: string;
  telephone?: string;
  email?: string;
  onClose: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!CALCOM_LINK || !containerRef.current) return;
    loadCalEmbed();
    window.Cal!('init', { origin: 'https://cal.com' });
    window.Cal!('inline', {
      elementOrSelector: containerRef.current,
      calLink: CALCOM_LINK,
      layout: 'month_view',
      config: {
        name: prenom || undefined,
        email: email || undefined,
        notes: telephone ? `Téléphone : ${telephone}` : undefined,
      },
    });
  }, [prenom, telephone, email]);

  if (!CALCOM_LINK) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="relative max-h-[90vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-2 shadow-2xl sm:p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer"
          className="absolute right-3 top-3 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-500 hover:bg-slate-200"
        >
          ✕
        </button>
        <div ref={containerRef} style={{ minHeight: 500, width: '100%' }} />
      </div>
    </div>
  );
}
