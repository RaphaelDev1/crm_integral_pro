"""Ajoute le flag `peut_renseigner_demarches` sur `tokens_publics` — autorise
le client à compléter, depuis son portail, les champs manquants d'une
démarche (RIO, PDL/PCE, RIB...). Migration séparée de 0007 (qui crée la
table `demarches`) pour pouvoir la rollback indépendamment : celle-ci touche
une table existante en production.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tokens_publics",
        sa.Column("peut_renseigner_demarches", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tokens_publics", "peut_renseigner_demarches")
