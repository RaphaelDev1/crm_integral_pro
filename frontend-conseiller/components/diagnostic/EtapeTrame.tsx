"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Champ, ChampSelect } from "@/components/diagnostic/champs";
import { SessionTrameWorkspace } from "@/components/ia-conseil/SessionTrameWorkspace";
import { apiFetch, ApiError, downloadBackendFile } from "@/lib/api";
import { CATEGORIES_ABONNEMENT } from "@/lib/diagnosticConstants";
import type { DiagnosticDispatch, DiagnosticState } from "@/lib/hooks/useDiagnosticWizard";
import { clientsResource, useIaConseilClientClient } from "@/lib/hooks/useClients";
import { contratsResource } from "@/lib/hooks/useContrats";
import { useCreerDossier, useEnvoyerLienClientDossier } from "@/lib/hooks/useDossiers";
import { useCreerSessionTrame, useIaConseilFournisseurs, useRecommandations, useSessionTrame } from "@/lib/hooks/useIaConseil";
import { useCreerComparaisonOffre, useOffresComparees } from "@/lib/hooks/useOffres";
import { prospectsResource, useClientMiroirProspect, useIaConseilClientProspect } from "@/lib/hooks/useProspects";
import type { OffreComparee, Prospect } from "@/lib/types";

interface EtapeTrameProps {
  state: DiagnosticState;
  dispatch: DiagnosticDispatch;
  onTermine: () => void;
}

interface CategorieMeta {
  slug: string;
  label: string;
  univers: "Télécom" | "Énergie";
}

const CATEGORIE_META: Record<string, CategorieMeta> = {
  mobile: { slug: "mobile", label: "📱 Mobile", univers: "Télécom" },
  box: { slug: "box", label: "📶 Box / Fibre", univers: "Télécom" },
  energie_elec: { slug: "energie_elec", label: "⚡ Électricité", univers: "Énergie" },
  energie_gaz: { slug: "energie_gaz", label: "🔥 Gaz", univers: "Énergie" },
};

// Catégories IA Conseil requises par le diagnostic (§4 du PLAN "Fusionner la
// trame IA Conseil dans Nouveau diagnostic") : pas de correspondance 1:1
// stricte entre servicePrincipal et catégorie — "Pack Box + Mobile" ouvre
// deux sessions, "Multi-lignes" est traité comme "mobile" faute de slug dédié
// (la question nb_lignes de la trame mobile capture déjà le multi-lignes).
function categoriesRequises(univers: string[], servicePrincipal: string): string[] {
  const categories: string[] = [];
  if (univers.includes("Télécom")) {
    if (servicePrincipal === "Box / Fibre uniquement") categories.push("box");
    else if (servicePrincipal === "Pack Box + Mobile") categories.push("mobile", "box");
    else categories.push("mobile");
  }
  if (univers.includes("Énergie")) categories.push("energie_elec", "energie_gaz");
  return categories;
}

