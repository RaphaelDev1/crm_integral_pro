"use client";

import { Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Champ, ChampSelect } from "@/components/diagnostic/champs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  CATEGORIES_ABONNEMENT,
  GO_OPTIONS,
  LISTE_FOURNISSEURS_ENERGIE,
  LISTE_OPERATEURS_TEL,
  LISTE_TECHNO,
  LISTE_TECHNO_MOBILE,
  matchGoOption,
  matchOperateur,
  NIVEAUX_DEFAUT_TECHNIQUE,
  SATISFACTION_RESEAU,
  VEUT_RESTER_OPTIONS,
} from "@/lib/diagnosticConstants";
import { groupeContrat } from "@/lib/contratsGroupes";
import { useContrats } from "@/lib/hooks/useContrats";
import type { DiagnosticDispatch, DiagnosticState } from "@/lib/hooks/useDiagnosticWizard";
import type { Contrat } from "@/lib/types";

interface EtapeSituationProps {
  state: DiagnosticState;
  dispatch: DiagnosticDispatch;
}

function libelleContrat(c: Contrat): string {
  const parties = [c.fournisseur || "Fournisseur non renseigné", c.categorie].filter(Boolean);
  if (c.cout_mensuel != null) parties.push(`${c.cout_mensuel} €/mois`);
  if (c.consommation) parties.push(c.consommation);
  return parties.join(" — ");
}

// Étape 3 du diagnostic (plan Phase 6.5) — un bloc par univers coché à
// l'étape 1, miroir des champs de src/app.py (étape 3 du wizard Streamlit).
// Préremplit chaque bloc depuis les contrats déjà enregistrés sur la fiche
// (prospect/client) quand une fiche existante a été choisie à l'étape Identité.
export function EtapeSituation({ state, dispatch }: EtapeSituationProps) {
  const { entiteType, entiteId, mode } = state.identite;
  const contratsQuery = useContrats({
    clientId: mode === "existant" && entiteType === "client" && entiteId ? entiteId : undefined,
    prospectId: mode === "existant" && entiteType === "prospect" && entiteId ? entiteId : undefined,
  });
  const contrats = contratsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Situation actuelle du client</h2>
        <p className="text-sm text-muted-foreground">Renseignez les informations pour chaque univers analysé.</p>
      </div>

      {state.univers.includes("Télécom") && (
        <BlocTelecom state={state} dispatch={dispatch} contrats={contrats} />
      )}
      {state.univers.includes("Énergie") && (
        <BlocEnergie state={state} dispatch={dispatch} contrats={contrats} />
      )}
      {state.univers.includes("Abonnements") && (
        <BlocAbonnements state={state} dispatch={dispatch} contrats={contrats} />
      )}
    </div>
  );
}

// `Contrat.date_fin_engagement` est saisi en texte libre "JJ/MM/AAAA"
// (ContratForm.tsx) alors que le champ diagnostic est un <input type="date">
// natif qui attend "AAAA-MM-JJ" — sans conversion le champ resterait vide.
function versDateIso(date: string | null): string {
  const m = (date || "").match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : "";
}

function mapContratVersTelecom(c: Contrat): Partial<DiagnosticState["telecom"]> {
  return {
    // Conserve la ligne d'origine : permet à la finalisation du diagnostic de
    // mettre à jour ce contrat plutôt que d'en créer un nouveau (voir "ligne
    // principale", EtapeRecommandations.tsx).
    contratId: c.id,
    operateurActuel: matchOperateur(c.fournisseur),
    offreActuelle: c.nom_offre || "",
    coutMensuelActuel: c.cout_mensuel ?? 0,
    dataGoMin: matchGoOption(c.consommation),
    finEngagement: versDateIso(c.date_fin_engagement),
    // Déjà éventuellement renseignés par le client lui-même via le lien de
    // collecte (/portail/{token}/situation) — on les reprend plutôt que de
    // laisser le conseiller les redemander à l'oral.
    satisfactionReseau: c.satisfaction_reseau || "",
    veutRester: c.veut_rester || "",
    defautTechnique: c.defaut_technique || "",
    speedDown: c.speed_down ?? 0,
    speedUp: c.speed_up ?? 0,
  };
}

