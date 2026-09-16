import Link from "next/link";
import { getContexte } from "@/lib/api";
import { CheckCircle2, Upload, FileSignature, AlertCircle, Sparkles, FileText, MessageCircleQuestion, ListChecks, Gauge, Send } from "lucide-react";
import { TYPES_QUESTIONNAIRE_SECTEUR } from "@/lib/demarches";

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
  const situationOk = ctx.situation_renseignee || !ctx.peut_renseigner_situation;
  const speedtestOk = ctx.speedtest_fait || !ctx.peut_transmettre_speedtest;
  // Le questionnaire secteur (audit_*/portabilite) a sa propre section
  // ci-dessous, distincte des autres démarches (résiliation...) — voir
  // TokenContexte.audit_complet.
  const demarchesAutres = ctx.demarches_a_completer.filter((d) => !TYPES_QUESTIONNAIRE_SECTEUR.has(d.type_demarche));
  const toutEstFait =
    tousDocsOk && mandatOk && ctx.audit_complet && demarchesAutres.length === 0 && situationOk && speedtestOk;

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

      {ctx.peut_voir_suivi && (
        <Link
          href={`/dossier/${params.token}/suivi`}
          className="mb-6 flex items-center justify-between bg-white rounded-2xl shadow-sm border border-slate-200 p-6 hover:border-primary transition"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full flex items-center justify-center bg-blue-100 text-primary">
              <ListChecks className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Suivre l&apos;avancement de mon dossier</h3>
              <p className="text-sm text-slate-500">Où j&apos;en suis, ce qu&apos;il me reste à faire.</p>
            </div>
          </div>
        </Link>
      )}

      {ctx.mandat_statut === "a_signer" && (
        <a
          href="#mandats"
          className="mb-6 flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-2xl p-4 hover:border-orange-300 transition"
        >
          <FileSignature className="w-6 h-6 text-orange-600 shrink-0" />
          <p className="text-sm font-medium text-orange-900">
            ✍️ Vous devez signer votre mandat de représentation pour que nous puissions poursuivre vos démarches.
          </p>
        </a>
      )}

      {ctx.mandat_honoraires_statut === "a_signer" && (
        <a
          href="#mandats"
          className="mb-6 flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-2xl p-4 hover:border-orange-300 transition"
        >
          <FileSignature className="w-6 h-6 text-orange-600 shrink-0" />
          <p className="text-sm font-medium text-orange-900">
            ✍️ Votre mandat d&apos;honoraires est prêt — merci de le signer pour finaliser votre dossier.
          </p>
        </a>
      )}

      {ctx.dossier_soumis_fournisseur && ctx.statut_dossier !== "actif" && (
        <div className="mb-6 flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-2xl p-4">
          <Send className="w-6 h-6 text-orange-600 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-orange-900">📤 Envoi de votre dossier au fournisseur en cours</p>
            <p className="text-sm text-orange-800 mt-0.5">
              Nous sommes en train d&apos;envoyer votre dossier complet au fournisseur.
            </p>
          </div>
        </div>
      )}

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

      {!ctx.audit_complet && (
        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full flex items-center justify-center bg-blue-100 text-primary">
              <MessageCircleQuestion className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-semibold">Quelques questions sur votre situation</h3>
          </div>
          <p className="text-slate-600 mb-4">
            Répondez à ces questions pour que votre conseiller prépare le bon dossier — c&apos;est la
            première étape, avant l&apos;envoi de vos documents.
          </p>
          <Link
            href={`/dossier/${params.token}/questionnaire`}
            className="block w-full bg-primary text-white text-center py-3 rounded-lg font-semibold hover:bg-primary/90 transition"
          >
            Répondre aux questions →
          </Link>
        </section>
      )}

      {ctx.remplissage_autonome !== false && (
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
            ctx.audit_complet ? (
              <Link
                href={`/dossier/${params.token}/documents`}
                className="mt-6 block w-full bg-primary text-white text-center py-3 rounded-lg font-semibold hover:bg-primary/90 transition"
              >
                Envoyer mes documents →
              </Link>
            ) : (
              <p className="mt-6 text-center text-sm text-slate-500 bg-slate-50 rounded-lg py-3">
                Disponible après avoir répondu au questionnaire ci-dessus.
              </p>
            )
          )}
          {docsAFournir.length === 0 && ctx.peut_uploader_docs && ctx.documents_a_fournir.length > 0 && (
            <Link
              href={`/dossier/${params.token}/documents`}
              className="mt-6 block w-full text-center text-sm font-medium text-primary hover:underline"
            >
              Ajouter un autre document
            </Link>
          )}
        </section>
      )}

      {(ctx.mandat_statut || ctx.mandat_honoraires_statut) && (
        <section id="mandats" className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6 space-y-5">
          <h3 className="text-lg font-semibold">Vos mandats</h3>

          {ctx.mandat_statut && (
            <div className="flex items-start gap-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${ctx.mandat_statut === "signe" ? "bg-emerald-100 text-accent" : "bg-orange-100 text-orange-600"}`}>
                <FileSignature className="w-6 h-6" />
              </div>
              <div>
                <p className="font-medium mb-1">Mandat de représentation</p>
                {ctx.mandat_statut === "signe" ? (
                  <p className="text-accent flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5" /> Mandat signé avec succès.
                  </p>
                ) : (
                  <p className="text-slate-600">
                    Le mandat autorise votre conseiller à effectuer les démarches à votre place. Vous recevrez un email de Yousign pour signer.
                  </p>
                )}
              </div>
            </div>
          )}

          {ctx.mandat_honoraires_statut && (
            <div className="flex items-start gap-3">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${ctx.mandat_honoraires_statut === "signe" ? "bg-emerald-100 text-accent" : "bg-orange-100 text-orange-600"}`}>
                <FileSignature className="w-6 h-6" />
              </div>
              <div>
                <p className="font-medium mb-1">Mandat d&apos;honoraires</p>
                {ctx.mandat_honoraires_statut === "signe" ? (
                  <p className="text-accent flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5" /> Mandat d&apos;honoraires signé avec succès.
                  </p>
                ) : (
                  <p className="text-slate-600">
                    Le mandat d&apos;honoraires autorise la rémunération de votre conseiller pour les démarches effectuées. Merci de le signer.
                  </p>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      {demarchesAutres.length > 0 && ctx.peut_renseigner_demarches && (
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

      {ctx.peut_renseigner_situation && (
        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${ctx.situation_renseignee ? "bg-emerald-100 text-accent" : "bg-blue-100 text-primary"}`}>
              {ctx.situation_renseignee ? <CheckCircle2 className="w-6 h-6" /> : <MessageCircleQuestion className="w-6 h-6" />}
            </div>
            <h3 className="text-lg font-semibold">Votre situation actuelle</h3>
          </div>
          {ctx.situation_renseignee ? (
            <>
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <span className="font-medium">Vos réponses sur votre situation actuelle</span>
                <StatutBadge statut="recu" />
              </div>
              <Link
                href={`/dossier/${params.token}/situation`}
                className="mt-3 block w-full text-center text-sm font-medium text-primary hover:underline"
              >
                Modifier mes réponses →
              </Link>
            </>
          ) : (
            <>
              <p className="text-slate-600 mb-4">
                Quelques questions sur votre offre et votre réseau actuels, pour aider votre conseiller à préparer votre dossier.
              </p>
              <Link
                href={`/dossier/${params.token}/situation`}
                className="block w-full bg-primary text-white text-center py-3 rounded-lg font-semibold hover:bg-primary/90 transition"
              >
                Répondre aux questions →
              </Link>
              {ctx.peut_transmettre_speedtest && !ctx.speedtest_fait && ctx.remplissage_autonome !== false && (
                <Link
                  href={`/dossier/${params.token}/speedtest`}
                  className="block w-full text-primary text-center py-2 mt-2 text-sm font-medium hover:underline"
                >
                  Passer directement au test de débit →
                </Link>
              )}
            </>
          )}
        </section>
      )}

      {ctx.peut_transmettre_speedtest && ctx.remplissage_autonome !== false && (
        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${ctx.speedtest_fait ? "bg-emerald-100 text-accent" : "bg-blue-100 text-primary"}`}>
              {ctx.speedtest_fait ? <CheckCircle2 className="w-6 h-6" /> : <Gauge className="w-6 h-6" />}
            </div>
            <h3 className="text-lg font-semibold">Votre débit internet</h3>
          </div>
          {ctx.speedtest_fait ? (
            <>
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                <span className="font-medium">Résultat de votre test de débit</span>
                <StatutBadge statut="recu" />
              </div>
              <Link
                href={`/dossier/${params.token}/speedtest`}
                className="mt-3 block w-full text-center text-sm font-medium text-primary hover:underline"
              >
                Refaire le test →
              </Link>
            </>
          ) : (
            <>
              <p className="text-slate-600 mb-4">
                Testez votre débit internet actuel en 30 secondes, pour aider votre conseiller à comparer les offres.
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
