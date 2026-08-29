/**
 * Landing publique /economiser — capture prospects depuis campagnes TikTok / Instagram / Facebook.
 *
 * Structure :
 *   - Hero avec CTA agressif mais safe ("jusqu'à X€/an*")
 *   - Preuve sociale (chiffres réels, avis)
 *   - Tunnel 4 étapes (composant client EstimationForm)
 *   - Footer légal (mentions, RGPD, méthodologie)
 *
 * Server component (SEO/perf) qui charge le composant client uniquement pour le formulaire.
 * Aucun cookie / auth : c'est une page publique, indexable ou non selon meta robots.
 */
import { EstimationForm } from '@/components/landing/EstimationForm';
import { ConsentManager } from '@/components/legal/ConsentManager';
import { GererCookiesButton } from '@/components/legal/GererCookiesButton';
import { getLandingVariant, LANDING_COPY } from '@/lib/variant';
import Link from 'next/link';

export const metadata = {
  title: 'Économisez jusqu\'à 480€/an sur vos abonnements | IA Conseil',
  description:
    'Estimation gratuite en 60 secondes. Un conseiller vous rappelle sous 24h. Télécom, énergie, assurances — jusqu\'à 480€/an d\'économies.',
  openGraph: {
    title: 'Économisez jusqu\'à 480€/an sur vos abonnements',
    description: 'Estimation gratuite en 60 secondes.',
    type: 'website',
  },
  // On laisse l'indexation ouverte — le SEO longue traîne finit par convertir moins cher que le paid.
  robots: { index: true, follow: true },
};

export default function LandingEconomiser() {
  const variant = getLandingVariant();
  const copy = LANDING_COPY[variant];
  return (
    <>
      <ConsentManager />
      <main className="min-h-screen bg-gradient-to-b from-sky-50 to-white">
        {/* HERO ------------------------------------------------------------ */}
        <section className="mx-auto max-w-3xl px-4 pt-10 pb-6 text-center">
          <p className="mb-3 inline-block rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-800">
            {copy.badge}
          </p>
          <h1 className="text-4xl font-bold leading-tight text-slate-900 sm:text-5xl">
            {copy.titre.ligne1}
            <br />
            <span className="text-sky-600">{copy.titre.ligne2}</span>
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-lg text-slate-600">
            Un conseiller <strong>humain</strong> analyse vos factures télécom, énergie et
            assurances, et vous propose les meilleures offres adaptées à vous.
            <br />
            <strong className="text-slate-900">{copy.accroche}</strong>
          </p>

          {/* Preuve sociale rapide */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-6 text-sm text-slate-600">
            <div className="flex items-center gap-2">
              <span className="text-2xl">⭐</span>
              <span>
                <strong>4,8/5</strong> — 1 240 clients
              </span>
            </div>
            <div>
              <strong>350€</strong> économisés en moyenne
            </div>
            <div>
              <strong>Sans changer</strong> de qualité de service
            </div>
          </div>
        </section>

        {/* FORMULAIRE ------------------------------------------------------ */}
        <section className="mx-auto max-w-xl px-4 pb-10">
          <div className="rounded-2xl bg-white p-6 shadow-xl ring-1 ring-slate-200 sm:p-8">
            <EstimationForm variant={variant} ctaFinalLabel={copy.ctaFinal} />
          </div>
        </section>

        {/* COMMENT ÇA MARCHE ---------------------------------------------- */}
        <section className="mx-auto max-w-3xl px-4 py-12">
          <h2 className="mb-8 text-center text-2xl font-bold text-slate-900">
            Comment ça marche ?
          </h2>
          <ol className="grid gap-6 sm:grid-cols-3">
            {[
              {
                n: '1',
                titre: '60 secondes',
                texte: 'Renseignez vos abonnements actuels. On calcule votre estimation en direct.',
              },
              {
                n: '2',
                titre: 'Un appel',
                texte: 'Un conseiller vous rappelle sous 24h pour affiner et vous proposer les meilleures offres.',
              },
              {
                n: '3',
                titre: 'Vous économisez',
                texte: 'On s\'occupe des démarches. Vous continuez comme avant, avec une facture plus légère.',
              },
            ].map((etape) => (
              <li key={etape.n} className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
                <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full bg-sky-600 text-lg font-bold text-white">
                  {etape.n}
                </div>
                <h3 className="mb-2 font-semibold text-slate-900">{etape.titre}</h3>
                <p className="text-sm text-slate-600">{etape.texte}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* FOOTER LÉGAL --------------------------------------------------- */}
        <footer className="border-t border-slate-200 bg-slate-50 py-8">
          <div className="mx-auto max-w-3xl px-4 text-center text-xs text-slate-500">
            <p className="mb-2">
              *Estimation indicative basée sur la médiane payée par nos clients actuels dans la même
              catégorie et tranche d\'âge. Économie réelle variable selon votre situation exacte
              (consommation, options, éligibilité).{' '}
              <Link href="/economiser/methodologie" className="underline hover:text-slate-700">
                Voir notre méthodologie
              </Link>
              .
            </p>
            <p className="mb-2">
              Vos données sont utilisées uniquement pour vous recontacter et calculer votre
              estimation. Elles ne sont jamais revendues.{' '}
              <Link href="/politique-confidentialite" className="underline hover:text-slate-700">
                Politique de confidentialité
              </Link>{' '}
              ·{' '}
              <Link href="/mentions-legales" className="underline hover:text-slate-700">
                Mentions légales
              </Link>{' '}
              · <GererCookiesButton />
            </p>
            <p>© {new Date().getFullYear()} IA Conseil — Tous droits réservés</p>
          </div>
        </footer>
      </main>
    </>
  );
}
