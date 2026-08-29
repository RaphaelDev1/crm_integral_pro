/**
 * Mentions légales (P5.1) — page légale obligatoire (LCEN art. 6-III),
 * liée depuis le pied de page de /economiser.
 *
 * ⚠️ Brouillon : les champs `[À COMPLÉTER]` (SIRET, capital social, directeur
 * de publication…) doivent être renseignés avec les informations réelles de
 * l'entreprise avant le lancement des premières campagnes publicitaires —
 * voir docs/REGISTRE_TRAITEMENTS_CNIL.md, section 6.
 */
import Link from 'next/link';

export const metadata = {
  title: 'Mentions légales | IA Conseil',
  robots: { index: true, follow: true },
};

export default function MentionsLegales() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-10 text-slate-700">
      <p className="mb-6 rounded-lg bg-amber-50 p-3 text-xs text-amber-800 ring-1 ring-amber-200">
        Document en cours de finalisation — les mentions{' '}
        <code className="text-amber-900">[À COMPLÉTER]</code> seront renseignées avec les
        informations réelles de l'entreprise avant le lancement des premières campagnes
        publicitaires.
      </p>

      <h1 className="mb-8 text-2xl font-bold text-slate-900">Mentions légales</h1>

      <div className="space-y-6 text-sm leading-relaxed">
        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">1. Édition du site</h2>
          <ul className="space-y-1">
            <li>Raison sociale : [À COMPLÉTER : ex. IA Conseil SAS]</li>
            <li>Forme juridique : [À COMPLÉTER]</li>
            <li>Capital social : [À COMPLÉTER]</li>
            <li>SIRET : [À COMPLÉTER]</li>
            <li>Siège social : [À COMPLÉTER]</li>
            <li>Directeur de la publication : [À COMPLÉTER]</li>
            <li>Contact : [À COMPLÉTER : email de contact]</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">2. Hébergement</h2>
          <p>
            Le présent site est hébergé par [À COMPLÉTER : raison sociale de l'hébergeur, adresse,
            téléphone].
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">3. Propriété intellectuelle</h2>
          <p>
            L'ensemble des contenus présents sur ce site (textes, visuels, logos) est la propriété
            de [À COMPLÉTER : raison sociale] ou de ses partenaires, sauf mention contraire. Toute
            reproduction, représentation ou diffusion, en tout ou partie, sans autorisation
            préalable, est interdite.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">4. Responsabilité</h2>
          <p>
            Les informations et estimations fournies sur ce site sont données à titre indicatif.
            Elles ne constituent pas un engagement contractuel avant validation par un conseiller.
            Voir notre{' '}
            <Link href="/economiser/methodologie" className="underline hover:text-slate-900">
              méthodologie de calcul
            </Link>
            .
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">
            5. Données personnelles et cookies
          </h2>
          <p>
            Le traitement de vos données personnelles et l'utilisation de cookies sont détaillés
            dans notre{' '}
            <Link href="/politique-confidentialite" className="underline hover:text-slate-900">
              politique de confidentialité
            </Link>
            .
          </p>
        </section>
      </div>
    </main>
  );
}
