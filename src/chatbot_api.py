# ==============================================================================
#  API CHATBOT — FastAPI, process indépendant de Streamlit (Roadmap 4.1)
#
#  Expose les endpoints consommés par le widget JS public (src/static/chatbot_widget.js) :
#  conversation (Claude tool-use), comparaison d'offres, bilan chiffré, création directe
#  de prospect. Partage la même base SQLite que l'app Streamlit (db.py, mode WAL).
#
#  Lancement (depuis src/) :
#     uvicorn chatbot_api:app --host 0.0.0.0 --port 8001
# ==============================================================================
import io
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import secrets_config
from chatbot_engine import traiter_message
from db import enregistrer_action, initialiser_bdd, lire_parametre
from notifications import notifier_document_prospect_recu
from offres_engine import comparer_offres, construire_recommandations
from pdf_engine import (
    analyser_facture, analyser_facture_vision, analyser_speedtest_pdf,
    analyser_speedtest_vision, construire_apercu_pdf_prospect, lire_pdf,
)
from prospects_engine import (
    ajouter_prospect, maj_prospect, valider_token_documents, enregistrer_document_prospect,
)
from utils import generer_ref, safe_float, valider_email, valider_telephone

STATIC_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PORTAIL_HTML     = os.path.join(STATIC_DIR, "portail_prospect.html")
EXTENSIONS_OK    = {"pdf", "jpg", "jpeg", "png"}
TAILLE_MAX_OCTETS = 10 * 1024 * 1024


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Assure la présence du schéma (tables + migrations) même si ce process démarre
    # avant l'app Streamlit — les deux partagent la même base ia_conseil_crm.db.
    # Placé dans le lifespan (exécuté au démarrage réel du serveur) plutôt qu'à
    # l'import du module, pour ne jamais toucher la base au simple `import chatbot_api`
    # (ex. dans les tests, qui redirigent db.DB_NAME vers une base jetable).
    initialiser_bdd()
    yield


