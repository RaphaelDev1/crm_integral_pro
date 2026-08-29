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
import { FormEvent, useCallback, useEffect, useState } from 'react';

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

// Sous-choix télécom (étape 1) — évite de comparer mobile ET box/fibre quand
// une seule des deux intéresse le prospect (étape 2 n'affiche alors que le(s)
// champ(s) pertinent(s)).
const TELECOM_CHOIX = [
  { key: 'mobile', label: '📱 Mobile' },
  { key: 'box', label: '📶 Box / Fibre' },
  { key: 'les_deux', label: '📱📶 Les deux' },
] as const;
type TelecomChoix = (typeof TELECOM_CHOIX)[number]['key'] | '';

// Mêmes libellés/valeurs que la trame mobile conseiller (roaming_ue /
// sensibilite_prix, voir backend/scripts/seed_ia_conseil.py) — posées ici
// pour que le conseiller n'ait plus à les redemander au téléphone.
const ROAMING_OPTIONS = ['Jamais', 'Occasionnellement', 'Souvent'] as const;
const SENSIBILITE_PRIX_OPTIONS = ['Prix avant tout', 'Équilibre', 'Qualité avant tout'] as const;

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

export function EstimationForm({
  variant = 'A',
  ctaFinalLabel = 'Obtenir mon estimation 🎯',
}: {
  variant?: LandingVariant;
  ctaFinalLabel?: string;
}) {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [showBooking, setShowBooking] = useState(false);
  const [secteurs, setSecteurs] = useState<string[]>([]);
  const [telecomChoix, setTelecomChoix] = useState<TelecomChoix>('');
  const [depenses, setDepenses] = useState<Depenses>({});
  const [operateurActuel, setOperateurActuel] = useState('');
  const [consoDataGo, setConsoDataGo] = useState<number | ''>('');
  const [roamingEurope, setRoamingEurope] = useState('');
  const [sensibilitePrix, setSensibilitePrix] = useState('');
  const [age, setAge] = useState<number | ''>('');
  const [bonusMalusAuto, setBonusMalusAuto] = useState('');
  const [prenom, setPrenom] = useState('');
  const [telephone, setTelephone] = useState('');
  const [email, setEmail] = useState('');
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
  const canGoStep3 = Object.values(depenses).some((v) => v && v > 0) && age !== '';
  const canSubmit =
    prenom.trim().length > 0 && TEL_RE.test(telephone.trim()) && consentement;

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
          age: typeof age === 'number' ? age : undefined,
          depenses,
          operateur_actuel: operateurActuel.trim() || undefined,
          conso_data_go: typeof consoDataGo === 'number' ? consoDataGo : undefined,
          roaming_europe: roamingEurope || undefined,
          sensibilite_prix: sensibilitePrix || undefined,
          bonus_malus_auto: bonusMalusAuto.trim() || undefined,
          plage_horaire_rappel: plageHoraire || undefined,
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
            <span>Étape {step}/3</span>
            <span>{Math.round((step / 3) * 100)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full bg-sky-600 transition-all duration-500"
              style={{ width: `${(step / 3) * 100}%` }}
            />
          </div>
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
            onClick={() => setStep(2)}
            className="mt-6 w-full rounded-xl bg-sky-600 py-4 text-lg font-semibold text-white transition-opacity hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Continuer →
          </button>
        </div>
      )}

      {step === 2 && (
        <div>
          <h2 className="mb-4 text-xl font-bold text-slate-900">Combien payez-vous aujourd'hui ?</h2>
          <p className="mb-6 text-sm text-slate-600">
            Une estimation suffit — on affinera au téléphone.
          </p>

          <div className="space-y-3">
            {mobilePertinent && (
              <MoneyInput label="Forfait mobile" value={depenses.mobile}
                onChange={(v) => setDepenses({ ...depenses, mobile: v })} />
            )}
            {boxPertinent && (
              <MoneyInput label="Box / Fibre" value={depenses.box_fibre}
                onChange={(v) => setDepenses({ ...depenses, box_fibre: v })} />
            )}
            {secteurs.includes('energie') && (
              <>
                <MoneyInput label="Électricité" value={depenses.electricite}
                  onChange={(v) => setDepenses({ ...depenses, electricite: v })} />
                <MoneyInput label="Gaz" value={depenses.gaz}
                  onChange={(v) => setDepenses({ ...depenses, gaz: v })} />
              </>
            )}
            {secteurs.includes('assurances') && (
              <>
                <MoneyInput label="Assurance auto" value={depenses.assurance_auto}
                  onChange={(v) => setDepenses({ ...depenses, assurance_auto: v })} />
                {depenses.assurance_auto ? (
                  <div>
                    <label className="mb-1 block text-sm font-medium text-slate-700">
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
                ) : null}
                <MoneyInput label="Assurance habitation" value={depenses.assurance_habitation}
                  onChange={(v) => setDepenses({ ...depenses, assurance_habitation: v })} />
                <MoneyInput label="Mutuelle santé" value={depenses.assurance_sante}
                  onChange={(v) => setDepenses({ ...depenses, assurance_sante: v })} />
              </>
            )}
          </div>

          {mobilePertinent && (
            <div className="mt-6 space-y-4 rounded-xl border-2 border-sky-100 bg-sky-50/60 p-4">
              <p className="text-sm font-medium text-slate-700">
                Quelques infos en plus — pour que le conseiller ne vous les redemande pas au téléphone.
              </p>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Opérateur mobile actuel (optionnel)
                </label>
                <input
                  type="text"
                  value={operateurActuel}
                  onChange={(e) => setOperateurActuel(e.target.value)}
                  placeholder="Ex : Orange, SFR, Free…"
                  className="w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
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
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-slate-500">
                    Go
                  </span>
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Voyagez-vous en Europe ?
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {ROAMING_OPTIONS.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => setRoamingEurope((prev) => (prev === opt ? '' : opt))}
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

              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">
                  Ce qui compte le plus pour vous ?
                </label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {SENSIBILITE_PRIX_OPTIONS.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => setSensibilitePrix((prev) => (prev === opt ? '' : opt))}
                      className={`rounded-lg border-2 px-2 py-2 text-xs font-medium transition-all sm:text-sm ${
                        sensibilitePrix === opt
                          ? 'border-sky-600 bg-sky-50 text-sky-900'
                          : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="mt-6">
            <label className="mb-2 block text-sm font-medium text-slate-700">
              Votre âge (pour comparer avec des clients similaires)
            </label>
            <input
              type="number"
              inputMode="numeric"
              min={18}
              max={120}
              value={age}
              onChange={(e) => setAge(e.target.value ? Number(e.target.value) : '')}
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
              placeholder="35"
            />
          </div>

          <div className="mt-6 flex gap-3">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="rounded-xl border border-slate-300 px-4 py-3 text-slate-600 hover:bg-slate-50"
            >
              ← Retour
            </button>
            <button
              type="button"
              disabled={!canGoStep3}
              onClick={() => setStep(3)}
              className="flex-1 rounded-xl bg-sky-600 py-4 text-lg font-semibold text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Voir mon estimation →
            </button>
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
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
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
              onClick={() => setStep(2)}
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

function MoneyInput({
  label, value, onChange,
}: {
  label: string;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
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
