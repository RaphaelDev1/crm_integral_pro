"use client";

import { useState } from "react";
import { Loader2, Send } from "lucide-react";
import { DemarcheAFournir } from "@/lib/api";
import { LABELS_TYPE_DEMARCHE } from "@/lib/demarches";

export function DemarcheCard({
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
            {champ.type === "choix" && champ.options ? (
              <div className="grid grid-cols-2 gap-2">
                {champ.options.map((opt) => (
                  <button
                    key={opt.valeur}
                    type="button"
                    onClick={() => setValeurs({ ...valeurs, [champ.cle]: opt.valeur })}
                    className={`rounded-lg border-2 px-3 py-2 text-sm font-medium transition-all ${
                      valeurs[champ.cle] === opt.valeur
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            ) : (
              <input
                type="text"
                value={valeurs[champ.cle] || ""}
                onChange={(e) => setValeurs({ ...valeurs, [champ.cle]: e.target.value })}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            )}
            {champ.aide && <p className="text-xs text-slate-500 mt-1">{champ.aide}</p>}
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
