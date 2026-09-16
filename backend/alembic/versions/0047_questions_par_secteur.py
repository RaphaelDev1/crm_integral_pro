"""Trame de questions par secteur sur la landing publique /economiser
(docs QUESTIONS_PAR_SECTEUR.md — socle commun + questions à fort pouvoir de
filtrage par univers, cf. backend/routers/leads_public.py).

Socle commun (S5 objectif principal) + questions mobile (nb de lignes,
qualité réseau) sur `prospects` — décrivent la personne, pas un contrat
particulier. Questions énergie (chauffage, puissance souscrite, option
tarifaire, gros équipement) et box (usage TV, abonnements payants en plus)
sur `contrats` — rattachées au contrat concerné (Électricité/Gaz ou
Box-Fibre), comme `debit_declare`/`nom_offre` (migration 0046) pour la box.

Revision ID: 0047
Revises: 0046
Create Date: 2026-09-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prospects", sa.Column("objectif_principal", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("nb_lignes_mobiles", sa.String(), nullable=True))
    op.add_column("prospects", sa.Column("qualite_reseau_mobile", sa.String(), nullable=True))

    op.add_column("contrats", sa.Column("chauffage_principal", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("puissance_kva", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("option_tarifaire", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("gros_equipement_electrique", sa.Boolean(), nullable=True))
    op.add_column("contrats", sa.Column("usage_tv", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("abonnements_payants", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("contrats", "abonnements_payants")
    op.drop_column("contrats", "usage_tv")
    op.drop_column("contrats", "gros_equipement_electrique")
    op.drop_column("contrats", "option_tarifaire")
    op.drop_column("contrats", "puissance_kva")
    op.drop_column("contrats", "chauffage_principal")

    op.drop_column("prospects", "qualite_reseau_mobile")
    op.drop_column("prospects", "nb_lignes_mobiles")
    op.drop_column("prospects", "objectif_principal")
