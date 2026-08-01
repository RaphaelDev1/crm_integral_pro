"""Ajoute les tables du pipeline de découverte du catalogue — `catalogue_sources`
(pages à ingérer) et `offres_staging` (offres détectées par le LLM, en attente
de validation admin avant copie dans `offres`). Voir
backend/services/catalogue_engine.py et backend/models/catalogue_source.py /
backend/models/offre_staging.py. Miroir de src/db.py.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalogue_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("univers", sa.String(), nullable=True),
        sa.Column("categorie", sa.String(), nullable=True),
        sa.Column("fournisseur", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("type_source", sa.String(), server_default="page_officielle", nullable=False),
        sa.Column("methode", sa.String(), server_default="requests", nullable=False),
        sa.Column("actif", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("robots_ok", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("frequence_h", sa.Integer(), server_default="24", nullable=False),
        sa.Column("date_derniere_ingestion", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
    )

    op.create_table(
        "offres_staging",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("catalogue_sources.id"), nullable=True),
        sa.Column("univers", sa.String(), nullable=True),
        sa.Column("categorie", sa.String(), nullable=True),
        sa.Column("fournisseur", sa.String(), nullable=True),
        sa.Column("nom_offre", sa.String(), nullable=True),
        sa.Column("prix_mensuel", sa.Float(), nullable=True),
        sa.Column("frais_activation", sa.Float(), server_default="0", nullable=True),
        sa.Column("engagement_mois", sa.Integer(), server_default="0", nullable=True),
        sa.Column("data_go", sa.Float(), server_default="0", nullable=True),
        sa.Column("caracteristiques", sa.String(), nullable=True),
        sa.Column("commission_affiliation", sa.Float(), server_default="0", nullable=True),
        sa.Column("url_souscription", sa.String(), nullable=True),
        sa.Column("code_affiliation", sa.String(), nullable=True),
        sa.Column("hash_contenu", sa.String(), nullable=True),
        sa.Column("statut", sa.String(), server_default="en_attente", nullable=False),
        sa.Column("confiance_llm", sa.Float(), nullable=True),
        sa.Column("champs_incertains", sa.JSON(), nullable=True),
        sa.Column("payload_brut", sa.JSON(), nullable=True),
        sa.Column("offre_existante_id", sa.Integer(), sa.ForeignKey("offres.id"), nullable=True),
        sa.Column("date_detection", sa.String(), nullable=True),
        sa.Column("date_traitement", sa.String(), nullable=True),
    )
    op.create_index("ix_offres_staging_source_id", "offres_staging", ["source_id"])
    op.create_index("ix_offres_staging_statut", "offres_staging", ["statut"])
    op.create_index("ix_offres_staging_hash_contenu", "offres_staging", ["hash_contenu"])


def downgrade() -> None:
    op.drop_index("ix_offres_staging_hash_contenu", table_name="offres_staging")
    op.drop_index("ix_offres_staging_statut", table_name="offres_staging")
    op.drop_index("ix_offres_staging_source_id", table_name="offres_staging")
    op.drop_table("offres_staging")
    op.drop_table("catalogue_sources")
