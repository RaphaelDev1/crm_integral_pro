"""UTM dashboard + attribution multi-touch + séquence de nurturing.

Ajoute :
  - `touchpoints` : historique des points de contact UTM d'un prospect avant
    conversion (première visite, visites suivantes) — alimenté côté client par
    frontend-portail/lib/attribution.ts, persisté par
    backend/routers/leads_public.py::capturer_lead. Sert l'attribution
    multi-touch (P4.3).
  - `campagnes_couts` : dépense publicitaire saisie manuellement par
    campagne/mois — permet de calculer le CAC dans le dashboard UTM (P4.1),
    faute d'intégration API directe avec Meta/TikTok/Google Ads.
  - `prospects.email_jN_envoye` (N=2..5) : idempotence de la séquence de
    nurturing multi-touches (P4.2), sur le même principe que
    `email_j1_envoye` (migration 0028).
  - `prospects.email_desabonne` : désabonnement des emails marketing
    (nurturing), distinct de `consentement_demarchage` qui couvre le
    démarchage téléphonique.

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for jour in (2, 3, 4, 5):
        op.add_column(
            "prospects",
            sa.Column(f"email_j{jour}_envoye", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    op.add_column(
        "prospects",
        sa.Column("email_desabonne", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "touchpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("prospect_id", sa.Integer(), sa.ForeignKey("prospects.id"), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("utm_source", sa.String(), nullable=True),
        sa.Column("utm_medium", sa.String(), nullable=True),
        sa.Column("utm_campaign", sa.String(), nullable=True),
        sa.Column("utm_content", sa.String(), nullable=True),
        sa.Column("utm_term", sa.String(), nullable=True),
        sa.Column("referrer", sa.String(), nullable=True),
        sa.Column("landing_page", sa.String(), nullable=True),
        sa.Column("horodatage_client", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
    )
    op.create_index("idx_touchpoints_prospect_id", "touchpoints", ["prospect_id"])

    op.create_table(
        "campagnes_couts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("utm_source", sa.String(), nullable=False),
        sa.Column("utm_campaign", sa.String(), nullable=True),
        sa.Column("mois", sa.String(), nullable=False),
        sa.Column("cout", sa.Float(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
    )
    op.create_index(
        "idx_campagnes_couts_unique",
        "campagnes_couts",
        ["utm_source", "utm_campaign", "mois"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_campagnes_couts_unique", table_name="campagnes_couts")
    op.drop_table("campagnes_couts")

    op.drop_index("idx_touchpoints_prospect_id", table_name="touchpoints")
    op.drop_table("touchpoints")

    op.drop_column("prospects", "email_desabonne")
    for jour in (5, 4, 3, 2):
        op.drop_column("prospects", f"email_j{jour}_envoye")
