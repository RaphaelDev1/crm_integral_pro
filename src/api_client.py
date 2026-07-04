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

API_BASE_URL = os.environ.get("CRM_API_URL", "http://127.0.0.1:8000")
TIMEOUT      = float(os.environ.get("CRM_API_TIMEOUT", "3"))


class _ApiIndisponible(Exception):
    pass


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


def _requete(methode: str, path: str, **kwargs):
    if not REQUESTS_OK:
        raise _ApiIndisponible("Bibliothèque 'requests' non installée.")
    try:
        reponse = requests.request(methode, f"{API_BASE_URL}{path}", headers=_headers(),
                                    timeout=TIMEOUT, **kwargs)
        reponse.raise_for_status()
        return reponse.json()
    except Exception as exc:
        raise _ApiIndisponible(str(exc)) from exc


def _df_depuis_payload(payload: dict) -> pd.DataFrame:
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
