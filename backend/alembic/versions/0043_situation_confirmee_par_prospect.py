"""`situation_renseignee` (portail_public.py::_contexte_token_prospect) était
déduit de la présence de valeurs sur les champs "situation actuelle" du
`Contrat` (fournisseur/satisfaction_reseau/veut_rester/defaut_technique) —
or ces mêmes champs sont aussi remplis ailleurs (capture landing /economiser,
saisie conseiller via ContratForm.tsx), donc le badge "reçu" s'affichait au
prospect avant même qu'il ait soumis quoi que ce soit via
POST /portail/{token}/situation.

On ajoute un flag explicite, posé uniquement par
`renseigner_situation_actuelle` (la vraie soumission du prospect), qui
devient l'unique source de vérité pour `situation_renseignee`.

Revision ID: 0043
Revises: 0042
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contrats", sa.Column("situation_confirmee_le", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("contrats", "situation_confirmee_le")
