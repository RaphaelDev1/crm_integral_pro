# ==============================================================================
#  TOKEN ENGINE — génération et validation des tokens publics (lien unique
#  donné au client, sans login).
#
#  Sécurité :
#    - secrets.token_urlsafe(32) — ~256 bits d'entropie, impossible à deviner
#    - Expiration configurable (défaut 30 jours)
#    - Optionnel : lock sur IP de première utilisation (blocage si IP change)
#    - Rate limiting côté router (à ajouter avec slowapi)
#    - Journalisation à chaque accès (audit trail)
# ==============================================================================
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.token_public import TokenPublic


DUREE_VALIDITE_PAR_DEFAUT = timedelta(days=30)
# Même durée que src/prospects_engine.py::TOKEN_DOCUMENTS_DUREE_JOURS.
DUREE_VALIDITE_DOCUMENTS_PROSPECT = timedelta(days=14)
FORMAT_DATE = "%d/%m/%Y %H:%M"


def _maintenant_str() -> str:
    return datetime.now().strftime(FORMAT_DATE)


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, FORMAT_DATE)
    except ValueError:
        return None


async def generer_token(
    db: AsyncSession,
    *,
    client_id: int | None = None,
    prospect_id: int | None = None,
    dossier_id: int | None = None,
    cree_par: str | None = None,
    duree: timedelta = DUREE_VALIDITE_PAR_DEFAUT,
    peut_uploader_docs: bool = True,
    peut_signer_mandat: bool = True,
    peut_voir_suivi: bool = True,
    peut_transmettre_speedtest: bool = True,
    peut_renseigner_demarches: bool = True,
) -> TokenPublic:
    """Génère un nouveau token public pour un client OU un prospect (exactement
    l'un des deux — cf. contrainte XOR, migration 0019)."""
    if (client_id is None) == (prospect_id is None):
        raise ValueError("Fournir exactement un de client_id ou prospect_id.")

    now = datetime.now()
    token = TokenPublic(
        token=secrets.token_urlsafe(32),
        client_id=client_id,
        prospect_id=prospect_id,
        dossier_id=dossier_id,
        peut_uploader_docs=peut_uploader_docs,
        peut_signer_mandat=peut_signer_mandat,
        peut_voir_suivi=peut_voir_suivi,
        peut_transmettre_speedtest=peut_transmettre_speedtest,
        peut_renseigner_demarches=peut_renseigner_demarches,
        date_creation=now.strftime(FORMAT_DATE),
        date_expiration=(now + duree).strftime(FORMAT_DATE),
        cree_par=cree_par,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def generer_token_prospect_documents(
    db: AsyncSession,
    prospect_id: int,
    *,
    cree_par: str | None = None,
    duree: timedelta = DUREE_VALIDITE_DOCUMENTS_PROSPECT,
) -> TokenPublic:
    """Génère un token pour qu'un prospect (pas encore client) transmette lui-même
    sa facture/son test de débit — équivalent de
    src/prospects_engine.py::creer_token_documents. Aucun dossier n'existe encore :
    upload de documents ET test de débit en direct (widget LibreSpeed self-hosted,
    voir /portail/{token}/speedtest) sont autorisés ; les autres permissions
    restent désactivées (pas de suivi/mandat/démarches sans dossier)."""
    return await generer_token(
        db,
        prospect_id=prospect_id,
        dossier_id=None,
        cree_par=cree_par,
        duree=duree,
        peut_uploader_docs=True,
        peut_signer_mandat=False,
        peut_voir_suivi=False,
        peut_transmettre_speedtest=True,
        peut_renseigner_demarches=False,
    )


async def valider_token(
    db: AsyncSession,
    token_str: str,
    ip_appelant: str | None = None,
    strict_ip: bool = False,
) -> TokenPublic | None:
    """Retourne le TokenPublic si valide, None sinon."""
    result = await db.execute(select(TokenPublic).where(TokenPublic.token == token_str))
    token: TokenPublic | None = result.scalar_one_or_none()

    if token is None or token.revoque:
        return None

    date_exp = _parse_date(token.date_expiration)
    if date_exp is not None and datetime.now() > date_exp:
        return None

    if strict_ip and token.ip_premiere_utilisation and ip_appelant:
        if token.ip_premiere_utilisation != ip_appelant:
            return None

    now_str = _maintenant_str()
    if token.date_premiere_utilisation is None:
        token.date_premiere_utilisation = now_str
        if ip_appelant:
            token.ip_premiere_utilisation = ip_appelant
    token.date_derniere_utilisation = now_str
    token.nb_utilisations = (token.nb_utilisations or 0) + 1
    await db.commit()
    return token


async def revoquer_token(db: AsyncSession, token_id: int, motif: str) -> bool:
    token = await db.get(TokenPublic, token_id)
    if token is None:
        return False
    token.revoque = True
    token.motif_revocation = motif
    await db.commit()
    return True


def construire_url_client(token: str, base_url: str = "https://client.iaconseil.fr") -> str:
    return f"{base_url}/dossier/{token}"
