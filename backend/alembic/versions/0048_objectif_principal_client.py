"""Objectif principal sur la fiche client

`objectif_principal` existait déjà sur `prospects` depuis la landing
/economiser (migration 0047) mais n'était repris ni sur `clients` ni dans les
schémas Pydantic — le conseiller n'avait donc aucun moyen de voir, une fois le
prospect converti, si la demande initiale était motivée par une raison
financière ("economiser") ou un gain de temps ("simplifier"), voir
backend/schemas/lead_public.py::OBJECTIFS_PRINCIPAUX. Ajoutée ici sur
`clients` et reprise à la conversion (prospect_conversion.CHAMPS_PROSPECT_VERS_CLIENT).

Revision ID: 0048
Revises: 0047
Create Date: 2026-09-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("objectif_principal", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "objectif_principal")
