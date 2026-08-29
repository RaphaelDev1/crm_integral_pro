"""Upload de facture rattaché à une session de trame — PLAN_IMPLEMENTATION_4_PHASES.md §3.1.

Nouvelle table `session_facture` : la facture téléversée par le conseiller
pendant une session est analysée (réutilise
backend/services/facture_analyzer.py, déjà utilisé pour le CRM legacy) puis
proposée pour auto-remplissage des réponses — jamais appliquée sans
validation explicite du conseiller (voir ia_conseil_facture.py::appliquer).

Ajoute aussi `session_trame.synthese_llm_texte` (§3.3) : cache du paragraphe
de synthèse rédigé par LLM pour le PDF final, généré une seule fois par
session (idempotent).

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.create_table(
        "session_facture",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=_UUID_DEFAULT),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("session_trame.id"), nullable=True),
        sa.Column("categorie_slug", sa.Text(), sa.ForeignKey("categorie.slug"), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("nom_fichier", sa.Text(), nullable=True),
        # statut : en_attente | analysee | echouee
        sa.Column("statut", sa.Text(), server_default="en_attente", nullable=False),
        sa.Column("extraction", postgresql.JSONB(), nullable=True),
        sa.Column("reponses_appliquees", postgresql.JSONB(), nullable=True),
        sa.Column("erreur", sa.Text(), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("analysee_le", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_session_facture_session", "session_facture", ["session_id"])

    op.add_column("session_trame", sa.Column("synthese_llm_texte", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("session_trame", "synthese_llm_texte")

    op.drop_index("idx_session_facture_session", table_name="session_facture")
    op.drop_table("session_facture")