// Étape 3 du diagnostic fusionné — remplace les anciennes étapes Situation +
// Recommandations : après l'étape Identité, la situation ET les recommandations
// pour Télécom/Énergie sont pilotées par le moteur de trame adaptative IA
// Conseil (une session par catégorie requise), Abonnements/Assurances gardent
// l'ancien mini-formulaire manuel (aucune trame IA Conseil n'existe pour ces
// univers). Voir PLAN "Fusionner la trame IA Conseil dans Nouveau diagnostic".
export function EtapeTrame({ state, dispatch, onTermine }: EtapeTrameProps) {
  const iaConseilClientProspect = useIaConseilClientProspect();
  const iaConseilClientClient = useIaConseilClientClient();
  const creerSession = useCreerSessionTrame();
  const fournisseurs = useIaConseilFournisseurs();
  const fournisseurNomParId = useMemo(() => {
    const map = new Map<string, string>();
    for (const f of fournisseurs.data ?? []) map.set(f.id, f.nom);
    return map;
  }, [fournisseurs.data]);

  const categories = useMemo(
    () => categoriesRequises(state.univers, state.servicePrincipal),
    [state.univers, state.servicePrincipal]
  );

  const clientConseilId = state.trame.clientConseilId;
  const clientRequisRef = useRef(false);
  useEffect(() => {
    if (clientConseilId || clientRequisRef.current) return;
    if (!state.identite.entiteId || !state.identite.entiteType) return;
    clientRequisRef.current = true;
    const mutation = state.identite.entiteType === "prospect" ? iaConseilClientProspect : iaConseilClientClient;
    // mutateAsync + .then/.catch plutôt que mutate(vars, {onSuccess, onError}) :
    // ces callbacks-là sont attachés à l'observer du hook et ne se déclenchent
    // pas de façon fiable si le composant a été démonté entre-temps — ce qui
    // arrive systématiquement ici en dev avec reactStrictMode (mount → cleanup
    // → mount) : la requête aboutit bien côté réseau, mais le callback est
    // perdu et clientConseilId ne se pose jamais (diagnostic bloqué sans
    // erreur visible). mutateAsync retourne une Promise directement liée à
    // l'appel, indépendante du cycle de vie du composant.
    mutation
      .mutateAsync(state.identite.entiteId as never)
      .then((data) => dispatch({ type: "SET_CLIENT_CONSEIL_ID", id: data.id }))
      .catch(() => {
        clientRequisRef.current = false;
        toast.error("Impossible d'initialiser la session IA Conseil.");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientConseilId, state.identite.entiteId, state.identite.entiteType]);

  const sessionsRequisesRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (!clientConseilId) return;
    for (const categorie of categories) {
      if (state.trame.sessions[categorie] || sessionsRequisesRef.current.has(categorie)) continue;
      sessionsRequisesRef.current.add(categorie);
      // Voir commentaire ci-dessus : mutateAsync plutôt que mutate(vars, {onSuccess, onError}).
      creerSession
        .mutateAsync({ client_id: clientConseilId, categorie_slug: categorie })
        .then((session) => dispatch({ type: "SET_SESSION_ID", categorieSlug: categorie, sessionId: session.id }))
        .catch(() => {
          sessionsRequisesRef.current.delete(categorie);
          toast.error(`Impossible de démarrer la trame « ${CATEGORIE_META[categorie]?.label ?? categorie} ».`);
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientConseilId, categories, state.trame.sessions]);

  const ongletsTrame = categories.map((slug) => CATEGORIE_META[slug]).filter((m): m is CategorieMeta => Boolean(m));
  const premierOnglet = ongletsTrame[0]?.slug ?? (state.univers.includes("Abonnements") ? "abonnements" : "assurances");
  const [ongletActif, setOngletActif] = useState(premierOnglet);

  if (categories.length === 0 && !state.univers.includes("Abonnements") && !state.univers.includes("Assurances")) {
    return <p className="text-sm text-muted-foreground">Aucun univers sélectionné à l&apos;étape précédente.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Situation & recommandations</h2>
        <p className="text-sm text-muted-foreground">
          Répondez aux questions de chaque onglet — le moteur s&apos;arrête dès qu&apos;il a assez d&apos;informations.
        </p>
      </div>

      <Tabs value={ongletActif} onValueChange={setOngletActif}>
        <TabsList className="flex-wrap">
          {ongletsTrame.map((meta) => (
            <TabsTrigger key={meta.slug} value={meta.slug}>
              {meta.label}
            </TabsTrigger>
          ))}
          {state.univers.includes("Abonnements") && <TabsTrigger value="abonnements">🎬 Abonnements</TabsTrigger>}
          {state.univers.includes("Assurances") && <TabsTrigger value="assurances">🛡️ Assurances</TabsTrigger>}
        </TabsList>

        {ongletsTrame.map((meta) => {
          const sessionId = state.trame.sessions[meta.slug];
          return (
            <TabsContent key={meta.slug} value={meta.slug} className="space-y-4">
              {!clientConseilId || !sessionId ? (
                <Skeleton className="h-96 w-full" />
              ) : (
                <SessionTrameWorkspace clientId={clientConseilId} sessionId={sessionId} />
              )}
            </TabsContent>
          );
        })}

        {state.univers.includes("Abonnements") && (
          <TabsContent value="abonnements" className="space-y-4">
            <BlocAbonnementsInput state={state} dispatch={dispatch} />
          </TabsContent>
        )}

        {state.univers.includes("Assurances") && (
          <TabsContent value="assurances" className="space-y-4">
            <Card>
              <CardContent className="p-4 text-sm text-muted-foreground">
                Aucune offre Assurances au catalogue pour le moment.
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Clôture — restitution par univers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {ongletsTrame.map((meta) => {
            const sessionId = state.trame.sessions[meta.slug];
            if (!sessionId) return null;
            return (
              <CategorieClotureCard
                key={meta.slug}
                meta={meta}
                sessionId={sessionId}
                state={state}
                fournisseurNomParId={fournisseurNomParId}
                onTermine={onTermine}
              />
            );
          })}

          {state.univers.includes("Abonnements") && (
            <PanierClotureCard state={state} dispatch={dispatch} univers="Abonnements" onTermine={onTermine} />
          )}

          {state.panier.length === 0 && ongletsTrame.length === 0 && (
            <p className="text-sm text-muted-foreground">Répondez aux questions ci-dessus pour obtenir des recommandations.</p>
          )}

          <Button
            type="button"
            variant="outline"
            onClick={() => {
              onTermine();
              const { entiteType, entiteId } = state.identite;
              if (entiteType && entiteId) window.location.assign(`/${entiteType === "client" ? "clients" : "prospects"}/${entiteId}`);
            }}
          >
            Terminer le diagnostic
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function BlocAbonnementsInput({ state, dispatch }: { state: DiagnosticState; dispatch: DiagnosticDispatch }) {
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
        <CardTitle className="text-base">🎬 Abonnements actuels</CardTitle>
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
                <Button type="button" variant="ghost" size="icon" onClick={() => dispatch({ type: "REMOVE_ABONNEMENT", id: a.id })}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <p className="text-sm text-muted-foreground">
              Total abonnements : <strong>{total.toFixed(2)} €/mois</strong> ({(total * 12).toFixed(2)} €/an)
            </p>
            {state.abonnements.map((a) => (
              <BlocComparaisonAbonnement key={a.id} abonnement={a} state={state} dispatch={dispatch} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function BlocComparaisonAbonnement({
  abonnement,
  dispatch,
}: {
  abonnement: DiagnosticState["abonnements"][number];
  state: DiagnosticState;
  dispatch: DiagnosticDispatch;
}) {
  const query = useOffresComparees(
    { univers: "Abonnements", categorie: abonnement.categorie, cout_actuel_mensuel: abonnement.cout },
    abonnement.cout > 0
  );

  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  const offres = (query.data ?? []).filter((o) => o.prix_mensuel < abonnement.cout).slice(0, 3);
  if (offres.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">🎬 {abonnement.nom} — offres moins chères</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {offres.map((offre) => (
          <OffreCard
            key={offre.id}
            offre={offre}
            auPanier={false}
            onAjouter={() =>
              dispatch({
                type: "ADD_PANIER",
                item: {
                  id: `Abonnements-${abonnement.categorie}-${offre.id}`,
                  univers: "Abonnements",
                  categorie: abonnement.categorie,
                  coutActuelMensuel: abonnement.cout,
                  offre,
                },
              })
            }
          />
        ))}
      </CardContent>
    </Card>
  );
}

function OffreCard({ offre, auPanier, onAjouter }: { offre: OffreComparee; auPanier: boolean; onAjouter: () => void }) {
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <div>
        <p className="font-medium">{offre.nom}</p>
        <p className="text-sm text-muted-foreground">{offre.fournisseur}</p>
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

// Résout le client_id CRM (client miroir si prospect) — même logique que
// l'ancienne EtapeRecommandations.tsx (client_id toujours requis par Dossier).
async function resoudreClientId(
  state: DiagnosticState,
  clientMiroirProspect: ReturnType<typeof useClientMiroirProspect>,
  creerClient: ReturnType<typeof clientsResource.useCreate>,
  onTermine: () => void
): Promise<number | null> {
  if (state.identite.entiteType === "client" && state.identite.entiteId) return state.identite.entiteId;

  if (state.identite.entiteType === "prospect" && state.identite.entiteId) {
    try {
      const client = await clientMiroirProspect.mutateAsync(state.identite.entiteId);
      return client.id;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        onTermine();
        toast.error("Ce prospect n'existe plus (fiche supprimée) — le diagnostic a été réinitialisé, recommencez.");
        return null;
      }
      if (err instanceof ApiError && err.status === 409) {
        const prospect = await apiFetch<Prospect>(`/prospects/${state.identite.entiteId}`);
        if (!prospect.client_id) throw err;
        toast.info("Ce prospect a déjà été converti en client — la fiche client existante est utilisée.");
        return prospect.client_id;
      }
      throw err;
    }
  }

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
  return client.id;
}

function CategorieClotureCard({
  meta,
  sessionId,
  state,
  fournisseurNomParId,
  onTermine,
}: {
  meta: CategorieMeta;
  sessionId: string;
  state: DiagnosticState;
  fournisseurNomParId: Map<string, string>;
  onTermine: () => void;
}) {
  const router = useRouter();
  const sessionQuery = useSessionTrame(sessionId);
  const recommandationsQuery = useRecommandations(sessionId);
  const clientMiroirProspect = useClientMiroirProspect();
  const creerClient = clientsResource.useCreate();
  const majProspect = prospectsResource.useUpdate();
  const majClient = clientsResource.useUpdate();
  const creerContrat = contratsResource.useCreate();
  const creerComparaison = useCreerComparaisonOffre();
  const creerDossier = useCreerDossier();
  const envoyerLienEmail = useEnvoyerLienClientDossier();
  const [envoyerEmail, setEnvoyerEmail] = useState(true);
  const [genererEnCours, setGenererEnCours] = useState(false);

  const session = sessionQuery.data;
  const terminee = session?.etat === "terminee";
  const recommandations = recommandationsQuery.data ?? [];
  const meilleure = recommandations[0];
  const reponses = session?.reponses ?? {};

  if (!terminee) {
    return (
      <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm text-muted-foreground">
        <span>{meta.label} — trame en cours</span>
      </div>
    );
  }

  if (!meilleure) {
    return (
      <div className="flex items-center justify-between rounded-md border px-3 py-2 text-sm text-muted-foreground">
        <span>{meta.label} — aucune offre recommandée au catalogue.</span>
      </div>
    );
  }

  const fournisseurNom = meilleure.offre?.fournisseur_id ? fournisseurNomParId.get(meilleure.offre.fournisseur_id) : undefined;
  const coutActuelMensuel = Number(reponses["cout_actuel_mensuel"] ?? 0);
  const operateurActuel = typeof reponses["operateur_actuel"] === "string" ? (reponses["operateur_actuel"] as string) : undefined;

  async function genererRestitution() {
    setGenererEnCours(true);
    try {
      const clientId = await resoudreClientId(state, clientMiroirProspect, creerClient, onTermine);
      if (!clientId) return;
      const estProspect = state.identite.entiteType === "prospect";

      if (operateurActuel && coutActuelMensuel > 0) {
        await creerContrat.mutateAsync({
          client_id: clientId,
          univers: meta.univers,
          categorie: meta.label.replace(/^\S+\s/, ""),
          fournisseur: operateurActuel,
          cout_mensuel: coutActuelMensuel,
          statut_contrat: "Actuel",
        });
      }

      await creerComparaison.mutateAsync({
        client_id: clientId,
        univers: meta.univers,
        categorie: meta.slug,
        cout_actuel_mensuel: coutActuelMensuel,
        offre_recommandee_id: null,
        offres_comparees: recommandations.map((r) => ({
          offre_id: r.offre_id,
          nom: r.offre?.nom ?? null,
          fournisseur: (r.offre?.fournisseur_id && fournisseurNomParId.get(r.offre.fournisseur_id)) ?? null,
          prix_mensuel: r.offre?.prix_mensuel ?? null,
          economie_mensuelle: r.economie_mensuelle,
          frais_annexes_total: r.offre?.frais_mise_en_service ?? null,
          comparable: true,
        })),
        economie_mensuelle_estimee: meilleure.economie_mensuelle ?? 0,
        economie_annuelle_estimee: meilleure.economie_annuelle ?? 0,
        contexte: "IA Conseil",
      });

      const dossier = await creerDossier.mutateAsync({
        client_id: clientId,
        univers: meta.univers,
        fournisseur_cible: fournisseurNom,
        economie_annuelle_estimee: meilleure.economie_annuelle ?? 0,
        frais_annexes_cible: meilleure.offre?.frais_mise_en_service ?? 0,
        est_prospect: estProspect,
      });

      await downloadBackendFile(
        `/dossiers/${dossier.id}/pdf-restitution`,
        `restitution_${meta.slug}_${(state.identite.prenom + "_" + state.identite.nom).replace(/\s+/g, "_")}.pdf`
      );

      if (envoyerEmail && state.identite.email) {
        await envoyerLienEmail.mutateAsync({ dossierId: dossier.id, canal: "email" });
      }

      const situationReseau = {
        operateur_actuel: operateurActuel,
        cout_mensuel_actuel: coutActuelMensuel || undefined,
        data_go: reponses["conso_data_go"] != null ? String(reponses["conso_data_go"]) : undefined,
        roaming_europe: typeof reponses["roaming_ue"] === "string" ? (reponses["roaming_ue"] as string) : undefined,
        sensibilite_prix: typeof reponses["sensibilite_prix"] === "string" ? (reponses["sensibilite_prix"] as string) : undefined,
        satisfaction_reseau: typeof reponses["satisfaction_reseau"] === "string" ? (reponses["satisfaction_reseau"] as string) : undefined,
        veut_rester: typeof reponses["veut_rester"] === "string" ? (reponses["veut_rester"] as string) : undefined,
        defaut_technique: typeof reponses["defaut_technique"] === "string" ? (reponses["defaut_technique"] as string) : undefined,
        economie_estimee_an: meilleure.economie_annuelle ?? 0,
      };
      if (estProspect && state.identite.entiteId) {
        await majProspect.mutateAsync({ id: state.identite.entiteId, values: situationReseau });
      } else if (!estProspect && clientId) {
        await majClient.mutateAsync({ id: clientId, values: situationReseau });
      }

      toast.success(`Restitution ${meta.label} générée — dossier créé et PDF téléchargé.`);
      if (estProspect && state.identite.entiteId) router.push(`/prospects/${state.identite.entiteId}`);
      else router.push(`/clients/${clientId}`);
    } catch {
      toast.error(`Échec de la génération de la restitution ${meta.label}.`);
    } finally {
      setGenererEnCours(false);
    }
  }

  return (
    <div className="space-y-2 rounded-md border p-3">
      <p className="text-sm font-medium">
        {meta.label} — {meilleure.offre?.nom ?? "Offre"} {fournisseurNom ? `(${fournisseurNom})` : ""}
      </p>
      <p className="text-sm text-emerald-700">Économie estimée : {(meilleure.economie_annuelle ?? 0).toFixed(2)} €/an</p>
      {state.identite.email && (
        <div className="flex items-center gap-2">
          <Checkbox checked={envoyerEmail} onCheckedChange={(checked) => setEnvoyerEmail(checked === true)} />
          <Label className="font-normal text-xs">Envoyer aussi le lien de suivi par email au client</Label>
        </div>
      )}
      <Button type="button" size="sm" onClick={genererRestitution} disabled={genererEnCours}>
        {genererEnCours ? "Génération en cours…" : `Générer restitution ${meta.label}`}
      </Button>
    </div>
  );
}

function PanierClotureCard({
  state,
  dispatch,
  univers,
  onTermine,
}: {
  state: DiagnosticState;
  dispatch: DiagnosticDispatch;
  univers: string;
  onTermine: () => void;
}) {
  const router = useRouter();
  const clientMiroirProspect = useClientMiroirProspect();
  const creerClient = clientsResource.useCreate();
  const majProspect = prospectsResource.useUpdate();
  const majClient = clientsResource.useUpdate();
  const creerContrat = contratsResource.useCreate();
  const creerComparaison = useCreerComparaisonOffre();
  const creerDossier = useCreerDossier();
  const envoyerLienEmail = useEnvoyerLienClientDossier();
  const [genererEnCours, setGenererEnCours] = useState(false);

  const items = state.panier.filter((p) => p.univers === univers);
  if (items.length === 0) return null;

  const meilleur = items.reduce((a, b) => (b.offre.economie_annuelle > a.offre.economie_annuelle ? b : a));
  const categories = new Set(items.map((i) => i.categorie));
  const coutActuelMensuel = state.abonnements.filter((a) => categories.has(a.categorie)).reduce((sum, a) => sum + a.cout, 0);

  async function genererRestitution() {
    setGenererEnCours(true);
    try {
      const clientId = await resoudreClientId(state, clientMiroirProspect, creerClient, onTermine);
      if (!clientId) return;
      const estProspect = state.identite.entiteType === "prospect";

      const abonnementsConcernes = state.abonnements.filter((a) => categories.has(a.categorie));
      const fournisseurActuel = abonnementsConcernes.map((a) => a.nom).join(", ") || undefined;
      if (fournisseurActuel && coutActuelMensuel > 0) {
        await creerContrat.mutateAsync({
          client_id: clientId,
          univers,
          categorie: meilleur.categorie,
          fournisseur: fournisseurActuel,
          cout_mensuel: coutActuelMensuel,
          statut_contrat: "Actuel",
        });
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
          comparable: true,
        })),
        economie_mensuelle_estimee: meilleur.offre.economie_mensuelle,
        economie_annuelle_estimee: meilleur.offre.economie_annuelle,
        contexte: "Diagnostic conseiller",
      });

      const dossier = await creerDossier.mutateAsync({
        client_id: clientId,
        univers,
        fournisseur_cible: meilleur.offre.fournisseur ?? undefined,
        offre_cible_id: meilleur.offre.id,
        economie_annuelle_estimee: meilleur.offre.economie_annuelle,
        frais_annexes_cible: meilleur.offre.frais_annexes_total,
        est_prospect: estProspect,
      });

      await downloadBackendFile(
        `/dossiers/${dossier.id}/pdf-restitution`,
        `restitution_${univers.toLowerCase()}_${(state.identite.prenom + "_" + state.identite.nom).replace(/\s+/g, "_")}.pdf`
      );

      if (state.identite.email) {
        await envoyerLienEmail.mutateAsync({ dossierId: dossier.id, canal: "email" });
      }

      if (estProspect && state.identite.entiteId) {
        await majProspect.mutateAsync({ id: state.identite.entiteId, values: { economie_estimee_an: meilleur.offre.economie_annuelle } });
      } else if (!estProspect) {
        await majClient.mutateAsync({ id: clientId, values: { economie_estimee_an: meilleur.offre.economie_annuelle } });
      }

      toast.success(`Restitution ${univers} générée — dossier créé et PDF téléchargé.`);
      for (const item of items) dispatch({ type: "REMOVE_PANIER", id: item.id });
      if (estProspect && state.identite.entiteId) router.push(`/prospects/${state.identite.entiteId}`);
      else router.push(`/clients/${clientId}`);
    } catch {
      toast.error(`Échec de la génération de la restitution ${univers}.`);
    } finally {
      setGenererEnCours(false);
    }
  }

  return (
    <div className="space-y-2 rounded-md border p-3">
      <p className="text-sm font-medium">
        {univers} — {items.length} offre(s) au panier, meilleure : {meilleur.offre.nom} ({meilleur.offre.fournisseur})
      </p>
      <p className="text-sm text-emerald-700">Économie estimée : {meilleur.offre.economie_annuelle.toFixed(2)} €/an</p>
      <Button type="button" size="sm" onClick={genererRestitution} disabled={genererEnCours}>
        {genererEnCours ? "Génération en cours…" : `Générer restitution ${univers}`}
      </Button>
    </div>
  );
}
