# ==============================================================================
#  PURGE DONNÉES DE TEST — supprime en une fois TOUS les prospects et clients,
#  ainsi que tout ce qui en dépend (dossiers, mandats, documents, factures,
#  commissions...), y compris les fichiers S3/local associés (photos de
#  documents, PDF de mandat...). Outil de dev/test pour désencombrer la base
#  entre deux campagnes de tests — jamais utilisable en production (voir
#  purger_prospects_et_clients).
# ==============================================================================
from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.abonnement import Abonnement
from backend.models.alerte_offre import AlerteOffre
from backend.models.client import Client
from backend.models.commission import Commission
from backend.models.comparaison_offre import ComparaisonOffre
from backend.models.contrat import Contrat
from backend.models.demarche import Demarche
from backend.models.document import Document
from backend.models.document_prospect import DocumentProspect
from backend.models.dossier import Dossier
from backend.models.facture_analyse import FactureAnalyse
from backend.models.historique_action import HistoriqueAction
from backend.models.mandat import Mandat
from backend.models.mandat_honoraires import MandatHonoraires
from backend.models.notification import Notification
from backend.models.prospect import Prospect
from backend.models.token_public import TokenPublic
from backend.services.storage_engine import StorageError, supprimer_document

logger = logging.getLogger(__name__)

# Tables qui ne dépendent que de clients/dossiers/prospects (aucune donnée
# indépendante) — vidées intégralement avant les dossiers, dans un ordre qui
# respecte leurs FK mutuelles (ex. Demarche.mandat_id -> Mandat, donc Demarche
# avant Mandat).
_TABLES_DEPENDANTES = (
    Notification, Commission, MandatHonoraires, Demarche, FactureAnalyse,
    TokenPublic, ComparaisonOffre, AlerteOffre, Abonnement, Document, Mandat,
)

# Colonnes contenant des clés de stockage (S3 ou disque local, voir
# backend/services/storage_engine.py) à supprimer avant de perdre toute trace
# de leur existence en base.
_COLONNES_STOCKAGE = (
    Document.url_stockage,
    DocumentProspect.cle_stockage,
    Mandat.pdf_url,
    Mandat.pdf_signe_url,
    Demarche.document_url,
    Demarche.preuve_url,
)


class PurgeInterdite(Exception):
    """Levée si une purge de données de test est tentée en production."""


async def _cles_stockage(db: AsyncSession) -> list[str]:
    cles: list[str] = []
    for colonne in _COLONNES_STOCKAGE:
        result = await db.execute(select(colonne).where(colonne.is_not(None)))
        cles.extend(cle for cle in result.scalars().all() if cle)
    return cles


async def purger_prospects_et_clients(db: AsyncSession) -> dict[str, int]:
    """Supprime TOUS les prospects et clients (et toutes leurs dépendances),
    fichiers de stockage inclus. Irréversible — réservé au rôle Admin (voir
    backend/routers/admin.py) et bloqué en production."""
    if settings.is_production:
        raise PurgeInterdite("Purge des données de test interdite en production.")

    nb_clients = len((await db.execute(select(Client.id))).scalars().all())
    nb_prospects = len((await db.execute(select(Prospect.id))).scalars().all())
    cles_stockage = await _cles_stockage(db)

    for modele in _TABLES_DEPENDANTES:
        await db.execute(delete(modele))
    # Dossier référence Contrat (contrat_id) : doit disparaître avant lui.
    await db.execute(delete(Dossier))
    await db.execute(delete(Contrat))
    # DocumentProspect référence Prospect : doit disparaître avant lui.
    await db.execute(delete(DocumentProspect))
    await db.execute(
        delete(HistoriqueAction).where(HistoriqueAction.entite_type.in_(("client", "prospect")))
    )
    # Prospect référence Client (client_id, fiche miroir) : doit disparaître avant lui.
    await db.execute(delete(Prospect))
    await db.execute(delete(Client))
    await db.commit()

    nb_fichiers_supprimes = 0
    for cle in cles_stockage:
        try:
            supprimer_document(cle)
            nb_fichiers_supprimes += 1
        except StorageError:
            logger.warning("Suppression du fichier de stockage échouée pour la clé %s", cle)

    return {
        "clients_supprimes": nb_clients,
        "prospects_supprimes": nb_prospects,
        "fichiers_supprimes": nb_fichiers_supprimes,
    }
