"""Ligne mobile principale d'un client/prospect.

Un client/prospect peut avoir plusieurs contrats "Forfait mobile" (plusieurs
lignes du foyer) sans qu'aucun ne soit distingué comme la ligne de référence.
Le lien public "situation actuelle" (backend/routers/portail_public.py::
_contrat_situation_actuelle_prospect) et l'étape 3 du diagnostic
(EtapeSituation.tsx::BlocTelecom) en avaient besoin pour savoir quel contrat
mettre à jour plutôt que d'en recréer un ou de mettre à jour la mauvaise
ligne. `ligne_principale` est posé automatiquement à True sur le premier
contrat mobile créé pour une entité (backend/routers/contrats.py::
creer_contrat) et peut être réassigné manuellement depuis la fiche
client/prospect.

Revision ID: 0041
Revises: 0040
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contrats",
        sa.Column("ligne_principale", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("contrats", "ligne_principale")
