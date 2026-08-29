"""Bonus/malus assurance auto, plage horaire de rappel souhaitée, motif de refus.

Ajoute :
  - `prospects.bonus_malus_auto` : coefficient bonus/malus assurance auto
    déclaré à l'étape 2 du formulaire /economiser (remplace l'ancien champ
    "opérateur actuel" retiré du tunnel), texte libre ("0.50", "1.00", "3.50"…)
    pour rester tolérant à la saisie.
  - `prospects.plage_horaire_rappel` : créneau souhaité par le prospect pour
    être rappelé (étape 3 du formulaire), ex. "Matin (9h-12h)".
  - `prospects.motif_refus` : raison donnée par le client quand il refuse
    notre service, saisie par le conseiller sur la fiche prospect
    (statut "Refusé").

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("bonus_malus_auto", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("plage_horaire_rappel", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("motif_refus", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("prospects", "motif_refus")
    op.drop_column("prospects", "plage_horaire_rappel")
    op.drop_column("prospects", "bonus_malus_auto")
