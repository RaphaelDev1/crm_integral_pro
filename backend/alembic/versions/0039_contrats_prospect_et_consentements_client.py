"""Contrats rattachables à un prospect (avant conversion en client) +
champs de consentement/âge sur `clients` en miroir de `prospects`.

- `contrats.prospect_id` (FK `prospects.id`, nullable) : un prospect a souvent
  déjà des contrats en cours chez un concurrent avant de devenir client — on
  doit pouvoir les enregistrer dès ce stade (voir backend/routers/leads_public.py
  qui alimente désormais ces lignes depuis la landing /economiser).
- `contrats.consommation` (texte libre, ex. "120 Go", "3500 kWh").
- `contrats.chez_nous` (bool, default False) : distingue un contrat souscrit
  chez nous d'un contrat concurrent en cours, indépendamment de `statut_contrat`
  qui décrit l'avancement de notre propre pipeline de vente.
- `clients.tranche_age`/`consentement_rgpd`/`consentement_demarchage`/
  `date_consentement` : `clients` avait déjà `age` mais pas le reste — ces
  colonnes existent sur `prospects` depuis 0027/0028 et doivent suivre le
  prospect à sa conversion (voir backend/services/prospect_conversion.py).

Revision ID: 0039
Revises: 0038
Create Date: 2026-08-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contrats", sa.Column("prospect_id", sa.Integer(), sa.ForeignKey("prospects.id"), nullable=True))
    op.add_column("contrats", sa.Column("consommation", sa.String(), nullable=True))
    op.add_column("contrats", sa.Column("chez_nous", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("clients", sa.Column("tranche_age", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("consentement_rgpd", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("clients", sa.Column("consentement_demarchage", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("clients", sa.Column("date_consentement", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "date_consentement")
    op.drop_column("clients", "consentement_demarchage")
    op.drop_column("clients", "consentement_rgpd")
    op.drop_column("clients", "tranche_age")

    op.drop_column("contrats", "chez_nous")
    op.drop_column("contrats", "consommation")
    op.drop_column("contrats", "prospect_id")
