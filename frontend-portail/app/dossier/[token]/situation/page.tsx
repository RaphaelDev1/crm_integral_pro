"use client";

import { ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ContratTelecom,
  getContexte,
  getContratsTelecom,
  soumettreSituationActuelle,
  TokenContexte,
} from "@/lib/api";
import { ArrowLeft, CheckCircle2, Loader2, Wifi } from "lucide-react";

// Mêmes libellés que frontend-conseiller/lib/diagnosticConstants.ts — dupliqués
// ici car frontend-portail est une app Next indépendante (pas de package
// partagé entre les deux frontends).
const LISTE_OPERATEURS_TEL = ["Orange", "YouPrice (Réseau Orange)", "SFR", "Bouygues", "Free", "Autre / Aucun"];
const SATISFACTION_RESEAU = ["😀 Très content", "😐 Ça va", "😡 Pas du tout"];
const VEUT_RESTER_OPTIONS = ["Oui", "Pas spécialement", "Non"];
const NIVEAUX_DEFAUT_TECHNIQUE = ["Aucun signalé", "Faible", "Moyen", "Critique"];

// Trame mobile (docs/QUESTIONS_PAR_SECTEUR.md) — mêmes libellés que
// components/landing/EstimationForm.tsx (landing /economiser) pour la partie
// socle (S5/M1), afin qu'un prospect qui répond aux deux endroits voie les
// mêmes questions/choix.
const OBJECTIFS_PRINCIPAUX = [
  { valeur: "economiser", label: "💰 Économiser" },
  { valeur: "simplifier", label: "✨ Simplifier" },
  { valeur: "ameliorer_qualite", label: "🚀 Améliorer la qualité" },
  { valeur: "regrouper", label: "📦 Tout regrouper" },
];
const NB_LIGNES_MOBILES = ["1", "2+"];
const CONSERVER_NUMERO_OPTIONS = [
  { valeur: "oui", label: "Oui, je garde mon numéro" },
  { valeur: "non", label: "Non, nouveau numéro" },
];
const TYPE_SIM_OPTIONS = [
  { valeur: "esim", label: "eSIM" },
  { valeur: "carte_sim", label: "Carte SIM" },
];
const AIDE_RIO = "Pour obtenir votre RIO, appelez gratuitement le 3179 depuis le téléphone dont vous souhaitez porter le numéro.";

// Trame Box + Énergie (docs/QUESTIONS_PAR_SECTEUR.md) — mêmes libellés/valeurs
// que frontend-portail/components/landing/EstimationForm.tsx (capture initiale
// sur la landing /economiser), pour qu'un prospect qui répond aux deux
// endroits voie des choix cohérents.
const USAGES_TV = ["Jamais, uniquement streaming", "Quelques chaînes", "Bouquet premium"];
const CHAUFFAGES_PRINCIPAUX = ["Électrique", "Gaz", "Bois / fioul / PAC", "Chauffage collectif inclus"];
const PUISSANCES_KVA = ["3", "6", "9", "12+"];
const OPTIONS_TARIFAIRES = ["Base", "Heures Pleines-Creuses", "Tempo"];
const OUI_NON_OPTIONS = [
  { valeur: "oui", label: "Oui" },
  { valeur: "non", label: "Non" },
];

// Trame Box B4/B5/B6/B7 (docs/QUESTIONS_PAR_SECTEUR.md) — posées uniquement
// sur le lien (jamais sur /economiser, qui reste volontairement courte).
const ABONNEMENTS_PAYANTS_OPTIONS = [
  "Canal+", "beIN Sports", "RMC Sport", "OCS", "Ligue 1+", "Netflix (inclus box)", "Disney+", "Paramount+",
];
const NB_UTILISATEURS_STREAMING = ["1-2", "3+"];
const TELETRAVAIL_OPTIONS = [
  { valeur: "non", label: "Non" },
  { valeur: "oui_occasionnel", label: "Oui, occasionnellement" },
  { valeur: "oui_frequent", label: "Oui, régulièrement" },
];
const INTERET_4G5G_OPTIONS = [
  { valeur: "oui", label: "Oui, intéressé" },
  { valeur: "non", label: "Non" },
  { valeur: "a_voir", label: "À voir avec le conseiller" },
];

// Vocabulaire des lignes mobiles : celui du formulaire conseiller
// ("Forfait mobile") et celui de la landing /economiser ("Mobile") — voir
// backend/routers/portail_public.py::CATEGORIES_CONTRAT_MOBILE. `null`
// (aucun contrat encore enregistré) est traité comme mobile par défaut : le
// backend crée alors la ligne "par défaut" avec cette catégorie, voir
// _contrat_situation_actuelle_prospect.
function estLigneMobile(categorie: string | null): boolean {
  return categorie === null || categorie === "Forfait mobile" || categorie === "Mobile";
}
function estLigneBox(categorie: string | null): boolean {
  return categorie === "Forfait box" || categorie === "Box / Fibre" || categorie === "Pack Box + Mobile";
}
function estLigneEnergie(categorie: string | null): boolean {
  return categorie === "Électricité" || categorie === "Gaz" || categorie === "Énergie électricité" || categorie === "Énergie gaz";
}
// Puissance/option tarifaire (E5/E6) ne concernent que le compteur électrique
// — même logique que backend/routers/leads_public.py (est_electricite).
function estLigneElectricite(categorie: string | null): boolean {
  return categorie === "Électricité" || categorie === "Énergie électricité";
}

