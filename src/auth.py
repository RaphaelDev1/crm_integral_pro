# ==============================================================================
#  AUTHENTIFICATION (PBKDF2-SHA256) + GESTION DES UTILISATEURS
# ==============================================================================
import hashlib
import secrets
from datetime import datetime, timedelta

import pandas as pd
import sqlite3

from db import get_conn

_ITERATIONS = 260_000   # OWASP 2024 recommandation pour PBKDF2-SHA256

CHAMPS_UTILISATEUR = {"nom_complet", "role", "actif", "password_hash", "doit_changer_mdp"}

# ── Rate limiting login ──────────────────────────────────────────────────────
MAX_TENTATIVES        = 5    # échecs consécutifs autorisés
FENETRE_MINUTES       = 15   # fenêtre glissante de blocage
_PURGE_RETENTION_JOURS = 1   # historique des tentatives conservé (purge opportuniste)
_FMT_TENTATIVE = "%Y-%m-%d %H:%M:%S"   # format triable lexicographiquement


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
    """Crée un compte admin si la table est vide (premier lancement). Le mot de
    passe est généré aléatoirement (jamais codé en dur) et son changement est
    exigé à la première connexion. Renvoie le mot de passe en clair (à afficher
    une seule fois à l'écran) ou None si aucun compte n'a été créé."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM utilisateurs")
    n = c.fetchone()[0]
    conn.close()
    if n == 0:
        mot_de_passe = secrets.token_urlsafe(9)   # ex. "kQ3f9zP-2xLmN1"
        creer_utilisateur("admin", "Administrateur", mot_de_passe, "Admin")
        conn = get_conn()
        c    = conn.cursor()
        c.execute("UPDATE utilisateurs SET doit_changer_mdp=1 WHERE username='admin'")
        conn.commit()
        conn.close()
        return mot_de_passe
    return None


def authentifier_utilisateur(username: str, password: str):
    """Retourne le dict utilisateur si les identifiants sont corrects, sinon None."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        "SELECT id, username, nom_complet, password_hash, role, doit_changer_mdp "
        "FROM utilisateurs WHERE username=? AND actif=1",
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


def _purger_vieilles_tentatives(c):
    seuil = (datetime.now() - timedelta(days=_PURGE_RETENTION_JOURS)).strftime(_FMT_TENTATIVE)
    c.execute("DELETE FROM login_tentatives WHERE date_tentative < ?", (seuil,))


def _enregistrer_tentative(username: str, ip: str, succes: bool):
    conn = get_conn()
    c    = conn.cursor()
    _purger_vieilles_tentatives(c)
    c.execute(
        "INSERT INTO login_tentatives (identifiant, ip, succes, date_tentative) VALUES (?,?,?,?)",
        (username.strip().lower(), ip or "", 1 if succes else 0, datetime.now().strftime(_FMT_TENTATIVE))
    )
    conn.commit()
    conn.close()


def _compte_verrouille(username: str, ip: str):
    """Renvoie (verrouillé: bool, minutes_restantes: int) selon les échecs
    consécutifs du couple (identifiant, ip) sur la fenêtre glissante. Un succès
    plus récent qu'un échec réinitialise le compteur."""
    conn = get_conn()
    c    = conn.cursor()
    seuil = (datetime.now() - timedelta(minutes=FENETRE_MINUTES)).strftime(_FMT_TENTATIVE)
    rows = c.execute(
        """SELECT succes, date_tentative FROM login_tentatives
           WHERE identifiant=? AND ip=? AND date_tentative >= ?
           ORDER BY date_tentative DESC""",
        (username.strip().lower(), ip or "", seuil)
    ).fetchall()
    conn.close()

    echecs, plus_recent_echec = 0, None
    for r in rows:
        if r["succes"]:
            break
        echecs += 1
        if plus_recent_echec is None:
            plus_recent_echec = r["date_tentative"]

    if echecs >= MAX_TENTATIVES and plus_recent_echec:
        expiration = datetime.strptime(plus_recent_echec, _FMT_TENTATIVE) + timedelta(minutes=FENETRE_MINUTES)
        restant_min = (expiration - datetime.now()).total_seconds() / 60
        if restant_min > 0:
            return True, max(1, round(restant_min))
    return False, 0


def authentifier_avec_limite(username: str, password: str, ip: str = ""):
    """Point d'entrée à utiliser par les UI (Streamlit + API) : applique le
    verrouillage (MAX_TENTATIVES échecs / FENETRE_MINUTES min, par couple
    identifiant+IP) avant de déléguer à authentifier_utilisateur(). Renvoie
    (user_dict_ou_None, message_erreur_ou_None)."""
    if not username or not username.strip():
        return None, "Identifiant ou mot de passe incorrect."

    verrouille, minutes_restantes = _compte_verrouille(username, ip)
    if verrouille:
        return None, (f"Trop de tentatives échouées. Réessayez dans "
                       f"{minutes_restantes} min.")

    user = authentifier_utilisateur(username, password)
    _enregistrer_tentative(username, ip, succes=user is not None)
    if user is None:
        return None, "Identifiant ou mot de passe incorrect."
    return user, None


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
