# ==============================================================================
#  PROSPECT CONVERSION — bascule d'un Prospect en Client réel, porté de
#  src/app.py::_finaliser_prospect_en_client (côté SQLite/Streamlit) vers un
#  service async unique côté backend/Postgres.
#
#  Le client rattaché à un prospect peut déjà exister (« client miroir »,
#  cf. src/api_client.py::_backend_client_id_pour) si un dossier ou un token
#  de documents a été créé avant la conversion — dans ce cas on le réutilise
#  au lieu d'en créer un second.
# ==============================================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.client import Client
from backend.models.dossier import Dossier
from backend.models.prospect import Prospect
from backend.models.token_public import TokenPublic
from backend.services import audit_engine

FORMAT_DATE = "%d/%m/%Y %H:%M"

# Champs communs entre Prospect et Client (intersection de
# backend/schemas/prospect.py::ProspectBase et backend/schemas/client.py::ClientBase),
# transférés du prospect vers son client à la conversion — même liste que
# src/api_client.py:382-388 (_CHAMPS_CLIENT_BACKEND).
CHAMPS_PROSPECT_VERS_CLIENT = (
    "ref", "prenom", "nom", "telephone", "email", "code_postal", "ville", "adresse",
    "type_client", "operateur_actuel", "techno", "data_go", "offre_actuelle",
    "cout_mensuel_actuel", "satisfaction_reseau", "veut_rester", "speed_down", "speed_up",
    "fournisseur_energie", "cout_elec", "cout_gaz", "economie_estimee_an", "notes",
    "date_relance",
)


class ProspectDejaConverti(Exception):
    """Le prospect a déjà été converti en client."""


async def convertir_prospect(db: AsyncSession, prospect: Prospect, *, par: str) -> Client:
    """Convertit un prospect en client, en une seule transaction :
      1. Crée (ou réutilise le miroir existant) le Client.
      2. Bascule est_prospect=False sur tous les dossiers déjà rattachés à ce client.
      3. Réassigne au client les tokens publics émis pour ce prospect avant conversion.
      4. Marque le prospect comme converti et journalise l'action.

    Un seul `db.commit()` en fin de fonction : si une étape lève une exception,
    aucune écriture n'est persistée (la session, jamais committée, est fermée
    sans effet par le `async with` de backend/core/database.py::get_db)."""
    if prospect.converti_at is not None:
        raise ProspectDejaConverti(f"Le prospect {prospect.id} a déjà été converti le {prospect.converti_at}.")

    client: Client | None = None
    if prospect.client_id is not None:
        client = await db.get(Client, prospect.client_id)

    now_str = datetime.now().strftime(FORMAT_DATE)

    if client is None:
        client = Client(
            **{champ: getattr(prospect, champ) for champ in CHAMPS_PROSPECT_VERS_CLIENT},
            date_creation=now_str,
            cree_par=par,
        )
        db.add(client)
        await db.flush()  # obtenir client.id sans committer
    else:
        for champ in CHAMPS_PROSPECT_VERS_CLIENT:
            setattr(client, champ, getattr(prospect, champ))

    await db.execute(
        update(Dossier).where(Dossier.client_id == client.id).values(est_prospect=False)
    )
    await db.execute(
        update(TokenPublic)
        .where(TokenPublic.prospect_id == prospect.id)
        .values(prospect_id=None, client_id=client.id)
    )

    prospect.client_id = client.id
    prospect.converti_at = now_str

    await audit_engine.enregistrer_action(
        db, entite_type="prospect", entite_id=prospect.id,
        action="Converti en client", details=f"client_id={client.id}", auteur=par,
    )

    await db.commit()
    await db.refresh(client)
    await db.refresh(prospect)
    return client
