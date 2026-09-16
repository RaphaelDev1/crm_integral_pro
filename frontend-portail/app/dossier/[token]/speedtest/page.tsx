"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import {
  ContratTelecom,
  getContexte,
  getContratsTelecom,
  soumettreSpeedtest,
  soumettreSpeedtestFichier,
  TokenContexte,
} from "@/lib/api";
import { AlertTriangle, ArrowLeft, CheckCircle2, Loader2, Upload, Wifi } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Mêmes catégories que backend/routers/portail_public.py::CATEGORIES_CONTRAT_TELECOM
// — sert à distinguer les lignes mobile des lignes box parmi les contrats du
// prospect, pour proposer le second test (voir `phase` ci-dessous).
const CATEGORIES_MOBILE = ["Forfait mobile", "Mobile"];
const CATEGORIES_BOX = ["Forfait box", "Box / Fibre", "Pack Box + Mobile"];

type Phase = "mobile" | "box";
type EtatTest = "idle" | "running" | "submitting" | "done" | "error";

// Libellé lisible par un client — même logique que situation/page.tsx::libelleLigne.
function libelleLigne(ligne: ContratTelecom): string {
  const operateur = ligne.fournisseur ? ` - ${ligne.fournisseur}` : "";
  if (ligne.categorie === "Mobile") return `Votre forfait mobile${operateur}`;
  if (ligne.categorie === "Box / Fibre") return `Votre box internet${operateur}`;
  return [ligne.categorie, ligne.fournisseur, ligne.nom_offre].filter(Boolean).join(" — ");
}

interface DonneesTest {
  dlStatus: string;
  ulStatus: string;
  pingStatus: string;
  jitterStatus: string;
}

