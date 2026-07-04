# ==============================================================================
#  API CRM INTERNE — FastAPI, process indépendant de Streamlit (Roadmap 4.3)
#
#  Expose en HTTP la couche métier déjà utilisée par app.py (prospects_engine,
#  clients_engine, contrats_engine, offres_engine) : CRUD complet + diagnostic.
#  Authentification par JWT (voir jwt_auth.py) — à distinguer de chatbot_api.py
#  qui reste l'API publique, non authentifiée, dédiée au widget chatbot du site.
#
#  Cette API est le nouveau point d'entrée pour toute intégration future (app
#  mobile conseiller, portail client, webhooks) sans dépendre de Streamlit.
#  Streamlit lui-même l'utilise déjà via api_client.py, avec repli automatique
#  sur les modules *_engine.py si l'API n'est pas démarrée (cf. api_client.py).
#
#  Lancement (depuis src/) :
#     uvicorn crm_api:app --host 0.0.0.0 --port 8000
#  Documentation interactive : http://localhost:8000/docs
# ==============================================================================
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import authentifier_utilisateur
from clients_engine import (
    CHAMPS_CLIENT, ajouter_client, lire_clients, maj_client, supprimer_client,
)
from contrats_engine import (
    CHAMPS_CONTRAT, ajouter_contrat, lire_contrats_client, maj_contrat, supprimer_contrat,
)
from db import get_conn, initialiser_bdd
from jwt_auth import creer_token, get_current_user, require_role
from offres_engine import (
    CHAMPS_OFFRE, ajouter_offre, comparer_offres, construire_recommandations,
    lire_offres, maj_offre, supprimer_offre,
)
from prospects_engine import CHAMPS_PROSPECT, ajouter_prospect, lire_prospects, maj_prospect, supprimer_prospect
from utils import generer_ref, safe_float, valider_email, valider_telephone

CONSEILLER_OU_ADMIN = require_role("Conseiller", "Admin")
ADMIN_SEUL          = require_role("Admin")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Voir chatbot_api.py : même rationale, placé dans le lifespan pour ne jamais
    # toucher la base au simple `import crm_api` (tests avec base jetable).
    initialiser_bdd()
    yield


