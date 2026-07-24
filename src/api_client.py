# ==============================================================================
#  CLIENT DE L'API CRM INTERNE — utilisé par app.py (Streamlit) à la place d'un
#  accès direct aux modules *_engine.py, pour les entités déjà exposées par
#  crm_api.py (Roadmap 4.3 : « Streamlit appelle l'API au lieu de la BDD »).
#
#  Chaque fonction a EXACTEMENT la même signature et le même type de retour que
#  son équivalent dans *_engine.py — un simple changement d'import dans app.py
#  suffit donc à activer le découplage, sans toucher au reste du fichier.
#
#  Repli automatique : si l'API n'est pas démarrée, injoignable, ou renvoie une
#  erreur réseau, chaque fonction retombe silencieusement sur l'appel direct au
#  module *_engine.py correspondant — le logiciel continue de fonctionner à
#  l'identique (on est encore en phase de test, l'API n'est pas systématiquement
#  lancée sur tous les postes).
# ==============================================================================
import os

import pandas as pd

try:
    import requests
    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

import clients_engine as _clients_db
import contrats_engine as _contrats_db
import offres_engine as _offres_db
import prospects_engine as _prospects_db

# Deux backends distincts et volontairement isolés l'un de l'autre :
#  - CRM_API_URL     : src/crm_api.py (SQLite, prospects/clients/contrats/offres/diagnostic).
#                      Port 8003 par défaut (voir ROADMAP_BACKEND_SETUP.md §2) — PAS 8000, pour
#                      ne jamais atterrir par erreur sur backend/ si les deux tournent en même
#                      temps : backend/ n'implémente ni /contrats ni /offres, et son /clients
#                      pointe vers une base Postgres différente. Les faire cohabiter sur le même
#                      port a déjà provoqué des IntegrityError (contrat créé en repli SQLite
#                      avec un client_id qui n'existe que côté Postgres) et des clients
#                      « impossibles à supprimer » (DELETE routé vers la mauvaise base).
#  - BACKEND_API_URL : backend/main.py (Postgres, dossiers/factures/honoraires/portail client).
#                      Port 8000 par défaut — aucun repli local possible pour ces fonctions.
API_BASE_URL     = os.environ.get("CRM_API_URL", "http://127.0.0.1:8003")
BACKEND_API_URL  = os.environ.get("BACKEND_API_URL", "http://127.0.0.1:8000")
TIMEOUT      = float(os.environ.get("CRM_API_TIMEOUT", "3"))


class _ApiIndisponible(Exception):
    pass


# Alias public — utilisé par app.py pour les fonctionnalités backend/ sans
# équivalent local (dossiers, briefing, factures liées à un client) : il n'y a
# ici aucun repli SQLite possible, l'appelant doit donc pouvoir attraper
# l'erreur lui-même et afficher un message clair au conseiller.
ApiIndisponible = _ApiIndisponible


def _token():
    try:
        import streamlit as st
        return st.session_state.get("api_token")
    except Exception:
        return None


def _headers():
    token = _token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _signaler_repli(contexte: str):
    """Avertit une seule fois par session (si contexte Streamlit dispo) que l'API
    n'a pas répondu et que l'appel est retombé sur un accès direct à la base."""
    try:
        import streamlit as st
        cle = "_api_repli_signale"
        if not st.session_state.get(cle):
            st.session_state[cle] = True
            st.toast("⚠️ API CRM interne injoignable — bascule sur l'accès direct à la base.", icon="⚠️")
    except Exception:
        pass


def _requete(methode: str, path: str, base: str = None, **kwargs):
    if not REQUESTS_OK:
        raise _ApiIndisponible("Bibliothèque 'requests' non installée.")
    try:
        reponse = requests.request(methode, f"{base or API_BASE_URL}{path}", headers=_headers(),
                                    timeout=TIMEOUT, **kwargs)
        reponse.raise_for_status()
        return reponse.json()
    except Exception as exc:
        raise _ApiIndisponible(str(exc)) from exc


def _df_depuis_payload(payload) -> pd.DataFrame:
    """Accepte les deux formats renvoyés par les API internes : l'ancien
    {columns, records} (src/crm_api.py, encore utilisé pour /contrats et
    /offres) et la liste JSON brute renvoyée par backend/ (routers clients.py
    et prospects.py, qui ont remplacé leurs équivalents crm_api.py)."""
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    return pd.DataFrame(payload["records"], columns=payload["columns"])