export default function SpeedtestPage({ params }: { params: { token: string } }) {
  const router = useRouter();
  const [ctx, setCtx] = useState<TokenContexte | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [etat, setEtat] = useState<EtatTest>("idle");
  const [donnees, setDonnees] = useState<DonneesTest | null>(null);
  const [resultatMessage, setResultatMessage] = useState<string | null>(null);
  const [uploadingFichier, setUploadingFichier] = useState(false);
  const [wifiConfirme, setWifiConfirme] = useState(false);
  const [contrats, setContrats] = useState<ContratTelecom[]>([]);
  const [contratId, setContratId] = useState<number | undefined>(undefined);
  // Ligne actuellement testée, et lignes déjà testées dans cette visite —
  // permet d'enchaîner mobile puis box (ou l'inverse) quand le prospect a
  // les deux, chaque résultat étant rattaché au contrat correspondant (voir
  // `contratsPhase`/`autrePhaseDisponible` plus bas).
  const [phase, setPhase] = useState<Phase | null>(null);
  const [phasesFaites, setPhasesFaites] = useState<Set<Phase>>(new Set());
  const donneesRef = useRef<DonneesTest | null>(null);

  useEffect(() => {
    getContexte(params.token)
      .then((c) => {
        setCtx(c);
        if (c.univers === "telecom_mobile") setPhase("mobile");
        else if (c.univers === "telecom_box") setPhase("box");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // Best-effort : si le lien ne permet pas de lister les contrats (ou s'il
    // n'y en a aucun), le test reste utilisable sans sélecteur.
    getContratsTelecom(params.token)
      .then((liste) => {
        setContrats(liste);
        setPhase((prev) => prev ?? (liste.some((c) => CATEGORIES_MOBILE.includes(c.categorie ?? "")) ? "mobile" : "box"));
      })
      .catch(() => {});
  }, [params.token]);

  const contratsPhase = contrats.filter((c) =>
    (phase === "box" ? CATEGORIES_BOX : CATEGORIES_MOBILE).includes(c.categorie ?? "")
  );
  const autrePhase: Phase | null = phase === "mobile" ? "box" : phase === "box" ? "mobile" : null;
  const autrePhaseDisponible =
    autrePhase !== null &&
    !phasesFaites.has(autrePhase) &&
    contrats.some((c) => (autrePhase === "box" ? CATEGORIES_BOX : CATEGORIES_MOBILE).includes(c.categorie ?? ""));

  useEffect(() => {
    setContratId(contratsPhase.length === 1 ? contratsPhase[0].id : undefined);
    // contratsPhase est recalculé à chaque rendu à partir de `contrats`/`phase` ;
    // on ne le met pas dans les deps (nouvelle référence de tableau à chaque
    // rendu) mais on veut bien redéclencher quand l'un ou l'autre change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, contrats]);

  function testerAutreLigne() {
    if (!autrePhase) return;
    setPhase(autrePhase);
    setPhasesFaites((prev) => new Set(prev).add(phase!));
    setEtat("idle");
    setWifiConfirme(false);
    setDonnees(null);
    setResultatMessage(null);
  }

  function lancerTest() {
    const w = window as any;
    if (!w.Speedtest) return;
    setError(null);
    setEtat("running");
    setDonnees(null);
    setResultatMessage(null);
    donneesRef.current = null;

    const s = new w.Speedtest();
    s.setSelectedServer({
      name: "IA Conseil",
      server: API_URL,
      dlURL: "/speedtest-backend/garbage",
      ulURL: "/speedtest-backend/upload",
      pingURL: "/speedtest-backend/empty",
      getIpURL: "/speedtest-backend/getIP",
    });

    s.onupdate = (data: any) => {
      const nouvelles: DonneesTest = {
        dlStatus: data.dlStatus,
        ulStatus: data.ulStatus,
        pingStatus: data.pingStatus,
        jitterStatus: data.jitterStatus,
      };
      donneesRef.current = nouvelles;
      setDonnees(nouvelles);
    };

    s.onend = async (aborted: boolean) => {
      if (aborted) {
        setEtat("idle");
        return;
      }
      const download = parseFloat(donneesRef.current?.dlStatus ?? "0") || 0;
      const upload = parseFloat(donneesRef.current?.ulStatus ?? "0") || 0;
      const ping = parseFloat(donneesRef.current?.pingStatus ?? "");

      setEtat("submitting");
      try {
        const resultat = await soumettreSpeedtest(params.token, {
          download_mbps: download,
          upload_mbps: upload,
          ping_ms: Number.isFinite(ping) ? ping : undefined,
          contrat_id: contratId,
        });
        setResultatMessage(resultat.message);
        setEtat("done");
        // Voir documents/page.tsx : sans ce refresh(), revenir à la page
        // d'accueil montre encore l'ancien statut pendant ~30s (cache routeur
        // App Router côté client).
        router.refresh();
      } catch (e: any) {
        setError(e.message);
        setEtat("error");
      }
    };

    s.start();
  }

  async function handleFichier(file: File) {
    setError(null);
    setUploadingFichier(true);
    try {
      const resultat = await soumettreSpeedtestFichier(params.token, file);
      setResultatMessage(resultat.message);
      setEtat("done");
      router.refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploadingFichier(false);
    }
  }

  if (loading) {
    return (
      <div className="text-center py-16">
        <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" />
      </div>
    );
  }
  if (!ctx) return <div className="text-center py-16 text-danger">Erreur : {error}</div>;
  if (!ctx.peut_transmettre_speedtest) {
    return (
      <main className="text-center py-16">
        <p className="text-slate-600">Cette action n'est pas disponible sur votre lien.</p>
      </main>
    );
  }

  const estMobile = phase === "mobile";
  const estBox = phase === "box";
  // Sur une offre mobile, le Wi-Fi fausse le test (il faudrait tester le
  // réseau mobile, pas la box) ; sur une offre box testée depuis un
  // téléphone, c'est l'inverse. On bloque le lancement tant que le client
  // n'a pas confirmé être dans la bonne configuration.
  const wifiAConfirmer = estMobile || estBox;

  return (
    <main>
      <Script src="/js/speedtest.js" strategy="afterInteractive" onLoad={() => setScriptReady(true)} />

      <button
        onClick={() => router.push(`/dossier/${params.token}`)}
        className="flex items-center gap-2 text-slate-600 mb-6 hover:text-primary"
      >
        <ArrowLeft className="w-4 h-4" /> Retour
      </button>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
        <h2 className="text-xl font-bold text-primary mb-2 flex items-center gap-2">
          <Wifi className="w-5 h-5" /> Testez votre débit
        </h2>
        <p className="text-slate-600 text-sm">
          Lancez le test directement depuis votre téléphone ou votre ordinateur, en un tap. Le
          résultat est transmis automatiquement à votre conseiller.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-danger p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6 text-center">
        {etat === "done" ? (
          <div className="text-accent">
            <CheckCircle2 className="w-10 h-10 mx-auto mb-3" />
            <p className="font-semibold">{resultatMessage}</p>
            {autrePhaseDisponible ? (
              <>
                <p className="text-sm text-slate-600 mt-2">
                  Vous avez aussi {autrePhase === "box" ? "une box" : "un forfait mobile"} — si vous
                  pouvez, testez-la aussi : on aura ainsi le débit de chacune de vos lignes.
                </p>
                <button
                  onClick={testerAutreLigne}
                  className="mt-4 w-full bg-primary text-white py-3 rounded-lg font-semibold hover:bg-primary/90 transition"
                >
                  Tester aussi {autrePhase === "box" ? "ma box" : "mon forfait mobile"} →
                </button>
              </>
            ) : (
              <p className="text-sm text-slate-600 mt-2">
                Si vous avez un doute sur le résultat (Wi-Fi mal coupé, box loin de la pièce...),
                vous pouvez rouvrir ce lien et relancer le test dans de meilleures conditions.
                Sinon, c'est tout bon, vous n'avez plus rien à faire. Votre conseiller retrouvera cette
                information et reviendra vers vous avec la suite.
              </p>
            )}
          </div>
        ) : (
          <>
            {estMobile && (
              <div className="flex items-start gap-3 text-left bg-orange-50 border border-orange-200 rounded-lg p-4 mb-4">
                <AlertTriangle className="w-5 h-5 text-orange-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-orange-900">Important : coupez le Wi-Fi avant de lancer ce test</p>
                  <p className="text-sm text-orange-800 mt-1">
                    Vous testez ici votre forfait <strong>mobile</strong> (4G/5G) : si votre téléphone
                    reste connecté au Wi-Fi pendant le test, le résultat mesurera votre box et pas votre
                    ligne mobile — désactivez le Wi-Fi (pas seulement la box) avant de continuer.
                  </p>
                  <label className="flex items-center gap-2 mt-3 text-sm text-orange-900">
                    <input
                      type="checkbox"
                      checked={wifiConfirme}
                      onChange={(e) => setWifiConfirme(e.target.checked)}
                    />
                    J&apos;ai désactivé mon Wi-Fi, je suis bien en 4G/5G
                  </label>
                </div>
              </div>
            )}

            {estBox && (
              <div className="flex items-start gap-3 text-left bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <Wifi className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-900">Important : restez connecté au Wi-Fi de votre box</p>
                  <p className="text-sm text-blue-800 mt-1">
                    Vous testez ici votre <strong>box internet</strong> : à l'inverse d'un test mobile, il
                    faut ici rester connecté au Wi-Fi de votre box (pas en 4G/5G), sinon le résultat
                    mesurera votre réseau mobile et pas votre box.
                  </p>
                  <label className="flex items-center gap-2 mt-3 text-sm text-blue-900">
                    <input
                      type="checkbox"
                      checked={wifiConfirme}
                      onChange={(e) => setWifiConfirme(e.target.checked)}
                    />
                    Je suis connecté au Wi-Fi de ma box
                  </label>
                </div>
              </div>
            )}

            {contratsPhase.length > 1 && (
              <div className="text-left mb-4">
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Ce test concerne :
                </label>
                <select
                  value={contratId ?? ""}
                  onChange={(e) => setContratId(e.target.value ? Number(e.target.value) : undefined)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                >
                  <option value="">Sélectionner un forfait…</option>
                  {contratsPhase.map((c) => (
                    <option key={c.id} value={c.id}>
                      {libelleLigne(c)}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 mb-6">
              <Mesure label="Download" valeur={donnees?.dlStatus} unite="Mbit/s" />
              <Mesure label="Upload" valeur={donnees?.ulStatus} unite="Mbit/s" />
              <Mesure label="Latence" valeur={donnees?.pingStatus} unite="ms" />
              <Mesure label="Jitter" valeur={donnees?.jitterStatus} unite="ms" />
            </div>
            <button
              onClick={lancerTest}
              disabled={!scriptReady || etat === "running" || etat === "submitting" || (wifiAConfirmer && !wifiConfirme)}
              className="w-full bg-primary text-white py-3 rounded-lg font-semibold hover:bg-primary/90 transition disabled:opacity-50"
            >
              {etat === "running" && "Test en cours..."}
              {etat === "submitting" && "Envoi du résultat..."}
              {(etat === "idle" || etat === "error") && "Lancer le test"}
            </button>
            {(etat === "idle" || etat === "error") && (
              <button
                onClick={() => router.push(`/dossier/${params.token}`)}
                className="w-full text-center text-sm text-slate-500 hover:text-slate-700 hover:underline mt-3"
              >
                Pas maintenant, j&apos;y reviendrai plus tard
              </button>
            )}
          </>
        )}
      </div>

      {etat !== "done" && (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <p className="text-slate-600 text-sm mb-3">
            Vous préférez envoyer une capture d'écran ou un export PDF d'un autre test (nPerf,
            Speedtest.net...) ?
          </p>
          <label className={`block w-full ${uploadingFichier ? "opacity-50" : "cursor-pointer"}`}>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              disabled={uploadingFichier}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFichier(file);
              }}
              className="hidden"
            />
            <div
              className={`border-2 border-dashed rounded-lg p-6 text-center transition ${
                uploadingFichier ? "border-slate-300 bg-slate-50" : "border-primary/40 hover:border-primary hover:bg-primary/5"
              }`}
            >
              {uploadingFichier ? (
                <div className="flex items-center justify-center gap-2 text-slate-600">
                  <Loader2 className="w-5 h-5 animate-spin" /> Envoi en cours...
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
        </div>
      )}
    </main>
  );
}

function Mesure({ label, valeur, unite }: { label: string; valeur?: string; unite: string }) {
  return (
    <div className="bg-slate-50 rounded-lg p-4">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className="text-xl font-bold text-primary">{valeur || "—"}</div>
      <div className="text-xs text-slate-400">{unite}</div>
    </div>
  );
}
