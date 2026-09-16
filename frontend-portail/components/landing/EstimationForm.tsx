'use client';

/**
 * EstimationForm — tunnel de capture en 4 étapes pour la landing publique
 * /economiser (frontend-portail).
 *
 * Appelle le backend via le proxy BFF same-origin `/api/leads/capture`
 * (voir app/api/leads/capture/route.ts), aligné sur le pattern déjà en place
 * dans frontend-conseiller/app/api/backend/[...path]/route.ts : le backend
 * n'est jamais exposé au client, et l'IP/UA réels sont relayés côté serveur.
 *
 * Optimisations CRO :
 *   - Progression visible, un seul champ obligatoire par étape (friction minimale)
 *   - Validation inline, mobile-first (80 % du trafic Meta/TikTok = mobile)
 *   - Honeypot invisible (bots)
 *   - UTM auto-récupérés depuis URL + localStorage
 *   - Pixels Meta/TikTok/GA4 sur les étapes clés
 */
import { FormEvent, ReactNode, useCallback, useEffect, useState } from 'react';

import { AdresseAutocomplete, type AdresseSuggestion } from '@/components/landing/AdresseAutocomplete';
import { CalBooking, calBookingEnabled } from '@/components/landing/CalBooking';
import { TurnstileWidget } from '@/components/landing/TurnstileWidget';
import { enregistrerTouchpoint, getStoredTouchpoints, reinitialiserTouchpoints } from '@/lib/attribution';
import { firePixel } from '@/lib/pixels';
import type { LandingVariant } from '@/lib/variant';

type Depenses = {
  mobile?: number;
  box_fibre?: number;
  pack_box_mobile?: number;
  electricite?: number;
  gaz?: number;
  assurance_auto?: number;
  assurance_habitation?: number;
  assurance_sante?: number;
};

const PLAGES_HORAIRES = ['Matin (9h-12h)', 'Après-midi (12h-17h)', 'Soir (17h-20h)'] as const;
const JOURS_RAPPEL = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Peu importe'] as const;

// Mêmes tranches que backend/services/estimation_publique.py::TRANCHES_AGE —
// on ne demande plus l'âge exact, seulement la tranche.
const TRANCHES_AGE = ['18-25', '26-35', '36-45', '46-55', '56-65', '66+'] as const;

// Sous-choix télécom (étape 1) — évite de comparer mobile ET box/fibre quand
// une seule des deux intéresse le prospect (étape 2 n'affiche alors que le(s)
// champ(s) pertinent(s)).
const TELECOM_CHOIX = [
  { key: 'mobile', label: '📱 Mobile' },
  { key: 'box', label: '📶 Box internet' },
  { key: 'les_deux', label: '📱📶 Les deux' },
] as const;
type TelecomChoix = (typeof TELECOM_CHOIX)[number]['key'] | '';

// Mêmes libellés/valeurs que la trame mobile conseiller (roaming_ue /
// sensibilite_prix, voir backend/scripts/seed_ia_conseil.py) — posées ici
// pour que le conseiller n'ait plus à les redemander au téléphone.
const ROAMING_OPTIONS = ['Jamais', 'Occasionnellement', 'Souvent'] as const;

// Mêmes opérateurs que la trame conseiller (backend/scripts/seed_ia_conseil.py
// pour le mobile, seed_ia_conseil_box.py pour la box) — un client peut avoir
// deux opérateurs différents (mobile ≠ box), donc deux listes distinctes.
const OPERATEURS_MOBILE = ['Orange', 'Sosh', 'SFR', 'RED by SFR', 'Bouygues Telecom', 'B&You', 'Free Mobile'] as const;
const OPERATEURS_BOX = [
  'Orange', 'Sosh', 'SFR', 'RED by SFR', 'Bouygues Telecom', 'Free',
  'Coriolis Telecom', 'Nordnet', 'La Poste Mobile', 'Ozone',
] as const;
const OFFRES_BOX = ['ADSL', 'Fibre'] as const;

type UTM = {
  source?: string;
  medium?: string;
  campaign?: string;
  content?: string;
  term?: string;
};

type EstimationResp = {
  ok: boolean;
  ref: string;
  message: string;
  estimation: {
    lignes: Array<{
      categorie: string;
      cout_actuel_mensuel: number;
      notre_moyenne_mensuel: number;
      economie_annuelle_typique: number;
      source: string;
      echantillon: number;
      tranche_age_utilisee: string | null;
    }>;
    economie_annuelle_totale_basse: number;
    economie_annuelle_totale_haute: number;
    economie_annuelle_totale_typique: number;
  };
  fibre: {
    disponible: boolean | null;
    taux_couverture: number | null;
  };
};

const SECTEURS = [
  { key: 'telecom', label: '📱 Télécom (mobile / fibre)' },
  { key: 'energie', label: '⚡ Énergie (électricité / gaz)' },
  { key: 'assurances', label: '🛡️ Assurances (auto / habitation / santé)' },
] as const;

const TEL_RE = /^(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}$/;

