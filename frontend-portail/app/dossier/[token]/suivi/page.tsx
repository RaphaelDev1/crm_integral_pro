import Link from "next/link";
import { getSuivi } from "@/lib/api";
import { AlertCircle, ArrowLeft, CheckCircle2, Circle, Clock, Hourglass } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function SuiviPage({
  params,
}: {
  params: { token: string };
}) {
  let suivi;
  try {
    suivi = await getSuivi(params.token);
  } catch (e: any) {
    return (
      <main className="text-center py-16">
        <AlertCircle className="w-16 h-16 text-danger mx-auto mb-4" />
        <h2 className="text-2xl font-bold mb-2">Suivi indisponible</h2>
        <p className="text-slate-600">{e.message || "Ce lien ne permet pas de voir le suivi du dossier."}</p>
        <Link href={`/dossier/${params.token}`} className="inline-block mt-6 text-primary font-medium">
          ← Retour à mon dossier
        </Link>
      </main>
    );
  }

  return (
    <main>
      <Link
        href={`/dossier/${params.token}`}
        className="flex items-center gap-2 text-slate-600 mb-6 hover:text-primary"
      >
        <ArrowLeft className="w-4 h-4" /> Retour
      </Link>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-xl font-bold text-primary mb-2">Suivi de votre dossier</h2>
        {suivi.prochaine_action && (
          <p className="text-slate-600 text-sm">{suivi.prochaine_action}</p>
        )}
        {suivi.delai_estime && (
          <p className="flex items-start gap-2 text-xs text-slate-500 mt-3 bg-slate-50 rounded-lg px-3 py-2">
            <Hourglass className="w-4 h-4 shrink-0 mt-0.5" />
            {suivi.delai_estime}
          </p>
        )}
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
        <ol className="relative border-l-2 border-slate-200 pl-6 space-y-6">
          {suivi.etapes.map((etape) => (
            <li key={etape.cle} className="relative">
              <span
                className={`absolute -left-[31px] flex items-center justify-center w-6 h-6 rounded-full ${
                  etape.statut === "termine"
                    ? "bg-emerald-100 text-accent"
                    : etape.statut === "en_cours"
                    ? "bg-blue-100 text-primary"
                    : "bg-slate-100 text-slate-400"
                }`}
              >
                {etape.statut === "termine" ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : etape.statut === "en_cours" ? (
                  <Clock className="w-4 h-4" />
                ) : (
                  <Circle className="w-3 h-3" />
                )}
              </span>
              <div
                className={`font-medium ${
                  etape.statut === "a_venir" ? "text-slate-400" : "text-slate-900"
                }`}
              >
                {etape.label}
              </div>
              {etape.date && <div className="text-xs text-slate-400 mt-0.5">{etape.date}</div>}
            </li>
          ))}
        </ol>
      </div>
    </main>
  );
}
