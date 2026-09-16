"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getContexte, uploadDocument, TokenContexte, DocumentDemande } from "@/lib/api";
import { Upload, Camera, CheckCircle2, XCircle, ArrowLeft, Loader2, MessageCircleQuestion } from "lucide-react";

export default function DocumentsPage({ params }: { params: { token: string } }) {
  const router = useRouter();
  const [ctx, setCtx] = useState<TokenContexte | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getContexte(params.token)
      .then(setCtx)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [params.token]);

  async function handleUpload(typeDoc: string, files: File[]) {
    setError(null);
    setUploading(typeDoc);
    try {
      // Envoyés séquentiellement (pas en parallèle) pour rester simple côté
      // serveur et pouvoir arrêter proprement dès le premier échec.
      for (const file of files) {
        await uploadDocument(params.token, typeDoc, file);
      }
      const nouveauCtx = await getContexte(params.token);
      setCtx(nouveauCtx);
      // La page d'accueil (/dossier/[token]) est un Server Component mis en
      // cache côté client par Next.js (routeur App Router, ~30s) : sans ce
      // refresh(), y revenir juste après l'envoi montre encore l'ancien statut
      // "à fournir" pendant toute la durée du cache.
      router.refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(null);
    }
  }

  if (loading) return <div className="text-center py-16"><Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" /></div>;
  if (!ctx) return <div className="text-center py-16 text-danger">Erreur : {error}</div>;

  // Le serveur refuse déjà l'upload tant que le questionnaire n'est pas
  // complet (voir POST /{token}/documents) — ce garde-fou évite juste au
  // client d'arriver ici par un lien direct et de le découvrir après coup.
  if (!ctx.audit_complet) {
    return (
      <main className="text-center py-16">
        <MessageCircleQuestion className="w-16 h-16 text-primary mx-auto mb-4" />
        <h2 className="text-2xl font-bold mb-2">Répondez d&apos;abord au questionnaire</h2>
        <p className="text-slate-600 mb-6">
          Quelques questions sur votre situation sont nécessaires avant l&apos;envoi de vos documents.
        </p>
        <Link
          href={`/dossier/${params.token}/questionnaire`}
          className="inline-block bg-primary text-white px-6 py-3 rounded-lg font-semibold hover:bg-primary/90 transition"
        >
          Répondre aux questions →
        </Link>
      </main>
    );
  }

  // Un document client démarre désormais toujours à "en_attente" (plus jamais
  // validé automatiquement, voir portail_public.py::uploader_document) — donc
  // "tous reçus" ne peut plus se limiter à "valide"/"recu" sous peine de ne
  // (presque) jamais afficher les étapes suivantes tant que le conseiller n'a
  // pas cliqué "Valider" sur chaque document.
  const tousRecus =
    ctx.documents_a_fournir.length > 0 &&
    ctx.documents_a_fournir.every((doc) =>
      doc.statut === "valide" || doc.statut === "recu" || doc.statut === "en_attente" || doc.statut === "erreur"
    );
  // Les trois étapes pouvant rester après l'envoi des documents. Auparavant
  // seule une branche if/else était affichée (la situation masquait le débit,
  // qui n'était mentionné nulle part ici) : le message annonçait "il reste
  // une dernière étape" alors qu'il en restait potentiellement deux. On
  // recense maintenant chaque étape restante et on les affiche toutes, avec
  // un accès direct à chacune (dont le débit, qui gardait un point d'entrée
  // séparé sur la page d'accueil mais n'était jamais proposé ici).
  // Le type "facture" (lien prospect) n'attend pas UNE facture précise mais
  // toutes celles que le prospect a sous la main (mobile, box, énergie...) —
  // on le dit explicitement plutôt que de laisser le texte générique
  // "formats acceptés", pour maximiser ce qu'on reçoit et pouvoir tout
  // comparer d'un coup.
  const demandeToutesFactures = ctx.documents_a_fournir.some((doc) => doc.type_document === "facture");
  const demarchesRestantes = ctx.peut_renseigner_demarches && ctx.demarches_a_completer.length > 0;
  const situationRestante = ctx.peut_renseigner_situation && !ctx.situation_renseignee;
  const speedtestRestant = ctx.peut_transmettre_speedtest && !ctx.speedtest_fait;
  const etapesRestantes = [demarchesRestantes, situationRestante, speedtestRestant].filter(Boolean).length;

  return (
    <main>
      <button
        onClick={() => router.push(`/dossier/${params.token}`)}
        className="flex items-center gap-2 text-slate-600 mb-6 hover:text-primary"
      >
        <ArrowLeft className="w-4 h-4" /> Retour
      </button>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-xl font-bold text-primary mb-2">Envoyez vos documents</h2>
        {demandeToutesFactures ? (
          <p className="text-slate-600 text-sm">
            Envoyez-nous toutes les factures que vous avez sous la main (mobile, box, énergie...) :
            on s&apos;occupe de tout comparer pour vous. Formats acceptés : PDF, JPG, PNG (max 10 Mo).
          </p>
        ) : (
          <p className="text-slate-600 text-sm">
            Formats acceptés : PDF, JPG, PNG (max 10 Mo). Votre conseiller vérifiera vos documents
            dès réception.
          </p>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-danger p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {demandeToutesFactures && <PasDeDocument />}

      {tousRecus && etapesRestantes > 0 && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 p-4 rounded-lg mb-6 text-center">
          <p className="font-semibold mb-1">✅ Documents bien reçus.</p>
          <p className="text-sm mb-3">
            {etapesRestantes === 1
              ? "Il reste une dernière étape :"
              : `Il reste ${etapesRestantes} étapes :`}
          </p>
          <div className="flex flex-col gap-2 items-center">
            {demarchesRestantes && (
              <button
                onClick={() => router.push(`/dossier/${params.token}/demarches`)}
                className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90 w-full max-w-xs"
              >
                Compléter mes informations →
              </button>
            )}
            {situationRestante && (
              <button
                onClick={() => router.push(`/dossier/${params.token}/situation`)}
                className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90 w-full max-w-xs"
              >
                Répondre aux questions sur ma situation →
              </button>
            )}
            {speedtestRestant && (
              <button
                onClick={() => router.push(`/dossier/${params.token}/speedtest`)}
                className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90 w-full max-w-xs"
              >
                Tester mon débit →
              </button>
            )}
          </div>
        </div>
      )}

      {tousRecus && etapesRestantes === 0 && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 p-4 rounded-lg mb-6 text-center">
          <p className="font-semibold mb-1">✅ Documents bien reçus.</p>
          <button
            onClick={() => router.push(`/dossier/${params.token}`)}
            className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            Retour à l&apos;accueil
          </button>
        </div>
      )}

      <div className="space-y-4">
        {ctx.documents_a_fournir.map((doc) => (
          <DocumentCard
            key={doc.type_document}
            doc={doc}
            uploading={uploading === doc.type_document}
            onUpload={(files) => handleUpload(doc.type_document, files)}
          />
        ))}
      </div>
    </main>
  );
}

