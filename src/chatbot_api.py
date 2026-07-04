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
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chatbot_engine import traiter_message
from db import initialiser_bdd
from offres_engine import comparer_offres, construire_recommandations
from prospects_engine import ajouter_prospect
from utils import generer_ref, safe_float, valider_email, valider_telephone

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


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
