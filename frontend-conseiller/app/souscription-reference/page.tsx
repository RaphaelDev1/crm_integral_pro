"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

// Page de référence ouverte à côté de la fenêtre Playwright par
// OffreCibleSection.handlePreRemplir (dossiers/[id]/page.tsx) — pas de layout
// (conseiller) volontairement : dans une fenêtre popup positionnée sur une
// moitié d'écran, la sidebar/header de l'appli n'auraient fait que réduire
// la place utile. Toutes les données affichées viennent de la query string
// (pas de nouvel appel réseau) — le conseiller les a déjà sous les yeux dans
// la fiche dossier qui a ouvert cette fenêtre.
export default function SouscriptionReferencePage() {
  return (
    <Suspense>
      <SouscriptionReferenceContent />
    </Suspense>
  );
}

function SouscriptionReferenceContent() {
  const params = useSearchParams();

  const client = {
    prenom: params.get("prenom") || "",
    nom: params.get("nom") || "",
    telephone: params.get("telephone") || "",
    email: params.get("email") || "",
    adresse: params.get("adresse") || "",
    codePostal: params.get("code_postal") || "",
    ville: params.get("ville") || "",
    dateNaissance: params.get("date_naissance") || "",
    departementNaissance: params.get("departement_naissance") || "",
    villeNaissance: params.get("ville_naissance") || "",
  };
  const offre = {
    fournisseur: params.get("fournisseur") || "",
    nom: params.get("offre") || "",
    prixMensuel: params.get("prix_mensuel") || "",
    economieAnnuelle: params.get("economie_annuelle") || "",
  };
  const portabilite = {
    conserverNumero: params.get("conserver_numero") || "",
    rio: params.get("rio") || "",
    numeroLigne: params.get("numero_ligne") || "",
    typeSim: params.get("type_sim") || "",
  };
  // Section affichée dès qu'il y a une ligne mobile de référence (indépendamment
  // de ce qui a été répondu) — voir dossiers/[id]/page.tsx:handlePreRemplir, qui
  // passe explicitement ce flag. Ne pas se fier aux 4 champs de portabilité
  // eux-mêmes : ils sont toujours présents dans l'URL (même vides), donc
  // impossibles à distinguer d'un dossier sans ligne mobile.
  const aUneLigneMobile = params.get("a_ligne_mobile") === "1";

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-md mx-auto space-y-4">
        <div>
          <h1 className="text-lg font-bold text-primary">Aide-mémoire souscription</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Reportez ces informations dans le formulaire ouvert à côté — vérifiez et validez vous-même
            avant de finaliser la souscription sur le site de l&apos;opérateur.
          </p>
        </div>

        <section className="bg-white rounded-lg border p-4 space-y-2">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Client</h2>
          <Champ label="Nom" valeur={`${client.prenom} ${client.nom}`.trim()} />
          <Champ label="Téléphone" valeur={client.telephone} />
          <Champ label="Email" valeur={client.email} />
          <Champ label="Adresse" valeur={[client.adresse, client.codePostal, client.ville].filter(Boolean).join(", ")} />
          <Champ label="Date de naissance" valeur={client.dateNaissance} />
          <Champ label="Département de naissance" valeur={client.departementNaissance} />
          <Champ label="Ville de naissance" valeur={client.villeNaissance} />
        </section>

        <section className="bg-white rounded-lg border p-4 space-y-2">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Offre visée</h2>
          <Champ label="Fournisseur" valeur={offre.fournisseur} />
          <Champ label="Offre" valeur={offre.nom} />
          {offre.prixMensuel && <Champ label="Prix mensuel" valeur={`${offre.prixMensuel} €/mois`} />}
          {offre.economieAnnuelle && offre.economieAnnuelle !== "0" && (
            <Champ label="Économie estimée" valeur={`${offre.economieAnnuelle} €/an`} />
          )}
        </section>

        {aUneLigneMobile && (
          <section className="bg-white rounded-lg border p-4 space-y-2">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Portabilité</h2>
            {portabilite.conserverNumero === "non" ? (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">
                ⚠️ NOUVEAU numéro — le client ne conserve pas son numéro actuel.
              </div>
            ) : portabilite.conserverNumero === "oui" ? (
              <Champ label="Conserver le numéro" valeur="Oui" />
            ) : (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">
                ⚠️ Conserver le numéro : non renseigné — à demander au client avant de continuer.
              </div>
            )}
            <Champ label="Numéro de ligne" valeur={portabilite.numeroLigne} />
            <Champ label="RIO" valeur={portabilite.rio} />
            <Champ label="Type de SIM" valeur={portabilite.typeSim === "esim" ? "eSIM" : portabilite.typeSim === "carte_sim" ? "Carte SIM" : ""} />
          </section>
        )}
      </div>
    </div>
  );
}

function Champ({ label, valeur }: { label: string; valeur: string }) {
  if (!valeur) return null;
  return (
    <div className="flex justify-between gap-4 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-right">{valeur}</span>
    </div>
  );
}
