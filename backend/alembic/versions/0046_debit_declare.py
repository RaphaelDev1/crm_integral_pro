"""Ajoute `debit_declare` sur `prospects` et `contrats` — débit auto-déclaré
par le visiteur sur la landing publique /economiser (champ libre "Débit box
(optionnel)", jamais mesuré), jusqu'ici écrit à tort dans `speed_down` (voir
backend/routers/leads_public.py). Cette colonne partagée avec le vrai test de
débit mesuré (backend/routers/portail_public.py::soumettre_speedtest) faisait
passer `speedtest_fait` à vrai dès l'ouverture du lien "collecte docs", sans
qu'aucun test réel n'ait été lancé. `debit_declare` sépare désormais la valeur
déclarée (indicative, gardée pour l'estimation) de la valeur mesurée
(`speed_down`, seule source de vérité pour `speedtest_fait`).

Revision ID: 0046
Revises: 0045
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("debit_declare", sa.Float(), nullable=True))
    op.add_column("contrats", sa.Column("debit_declare", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("contrats", "debit_declare")
    op.drop_column("prospects", "debit_declare")
