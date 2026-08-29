/**
 * Page méthodologie — expose publiquement les sources et la logique de calcul
 * de l'estimation. Sert de :
 *   1. Justification légale (DGCCRF) pour la mention "jusqu'à X€/an*"
 *   2. Preuve de sérieux vis-à-vis des prospects sceptiques
 *   3. Cible du lien "Voir notre méthodologie" du footer landing
 */
export const metadata = {
  title: 'Méthodologie de nos estimations d\'économies | IA Conseil',
  robots: { index: true, follow: true },
};

export default function Methodologie() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="mb-6 text-3xl font-bold text-slate-900">
        Comment nous calculons vos économies
      </h1>

      <section className="mb-8">
        <h2 className="mb-3 text-xl font-semibold text-slate-900">Principe</h2>
        <p className="text-slate-700">
          Nous comparons le montant que vous nous déclarez au <strong>coût médian réel</strong>{' '}
          payé par nos clients dans la même catégorie (télécom, énergie, assurances) et,
          dans la mesure du possible, dans la même tranche d'âge.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-xl font-semibold text-slate-900">Sources</h2>
        <p className="mb-3 text-slate-700">
          Lorsque notre échantillon interne compte au moins 30 clients dans la catégorie visée,
          nous utilisons la médiane observée sur cet échantillon.
        </p>
        <p className="mb-3 text-slate-700">Sinon, nous nous appuyons sur les moyennes publiques :</p>
        <ul className="list-inside list-disc space-y-1 text-slate-700">
          <li>
            <strong>Télécom</strong> — Arcep, Observatoire des marchés (T4 2025)
          </li>
          <li>
            <strong>Énergie</strong> — CRE, tarif régulé TRV + moyennes offres marché
          </li>
          <li>
            <strong>Assurances</strong> — FFA (Fédération Française de l'Assurance), primes moyennes
          </li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-xl font-semibold text-slate-900">Fourchette</h2>
        <p className="text-slate-700">
          Nos estimations sont présentées sous forme d'une fourchette{' '}
          <strong>±25 % autour d'une valeur typique</strong>. Les économies réelles dépendent de
          votre situation exacte : options souscrites, consommation réelle, éligibilité à des
          promotions, période de l'année, etc.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-xl font-semibold text-slate-900">Aucune promesse chiffrée exacte</h2>
        <p className="text-slate-700">
          L'estimation en ligne est <strong>indicative</strong>. Seul un rendez-vous téléphonique
          avec un conseiller permet d'obtenir un chiffre d'économie définitif, basé sur vos
          factures et votre profil réel.
        </p>
      </section>

      <p className="mt-12 text-xs text-slate-500">
        Dernière mise à jour de nos barèmes : recalcul automatique toutes les 6 heures sur la base
        de notre parc clients actif.
      </p>
    </main>
  );
}
