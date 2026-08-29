"""Fondations du moteur "IA Conseil" (trame adaptative + recommandation) —
PLAN_IMPLEMENTATION_4_PHASES.md §0.1.

Neuf tables entièrement nouvelles, isolées du CRM existant (`clients`,
`offres`, `contrats`...) : catalogue (`categorie`, `fournisseur`, `offre`),
trame (`trame_template`, `regle_recommandation`) et sessions
(`client`, `session_trame`, `recommandation`, `souscription`). PK en UUID
(gen_random_uuid(), natif depuis Postgres 13, pas besoin de pgcrypto) —
décision volontaire, différente du reste du schéma (Integer autoincrement),
pour ce nouveau sous-système. `client` (singulier) est distincte de la table
`clients` (CRM historique) : duplication assumée, voir décision produit.

Les FK `conseiller_id` pointent vers `utilisateurs.id` (Integer) : mêmes
conseillers que le CRM existant, pas de table utilisateur dupliquée.

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    # ============ CATALOGUE ============
    op.create_table(
        "categorie",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("nom", sa.Text(), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=True),
        sa.Column("actif", sa.Boolean(), server_default=sa.true(), nullable=False),
    )

    op.create_table(
        "fournisseur",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("nom", sa.Text(), nullable=False),
        sa.Column("categorie_slug", sa.Text(), sa.ForeignKey("categorie.slug"), nullable=True),
        sa.Column("note_fiabilite", sa.Numeric(3, 2), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("site_url", sa.Text(), nullable=True),
        sa.Column("affilie", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("taux_commission", sa.Numeric(5, 2), nullable=True),
    )

    op.create_table(
        "offre",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("fournisseur_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fournisseur.id"), nullable=True),
        sa.Column("categorie_slug", sa.Text(), sa.ForeignKey("categorie.slug"), nullable=True),
        sa.Column("nom", sa.Text(), nullable=False),
        sa.Column("prix_mensuel", sa.Numeric(10, 2), nullable=True),
        sa.Column("prix_apres_promo", sa.Numeric(10, 2), nullable=True),
        sa.Column("duree_promo_mois", sa.Integer(), nullable=True),
        sa.Column("engagement_mois", sa.Integer(), server_default="0", nullable=False),
        sa.Column("frais_mise_en_service", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("caracteristiques", postgresql.JSONB(), nullable=False),
        sa.Column("conditions", postgresql.JSONB(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("valide", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("date_maj", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("fournisseur_id", "nom", name="uq_offre_fournisseur_nom"),
    )
    op.create_index(
        "idx_offre_categorie", "offre", ["categorie_slug"], postgresql_where=sa.text("valide = true")
    )
    op.create_index("idx_offre_caract", "offre", ["caracteristiques"], postgresql_using="gin")

    # ============ TRAME ============
    op.create_table(
        "trame_template",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("categorie_slug", sa.Text(), sa.ForeignKey("categorie.slug"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("actif", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.UniqueConstraint("categorie_slug", "version", name="uq_trame_template_categorie_version"),
    )

    op.create_table(
        "regle_recommandation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("categorie_slug", sa.Text(), sa.ForeignKey("categorie.slug"), nullable=True),
        sa.Column("nom", sa.Text(), nullable=False),
        sa.Column(
            "type",
            sa.Text(),
            sa.CheckConstraint("type IN ('filtre','scoring','alerte')", name="ck_regle_recommandation_type"),
            nullable=False,
        ),
        sa.Column("priorite", sa.Integer(), server_default="0", nullable=False),
        sa.Column("condition", postgresql.JSONB(), nullable=False),
        sa.Column("action", postgresql.JSONB(), nullable=False),
        sa.Column("actif", sa.Boolean(), server_default=sa.true(), nullable=False),
    )

    # ============ CLIENTS & SESSIONS ============
    op.create_table(
        "client",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("conseiller_id", sa.Integer(), sa.ForeignKey("utilisateurs.id"), nullable=True),
        sa.Column("prenom", sa.Text(), nullable=True),
        sa.Column("nom", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("telephone", sa.Text(), nullable=True),
        sa.Column("adresse", postgresql.JSONB(), nullable=True),
        sa.Column("foyer", postgresql.JSONB(), nullable=True),
        sa.Column("profil", postgresql.JSONB(), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "session_trame",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client.id"), nullable=True),
        sa.Column("conseiller_id", sa.Integer(), sa.ForeignKey("utilisateurs.id"), nullable=True),
        sa.Column("categorie_slug", sa.Text(), sa.ForeignKey("categorie.slug"), nullable=True),
        sa.Column("trame_template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trame_template.id"), nullable=True),
        sa.Column("reponses", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        # etat: 'en_cours' | 'terminee' | 'abandonnee' — canal: 'visio' | 'telephone' | 'physique'
        sa.Column("etat", sa.Text(), server_default="en_cours", nullable=False),
        sa.Column("canal", sa.Text(), nullable=True),
        sa.Column("demarree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("terminee_le", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "recommandation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("session_trame.id"), nullable=True),
        sa.Column("offre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offre.id"), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("rang", sa.Integer(), nullable=True),
        sa.Column("justifications", postgresql.JSONB(), nullable=True),
        sa.Column("alertes", postgresql.JSONB(), nullable=True),
        sa.Column("economie_mensuelle", sa.Numeric(10, 2), nullable=True),
        sa.Column("economie_annuelle", sa.Numeric(10, 2), nullable=True),
    )

    op.create_table(
        "souscription",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client.id"), nullable=True),
        sa.Column("offre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offre.id"), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("session_trame.id"), nullable=True),
        sa.Column("conseiller_id", sa.Integer(), sa.ForeignKey("utilisateurs.id"), nullable=True),
        sa.Column("date_souscription", sa.Date(), nullable=True),
        sa.Column("date_activation", sa.Date(), nullable=True),
        sa.Column("prix_mensuel_negocie", sa.Numeric(10, 2), nullable=True),
        sa.Column("commission_prevue", sa.Numeric(10, 2), nullable=True),
        sa.Column("commission_encaissee", sa.Numeric(10, 2), nullable=True),
        # statut: 'en_attente' | 'active' | 'resiliee' | 'annulee'
        sa.Column("statut", sa.Text(), server_default="en_attente", nullable=False),
        sa.Column("fin_engagement", sa.Date(), nullable=True),
    )
    op.create_index("idx_souscription_conseiller", "souscription", ["conseiller_id", "date_souscription"])
    op.create_index(
        "idx_souscription_fin_engagement",
        "souscription",
        ["fin_engagement"],
        postgresql_where=sa.text("statut = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("idx_souscription_fin_engagement", table_name="souscription")
    op.drop_index("idx_souscription_conseiller", table_name="souscription")
    op.drop_table("souscription")
    op.drop_table("recommandation")
    op.drop_table("session_trame")
    op.drop_table("client")
    op.drop_table("regle_recommandation")
    op.drop_table("trame_template")
    op.drop_index("idx_offre_caract", table_name="offre")
    op.drop_index("idx_offre_categorie", table_name="offre")
    op.drop_table("offre")
    op.drop_table("fournisseur")
    op.drop_table("categorie")
