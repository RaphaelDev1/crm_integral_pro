# ==============================================================================
#  AUTHENTIFICATION (PBKDF2-SHA256) + GESTION DES UTILISATEURS
# ==============================================================================
import hashlib
import secrets
from datetime import datetime

import pandas as pd
import sqlite3

from db import get_conn

_ITERATIONS = 260_000   # OWASP 2024 recommandation pour PBKDF2-SHA256

CHAMPS_UTILISATEUR = {"nom_complet", "role", "actif", "password_hash"}


def hash_password(password: str) -> str:
    """Retourne 'salt:hash' stockable en base."""
    salt = secrets.token_hex(16)
    h    = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return f"{salt}:{h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Vérifie un mot de passe contre le hash stocké. Résistant aux attaques de timing."""
    try:
        salt, h = stored.split(":", 1)
        new_h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
        return secrets.compare_digest(new_h.hex(), h)
    except Exception:
        return False


def creer_utilisateur(username: str, nom_complet: str, password: str, role: str = "Conseiller"):
    conn = get_conn()
    c    = conn.cursor()
    try:
        c.execute(
            """INSERT INTO utilisateurs (username, nom_complet, password_hash, role, date_creation)
               VALUES (?,?,?,?,?)""",
            (username.strip().lower(), nom_complet.strip(), hash_password(password), role,
             datetime.now().strftime("%d/%m/%Y %H:%M"))
        )
        conn.commit()
        return True, "Utilisateur créé avec succès."
    except sqlite3.IntegrityError:
        return False, f"L'identifiant « {username} » est déjà utilisé."
    finally:
        conn.close()


def creer_admin_par_defaut():
    """Crée un compte admin si la table est vide (premier lancement)."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM utilisateurs")
    n = c.fetchone()[0]
    conn.close()
    if n == 0:
        creer_utilisateur("admin", "Administrateur", "Admin2026!", "Admin")
        return True
    return False


def authentifier_utilisateur(username: str, password: str):
    """Retourne le dict utilisateur si les identifiants sont corrects, sinon None."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        "SELECT id, username, nom_complet, password_hash, role FROM utilisateurs WHERE username=? AND actif=1",
        (username.strip().lower(),)
    )
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    user = dict(row)
    if verify_password(password, user["password_hash"]):
        return user
    return None


def lire_utilisateurs():
    conn = get_conn()
    df   = pd.read_sql_query(
        "SELECT id, username, nom_complet, role, actif, date_creation FROM utilisateurs ORDER BY id",
        conn
    )
    conn.close()
    return df


def maj_utilisateur(uid: int, champ: str, valeur):
    if champ not in CHAMPS_UTILISATEUR:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE utilisateurs SET {champ}=? WHERE id=?", (valeur, uid))
    conn.commit()
    conn.close()


def supprimer_utilisateur(uid: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM utilisateurs WHERE id=?", (uid,))
    conn.commit()
    conn.close()
