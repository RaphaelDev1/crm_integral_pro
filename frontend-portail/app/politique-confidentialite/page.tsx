/**
 * Politique de confidentialité (P5.1) — page légale obligatoire, liée depuis
 * le pied de page de /economiser. Contenu aligné sur
 * docs/REGISTRE_TRAITEMENTS_CNIL.md (mêmes finalités, durées de conservation,
 * sous-traitants) : toute modification de l'un doit se répercuter sur l'autre.
 *
 * ⚠️ Les champs `[À COMPLÉTER]` reprennent le même statut de brouillon que le
 * registre des traitements — à faire valider par un juriste/DPO avant le
 * lancement des premières campagnes publicitaires (voir registre, section 6).
 */
import Link from 'next/link';

import { GererCookiesButton } from '@/components/legal/GererCookiesButton';

export const metadata = {
  title: 'Politique de confidentialité | IA Conseil',
  robots: { index: true, follow: true },
};

export default function PolitiqueConfidentialite() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-10 text-slate-700">
      <p className="mb-6 rounded-lg bg-amber-50 p-3 text-xs text-amber-800 ring-1 ring-amber-200">
        Document en cours de finalisation — les mentions{' '}
        <code className="text-amber-900">[À COMPLÉTER]</code> seront renseignées avec les
        informations réelles de l'entreprise avant le lancement des premières campagnes
        publicitaires. Voir aussi <code className="text-amber-900">docs/REGISTRE_TRAITEMENTS_CNIL.md</code>.
      </p>

      <h1 className="mb-1 text-2xl font-bold text-slate-900">Politique de confidentialité</h1>
      <p className="mb-8 text-sm text-slate-500">Dernière mise à jour : [À COMPLÉTER : date]</p>

      <div className="space-y-6 text-sm leading-relaxed">
        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">1. Qui sommes-nous ?</h2>
          <p>
            Le présent site est édité par [À COMPLÉTER : raison sociale, ex. IA Conseil SAS],
            responsable du traitement de vos données personnelles au sens du Règlement Général sur
            la Protection des Données (RGPD). Pour toute question relative à vos données,
            contactez notre DPO : [À COMPLÉTER : email dédié, ex. dpo@iaconseil.fr].
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">
            2. Quelles données collectons-nous, et pourquoi ?
          </h2>
          <p>
            Lorsque vous utilisez notre simulateur d'économies (
            <Link href="/economiser" className="underline hover:text-slate-900">
              /economiser
            </Link>
            ), nous collectons : votre prénom, votre numéro de téléphone, votre email (facultatif),
            votre adresse (facultative), votre âge, vos dépenses mensuelles déclarées (mobile, box,
            énergie, assurances) ainsi que des données techniques (adresse IP, user-agent,
            paramètres UTM de la campagne publicitaire qui vous a amené sur le site).
          </p>
          <p className="mt-2">
            Ces données sont utilisées pour calculer votre estimation d'économies personnalisée et
            permettre à un conseiller de vous recontacter. Elles ne sont{' '}
            <strong>jamais revendues à des tiers</strong>.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">3. Sur quelle base légale ?</h2>
          <p>
            Le traitement repose sur votre consentement explicite, recueilli via les cases à
            cocher du formulaire : une case pour l'utilisation de vos données afin de calculer
            votre estimation et vous recontacter, une case distincte pour le démarchage
            téléphonique commercial. Vous pouvez retirer ce consentement à tout moment (voir
            section 7).
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">
            4. Combien de temps conservons-nous vos données ?
          </h2>
          <p>
            3 ans maximum après notre dernier contact avec vous, sauf si vous devenez client —
            dans ce cas la durée de conservation est alignée sur celle de la relation
            contractuelle et des obligations légales comptables applicables.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">5. Qui a accès à vos données ?</h2>
          <p>
            En interne : nos conseillers commerciaux, via un accès authentifié. En externe,
            certains prestataires techniques agissent en tant que sous-traitants (hébergement,
            envoi de SMS et d'emails, signature électronique) : [À COMPLÉTER : liste des
            sous-traitants réels et vérification de l'existence d'un contrat de sous-traitance
            (DPA) avec chacun].
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">
            6. Cookies et mesure d'audience
          </h2>
          <p>
            Nous utilisons des cookies de mesure d'audience et publicitaires (Meta, TikTok, Google
            Analytics) uniquement après votre consentement, recueilli via la bannière affichée à
            votre première visite. Vous pouvez modifier votre choix à tout moment :{' '}
            <GererCookiesButton />.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-bold text-slate-900">7. Vos droits</h2>
          <p>
            Conformément au RGPD, vous disposez d'un droit d'accès, de rectification,
            d'effacement, de limitation, d'opposition et de portabilité sur vos données. Vous
            pouvez exercer ces droits en écrivant à [À COMPLÉTER : email DPO]. Vous pouvez
            également vous désabonner de nos emails en un clic depuis le lien présent en pied de
            chacun d'eux.
          </p>
          <p className="mt-2">
            Si vous estimez que vos droits ne sont pas respectés, vous pouvez introduire une
            réclamation auprès de la CNIL (
            <a
              href="https://www.cnil.fr/fr/plaintes"
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-slate-900"
            >
              www.cnil.fr/fr/plaintes
            </a>
            ).
          </p>
        </section>
      </div>

      <p className="mt-10 text-sm">
        Voir aussi nos{' '}
        <Link href="/mentions-legales" className="underline hover:text-slate-900">
          mentions légales
        </Link>
        .
      </p>
    </main>
  );
}
