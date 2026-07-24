"""État initial — miroir du schéma SQLite existant (utilisateurs, prospects,
clients, contrats, offres), tel que produit par src/db.py::initialiser_bdd()
et _migrer_bdd() au moment de la migration vers Postgres.

Revision ID: 0001
Revises:
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "utilisateurs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("nom_complet", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), server_default="Conseiller"),
        sa.Column("actif", sa.Boolean(), server_default=sa.true()),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("doit_changer_mdp", sa.Boolean(), server_default=sa.false()),
    )

    op.create_table(
        "prospects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ref", sa.String(), nullable=True),
        sa.Column("prenom", sa.String(), nullable=True),
        sa.Column("nom", sa.String(), nullable=True),
        sa.Column("telephone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("code_postal", sa.String(), nullable=True),
        sa.Column("ville", sa.String(), nullable=True),
        sa.Column("adresse", sa.String(), nullable=True),
        sa.Column("type_client", sa.String(), nullable=True),
        sa.Column("univers_interesse", sa.String(), nullable=True),
        sa.Column("service_principal", sa.String(), nullable=True),
        sa.Column("operateur_actuel", sa.String(), nullable=True),
        sa.Column("techno", sa.String(), nullable=True),
        sa.Column("data_go", sa.String(), nullable=True),
        sa.Column("cout_mensuel_actuel", sa.Float(), server_default="0"),
        sa.Column("offre_actuelle", sa.String(), nullable=True),
        sa.Column("satisfaction_reseau", sa.String(), nullable=True),
        sa.Column("veut_rester", sa.String(), nullable=True),
        sa.Column("speed_down", sa.Float(), server_default="0"),
        sa.Column("speed_up", sa.Float(), server_default="0"),
        sa.Column("cout_elec", sa.Float(), server_default="0"),
        sa.Column("cout_gaz", sa.Float(), server_default="0"),
        sa.Column("fournisseur_energie", sa.String(), nullable=True),
        sa.Column("abonnements", sa.String(), nullable=True),
        sa.Column("lignes_multi", sa.String(), nullable=True),
        sa.Column("economie_estimee_an", sa.Float(), server_default="0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("statut", sa.String(), server_default="À relancer"),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("date_relance", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=True),
        sa.Column("offres_interet", sa.String(), nullable=True),
        sa.Column("score", sa.Float(), server_default="0"),
        sa.Column("origine", sa.String(), server_default="Manuel"),
    )

    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ref", sa.String(), nullable=True),
        sa.Column("prenom", sa.String(), nullable=True),
        sa.Column("nom", sa.String(), nullable=True),
        sa.Column("telephone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("code_postal", sa.String(), nullable=True),
        sa.Column("ville", sa.String(), nullable=True),
        sa.Column("adresse", sa.String(), nullable=True),
        sa.Column("type_client", sa.String(), nullable=True),
        sa.Column("operateur_actuel", sa.String(), nullable=True),
        sa.Column("techno", sa.String(), nullable=True),
        sa.Column("data_go", sa.String(), nullable=True),
        sa.Column("offre_actuelle", sa.String(), nullable=True),
        sa.Column("cout_mensuel_actuel", sa.Float(), server_default="0"),
        sa.Column("satisfaction_reseau", sa.String(), nullable=True),
        sa.Column("veut_rester", sa.String(), nullable=True),
        sa.Column("speed_down", sa.Float(), server_default="0"),
        sa.Column("speed_up", sa.Float(), server_default="0"),
        sa.Column("fournisseur_energie", sa.String(), nullable=True),
        sa.Column("cout_elec", sa.Float(), server_default="0"),
        sa.Column("cout_gaz", sa.Float(), server_default="0"),
        sa.Column("economie_estimee_an", sa.Float(), server_default="0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("date_creation", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=True),
        sa.Column("date_relance", sa.String(), nullable=True),
        sa.Column("statut_relance", sa.String(), server_default="Aucune"),
    )

    op.create_table(
        "contrats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("univers", sa.String(), nullable=True),
        sa.Column("categorie", sa.String(), nullable=True),
        sa.Column("fournisseur", sa.String(), nullable=True),
        sa.Column("nom_offre", sa.String(), nullable=True),
        sa.Column("cout_mensuel", sa.Float(), server_default="0"),
        sa.Column("economie_mensuelle", sa.Float(), server_default="0"),
        sa.Column("reference_contrat", sa.String(), nullable=True),
        sa.Column("statut_contrat", sa.String(), nullable=True),
        sa.Column("date_souscription", sa.String(), nullable=True),
        sa.Column("date_fin_engagement", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=True),
    )

    op.create_table(
        "offres",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("univers", sa.String(), nullable=True),
        sa.Column("categorie", sa.String(), nullable=True),
        sa.Column("fournisseur", sa.String(), nullable=True),
        sa.Column("nom_offre", sa.String(), nullable=True),
        sa.Column("prix_mensuel", sa.Float(), nullable=True),
        sa.Column("frais_activation", sa.Float(), nullable=True),
        sa.Column("engagement_mois", sa.Integer(), nullable=True),
        sa.Column("caracteristiques", sa.String(), nullable=True),
        sa.Column("commission_affiliation", sa.Float(), nullable=True),
        sa.Column("data_go", sa.Float(), server_default="0"),
        sa.Column("actif", sa.Boolean(), server_default=sa.true()),
        sa.Column("url_souscription", sa.String(), nullable=True),
        sa.Column("code_affiliation", sa.String(), nullable=True),
        sa.Column("date_maj", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("offres")
    op.drop_table("contrats")
    op.drop_table("clients")
    op.drop_table("prospects")
    op.drop_table("utilisateurs")
