"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getContexte, uploadDocument, TokenContexte, DocumentDemande } from "@/lib/api";
import { Upload, CheckCircle2, XCircle, ArrowLeft, Loader2 } from "lucide-react";

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

  async function handleUpload(typeDoc: string, file: File) {
    setError(null);
    setUploading(typeDoc);
    try {
      await uploadDocument(params.token, typeDoc, file);
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

  const tousRecus =
    ctx.documents_a_fournir.length > 0 &&
    ctx.documents_a_fournir.every((doc) => doc.statut === "valide" || doc.statut === "recu");
  // Les informations complémentaires (démarches) passent avant le speedtest :
  // sinon un dossier qui n'a besoin que d'informations (pas de speedtest)
  // affichait quand même "il reste le test de débit" comme unique étape
  // restante, alors que c'est du remplissage d'informations qui est attendu.
  const demarchesRestantes = ctx.peut_renseigner_demarches && ctx.demarches_a_completer.length > 0;
  const resteAFaire = !demarchesRestantes && ctx.peut_transmettre_speedtest && !ctx.speedtest_fait;

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
        <p className="text-slate-600 text-sm">
          Formats acceptés : PDF, JPG, PNG (max 10 Mo). Vos documents sont analysés et
          validés automatiquement.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-danger p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {tousRecus && demarchesRestantes && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 p-4 rounded-lg mb-6 text-center">
          <p className="font-semibold mb-1">✅ Documents bien reçus.</p>
          <p className="text-sm mb-3">Il reste une dernière étape : quelques informations à compléter.</p>
          <button
            onClick={() => router.push(`/dossier/${params.token}/demarches`)}
            className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            Compléter mes informations →
          </button>
        </div>
      )}

      {tousRecus && resteAFaire && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 p-4 rounded-lg mb-6 text-center">
          <p className="font-semibold mb-1">✅ Documents bien reçus.</p>
          <p className="text-sm mb-3">Il reste une dernière étape : le test de débit.</p>
          <button
            onClick={() => router.push(`/dossier/${params.token}/speedtest`)}
            className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            Tester mon débit →
          </button>
        </div>
      )}

      {tousRecus && !resteAFaire && !demarchesRestantes && (
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
            onUpload={(file) => handleUpload(doc.type_document, file)}
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
  onUpload: (file: File) => void;
}) {
  // "recu" = document transmis par un prospect (pas encore client, pas de
  // vérification KYC automatique — voir backend/routers/portail_public.py::
  // _uploader_document_prospect) : considéré comme reçu au même titre qu'un
  // document "valide", pour ne pas laisser la zone de dépôt réapparaître
  // après un envoi pourtant réussi.
  const recu = doc.statut === "valide" || doc.statut === "recu";
  const rejete = doc.statut === "rejete";

  return (
    <div className={`bg-white rounded-2xl border p-5 ${recu ? "border-emerald-200 bg-emerald-50/30" : rejete ? "border-red-200" : "border-slate-200"}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="font-semibold flex items-center gap-2">
            {recu && <CheckCircle2 className="w-5 h-5 text-accent" />}
            {rejete && <XCircle className="w-5 h-5 text-danger" />}
            {doc.label_affiche}
          </h3>
          {doc.motif_rejet && (
            <p className="text-sm text-danger mt-1">⚠️ {doc.motif_rejet}</p>
          )}
        </div>
      </div>

      {!recu && (
        <label className={`block w-full ${uploading ? "opacity-50" : "cursor-pointer"}`}>
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            disabled={uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onUpload(file);
            }}
            className="hidden"
          />
          <div className={`border-2 border-dashed rounded-lg p-6 text-center transition ${uploading ? "border-slate-300 bg-slate-50" : "border-primary/40 hover:border-primary hover:bg-primary/5"}`}>
            {uploading ? (
              <div className="flex items-center justify-center gap-2 text-slate-600">
                <Loader2 className="w-5 h-5 animate-spin" /> Analyse en cours...
              </div>
            ) : (
              <>
                <Upload className="w-8 h-8 text-primary mx-auto mb-2" />
                <p className="font-medium text-primary">Choisir un fichier</p>
                <p className="text-xs text-slate-500 mt-1">PDF, JPG ou PNG</p>
              </>
            )}
          </div>
        </label>
      )}
    </div>
  );
}
