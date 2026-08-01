"""Ajoute `est_prospect` sur `dossiers` — True tant que le client rattaché n'est
encore qu'un prospect côté CRM (src/api_client.py::creer_dossier, entite="prospect"),
bascule à False à la conversion (src/app.py::finaliser_conversion_client). Permet à
dossier_engine.documents_requis_pour_univers() de ne pas réclamer CNI/justificatif de
domicile tant que la personne n'est pas encore officiellement cliente.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dossiers",
        sa.Column("est_prospect", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("dossiers", "est_prospect")