// Questions par secteur (docs/QUESTIONS_PAR_SECTEUR.md) — uniquement les
// questions à fort pouvoir de filtrage ou de valeur pour le conseiller ; les
// questions de confort (5G, engagement, isolation…) restent posées au
// téléphone, pas sur la landing (« moins on a de questions, meilleur c'est »).
const OBJECTIFS_PRINCIPAUX = [
  { key: 'economiser', label: '💰 Économiser' },
  { key: 'simplifier', label: '✨ Simplifier' },
  { key: 'ameliorer_qualite', label: '🚀 Améliorer la qualité' },
  { key: 'regrouper', label: '📦 Tout regrouper' },
] as const;
const NB_LIGNES_MOBILES = ['1', '2+'] as const;
const CHAUFFAGES_PRINCIPAUX = ['Électrique', 'Gaz', 'Bois / fioul / PAC', 'Chauffage collectif inclus'] as const;
const PUISSANCES_KVA = ['3', '6', '9', '12+'] as const;
const OPTIONS_TARIFAIRES = ['Base', 'Heures Pleines-Creuses', 'Tempo'] as const;
const USAGES_TV = ['Jamais, uniquement streaming', 'Quelques chaînes', 'Bouquet premium'] as const;

// B3b (docs/QUESTIONS_PAR_SECTEUR.md) — liste standard des abonnements
// payants les plus fréquents en plus du bouquet box, + "Autre" en texte
// libre (voir SelectionMultiple ci-dessous).
const ABONNEMENTS_PAYANTS_OPTIONS = [
  'Canal+', 'beIN Sports', 'RMC Sport', 'OCS', 'Ligue 1+', 'Netflix (inclus box)', 'Disney+', 'Paramount+',
] as const;

