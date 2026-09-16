"""Date et lieu de naissance du prospect/client

Nécessaires pour la page "informations personnelles" du tunnel de souscription
Free Mobile (date de naissance, département et ville de naissance) — jusqu'ici
non couverts par le CRM, ce qui empêchait tout pré-remplissage automatique de
cette page (voir backend/services/souscription_engine.py). Ajoutés sur
`prospects` (posés dans la trame du lien personnel, cf.
frontend-portail/app/dossier/[token]/situation/page.tsx) et repris sur
`clients` à la conversion (prospect_conversion.CHAMPS_PROSPECT_VERS_CLIENT),
même pattern que `objectif_principal` (migrations 0047/0048).

Revision ID: 0053
Revises: 0052
Create Date: 2026-09-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("prospects", "clients"):
        op.add_column(table, sa.Column("date_naissance", sa.String(), nullable=True))
        op.add_column(table, sa.Column("departement_naissance", sa.String(), nullable=True))
        op.add_column(table, sa.Column("ville_naissance", sa.String(), nullable=True))


def downgrade() -> None:
    for table in ("prospects", "clients"):
        op.drop_column(table, "ville_naissance")
        op.drop_column(table, "departement_naissance")
        op.drop_column(table, "date_naissance")