app = FastAPI(
    title="IA Conseil — API CRM interne",
    version="1.0.0",
    description="CRUD prospects/clients/contrats/offres + diagnostic, protégé par JWT.",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _df_payload(df) -> dict:
    """Sérialise un DataFrame en {columns, records} — `columns` provient toujours
    du schéma SQL (même sur un résultat vide), ce qui permet au client de
    reconstruire un DataFrame avec les bonnes colonnes même quand records=[]."""
    return {"columns": df.columns.tolist(), "records": df.to_dict(orient="records")}


# ------------------------------------------------------------------------------
#  AUTHENTIFICATION
# ------------------------------------------------------------------------------
class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/auth/login")
def login(payload: LoginIn):
    user = authentifier_utilisateur(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect.")
    token = creer_token(user)
    user_public = {k: v for k, v in user.items() if k != "password_hash"}
    return {"access_token": token, "token_type": "bearer", "user": user_public}


@app.get("/auth/me")
def me(current=Depends(get_current_user)):
    return current


# ------------------------------------------------------------------------------
#  MODÈLES PYDANTIC — CRUD
# ------------------------------------------------------------------------------
class ChampValeur(BaseModel):
    champ: str
    valeur: Any


class ProspectCreate(BaseModel):
    prenom: str = ""
    nom: str = ""
    telephone: str = ""
    email: str = ""
    code_postal: str = ""
    ville: str = ""
    adresse: str = ""
    type_client: str = "Particulier"
    univers_interesse: str = ""
    service_principal: str = ""
    operateur_actuel: str = ""
    techno: str = ""
    data_go: str = ""
    cout_mensuel_actuel: float = 0.0
    offre_actuelle: str = ""
    satisfaction_reseau: str = ""
    veut_rester: str = ""
    speed_down: float = 0.0
    speed_up: float = 0.0
    cout_elec: float = 0.0
    cout_gaz: float = 0.0
    fournisseur_energie: str = ""
    abonnements: str = ""
    lignes_multi: str = ""
    economie_estimee_an: float = 0.0
    notes: str = ""
    statut: str = "À relancer"
    date_relance: Optional[str] = None
    offres_interet: str = "[]"


class ClientCreate(BaseModel):
    prenom: str = ""
    nom: str = ""
    telephone: str = ""
    email: str = ""
    code_postal: str = ""
    ville: str = ""
    adresse: str = ""
    type_client: str = "Particulier"
    operateur_actuel: str = ""
    techno: str = ""
    data_go: str = ""
    offre_actuelle: str = ""
    cout_mensuel_actuel: float = 0.0
    satisfaction_reseau: str = ""
    veut_rester: str = ""
    speed_down: float = 0.0
    speed_up: float = 0.0
    fournisseur_energie: str = ""
    cout_elec: float = 0.0
    cout_gaz: float = 0.0
    economie_estimee_an: float = 0.0
    notes: str = ""


class ContratCreate(BaseModel):
    univers: str = ""
    categorie: str = ""
    fournisseur: str = ""
    nom_offre: str = ""
    cout_mensuel: float = 0.0
    economie_mensuelle: float = 0.0
    reference_contrat: str = ""
    statut_contrat: str = "En cours d'ouverture"
    date_fin_engagement: str = ""
    notes: str = ""


class OffreCreate(BaseModel):
    univers: str
    categorie: str
    fournisseur: str
    nom_offre: str
    prix_mensuel: float = 0.0
    frais_activation: float = 0.0
    engagement_mois: int = 0
    caracteristiques: str = ""
    commission_affiliation: float = 0.0
    data_go: float = 0.0
    url_souscription: str = ""
    code_affiliation: str = ""


def _appliquer_champ(champs_autorises: set, payload: ChampValeur, maj_fn, *args):
    if payload.champ not in champs_autorises:
        raise HTTPException(status_code=422, detail=f"Champ non autorisé : {payload.champ}")
    maj_fn(*args, payload.champ, payload.valeur)
    return {"ok": True}


# ------------------------------------------------------------------------------
#  PROSPECTS
# ------------------------------------------------------------------------------
@app.get("/prospects")
def api_lire_prospects(current=Depends(get_current_user)):
    return _df_payload(lire_prospects())


@app.get("/prospects/{prospect_id}")
def api_lire_prospect(prospect_id: int, current=Depends(get_current_user)):
    conn = get_conn()
    row = conn.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Prospect introuvable.")
    return dict(row)


@app.post("/prospects")
def api_creer_prospect(payload: ProspectCreate, current=Depends(CONSEILLER_OU_ADMIN)):
    if payload.email and not valider_email(payload.email):
        raise HTTPException(status_code=422, detail="Email invalide.")
    if payload.telephone and not valider_telephone(payload.telephone):
        raise HTTPException(status_code=422, detail="Numéro de téléphone invalide.")
    d = payload.model_dump()
    d["ref"]      = generer_ref()
    d["cree_par"] = current["nom_complet"]
    d["origine"]  = "API"
    pid = ajouter_prospect(d)
    return {"id": pid}


@app.patch("/prospects/{prospect_id}")
def api_maj_prospect(prospect_id: int, payload: ChampValeur, current=Depends(CONSEILLER_OU_ADMIN)):
    return _appliquer_champ(CHAMPS_PROSPECT, payload, maj_prospect, prospect_id)


@app.delete("/prospects/{prospect_id}")
def api_supprimer_prospect(prospect_id: int, current=Depends(CONSEILLER_OU_ADMIN)):
    supprimer_prospect(prospect_id)
    return {"ok": True}


# ------------------------------------------------------------------------------
#  CLIENTS
# ------------------------------------------------------------------------------
@app.get("/clients")
def api_lire_clients(current=Depends(get_current_user)):
    return _df_payload(lire_clients())


@app.get("/clients/{client_id}")
def api_lire_client(client_id: int, current=Depends(get_current_user)):
    conn = get_conn()
    row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Client introuvable.")
    return dict(row)


@app.post("/clients")
def api_creer_client(payload: ClientCreate, current=Depends(CONSEILLER_OU_ADMIN)):
    if payload.email and not valider_email(payload.email):
        raise HTTPException(status_code=422, detail="Email invalide.")
    if payload.telephone and not valider_telephone(payload.telephone):
        raise HTTPException(status_code=422, detail="Numéro de téléphone invalide.")
    d = payload.model_dump()
    d["ref"]      = generer_ref()
    d["cree_par"] = current["nom_complet"]
    cid = ajouter_client(d)
    return {"id": cid}


@app.patch("/clients/{client_id}")
def api_maj_client(client_id: int, payload: ChampValeur, current=Depends(CONSEILLER_OU_ADMIN)):
    if payload.champ not in CHAMPS_CLIENT:
        raise HTTPException(status_code=422, detail=f"Champ non autorisé : {payload.champ}")
    maj_client(client_id, payload.champ, payload.valeur, auteur=current["nom_complet"])
    return {"ok": True}


@app.delete("/clients/{client_id}")
def api_supprimer_client(client_id: int, current=Depends(CONSEILLER_OU_ADMIN)):
    supprimer_client(client_id, auteur=current["nom_complet"])
    return {"ok": True}


# ------------------------------------------------------------------------------
#  CONTRATS (rattachés à un client)
# ------------------------------------------------------------------------------
@app.get("/clients/{client_id}/contrats")
def api_lire_contrats(client_id: int, current=Depends(get_current_user)):
    return _df_payload(lire_contrats_client(client_id))


@app.post("/clients/{client_id}/contrats")
def api_creer_contrat(client_id: int, payload: ContratCreate, current=Depends(CONSEILLER_OU_ADMIN)):
    d = payload.model_dump()
    d["client_id"] = client_id
    d["cree_par"]  = current["nom_complet"]
    ajouter_contrat(d)
    return {"ok": True}


@app.patch("/contrats/{contrat_id}")
def api_maj_contrat(contrat_id: int, payload: ChampValeur, current=Depends(CONSEILLER_OU_ADMIN)):
    if payload.champ not in CHAMPS_CONTRAT:
        raise HTTPException(status_code=422, detail=f"Champ non autorisé : {payload.champ}")
    maj_contrat(contrat_id, payload.champ, payload.valeur, auteur=current["nom_complet"])
    return {"ok": True}


@app.delete("/contrats/{contrat_id}")
def api_supprimer_contrat(contrat_id: int, current=Depends(CONSEILLER_OU_ADMIN)):
    supprimer_contrat(contrat_id, auteur=current["nom_complet"])
    return {"ok": True}


# ------------------------------------------------------------------------------
#  OFFRES (catalogue) — gestion réservée aux admins, comme dans l'onglet Admin
# ------------------------------------------------------------------------------
@app.get("/offres")
def api_lire_offres(univers: Optional[str] = None, categorie: Optional[str] = None,
                     actif_seulement: bool = True, current=Depends(get_current_user)):
    return _df_payload(lire_offres(univers=univers, categorie=categorie, actif_seulement=actif_seulement))


@app.post("/offres")
def api_creer_offre(payload: OffreCreate, current=Depends(ADMIN_SEUL)):
    ajouter_offre(payload.model_dump())
    return {"ok": True}


@app.patch("/offres/{offre_id}")
def api_maj_offre(offre_id: int, payload: ChampValeur, current=Depends(ADMIN_SEUL)):
    return _appliquer_champ(CHAMPS_OFFRE, payload, maj_offre, offre_id)


@app.delete("/offres/{offre_id}")
def api_supprimer_offre(offre_id: int, current=Depends(ADMIN_SEUL)):
    supprimer_offre(offre_id)
    return {"ok": True}


# ------------------------------------------------------------------------------
#  DIAGNOSTIC — comparaison d'offres et bilan chiffré (auth requise, sans limite
#  de débit contrairement à chatbot_api.py qui est exposée publiquement)
# ------------------------------------------------------------------------------
class OffresCompareIn(BaseModel):
    univers: str
    categorie: Optional[str] = None
    cout_actuel_mensuel: float
    fournisseurs_autorises: Optional[List[str]] = None
    fournisseur_exclu: Optional[str] = None
    data_go_min: Optional[float] = None


@app.post("/diagnostic/comparer")
def api_diagnostic_comparer(payload: OffresCompareIn, current=Depends(get_current_user)):
    resultats = comparer_offres(
        payload.univers, payload.categorie, safe_float(payload.cout_actuel_mensuel),
        fournisseurs_autorises=payload.fournisseurs_autorises,
        fournisseur_exclu=payload.fournisseur_exclu,
        data_go_min=payload.data_go_min,
    )
    return {"resultats": resultats}


class BilanIn(BaseModel):
    service_principal: str
    cout_tel: float
    fournisseurs_autorises: Optional[List[str]] = None
    fournisseur_exclu: Optional[str] = None
    data_go_min: Optional[float] = None


@app.post("/diagnostic/bilan")
def api_diagnostic_bilan(payload: BilanIn, current=Depends(get_current_user)):
    """Renvoie la structure brute de construire_recommandations() (principal +
    cross_sell), consommée telle quelle par api_client.construire_recommandations
    pour l'assistant de diagnostic Streamlit."""
    reco = construire_recommandations(
        payload.service_principal, safe_float(payload.cout_tel),
        fournisseurs_autorises=payload.fournisseurs_autorises,
        fournisseur_exclu=payload.fournisseur_exclu, data_go_min=payload.data_go_min,
    )
    titre_p, offres_p = reco["principal"]
    return {
        "principal": {"titre": titre_p, "offres": offres_p},
        "cross_sell": [{"titre": t, "offres": o} for t, o in reco["cross_sell"]],
    }


class DiagnosticCompletIn(BaseModel):
    service_principal: str
    cout_tel: float = 0.0
    fournisseur_exclu: Optional[str] = None
    data_go_min: Optional[float] = None
    cout_elec: float = 0.0
    cout_gaz: float = 0.0
    abonnements: Optional[List[Dict[str, Any]]] = None   # [{"nom": "...", "cout": 9.99}, ...]


@app.post("/diagnostic/complet")
def api_diagnostic_complet(payload: DiagnosticCompletIn, current=Depends(get_current_user)):
    """Diagnostic complet multi-univers (Télécom + Énergie + Abonnements) : reprend
    la même logique que l'assistant de diagnostic Streamlit (app.py, étape 4), pour
    des consommateurs headless (app mobile, portail client, webhooks)."""
    reco = construire_recommandations(
        payload.service_principal, safe_float(payload.cout_tel),
        fournisseur_exclu=payload.fournisseur_exclu, data_go_min=payload.data_go_min,
    )
    titre_p, offres_p = reco["principal"]
    economie_max = offres_p[0]["economie_annuelle"] if offres_p else 0.0

    energie = {}
    for cat, cout in (("Électricité", payload.cout_elec), ("Gaz", payload.cout_gaz)):
        if cout > 0:
            offres = comparer_offres("Énergie", cat, float(cout)) or comparer_offres("Énergie", cat + " Pro", float(cout))
            if offres:
                energie[cat] = offres[:3]

    abonnements = []
    for a in (payload.abonnements or []):
        cout_abo = safe_float(a.get("cout"))
        alt = [o for o in comparer_offres("Abonnements", None, cout_abo) if safe_float(o["prix_mensuel"]) < cout_abo]
        if alt:
            o = alt[0]
            eco_an = round((cout_abo - safe_float(o["prix_mensuel"])) * 12, 2)
            abonnements.append({"nom": a.get("nom"), "actuel": cout_abo,
                                 "alternative": {**o, "economie_annuelle": eco_an}})

    return {
        "telecom": {
            "principal": {"titre": titre_p, "offres": offres_p},
            "cross_sell": [{"titre": t, "offres": o} for t, o in reco["cross_sell"]],
        },
        "energie": energie,
        "abonnements": abonnements,
        "economie_max_annuelle": economie_max,
    }


@app.get("/health")
def health():
    return {"statut": "ok"}
