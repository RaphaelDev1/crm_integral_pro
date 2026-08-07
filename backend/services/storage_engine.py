# ==============================================================================
#  STORAGE ENGINE — stockage sécurisé des documents client sur S3 (Scaleway
#  Object Storage recommandé, compatible S3 API).
#
#  Sécurité :
#    - Chiffrement SSE-S3 côté serveur (AES-256)
#    - URLs signées à durée limitée pour les téléchargements
#    - Clés d'objet non-devinables (uuid + hash)
#    - Bucket privé, pas d'accès public
# ==============================================================================
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path

import boto3
import filetype
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Fallback disque local, DEV UNIQUEMENT (voir _stockage_local_actif) — jamais
# utilisé en production, où S3 reste obligatoire.
LOCAL_STORAGE_DIR = Path(__file__).resolve().parent.parent / "_local_storage"


class StorageError(Exception):
    """Erreur d'accès au stockage S3."""


def _stockage_local_actif() -> bool:
    """True si on doit écrire sur disque local au lieu de S3.

    Sert uniquement à débloquer les tests en dev quand aucun bucket S3 n'est
    configuré. En production, on refuse plutôt que d'écrire silencieusement
    des documents KYC sensibles sur le disque du serveur.
    """
    if settings.s3_bucket:
        return False
    if settings.is_production:
        raise StorageError("S3 non configuré (voir .env : S3_ENDPOINT_URL, S3_BUCKET, S3_ACCESS_KEY_ID...).")
    logger.warning(
        "S3 non configuré — stockage local de secours utilisé (%s). "
        "À ne jamais utiliser en production, voir backend/.env.example.",
        LOCAL_STORAGE_DIR,
    )
    return True


def _chemin_local(cle: str) -> Path:
    return LOCAL_STORAGE_DIR / cle


def resoudre_fichier_local(cle: str) -> Path | None:
    """Résout `cle` vers un fichier existant sous LOCAL_STORAGE_DIR, ou None si
    absent / si `cle` tente d'en sortir (`../..`) — utilisé par
    backend/routers/stockage_local.py, seul point d'entrée HTTP qui sert ces
    fichiers (repli dev uniquement, voir _stockage_local_actif)."""
    chemin = _chemin_local(cle).resolve()
    if LOCAL_STORAGE_DIR.resolve() not in chemin.parents:
        return None
    return chemin if chemin.is_file() else None


def _client_s3():
    if not settings.s3_bucket:
        raise StorageError("S3 non configuré (voir .env : S3_ENDPOINT_URL, S3_BUCKET, S3_ACCESS_KEY_ID...).")
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=BotoConfig(signature_version="s3v4"),
    )


def _generer_cle(client_id: int, type_document: str, nom_fichier: str) -> str:
    now = datetime.now()
    unique = uuid.uuid4().hex[:8]
    h = hashlib.sha256(nom_fichier.encode()).hexdigest()[:8]
    ext = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else "bin"
    return f"clients/{client_id}/{now.year}/{now.month:02d}/{type_document}_{unique}_{h}.{ext}"


def upload_document(
    client_id: int,
    type_document: str,
    contenu: bytes,
    nom_fichier: str,
) -> str:
    """Upload un document sur S3 chiffré (ou en local en dev, voir _stockage_local_actif). Retourne la clé."""
    if not contenu:
        raise StorageError("Contenu vide.")

    cle = _generer_cle(client_id, type_document, nom_fichier)

    if _stockage_local_actif():
        chemin = _chemin_local(cle)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(contenu)
        return cle

    s3 = _client_s3()

    try:
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=cle,
            Body=contenu,
            ServerSideEncryption="AES256",
            ContentType=_deviner_mime(nom_fichier),
            Metadata={
                "client_id": str(client_id),
                "type_document": type_document,
                "upload_date": datetime.now().isoformat(),
            },
        )
    except ClientError as exc:
        raise StorageError(f"Upload S3 échoué : {exc}") from exc

    return cle


def _generer_cle_generique(prefixe: str, type_document: str, nom_fichier: str) -> str:
    now = datetime.now()
    unique = uuid.uuid4().hex[:8]
    h = hashlib.sha256(nom_fichier.encode()).hexdigest()[:8]
    ext = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else "bin"
    return f"{prefixe}/{now.year}/{now.month:02d}/{type_document}_{unique}_{h}.{ext}"


def upload_fichier(prefixe: str, type_document: str, contenu: bytes, nom_fichier: str) -> str:
    """Variante de upload_document() pour un fichier non rattaché à un
    client_id (ex : PDF de démarche rattaché à un dossier) — même politique
    de chiffrement/repli local, clé `{prefixe}/{year}/{month}/{type}_{uuid8}_{hash8}.{ext}`."""
    if not contenu:
        raise StorageError("Contenu vide.")

    cle = _generer_cle_generique(prefixe, type_document, nom_fichier)

    if _stockage_local_actif():
        chemin = _chemin_local(cle)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(contenu)
        return cle

    s3 = _client_s3()
    try:
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=cle,
            Body=contenu,
            ServerSideEncryption="AES256",
            ContentType=_deviner_mime(nom_fichier),
        )
    except ClientError as exc:
        raise StorageError(f"Upload S3 échoué : {exc}") from exc

    return cle


def telecharger_document(cle: str) -> bytes:
    if _stockage_local_actif():
        chemin = _chemin_local(cle)
        if not chemin.is_file():
            raise StorageError(f"Document local introuvable : {cle}")
        return chemin.read_bytes()

    s3 = _client_s3()
    try:
        response = s3.get_object(Bucket=settings.s3_bucket, Key=cle)
        return response["Body"].read()
    except ClientError as exc:
        raise StorageError(f"Download S3 échoué : {exc}") from exc


def url_signee(cle: str, duree_secondes: int = 3600) -> str:
    if _stockage_local_actif():
        # `local://{cle}` n'était pas une URL ouvrable par un navigateur (aucun
        # gestionnaire de ce pseudo-schéma) — le lien "Voir" ne faisait donc
        # jamais rien en dev. On sert le fichier via un vrai endpoint HTTP, voir
        # backend/routers/stockage_local.py.
        return f"{settings.backend_public_base_url}/stockage-local/{cle}"

    s3 = _client_s3()
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": cle},
            ExpiresIn=duree_secondes,
        )
    except ClientError as exc:
        raise StorageError(f"Génération URL signée échouée : {exc}") from exc


def supprimer_document(cle: str) -> None:
    if _stockage_local_actif():
        _chemin_local(cle).unlink(missing_ok=True)
        return

    s3 = _client_s3()
    try:
        s3.delete_object(Bucket=settings.s3_bucket, Key=cle)
    except ClientError as exc:
        raise StorageError(f"Suppression S3 échouée : {exc}") from exc


def _deviner_mime(nom_fichier: str) -> str:
    ext = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else ""
    return {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")


def deviner_mime_reel(contenu: bytes) -> str | None:
    """Détecte le vrai type MIME par magic bytes (contenu réel du fichier),
    contrairement à `_deviner_mime` qui ne fait confiance qu'à l'extension du
    nom de fichier. À utiliser partout où le fichier vient d'un tiers non fiable
    (upload public) et où renommer un exécutable en `.pdf` ne doit pas suffire
    à le faire accepter."""
    kind = filetype.guess(contenu)
    return kind.mime if kind else None
