import Link from "next/link";
import { getContexte } from "@/lib/api";
import { CheckCircle2, Upload, FileSignature, AlertCircle, Sparkles, FileText, Wifi } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function DossierPage({
  params,
}: {
  params: { token: string };
}) {
  let ctx;
  try {
    ctx = await getContexte(params.token);
  } catch (e: any) {
    return (
      <main className="text-center py-16">
        <AlertCircle className="w-16 h-16 text-danger mx-auto mb-4" />
        <h2 className="text-2xl font-bold mb-2">Lien invalide</h2>
        <p className="text-slate-600">
          Ce lien est expiré, invalide, ou a été révoqué. Contactez votre conseiller.
        </p>
      </main>
    );
  }

  const docsAFournir = ctx.documents_a_fournir.filter((d) => d.statut === "a_fournir" || d.statut === "rejete");
  const tousDocsOk = docsAFournir.length === 0 && ctx.documents_a_fournir.length > 0;
  const mandatOk = !ctx.mandat_statut || ctx.mandat_statut === "signe";
  const speedtestOk = ctx.speedtest_fait || !ctx.peut_transmettre_speedtest;
  const toutEstFait = tousDocsOk && mandatOk && ctx.demarches_a_completer.length === 0 && speedtestOk;

  return (
    <main>
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-2xl font-bold text-primary">
          Bonjour {ctx.prenom_client} !
        </h2>
        <p className="text-slate-600 mt-2">
          Voici ce dont nous avons besoin pour finaliser votre changement d'offre.
        </p>
        {ctx.economie_annuelle_estimee > 0 && (
          <div className="mt-4 flex items-center gap-2 text-accent bg-emerald-50 px-4 py-3 rounded-lg">
            <Sparkles className="w-5 h-5" />
            <span className="font-medium">
              Économie estimée : {ctx.economie_annuelle_estimee.toFixed(0)} € / an
            </span>
          </div>
        )}
      </div>

      {toutEstFait && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 mb-6 flex items-center gap-3">
          <CheckCircle2 className="w-8 h-8 text-accent shrink-0" />
          <div>
            <p className="font-semibold text-emerald-900">✅ Tous vos documents ont bien été transmis.</p>
            <p className="text-sm text-emerald-800 mt-1">
              Votre conseiller les vérifie et reviendra vers vous avec la suite.
            </p>
          </div>
        </div>
      )}

      <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${tousDocsOk ? "bg-emerald-100 text-accent" : "bg-blue-100 text-primary"}`}>
            {tousDocsOk ? <CheckCircle2 className="w-6 h-6" /> : <Upload className="w-6 h-6" />}
          </div>
          <h3 className="text-lg font-semibold">Vos documents</h3>
        </div>

        <ul className="space-y-3">
          {ctx.documents_a_fournir.map((doc) => (
            <li key={doc.type_document} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <div>
                <div className="font-medium">{doc.label_affiche}</div>
                {doc.motif_rejet && (
                  <div className="text-sm text-danger mt-1">⚠️ {doc.motif_rejet}</div>
                )}
              </div>
              <StatutBadge statut={doc.statut} />
            </li>
          ))}
        </ul>

        {docsAFournir.length > 0 && ctx.peut_uploader_docs && !toutEstFait && (
          <Link
            href={`/dossier/${params.token}/documents`}
            className="mt-6 block w-full bg-primary text-white text-center py-3 rounded-lg font-semibold hover:bg-primary/90 transition"
          >
            Envoyer mes documents →
          </Link>
        )}
      </section>

      {ctx.mandat_statut && (
        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${ctx.mandat_statut === "signe" ? "bg-emerald-100 text-accent" : "bg-blue-100 text-primary"}`}>
              <FileSignature className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-semibold">Votre mandat</h3>
          </div>

          {ctx.mandat_statut === "signe" ? (
            <p className="text-accent flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5" /> Mandat signé avec succès.
            </p>
          ) : (
            <p className="text-slate-600">
              Le mandat autorise votre conseiller à effectuer les démarches à votre place. Vous recevrez un email de Yousign pour signer.
            </p>
          )}
        </section>
      )}

      {ctx.demarches_a_completer.length > 0 && ctx.peut_renseigner_demarches && (
        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full flex items-center justify-center bg-blue-100 text-primary">
              <FileText className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-semibold">Informations complémentaires</h3>
          </div>
          <p className="text-slate-600 mb-4">
            Votre conseiller a besoin de quelques informations pour préparer vos démarches.
          </p>
          <Link
            href={`/dossier/${params.token}/demarches`}
            className="block w-full bg-primary text-white text-center py-3 rounded-lg font-semibold hover:bg-primary/90 transition"
          >
            Compléter mes informations →
          </Link>
        </section>
      )}

      {ctx.peut_transmettre_speedtest && (
        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${ctx.speedtest_fait ? "bg-emerald-100 text-accent" : "bg-blue-100 text-primary"}`}>
              {ctx.speedtest_fait ? <CheckCircle2 className="w-6 h-6" /> : <Wifi className="w-6 h-6" />}
            </div>
            <h3 className="text-lg font-semibold">Testons la puissance de votre réseau</h3>
          </div>
          {ctx.speedtest_fait ? (
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <span className="font-medium">Votre débit internet testé</span>
              <StatutBadge statut="recu" />
            </div>
          ) : (
            <>
              <p className="text-slate-600 mb-4">
                Un test de débit nous aide à confirmer la qualité de votre offre actuelle.
              </p>
              <Link
                href={`/dossier/${params.token}/speedtest`}
                className="block w-full bg-primary text-white text-center py-3 rounded-lg font-semibold hover:bg-primary/90 transition"
              >
                Tester mon débit →
              </Link>
            </>
          )}
        </section>
      )}

      {ctx.conseiller_nom && (
        <div className="mt-8 text-center text-sm text-slate-500">
          Votre conseiller : <span className="font-medium">{ctx.conseiller_nom}</span>
        </div>
      )}
    </main>
  );
}

function StatutBadge({ statut }: { statut: string }) {
  const map: Record<string, { label: string; className: string }> = {
    a_fournir: { label: "À envoyer", className: "bg-orange-100 text-orange-700" },
    en_attente: { label: "En attente", className: "bg-slate-100 text-slate-600" },
    recu: { label: "✓ Reçu", className: "bg-emerald-100 text-accent" },
    valide: { label: "✓ Validé", className: "bg-emerald-100 text-accent" },
    rejete: { label: "✗ À refaire", className: "bg-red-100 text-danger" },
  };
  const s = map[statut] || map.en_attente;
  return <span className={`text-xs px-3 py-1 rounded-full font-medium ${s.className}`}>{s.label}</span>;
}
