# ==============================================================================
#  CLIENT SUPPRESSION — supprime un Client, corrige le 500 de DELETE /clients/{id}
#  (`db.delete(client)` seul échouait dès qu'une ligne dépendante existait,
#  violation de contrainte FK non gérée — même bug que celui déjà corrigé pour
#  les prospects, voir backend/services/prospect_conversion.py::supprimer_prospect).
#
#  Contrairement à un prospect (lead pas encore engagé), un client peut porter
#  des données qu'on ne veut jamais perdre silencieusement : dossier en cours,
#  mandat signé, contrats, factures analysées, abonnement Gestionnaire (Stripe),
#  documents KYC. La suppression est donc bloquée tant que l'une de ces
#  données existe — au conseiller de les traiter/archiver d'abord. Seules les
#  données annexes (tokens publics, alertes d'offres, comparaisons, prospects
#  historiques rattachés) sont nettoyées automatiquement.
#
#  Un Admin peut cependant forcer une suppression complète en cascade
#  (`forcer=True`) — tout ce qui est lié au client est alors supprimé
#  définitivement avec lui, sans exception.
# ==============================================================================
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.abonnement import Abonnement
from backend.models.alerte_offre import AlerteOffre
from backend.models.client import Client
from backend.models.commission import Commission
from backend.models.comparaison_offre import ComparaisonOffre
from backend.models.contrat import Contrat
from backend.models.demarche import Demarche
from backend.models.document import Document
from backend.models.dossier import Dossier
from backend.models.facture_analyse import FactureAnalyse
from backend.models.mandat import Mandat
from backend.models.mandat_honoraires import MandatHonoraires
from backend.models.notification import Notification
from backend.models.prospect import Prospect
from backend.models.token_public import TokenPublic

# Libellé affiché + modèle à vérifier, dans l'ordre où on veut les citer au
# conseiller si plusieurs blocages existent en même temps.
_DONNEES_BLOQUANTES: tuple[tuple[str, type], ...] = (
    ("un dossier", Dossier),
    ("un mandat", Mandat),
    ("un contrat", Contrat),
    ("une facture analysée", FactureAnalyse),
    ("un abonnement Gestionnaire", Abonnement),
    ("un document", Document),
)


class ClientSuppressionBloquee(Exception):
    """Le client a des données liées jugées trop importantes pour être
    supprimées avec lui — la suppression doit être refusée (409)."""


async def supprimer_client(db: AsyncSession, client: Client, *, forcer: bool = False) -> None:
    if not forcer:
        labels_bloquants = []
        for label, modele in _DONNEES_BLOQUANTES:
            existe = (
                await db.execute(select(modele.id).where(modele.client_id == client.id).limit(1))
            ).scalar_one_or_none() is not None
            if existe:
                labels_bloquants.append(label)

        if labels_bloquants:
            raise ClientSuppressionBloquee(
                f"Impossible de supprimer ce client : il a encore {', '.join(labels_bloquants)} "
                "lié(e). Traitez/supprimez-les d'abord."
            )

    await db.execute(delete(TokenPublic).where(TokenPublic.client_id == client.id))
    await db.execute(delete(AlerteOffre).where(AlerteOffre.client_id == client.id))
    await db.execute(delete(ComparaisonOffre).where(ComparaisonOffre.client_id == client.id))
    # Prospect(s) historiques convertis vers ce client (voir
    # prospect_conversion.obtenir_ou_creer_client_miroir) : détachés, pas
    # supprimés, pour garder la trace du prospect d'origine.
    await db.execute(update(Prospect).where(Prospect.client_id == client.id).values(client_id=None))

    if forcer:
        # Cascade complète pour l'Admin — enfants des Dossier d'abord (FK non
        # nullable vers dossiers.id), puis les données rattachées directement
        # au client, puis les Dossier eux-mêmes, puis Mandat/Contrat (dans cet
        # ordre car Demarche.mandat_id référence Mandat).
        sous_requete_dossiers = select(Dossier.id).where(Dossier.client_id == client.id)
        await db.execute(delete(Demarche).where(Demarche.dossier_id.in_(sous_requete_dossiers)))
        await db.execute(delete(Commission).where(Commission.dossier_id.in_(sous_requete_dossiers)))
        await db.execute(delete(MandatHonoraires).where(MandatHonoraires.dossier_id.in_(sous_requete_dossiers)))
        await db.execute(delete(Notification).where(Notification.dossier_id.in_(sous_requete_dossiers)))
        await db.execute(delete(FactureAnalyse).where(FactureAnalyse.client_id == client.id))
        await db.execute(delete(Document).where(Document.client_id == client.id))
        await db.execute(delete(Abonnement).where(Abonnement.client_id == client.id))
        await db.execute(delete(Dossier).where(Dossier.client_id == client.id))
        await db.execute(delete(Mandat).where(Mandat.client_id == client.id))
        await db.execute(delete(Contrat).where(Contrat.client_id == client.id))

    await db.delete(client)
    await db.commit()