type Reponse = {
  operateur: string;
  satisfaction: string;
  veutRester: string;
  defautTechnique: string;
  consommation: string;
  dateFinEngagement: string;
  conserverNumero: string;
  rio: string;
  numeroLigne: string;
  typeSim: string;
  usageTv: string;
  abonnementsSelection: string[];
  abonnementAutre: string;
  chauffagePrincipal: string;
  puissanceKva: string;
  optionTarifaire: string;
  grosEquipementElectrique: string;
  nbUtilisateursStreaming: string;
  usage4k: string;
  teletravail: string;
  interetBox4g5g: string;
  telephoneFixeUtilise: string;
  appelsFixeMensuels: string;
};
const VIDE: Reponse = {
  operateur: "", satisfaction: "", veutRester: "", defautTechnique: "",
  consommation: "", dateFinEngagement: "", conserverNumero: "", rio: "", numeroLigne: "", typeSim: "",
  usageTv: "", abonnementsSelection: [], abonnementAutre: "", chauffagePrincipal: "", puissanceKva: "",
  optionTarifaire: "", grosEquipementElectrique: "",
  nbUtilisateursStreaming: "", usage4k: "", teletravail: "", interetBox4g5g: "",
  telephoneFixeUtilise: "", appelsFixeMensuels: "",
};

// Sépare une chaîne "Canal+, beIN Sports, Autre truc" persistée en options
// connues (cases pré-cochées) + reste en texte libre (champ "Autre") — pour
// pré-remplir SelectionMultiple quand le prospect revient modifier B3b.
function decomposerAbonnements(valeur: string | null | undefined): { selection: string[]; autre: string } {
  if (!valeur) return { selection: [], autre: "" };
  const items = valeur.split(",").map((s) => s.trim()).filter(Boolean);
  const selection = items.filter((i) => ABONNEMENTS_PAYANTS_OPTIONS.includes(i));
  const autre = items.filter((i) => !ABONNEMENTS_PAYANTS_OPTIONS.includes(i)).join(", ");
  return { selection, autre };
}

// Libellé lisible par un client (plutôt que la concaténation technique
// "categorie — fournisseur — nom_offre", ex. "Box / Fibre — Orange — Fibre"
// qui répète l'offre après la catégorie) — même logique dans speedtest/page.tsx.
function libelleLigne(ligne: ContratTelecom): string {
  const operateur = ligne.fournisseur ? ` - ${ligne.fournisseur}` : "";
  if (ligne.categorie === "Mobile") return `Votre forfait mobile${operateur}`;
  if (ligne.categorie === "Box / Fibre") return `Votre box internet${operateur}`;
  return [ligne.categorie, ligne.fournisseur, ligne.nom_offre].filter(Boolean).join(" — ");
}

