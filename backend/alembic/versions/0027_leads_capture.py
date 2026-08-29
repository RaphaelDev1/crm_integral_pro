"""Landing capture prospects — UTM, consentements RGPD, âge, tracking IP/UA.

Ajoute au modèle `prospects` les colonnes nécessaires pour tracer un lead
capturé depuis la landing publique /economiser (campagnes TikTok / Instagram /
Facebook), et une colonne `age` sur `clients` pour calibrer le moteur
d'estimation `estimation_publique` par tranche d'âge (« clients de votre âge
paient X€/mois »).

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- prospects : tracking landing publique -------------------------------
    op.add_column("prospects", sa.Column("utm_source", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("utm_medium", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("utm_campaign", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("utm_content", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("utm_term", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("age", sa.Integer(), nullable=True))
    op.add_column("prospects", sa.Column("tranche_age", sa.String(), nullable=True))
    op.add_column(
        "prospects",
        sa.Column("consentement_rgpd", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "prospects",
        sa.Column("consentement_demarchage", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("prospects", sa.Column("date_consentement", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("ip_creation", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("user_agent_creation", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("depenses_declarees_json", sa.String(), nullable=True))

    op.create_index("idx_prospects_utm_source", "prospects", ["utm_source"])
    op.create_index("idx_prospects_utm_campaign", "prospects", ["utm_campaign"])
    op.create_index("idx_prospects_origine", "prospects", ["origine"])

    # -- clients : âge pour calibrer les moyennes par tranche ---------------
    op.add_column("clients", sa.Column("age", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "age")

    op.drop_index("idx_prospects_origine", table_name="prospects")
    op.drop_index("idx_prospects_utm_campaign", table_name="prospects")
    op.drop_index("idx_prospects_utm_source", table_name="prospects")

    for col in (
        "depenses_declarees_json", "user_agent_creation", "ip_creation",
        "date_consentement", "consentement_demarchage", "consentement_rgpd",
        "tranche_age", "age",
        "utm_term", "utm_content", "utm_campaign", "utm_medium", "utm_source",
    ):
        op.drop_column("prospects", col)
