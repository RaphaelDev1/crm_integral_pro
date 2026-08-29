"""Enrichissements landing V3 — adresse/fibre, validation téléphone, FAI détecté,
idempotence email J+1.

Ajoute au modèle `prospects` les colonnes nécessaires aux chantiers P2.1
(adresse + éligibilité fibre niveau commune), P2.2 (validation Twilio Lookup),
P2.3 (FAI détecté par IP) et P3.2 (idempotence de l'email de relance J+1),
tous alimentés par backend/routers/leads_public.py et backend/workers/tasks.py.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("code_insee", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("prospects", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("prospects", sa.Column("fibre_disponible", sa.Boolean(), nullable=True))
    op.add_column("prospects", sa.Column("fibre_taux_couverture", sa.Float(), nullable=True))
    op.add_column("prospects", sa.Column("telephone_verifie", sa.Boolean(), nullable=True))
    op.add_column("prospects", sa.Column("telephone_type_ligne", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("operateur_detecte_ip", sa.String(), nullable=True))
    op.add_column(
        "prospects",
        sa.Column("email_j1_envoye", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("idx_prospects_code_insee", "prospects", ["code_insee"])


def downgrade() -> None:
    op.drop_index("idx_prospects_code_insee", table_name="prospects")
    op.drop_column("prospects", "email_j1_envoye")
    op.drop_column("prospects", "operateur_detecte_ip")
    op.drop_column("prospects", "telephone_type_ligne")
    op.drop_column("prospects", "telephone_verifie")
    op.drop_column("prospects", "fibre_taux_couverture")
    op.drop_column("prospects", "fibre_disponible")
    op.drop_column("prospects", "longitude")
    op.drop_column("prospects", "latitude")
    op.drop_column("prospects", "code_insee")
