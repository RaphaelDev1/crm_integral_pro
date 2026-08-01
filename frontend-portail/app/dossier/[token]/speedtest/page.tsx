"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import {
  getContexte,
  soumettreSpeedtest,
  soumettreSpeedtestFichier,
  TokenContexte,
} from "@/lib/api";
import { ArrowLeft, Gauge, Loader2, Upload, Wifi } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type EtatTest = "idle" | "running" | "submitting" | "done" | "error";

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
  const donneesRef = useRef<DonneesTest | null>(null);

  useEffect(() => {
    getContexte(params.token)
      .then(setCtx)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [params.token]);

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
        });
        setResultatMessage(resultat.message);
        setEtat("done");
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
            <Gauge className="w-10 h-10 mx-auto mb-3" />
            <p className="font-semibold">{resultatMessage}</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 mb-6">
              <Mesure label="Download" valeur={donnees?.dlStatus} unite="Mbit/s" />
              <Mesure label="Upload" valeur={donnees?.ulStatus} unite="Mbit/s" />
              <Mesure label="Latence" valeur={donnees?.pingStatus} unite="ms" />
              <Mesure label="Jitter" valeur={donnees?.jitterStatus} unite="ms" />
            </div>
            <button
              onClick={lancerTest}
              disabled={!scriptReady || etat === "running" || etat === "submitting"}
              className="w-full bg-primary text-white py-3 rounded-lg font-semibold hover:bg-primary/90 transition disabled:opacity-50"
            >
              {etat === "running" && "Test en cours..."}
              {etat === "submitting" && "Envoi du résultat..."}
              {(etat === "idle" || etat === "error") && "Lancer le test"}
            </button>
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
