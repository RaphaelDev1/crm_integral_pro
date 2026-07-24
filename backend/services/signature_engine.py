# ==============================================================================
#  SIGNATURE ÉLECTRONIQUE — wrapper API Yousign v3 : créer une demande de
#  signature, y attacher le PDF du mandat et le signataire, l'activer (envoi),
#  vérifier/parser les webhooks, télécharger le PDF signé une fois la
#  procédure terminée. Référence API : https://developers.yousign.com
# ==============================================================================
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Literal

import httpx

from backend.core.config import settings

SignatureLevel = Literal["electronic_signature", "advanced_electronic_signature"]
AuthMode = Literal["no_otp", "otp_email", "otp_sms"]


class SignatureEngineError(Exception):
    """Erreur retournée par l'API Yousign (statut HTTP non 2xx) ou clé API
    absente."""


def _client() -> httpx.AsyncClient:
    if not settings.yousign_api_key:
        raise SignatureEngineError("YOUSIGN_API_KEY absente (voir backend/.env.example).")
    return httpx.AsyncClient(
        base_url=settings.yousign_api_url,
        headers={"Authorization": f"Bearer {settings.yousign_api_key}"},
        timeout=30.0,
    )


async def _appel(methode: str, chemin: str, **kwargs: Any) -> dict:
    async with _client() as client:
        reponse = await client.request(methode, chemin, **kwargs)
    if reponse.status_code >= 400:
        raise SignatureEngineError(f"Yousign {methode} {chemin} → {reponse.status_code} : {reponse.text}")
    return reponse.json() if reponse.content else {}


async def creer_demande_signature(nom: str, delivery_mode: str = "email") -> dict:
    """Crée une demande de signature à l'état 'draft'. Retourne l'objet Yousign
    (son id est nécessaire pour toutes les étapes suivantes)."""
    return await _appel(
        "POST",
        "/signature_requests",
        json={"name": nom, "delivery_mode": delivery_mode, "timezone": "Europe/Paris"},
    )


async def ajouter_document(signature_request_id: str, pdf: bytes, nom_fichier: str) -> dict:
    """Attache le PDF du mandat à la demande de signature. Retourne l'objet
    document Yousign (son id est nécessaire pour positionner le champ de
    signature)."""
    fichiers = {"file": (nom_fichier, pdf, "application/pdf")}
    return await _appel(
        "POST",
        f"/signature_requests/{signature_request_id}/documents",
        data={"nature": "signable_document"},
        files=fichiers,
    )


async def ajouter_signataire(
    signature_request_id: str,
    document_id: str,
    *,
    prenom: str,
    nom: str,
    email: str,
    telephone: str | None = None,
    page: int = 1,
    x: int = 100,
    y: int = 100,
    signature_level: SignatureLevel = "electronic_signature",
    auth_mode: AuthMode = "otp_email",
) -> dict:
    """Ajoute le client comme signataire, avec un champ de signature positionné
    sur le document. `auth_mode="otp_email"` par défaut (code reçu par email
    avant signature) — passer "otp_sms" si le téléphone client est vérifié."""
    info: dict[str, Any] = {"first_name": prenom, "last_name": nom, "email": email, "locale": "fr"}
    if telephone:
        info["phone_number"] = telephone
    return await _appel(
        "POST",
        f"/signature_requests/{signature_request_id}/signers",
        json={
            "info": info,
            "signature_level": signature_level,
            "signature_authentication_mode": auth_mode,
            "fields": [{"document_id": document_id, "type": "signature", "page": page, "x": x, "y": y}],
        },
    )


async def activer_demande(signature_request_id: str) -> dict:
    """Passe la demande de 'draft' à 'ongoing' — déclenche l'envoi de
    l'invitation à signer (email ou SMS) au(x) signataire(s)."""
    return await _appel("POST", f"/signature_requests/{signature_request_id}/activate")


async def telecharger_document_signe(signature_request_id: str, document_id: str) -> bytes:
    """Télécharge le PDF signé — disponible uniquement une fois la demande au
    statut 'done' (après réception de l'événement webhook correspondant)."""
    async with _client() as client:
        reponse = await client.get(f"/signature_requests/{signature_request_id}/documents/{document_id}/download")
    if reponse.status_code >= 400:
        raise SignatureEngineError(
            f"Yousign download {signature_request_id}/{document_id} → {reponse.status_code}"
        )
    return reponse.content


async def envoyer_mandat(
    *,
    nom_demande: str,
    pdf: bytes,
    nom_fichier: str,
    prenom: str,
    nom: str,
    email: str,
    telephone: str | None = None,
) -> dict:
    """Orchestration complète : crée la demande, y attache le mandat, ajoute le
    client comme signataire et active l'envoi. Retourne
    {signature_request_id, document_id} à stocker sur le Mandat pour
    retrouver la procédure lors du webhook."""
    demande = await creer_demande_signature(nom_demande)
    signature_request_id = demande["id"]
    document = await ajouter_document(signature_request_id, pdf, nom_fichier)
    document_id = document["id"]
    await ajouter_signataire(
        signature_request_id, document_id,
        prenom=prenom, nom=nom, email=email, telephone=telephone,
    )
    await activer_demande(signature_request_id)
    return {"signature_request_id": signature_request_id, "document_id": document_id}


def verifier_signature_webhook(corps_brut: bytes, signature_recue: str | None) -> bool:
    """Vérifie l'en-tête `X-Yousign-Signature-256` (HMAC-SHA256 du corps brut de
    la requête avec le secret webhook Yousign) — indispensable avant de
    traiter un webhook, qui expose sinon la mise à jour de statut des mandats
    à n'importe quel appelant."""
    if not signature_recue or not settings.yousign_webhook_secret:
        return False
    attendu = hmac.new(settings.yousign_webhook_secret.encode(), corps_brut, hashlib.sha256).hexdigest()
    return hmac.compare_digest(attendu, signature_recue)


def parser_evenement_webhook(payload: dict) -> dict:
    """Extrait du payload webhook Yousign le nom de l'événement ainsi que
    l'id/statut de la demande de signature concernée."""
    demande = payload.get("data", {}).get("signature_request", {})
    return {
        "event_name": payload.get("event_name", ""),
        "signature_request_id": demande.get("id"),
        "status": demande.get("status"),
    }