export default function SituationPage({ params }: { params: { token: string } }) {
  const router = useRouter();
  const [ctx, setCtx] = useState<TokenContexte | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const [contrats, setContrats] = useState<ContratTelecom[]>([]);
  // Une réponse par ligne (mobile/box) — le prospect répond à la satisfaction
  // réseau (et aux autres questions) pour tous ses contrats en une seule
  // fois, plutôt que de devoir revenir une fois par ligne. Clé = id du
  // contrat, ou -1 (voir `lignes` ci-dessous) quand le prospect n'a aucune
  // ligne enregistrée (le backend en crée une par défaut, voir
  // _contrat_situation_actuelle_prospect).
  const [reponses, setReponses] = useState<Record<string, Reponse>>({});
  // Le lien reste utilisable à tout moment pour corriger ses réponses (ex.
  // changement d'opérateur entre-temps) — `editing` bascule vers le
  // formulaire pré-rempli avec les valeurs déjà enregistrées sur les
  // contrats (voir ContratTelecom.satisfaction_reseau/veut_rester/
  // defaut_technique, exposés par GET /contrats-telecom).
  const [editing, setEditing] = useState(false);
  // Socle de la trame mobile (S5/M1, docs/QUESTIONS_PAR_SECTEUR.md) — posé
  // une seule fois pour la personne, pas par ligne (voir
  // TokenContexte.objectif_principal/nb_lignes_mobiles).
  const [objectifPrincipal, setObjectifPrincipal] = useState("");
  const [nbLignesMobiles, setNbLignesMobiles] = useState("");
  // Identité (requise par la page "informations personnelles" du tunnel de
  // souscription Free Mobile, voir souscription_engine.py) — socle, posée une
  // seule fois pour la personne, pas par ligne.
  const [dateNaissance, setDateNaissance] = useState("");
  const [departementNaissance, setDepartementNaissance] = useState("");
  const [villeNaissance, setVilleNaissance] = useState("");
  // Champs déjà répondus (sur /economiser ou une précédente visite du lien)
  // qu'on ne repose pas — affichés en tableau récap plutôt qu'en question
  // active, sauf si le prospect clique "Modifier". Clé : "socle:<champ>" pour
  // le socle, "<idLigne>:<champ>" par ligne — voir clePourRecap ci-dessous.
  const [champsEnEdition, setChampsEnEdition] = useState<Set<string>>(new Set());
  const activerEdition = (cle: string) =>
    setChampsEnEdition((prev) => {
      const next = new Set(prev);
      next.add(cle);
      return next;
    });

  useEffect(() => {
    getContexte(params.token)
      .then((c) => {
        setCtx(c);
        setObjectifPrincipal(c.objectif_principal ?? "");
        setNbLignesMobiles(c.nb_lignes_mobiles ?? "");
        setDateNaissance(c.date_naissance ?? "");
        setDepartementNaissance(c.departement_naissance ?? "");
        setVilleNaissance(c.ville_naissance ?? "");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // Best-effort, comme dans speedtest/page.tsx : si le lien ne permet pas
    // de lister les contrats, le formulaire reste utilisable sans sélecteur.
    getContratsTelecom(params.token, { avecEnergie: true })
      .then((liste) => {
        setContrats(liste);
        setReponses((prev) => {
          const next = { ...prev };
          for (const c of liste) {
            if (next[c.id]) continue;
            const { selection, autre } = decomposerAbonnements(c.abonnements_payants);
            next[c.id] = {
              operateur: "",
              satisfaction: c.satisfaction_reseau ?? "",
              veutRester: c.veut_rester ?? "",
              defautTechnique: c.defaut_technique ?? "",
              consommation: c.consommation ?? "",
              dateFinEngagement: c.date_fin_engagement ?? "",
              conserverNumero: c.conserver_numero ?? "",
              rio: c.rio ?? "",
              numeroLigne: c.numero_ligne ?? "",
              typeSim: c.type_sim ?? "",
              usageTv: c.usage_tv ?? "",
              abonnementsSelection: selection,
              abonnementAutre: autre,
              chauffagePrincipal: c.chauffage_principal ?? "",
              puissanceKva: c.puissance_kva ?? "",
              optionTarifaire: c.option_tarifaire ?? "",
              grosEquipementElectrique:
                c.gros_equipement_electrique == null ? "" : c.gros_equipement_electrique ? "oui" : "non",
              nbUtilisateursStreaming: c.nb_utilisateurs_streaming ?? "",
              usage4k: c.usage_4k == null ? "" : c.usage_4k ? "oui" : "non",
              teletravail: c.teletravail ?? "",
              interetBox4g5g: c.interet_box_4g5g ?? "",
              telephoneFixeUtilise: c.telephone_fixe_utilise ?? "",
              appelsFixeMensuels: c.appels_fixe_mensuels ?? "",
            };
          }
          return next;
        });
      })
      .catch(() => {});
  }, [params.token]);

  // Une ligne par contrat existant, ou une ligne "par défaut" s'il n'y en a
  // aucune — unifie le rendu (plus jamais de sélecteur "Cette situation
  // concerne", qui redemandait un opérateur déjà connu par ce choix).
  const lignes: ContratTelecom[] =
    contrats.length > 0 ? contrats : [{ id: -1, categorie: null, fournisseur: null, nom_offre: null }];

  function majReponse(id: number, champ: keyof Omit<Reponse, "abonnementsSelection">, valeur: string) {
    setReponses((prev) => ({ ...prev, [id]: { ...VIDE, ...prev[id], [champ]: valeur } }));
  }

  function majReponseListe(id: number, champ: "abonnementsSelection", valeur: string[]) {
    setReponses((prev) => ({ ...prev, [id]: { ...VIDE, ...prev[id], [champ]: valeur } }));
  }

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      await Promise.all(
        lignes.map((ligne, index) => {
          const r = reponses[ligne.id] ?? VIDE;
          const mobile = estLigneMobile(ligne.categorie);
          const box = estLigneBox(ligne.categorie);
          const energie = estLigneEnergie(ligne.categorie);
          const electricite = estLigneElectricite(ligne.categorie);
          return soumettreSituationActuelle(params.token, {
            operateur_actuel: ligne.fournisseur ? undefined : r.operateur || undefined,
            satisfaction_reseau: r.satisfaction || undefined,
            veut_rester: r.veutRester || undefined,
            defaut_technique: r.defautTechnique || undefined,
            contrat_id: ligne.id > 0 ? ligne.id : undefined,
            consommation: r.consommation || undefined,
            date_fin_engagement: r.dateFinEngagement || undefined,
            conserver_numero: mobile ? r.conserverNumero || undefined : undefined,
            rio: mobile && r.conserverNumero === "oui" ? r.rio || undefined : undefined,
            numero_ligne: mobile && r.conserverNumero === "oui" ? r.numeroLigne || undefined : undefined,
            type_sim: mobile ? r.typeSim || undefined : undefined,
            usage_tv: box ? r.usageTv || undefined : undefined,
            abonnements_payants:
              box && r.usageTv !== "Jamais, uniquement streaming"
                ? [...r.abonnementsSelection, r.abonnementAutre.trim()].filter(Boolean).join(", ") || undefined
                : undefined,
            nb_utilisateurs_streaming: box ? r.nbUtilisateursStreaming || undefined : undefined,
            usage_4k: box && r.usage4k ? r.usage4k === "oui" : undefined,
            teletravail: box ? r.teletravail || undefined : undefined,
            interet_box_4g5g: box ? r.interetBox4g5g || undefined : undefined,
            telephone_fixe_utilise: box ? r.telephoneFixeUtilise || undefined : undefined,
            appels_fixe_mensuels:
              box && r.telephoneFixeUtilise === "oui" ? r.appelsFixeMensuels || undefined : undefined,
            chauffage_principal: energie ? r.chauffagePrincipal || undefined : undefined,
            puissance_kva: electricite ? r.puissanceKva || undefined : undefined,
            option_tarifaire: electricite ? r.optionTarifaire || undefined : undefined,
            gros_equipement_electrique:
              electricite && (r.puissanceKva === "9" || r.puissanceKva === "12+")
                ? r.grosEquipementElectrique === "oui"
                : undefined,
            // Socle (posé une seule fois) : envoyé avec la première ligne
            // seulement, le backend le route vers Prospect quelle que soit
            // la ligne ciblée par cette requête (voir CHAMPS_SOCLE_PROSPECT).
            objectif_principal: index === 0 ? objectifPrincipal || undefined : undefined,
            nb_lignes_mobiles: index === 0 ? nbLignesMobiles || undefined : undefined,
            date_naissance: index === 0 ? dateNaissance || undefined : undefined,
            departement_naissance: index === 0 ? departementNaissance || undefined : undefined,
            ville_naissance: index === 0 ? villeNaissance || undefined : undefined,
          });
        })
      );
      setDone(true);
      setEditing(false);
      router.refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="text-center py-16"><Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" /></div>;
  if (!ctx) return <div className="text-center py-16 text-danger">Erreur : {error}</div>;
  if (!ctx.peut_renseigner_situation) {
    return (
      <main className="text-center py-16">
        <p className="text-slate-600">Cette action n&apos;est pas disponible sur votre lien.</p>
      </main>
    );
  }

  return (
    <main>
      <button
        onClick={() => router.push(`/dossier/${params.token}`)}
        className="flex items-center gap-2 text-slate-600 mb-6 hover:text-primary"
      >
        <ArrowLeft className="w-4 h-4" /> Retour
      </button>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-xl font-bold text-primary mb-2 flex items-center gap-2">
          <Wifi className="w-5 h-5" /> Votre situation actuelle
        </h2>
        <p className="text-slate-600 text-sm">
          Quelques questions sur votre offre et votre réseau actuels, pour aider votre conseiller à préparer votre dossier.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-danger p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {(done || ctx.situation_renseignee) && !editing ? (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 text-center text-accent">
          <CheckCircle2 className="w-10 h-10 mx-auto mb-3" />
          <p className="font-semibold">Merci, c&apos;est enregistré !</p>
          <p className="text-sm text-slate-600 mt-2">Votre conseiller a bien reçu vos réponses.</p>
          {ctx.peut_transmettre_speedtest && !ctx.speedtest_fait && (
            <>
              <p className="text-sm text-slate-600 mt-4 mb-2">Il reste une dernière étape :</p>
              <button
                onClick={() => router.push(`/dossier/${params.token}/speedtest`)}
                className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90 w-full max-w-xs"
              >
                Tester mon débit (30 secondes) →
              </button>
            </>
          )}
          <button
            onClick={() => setEditing(true)}
            className="mt-4 text-sm font-medium text-primary hover:underline"
          >
            Modifier mes réponses
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
            <p className="text-sm font-semibold text-primary">Pour mieux vous conseiller</p>
            <TableauRecap
              lignes={[
                ctx.objectif_principal && !champsEnEdition.has("socle:objectifPrincipal")
                  ? {
                      cle: "socle:objectifPrincipal",
                      label: "Objectif principal",
                      valeur: OBJECTIFS_PRINCIPAUX.find((o) => o.valeur === ctx.objectif_principal)?.label ?? ctx.objectif_principal,
                      onModifier: () => activerEdition("socle:objectifPrincipal"),
                    }
                  : null,
                ctx.nb_lignes_mobiles && !champsEnEdition.has("socle:nbLignesMobiles")
                  ? {
                      cle: "socle:nbLignesMobiles",
                      label: "Lignes mobiles à optimiser",
                      valeur: ctx.nb_lignes_mobiles,
                      onModifier: () => activerEdition("socle:nbLignesMobiles"),
                    }
                  : null,
                ctx.date_naissance && !champsEnEdition.has("socle:dateNaissance")
                  ? {
                      cle: "socle:dateNaissance",
                      label: "Date de naissance",
                      valeur: ctx.date_naissance,
                      onModifier: () => activerEdition("socle:dateNaissance"),
                    }
                  : null,
                ctx.departement_naissance && !champsEnEdition.has("socle:departementNaissance")
                  ? {
                      cle: "socle:departementNaissance",
                      label: "Département de naissance",
                      valeur: ctx.departement_naissance,
                      onModifier: () => activerEdition("socle:departementNaissance"),
                    }
                  : null,
                ctx.ville_naissance && !champsEnEdition.has("socle:villeNaissance")
                  ? {
                      cle: "socle:villeNaissance",
                      label: "Ville de naissance",
                      valeur: ctx.ville_naissance,
                      onModifier: () => activerEdition("socle:villeNaissance"),
                    }
                  : null,
              ]}
            />
            {(!ctx.objectif_principal || champsEnEdition.has("socle:objectifPrincipal")) && (
              <ChampOptions
                label="Quel est votre objectif principal ?"
                value={objectifPrincipal}
                onChange={setObjectifPrincipal}
                options={OBJECTIFS_PRINCIPAUX}
              />
            )}
            {(!ctx.nb_lignes_mobiles || champsEnEdition.has("socle:nbLignesMobiles")) && (
              <Champ
                label="Combien de lignes mobiles souhaitez-vous optimiser ?"
                value={nbLignesMobiles}
                onChange={setNbLignesMobiles}
                options={NB_LIGNES_MOBILES}
              />
            )}
            {(!ctx.date_naissance || champsEnEdition.has("socle:dateNaissance")) && (
              <ChampTexte
                label="Votre date de naissance"
                placeholder="JJ/MM/AAAA"
                value={dateNaissance}
                onChange={setDateNaissance}
              />
            )}
            {(!ctx.departement_naissance || champsEnEdition.has("socle:departementNaissance")) && (
              <ChampTexte
                label="Votre département de naissance"
                placeholder="ex. 75"
                value={departementNaissance}
                onChange={setDepartementNaissance}
              />
            )}
            {(!ctx.ville_naissance || champsEnEdition.has("socle:villeNaissance")) && (
              <ChampTexte
                label="Votre ville de naissance"
                value={villeNaissance}
                onChange={setVilleNaissance}
              />
            )}
          </div>

          {lignes.map((ligne) => {
            const r = reponses[ligne.id] ?? VIDE;
            const label = libelleLigne(ligne);
            const mobile = estLigneMobile(ligne.categorie);
            const box = estLigneBox(ligne.categorie);
            const energie = estLigneEnergie(ligne.categorie);
            const electricite = estLigneElectricite(ligne.categorie);
            const aUneLigneMobile = lignes.some((l) => estLigneMobile(l.categorie));

            // Ne repose pas une question déjà répondue (sur /economiser ou
            // une visite précédente du lien) : `connu` teste la valeur
            // persistée (`ligne`, pas `r` qui peut contenir une saisie en
            // cours) — si connue et pas en cours de modification, la réponse
            // va dans le tableau récap plutôt que redevenir une question
            // active. `dejaRepondu` réutilise la même clé pour les questions
            // dont la présence dépend d'une autre réponse déjà connue (ex.
            // abonnements dépend de usageTv).
            const enEdition = (champ: string) => champsEnEdition.has(`${ligne.id}:${champ}`);
            const modifier = (champ: string) => activerEdition(`${ligne.id}:${champ}`);
            const connu = (valeur: string | null | undefined, champ: string) =>
              Boolean(valeur) && !enEdition(champ);

            const conserverNumeroEffectif = ligne.conserver_numero || r.conserverNumero;
            const usageTvEffectif = ligne.usage_tv || r.usageTv;
            const telephoneFixeEffectif = ligne.telephone_fixe_utilise || r.telephoneFixeUtilise;
            const puissanceKvaEffectif = ligne.puissance_kva || r.puissanceKva;

            const recap: { cle: string; label: string; valeur: string; onModifier: () => void }[] = [];
            const questions: ReactNode[] = [];
            function ligneChamp(
              champ: string,
              labelChamp: string,
              valeurConnue: string | null | undefined,
              valeurAffichee: string,
              question: ReactNode
            ) {
              if (connu(valeurConnue, champ)) {
                recap.push({ cle: champ, label: labelChamp, valeur: valeurAffichee, onModifier: () => modifier(champ) });
              } else {
                questions.push(<div key={champ}>{question}</div>);
              }
            }

            if (!ligne.fournisseur) {
              ligneChamp("operateur", "Opérateur actuel", null, "",
                <Champ label="Opérateur actuel" value={r.operateur}
                  onChange={(v) => majReponse(ligne.id, "operateur", v)} options={LISTE_OPERATEURS_TEL} />);
            }
            ligneChamp("satisfaction", "Satisfaction réseau", ligne.satisfaction_reseau, ligne.satisfaction_reseau ?? "",
              <Champ label="Satisfaction réseau" value={r.satisfaction}
                onChange={(v) => majReponse(ligne.id, "satisfaction", v)} options={SATISFACTION_RESEAU} />);
            ligneChamp("veutRester", "Souhaitez-vous rester chez votre opérateur actuel ?", ligne.veut_rester, ligne.veut_rester ?? "",
              <Champ label="Souhaitez-vous rester chez votre opérateur actuel ?" value={r.veutRester}
                onChange={(v) => majReponse(ligne.id, "veutRester", v)} options={VEUT_RESTER_OPTIONS} />);
            ligneChamp("defautTechnique", "Défaut technique (coupures, mauvaise couverture...)", ligne.defaut_technique, ligne.defaut_technique ?? "",
              <Champ label="Avez-vous un défaut technique (coupures, mauvaise couverture...) ?" value={r.defautTechnique}
                onChange={(v) => majReponse(ligne.id, "defautTechnique", v)} options={NIVEAUX_DEFAUT_TECHNIQUE} />);
            ligneChamp(
              "consommation",
              mobile ? "Consommation data moyenne" : "Consommation / usage moyen",
              ligne.consommation, ligne.consommation ?? "",
              <ChampTexte
                label={mobile
                  ? "Consommation data moyenne (sur votre facture ou l'appli de votre opérateur), sur les 3 derniers mois"
                  : "Consommation / usage moyen constaté"}
                placeholder={mobile ? "ex. 20 Go" : undefined}
                value={r.consommation}
                onChange={(v) => majReponse(ligne.id, "consommation", v)}
              />
            );
            ligneChamp("dateFinEngagement", "Sous engagement ?", ligne.date_fin_engagement, ligne.date_fin_engagement ?? "",
              <ChampTexte label="Êtes-vous sous engagement ? Jusqu'à quand ?" placeholder="ex. Non, ou jusqu'en mars 2027"
                value={r.dateFinEngagement} onChange={(v) => majReponse(ligne.id, "dateFinEngagement", v)} />);

            if (mobile) {
              ligneChamp(
                "conserverNumero", "Conserver votre numéro actuel ?", ligne.conserver_numero,
                ligne.conserver_numero === "oui" ? "Oui, je garde mon numéro" : ligne.conserver_numero === "non" ? "Non, nouveau numéro" : "",
                <ChampOptions label="Souhaitez-vous conserver votre numéro de téléphone actuel ?" value={r.conserverNumero}
                  onChange={(v) => majReponse(ligne.id, "conserverNumero", v)} options={CONSERVER_NUMERO_OPTIONS} />
              );
              if (conserverNumeroEffectif === "oui") {
                ligneChamp("numeroLigne", "Numéro de ligne à porter", ligne.numero_ligne, ligne.numero_ligne ?? "",
                  <ChampTexte label="Numéro de ligne à porter" value={r.numeroLigne}
                    onChange={(v) => majReponse(ligne.id, "numeroLigne", v)} />);
                ligneChamp("rio", "RIO", ligne.rio, ligne.rio ?? "",
                  <ChampTexte label="RIO (relevé d'identité opérateur)" aide={AIDE_RIO} value={r.rio}
                    onChange={(v) => majReponse(ligne.id, "rio", v)} />);
              }
              ligneChamp("typeSim", "eSIM ou carte SIM ?", ligne.type_sim,
                ligne.type_sim === "esim" ? "eSIM" : ligne.type_sim === "carte_sim" ? "Carte SIM" : "",
                <ChampOptions label="Souhaitez-vous une eSIM ou une carte SIM ?" value={r.typeSim}
                  onChange={(v) => majReponse(ligne.id, "typeSim", v)} options={TYPE_SIM_OPTIONS} />);
            }

            if (box) {
              ligneChamp("usageTv", "Regardez-vous la TV via la box ?", ligne.usage_tv, ligne.usage_tv ?? "",
                <Champ label="Regardez-vous la TV via la box ?" value={r.usageTv}
                  onChange={(v) => majReponse(ligne.id, "usageTv", v)} options={USAGES_TV} />);
              if (usageTvEffectif !== "" && usageTvEffectif !== "Jamais, uniquement streaming") {
                ligneChamp("abonnements", "Abonnements payants en plus", ligne.abonnements_payants, ligne.abonnements_payants ?? "",
                  <SelectionMultiple
                    label="Abonnements payants en plus (optionnel)"
                    options={ABONNEMENTS_PAYANTS_OPTIONS}
                    selection={r.abonnementsSelection}
                    onChangeSelection={(v) => majReponseListe(ligne.id, "abonnementsSelection", v)}
                    autre={r.abonnementAutre}
                    onChangeAutre={(v) => majReponse(ligne.id, "abonnementAutre", v)}
                  />);
              }
              // B4-B7 — questions confort, différées si le prospect remplit
              // seul (redemandées au conseiller à la signature des mandats,
              // voir ctx.remplissage_autonome / prospects/[id]/page.tsx).
              if (!ctx.remplissage_autonome) {
                // B4 — nombre d'utilisateurs simultanés en streaming + 4K.
                ligneChamp("nbUtilisateursStreaming", "Utilisateurs simultanés en streaming", ligne.nb_utilisateurs_streaming, ligne.nb_utilisateurs_streaming ?? "",
                  <Champ label="Combien de personnes utilisent internet en même temps (streaming) ?" value={r.nbUtilisateursStreaming}
                    onChange={(v) => majReponse(ligne.id, "nbUtilisateursStreaming", v)} options={NB_UTILISATEURS_STREAMING} />);
                ligneChamp("usage4k", "Vidéo 4K régulière ?", ligne.usage_4k == null ? null : "répondu",
                  ligne.usage_4k ? "Oui" : "Non",
                  <ChampOptions label="Regardez-vous régulièrement de la vidéo en 4K ?" value={r.usage4k}
                    onChange={(v) => majReponse(ligne.id, "usage4k", v)} options={OUI_NON_OPTIONS} />);
                // B5 — télétravail / fréquence de visios.
                ligneChamp("teletravail", "Télétravail", ligne.teletravail,
                  TELETRAVAIL_OPTIONS.find((o) => o.valeur === ligne.teletravail)?.label ?? "",
                  <ChampOptions label="Télétravaillez-vous ? À quelle fréquence des visios ?" value={r.teletravail}
                    onChange={(v) => majReponse(ligne.id, "teletravail", v)} options={TELETRAVAIL_OPTIONS} />);
                // B6 — box 4G/5G en remplacement, seulement si une ligne mobile existe aussi.
                if (aUneLigneMobile) {
                  const debitConnu = ligne.speed_down ?? ligne.debit_declare ?? null;
                  const contexteAdsl =
                    ligne.nom_offre === "ADSL" && debitConnu != null
                      ? debitConnu < 8
                        ? " (votre débit ADSL mesuré est faible : une box 4G/5G serait probablement plus rapide.)"
                        : debitConnu > 20
                          ? " (votre débit ADSL mesuré est correct pour un usage modéré.)"
                          : ""
                      : "";
                  ligneChamp("interetBox4g5g", "Intérêt box 4G/5G", ligne.interet_box_4g5g,
                    INTERET_4G5G_OPTIONS.find((o) => o.valeur === ligne.interet_box_4g5g)?.label ?? "",
                    <ChampOptions
                      label={`Une box 4G/5G pourrait-elle remplacer votre box actuelle ?${contexteAdsl}`}
                      value={r.interetBox4g5g}
                      onChange={(v) => majReponse(ligne.id, "interetBox4g5g", v)} options={INTERET_4G5G_OPTIONS} />);
                }
                // B7 — téléphone fixe rattaché à la box.
                ligneChamp("telephoneFixeUtilise", "Téléphone fixe utilisé ?", ligne.telephone_fixe_utilise,
                  ligne.telephone_fixe_utilise === "oui" ? "Oui" : ligne.telephone_fixe_utilise === "non" ? "Non" : "",
                  <ChampOptions label="Avez-vous un téléphone fixe rattaché à la box, et l'utilisez-vous pour appeler ?" value={r.telephoneFixeUtilise}
                    onChange={(v) => majReponse(ligne.id, "telephoneFixeUtilise", v)} options={OUI_NON_OPTIONS} />);
                if (telephoneFixeEffectif === "oui") {
                  ligneChamp("appelsFixeMensuels", "Appels fixe par mois", ligne.appels_fixe_mensuels, ligne.appels_fixe_mensuels ?? "",
                    <ChampTexte label="Combien d'appels fixes par mois environ ? Vers l'international ?"
                      placeholder="ex. 10 appels, dont 2 vers l'international"
                      value={r.appelsFixeMensuels} onChange={(v) => majReponse(ligne.id, "appelsFixeMensuels", v)} />);
                }
              }
            }

            if (energie) {
              ligneChamp("chauffagePrincipal", "Chauffage principal", ligne.chauffage_principal, ligne.chauffage_principal ?? "",
                <Champ label="Chauffage principal du logement" value={r.chauffagePrincipal}
                  onChange={(v) => majReponse(ligne.id, "chauffagePrincipal", v)} options={CHAUFFAGES_PRINCIPAUX} />);
              if (electricite) {
                ligneChamp("puissanceKva", "Puissance souscrite", ligne.puissance_kva, ligne.puissance_kva ?? "",
                  <Champ label="Puissance souscrite (kVA — sur votre facture, en haut)" value={r.puissanceKva}
                    onChange={(v) => majReponse(ligne.id, "puissanceKva", v)} options={PUISSANCES_KVA} />);
                if (puissanceKvaEffectif === "9" || puissanceKvaEffectif === "12+") {
                  ligneChamp("grosEquipementElectrique", "Gros équipement électrique", ligne.gros_equipement_electrique == null ? null : "répondu",
                    ligne.gros_equipement_electrique ? "Oui" : "Non",
                    <ChampOptions label="Avez-vous une clim, une piscine, un véhicule électrique ou des plaques induction puissantes ?"
                      value={r.grosEquipementElectrique} onChange={(v) => majReponse(ligne.id, "grosEquipementElectrique", v)} options={OUI_NON_OPTIONS} />);
                }
                ligneChamp("optionTarifaire", "Option tarifaire", ligne.option_tarifaire, ligne.option_tarifaire ?? "",
                  <Champ label="Option tarifaire actuelle" value={r.optionTarifaire}
                    onChange={(v) => majReponse(ligne.id, "optionTarifaire", v)} options={OPTIONS_TARIFAIRES} />);
              }
            }

            return (
              <div key={ligne.id} className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-4">
                {lignes.length > 1 && (
                  <p className="text-sm font-semibold text-primary">{label || "Votre forfait"}</p>
                )}
                <TableauRecap lignes={recap} />
                {questions.length > 0 && <div className="space-y-4">{questions}</div>}
              </div>
            );
          })}

          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full bg-primary text-white py-3 rounded-lg font-semibold hover:bg-primary/90 transition disabled:opacity-50"
          >
            {submitting ? "Envoi..." : editing ? "Mettre à jour mes réponses" : "Envoyer mes réponses"}
          </button>
          {!editing && (
            <button
              onClick={() => router.push(`/dossier/${params.token}`)}
              className="w-full text-center text-sm text-slate-500 hover:text-slate-700 hover:underline"
            >
              Pas maintenant, j&apos;y reviendrai plus tard
            </button>
          )}
        </div>
      )}
    </main>
  );
}

// Récap "ne pas reposer une question déjà répondue" — un tableau propre des
// réponses déjà connues (sur /economiser ou une visite précédente du lien),
// chacune avec un lien "Modifier" pour revenir dessus si besoin. Rien n'est
// affiché si aucune réponse n'est encore connue pour cette ligne.
function TableauRecap({
  lignes,
}: {
  lignes: ({ cle: string; label: string; valeur: string; onModifier: () => void } | null)[];
}) {
  const items = lignes.filter((l): l is { cle: string; label: string; valeur: string; onModifier: () => void } => l !== null);
  if (items.length === 0) return null;
  return (
    <table className="w-full border-separate border-spacing-y-1 text-sm">
      <tbody>
        {items.map((item) => (
          <tr key={item.cle}>
            <td className="py-1.5 pr-3 align-top text-slate-500">{item.label}</td>
            <td className="py-1.5 pr-3 align-top font-medium text-slate-900">{item.valeur || "—"}</td>
            <td className="py-1.5 align-top text-right">
              <button type="button" onClick={item.onModifier} className="text-xs font-medium text-primary hover:underline">
                Modifier
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Menu déroulant multi-choix (B3b) — cases à cocher parmi une liste standard
// + "Autre" en texte libre, valeurs jointes en une chaîne avant envoi (voir
// handleSubmit). Même composant que frontend-portail/components/landing/
// EstimationForm.tsx (pas de package partagé entre les deux frontends).
function SelectionMultiple({
  label, options, selection, onChangeSelection, autre, onChangeAutre,
}: {
  label: string;
  options: string[];
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
      <span className="block text-sm font-medium text-slate-700 mb-1">{label}</span>
      <div className="grid grid-cols-2 gap-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => toggle(option)}
            className={`flex items-center gap-2 rounded-lg border-2 px-2 py-2 text-sm font-medium transition-all ${
              selection.includes(option)
                ? "border-primary bg-primary/5 text-primary"
                : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
            }`}
          >
            <span
              className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${
                selection.includes(option) ? "border-primary bg-primary text-white" : "border-slate-300"
              }`}
            >
              {selection.includes(option) && "✓"}
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
        className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
      />
    </div>
  );
}

function Champ({
  label,
  value,
  onChange,
  options,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-700 mb-1">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
      >
        <option value="">{placeholder ?? "Sélectionner…"}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

// Variante de Champ pour des options dont le libellé affiché diffère de la
// valeur envoyée au backend (ex. "economiser" / "💰 Économiser") — rendue en
// boutons plutôt qu'un <select>, même style que DemarcheCard.tsx.
function ChampOptions({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { valeur: string; label: string }[];
}) {
  return (
    <div>
      <span className="block text-sm font-medium text-slate-700 mb-1">{label}</span>
      <div className="grid grid-cols-2 gap-2">
        {options.map((opt) => (
          <button
            key={opt.valeur}
            type="button"
            onClick={() => onChange(opt.valeur)}
            className={`rounded-lg border-2 px-3 py-2 text-sm font-medium transition-all ${
              value === opt.valeur
                ? "border-primary bg-primary/5 text-primary"
                : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ChampTexte({
  label,
  value,
  onChange,
  placeholder,
  aide,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  aide?: string;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-700 mb-1">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
      />
      {aide && <p className="text-xs text-slate-500 mt-1">{aide}</p>}
    </label>
  );
}