# ------------------------------------------------------------------------------
#  PROSPECTS
# ------------------------------------------------------------------------------
def ajouter_prospect(d: dict):
    try:
        return _requete("POST", "/prospects", json=d)["id"]
    except _ApiIndisponible:
        _signaler_repli("ajouter_prospect")
        return _prospects_db.ajouter_prospect(d)


def lire_prospects() -> pd.DataFrame:
    try:
        return _df_depuis_payload(_requete("GET", "/prospects"))
    except _ApiIndisponible:
        _signaler_repli("lire_prospects")
        return _prospects_db.lire_prospects()


def maj_prospect(pid: int, champ: str, valeur):
    try:
        _requete("PATCH", f"/prospects/{pid}", json={"champ": champ, "valeur": valeur})
    except _ApiIndisponible:
        _signaler_repli("maj_prospect")
        _prospects_db.maj_prospect(pid, champ, valeur)


def supprimer_prospect(pid: int):
    try:
        _requete("DELETE", f"/prospects/{pid}")
    except _ApiIndisponible:
        _signaler_repli("supprimer_prospect")
        _prospects_db.supprimer_prospect(pid)


# ------------------------------------------------------------------------------
#  CLIENTS
# ------------------------------------------------------------------------------
def ajouter_client(d: dict) -> int:
    try:
        return _requete("POST", "/clients", json=d)["id"]
    except _ApiIndisponible:
        _signaler_repli("ajouter_client")
        return _clients_db.ajouter_client(d)


def lire_clients() -> pd.DataFrame:
    try:
        return _df_depuis_payload(_requete("GET", "/clients"))
    except _ApiIndisponible:
        _signaler_repli("lire_clients")
        return _clients_db.lire_clients()


def maj_client(cid: int, champ: str, valeur):
    try:
        _requete("PATCH", f"/clients/{cid}", json={"champ": champ, "valeur": valeur})
    except _ApiIndisponible:
        _signaler_repli("maj_client")
        _clients_db.maj_client(cid, champ, valeur)


def supprimer_client(cid: int):
    try:
        _requete("DELETE", f"/clients/{cid}")
    except _ApiIndisponible:
        _signaler_repli("supprimer_client")
        _clients_db.supprimer_client(cid)


# ------------------------------------------------------------------------------
#  CONTRATS
# ------------------------------------------------------------------------------
def ajouter_contrat(d: dict):
    if d.get("prospect_id"):
        # crm_api.py n'expose pour l'instant que /clients/{id}/contrats — les contrats
        # rattachés à un prospect passent directement par la base locale.
        _contrats_db.ajouter_contrat(d)
        return
    try:
        _requete("POST", f"/clients/{d.get('client_id')}/contrats", json=d)
    except _ApiIndisponible:
        _signaler_repli("ajouter_contrat")
        _contrats_db.ajouter_contrat(d)


def lire_contrats_client(cid: int) -> pd.DataFrame:
    try:
        return _df_depuis_payload(_requete("GET", f"/clients/{cid}/contrats"))
    except _ApiIndisponible:
        _signaler_repli("lire_contrats_client")
        return _contrats_db.lire_contrats_client(cid)


def lire_contrats_prospect(pid: int) -> pd.DataFrame:
    """Autres contrats du prospect (ajoutés par le conseiller) — pas de route crm_api.py
    dédiée, accès direct à la base locale (cf. ajouter_contrat)."""
    return _contrats_db.lire_contrats_prospect(pid)


def transferer_contrats_dossier_vers_client(pid: int, cid: int):
    """Pas de route crm_api.py dédiée (opération interne à la conversion prospect→client),
    accès direct à la base locale."""
    _contrats_db.transferer_contrats_dossier_vers_client(pid, cid)


def maj_contrat(ctid: int, champ: str, valeur):
    try:
        _requete("PATCH", f"/contrats/{ctid}", json={"champ": champ, "valeur": valeur})
    except _ApiIndisponible:
        _signaler_repli("maj_contrat")
        _contrats_db.maj_contrat(ctid, champ, valeur)