function BlocTelecom({ state, dispatch, contrats }: EtapeSituationProps & { contrats: Contrat[] }) {
  const mobileSeul = state.servicePrincipal === "Mobile uniquement";
  const technoOptions = mobileSeul ? LISTE_TECHNO_MOBILE : LISTE_TECHNO;
  // En "Mobile uniquement", on ne doit proposer que des lignes mobiles comme
  // "ligne principale" à mettre à jour — sinon un contrat box du client/
  // prospect peut être coché par erreur alors qu'il n'a rien à voir avec la
  // situation mobile qu'on est en train de renseigner (voir consigne produit :
  // pas de box en Mobile uniquement, sauf en Multi-lignes/pack).
  const contratsTelecom = useMemo(() => {
    const tous = contrats.filter((c) => groupeContrat(c) === "Télécom");
    return mobileSeul ? tous.filter((c) => /mobile/i.test(c.categorie ?? "")) : tous;
  }, [contrats, mobileSeul]);

  // Le bloc "situation télécom" ne représente qu'une seule ligne à la fois —
  // si plusieurs contrats existants sont cochés (ex. 2 lignes mobile), on
  // préremplit avec le premier et on garde les autres en file d'attente :
  // "Ligne suivante" recharge le formulaire avec la ligne suivante, pour
  // traiter chaque contrat l'un après l'autre sans réécrire tout le wizard.
  const [file, setFile] = useState<number[]>([]);

  // S'il n'y a qu'une seule ligne mobile existante, c'est d'office elle la
  // "ligne principale" — pas besoin de faire cocher explicitement le
  // conseiller. S'il y en a plusieurs, on préselectionne celle déjà désignée
  // comme "ligne principale" (Contrat.ligne_principale, voir ContratsTab.tsx),
  // sans empêcher le conseiller de cocher une autre ligne à la place.
  useEffect(() => {
    if (file.length > 0) return;
    if (contratsTelecom.length === 1) {
      const seule = contratsTelecom[0];
      setFile([seule.id]);
      dispatch({ type: "SET_TELECOM", values: mapContratVersTelecom(seule) });
    } else {
      const principale = contratsTelecom.find((c) => c.ligne_principale);
      if (principale) {
        setFile([principale.id]);
        dispatch({ type: "SET_TELECOM", values: mapContratVersTelecom(principale) });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contratsTelecom]);

  function basculerContrat(contrat: Contrat, coche: boolean) {
    setFile((prev) => {
      const sansContrat = prev.filter((id) => id !== contrat.id);
      const next = coche ? [...sansContrat, contrat.id] : sansContrat;
      if (coche && prev.length === 0) {
        dispatch({ type: "SET_TELECOM", values: mapContratVersTelecom(contrat) });
      }
      return next;
    });
  }

  function ligneSuivante() {
    setFile((prev) => {
      const [, ...reste] = prev;
      const prochainId = reste[0];
      const prochainContrat = contratsTelecom.find((c) => c.id === prochainId);
      if (prochainContrat) dispatch({ type: "SET_TELECOM", values: mapContratVersTelecom(prochainContrat) });
      return reste;
    });
  }

  return (
    <div className="space-y-4">
      {contratsTelecom.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contrats télécom existants</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Cochez une ligne pour préremplir le formulaire ci-dessous. Si plusieurs lignes sont cochées, elles
              seront proposées une par une via « Ligne suivante ».
            </p>
            {contratsTelecom.map((c) => (
              <label key={c.id} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                <Checkbox
                  checked={file.includes(c.id)}
                  onCheckedChange={(coche) => basculerContrat(c, coche === true)}
                />
                {libelleContrat(c)}
              </label>
            ))}
            {file.length > 1 && (
              <Button type="button" variant="outline" size="sm" onClick={ligneSuivante}>
                Ligne suivante ({file.length - 1} restante{file.length - 1 > 1 ? "s" : ""}) ›
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">📱 Télécom</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <ChampSelect
            label="Opérateur actuel *"
            value={state.telecom.operateurActuel}
            onChange={(value) => dispatch({ type: "SET_TELECOM", values: { operateurActuel: value } })}
            options={LISTE_OPERATEURS_TEL}
          />
          <ChampSelect
            label="Technologie"
            value={state.telecom.techno}
            onChange={(value) => dispatch({ type: "SET_TELECOM", values: { techno: value } })}
            options={technoOptions}
          />
          <Champ
            label="Fin de contrat / engagement"
            type="date"
            value={state.telecom.finEngagement}
            onChange={(e) => dispatch({ type: "SET_TELECOM", values: { finEngagement: e.target.value } })}
          />
          <Champ
            label="Coût mensuel actuel (€) *"
            type="number"
            min={0}
            step={1}
            value={state.telecom.coutMensuelActuel || ""}
            onChange={(e) => dispatch({ type: "SET_TELECOM", values: { coutMensuelActuel: Number(e.target.value) } })}
          />
          <ChampSelect
            label="Go minimal *"
            value={state.telecom.dataGoMin}
            onChange={(value) => dispatch({ type: "SET_TELECOM", values: { dataGoMin: value } })}
            options={GO_OPTIONS}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">📶 Satisfaction réseau</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <ChampSelect
            label="Satisfaction réseau (réponse réelle du client) *"
            value={state.telecom.satisfactionReseau}
            onChange={(value) => dispatch({ type: "SET_TELECOM", values: { satisfactionReseau: value } })}
            options={SATISFACTION_RESEAU}
          />
          <ChampSelect
            label="Défaut technique potentiel *"
            value={state.telecom.defautTechnique}
            onChange={(value) => dispatch({ type: "SET_TELECOM", values: { defautTechnique: value } })}
            options={NIVEAUX_DEFAUT_TECHNIQUE}
            placeholder="Sélectionner…"
          />
          <ChampSelect
            label="Veut rester chez son opérateur *"
            value={state.telecom.veutRester}
            onChange={(value) => dispatch({ type: "SET_TELECOM", values: { veutRester: value } })}
            options={VEUT_RESTER_OPTIONS}
            placeholder="Sélectionner…"
          />
        </CardContent>
      </Card>
    </div>
  );
}

function BlocEnergie({ state, dispatch, contrats }: EtapeSituationProps & { contrats: Contrat[] }) {
  const contratsEnergie = useMemo(() => contrats.filter((c) => groupeContrat(c) === "Énergie"), [contrats]);

  // Contrairement au télécom, l'électricité et le gaz sont deux sous-champs
  // du même bloc "énergie" : cocher un contrat électricité ET un contrat gaz
  // remplit les deux sous-champs simultanément, sans file d'attente.
  const [coches, setCoches] = useState<number[]>([]);

  function basculerContrat(contrat: Contrat, coche: boolean) {
    setCoches((prev) => (coche ? [...prev, contrat.id] : prev.filter((id) => id !== contrat.id)));
    const estGaz = /\bgaz\b/i.test(`${contrat.categorie ?? ""} ${contrat.consommation ?? ""}`);
    if (!coche) return;
    // Un seul Contrat "Énergie" est écrit à la finalisation (élec + gaz
    // fusionnés, voir EtapeRecommandations.tsx) — le dernier contrat coché
    // devient la cible de la mise à jour.
    dispatch({
      type: "SET_ENERGIE",
      values: estGaz
        ? { contratId: contrat.id, coutGaz: contrat.cout_mensuel ?? 0, fournisseurEnergie: contrat.fournisseur || state.energie.fournisseurEnergie }
        : { contratId: contrat.id, coutElec: contrat.cout_mensuel ?? 0, fournisseurEnergie: contrat.fournisseur || state.energie.fournisseurEnergie },
    });
  }

  return (
    <div className="space-y-4">
      {contratsEnergie.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contrats énergie existants</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {contratsEnergie.map((c) => (
              <label key={c.id} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                <Checkbox
                  checked={coches.includes(c.id)}
                  onCheckedChange={(coche) => basculerContrat(c, coche === true)}
                />
                {libelleContrat(c)}
              </label>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">⚡ Énergie</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-3 gap-4">
          <ChampSelect
            label="Fournisseur actuel"
            value={state.energie.fournisseurEnergie}
            onChange={(value) => dispatch({ type: "SET_ENERGIE", values: { fournisseurEnergie: value } })}
            options={LISTE_FOURNISSEURS_ENERGIE}
          />
          <Champ
            label="Électricité — €/mois"
            type="number"
            min={0}
            step={1}
            value={state.energie.coutElec || ""}
            onChange={(e) => dispatch({ type: "SET_ENERGIE", values: { coutElec: Number(e.target.value) } })}
          />
          <Champ
            label="Gaz — €/mois"
            type="number"
            min={0}
            step={1}
            value={state.energie.coutGaz || ""}
            onChange={(e) => dispatch({ type: "SET_ENERGIE", values: { coutGaz: Number(e.target.value) } })}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function BlocAbonnements({ state, dispatch, contrats }: EtapeSituationProps & { contrats: Contrat[] }) {
  const [nom, setNom] = useState("");
  const [categorie, setCategorie] = useState<string>("");
  const [cout, setCout] = useState("");

  // Contrats "Autres" (abonnements) déjà connus — cocher plusieurs les ajoute
  // tous directement, `abonnements` étant déjà un tableau côté état.
  const contratsAbonnements = useMemo(
    () => contrats.filter((c) => groupeContrat(c) === "Autres" && (c.categorie || c.fournisseur)),
    [contrats]
  );
  const idAbonnementContrat = (contratId: number) => `contrat-${contratId}`;

  function basculerContrat(contrat: Contrat, coche: boolean) {
    const id = idAbonnementContrat(contrat.id);
    if (coche) {
      dispatch({
        type: "ADD_ABONNEMENT",
        item: {
          id,
          contratId: contrat.id,
          nom: contrat.fournisseur || contrat.categorie || `Contrat #${contrat.id}`,
          categorie: contrat.categorie || "Autre",
          cout: contrat.cout_mensuel ?? 0,
        },
      });
    } else {
      dispatch({ type: "REMOVE_ABONNEMENT", id });
    }
  }

  function ajouter() {
    if (!nom.trim() || !categorie || !cout) return;
    dispatch({
      type: "ADD_ABONNEMENT",
      item: { id: crypto.randomUUID(), nom: nom.trim(), categorie, cout: Number(cout) },
    });
    setNom("");
    setCategorie("");
    setCout("");
  }

  const total = state.abonnements.reduce((sum, a) => sum + a.cout, 0);
  const idsAbonnementsCoches = new Set(state.abonnements.map((a) => a.id));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">🎬 Abonnements</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {contratsAbonnements.length > 0 && (
          <div className="space-y-2 rounded-md border border-dashed p-3">
            <p className="text-xs text-muted-foreground">Contrats déjà enregistrés — cochez ceux à inclure :</p>
            {contratsAbonnements.map((c) => (
              <label key={c.id} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={idsAbonnementsCoches.has(idAbonnementContrat(c.id))}
                  onCheckedChange={(coche) => basculerContrat(c, coche === true)}
                />
                {libelleContrat(c)}
              </label>
            ))}
          </div>
        )}

        <div className="grid grid-cols-[2fr_1.5fr_1fr_auto] items-end gap-3">
          <Champ label="Nom de l'abonnement" value={nom} onChange={(e) => setNom(e.target.value)} />
          <ChampSelect label="Catégorie" value={categorie} onChange={setCategorie} options={CATEGORIES_ABONNEMENT} />
          <Champ label="€/mois" type="number" min={0} step={1} value={cout} onChange={(e) => setCout(e.target.value)} />
          <Button type="button" variant="outline" onClick={ajouter}>
            Ajouter
          </Button>
        </div>

        {state.abonnements.length > 0 && (
          <div className="space-y-2">
            {state.abonnements.map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                <span>
                  {a.nom} <span className="text-muted-foreground">({a.categorie})</span> — {a.cout} €/mois
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => dispatch({ type: "REMOVE_ABONNEMENT", id: a.id })}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <p className="text-sm text-muted-foreground">
              Total abonnements : <strong>{total.toFixed(2)} €/mois</strong> ({(total * 12).toFixed(2)} €/an)
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
