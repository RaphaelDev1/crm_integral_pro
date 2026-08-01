"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { downloadBackendFile } from "@/lib/api";
import { CATEGORIES_ENERGIE } from "@/lib/diagnosticConstants";
import { useLancerAudit } from "@/lib/hooks/useAuditAgent";
import { useConvertirProspect } from "@/lib/hooks/useProspects";
import { useCreerDossier, useEnvoyerLienClientDossier } from "@/lib/hooks/useDossiers";
import type { DiagnosticDispatch, DiagnosticState, PanierItem } from "@/lib/hooks/useDiagnosticWizard";
import { useCreerComparaisonOffre, useOffresComparees, useRecommandationsTelecom } from "@/lib/hooks/useOffres";
import type { AuditResult, OffreComparee } from "@/lib/types";

interface EtapeRecommandationsProps {
  state: DiagnosticState;
  dispatch: DiagnosticDispatch;
  onTermine: () => void;
}

// Étape 4 du diagnostic (plan Phase 6.6) — appelle le comparateur d'offres
// par univers, laisse le conseiller composer un panier, puis génère la
// restitution : un Dossier + un PDF par univers analysé (le backend modélise
// un Dossier = un univers, voir décision prise en amont de ce module).
export function EtapeRecommandations({ state, dispatch, onTermine }: EtapeRecommandationsProps) {
  const router = useRouter();
  const convertirProspect = useConvertirProspect();
  const creerComparaison = useCreerComparaisonOffre();
  const creerDossier = useCreerDossier();
  const envoyerLienEmail = useEnvoyerLienClientDossier();
  const lancerAudit = useLancerAudit();
  const [envoyerEmail, setEnvoyerEmail] = useState(true);
  const [genererEnCours, setGenererEnCours] = useState(false);
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null);

  const nomComplet = `${state.identite.prenom} ${state.identite.nom}`.trim() || "Client";
  const coutTelTotal = state.telecom.coutMensuelActuel || 0;
  const fournisseurExclu =
    state.telecom.satisfactionReseau && state.telecom.satisfactionReseau !== "😀 Très content" && state.telecom.operateurActuel
      ? state.telecom.operateurActuel
      : undefined;

  function ajouterAuPanier(univers: string, categorie: string, coutActuelMensuel: number, offre: OffreComparee) {
    const item: PanierItem = { id: `${univers}-${categorie}-${offre.id}`, univers, categorie, coutActuelMensuel, offre };
    dispatch({ type: "ADD_PANIER", item });
    toast.success(`${offre.nom} ajoutée au panier de restitution.`);
  }

  function estAuPanier(offreId: number) {
    return state.panier.some((p) => p.offre.id === offreId);
  }

  async function lancerAuditAutomatique() {
    setAuditResult(null);
    try {
      const resultat = await lancerAudit.mutateAsync({
        situation: {
          service_principal: state.servicePrincipal,
          cout_mensuel_actuel: state.telecom.coutMensuelActuel || 0,
          ville: state.identite.ville || undefined,
          operateur_actuel: state.telecom.operateurActuel || undefined,
          satisfaction_reseau: state.telecom.satisfactionReseau || undefined,
          veut_rester: state.telecom.veutRester ? "Oui" : "Non",
          cout_elec: state.energie.coutElec || 0,
          cout_gaz: state.energie.coutGaz || 0,
          fournisseur_energie: state.energie.fournisseurEnergie || undefined,
          abonnements: state.abonnements.map((a) => ({ nom: a.nom, categorie: a.categorie, cout: a.cout })),
          data_go_min: state.telecom.dataGoMin ? Number(state.telecom.dataGoMin) : undefined,
        },
      });

      setAuditResult(resultat);
      for (const reco of resultat.offres_recommandees) {
        const univers = reco.offre.univers ?? "";
        const categorie = reco.offre.categorie ?? "";
        const item: PanierItem = {
          id: `${univers}-${categorie}-${reco.offre.id}`,
          univers,
          categorie,
          coutActuelMensuel: reco.offre.prix_mensuel + reco.offre.economie_mensuelle,
          offre: reco.offre,
        };
        dispatch({ type: "ADD_PANIER", item });
      }
      if (resultat.offres_recommandees.length > 0) {
        toast.success(`Audit automatique : ${resultat.offres_recommandees.length} offre(s) ajoutée(s) au panier.`);
      } else {
        toast.info("Audit automatique terminé — aucune offre retenue par l'agent.");
      }
    } catch {
      toast.error("Échec de l'audit automatique — voir le détail dans les notifications.");
    }
  }

  const universPanier = Array.from(new Set(state.panier.map((p) => p.univers)));

  async function genererRestitution() {
    if (state.panier.length === 0) {
      toast.error("Ajoutez au moins une offre au panier avant de générer la restitution.");
      return;
    }
    setGenererEnCours(true);
    try {
      let clientId = state.identite.entiteType === "client" ? state.identite.entiteId : null;

      if (state.identite.entiteType === "prospect" && state.identite.entiteId) {
        const client = await convertirProspect.mutateAsync(state.identite.entiteId);
        clientId = client.id;
        dispatch({ type: "SET_IDENTITE", values: { entiteType: "client", entiteId: client.id } });
      }

      if (!clientId) {
        toast.error("Identité du client introuvable — revenez à l'étape 2.");
        return;
      }

      for (const univers of universPanier) {
        const items = state.panier.filter((p) => p.univers === univers);
        const meilleur = items.reduce((a, b) => (b.offre.economie_annuelle > a.offre.economie_annuelle ? b : a));

        // Le coût actuel mensuel n'est pas la somme des offres du panier (un
        // même abonnement téléphonique peut apparaître dans plusieurs blocs
        // — principal + cross-sell — pour le MÊME coût actuel) : on le relit
        // directement depuis la saisie de l'étape 3, par univers.
        let coutActuelMensuel = 0;
        if (univers === "Télécom") {
          coutActuelMensuel = state.telecom.coutMensuelActuel || 0;
        } else if (univers === "Énergie") {
          const categories = new Set(items.map((i) => i.categorie));
          if (categories.has("Électricité")) coutActuelMensuel += state.energie.coutElec || 0;
          if (categories.has("Gaz")) coutActuelMensuel += state.energie.coutGaz || 0;
        } else if (univers === "Abonnements") {
          const categories = new Set(items.map((i) => i.categorie));
          coutActuelMensuel = state.abonnements
            .filter((a) => categories.has(a.categorie))
            .reduce((sum, a) => sum + a.cout, 0);
        }

        const economieMensuelle = items.reduce((sum, i) => sum + i.offre.economie_mensuelle, 0);
        const economieAnnuelle = items.reduce((sum, i) => sum + i.offre.economie_annuelle, 0);

        await creerComparaison.mutateAsync({
          client_id: clientId,
          univers,
          categorie: meilleur.categorie,
          cout_actuel_mensuel: coutActuelMensuel,
          offre_recommandee_id: meilleur.offre.id,
          offres_comparees: items.map((i) => ({
            offre_id: i.offre.id,
            nom: i.offre.nom,
            fournisseur: i.offre.fournisseur,
            prix_mensuel: i.offre.prix_mensuel,
            economie_mensuelle: i.offre.economie_mensuelle,
          })),
          economie_mensuelle_estimee: economieMensuelle,
          economie_annuelle_estimee: economieAnnuelle,
          contexte: "Diagnostic conseiller",
        });

        const dossier = await creerDossier.mutateAsync({
          client_id: clientId,
          univers,
          fournisseur_cible: meilleur.offre.fournisseur ?? undefined,
          offre_cible_id: meilleur.offre.id,
          economie_annuelle_estimee: economieAnnuelle,
        });

        await downloadBackendFile(
          `/dossiers/${dossier.id}/pdf-restitution`,
          `restitution_${univers.toLowerCase()}_${nomComplet.replace(/\s+/g, "_")}.pdf`
        );

        if (envoyerEmail && state.identite.email) {
          await envoyerLienEmail.mutateAsync({ dossierId: dossier.id, canal: "email" });
        }
      }

      toast.success("Restitution générée — dossier(s) créé(s) et PDF téléchargé(s).");
      onTermine();
      router.push(`/clients/${clientId}`);
    } catch {
      toast.error("Échec de la génération de la restitution — voir le détail dans les notifications.");
    } finally {
      setGenererEnCours(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Recommandations pour {nomComplet}</h2>
        {state.telecom.veutRester && (
          <p className="text-sm text-amber-600">
            ⚠️ Le client souhaite rester chez {state.telecom.operateurActuel || "son opérateur actuel"} — adaptez votre
            argumentaire.
          </p>
        )}
      </div>

      <Card>
        <CardContent className="pt-6 space-y-3">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium">🤖 Audit automatique</p>
              <p className="text-xs text-muted-foreground">
                L&apos;agent compare le catalogue et pré-remplit le panier avec les offres qu&apos;il retient.
              </p>
            </div>
            <Button type="button" variant="outline" onClick={lancerAuditAutomatique} disabled={lancerAudit.isPending}>
              {lancerAudit.isPending ? "Audit en cours…" : "Lancer l'audit automatique"}
            </Button>
          </div>

          {auditResult && (
            <div className="space-y-2 rounded-md border p-3 text-sm">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">Confiance {(auditResult.niveau_confiance * 100).toFixed(0)}%</Badge>
                <span className="text-muted-foreground">{auditResult.offres_recommandees.length} offre(s) retenue(s)</span>
              </div>
              {auditResult.situation_detectee && <p className="text-muted-foreground">{auditResult.situation_detectee}</p>}
              {auditResult.points_attention.length > 0 && (
                <ul className="list-disc space-y-1 pl-4 text-amber-600">
                  {auditResult.points_attention.map((point, i) => (
                    <li key={i}>{point}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {state.univers.includes("Télécom") && (
        <BlocTelecom
          servicePrincipal={state.servicePrincipal}
          coutTel={coutTelTotal}
          fournisseurExclu={fournisseurExclu}
          dataGoMin={state.telecom.dataGoMin}
          estAuPanier={estAuPanier}
          onAjouter={ajouterAuPanier}
        />
      )}

      {state.univers.includes("Énergie") &&
        CATEGORIES_ENERGIE.map((categorie) => {
          const cout = categorie === "Électricité" ? state.energie.coutElec : state.energie.coutGaz;
          if (!cout) return null;
          return (
            <BlocComparaison
              key={categorie}
              titre={`⚡ Énergie — ${categorie}`}
              univers="Énergie"
              categorie={categorie}
              coutActuel={cout}
              estAuPanier={estAuPanier}
              onAjouter={ajouterAuPanier}
            />
          );
        })}

      {state.univers.includes("Abonnements") &&
        state.abonnements.map((abo) => (
          <BlocComparaison
            key={abo.id}
            titre={`🎬 ${abo.nom} (${abo.categorie})`}
            univers="Abonnements"
            categorie={abo.categorie}
            coutActuel={abo.cout}
            estAuPanier={estAuPanier}
            onAjouter={ajouterAuPanier}
          />
        ))}

      {state.univers.includes("Assurances") && (
        <Card>
          <CardContent className="p-4 text-sm text-muted-foreground">
            Aucune offre Assurances au catalogue pour le moment.
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Panier de restitution ({state.panier.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {state.panier.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Cochez « Ajouter au panier » sur les offres à présenter au client.
            </p>
          ) : (
            <ul className="space-y-2 text-sm">
              {state.panier.map((item) => (
                <li key={item.id} className="flex items-center justify-between rounded-md border px-3 py-2">
                  <span>
                    <strong>{item.univers}</strong> — {item.offre.nom} ({item.offre.fournisseur}) — économie{" "}
                    {item.offre.economie_annuelle.toFixed(2)} €/an
                  </span>
                  <Button type="button" variant="ghost" size="sm" onClick={() => dispatch({ type: "REMOVE_PANIER", id: item.id })}>
                    Retirer
                  </Button>
                </li>
              ))}
            </ul>
          )}

          {state.identite.email && (
            <div className="flex items-center gap-2">
              <Checkbox checked={envoyerEmail} onCheckedChange={(checked) => setEnvoyerEmail(checked === true)} />
              <Label className="font-normal">Envoyer aussi le lien de suivi par email au client</Label>
            </div>
          )}

          <Button type="button" onClick={genererRestitution} disabled={genererEnCours || state.panier.length === 0}>
            {genererEnCours ? "Génération en cours…" : "Générer restitution PDF"}
          </Button>
          {universPanier.length > 1 && (
            <p className="text-xs text-muted-foreground">
              {universPanier.length} univers dans le panier → {universPanier.length} dossiers et {universPanier.length}{" "}
              PDF seront générés (un par univers).
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function OffreCard({
  offre,
  auPanier,
  onAjouter,
}: {
  offre: OffreComparee;
  auPanier: boolean;
  onAjouter: () => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <div>
        <p className="font-medium">{offre.nom}</p>
        <p className="text-sm text-muted-foreground">
          {offre.fournisseur} · {offre.caracteristiques}
        </p>
        <p className="text-sm">
          💶 {offre.prix_mensuel.toFixed(2)} €/mois — économie{" "}
          <strong className="text-emerald-700">{offre.economie_annuelle.toFixed(2)} €/an</strong>
        </p>
      </div>
      <Button type="button" size="sm" variant={auPanier ? "secondary" : "outline"} onClick={onAjouter} disabled={auPanier}>
        {auPanier ? "Dans le panier" : "⭐ Ajouter au panier"}
      </Button>
    </div>
  );
}

function BlocTelecom({
  servicePrincipal,
  coutTel,
  fournisseurExclu,
  dataGoMin,
  estAuPanier,
  onAjouter,
}: {
  servicePrincipal: string;
  coutTel: number;
  fournisseurExclu: string | undefined;
  dataGoMin: string;
  estAuPanier: (id: number) => boolean;
  onAjouter: (univers: string, categorie: string, coutActuel: number, offre: OffreComparee) => void;
}) {
  const query = useRecommandationsTelecom(
    {
      service_principal: servicePrincipal,
      cout_tel: coutTel,
      fournisseur_exclu: fournisseurExclu,
      data_go_min: dataGoMin ? Number(dataGoMin) : undefined,
    },
    coutTel > 0
  );

  if (coutTel <= 0) return null;
  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (!query.data) return null;

  const categorieDe = (titre: string) => titre.replace(/^[^\wÀ-ÿ]+/u, "").trim();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{query.data.principal.titre}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {fournisseurExclu && (
          <p className="text-xs text-muted-foreground">
            ℹ️ Client pas pleinement satisfait de {fournisseurExclu} — offres d&apos;autres opérateurs proposées en priorité.
          </p>
        )}
        {query.data.principal.offres.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune offre dans cette catégorie au catalogue.</p>
        ) : (
          query.data.principal.offres.map((offre) => (
            <OffreCard
              key={offre.id}
              offre={offre}
              auPanier={estAuPanier(offre.id)}
              onAjouter={() => onAjouter("Télécom", categorieDe(query.data!.principal.titre), coutTel, offre)}
            />
          ))
        )}

        {query.data.cross_sell
          .filter((bloc) => bloc.offres.length > 0)
          .map((bloc) => (
            <div key={bloc.titre} className="space-y-2 border-t pt-3">
              <p className="text-sm font-medium text-muted-foreground">{bloc.titre}</p>
              {bloc.offres.map((offre) => (
                <OffreCard
                  key={offre.id}
                  offre={offre}
                  auPanier={estAuPanier(offre.id)}
                  onAjouter={() => onAjouter("Télécom", categorieDe(bloc.titre), coutTel, offre)}
                />
              ))}
            </div>
          ))}
      </CardContent>
    </Card>
  );
}

function BlocComparaison({
  titre,
  univers,
  categorie,
  coutActuel,
  estAuPanier,
  onAjouter,
}: {
  titre: string;
  univers: string;
  categorie: string;
  coutActuel: number;
  estAuPanier: (id: number) => boolean;
  onAjouter: (univers: string, categorie: string, coutActuel: number, offre: OffreComparee) => void;
}) {
  const query = useOffresComparees({ univers, categorie, cout_actuel_mensuel: coutActuel }, coutActuel > 0);

  if (query.isLoading) return <Skeleton className="h-24 w-full" />;

  const offres = (query.data ?? []).filter((o) => o.prix_mensuel < coutActuel).slice(0, 3);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{titre}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Actuel : {coutActuel.toFixed(2)} €/mois soit {(coutActuel * 12).toFixed(2)} €/an
        </p>
        {offres.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune offre moins chère au catalogue.</p>
        ) : (
          offres.map((offre) => (
            <OffreCard
              key={offre.id}
              offre={offre}
              auPanier={estAuPanier(offre.id)}
              onAjouter={() => onAjouter(univers, categorie, coutActuel, offre)}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}