def supprimer_contrat(ctid: int):
    try:
        _requete("DELETE", f"/contrats/{ctid}")
    except _ApiIndisponible:
        _signaler_repli("supprimer_contrat")
        _contrats_db.supprimer_contrat(ctid)


# ------------------------------------------------------------------------------
#  OFFRES + DIAGNOSTIC
# ------------------------------------------------------------------------------
def ajouter_offre(d: dict):
    try:
        _requete("POST", "/offres", json=d)
    except _ApiIndisponible:
        _signaler_repli("ajouter_offre")
        _offres_db.ajouter_offre(d)


def lire_offres(univers=None, categorie=None, actif_seulement=True) -> pd.DataFrame:
    try:
        params = {"actif_seulement": actif_seulement}
        if univers:
            params["univers"] = univers
        if categorie:
            params["categorie"] = categorie
        return _df_depuis_payload(_requete("GET", "/offres", params=params))
    except _ApiIndisponible:
        _signaler_repli("lire_offres")
        return _offres_db.lire_offres(univers=univers, categorie=categorie, actif_seulement=actif_seulement)


def maj_offre(oid: int, champ: str, valeur):
    try:
        _requete("PATCH", f"/offres/{oid}", json={"champ": champ, "valeur": valeur})
    except _ApiIndisponible:
        _signaler_repli("maj_offre")
        _offres_db.maj_offre(oid, champ, valeur)


def supprimer_offre(oid: int):
    try:
        _requete("DELETE", f"/offres/{oid}")
    except _ApiIndisponible:
        _signaler_repli("supprimer_offre")
        _offres_db.supprimer_offre(oid)


def comparer_offres(univers, categorie, cout_actuel_mensuel, fournisseurs_autorises=None,
                     fournisseur_exclu=None, data_go_min=None):
    try:
        return _requete("POST", "/diagnostic/comparer", json={
            "univers": univers, "categorie": categorie, "cout_actuel_mensuel": cout_actuel_mensuel,
            "fournisseurs_autorises": fournisseurs_autorises, "fournisseur_exclu": fournisseur_exclu,
            "data_go_min": data_go_min,
        })["resultats"]
    except _ApiIndisponible:
        _signaler_repli("comparer_offres")
        return _offres_db.comparer_offres(univers, categorie, cout_actuel_mensuel,
                                           fournisseurs_autorises=fournisseurs_autorises,
                                           fournisseur_exclu=fournisseur_exclu, data_go_min=data_go_min)


def construire_recommandations(service_principal, cout_tel, fournisseurs_autorises=None,
                                fournisseur_exclu=None, data_go_min=None):
    try:
        data = _requete("POST", "/diagnostic/bilan", json={
            "service_principal": service_principal, "cout_tel": cout_tel,
            "fournisseurs_autorises": fournisseurs_autorises,
            "fournisseur_exclu": fournisseur_exclu, "data_go_min": data_go_min,
        })
        principal   = (data["principal"]["titre"], data["principal"]["offres"])
        cross_sell  = [(cs["titre"], cs["offres"]) for cs in data["cross_sell"]]
        return {"principal": principal, "cross_sell": cross_sell}
    except _ApiIndisponible:
        _signaler_repli("construire_recommandations")
        return _offres_db.construire_recommandations(service_principal, cout_tel,
                                                       fournisseurs_autorises=fournisseurs_autorises,
                                                       fournisseur_exclu=fournisseur_exclu,
                                                       data_go_min=data_go_min)


# ------------------------------------------------------------------------------
#  DOSSIERS / BRIEFING / FACTURES — fonctionnalités propres à backend/ (API
#  FastAPI + Postgres), sans équivalent dans les modules *_engine.py côté
#  SQLite. Aucun repli local possible ici : en cas d'échec, l'appelant (app.py)
#  doit attraper `ApiIndisponible` et informer le conseiller que le backend
#  (uvicorn backend.main:app) doit être lancé pour utiliser ces fonctions.
# ------------------------------------------------------------------------------
# Champs communs entre le client SQLite (clients_engine.CHAMPS_CLIENT + prenom/nom) et le
# schéma backend/schemas/client.py::ClientBase — payload envoyé pour créer/rafraîchir le miroir.
_CHAMPS_CLIENT_BACKEND = (
    "ref", "prenom", "nom", "telephone", "email", "code_postal", "ville", "adresse",
    "type_client", "operateur_actuel", "techno", "data_go", "offre_actuelle",
    "cout_mensuel_actuel", "satisfaction_reseau", "veut_rester", "speed_down", "speed_up",
    "fournisseur_energie", "cout_elec", "cout_gaz", "economie_estimee_an", "notes",
    "date_relance", "statut_relance",
)


