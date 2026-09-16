"""Ajoute la question M1a de la trame mobile (docs/QUESTIONS_PAR_SECTEUR.md) —
"Toutes les lignes chez le même opérateur ?" — posée par le conseiller sur la
ligne principale une fois le détail multi-lignes obtenu au téléphone (le
nombre exact de lignes n'est pas stocké séparément : il se déduit du nombre de
`Contrat` catégorie "Forfait mobile" du prospect/client).

Revision ID: 0050
Revises: 0049
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contrats", sa.Column("meme_operateur_mobile", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("contrats", "meme_operateur_mobile")
