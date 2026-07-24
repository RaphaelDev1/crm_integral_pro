# ==============================================================================
#  LRE ENGINE — wrapper API AR24 (lettre recommandée électronique). Envoi
#  tracé et à valeur légale des documents de démarche (résiliation,
#  portabilité, changement de fournisseur).
#
#  Convention volontairement différente de `notification_engine.py` : ici on
#  LÈVE `LreEngineError` (y compris si non configuré) plutôt que de renvoyer
#  silencieusement `False`. La LRE est le canal légalement requis pour ces
#  démarches — contrairement à un SMS/email de confort, un échec silencieux
#  laisserait une démarche non envoyée sans que personne ne le sache.
#  L'appelant (tâche Celery, voir backend/workers/tasks.py) catch cette
#  exception et persiste explicitement `Demarche.statut="echouee"` + une note.
#
#  ⚠️ Endpoints/champs exacts (chemins, forme de `destinataire`, vocabulaire
#  de statut) à confirmer contre la documentation AR24 réelle avant mise en
#  prod — aucun compte AR24 créé à ce jour (voir SETUP_STATUS.md). Tant que
#  `AR24_API_KEY` n'est pas configurée, toute fonction lève immédiatement
#  `LreEngineError` sans appel réseau (même doctrine que
#  signature_engine.py::_client pour Yousign).
# ==============================================================================
from __future__ import annotations

from typing import Any

import httpx

from backend.core.config import settings


class LreEngineError(Exception):
    """Erreur retournée par l'API AR24 (statut HTTP non 2xx) ou clé API absente."""


def _client() -> httpx.AsyncClient:
    if not settings.ar24_api_key:
        raise LreEngineError("AR24_API_KEY absente (voir backend/.env.example).")
    return httpx.AsyncClient(
        base_url=settings.ar24_api_url,
        headers={"Authorization": f"Bearer {settings.ar24_api_key}"},
        timeout=30.0,
    )


async def _appel(methode: str, chemin: str, **kwargs: Any) -> dict:
    async with _client() as client:
        reponse = await client.request(methode, chemin, **kwargs)
    if reponse.status_code >= 400:
        raise LreEngineError(f"AR24 {methode} {chemin} → {reponse.status_code} : {reponse.text}")
    return reponse.json() if reponse.content else {}


async def envoyer_lre(destinataire: dict, sujet: str, pdf: bytes, nom_fichier: str) -> dict:
    """Envoie un document en LRE. `destinataire` : {"prenom", "nom", "email"}
    (champs exacts à confirmer contre la doc AR24). Retourne
    {"lre_id": str, "statut": str}. Lève `LreEngineError` si non configuré ou
    si l'API répond en erreur — ne renvoie jamais silencieusement un échec."""
    fichiers = {"file": (nom_fichier, pdf, "application/pdf")}
    resultat = await _appel("POST", "/lre/send", data={"subject": sujet, **destinataire}, files=fichiers)
    return {"lre_id": resultat.get("id"), "statut": resultat.get("status", "envoyee")}


async def verifier_statut_lre(lre_id: str) -> dict:
    """Interroge le statut d'une LRE envoyée (polling — AR24 ne garantit pas
    de webhook aussi fiable que Yousign pour ce cas d'usage, à confirmer).
    Retourne {"lre_id": str, "statut": str}."""
    resultat = await _appel("GET", f"/lre/{lre_id}/status")
    return {"lre_id": lre_id, "statut": resultat.get("status")}


async def telecharger_preuve_depot(lre_id: str) -> bytes:
    """Télécharge l'accusé de dépôt/réception (PDF probant AR24)."""
    async with _client() as client:
        reponse = await client.get(f"/lre/{lre_id}/proof")
    if reponse.status_code >= 400:
        raise LreEngineError(f"AR24 téléchargement preuve {lre_id} → {reponse.status_code}")
    return reponse.content