function DocumentCard({
  doc,
  uploading,
  onUpload,
}: {
  doc: DocumentDemande;
  uploading: boolean;
  onUpload: (files: File[]) => void;
}) {
  // "facture" (lien prospect) accepte plusieurs fichiers — un prospect peut
  // avoir une facture mobile ET une facture box à transmettre — donc la zone
  // de dépôt reste affichée même après un premier envoi, avec la liste de ce
  // qui a déjà été reçu. Les autres types (CNI/RIB/justificatif, flux client)
  // restent à un seul document canonique : la zone se masque une fois transmis,
  // comme avant.
  const acceptePlusieurs = doc.type_document === "facture";

  // Un document transmis (par un prospect via "recu", ou par un client via
  // "en_attente"/"erreur"/"valide") ne doit plus jamais réafficher la zone de
  // dépôt — seul un document encore à fournir ou rejeté doit pouvoir être
  // (re)déposé. La validation d'un document client n'est désormais jamais
  // automatique (voir backend/routers/portail_public.py::uploader_document) :
  // "en_attente" veut dire "bien reçu, en cours de vérification par votre
  // conseiller", pas "en attente d'envoi".
  const valide = doc.statut === "valide";
  const enAttenteVerification = doc.statut === "en_attente" || doc.statut === "recu" || doc.statut === "erreur";
  const recu = valide || enAttenteVerification;
  const rejete = doc.statut === "rejete";
  const masquerZoneDepot = recu && !acceptePlusieurs;

  return (
    <div className={`bg-white rounded-2xl border p-5 ${valide ? "border-emerald-200 bg-emerald-50/30" : rejete ? "border-red-200" : enAttenteVerification ? "border-amber-200 bg-amber-50/30" : "border-slate-200"}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="font-semibold flex items-center gap-2">
            {valide && <CheckCircle2 className="w-5 h-5 text-accent" />}
            {rejete && <XCircle className="w-5 h-5 text-danger" />}
            {doc.label_affiche}
          </h3>
          {enAttenteVerification && (
            <p className="text-sm text-amber-700 mt-1">Reçu, en attente de vérification par votre conseiller.</p>
          )}
          {doc.motif_rejet && (
            <p className="text-sm text-danger mt-1">⚠️ {doc.motif_rejet}</p>
          )}
        </div>
      </div>

      {doc.fichiers_recus.length > 0 && (
        <ul className="mb-3 space-y-1">
          {doc.fichiers_recus.map((f) => (
            <li key={f.document_id} className="flex items-center gap-2 text-sm text-slate-600 bg-slate-50 rounded-lg px-3 py-2">
              <CheckCircle2 className="w-4 h-4 text-accent shrink-0" />
              <span className="truncate">{f.nom_fichier || "Fichier"}</span>
              {f.date_upload && <span className="text-xs text-slate-400 ml-auto shrink-0">{f.date_upload}</span>}
            </li>
          ))}
        </ul>
      )}

      {acceptePlusieurs && recu && (
        <p className="text-sm text-slate-500 mb-3">Vous pouvez ajouter une autre facture si besoin (ex. box et mobile).</p>
      )}

      {!masquerZoneDepot && (
        uploading ? (
          <div className="border-2 border-dashed rounded-lg p-6 text-center border-slate-300 bg-slate-50">
            <div className="flex items-center justify-center gap-2 text-slate-600">
              <Loader2 className="w-5 h-5 animate-spin" /> Analyse en cours...
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <label className="block w-full cursor-pointer">
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                multiple={acceptePlusieurs}
                disabled={uploading}
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? []);
                  if (files.length > 0) onUpload(files);
                  e.target.value = "";
                }}
                className="hidden"
              />
              <div className="border-2 border-dashed rounded-lg p-6 text-center transition border-primary/40 hover:border-primary hover:bg-primary/5">
                <Upload className="w-8 h-8 text-primary mx-auto mb-2" />
                <p className="font-medium text-primary">Choisir un fichier</p>
                <p className="text-xs text-slate-500 mt-1">PDF, JPG ou PNG</p>
              </div>
            </label>
            <label className="block w-full cursor-pointer">
              <input
                type="file"
                accept="image/*"
                capture="environment"
                disabled={uploading}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) onUpload([file]);
                  e.target.value = "";
                }}
                className="hidden"
              />
              <div className="border-2 border-dashed rounded-lg p-6 text-center transition border-primary/40 hover:border-primary hover:bg-primary/5">
                <Camera className="w-8 h-8 text-primary mx-auto mb-2" />
                <p className="font-medium text-primary">Prendre une photo</p>
                <p className="text-xs text-slate-500 mt-1">Avec l&apos;appareil photo</p>
              </div>
            </label>
          </div>
        )
      )}
    </div>
  );
}

// Vous ne trouvez pas votre facture ? Plutôt que de forcer la recherche du
// document (on ne prend que les factures, pas de montant déclaré à la
// place), une simple case à cocher rassure le prospect : ce n'est pas
// bloquant, il pourra l'envoyer plus tard.
function PasDeDocument() {
  const [coche, setCoche] = useState(false);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
      <label className="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={coche}
          onChange={(e) => setCoche(e.target.checked)}
          className="mt-1 w-4 h-4 rounded border-slate-300 text-primary focus:ring-primary/40"
        />
        <span className="text-sm text-slate-700">Je n&apos;ai pas mon document sous la main</span>
      </label>
      {coche && (
        <p className="text-sm text-slate-500 mt-3">
          Pas de souci, vous pourrez nous l&apos;envoyer plus tard.
        </p>
      )}
    </div>
  );
}