export function EstimationForm({
  variant = 'A',
  ctaFinalLabel = 'Obtenir mon estimation 🎯',
}: {
  variant?: LandingVariant;
  ctaFinalLabel?: string;
}) {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  // Position dans la liste dynamique de sous-questions de l'étape 2 (une
  // question affichée à la fois, style Typeform) — voir questionsEtape2
  // ci-dessous, calculée à partir des réponses déjà données.
  const [subStep, setSubStep] = useState(0);
  const [showBooking, setShowBooking] = useState(false);
  const [secteurs, setSecteurs] = useState<string[]>([]);
  const [telecomChoix, setTelecomChoix] = useState<TelecomChoix>('');
  const [depenses, setDepenses] = useState<Depenses>({});
  const [operateurMobile, setOperateurMobile] = useState('');
  const [operateurBox, setOperateurBox] = useState('');
  const [offreBox, setOffreBox] = useState('');
  const [debitBox, setDebitBox] = useState<number | ''>('');
  const [fournisseurEnergie, setFournisseurEnergie] = useState('');
  const [consoDataGo, setConsoDataGo] = useState<number | ''>('');
  const [roamingEurope, setRoamingEurope] = useState('');
  const [roamingMonde, setRoamingMonde] = useState('');
  const [trancheAge, setTrancheAge] = useState('');
  const [bonusMalusAuto, setBonusMalusAuto] = useState('');
  // Socle commun (S5, toujours posé) + adresse (S1, posée seulement si énergie
  // sélectionné — inutile pour le télécom seul : le client indique déjà s'il a
  // l'ADSL ou la fibre via la question "Offre actuelle" juste après).
  const [objectifPrincipal, setObjectifPrincipal] = useState('');
  const [adresseTexte, setAdresseTexte] = useState('');
  const [adresseSuggestion, setAdresseSuggestion] = useState<AdresseSuggestion | null>(null);
  // Trame mobile (M1)
  const [nbLignesMobiles, setNbLignesMobiles] = useState('');
  // Trame énergie (E1, E5, E5a, E6)
  const [chauffagePrincipal, setChauffagePrincipal] = useState('');
  const [puissanceKva, setPuissanceKva] = useState('');
  const [grosEquipementElectrique, setGrosEquipementElectrique] = useState<boolean | null>(null);
  const [optionTarifaire, setOptionTarifaire] = useState('');
  // Trame box (B3, B3b)
  const [usageTv, setUsageTv] = useState('');
  const [abonnementsSelection, setAbonnementsSelection] = useState<string[]>([]);
  const [abonnementAutre, setAbonnementAutre] = useState('');
  const [prenom, setPrenom] = useState('');
  const [telephone, setTelephone] = useState('');
  const [email, setEmail] = useState('');
  const [jourRappel, setJourRappel] = useState('');
  const [plageHoraire, setPlageHoraire] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const [consentement, setConsentement] = useState(false);
  const [consentementDemarchage, setConsentementDemarchage] = useState(false);
  const [hpField, setHpField] = useState('');
  const [utm, setUtm] = useState<UTM>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EstimationResp | null>(null);

  const handleTurnstileToken = useCallback((token: string) => setTurnstileToken(token), []);

  // UTM depuis URL + persistance localStorage (survit à un refresh entre pages)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const readUtm: UTM = {
      source: params.get('utm_source') || undefined,
      medium: params.get('utm_medium') || undefined,
      campaign: params.get('utm_campaign') || undefined,
      content: params.get('utm_content') || undefined,
      term: params.get('utm_term') || undefined,
    };
    if (readUtm.source) {
      try {
        localStorage.setItem('ia_utm', JSON.stringify(readUtm));
      } catch {}
      setUtm(readUtm);
      // Attribution multi-touch (P4.3) — chaque visite trackée (UTM dans
      // l'URL) est ajoutée à l'historique first-party envoyé à la capture.
      enregistrerTouchpoint(readUtm);
    } else {
      try {
        const stored = localStorage.getItem('ia_utm');
        if (stored) setUtm(JSON.parse(stored));
      } catch {}
    }
    firePixel('PageView');
    // Impression par variante (A/B test headline+CTA, roadmap V3 P1.4) — lue
    // ensuite dans les rapports natifs GA4 par le paramètre `variant`.
    firePixel('landing_variant_view', { variant });
  }, [variant]);

  const mobilePertinent = secteurs.includes('telecom') && (telecomChoix === 'mobile' || telecomChoix === 'les_deux');
  const boxPertinent = secteurs.includes('telecom') && (telecomChoix === 'box' || telecomChoix === 'les_deux');

  const canGoStep2 = secteurs.length > 0 && (!secteurs.includes('telecom') || telecomChoix !== '');
  const canGoStep3 = Object.values(depenses).some((v) => v && v > 0) && trancheAge !== '';
  const canSubmit =
    prenom.trim().length > 0 && TEL_RE.test(telephone.trim()) && consentement;

  const avancerSousEtape = () => setSubStep((s) => s + 1);
  const reculerSousEtape = () => (subStep > 0 ? setSubStep((s) => s - 1) : setStep(1));

  // Liste ordonnée des sous-questions de l'étape 2 — même ordre et mêmes
  // conditions d'affichage que l'ancien formulaire "tout en un", mais une
  // seule question rendue à la fois (voir `step === 2` plus bas). Un item
  // masqué (`visible: false`) est simplement retiré de la liste filtrée :
  // une question qui devient pertinente après une réponse (ex. "Offre
  // actuelle" après avoir saisi une dépense box) apparaît alors à sa place
  // naturelle, juste après la question qui l'a révélée.
  type QuestionEtape2 = { key: string; visible: boolean; content: ReactNode };

  const questionsEtape2: QuestionEtape2[] = [
    {
      key: 'objectif',
      visible: true,
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Votre objectif principal ?</h3>
          <div className="grid grid-cols-2 gap-2">
            {OBJECTIFS_PRINCIPAUX.map((opt) => (
              <button
                key={opt.key}
                type="button"
                onClick={() => {
                  const nouveau = objectifPrincipal === opt.key ? '' : opt.key;
                  setObjectifPrincipal(nouveau);
                  if (nouveau) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2.5 text-sm font-medium transition-all ${
                  objectifPrincipal === opt.key
                    ? 'border-sky-600 bg-sky-600 text-white'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: 'adresse',
      visible: secteurs.includes('energie'),
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Votre adresse</h3>
          <AdresseAutocomplete
            value={adresseTexte}
            onChange={(v) => {
              setAdresseTexte(v);
              setAdresseSuggestion(null);
            }}
            onSelect={setAdresseSuggestion}
          />
        </div>
      ),
    },
    {
      key: 'depense_mobile',
      visible: mobilePertinent,
      content: <MoneyInput label="Forfait mobile — combien payez-vous par mois ?" value={depenses.mobile}
        onChange={(v) => setDepenses({ ...depenses, mobile: v })} />,
    },
    {
      key: 'depense_box',
      visible: boxPertinent,
      content: <MoneyInput label="Box internet — combien payez-vous par mois ?" value={depenses.box_fibre}
        onChange={(v) => setDepenses({ ...depenses, box_fibre: v })} />,
    },
    {
      key: 'box_operateur',
      visible: boxPertinent && Boolean(depenses.box_fibre),
      content: (
        <SelectOperateur
          label="Opérateur box actuel (optionnel)"
          options={OPERATEURS_BOX}
          value={operateurBox}
          onChange={setOperateurBox}
        />
      ),
    },
    {
      key: 'box_offre',
      visible: boxPertinent && Boolean(depenses.box_fibre),
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Offre actuelle</h3>
          <div className="grid grid-cols-2 gap-2">
            {OFFRES_BOX.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const nouveau = offreBox === opt ? '' : opt;
                  setOffreBox(nouveau);
                  if (nouveau) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2 text-sm font-medium transition-all ${
                  offreBox === opt
                    ? 'border-sky-600 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: 'box_debit',
      visible: boxPertinent && Boolean(depenses.box_fibre),
      content: (
        <div>
          <label className="mb-1 block text-lg font-semibold text-slate-900">Débit box (optionnel)</label>
          <div className="relative">
            <input
              type="number"
              inputMode="numeric"
              min={0}
              value={debitBox}
              onChange={(e) => setDebitBox(e.target.value ? Number(e.target.value) : '')}
              placeholder="Ex : 400"
              className="w-full rounded-lg border border-slate-300 py-3 pl-4 pr-16 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
            />
            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-slate-500">Mbps</span>
          </div>
        </div>
      ),
    },
    {
      key: 'box_usage_tv',
      visible: boxPertinent && Boolean(depenses.box_fibre),
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Regardez-vous la TV via la box ?</h3>
          <div className="grid grid-cols-1 gap-2">
            {USAGES_TV.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const nouveau = usageTv === opt ? '' : opt;
                  setUsageTv(nouveau);
                  if (nouveau) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2 text-sm font-medium transition-all ${
                  usageTv === opt
                    ? 'border-sky-600 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: 'box_abonnements',
      visible: boxPertinent && Boolean(depenses.box_fibre) && usageTv !== '' && usageTv !== 'Jamais, uniquement streaming',
      content: (
        <SelectionMultiple
          label="Abonnements payants en plus (optionnel)"
          options={ABONNEMENTS_PAYANTS_OPTIONS}
          selection={abonnementsSelection}
          onChangeSelection={setAbonnementsSelection}
          autre={abonnementAutre}
          onChangeAutre={setAbonnementAutre}
        />
      ),
    },
    {
      key: 'depense_electricite',
      visible: secteurs.includes('energie'),
      content: <MoneyInput label="Électricité — combien payez-vous par mois ?" value={depenses.electricite}
        onChange={(v) => setDepenses({ ...depenses, electricite: v })} />,
    },
    {
      key: 'depense_gaz',
      visible: secteurs.includes('energie'),
      content: <MoneyInput label="Gaz — combien payez-vous par mois ?" value={depenses.gaz}
        onChange={(v) => setDepenses({ ...depenses, gaz: v })} />,
    },
    {
      key: 'energie_fournisseur',
      visible: secteurs.includes('energie') && Boolean(depenses.electricite || depenses.gaz),
      content: (
        <div>
          <label className="mb-1 block text-lg font-semibold text-slate-900">
            Fournisseur d'énergie actuel (optionnel)
          </label>
          <input
            type="text"
            value={fournisseurEnergie}
            onChange={(e) => setFournisseurEnergie(e.target.value)}
            placeholder="Ex : EDF, Engie, TotalEnergies…"
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
          />
        </div>
      ),
    },
    {
      key: 'energie_chauffage',
      visible: secteurs.includes('energie') && Boolean(depenses.electricite || depenses.gaz),
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Chauffage principal du logement</h3>
          <div className="grid grid-cols-2 gap-2">
            {CHAUFFAGES_PRINCIPAUX.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const nouveau = chauffagePrincipal === opt ? '' : opt;
                  setChauffagePrincipal(nouveau);
                  if (nouveau) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2 text-xs font-medium transition-all sm:text-sm ${
                  chauffagePrincipal === opt
                    ? 'border-sky-600 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: 'energie_puissance',
      visible: Boolean(depenses.electricite),
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">
            Puissance souscrite (kVA — sur votre facture, en haut)
          </h3>
          <div className="grid grid-cols-4 gap-2">
            {PUISSANCES_KVA.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const nouveau = puissanceKva === opt ? '' : opt;
                  setPuissanceKva(nouveau);
                  if (nouveau) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2 text-sm font-medium transition-all ${
                  puissanceKva === opt
                    ? 'border-sky-600 bg-sky-600 text-white'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: 'energie_gros_equipement',
      visible: puissanceKva === '9' || puissanceKva === '12+',
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">
            Avez-vous une clim, une piscine, un véhicule électrique ou des plaques induction puissantes ?
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {[{ label: 'Oui', value: true }, { label: 'Non', value: false }].map((opt) => (
              <button
                key={opt.label}
                type="button"
                onClick={() => {
                  const nouveau = grosEquipementElectrique === opt.value ? null : opt.value;
                  setGrosEquipementElectrique(nouveau);
                  if (nouveau !== null) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2 text-sm font-medium transition-all ${
                  grosEquipementElectrique === opt.value
                    ? 'border-sky-600 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {grosEquipementElectrique === false && (
            <p className="mt-2 rounded-lg bg-emerald-50 p-3 text-xs text-emerald-800">
              💡 Sans gros équipement, vous pourriez économiser en baissant votre puissance souscrite à
              6 kVA — le conseiller vérifiera ça avec vous.
            </p>
          )}
        </div>
      ),
    },
    {
      key: 'energie_option_tarifaire',
      visible: Boolean(depenses.electricite),
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Option tarifaire actuelle</h3>
          <div className="grid grid-cols-3 gap-2">
            {OPTIONS_TARIFAIRES.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const nouveau = optionTarifaire === opt ? '' : opt;
                  setOptionTarifaire(nouveau);
                  if (nouveau) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2 text-xs font-medium transition-all sm:text-sm ${
                  optionTarifaire === opt
                    ? 'border-sky-600 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: 'depense_assurance_auto',
      visible: secteurs.includes('assurances'),
      content: <MoneyInput label="Assurance auto — combien payez-vous par mois ?" value={depenses.assurance_auto}
        onChange={(v) => setDepenses({ ...depenses, assurance_auto: v })} />,
    },
    {
      key: 'assurance_bonus_malus',
      visible: secteurs.includes('assurances') && Boolean(depenses.assurance_auto),
      content: (
        <div>
          <label className="mb-1 block text-lg font-semibold text-slate-900">
            Bonus/malus assurance auto (optionnel)
          </label>
          <input
            type="text"
            inputMode="decimal"
            value={bonusMalusAuto}
            onChange={(e) => setBonusMalusAuto(e.target.value)}
            placeholder="Ex : 0.85"
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
          />
        </div>
      ),
    },
    {
      key: 'depense_assurance_habitation',
      visible: secteurs.includes('assurances'),
      content: <MoneyInput label="Assurance habitation — combien payez-vous par mois ?" value={depenses.assurance_habitation}
        onChange={(v) => setDepenses({ ...depenses, assurance_habitation: v })} />,
    },
    {
      key: 'depense_assurance_sante',
      visible: secteurs.includes('assurances'),
      content: <MoneyInput label="Mutuelle santé — combien payez-vous par mois ?" value={depenses.assurance_sante}
        onChange={(v) => setDepenses({ ...depenses, assurance_sante: v })} />,
    },
    {
      key: 'mobile_nb_lignes',
      visible: mobilePertinent,
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Combien de lignes mobiles à optimiser ?</h3>
          <div className="grid grid-cols-2 gap-2">
            {NB_LIGNES_MOBILES.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const nouveau = nbLignesMobiles === opt ? '' : opt;
                  setNbLignesMobiles(nouveau);
                  if (nouveau) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2 text-sm font-medium transition-all ${
                  nbLignesMobiles === opt
                    ? 'border-sky-600 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: 'mobile_operateur',
      visible: mobilePertinent,
      content: (
        <SelectOperateur
          label="Opérateur mobile actuel (optionnel)"
          options={OPERATEURS_MOBILE}
          value={operateurMobile}
          onChange={setOperateurMobile}
        />
      ),
    },
    {
      key: 'mobile_conso_data',
      visible: mobilePertinent,
      content: (
        <div>
          <label className="mb-1 block text-lg font-semibold text-slate-900">
            Consommation data mensuelle (optionnel)
          </label>
          <div className="relative">
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={1000}
              value={consoDataGo}
              onChange={(e) => setConsoDataGo(e.target.value ? Number(e.target.value) : '')}
              placeholder="20 (moyenne nationale)"
              className="w-full rounded-lg border border-slate-300 py-3 pl-4 pr-12 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
            />
            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-slate-500">Go</span>
          </div>
        </div>
      ),
    },
    {
      key: 'mobile_roaming_europe',
      visible: mobilePertinent,
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Voyagez-vous en Europe ?</h3>
          <div className="grid grid-cols-3 gap-2">
            {ROAMING_OPTIONS.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const nouveau = roamingEurope === opt ? '' : opt;
                  setRoamingEurope(nouveau);
                  if (nouveau) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2 text-xs font-medium transition-all sm:text-sm ${
                  roamingEurope === opt
                    ? 'border-sky-600 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: 'mobile_roaming_monde',
      visible: mobilePertinent && roamingEurope !== '',
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">Voyagez-vous dans le monde (hors Europe) ?</h3>
          <div className="grid grid-cols-3 gap-2">
            {ROAMING_OPTIONS.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  const nouveau = roamingMonde === opt ? '' : opt;
                  setRoamingMonde(nouveau);
                  if (nouveau) avancerSousEtape();
                }}
                className={`rounded-lg border-2 px-2 py-2 text-xs font-medium transition-all sm:text-sm ${
                  roamingMonde === opt
                    ? 'border-sky-600 bg-sky-50 text-sky-900'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: 'tranche_age',
      visible: true,
      content: (
        <div>
          <h3 className="mb-4 text-lg font-semibold text-slate-900">
            Votre tranche d'âge (pour comparer avec des clients similaires)
          </h3>
          <div className="grid grid-cols-3 gap-2">
            {TRANCHES_AGE.map((tr) => (
              <button
                key={tr}
                type="button"
                onClick={() => setTrancheAge((prev) => (prev === tr ? '' : tr))}
                className={`rounded-lg border-2 px-2 py-2.5 text-sm font-medium transition-all ${
                  trancheAge === tr
                    ? 'border-sky-600 bg-sky-600 text-white'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                }`}
              >
                {tr}
              </button>
            ))}
          </div>
        </div>
      ),
    },
  ];

  const questionsEtape2Visibles = questionsEtape2.filter((q) => q.visible);
  const subStepClamped = Math.min(subStep, questionsEtape2Visibles.length - 1);
  const questionActuelle = questionsEtape2Visibles[subStepClamped];

  const toggleSecteur = (key: string) => {
    setSecteurs((prev) => {
      const next = prev.includes(key) ? prev.filter((s) => s !== key) : [...prev, key];
      if (key === 'telecom' && prev.includes('telecom')) setTelecomChoix('');
      return next;
    });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/leads/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prenom: prenom.trim(),
          telephone: telephone.trim(),
          email: email.trim() || undefined,
          tranche_age: trancheAge || undefined,
          depenses,
          operateur_mobile: operateurMobile.trim() || undefined,
          operateur_box: operateurBox.trim() || undefined,
          offre_box: offreBox || undefined,
          debit_box: typeof debitBox === 'number' ? debitBox : undefined,
          fournisseur_energie: fournisseurEnergie.trim() || undefined,
          conso_data_go: typeof consoDataGo === 'number' ? consoDataGo : undefined,
          roaming_europe: roamingEurope || undefined,
          roaming_hors_ue: roamingMonde || undefined,
          bonus_malus_auto: bonusMalusAuto.trim() || undefined,
          plage_horaire_rappel: [jourRappel, plageHoraire].filter(Boolean).join(' · ') || undefined,
          objectif_principal: objectifPrincipal || undefined,
          adresse: adresseSuggestion
            ? {
                label: adresseTexte || undefined,
                code_postal: adresseSuggestion.code_postal,
                ville: adresseSuggestion.ville,
                code_insee: adresseSuggestion.code_insee,
                latitude: adresseSuggestion.latitude,
                longitude: adresseSuggestion.longitude,
              }
            : undefined,
          nb_lignes_mobiles: nbLignesMobiles || undefined,
          chauffage_principal: chauffagePrincipal || undefined,
          puissance_kva: puissanceKva || undefined,
          gros_equipement_electrique: grosEquipementElectrique ?? undefined,
          option_tarifaire: optionTarifaire || undefined,
          usage_tv: usageTv || undefined,
          abonnements_payants:
            [...abonnementsSelection, abonnementAutre.trim()].filter(Boolean).join(', ') || undefined,
          consentement_rgpd: consentement,
          consentement_demarchage: consentementDemarchage,
          utm,
          touchpoints: getStoredTouchpoints(),
          turnstile_token: turnstileToken || undefined,
          hp_field: hpField,
        }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        const msg =
          typeof errBody.detail === 'string'
            ? errBody.detail
            : Array.isArray(errBody.detail)
              ? errBody.detail.map((d: any) => d.msg).join(' · ')
              : `Erreur ${res.status}`;
        throw new Error(msg);
      }
      const data: EstimationResp = await res.json();
      setResult(data);
      setStep(4);
      firePixel('Lead', {
        value: data.estimation.economie_annuelle_totale_typique,
        currency: 'EUR',
      });
      firePixel('CompleteRegistration', {
        value: data.estimation.economie_annuelle_totale_typique,
        currency: 'EUR',
      });
      try {
        localStorage.removeItem('ia_utm');
      } catch {}
      reinitialiserTouchpoints();
    } catch (err: any) {
      setError(err.message || 'Une erreur est survenue. Réessayez dans un instant.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {step < 4 && (
        <div className="mb-6">
          <div className="mb-2 flex justify-between text-xs font-medium text-slate-500">
            <span>
              Étape {step}/3
              {step === 2 && ` · question ${subStepClamped + 1}/${questionsEtape2Visibles.length}`}
            </span>
            <span>{Math.round((step / 3) * 100)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full bg-sky-600 transition-all duration-500"
              style={{ width: `${(step / 3) * 100}%` }}
            />
          </div>
          {step === 2 && (
            <div className="mt-1 h-1 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full bg-sky-300 transition-all duration-300"
                style={{
                  width: `${questionsEtape2Visibles.length > 0 ? ((subStepClamped + 1) / questionsEtape2Visibles.length) * 100 : 0}%`,
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Honeypot invisible */}
      <input
        type="text"
        name="website"
        tabIndex={-1}
        autoComplete="off"
        value={hpField}
        onChange={(e) => setHpField(e.target.value)}
        style={{ position: 'absolute', left: '-9999px', width: 1, height: 1, opacity: 0 }}
        aria-hidden="true"
      />

      {step === 1 && (
        <div>
          <h2 className="mb-4 text-xl font-bold text-slate-900">Sur quoi voulez-vous économiser ?</h2>
          <p className="mb-6 text-sm text-slate-600">
            Sélectionnez tout ce qui vous concerne (plusieurs choix possibles).
          </p>
          <div className="grid gap-3">
            {SECTEURS.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => toggleSecteur(s.key)}
                className={`flex items-center justify-between rounded-xl border-2 p-4 text-left transition-all ${
                  secteurs.includes(s.key)
                    ? 'border-sky-600 bg-sky-50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <span className="text-lg font-medium text-slate-900">{s.label}</span>
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full border-2 text-sm ${
                    secteurs.includes(s.key)
                      ? 'border-sky-600 bg-sky-600 text-white'
                      : 'border-slate-300'
                  }`}
                >
                  {secteurs.includes(s.key) && '✓'}
                </span>
              </button>
            ))}
          </div>

          {secteurs.includes('telecom') && (
            <div className="mt-4 rounded-xl border-2 border-sky-100 bg-sky-50/60 p-4">
              <p className="mb-3 text-sm font-medium text-slate-700">
                Télécom : qu'est-ce qui vous intéresse ?
              </p>
              <div className="grid grid-cols-3 gap-2">
                {TELECOM_CHOIX.map((opt) => (
                  <button
                    key={opt.key}
                    type="button"
                    onClick={() => setTelecomChoix(opt.key)}
                    className={`rounded-lg border-2 px-2 py-2.5 text-sm font-medium transition-all ${
                      telecomChoix === opt.key
                        ? 'border-sky-600 bg-sky-600 text-white'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <button
            type="button"
            disabled={!canGoStep2}
            onClick={() => {
              setSubStep(0);
              setStep(2);
            }}
            className="mt-6 w-full rounded-xl bg-sky-600 py-4 text-lg font-semibold text-white transition-opacity hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Continuer →
          </button>
        </div>
      )}

      {step === 2 && questionActuelle && (
        <div>
          <QuestionSlide slideKey={questionActuelle.key}>
            {questionActuelle.content}
          </QuestionSlide>

          <div className="mt-6 flex gap-3">
            <button
              type="button"
              onClick={reculerSousEtape}
              className="rounded-xl border border-slate-300 px-4 py-3 text-slate-600 hover:bg-slate-50"
            >
              ← Retour
            </button>
            {subStepClamped === questionsEtape2Visibles.length - 1 ? (
              <button
                type="button"
                disabled={!canGoStep3}
                onClick={() => setStep(3)}
                className="flex-1 rounded-xl bg-sky-600 py-4 text-lg font-semibold text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Voir mon estimation →
              </button>
            ) : (
              <button
                type="button"
                onClick={avancerSousEtape}
                className="flex-1 rounded-xl bg-sky-600 py-4 text-lg font-semibold text-white hover:bg-sky-700"
              >
                Suivant →
              </button>
            )}
          </div>
        </div>
      )}

      {step === 3 && (
        <form onSubmit={submit}>
          <h2 className="mb-4 text-xl font-bold text-slate-900">Où on vous rappelle avec votre estimation ?</h2>
          <p className="mb-6 text-sm text-slate-600">
            Un conseiller vous appelle sous 24h — pas de bot, pas de spam.
          </p>

          <div className="space-y-3">
            <FieldInput label="Prénom *" value={prenom} onChange={setPrenom}
              type="text" autoComplete="given-name" required />
            <FieldInput label="Téléphone mobile *" value={telephone} onChange={setTelephone}
              type="tel" autoComplete="tel" placeholder="06 12 34 56 78" required />
            <FieldInput label="Email (optionnel — pour recevoir le récap)"
              value={email} onChange={setEmail} type="email" autoComplete="email" />
          </div>

          <div className="mt-4">
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Quand préférez-vous être rappelé ? (optionnel)
            </label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {JOURS_RAPPEL.map((jour) => (
                <button
                  key={jour}
                  type="button"
                  onClick={() => setJourRappel((prev) => (prev === jour ? '' : jour))}
                  className={`rounded-lg border-2 px-3 py-2 text-sm font-medium transition-all ${
                    jourRappel === jour
                      ? 'border-sky-600 bg-sky-50 text-sky-900'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                  }`}
                >
                  {jour}
                </button>
              ))}
            </div>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
              {PLAGES_HORAIRES.map((plage) => (
                <button
                  key={plage}
                  type="button"
                  onClick={() => setPlageHoraire((prev) => (prev === plage ? '' : plage))}
                  className={`rounded-lg border-2 px-3 py-2 text-sm font-medium transition-all ${
                    plageHoraire === plage
                      ? 'border-sky-600 bg-sky-50 text-sky-900'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                  }`}
                >
                  {plage}
                </button>
              ))}
            </div>
          </div>

          <TurnstileWidget onToken={handleTurnstileToken} />

          <div className="mt-6 space-y-3 rounded-lg bg-slate-50 p-4">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={consentement}
                onChange={(e) => setConsentement(e.target.checked)}
                className="mt-1 h-5 w-5 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                required
              />
              <span className="text-sm text-slate-700">
                J'accepte que mes données soient utilisées par IA Conseil pour me recontacter et
                calculer mon estimation. <strong>Aucune revente à des tiers.</strong> *
              </span>
            </label>
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={consentementDemarchage}
                onChange={(e) => setConsentementDemarchage(e.target.checked)}
                className="mt-1 h-5 w-5 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
              />
              <span className="text-sm text-slate-700">
                J'accepte d'être recontacté(e) par téléphone pour des offres commerciales adaptées à
                mon profil.
              </span>
            </label>
          </div>

          {error && (
            <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
          )}

          <div className="mt-6 flex gap-3">
            <button
              type="button"
              onClick={() => {
                setSubStep(questionsEtape2Visibles.length - 1);
                setStep(2);
              }}
              className="rounded-xl border border-slate-300 px-4 py-3 text-slate-600 hover:bg-slate-50"
            >
              ← Retour
            </button>
            <button
              type="submit"
              disabled={!canSubmit || loading}
              className="flex-1 rounded-xl bg-emerald-600 py-4 text-lg font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? 'Calcul en cours…' : ctaFinalLabel}
            </button>
          </div>
        </form>
      )}

      {step === 4 && result && (
        <div className="text-center">
          <div className="mb-4 text-5xl">🎉</div>
          <h2 className="mb-2 text-2xl font-bold text-slate-900">{prenom}, voici votre estimation</h2>
          <p className="mb-6 text-sm text-slate-600">Référence : {result.ref}</p>

          <div className="mb-6 rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-700 p-6 text-white">
            <div className="text-sm uppercase tracking-wide opacity-90">
              Économie annuelle estimée
            </div>
            <div className="my-2 text-5xl font-bold">
              {Math.round(result.estimation.economie_annuelle_totale_typique)}€
            </div>
            <div className="text-sm opacity-90">
              (fourchette : {Math.round(result.estimation.economie_annuelle_totale_basse)}€ à{' '}
              {Math.round(result.estimation.economie_annuelle_totale_haute)}€ / an)
            </div>
          </div>

          <div className="mb-6 space-y-2 text-left">
            {result.estimation.lignes
              .filter((l) => l.economie_annuelle_typique > 0)
              .map((l) => (
                <div
                  key={l.categorie}
                  className="flex items-center justify-between rounded-lg bg-slate-50 p-3"
                >
                  <div>
                    <div className="font-medium text-slate-900">{l.categorie}</div>
                    <div className="text-xs text-slate-500">
                      Vous : {l.cout_actuel_mensuel}€/mois · Nos clients : {l.notre_moyenne_mensuel}
                      €/mois
                    </div>
                  </div>
                  <div className="font-bold text-emerald-600">
                    -{Math.round(l.economie_annuelle_typique)}€/an
                  </div>
                </div>
              ))}
          </div>

          <div className="rounded-xl bg-sky-50 p-4 text-left">
            <p className="text-sm text-slate-700">
              <strong>📞 {result.message}</strong>
            </p>
          </div>

          {result.fibre.disponible && (
            <div className="mt-4 rounded-xl bg-emerald-50 p-4 text-left">
              <p className="text-sm text-emerald-800">
                <strong>🚀 Fibre disponible dans votre commune</strong>
                {result.fibre.taux_couverture != null && (
                  <> — {Math.round(result.fibre.taux_couverture * 100)}% des logements raccordés.</>
                )}
              </p>
            </div>
          )}

          {calBookingEnabled() && (
            <button
              type="button"
              onClick={() => {
                firePixel('Schedule');
                setShowBooking(true);
              }}
              className="mt-4 w-full rounded-xl bg-sky-600 py-4 text-lg font-semibold text-white transition-opacity hover:bg-sky-700"
            >
              Choisir un créneau maintenant 📅
            </button>
          )}

          <p className="mt-6 text-xs text-slate-500">
            Estimation calculée sur la médiane payée par nos clients dans la même catégorie et
            tranche d'âge. Économie réelle variable selon votre situation exacte.
          </p>

          {showBooking && (
            <CalBooking
              prenom={prenom}
              telephone={telephone}
              email={email}
              onClose={() => setShowBooking(false)}
            />
          )}
        </div>
      )}
    </div>
  );
}

// Enveloppe une sous-question de l'étape 2 avec une transition fondu +
// léger glissement à chaque changement de `slideKey` (sans démonter le
// contenu — juste un aller-retour opacity/translate piloté par CSS) : donne
// l'effet "une question à la fois" façon Typeform sans dépendance externe.
function QuestionSlide({ slideKey, children }: { slideKey: string; children: ReactNode }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(false);
    const frame = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(frame);
  }, [slideKey]);

  return (
    <div
      className={`transition-all duration-300 ease-out ${
        visible ? 'translate-x-0 opacity-100' : 'translate-x-2 opacity-0'
      }`}
    >
      {children}
    </div>
  );
}

function MoneyInput({
  label, value, onChange,
}: {
  label: string;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
}) {
  return (
    <div>
      <label className="mb-3 block text-lg font-semibold text-slate-900">{label}</label>
      <div className="relative">
        <input
          type="number"
          inputMode="decimal"
          min={0}
          step={0.01}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
          placeholder="0"
          className="w-full rounded-lg border border-slate-300 py-3 pl-4 pr-16 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
        />
        <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-slate-500">
          €/mois
        </span>
      </div>
    </div>
  );
}

// Menu déroulant "opérateur" avec option "Autre" qui révèle un champ texte
// libre — même liste réutilisable pour mobile et box (valeurs différentes).
function SelectOperateur({
  label, options, value, onChange,
}: {
  label: string;
  options: readonly string[];
  value: string;
  onChange: (v: string) => void;
}) {
  const [modeAutre, setModeAutre] = useState(() => value !== '' && !options.includes(value));

  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <select
        value={modeAutre ? 'Autre' : value}
        onChange={(e) => {
          if (e.target.value === 'Autre') {
            setModeAutre(true);
            onChange('');
          } else {
            setModeAutre(false);
            onChange(e.target.value);
          }
        }}
        className="w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
      >
        <option value="">Sélectionner…</option>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
        <option value="Autre">Autre</option>
      </select>
      {modeAutre && (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Précisez l'opérateur…"
          className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
        />
      )}
    </div>
  );
}

// Menu déroulant multi-choix (B3b) — cases à cocher parmi une liste standard
// + "Autre" en texte libre. Les valeurs sont jointes en une chaîne
// ", "-séparée par l'appelant avant envoi (pas de changement de schéma
// backend, `abonnements_payants` reste une simple chaîne).
function SelectionMultiple({
  label, options, selection, onChangeSelection, autre, onChangeAutre,
}: {
  label: string;
  options: readonly string[];
  selection: string[];
  onChangeSelection: (v: string[]) => void;
  autre: string;
  onChangeAutre: (v: string) => void;
}) {
  const toggle = (option: string) => {
    onChangeSelection(
      selection.includes(option) ? selection.filter((o) => o !== option) : [...selection, option]
    );
  };
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-slate-700">{label}</label>
      <div className="grid grid-cols-2 gap-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => toggle(option)}
            className={`flex items-center gap-2 rounded-lg border-2 px-2 py-2 text-sm font-medium transition-all ${
              selection.includes(option)
                ? 'border-sky-600 bg-sky-50 text-sky-900'
                : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
            }`}
          >
            <span
              className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${
                selection.includes(option) ? 'border-sky-600 bg-sky-600 text-white' : 'border-slate-300'
              }`}
            >
              {selection.includes(option) && '✓'}
            </span>
            {option}
          </button>
        ))}
      </div>
      <input
        type="text"
        value={autre}
        onChange={(e) => onChangeAutre(e.target.value)}
        placeholder="Autre (précisez)…"
        className="mt-2 w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
      />
    </div>
  );
}

function FieldInput({
  label, value, onChange, type, autoComplete, required, placeholder, pattern, maxLength,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type: string;
  autoComplete?: string;
  required?: boolean;
  placeholder?: string;
  pattern?: string;
  maxLength?: number;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
      <input
        type={type}
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        pattern={pattern}
        maxLength={maxLength}
        inputMode={pattern === '[0-9]{5}' ? 'numeric' : undefined}
        className="w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
      />
    </div>
  );
}