app = FastAPI(title="IA Conseil — API Chatbot", version="1.0.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # le widget doit fonctionner depuis n'importe quel site tiers
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.isdir(STATIC_DIR):
    app.mount("/widget", StaticFiles(directory=STATIC_DIR), name="widget")


# ------------------------------------------------------------------------------
#  LIMITEUR DE DÉBIT — basique, en mémoire, par IP (sans nouvelle dépendance)
# ------------------------------------------------------------------------------
_FENETRE_SEC   = 60
_MAX_REQUETES  = 30
_appels_par_ip: dict = defaultdict(list)


def _verifier_limite(request: Request):
    ip = request.client.host if request.client else "inconnu"
    maintenant = time.time()
    appels = [t for t in _appels_par_ip[ip] if maintenant - t < _FENETRE_SEC]
    if len(appels) >= _MAX_REQUETES:
        raise HTTPException(status_code=429, detail="Trop de requêtes, merci de patienter.")
    appels.append(maintenant)
    _appels_par_ip[ip] = appels


# ------------------------------------------------------------------------------
#  MODÈLES PYDANTIC
# ------------------------------------------------------------------------------
class ChatIn(BaseModel):
    session_id: str
    message: str


class ProspectIn(BaseModel):
    prenom: str = ""
    nom: str = ""
    telephone: str = ""
    email: str = ""
    ville: str = ""
    code_postal: str = ""
    type_client: str = "Particulier"
    univers_interesse: str = ""
    operateur_actuel: str = ""
    cout_mensuel_actuel: float = 0.0
    fournisseur_energie: str = ""
    cout_elec: float = 0.0
    cout_gaz: float = 0.0
    economie_estimee_an: float = 0.0
    notes: str = ""


class OffresCompareIn(BaseModel):
    univers: str
    categorie: Optional[str] = None
    cout_actuel_mensuel: float
    fournisseurs_autorises: Optional[List[str]] = None
    fournisseur_exclu: Optional[str] = None
    data_go_min: Optional[float] = None


class BilanIn(BaseModel):
    service_principal: str
    cout_tel: float
    fournisseur_exclu: Optional[str] = None
    data_go_min: Optional[float] = None


# ------------------------------------------------------------------------------
#  ENDPOINTS
# ------------------------------------------------------------------------------
@app.post("/api/chat")
def chat(payload: ChatIn, request: Request):
    _verifier_limite(request)
    if not payload.message.strip():
        raise HTTPException(status_code=422, detail="Message vide.")
    return traiter_message(payload.session_id, payload.message)


@app.post("/api/prospects")
def creer_prospect(payload: ProspectIn, request: Request):
    _verifier_limite(request)
    if payload.email and not valider_email(payload.email):
        raise HTTPException(status_code=422, detail="Email invalide.")
    if payload.telephone and not valider_telephone(payload.telephone):
        raise HTTPException(status_code=422, detail="Numéro de téléphone invalide.")
    if not payload.telephone and not payload.email:
        raise HTTPException(status_code=422, detail="Téléphone ou email requis.")

    d = payload.model_dump()
    d["ref"] = generer_ref()
    d["cree_par"] = "API Chatbot"
    d["origine"] = "Chatbot"
    prospect_id = ajouter_prospect(d)
    return {"prospect_id": prospect_id}


@app.post("/api/offres/comparer")
def offres_comparer(payload: OffresCompareIn, request: Request):
    _verifier_limite(request)
    resultats = comparer_offres(
        payload.univers, payload.categorie, safe_float(payload.cout_actuel_mensuel),
        fournisseurs_autorises=payload.fournisseurs_autorises,
        fournisseur_exclu=payload.fournisseur_exclu,
        data_go_min=payload.data_go_min,
    )
    return {"resultats": resultats}


@app.post("/api/bilan")
def bilan(payload: BilanIn, request: Request):
    _verifier_limite(request)
    reco = construire_recommandations(
        payload.service_principal, safe_float(payload.cout_tel),
        fournisseur_exclu=payload.fournisseur_exclu, data_go_min=payload.data_go_min,
    )
    titre_p, offres_p = reco["principal"]
    economie_max = offres_p[0]["economie_annuelle"] if offres_p else 0.0
    return {
        "principal": {"titre": titre_p, "offres": offres_p},
        "cross_sell": [{"titre": t, "offres": o} for t, o in reco["cross_sell"]],
        "economie_max_annuelle": economie_max,
    }


@app.get("/api/health")
def health():
    return {"statut": "ok"}


# ------------------------------------------------------------------------------
#  PORTAIL PROSPECT — mini-page publique (lien à usage personnel, sans login)
#  où le prospect transmet lui-même sa facture et un test de débit, cf. le
#  bouton « Demander facture + test de débit » de la fiche prospect (app.py).
# ------------------------------------------------------------------------------
@app.get("/portail/{token}", response_class=HTMLResponse)
def portail_prospect_page(token: str):
    # Le token n'est pas vérifié ici : la page est statique, c'est le JS embarqué
    # qui l'extrait de l'URL et appelle /api/portail/{token} pour le valider.
    with open(PORTAIL_HTML, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/portail/{token}")
def portail_contexte(token: str, request: Request):
    _verifier_limite(request)
    prospect = valider_token_documents(token)
    if prospect is None:
        raise HTTPException(status_code=404, detail="Lien invalide ou expiré.")
    return {"prenom": prospect["prenom"] or "", "nom": prospect["nom"] or ""}


@app.get("/portail/{token}/apercu.pdf")
def portail_apercu_pdf(token: str, request: Request):
    """Régénère à la volée le PDF teaser (économie totale, sans détail des offres) d'un
    prospect — lien envoyé par SMS depuis la fiche prospect (un SMS ne pouvant pas porter de
    pièce jointe), cf. app.py::envoi de l'aperçu."""
    _verifier_limite(request)
    prospect = valider_token_documents(token)
    if prospect is None:
        raise HTTPException(status_code=404, detail="Lien invalide ou expiré.")
    pdf_bytes = construire_apercu_pdf_prospect(dict(prospect), lire_parametre("nom_societe", "IA CONSEIL"))
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Aucun aperçu disponible pour ce prospect.")
    return Response(content=pdf_bytes, media_type="application/pdf")


def _extension(nom_fichier: str) -> str:
    return nom_fichier.rsplit(".", 1)[-1].lower() if nom_fichier and "." in nom_fichier else ""


async def _lire_upload(fichier: UploadFile) -> bytes:
    ext = _extension(fichier.filename or "")
    if ext not in EXTENSIONS_OK:
        raise HTTPException(status_code=422, detail="Format non supporté (PDF, JPG ou PNG uniquement).")
    contenu = await fichier.read()
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 10 Mo).")
    if not contenu:
        raise HTTPException(status_code=422, detail="Fichier vide.")
    return contenu


@app.post("/api/portail/{token}/facture")
async def portail_upload_facture(token: str, request: Request, fichier: UploadFile = File(...)):
    _verifier_limite(request)
    prospect = valider_token_documents(token)
    if prospect is None:
        raise HTTPException(status_code=404, detail="Lien invalide ou expiré.")
    contenu = await _lire_upload(fichier)

    api_key = secrets_config.anthropic_api_key()
    ext = _extension(fichier.filename or "")
    data = None
    if ext == "pdf":
        data = analyser_facture(lire_pdf(io.BytesIO(contenu)))
        if data.get("prix", 0.0) == 0.0 and data.get("operateur") == "Autre / Aucun" and api_key:
            data = analyser_facture_vision(contenu, fichier.filename, api_key) or data
    elif api_key:
        data = analyser_facture_vision(contenu, fichier.filename, api_key)

    if not data or (data.get("prix", 0.0) == 0.0 and data.get("operateur") == "Autre / Aucun"
                    and data.get("fournisseur") == "Autre / Aucun"):
        raise HTTPException(status_code=422,
                             detail="Facture illisible — réessayez avec une photo plus nette ou un PDF.")

    pid = int(prospect["id"])
    if data.get("operateur") and data["operateur"] != "Autre / Aucun":
        maj_prospect(pid, "operateur_actuel", data["operateur"])
    if data.get("fournisseur") and data["fournisseur"] != "Autre / Aucun":
        maj_prospect(pid, "fournisseur_energie", data["fournisseur"])
    if data.get("prix"):
        maj_prospect(pid, "cout_mensuel_actuel", safe_float(data["prix"]))
    if data.get("data_go"):
        maj_prospect(pid, "data_go", data["data_go"])
    enregistrer_document_prospect(pid, "facture", fichier.filename or "facture",
                                   contenu, fichier.content_type or "application/octet-stream")

    operateur_resume = data.get("operateur") if data.get("operateur") != "Autre / Aucun" else data.get("fournisseur")
    resume = f"Facture reçue — {operateur_resume or '—'} · {safe_float(data.get('prix')):.0f} €/mois"
    nom_complet = f"{prospect['prenom'] or ''} {prospect['nom'] or ''}".strip()
    enregistrer_action("prospect", pid, "Facture reçue via lien personnel", resume,
                        auteur="Prospect (lien personnel)")
    notifier_document_prospect_recu(pid, nom_complet, resume)

    return {"ok": True, "resume": resume}


@app.post("/api/portail/{token}/speedtest")
async def portail_upload_speedtest(token: str, request: Request, fichier: UploadFile = File(...)):
    _verifier_limite(request)
    prospect = valider_token_documents(token)
    if prospect is None:
        raise HTTPException(status_code=404, detail="Lien invalide ou expiré.")
    contenu = await _lire_upload(fichier)

    api_key = secrets_config.anthropic_api_key()
    ext = _extension(fichier.filename or "")
    down = up = 0.0
    if ext == "pdf":
        down, up = analyser_speedtest_pdf(lire_pdf(io.BytesIO(contenu)))
    if down == 0.0 and up == 0.0 and api_key:
        resultat_vision = analyser_speedtest_vision(contenu, fichier.filename, api_key)
        if resultat_vision:
            down, up = resultat_vision

    if down == 0.0 and up == 0.0:
        raise HTTPException(status_code=422,
                             detail="Débit illisible — réessayez avec une capture plus nette ou un export PDF.")

    pid = int(prospect["id"])
    maj_prospect(pid, "speed_down", down)
    maj_prospect(pid, "speed_up", up)
    enregistrer_document_prospect(pid, "speedtest", fichier.filename or "speedtest",
                                   contenu, fichier.content_type or "application/octet-stream")

    resume = f"Test de débit reçu — ⬇️ {down} Mbps / ⬆️ {up} Mbps"
    nom_complet = f"{prospect['prenom'] or ''} {prospect['nom'] or ''}".strip()
    enregistrer_action("prospect", pid, "Test de débit reçu via lien personnel", resume,
                        auteur="Prospect (lien personnel)")
    notifier_document_prospect_recu(pid, nom_complet, resume)

    return {"ok": True, "resume": resume}