def _backend_client_id_pour(client: dict, entite: str = "client") -> int:
    """Retrouve (ou crée) le client miroir côté backend/ (Postgres) pour ce client OU ce
    prospect SQLite — nécessaire tant que la migration SQLite → Postgres (ROADMAP_EXECUTION
    Sprint 2) n'est pas faite : backend/ (dossiers, mandats, portail client) et le CRM
    Streamlit (clients/prospects/contrats) vivent dans deux bases disjointes avec des id
    indépendants. L'id SQLite ne peut donc jamais être envoyé tel quel comme client_id à
    backend/ (FK violation systématique sinon).

    `entite="prospect"` permet à un prospect (pas encore converti en client, cf.
    app.py::_finaliser_prospect_en_client) d'avoir lui aussi un dossier suivi côté backend/ —
    le miroir Postgres reste un `Client` (backend/models/dossier.py::Dossier.client_id pointe
    uniquement vers `clients`), seul l'endroit où l'on mémorise `backend_client_id` change
    (table `prospects` au lieu de `clients`, via prospects_engine.definir_backend_client_id)."""
    _db = _prospects_db if entite == "prospect" else _clients_db
    payload = {k: client.get(k) for k in _CHAMPS_CLIENT_BACKEND}
    backend_id = client.get("backend_client_id")
    if backend_id:
        # Rafraîchit le miroir (tél/email notamment — utilisés par backend/ pour l'envoi du
        # lien portail SMS/email) au cas où la fiche SQLite a été modifiée depuis sa création.
        _requete("PUT", f"/clients/{int(backend_id)}", base=BACKEND_API_URL, json=payload)
        return int(backend_id)
    cree = _requete("POST", "/clients", base=BACKEND_API_URL, json=payload)
    _db.definir_backend_client_id(int(client["id"]), cree["id"])
    return cree["id"]


def creer_dossier(client: dict, univers: str, fournisseur_cible: str = "",
                   economie_annuelle_estimee: float = 0.0, entite: str = "client") -> dict:
    backend_client_id = _backend_client_id_pour(client, entite=entite)
    return _requete("POST", "/dossiers", base=BACKEND_API_URL, json={
        "client_id": backend_client_id,
        "univers": univers,
        "fournisseur_cible": fournisseur_cible or None,
        "economie_annuelle_estimee": economie_annuelle_estimee,
    })


def lire_dossiers_client(client_id: int) -> list:
    return _requete("GET", "/dossiers", base=BACKEND_API_URL, params={"client_id": client_id})


def envoyer_lien_client(dossier_id: int, canal: str) -> dict:
    """Génère le lien personnel du client et l'envoie par le canal choisi
    ("sms" ou "email", selon la préférence du client) —
    POST /dossiers/{id}/envoyer-lien-client."""
    return _requete(
        "POST", f"/dossiers/{dossier_id}/envoyer-lien-client", base=BACKEND_API_URL,
        json={"canal": canal},
    )


def obtenir_briefing_client(client_id: int) -> dict:
    """Vue agrégée (infos client + dossier en cours + dernière facture
    analysée) à consulter avant d'appeler — GET /clients/{id}/briefing."""
    return _requete("GET", f"/clients/{client_id}/briefing", base=BACKEND_API_URL)


def obtenir_dossier(dossier_id: int) -> dict:
    """Détail complet d'un dossier, notes_workflow inclus — GET /dossiers/{id}."""
    return _requete("GET", f"/dossiers/{dossier_id}", base=BACKEND_API_URL)


def obtenir_timeline_dossier(dossier_id: int) -> list:
    """Étapes du stepper (statut/date/icône par étape), à afficher au
    conseiller — GET /dossiers/{id}/timeline."""
    return _requete("GET", f"/dossiers/{dossier_id}/timeline", base=BACKEND_API_URL)


