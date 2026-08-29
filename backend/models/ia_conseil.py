# ==============================================================================
#  IA CONSEIL — fondations du moteur de trame adaptative et de recommandation
#  (PLAN_IMPLEMENTATION_4_PHASES.md §0.1, migration 0032). Sous-système neuf,
#  isolé du CRM existant : `ClientConseil`/`OffreConseil` sont des tables
#  distinctes de `Client`/`Offre` (models/client.py, models/offre.py), avec
#  PK UUID (au lieu de l'Integer autoincrement utilisé partout ailleurs) —
#  décision volontaire pour ce sous-système, voir §0.1. `conseiller_id`
#  référence `utilisateurs.id` (Integer) : mêmes conseillers que le CRM.
# ==============================================================================
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.user import User


class Categorie(Base):
    __tablename__ = "categorie"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    ordre: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Fournisseur(Base):
    __tablename__ = "fournisseur"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    categorie_slug: Mapped[str | None] = mapped_column(ForeignKey("categorie.slug"), nullable=True)
    note_fiabilite: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    affilie: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    taux_commission: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)


class OffreConseil(Base):
    __tablename__ = "offre"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fournisseur_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fournisseur.id"), nullable=True)
    categorie_slug: Mapped[str | None] = mapped_column(ForeignKey("categorie.slug"), nullable=True)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    prix_mensuel: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    prix_apres_promo: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    duree_promo_mois: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engagement_mois: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    frais_mise_en_service: Mapped[float] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    caracteristiques: Mapped[dict] = mapped_column(JSONB, nullable=False)
    conditions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    valide: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    date_maj: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now())


class TrameTemplate(Base):
    __tablename__ = "trame_template"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    categorie_slug: Mapped[str | None] = mapped_column(ForeignKey("categorie.slug"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class RegleRecommandation(Base):
    __tablename__ = "regle_recommandation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    categorie_slug: Mapped[str | None] = mapped_column(ForeignKey("categorie.slug"), nullable=True)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # 'filtre' | 'scoring' | 'alerte'
    priorite: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    condition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    action: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ClientConseil(Base):
    __tablename__ = "client"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conseiller_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateurs.id"), nullable=True)
    prenom: Mapped[str | None] = mapped_column(Text, nullable=True)
    nom: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    telephone: Mapped[str | None] = mapped_column(Text, nullable=True)
    adresse: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    foyer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    profil: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    conseiller: Mapped["User"] = relationship()


class SessionTrame(Base):
    __tablename__ = "session_trame"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("client.id"), nullable=True)
    conseiller_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateurs.id"), nullable=True)
    categorie_slug: Mapped[str | None] = mapped_column(ForeignKey("categorie.slug"), nullable=True)
    trame_template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trame_template.id"), nullable=True)
    reponses: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    etat: Mapped[str] = mapped_column(Text, default="en_cours", server_default="en_cours")  # en_cours | terminee | abandonnee
    canal: Mapped[str | None] = mapped_column(Text, nullable=True)  # visio | telephone | physique
    demarree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    terminee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # §3.3 — paragraphe de synthèse rédigé par LLM, mis en cache après la
    # première génération du PDF (idempotent, voir ia_conseil_pdf.py).
    synthese_llm_texte: Mapped[str | None] = mapped_column(Text, nullable=True)


class Recommandation(Base):
    __tablename__ = "recommandation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("session_trame.id"), nullable=True)
    offre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("offre.id"), nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    rang: Mapped[int | None] = mapped_column(Integer, nullable=True)
    justifications: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    alertes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    economie_mensuelle: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    economie_annuelle: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)


class Souscription(Base):
    __tablename__ = "souscription"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("client.id"), nullable=True)
    offre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("offre.id"), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("session_trame.id"), nullable=True)
    conseiller_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateurs.id"), nullable=True)
    date_souscription: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_activation: Mapped[date | None] = mapped_column(Date, nullable=True)
    prix_mensuel_negocie: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    commission_prevue: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    commission_encaissee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    statut: Mapped[str] = mapped_column(Text, default="en_attente", server_default="en_attente")  # en_attente | active | resiliee | annulee
    fin_engagement: Mapped[date | None] = mapped_column(Date, nullable=True)


class AlerteOverride(Base):
    """Levée manuelle d'une alerte critique bloquante (§2.1) — un conseiller ne
    peut finaliser une souscription tant qu'une alerte critique de la
    recommandation choisie n'a pas été explicitement levée ici, justification
    obligatoire, à des fins d'audit (voir backend/services/alertes_engine.py)."""

    __tablename__ = "alerte_override"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("session_trame.id"), nullable=True)
    offre_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("offre.id"), nullable=True)
    regle_nom: Mapped[str] = mapped_column(Text, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    conseiller_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateurs.id"), nullable=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now())


class EvenementPlanifie(Base):
    """Relance/action planifiée à date fixe pour un client IA Conseil (§2.3) —
    fin d'engagement à J-60, bilan annuel, NPS à J+30, ou alerte de veille prix
    (§2.2). `payload` porte le contexte métier (ex. souscription_id, offre
    alternative) consommé par backend/services/evenement_planifie_engine.py au
    moment de l'exécution. `execute` passe à True une fois traité — jamais
    ré-exécuté (le balayage quotidien filtre sur `NOT execute`)."""

    __tablename__ = "evenement_planifie"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("client.id"), nullable=True)
    conseiller_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateurs.id"), nullable=True)
    # type: 'fin_engagement_J-60' | 'bilan_annuel' | 'nps_j30' | 'veille_alerte'
    type: Mapped[str] = mapped_column(Text, nullable=False)
    date_prevue: Mapped[date] = mapped_column(Date, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    execute: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    execute_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionFacture(Base):
    """Facture téléversée par le conseiller pendant une session de trame
    (§3.1) — analysée par backend/services/facture_analyzer.py (déjà
    utilisé pour le CRM legacy, réutilisé tel quel ici) puis proposée au
    conseiller pour auto-remplissage des réponses (jamais appliqué sans
    validation, voir ia_conseil_facture.py::appliquer)."""

    __tablename__ = "session_facture"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("session_trame.id"), nullable=True)
    categorie_slug: Mapped[str | None] = mapped_column(ForeignKey("categorie.slug"), nullable=True)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    nom_fichier: Mapped[str | None] = mapped_column(Text, nullable=True)
    # statut : en_attente | analysee | echouee
    statut: Mapped[str] = mapped_column(Text, default="en_attente", server_default="en_attente")
    extraction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reponses_appliquees: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    erreur: Mapped[str | None] = mapped_column(Text, nullable=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now())
    analysee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RapportVeilleMarche(Base):
    """Rapport hebdomadaire de l'agent de veille marché autonome (§3.4) —
    scan du web (outil serveur Claude web_search) pour détecter des offres
    non encore présentes au catalogue `offre`. N'écrit jamais directement
    dans `offre` : chaque entrée de `offres_detectees` est revue par un
    admin (voir routers/ia_conseil_catalogue.py) avant intégration."""

    __tablename__ = "rapport_veille_marche"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    categorie_slug: Mapped[str | None] = mapped_column(ForeignKey("categorie.slug"), nullable=True)
    semaine_debut: Mapped[date] = mapped_column(Date, nullable=False)
    offres_detectees: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    # statut : en_attente | traite
    statut: Mapped[str] = mapped_column(Text, default="en_attente", server_default="en_attente")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now())
