"""Situation actuelle (satisfaction réseau/envie de rester/défaut technique)
et débit mesuré (speedtest) rattachés au `Contrat` plutôt qu'à `Client`/
`Prospect`.

Jusqu'ici, `SituationActuelleCard.tsx` écrivait ces champs directement sur
`clients`/`prospects` (colonnes globales, un seul "opérateur actuel" par
personne), séparément des lignes `Contrat` (`chez_nous=False`) qui portent
déjà fournisseur/prix/consommation pour chaque forfait concurrent. On
rattache donc satisfaction/envie de rester/défaut technique/débit mesuré au
`Contrat` concerné (mobile, box...) — voir
frontend-conseiller/components/clients/ContratForm.tsx et
backend/routers/portail_public.py. Les colonnes existantes sur
`clients`/`prospects` ne sont pas supprimées (aucune perte de données),
seulement plus jamais écrites par la nouvelle UI.

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contrats", sa.Column("satisfaction_reseau", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("veut_rester", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("defaut_technique", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("speed_down", sa.Float(), nullable=True))
    op.add_column("contrats", sa.Column("speed_up", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("contrats", "speed_up")
    op.drop_column("contrats", "speed_down")
    op.drop_column("contrats", "defaut_technique")
    op.drop_column("contrats", "veut_rester")
    op.drop_column("contrats", "satisfaction_reseau")
