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
from backend.services import audit_engine, reference_engine

FORMAT_DATE = "%d/%m/%Y %H:%M"

# Champs communs entre Prospect et Client (intersection de
# backend/schemas/prospect.py::ProspectBase et backend/schemas/client.py::ClientBase),
# transférés du prospect vers son client à la conversion — même liste que
# src/api_client.py:382-388 (_CHAMPS_CLIENT_BACKEND). `ref` est exclu : il ne
# se copie pas tel quel, voir reference_engine.ref_client_depuis_ref_prospect.
CHAMPS_PROSPECT_VERS_CLIENT = (
    "prenom", "nom", "telephone", "email", "code_postal", "ville", "adresse",
    "type_client", "raison_sociale", "effectif", "operateur_actuel", "techno", "data_go", "offre_actuelle",
    "cout_mensuel_actuel", "satisfaction_reseau", "veut_rester", "speed_down", "speed_up",
    "fournisseur_energie", "cout_elec", "cout_gaz", "economie_estimee_an", "notes",
    "date_relance",
)


class ProspectDejaConverti(Exception):
    """Le prospect a déjà été converti en client."""


async def obtenir_ou_creer_client_miroir(db: AsyncSession, prospect: Prospect, *, par: str) -> Client:
    """Crée (ou réutilise et rafraîchit) le Client "miroir" rattaché à ce
    prospect, sans finaliser la conversion (pas de `converti_at`, pas de
    bascule `est_prospect`) — utilisé quand un dossier a besoin d'un vrai
    `client_id` avant que la conversion officielle n'ait eu lieu (ex. diagnostic
    conseiller, désormais piloté par la signature du mandat — voir
    mandat_engine.traiter_mandat_signe). Ne commit PAS : à la charge de l'appelant."""
    client: Client | None = None
    if prospect.client_id is not None:
        client = await db.get(Client, prospect.client_id)

    if client is None:
        ref_client = reference_engine.ref_client_depuis_ref_prospect(prospect.ref)
        if ref_client is None:
            ref_client = await reference_engine.generer_ref_client(db)
        client = Client(
            **{champ: getattr(prospect, champ) for champ in CHAMPS_PROSPECT_VERS_CLIENT},
            ref=ref_client,
            date_creation=datetime.now().strftime(FORMAT_DATE),
            cree_par=par,
        )
        db.add(client)
        await db.flush()  # obtenir client.id sans committer
        prospect.client_id = client.id
    else:
        for champ in CHAMPS_PROSPECT_VERS_CLIENT:
            setattr(client, champ, getattr(prospect, champ))

    return client


async def convertir_prospect(
    db: AsyncSession, prospect: Prospect, *, par: str, conseiller_id: int | None = None
) -> Client:
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

    client = await obtenir_ou_creer_client_miroir(db, prospect, par=par)
    if conseiller_id is not None:
        client.conseiller_id = conseiller_id

    now_str = datetime.now().strftime(FORMAT_DATE)

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
