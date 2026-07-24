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
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(null);
    }
  }

  if (loading) return <div className="text-center py-16"><Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" /></div>;
  if (!ctx) return <div className="text-center py-16 text-danger">Erreur : {error}</div>;

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
  const valide = doc.statut === "valide";
  const rejete = doc.statut === "rejete";

  return (
    <div className={`bg-white rounded-2xl border p-5 ${valide ? "border-emerald-200 bg-emerald-50/30" : rejete ? "border-red-200" : "border-slate-200"}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="font-semibold flex items-center gap-2">
            {valide && <CheckCircle2 className="w-5 h-5 text-accent" />}
            {rejete && <XCircle className="w-5 h-5 text-danger" />}
            {doc.label_affiche}
          </h3>
          {doc.motif_rejet && (
            <p className="text-sm text-danger mt-1">⚠️ {doc.motif_rejet}</p>
          )}
        </div>
      </div>

      {!valide && (
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
