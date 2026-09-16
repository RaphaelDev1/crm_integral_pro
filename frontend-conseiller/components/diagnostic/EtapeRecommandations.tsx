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
import { apiFetch, ApiError, downloadBackendFile } from "@/lib/api";
import { CATEGORIES_ENERGIE, champsIdentiteManquants, champsTelecomManquants, parseGoMinimal } from "@/lib/diagnosticConstants";
import { useLancerAudit } from "@/lib/hooks/useAuditAgent";
import { clientsResource } from "@/lib/hooks/useClients";
import { contratsResource, useContrats } from "@/lib/hooks/useContrats";
import { prospectsResource, useClientMiroirProspect } from "@/lib/hooks/useProspects";
import { useCreerDossier, useEnvoyerLienClientDossier } from "@/lib/hooks/useDossiers";
import type { DiagnosticDispatch, DiagnosticState, PanierItem } from "@/lib/hooks/useDiagnosticWizard";
import { useCreerComparaisonOffre, useOffresComparees, useRecommandationsTelecom } from "@/lib/hooks/useOffres";
import type { AuditResult, Contrat, OffreComparee, Prospect } from "@/lib/types";

// Estime le débit nécessaire au foyer à partir des réponses B4/B5 de la trame
// box (docs/QUESTIONS_PAR_SECTEUR.md) pour savoir si une box fibre est
// vraiment utile ou si une box 4G/5G (moins chère) suffit — objectif : ne pas
// vendre plus cher que nécessaire. `null` si le contrat n'a aucune réponse
// B4/B5 exploitable (rien à estimer).
interface BesoinDebit {
  debitMinMbps: number;
  uploadMinMbps?: number;
  technoRecommandee: string;
  motifs: string[];
}

