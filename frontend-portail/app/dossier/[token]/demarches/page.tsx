"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getContexte, soumettreChampsDemarche, TokenContexte } from "@/lib/api";
import { ArrowLeft, Loader2, CheckCircle2 } from "lucide-react";
import { DemarcheCard } from "@/components/dossier/DemarcheCard";
import { TYPES_QUESTIONNAIRE_SECTEUR } from "@/lib/demarches";

export default function DemarchesPage({ params }: { params: { token: string } }) {
  const router = useRouter();
  const [ctx, setCtx] = useState<TokenContexte | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getContexte(params.token)
      .then(setCtx)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [params.token]);

  async function handleSubmit(demarcheId: number, valeurs: Record<string, string>) {
    setError(null);
    try {
      await soumettreChampsDemarche(params.token, demarcheId, valeurs);
      const nouveauCtx = await getContexte(params.token);
      setCtx(nouveauCtx);
    } catch (e: any) {
      setError(e.message);
    }
  }

  if (loading) return <div className="text-center py-16"><Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" /></div>;
  if (!ctx) return <div className="text-center py-16 text-danger">Erreur : {error}</div>;

  // La trame de questions par secteur (audit_*/portabilite) a sa propre page
  // — voir /dossier/[token]/questionnaire — pour ne pas la faire apparaître
  // deux fois.
  const demarches = ctx.demarches_a_completer.filter((d) => !TYPES_QUESTIONNAIRE_SECTEUR.has(d.type_demarche));

  return (
    <main>
      <button
        onClick={() => router.push(`/dossier/${params.token}`)}
        className="flex items-center gap-2 text-slate-600 mb-6 hover:text-primary"
      >
        <ArrowLeft className="w-4 h-4" /> Retour
      </button>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-xl font-bold text-primary mb-2">Informations complémentaires</h2>
        <p className="text-slate-600 text-sm">
          Ces informations sont nécessaires à votre conseiller pour préparer vos démarches
          (résiliation, portabilité, changement de fournisseur).
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-danger p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {demarches.length === 0 ? (
        <div className="bg-white rounded-2xl border border-emerald-200 bg-emerald-50/30 p-6 flex items-center gap-3">
          <CheckCircle2 className="w-6 h-6 text-accent" />
          <p className="text-slate-700">Rien à compléter pour le moment.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {demarches.map((demarche) => (
            <DemarcheCard key={demarche.demarche_id} demarche={demarche} onSubmit={handleSubmit} />
          ))}
        </div>
      )}
    </main>
  );
}
