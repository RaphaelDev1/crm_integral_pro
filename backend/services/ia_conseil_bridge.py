# ==============================================================================
#  PONT CRM <-> IA CONSEIL — jusqu'ici `ClientConseil` (table `client`, IA
#  Conseil) et `Prospect`/`Client` (CRM) n'avaient aucun lien : le diagnostic
#  fusionné (voir PLAN "Fusionner la trame IA Conseil dans Nouveau diagnostic")
#  a besoin de rattacher la fiche CRM choisie à l'étape Identité à un
#  `ClientConseil` pour pouvoir lancer des sessions de trame. Même logique
#  idempotente que prospect_conversion.obtenir_ou_creer_client_miroir : ne crée
#  qu'une seule fois, réutilise ensuite via la colonne `ia_conseil_client_id`.
# ==============================================================================
from __future__ import annotations

from typing import Literal, Union

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.client import Client
from backend.models.ia_conseil import ClientConseil
from backend.models.prospect import Prospect

EntiteCRM = Union[Prospect, Client]


async def obtenir_ou_creer_client_conseil(
    db: AsyncSession, entite: EntiteCRM, entite_type: Literal["prospect", "client"], *, conseiller_id: int | None
) -> ClientConseil:
    """Ne commit PAS : à la charge de l'appelant (même convention que
    obtenir_ou_creer_client_miroir)."""
    if entite.ia_conseil_client_id is not None:
        client_conseil = await db.get(ClientConseil, entite.ia_conseil_client_id)
        if client_conseil is not None:
            return client_conseil

    client_conseil = ClientConseil(
        prenom=entite.prenom,
        nom=entite.nom,
        email=entite.email,
        telephone=entite.telephone,
        adresse={"adresse": entite.adresse, "code_postal": entite.code_postal, "ville": entite.ville},
        conseiller_id=conseiller_id,
    )
    db.add(client_conseil)
    await db.flush()  # obtenir client_conseil.id sans committer
    entite.ia_conseil_client_id = client_conseil.id
    return client_conseil
