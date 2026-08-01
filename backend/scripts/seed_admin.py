# ==============================================================================
#  SEED ADMIN — crée un compte admin si la table `utilisateurs` est vide
#  (premier lancement du backend/). Équivalent Postgres de
#  src/auth.py::creer_admin_par_defaut(), nécessaire depuis que
#  frontend-conseiller/ authentifie directement contre backend/ : sans lui,
#  il n'existe aucun moyen de créer le tout premier utilisateur (aucun
#  endpoint d'inscription n'est exposé, par design — la création de compte
#  est réservée aux admins via l'onglet "Utilisateurs").
#
#  Usage :
#      python -m backend.scripts.seed_admin
# ==============================================================================
from __future__ import annotations

import secrets

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.security import hash_password
from backend.models.user import User


def _pg_engine():
    # psycopg2 attend `sslmode=require`, pas le `ssl=require` d'asyncpg/Neon —
    # sans cette traduction, psycopg2 rejette le DSN ("invalid connection
    # option \"ssl\"").
    url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("ssl=require", "sslmode=require")
    return create_engine(url)


def seed_admin() -> str | None:
    """Crée un compte admin si `utilisateurs` est vide. Renvoie le mot de passe
    généré en clair (à noter immédiatement, jamais réaffiché) ou None si la
    table contenait déjà au moins un compte."""
    engine = _pg_engine()
    with Session(engine) as session:
        n = session.execute(select(func.count()).select_from(User)).scalar()
        if n:
            return None

        mot_de_passe = secrets.token_urlsafe(9)
        session.add(User(
            username="admin",
            nom_complet="Administrateur",
            password_hash=hash_password(mot_de_passe),
            role="Admin",
            doit_changer_mdp=True,
        ))
        session.commit()
        return mot_de_passe


def main() -> None:
    mot_de_passe = seed_admin()
    if mot_de_passe is None:
        print("La table utilisateurs contient déjà au moins un compte — rien créé.")
        return
    print("Compte admin créé.")
    print("  identifiant : admin")
    print(f"  mot de passe : {mot_de_passe}")
    print("Changement exigé à la première connexion (doit_changer_mdp).")


if __name__ == "__main__":
    main()
