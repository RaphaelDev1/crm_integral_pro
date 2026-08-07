# ==============================================================================
#  REFERENCE ENGINE — numérotation interne des prospects/clients.
#
#  Une seule suite numérique partagée entre les deux tables : un prospect
#  "PRS-000123" devient, une fois converti (ou dès qu'un client miroir est
#  créé), "CLT-000123" — même numéro, préfixe différent. Pas de table de
#  séquence dédiée : le prochain numéro est déduit du suffixe numérique le
#  plus élevé déjà attribué sur `prospects.ref` et `clients.ref`, ce qui
#  suffit pour le volume d'une CRM mono-cabinet.
# ==============================================================================
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.client import Client
from backend.models.prospect import Prospect

PREFIXE_PROSPECT = "PRS"
PREFIXE_CLIENT = "CLT"

_RE_SUFFIXE = re.compile(r"(\d+)$")


def _numero_depuis_ref(ref: str | None) -> int | None:
    if not ref:
        return None
    match = _RE_SUFFIXE.search(ref.strip())
    return int(match.group(1)) if match else None


async def prochain_numero(db: AsyncSession) -> int:
    """Plus grand numéro déjà attribué (prospects + clients confondus) + 1."""
    refs_prospects = (await db.execute(select(Prospect.ref))).scalars().all()
    refs_clients = (await db.execute(select(Client.ref))).scalars().all()
    numeros = [
        n for n in (_numero_depuis_ref(ref) for ref in (*refs_prospects, *refs_clients)) if n is not None
    ]
    return (max(numeros) + 1) if numeros else 1


async def generer_ref_prospect(db: AsyncSession) -> str:
    numero = await prochain_numero(db)
    return f"{PREFIXE_PROSPECT}-{numero:06d}"


async def generer_ref_client(db: AsyncSession) -> str:
    numero = await prochain_numero(db)
    return f"{PREFIXE_CLIENT}-{numero:06d}"


def ref_client_depuis_ref_prospect(ref_prospect: str | None) -> str | None:
    """Dérive la référence client d'un prospect converti en réutilisant le même
    numéro (`PRS-000123` -> `CLT-000123`). Renvoie None si `ref_prospect` ne
    porte pas de suffixe numérique exploitable (fiche legacy) — l'appelant doit
    alors se rabattre sur `generer_ref_client`."""
    numero = _numero_depuis_ref(ref_prospect)
    return f"{PREFIXE_CLIENT}-{numero:06d}" if numero is not None else None
