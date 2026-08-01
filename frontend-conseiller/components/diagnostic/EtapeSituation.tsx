"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Champ, ChampSelect } from "@/components/diagnostic/champs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  CATEGORIES_ABONNEMENT,
  DEBITS_OPTIONS,
  LISTE_FOURNISSEURS_ENERGIE,
  LISTE_OPERATEURS_TEL,
  LISTE_TECHNO,
  LISTE_TECHNO_MOBILE,
  SATISFACTION_RESEAU,
} from "@/lib/diagnosticConstants";
import type { DiagnosticDispatch, DiagnosticState } from "@/lib/hooks/useDiagnosticWizard";

interface EtapeSituationProps {
  state: DiagnosticState;
  dispatch: DiagnosticDispatch;
}

// Étape 3 du diagnostic (plan Phase 6.5) — un bloc par univers coché à
// l'étape 1, miroir des champs de src/app.py (étape 3 du wizard Streamlit).
export function EtapeSituation({ state, dispatch }: EtapeSituationProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Situation actuelle du client</h2>
        <p className="text-sm text-muted-foreground">Renseignez les informations pour chaque univers analysé.</p>
      </div>

      {state.univers.includes("Télécom") && <BlocTelecom state={state} dispatch={dispatch} />}
      {state.univers.includes("Énergie") && <BlocEnergie state={state} dispatch={dispatch} />}
      {state.univers.includes("Abonnements") && <BlocAbonnements state={state} dispatch={dispatch} />}
    </div>
  );
}

function BlocTelecom({ state, dispatch }: EtapeSituationProps) {
  const mobileSeul = state.servicePrincipal === "Mobile uniquement";
  const boxSeule = state.servicePrincipal === "Box / Fibre uniquement";
  const afficherDebit = boxSeule || state.telecom.techno === "FIBRE" || state.telecom.techno === "ADSL";
  const technoOptions = mobileSeul ? LISTE_TECHNO_MOBILE : LISTE_TECHNO;

  return (
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
          label="Offre / forfait actuel"
          value={state.telecom.offreActuelle}
          onChange={(e) => dispatch({ type: "SET_TELECOM", values: { offreActuelle: e.target.value } })}
        />
        <Champ
          label="Coût mensuel actuel (€) *"
          type="number"
          min={0}
          step={1}
          value={state.telecom.coutMensuelActuel || ""}
          onChange={(e) => dispatch({ type: "SET_TELECOM", values: { coutMensuelActuel: Number(e.target.value) } })}
        />
        {afficherDebit ? (
          <ChampSelect
            label="Bande passante souhaitée"
            value={state.telecom.debitSouhaite}
            onChange={(value) => dispatch({ type: "SET_TELECOM", values: { debitSouhaite: value } })}
            options={DEBITS_OPTIONS}
          />
        ) : (
          <Champ
            label="Data mobile minimum (Go) *"
            value={state.telecom.dataGoMin}
            onChange={(e) => dispatch({ type: "SET_TELECOM", values: { dataGoMin: e.target.value } })}
          />
        )}
        <ChampSelect
          label="Satisfaction réseau (réponse réelle du client) *"
          value={state.telecom.satisfactionReseau}
          onChange={(value) => dispatch({ type: "SET_TELECOM", values: { satisfactionReseau: value } })}
          options={SATISFACTION_RESEAU}
        />
        <Champ
          label="Débit descendant mesuré (Mbps)"
          type="number"
          min={0}
          value={state.telecom.speedDown || ""}
          onChange={(e) => dispatch({ type: "SET_TELECOM", values: { speedDown: Number(e.target.value) } })}
        />
        <Champ
          label="Débit montant mesuré (Mbps)"
          type="number"
          min={0}
          value={state.telecom.speedUp || ""}
          onChange={(e) => dispatch({ type: "SET_TELECOM", values: { speedUp: Number(e.target.value) } })}
        />
        <div className="col-span-2 flex items-center gap-2">
          <Checkbox
            checked={state.telecom.veutRester}
            onCheckedChange={(checked) => dispatch({ type: "SET_TELECOM", values: { veutRester: checked === true } })}
          />
          <Label className="font-normal">⚠️ Le client souhaite rester chez son opérateur actuel</Label>
        </div>
      </CardContent>
    </Card>
  );
}

function BlocEnergie({ state, dispatch }: EtapeSituationProps) {
  return (
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
  );
}

function BlocAbonnements({ state, dispatch }: EtapeSituationProps) {
  const [nom, setNom] = useState("");
  const [categorie, setCategorie] = useState<string>("");
  const [cout, setCout] = useState("");

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

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">🎬 Abonnements</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
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
