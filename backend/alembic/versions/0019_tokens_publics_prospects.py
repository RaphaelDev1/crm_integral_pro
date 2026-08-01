"""Permet à un TokenPublic de cibler un Prospect (pas encore client) au lieu
d'un Client — parcours « envoyer un lien à un prospect chaud pour qu'il
transmette facture/speedtest avant même la conversion », cf.
src/prospects_engine.py::creer_token_documents. `client_id` devient nullable,
ajout de `prospect_id` nullable, contrainte XOR (exactement l'un des deux).

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("tokens_publics", "client_id", nullable=True)
    op.add_column(
        "tokens_publics",
        sa.Column("prospect_id", sa.Integer(), sa.ForeignKey("prospects.id"), nullable=True),
    )
    op.create_index("ix_tokens_publics_prospect_id", "tokens_publics", ["prospect_id"])
    op.create_check_constraint(
        "ck_tokens_publics_client_xor_prospect",
        "tokens_publics",
        "(client_id IS NULL) != (prospect_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tokens_publics_client_xor_prospect", "tokens_publics", type_="check")
    op.drop_index("ix_tokens_publics_prospect_id", table_name="tokens_publics")
    op.drop_column("tokens_publics", "prospect_id")
    op.alter_column("tokens_publics", "client_id", nullable=False)
