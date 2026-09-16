"""Complète la trame mobile (docs/QUESTIONS_PAR_SECTEUR.md) exposée au
prospect sur son lien personnel (/dossier/[token]/situation, frontend-portail)
avec les questions de portabilité : souhait de conserver son numéro, RIO,
numéro de ligne à porter, eSIM ou carte SIM — jusqu'ici seulement modélisées
côté `Demarche.donnees_requises` (démarche "portabilite", qui exige un
dossier) et donc invisibles pour un prospect qui n'en a pas encore.

Revision ID: 0049
Revises: 0048
Create Date: 2026-09-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contrats", sa.Column("conserver_numero", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("rio", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("numero_ligne", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("type_sim", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("contrats", "type_sim")
    op.drop_column("contrats", "numero_ligne")
    op.drop_column("contrats", "rio")
    op.drop_column("contrats", "conserver_numero")