function estimerBesoinDebit(contrat: Contrat): BesoinDebit | null {
  if (!contrat.nb_utilisateurs_streaming && contrat.usage_4k == null && !contrat.teletravail) return null;

  const motifs: string[] = [];

  // B4 : nombre d'utilisateurs simultanés en streaming + vidéo 4K.
  let debitMinMbps = 100;
  if (contrat.nb_utilisateurs_streaming === "3+" || contrat.usage_4k) {
    debitMinMbps = 500;
    motifs.push(contrat.usage_4k ? "vidéo 4K régulière" : "3+ utilisateurs simultanés en streaming");
  } else if (contrat.nb_utilisateurs_streaming === "1-2") {
    motifs.push("1-2 utilisateurs en streaming, usage HD");
  }

  // B5 : télétravail avec visios fréquentes → upload symétrique nécessaire.
  let uploadMinMbps: number | undefined;
  if (contrat.teletravail === "oui_frequent") {
    uploadMinMbps = 200;
    motifs.push("télétravail avec visios fréquentes (besoin d'upload symétrique)");
  }

  // B1-bis : débit ADSL mesuré, pour juger si une box 4G/5G ferait déjà mieux.
  const debitMesure = contrat.speed_down ?? contrat.debit_declare ?? null;
  if (debitMesure != null && contrat.nom_offre === "ADSL") {
    motifs.push(`débit ADSL mesuré : ${debitMesure} Mbps`);
  }

  let technoRecommandee: string;
  if (uploadMinMbps) {
    technoRecommandee = "Fibre symétrique nécessaire";
  } else if (debitMinMbps >= 500) {
    technoRecommandee = "Fibre recommandée (usage intensif)";
  } else if (debitMesure != null && debitMesure < 8) {
    technoRecommandee = "Box 4G/5G probablement suffisante (et moins chère)";
  } else {
    technoRecommandee = "Box 4G/5G ou ADSL peuvent suffire — pas besoin de fibre très haut débit";
  }

  return { debitMinMbps, uploadMinMbps, technoRecommandee, motifs };
}

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
  const clientMiroirProspect = useClientMiroirProspect();
  const creerClient = clientsResource.useCreate();
  const majClient = clientsResource.useUpdate();
  const majProspect = prospectsResource.useUpdate();
  const creerContrat = contratsResource.useCreate();
  const majContrat = contratsResource.useUpdate();
  const creerComparaison = useCreerComparaisonOffre();
  const creerDossier = useCreerDossier();
  const envoyerLienEmail = useEnvoyerLienClientDossier();
  const lancerAudit = useLancerAudit();
  const [envoyerEmail, setEnvoyerEmail] = useState(true);
  const [genererEnCours, setGenererEnCours] = useState(false);
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null);

  const estProspect = state.identite.entiteType === "prospect";
  const contratsProspectQuery = useContrats({
    prospectId: estProspect ? state.identite.entiteId ?? undefined : undefined,
  });
  const lignesTelecomIncompletes = (contratsProspectQuery.data ?? [])
    .filter((c) => /mobile|box|internet/i.test(`${c.categorie ?? ""}`) || c.univers === "Télécom")
    .map((c) => ({ contrat: c, manquants: champsTelecomManquants(c) }))
    .filter((l) => l.manquants.length > 0);

  // Contrat box/fibre actuel (le seul concerné par B4/B5, voir docs/QUESTIONS_PAR_SECTEUR.md) —
  // sert à estimer si une fibre haut débit est vraiment nécessaire.
  const contratBox = (contratsProspectQuery.data ?? []).find((c) => /box|fibre/i.test(`${c.categorie ?? ""}`));
  const besoinDebit = contratBox ? estimerBesoinDebit(contratBox) : null;

  // Identité (date/département/ville de naissance) — requise par la page
  // "informations personnelles" du tunnel de souscription Free Mobile (voir
  // souscription_engine.py), posée sur le lien personnel du prospect
  // (/dossier/[token]/situation), pas dans ce wizard — d'où la requête dédiée
  // plutôt qu'une valeur déjà dans state.identite.
  const prospectQuery = prospectsResource.useOne(estProspect ? state.identite.entiteId ?? undefined : undefined);
  const champsIdentiteManquantsListe = estProspect ? champsIdentiteManquants(prospectQuery.data) : [];

  const nomComplet = `${state.identite.prenom} ${state.identite.nom}`.trim() || "Client";
  const coutTelTotal = state.telecom.coutMensuelActuel || 0;
  const fournisseurExclu =
    state.telecom.satisfactionReseau && state.telecom.satisfactionReseau !== "😀 Très content" && state.telecom.operateurActuel
      ? state.telecom.operateurActuel
      : undefined;

  function ajouterAuPanier(
    univers: string,
    categorie: string,
    coutActuelMensuel: number,
    offre: OffreComparee,
    comparable = true
  ) {
    const item: PanierItem = {
      id: `${univers}-${categorie}-${offre.id}`,
      univers,
      categorie,
      coutActuelMensuel,
      offre,
      comparable,
    };
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
          veut_rester: state.telecom.veutRester || undefined,
          cout_elec: state.energie.coutElec || 0,
          cout_gaz: state.energie.coutGaz || 0,
          fournisseur_energie: state.energie.fournisseurEnergie || undefined,
          abonnements: state.abonnements.map((a) => ({ nom: a.nom, categorie: a.categorie, cout: a.cout })),
          data_go_min: parseGoMinimal(state.telecom.dataGoMin),
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
          // L'agent d'audit ne recommande que des offres dont le coût de
          // référence est réellement comparable (voir audit_agent.py::
          // outil_cout_reference_categorie), donc toujours comparable ici.
          comparable: true,
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

      if (estProspect && state.identite.entiteId) {
        // Crée seulement un client "miroir" — le prospect reste actionnable
        // dans /prospects tant que le mandat de représentation n'est pas
        // signé (la vraie conversion se déclenche à la signature, pas ici).
        try {
          const client = await clientMiroirProspect.mutateAsync(state.identite.entiteId);
          clientId = client.id;
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) {
            // Le prospect référencé par ce brouillon n'existe plus (brouillon
            // repris depuis le localStorage après suppression du prospect, ou
            // après un diagnostic précédent resté inachevé) — mieux vaut
            // repartir d'un wizard vierge que de laisser l'utilisateur
            // ré-essayer indéfiniment sur un identifiant mort.
            onTermine();
            toast.error(
              "Ce prospect n'existe plus (fiche supprimée ou brouillon périmé) — le diagnostic a été réinitialisé, recommencez."
            );
            return;
          }
          if (err instanceof ApiError && err.status === 409) {
            // Le prospect a déjà été converti depuis ce brouillon (mandat signé
            // entre-temps, voir mandat_engine.traiter_mandat_signe) : le
            // client-miroir n'a plus de raison d'être créé, on réutilise
            // directement le client déjà rattaché au prospect.
            const prospect = await apiFetch<Prospect>(`/prospects/${state.identite.entiteId}`);
            if (!prospect.client_id) throw err;
            clientId = prospect.client_id;
            toast.info("Ce prospect a déjà été converti en client — la fiche client existante est utilisée.");
          } else {
            throw err;
          }
        }
      } else if (!clientId && state.identite.mode === "nouveau") {
        // Diagnostic fait en direct, sans prospect/client pré-enregistré : on
        // crée directement la fiche client à partir de la saisie de l'étape 2
        // (un Dossier a toujours besoin d'un client_id, voir backend/models/dossier.py).
        const client = await creerClient.mutateAsync({
          prenom: state.identite.prenom,
          nom: state.identite.nom,
          telephone: state.identite.telephone,
          email: state.identite.email || undefined,
          code_postal: state.identite.codePostal || undefined,
          ville: state.identite.ville || undefined,
          adresse: state.identite.adresse || undefined,
          type_client: state.identite.typeClient,
          raison_sociale: state.identite.raisonSociale || undefined,
          effectif: state.identite.effectif || undefined,
        });
        clientId = client.id;
      }

      if (!clientId) {
        toast.error("Identité du client introuvable — revenez à l'étape 2.");
        return;
      }

      let totalEconomieAnnuelle = 0;

      for (const univers of universPanier) {
        const items = state.panier.filter((p) => p.univers === univers);
        // Seules les offres comparables (même catégorie que ce que le client
        // paie déjà) entrent dans le calcul de l'économie mise en avant — une
        // offre cross-sell (ex. Box proposée alors qu'il a un forfait Mobile)
        // n'est pas comparable financièrement à son coût actuel, voir
        // PanierItem.comparable et OffreCard plus bas.
        const comparables = items.filter((i) => i.comparable !== false);
        const meilleur = (comparables.length > 0 ? comparables : items).reduce((a, b) =>
          b.offre.economie_annuelle > a.offre.economie_annuelle ? b : a
        );

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

        // Économie totale = celle de la meilleure offre comparable, pas la
        // somme de tout le panier (une offre cross-sell "négative" ne doit
        // pas venir grever l'économie réelle de l'offre principale).
        const economieMensuelle = comparables.length > 0 ? meilleur.offre.economie_mensuelle : 0;
        const economieAnnuelle = comparables.length > 0 ? meilleur.offre.economie_annuelle : 0;
        totalEconomieAnnuelle += economieAnnuelle;

        // Enregistre la situation ACTUELLE du client dans ses contrats (pas
        // l'offre recommandée) — pour qu'on retrouve sur sa fiche exactement
        // ce qu'il a aujourd'hui, avec quel fournisseur et à quel prix.
        let fournisseurActuel: string | undefined;
        let nomOffreActuelle: string | undefined;
        // Id du Contrat existant coché à l'étape Situation pour cet univers —
        // quand renseigné, la finalisation met à jour ce contrat au lieu d'en
        // recréer un nouveau (voir contratId sur SituationTelecomState/
        // SituationEnergieState/AbonnementDraft, useDiagnosticWizard.ts).
        let contratIdCible: number | undefined;
        if (univers === "Télécom") {
          fournisseurActuel = state.telecom.operateurActuel || undefined;
          nomOffreActuelle = state.telecom.offreActuelle || undefined;
          contratIdCible = state.telecom.contratId;
        } else if (univers === "Énergie") {
          fournisseurActuel = state.energie.fournisseurEnergie || undefined;
          contratIdCible = state.energie.contratId;
        } else if (univers === "Abonnements") {
          const categories = new Set(items.map((i) => i.categorie));
          const abonnementsConcernes = state.abonnements.filter((a) => categories.has(a.categorie));
          fournisseurActuel = abonnementsConcernes.map((a) => a.nom).join(", ") || undefined;
          contratIdCible = abonnementsConcernes.find((a) => a.contratId)?.contratId;
        }
        if (fournisseurActuel && coutActuelMensuel > 0) {
          // Une ligne/contrat existant a été choisi à l'étape Situation : on
          // met à jour ce contrat plutôt que d'en recréer un, sinon le client
          // se retrouve avec deux lignes pour la même situation.
          // Champs "situation actuelle" saisis à l'étape Situation (satisfaction,
          // souhait de rester, défaut technique, débit mesuré) — rattachés au
          // Contrat plutôt qu'au Client/Prospect (voir migration
          // 0040_situation_actuelle_sur_contrats), pour ne pas avoir à les
          // ressaisir à la main dans "Réseau actuel".
          const situationContrat =
            univers === "Télécom"
              ? {
                  satisfaction_reseau: state.telecom.satisfactionReseau || undefined,
                  veut_rester: state.telecom.veutRester || undefined,
                  defaut_technique: state.telecom.defautTechnique || undefined,
                  speed_down: state.telecom.speedDown || undefined,
                  speed_up: state.telecom.speedUp || undefined,
                }
              : {};
          if (contratIdCible) {
            await majContrat.mutateAsync({
              id: contratIdCible,
              values: {
                categorie: meilleur.categorie,
                fournisseur: fournisseurActuel,
                nom_offre: nomOffreActuelle,
                cout_mensuel: coutActuelMensuel,
                statut_contrat: "Actuel",
                date_fin_engagement: univers === "Télécom" ? state.telecom.finEngagement || undefined : undefined,
                ...situationContrat,
              },
            });
          } else {
            await creerContrat.mutateAsync({
              client_id: clientId,
              univers,
              categorie: meilleur.categorie,
              fournisseur: fournisseurActuel,
              nom_offre: nomOffreActuelle,
              cout_mensuel: coutActuelMensuel,
              statut_contrat: "Actuel",
              date_fin_engagement: univers === "Télécom" ? state.telecom.finEngagement || undefined : undefined,
              ...situationContrat,
            });
          }
        }

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
            frais_annexes_total: i.offre.frais_annexes_total,
            comparable: i.comparable !== false,
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
          frais_annexes_cible: meilleur.offre.frais_annexes_total,
          est_prospect: estProspect,
        });

        await downloadBackendFile(
          `/dossiers/${dossier.id}/pdf-restitution`,
          `restitution_${univers.toLowerCase()}_${nomComplet.replace(/\s+/g, "_")}.pdf`
        );

        if (envoyerEmail && state.identite.email) {
          await envoyerLienEmail.mutateAsync({ dossierId: dossier.id, canal: "email" });
        }
      }

      // Reporte l'économie totale identifiée sur la fiche source — c'est ce
      // qui alimente "économie estimée" dans les listes prospects/relances
      // (et, pour un prospect, son score qui en dépend). On reporte aussi
      // l'opérateur/techno/coût "réseau actuel" saisis à l'étape 3 : sans ça,
      // ces infos existaient bien quelque part (contrat créé plus haut) mais
      // jamais sur la fiche prospect/client elle-même, obligeant à les
      // ressaisir à la main. Satisfaction/souhait de rester/défaut
      // technique/débit sont eux désormais uniquement sur le Contrat
      // (voir situationContrat plus haut) — plus besoin de les dupliquer ici.
      const situationReseau = state.univers.includes("Télécom")
        ? {
            operateur_actuel: state.telecom.operateurActuel || undefined,
            techno: state.telecom.techno || undefined,
            cout_mensuel_actuel: state.telecom.coutMensuelActuel || undefined,
          }
        : {};
      if (estProspect && state.identite.entiteId) {
        await majProspect.mutateAsync({
          id: state.identite.entiteId,
          values: { economie_estimee_an: totalEconomieAnnuelle, ...situationReseau },
        });
      } else if (!estProspect) {
        await majClient.mutateAsync({
          id: clientId,
          values: { economie_estimee_an: totalEconomieAnnuelle, ...situationReseau },
        });
      }

      toast.success("Restitution générée — dossier(s) créé(s) et PDF téléchargé(s).");
      onTermine();
      // Un prospect reste un prospect tant qu'il n'est pas réellement converti
      // (mandat signé) — même si un client "miroir" existe déjà en base pour
      // porter le(s) dossier(s), on ne redirige pas vers /clients.
      if (estProspect && state.identite.entiteId) {
        router.push(`/prospects/${state.identite.entiteId}`);
      } else {
        router.push(`/clients/${clientId}`);
      }
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
        {state.telecom.veutRester === "Oui" && (
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

      {besoinDebit && (
        <Card className="border-sky-300 bg-sky-50">
          <CardHeader>
            <CardTitle className="text-base text-sky-900">📶 Débit réellement nécessaire au foyer</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-sky-900">
            <p>
              Débit minimum estimé : <strong>{besoinDebit.debitMinMbps} Mbps</strong>
              {besoinDebit.uploadMinMbps ? <> (upload ≥ {besoinDebit.uploadMinMbps} Mbps)</> : null}
            </p>
            <p className="font-medium">{besoinDebit.technoRecommandee}</p>
            {besoinDebit.motifs.length > 0 && (
              <ul className="list-disc space-y-0.5 pl-5 text-sky-800">
                {besoinDebit.motifs.map((motif) => (
                  <li key={motif}>{motif}</li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

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

      {(lignesTelecomIncompletes.length > 0 || champsIdentiteManquantsListe.length > 0) && (
        <Card className="border-amber-300 bg-amber-50">
          <CardHeader>
            <CardTitle className="text-base text-amber-900">
              ⚠️ Le prospect n&apos;a pas répondu à toutes les questions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-amber-900">
            <p>
              Avant de lancer le dossier, posez-lui les questions suivantes pour être sûr de lui proposer la
              meilleure offre — la réponse peut changer la recommandation finale :
            </p>
            {champsIdentiteManquantsListe.length > 0 && (
              <div>
                <p className="font-medium">Identité</p>
                <ul className="list-disc space-y-0.5 pl-5">
                  {champsIdentiteManquantsListe.map((label) => (
                    <li key={label}>{label}</li>
                  ))}
                </ul>
              </div>
            )}
            {lignesTelecomIncompletes.map(({ contrat, manquants }) => (
              <div key={contrat.id}>
                <p className="font-medium">{contrat.categorie || "Ligne télécom"} — {contrat.fournisseur || "opérateur non renseigné"}</p>
                <ul className="list-disc space-y-0.5 pl-5">
                  {manquants.map((label) => (
                    <li key={label}>{label}</li>
                  ))}
                </ul>
              </div>
            ))}
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
                    <strong>{item.univers}</strong> — {item.offre.nom} ({item.offre.fournisseur}){" "}
                    {item.comparable !== false ? (
                      <>— économie {item.offre.economie_annuelle.toFixed(2)} €/an</>
                    ) : (
                      <>— {item.offre.prix_mensuel.toFixed(2)} €/mois (non comparable)</>
                    )}
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
  comparable = true,
  onAjouter,
}: {
  offre: OffreComparee;
  auPanier: boolean;
  comparable?: boolean;
  onAjouter: () => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <div>
        <p className="font-medium">{offre.nom}</p>
        <p className="text-sm text-muted-foreground">
          {offre.fournisseur} · {offre.caracteristiques}
        </p>
        {comparable ? (
          <p className="text-sm">
            💶 {offre.prix_mensuel.toFixed(2)} €/mois — économie{" "}
            <strong className="text-emerald-700">{offre.economie_annuelle.toFixed(2)} €/an</strong>
          </p>
        ) : (
          <p className="text-sm">💶 {offre.prix_mensuel.toFixed(2)} €/mois</p>
        )}
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
  onAjouter: (univers: string, categorie: string, coutActuel: number, offre: OffreComparee, comparable?: boolean) => void;
}) {
  const query = useRecommandationsTelecom(
    {
      service_principal: servicePrincipal,
      cout_tel: coutTel,
      fournisseur_exclu: fournisseurExclu,
      data_go_min: parseGoMinimal(dataGoMin),
    },
    coutTel > 0
  );

  if (coutTel <= 0) return null;
  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (!query.data) return null;

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
              comparable
              onAjouter={() => onAjouter("Télécom", query.data!.principal.categorie, coutTel, offre, true)}
            />
          ))
        )}

        {query.data.cross_sell
          .filter((bloc) => bloc.offres.length > 0)
          .map((bloc) => (
            <div key={bloc.titre} className="space-y-2 border-t pt-3">
              <p className="text-sm font-medium text-muted-foreground">{bloc.titre}</p>
              <p className="text-xs text-muted-foreground">
                Autre type de service — non comparable financièrement à votre abonnement actuel.
              </p>
              {bloc.offres.map((offre) => (
                <OffreCard
                  key={offre.id}
                  offre={offre}
                  auPanier={estAuPanier(offre.id)}
                  comparable={false}
                  onAjouter={() => onAjouter("Télécom", bloc.categorie, coutTel, offre, false)}
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
