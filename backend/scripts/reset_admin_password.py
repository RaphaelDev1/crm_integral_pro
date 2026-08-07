# ==============================================================================
#  RESET ADMIN PASSWORD — régénère le mot de passe d'un compte existant sans
#  rien supprimer, pour le cas où l'identifiant/mot de passe admin a été perdu.
#  Contrepartie non destructive de seed_admin.py (qui ne crée un compte que si
#  la table est vide).
#
#  Usage :
#      python -m backend.scripts.reset_admin_password [username]
#      (username par défaut : "admin")
# ==============================================================================
from __future__ import annotations

import secrets
import sys

from sqlalchemy import create_engine, select
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


def reset_admin_password(username: str = "admin") -> str | None:
    """Régénère le mot de passe du compte `username`. Renvoie le mot de passe
    généré en clair (à noter immédiatement, jamais réaffiché) ou None si aucun
    compte ne porte ce nom."""
    engine = _pg_engine()
    with Session(engine) as session:
        utilisateur = session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if utilisateur is None:
            return None

        mot_de_passe = secrets.token_urlsafe(9)
        utilisateur.password_hash = hash_password(mot_de_passe)
        utilisateur.actif = True
        utilisateur.doit_changer_mdp = True
        session.commit()
        return mot_de_passe


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    mot_de_passe = reset_admin_password(username)
    if mot_de_passe is None:
        print(f"Aucun compte '{username}' trouvé — rien changé.")
        return
    print(f"Mot de passe réinitialisé pour '{username}'.")
    print(f"  identifiant : {username}")
    print(f"  mot de passe : {mot_de_passe}")
    print("Changement exigé à la première connexion (doit_changer_mdp).")


if __name__ == "__main__":
    main()
