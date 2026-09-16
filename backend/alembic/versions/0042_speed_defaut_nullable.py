"""Le débit mesuré (speedtest) sur `clients`/`prospects` valait `0` par
défaut (`Float, default=0` + `server_default="0"`) au lieu de `NULL`. Le
frontend affichait donc le badge "Mesuré" dès l'ouverture de la fiche, avant
même qu'un test de débit ait été transmis (`speed_down != null` était
toujours vrai). Seule `backend/routers/portail_public.py::soumettre_speedtest`
écrit ces colonnes, et un test réel ne renvoie jamais exactement `0.0` — donc
tout `0.0` existant est une valeur par défaut jamais testée, pas un résultat.

Revision ID: 0042
Revises: 0041
Create Date: 2026-09-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("prospects", "clients"):
        op.execute(f"UPDATE {table} SET speed_down = NULL WHERE speed_down = 0")
        op.execute(f"UPDATE {table} SET speed_up = NULL WHERE speed_up = 0")
        op.alter_column(table, "speed_down", server_default=None)
        op.alter_column(table, "speed_up", server_default=None)


def downgrade() -> None:
    for table in ("prospects", "clients"):
        op.alter_column(table, "speed_down", server_default="0")
        op.alter_column(table, "speed_up", server_default="0")
