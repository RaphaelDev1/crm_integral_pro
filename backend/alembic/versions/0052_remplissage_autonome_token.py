"""Ajoute `remplissage_autonome` sur tokens_publics : distingue, pour le lien
personnel envoyé à un prospect (/dossier/[token]/situation, frontend-portail),
le cas où le prospect répond seul (formulaire allégé, sans les questions
confort B4-B7 déjà isolées par la migration 0051) du cas où le conseiller
répond avec lui au téléphone (formulaire complet). Sans objet sur un token
client. Les tokens déjà émis restent traités comme "autonome" par défaut.

Revision ID: 0052
Revises: 0051
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tokens_publics",
        sa.Column("remplissage_autonome", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("tokens_publics", "remplissage_autonome")
