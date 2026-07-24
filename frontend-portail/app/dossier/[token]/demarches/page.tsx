"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getContexte, soumettreChampsDemarche, TokenContexte, DemarcheAFournir } from "@/lib/api";
import { ArrowLeft, Loader2, Send, CheckCircle2 } from "lucide-react";

const LABELS_TYPE_DEMARCHE: Record<string, string> = {
  mandat: "Mandat de représentation",
  resiliation: "Résiliation",
  portabilite: "Portabilité mobile",
  souscription: "Souscription",
  changement_fournisseur: "Changement de fournisseur",
};

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

      {ctx.demarches_a_completer.length === 0 ? (
        <div className="bg-white rounded-2xl border border-emerald-200 bg-emerald-50/30 p-6 flex items-center gap-3">
          <CheckCircle2 className="w-6 h-6 text-accent" />
          <p className="text-slate-700">Rien à compléter pour le moment.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {ctx.demarches_a_completer.map((demarche) => (
            <DemarcheCard key={demarche.demarche_id} demarche={demarche} onSubmit={handleSubmit} />
          ))}
        </div>
      )}
    </main>
  );
}

function DemarcheCard({
  demarche,
  onSubmit,
}: {
  demarche: DemarcheAFournir;
  onSubmit: (demarcheId: number, valeurs: Record<string, string>) => Promise<void>;
}) {
  const [valeurs, setValeurs] = useState<Record<string, string>>(
    Object.fromEntries(demarche.champs.map((c) => [c.cle, c.valeur || ""]))
  );
  const [submitting, setSubmitting] = useState(false);

  const champsRequisRemplis = demarche.champs
    .filter((c) => c.requis)
    .every((c) => (valeurs[c.cle] || "").trim().length > 0);

  async function handleSubmit() {
    setSubmitting(true);
    try {
      await onSubmit(demarche.demarche_id, valeurs);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5">
      <h3 className="font-semibold mb-4">{LABELS_TYPE_DEMARCHE[demarche.type_demarche] || demarche.type_demarche}</h3>
      <div className="space-y-3">
        {demarche.champs.map((champ) => (
          <div key={champ.cle}>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {champ.label} {champ.requis && <span className="text-danger">*</span>}
            </label>
            <input
              type="text"
              value={valeurs[champ.cle] || ""}
              onChange={(e) => setValeurs({ ...valeurs, [champ.cle]: e.target.value })}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
        ))}
      </div>
      <button
        onClick={handleSubmit}
        disabled={!champsRequisRemplis || submitting}
        className="mt-4 w-full flex items-center justify-center gap-2 bg-primary text-white py-2.5 rounded-lg font-semibold hover:bg-primary/90 transition disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        Envoyer
      </button>
    </div>
  );
}