def ajouter_note_dossier(dossier_id: int, texte: str) -> dict:
    """Ajoute une note manuelle au journal du dossier, sans changer son
    statut — POST /dossiers/{id}/notes."""
    return _requete("POST", f"/dossiers/{dossier_id}/notes", base=BACKEND_API_URL, json={"texte": texte})


def obtenir_mandat_honoraires(dossier_id: int) -> dict | None:
    """Mandat d'honoraires du dossier (le cas échéant) — GET
    /dossiers/{id}/mandat-honoraires."""
    return _requete("GET", f"/dossiers/{dossier_id}/mandat-honoraires", base=BACKEND_API_URL)


def creer_mandat_honoraires(dossier_id: int, montant: float, taux: float) -> dict:
    """Crée le mandat d'honoraires du dossier — POST
    /dossiers/{id}/mandat-honoraires."""
    return _requete("POST", f"/dossiers/{dossier_id}/mandat-honoraires", base=BACKEND_API_URL,
                     json={"montant": montant, "taux": taux})


def marquer_signe_honoraires(dossier_id: int, signataire: str) -> dict:
    """Marque le mandat d'honoraires du dossier comme signé — POST
    /dossiers/{id}/mandat-honoraires/marquer-signe."""
    return _requete("POST", f"/dossiers/{dossier_id}/mandat-honoraires/marquer-signe", base=BACKEND_API_URL,
                     json={"signataire": signataire})


def lister_demarches(dossier_id: int) -> dict:
    """Démarches existantes + types requis pas encore créés pour ce dossier
    — GET /dossiers/{id}/demarches."""
    return _requete("GET", f"/dossiers/{dossier_id}/demarches", base=BACKEND_API_URL)


def creer_demarche(dossier_id: int, type_demarche: str) -> dict:
    """Crée une démarche (mandat/résiliation/portabilité/souscription/
    changement_fournisseur) pour ce dossier — POST /dossiers/{id}/demarches."""
    return _requete("POST", f"/dossiers/{dossier_id}/demarches", base=BACKEND_API_URL,
                     json={"type_demarche": type_demarche})


def generer_demarche(demarche_id: int) -> dict:
    """Lance la génération du document PDF de la démarche (async, refuse si
    le mandat de représentation n'est pas signé) — POST /demarches/{id}/generer."""
    return _requete("POST", f"/demarches/{demarche_id}/generer", base=BACKEND_API_URL)


def envoyer_demarche(demarche_id: int) -> dict:
    """Lance l'envoi en LRE du document déjà généré (async) — POST
    /demarches/{id}/envoyer."""
    return _requete("POST", f"/demarches/{demarche_id}/envoyer", base=BACKEND_API_URL)


def renseigner_champs_demarche(demarche_id: int, valeurs: dict) -> dict:
    """Renseigne les champs manquants d'une démarche (RIO, PDL/PCE, RIB…) —
    PATCH /demarches/{id}/champs."""
    return _requete("PATCH", f"/demarches/{demarche_id}/champs", base=BACKEND_API_URL, json={"valeurs": valeurs})


def demarche_document_url(demarche_id: int) -> str:
    """URL signée (temporaire) du PDF généré pour cette démarche — GET
    /demarches/{id}/document."""
    return _requete("GET", f"/demarches/{demarche_id}/document", base=BACKEND_API_URL)["url"]


def analyser_facture_client(fichier_bytes: bytes, nom_fichier: str, client_id: int) -> dict:
    """Envoie une facture PDF à l'analyse LLM (backend/services/
    facture_analyzer.py) et persiste le résultat, lié à `client_id`, pour le
    briefing — POST /factures/analyze (multipart, distinct de `_requete` qui
    n'envoie que du JSON)."""
    if not REQUESTS_OK:
        raise _ApiIndisponible("Bibliothèque 'requests' non installée.")
    try:
        reponse = requests.post(
            f"{BACKEND_API_URL}/factures/analyze",
            headers=_headers(),
            files={"fichier": (nom_fichier, fichier_bytes, "application/pdf")},
            data={"client_id": client_id},
            timeout=30,
        )
        reponse.raise_for_status()
        return reponse.json()
    except Exception as exc:
        raise _ApiIndisponible(str(exc)) from exc
