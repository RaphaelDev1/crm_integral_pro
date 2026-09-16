"""Complète la trame box (docs/QUESTIONS_PAR_SECTEUR.md, B4/B5/B6/B7) exposée
au prospect sur son lien personnel (/dossier/[token]/situation,
frontend-portail) : nombre d'utilisateurs simultanés en streaming + usage 4K
(B4), télétravail/visios (B5), intérêt pour une box 4G/5G en remplacement
(B6), téléphone fixe via la box (B7). Posées uniquement sur le contrat box
concurrent du prospect, jamais sur /economiser (landing volontairement courte).

Revision ID: 0051
Revises: 0050
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contrats", sa.Column("nb_utilisateurs_streaming", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("usage_4k", sa.Boolean(), nullable=True))
    op.add_column("contrats", sa.Column("teletravail", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("interet_box_4g5g", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("telephone_fixe_utilise", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("appels_fixe_mensuels", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("contrats", "appels_fixe_mensuels")
    op.drop_column("contrats", "telephone_fixe_utilise")
    op.drop_column("contrats", "interet_box_4g5g")
    op.drop_column("contrats", "teletravail")
    op.drop_column("contrats", "usage_4k")
    op.drop_column("contrats", "nb_utilisateurs_streaming")
