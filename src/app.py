# ==============================================================================
#  IA CONSEIL — CRM INTÉGRAL PRO  (Télécom · Énergie · Abonnements)
#  Logiciel interne pour conseillers — accompagnement client de A à Z
#
#  ÉTAPE 1 — Fondations solides :
#    ✅ Mode WAL SQLite, comptes nominatifs, rôles, traçabilité, sécurité SQL
#
#  ÉTAPE 2 — Fiabiliser l'existant :
#    ✅ Bug critique : st.rerun() manquant fin étape 5 (page bloquée après création client)
#    ✅ Bug : generer_ref() pouvait produire des doublons en accès concurrent
#    ✅ Bug : abonnements — calcul économie ignorait le coût client réel
#    ✅ Validation email + téléphone avant enregistrement
#    ✅ safe_float() — conversions numériques protégées, plus de crash
#    ✅ Spinner sur les opérations lentes (comparaison, PDF)
#    ✅ Filtre par statut sur la page Prospects
#    ✅ Confirmation avant suppression prospect / client
#    ✅ Affichage propre quand la recherche client ne retourne rien
#    ✅ Notes auto enrichies à la création
#
#  Lancement :
#     pip install streamlit pandas PyPDF2 fpdf2
#     streamlit run crm_integral_pro.py
#
#  Identifiants par défaut (premier lancement) :
#     Login : admin   /   Mot de passe : Admin2026!
#     → À changer immédiatement dans Admin > Utilisateurs
# ==============================================================================

import streamlit as st
import sqlite3
import pandas as pd
import re
import json
import hashlib
import secrets
import smtplib
import urllib.request
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from PyPDF2 import PdfReader

try:
    from fpdf import FPDF
    FPDF_OK = True
except Exception:
    FPDF_OK = False

st.set_page_config(page_title="IA Conseil - CRM Intégral Pro", layout="wide")

# ==============================================================================
#  UTILITAIRES GLOBAUX
# ==============================================================================
def safe_float(val, default: float = 0.0) -> float:
    """Conversion float robuste — jamais de crash sur valeur vide ou invalide."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def valider_email(email: str) -> bool:
    """Vérifie qu'un email a une forme valide (non bloquant, juste un avertissement)."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$", email.strip())) if email.strip() else True


def valider_telephone(tel: str) -> bool:
    """Vérifie qu'un numéro FR a 10 chiffres (autorise espaces/tirets)."""
    digits = re.sub(r"[\s.\-]", "", tel.strip())
    return bool(re.match(r"^(0|\+33)[1-9]\d{8}$", digits)) if digits else True


# ==============================================================================
#  OPTIONS GLOBALES
# ==============================================================================
DEBITS_OPTIONS       = ["100 Mbps", "400 Mbps", "1 Gbps", "2 Gbps", "5 Gbps", "8 Gbps"]
LISTE_OPERATEURS_TEL = ["Orange", "YouPrice (Réseau Orange)", "SFR", "Bouygues", "Free", "Autre / Aucun"]
LISTE_FOURNISSEURS_ENERGIE = ["EDF", "Engie", "TotalEnergies", "Eni", "Vattenfall", "Ekwateur", "OHM Énergie", "Autre / Aucun"]
LISTE_TECHNO         = ["FIBRE", "ADSL", "5G", "4G"]
SATISFACTION_RESEAU  = ["😀 Très content", "😐 Ça va", "😡 Pas du tout"]

UNIVERS              = ["Télécom", "Énergie", "Abonnements"]
CATEGORIES_TELECOM   = ["Mobile", "Box / Fibre", "Pack Box + Mobile", "Multi-lignes"]
CATEGORIES_ENERGIE   = ["Électricité", "Gaz", "Électricité Pro", "Gaz Pro"]
CATEGORIES_ABO       = ["Streaming Vidéo", "Musique", "Salle de sport", "SaaS / Logiciel", "Assurance", "Autre"]
SERVICE_PRINCIPAL    = ["Mobile uniquement", "Box / Fibre uniquement", "Pack Box + Mobile", "Multi-lignes"]

ROLES = ["Admin", "Conseiller", "Lecture"]

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ia_conseil_crm.db")

# Colonnes autorisées pour les mises à jour (protection injection SQL)
CHAMPS_PROSPECT = {
    "telephone", "email", "operateur_actuel", "offre_actuelle", "cout_mensuel_actuel",
    "notes", "statut", "date_relance", "satisfaction_reseau", "veut_rester",
    "ville", "code_postal", "prenom", "nom", "fournisseur_energie",
    "techno", "data_go", "speed_down", "speed_up", "type_client",
}
CHAMPS_CLIENT = {
    "telephone", "email", "ville", "code_postal", "operateur_actuel", "offre_actuelle",
    "cout_mensuel_actuel", "satisfaction_reseau", "veut_rester", "notes",
    "fournisseur_energie", "techno", "data_go", "speed_down", "speed_up",
    "economie_estimee_an",
}
CHAMPS_CONTRAT = {
    "nom_offre", "cout_mensuel", "economie_mensuelle", "statut_contrat",
    "reference_contrat", "fournisseur", "notes", "date_souscription",
}
CHAMPS_OFFRE = {
    "prix_mensuel", "frais_activation", "engagement_mois", "caracteristiques",
    "commission_affiliation", "actif", "nom_offre", "fournisseur", "categorie",
}
CHAMPS_UTILISATEUR = {"nom_complet", "role", "actif", "password_hash"}

# ==============================================================================
#  1. BASE DE DONNÉES — CONNEXION + WAL
# ==============================================================================
def get_conn():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")      # ← Écriture concurrente sécurisée
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def initialiser_bdd():
    conn = get_conn()
    c = conn.cursor()

    # Table utilisateurs (NOUVELLE en Étape 1)
    c.execute("""
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            username       TEXT    UNIQUE NOT NULL,
            nom_complet    TEXT    NOT NULL,
            password_hash  TEXT    NOT NULL,
            role           TEXT    DEFAULT 'Conseiller',
            actif          INTEGER DEFAULT 1,
            date_creation  TEXT
        )
    """)

    # Table prospects
    c.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            ref                   TEXT,
            prenom                TEXT,
            nom                   TEXT,
            telephone             TEXT,
            email                 TEXT,
            code_postal           TEXT,
            ville                 TEXT,
            type_client           TEXT,
            univers_interesse     TEXT,
            service_principal     TEXT,
            operateur_actuel      TEXT,
            techno                TEXT,
            data_go               TEXT,
            cout_mensuel_actuel   REAL,
            offre_actuelle        TEXT,
            satisfaction_reseau   TEXT,
            veut_rester           TEXT,
            speed_down            REAL,
            speed_up              REAL,
            cout_elec             REAL,
            cout_gaz              REAL,
            fournisseur_energie   TEXT,
            abonnements           TEXT,
            lignes_multi          TEXT,
            economie_estimee_an   REAL,
            notes                 TEXT,
            statut                TEXT,
            date_creation         TEXT,
            date_relance          TEXT,
            cree_par              TEXT
        )
    """)

    # Table clients
    c.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            ref                   TEXT,
            prenom                TEXT,
            nom                   TEXT,
            telephone             TEXT,
            email                 TEXT,
            code_postal           TEXT,
            ville                 TEXT,
            type_client           TEXT,
            operateur_actuel      TEXT,
            techno                TEXT,
            data_go               TEXT,
            offre_actuelle        TEXT,
            cout_mensuel_actuel   REAL,
            satisfaction_reseau   TEXT,
            veut_rester           TEXT,
            speed_down            REAL,
            speed_up              REAL,
            fournisseur_energie   TEXT,
            cout_elec             REAL,
            cout_gaz              REAL,
            economie_estimee_an   REAL,
            notes                 TEXT,
            date_creation         TEXT,
            cree_par              TEXT
        )
    """)

    # Table contrats
    c.execute("""
        CREATE TABLE IF NOT EXISTS contrats (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id           INTEGER,
            univers             TEXT,
            categorie           TEXT,
            fournisseur         TEXT,
            nom_offre           TEXT,
            cout_mensuel        REAL,
            economie_mensuelle  REAL,
            reference_contrat   TEXT,
            statut_contrat      TEXT,
            date_souscription   TEXT,
            notes               TEXT,
            cree_par            TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    # Table offres (catalogue)
    c.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            univers               TEXT,
            categorie             TEXT,
            fournisseur           TEXT,
            nom_offre             TEXT,
            prix_mensuel          REAL,
            frais_activation      REAL,
            engagement_mois       INTEGER,
            caracteristiques      TEXT,
            commission_affiliation REAL,
            actif                 INTEGER DEFAULT 1,
            date_maj              TEXT
        )
    """)

    conn.commit()
    conn.close()
    _migrer_bdd()   # ← Ajoute les colonnes manquantes aux BDD existantes


def _migrer_bdd():
    """
    Migration incrémentale : ajoute toutes les colonnes potentiellement
    absentes (base créée avec une version antérieure du code).
    Chaque ALTER TABLE est ignoré si la colonne existe déjà.
    """
    # (table, colonne, type SQLite)
    migrations = [
        # ── prospects ──────────────────────────────────────────────────
        ("prospects", "type_client",          "TEXT"),
        ("prospects", "univers_interesse",    "TEXT"),
        ("prospects", "service_principal",    "TEXT"),
        ("prospects", "operateur_actuel",     "TEXT"),
        ("prospects", "techno",               "TEXT"),
        ("prospects", "data_go",              "TEXT"),
        ("prospects", "offre_actuelle",       "TEXT"),
        ("prospects", "cout_mensuel_actuel",  "REAL DEFAULT 0"),
        ("prospects", "satisfaction_reseau",  "TEXT"),
        ("prospects", "veut_rester",          "TEXT"),
        ("prospects", "speed_down",           "REAL DEFAULT 0"),
        ("prospects", "speed_up",             "REAL DEFAULT 0"),
        ("prospects", "cout_elec",            "REAL DEFAULT 0"),
        ("prospects", "cout_gaz",             "REAL DEFAULT 0"),
        ("prospects", "fournisseur_energie",  "TEXT"),
        ("prospects", "abonnements",          "TEXT"),
        ("prospects", "lignes_multi",         "TEXT"),
        ("prospects", "economie_estimee_an",  "REAL DEFAULT 0"),
        ("prospects", "statut",               "TEXT DEFAULT 'À relancer'"),
        ("prospects", "date_relance",         "TEXT"),
        ("prospects", "cree_par",             "TEXT"),
        # ── clients ────────────────────────────────────────────────────
        ("clients",   "type_client",          "TEXT"),
        ("clients",   "operateur_actuel",     "TEXT"),
        ("clients",   "techno",               "TEXT"),
        ("clients",   "data_go",              "TEXT"),
        ("clients",   "offre_actuelle",       "TEXT"),
        ("clients",   "cout_mensuel_actuel",  "REAL DEFAULT 0"),
        ("clients",   "satisfaction_reseau",  "TEXT"),
        ("clients",   "veut_rester",          "TEXT"),
        ("clients",   "speed_down",           "REAL DEFAULT 0"),
        ("clients",   "speed_up",             "REAL DEFAULT 0"),
        ("clients",   "fournisseur_energie",  "TEXT"),
        ("clients",   "cout_elec",            "REAL DEFAULT 0"),
        ("clients",   "cout_gaz",             "REAL DEFAULT 0"),
        ("clients",   "economie_estimee_an",  "REAL DEFAULT 0"),
        ("clients",   "cree_par",             "TEXT"),
        # ── contrats ───────────────────────────────────────────────────
        ("contrats",  "cree_par",             "TEXT"),
    ]
    conn = get_conn()
    c    = conn.cursor()
    for table, col, typ in migrations:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        except Exception:
            pass   # Colonne déjà présente → on ignore silencieusement
    conn.commit()
    conn.close()


initialiser_bdd()

# ==============================================================================
#  2. AUTHENTIFICATION — HASH PBKDF2-SHA256
# ==============================================================================
_ITERATIONS = 260_000   # OWASP 2024 recommandation pour PBKDF2-SHA256

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


# ==============================================================================
#  3. GESTION DES UTILISATEURS
# ==============================================================================
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


# Crée l'admin par défaut si besoin (premier lancement)
_admin_cree = creer_admin_par_defaut()

# ==============================================================================
#  4. PROSPECTS
# ==============================================================================
def ajouter_prospect(d: dict):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO prospects
        (ref, prenom, nom, telephone, email, code_postal, ville, type_client,
         univers_interesse, service_principal, operateur_actuel, techno, data_go,
         cout_mensuel_actuel, offre_actuelle, satisfaction_reseau, veut_rester,
         speed_down, speed_up, cout_elec, cout_gaz, fournisseur_energie,
         abonnements, lignes_multi, economie_estimee_an, notes, statut,
         date_creation, date_relance, cree_par)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get("ref"),             d.get("prenom"),          d.get("nom"),
        d.get("telephone"),       d.get("email"),           d.get("code_postal"),
        d.get("ville"),           d.get("type_client"),     d.get("univers_interesse"),
        d.get("service_principal"),d.get("operateur_actuel"),d.get("techno"),
        d.get("data_go"),         d.get("cout_mensuel_actuel", 0.0),
        d.get("offre_actuelle"),  d.get("satisfaction_reseau"),d.get("veut_rester"),
        d.get("speed_down", 0.0), d.get("speed_up", 0.0),  d.get("cout_elec", 0.0),
        d.get("cout_gaz", 0.0),   d.get("fournisseur_energie"),d.get("abonnements"),
        d.get("lignes_multi"),    d.get("economie_estimee_an", 0.0),d.get("notes"),
        d.get("statut", "À relancer"),
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        d.get("date_relance", ""),
        d.get("cree_par", ""),
    ))
    conn.commit()
    conn.close()


def lire_prospects():
    conn = get_conn()
    df   = pd.read_sql_query("SELECT * FROM prospects ORDER BY id DESC", conn)
    conn.close()
    return df


def maj_prospect(pid: int, champ: str, valeur):
    if champ not in CHAMPS_PROSPECT:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE prospects SET {champ}=? WHERE id=?", (valeur, pid))
    conn.commit()
    conn.close()


def supprimer_prospect(pid: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM prospects WHERE id=?", (pid,))
    conn.commit()
    conn.close()


# ==============================================================================
#  5. CLIENTS
# ==============================================================================
def ajouter_client(d: dict) -> int:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO clients
        (ref, prenom, nom, telephone, email, code_postal, ville, type_client,
         operateur_actuel, techno, data_go, offre_actuelle, cout_mensuel_actuel,
         satisfaction_reseau, veut_rester, speed_down, speed_up,
         fournisseur_energie, cout_elec, cout_gaz, economie_estimee_an,
         notes, date_creation, cree_par)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get("ref"),             d.get("prenom"),          d.get("nom"),
        d.get("telephone"),       d.get("email"),           d.get("code_postal"),
        d.get("ville"),           d.get("type_client"),     d.get("operateur_actuel"),
        d.get("techno"),          d.get("data_go"),         d.get("offre_actuelle"),
        d.get("cout_mensuel_actuel", 0.0),
        d.get("satisfaction_reseau"),d.get("veut_rester"),
        d.get("speed_down", 0.0), d.get("speed_up", 0.0),  d.get("fournisseur_energie"),
        d.get("cout_elec", 0.0),  d.get("cout_gaz", 0.0),  d.get("economie_estimee_an", 0.0),
        d.get("notes"),
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        d.get("cree_par", ""),
    ))
    cid = c.lastrowid
    conn.commit()
    conn.close()
    return cid


def lire_clients():
    conn = get_conn()
    df   = pd.read_sql_query("SELECT * FROM clients ORDER BY id DESC", conn)
    conn.close()
    return df


def maj_client(cid: int, champ: str, valeur):
    if champ not in CHAMPS_CLIENT:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE clients SET {champ}=? WHERE id=?", (valeur, cid))
    conn.commit()
    conn.close()


def supprimer_client(cid: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM contrats WHERE client_id=?", (cid,))
    c.execute("DELETE FROM clients WHERE id=?", (cid,))
    conn.commit()
    conn.close()


# ==============================================================================
#  6. CONTRATS
# ==============================================================================
def ajouter_contrat(d: dict):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO contrats
        (client_id, univers, categorie, fournisseur, nom_offre, cout_mensuel,
         economie_mensuelle, reference_contrat, statut_contrat, date_souscription,
         notes, cree_par)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get("client_id"),       d.get("univers"),         d.get("categorie"),
        d.get("fournisseur"),     d.get("nom_offre"),       d.get("cout_mensuel", 0.0),
        d.get("economie_mensuelle", 0.0),d.get("reference_contrat"),
        d.get("statut_contrat", "En cours d'ouverture"),
        datetime.now().strftime("%d/%m/%Y"),
        d.get("notes"),           d.get("cree_par", ""),
    ))
    conn.commit()
    conn.close()


def lire_contrats_client(cid: int):
    conn = get_conn()
    df   = pd.read_sql_query(
        "SELECT * FROM contrats WHERE client_id=? ORDER BY id DESC", conn, params=(cid,)
    )
    conn.close()
    return df


def maj_contrat(ctid: int, champ: str, valeur):
    if champ not in CHAMPS_CONTRAT:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE contrats SET {champ}=? WHERE id=?", (valeur, ctid))
    conn.commit()
    conn.close()


def supprimer_contrat(ctid: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM contrats WHERE id=?", (ctid,))
    conn.commit()
    conn.close()


# ==============================================================================
#  7. OFFRES (CATALOGUE)
# ==============================================================================
def ajouter_offre(d: dict):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO offres
        (univers, categorie, fournisseur, nom_offre, prix_mensuel, frais_activation,
         engagement_mois, caracteristiques, commission_affiliation, actif, date_maj)
        VALUES (?,?,?,?,?,?,?,?,?,1,?)
    """, (
        d.get("univers"),         d.get("categorie"),       d.get("fournisseur"),
        d.get("nom_offre"),       d.get("prix_mensuel", 0.0),d.get("frais_activation", 0.0),
        d.get("engagement_mois", 0),d.get("caracteristiques"),d.get("commission_affiliation", 0.0),
        datetime.now().strftime("%d/%m/%Y"),
    ))
    conn.commit()
    conn.close()


def lire_offres(univers=None, categorie=None, actif_seulement=True):
    conn   = get_conn()
    q      = "SELECT * FROM offres WHERE 1=1"
    params = []
    if actif_seulement:
        q += " AND actif=1"
    if univers:
        q += " AND univers=?";    params.append(univers)
    if categorie:
        q += " AND categorie=?";  params.append(categorie)
    q += " ORDER BY prix_mensuel ASC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def maj_offre(oid: int, champ: str, valeur):
    if champ not in CHAMPS_OFFRE:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE offres SET {champ}=?, date_maj=? WHERE id=?",
              (valeur, datetime.now().strftime("%d/%m/%Y"), oid))
    conn.commit()
    conn.close()


def supprimer_offre(oid: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM offres WHERE id=?", (oid,))
    conn.commit()
    conn.close()


def compter_offres() -> int:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM offres WHERE actif=1")
    n = c.fetchone()[0]
    conn.close()
    return n


def inserer_offres_demo():
    """Catalogue de démonstration — à charger depuis Admin > Pré-remplir."""
    demo = [
        # ---- TÉLÉCOM : Mobile ----
        ("Télécom","Mobile","Free","Forfait Free 5G 350 Go",19.99,10,0,"350 Go - 5G - Appels/SMS illimités - Europe incluse",30),
        ("Télécom","Mobile","Bouygues","B&You 200 Go",13.99,0,0,"200 Go - 5G - Illimité - 35 Go Europe",25),
        ("Télécom","Mobile","SFR","RED 130 Go",12.99,0,0,"130 Go - 5G - Illimité - 25 Go Europe",22),
        ("Télécom","Mobile","YouPrice (Réseau Orange)","Le Series 100 Go",9.99,0,0,"100 Go - Réseau Orange - Illimité",20),
        ("Télécom","Mobile","Orange","Forfait 5G 150 Go",24.99,0,0,"150 Go - 5G+ - Meilleure couverture",35),
        ("Télécom","Mobile","Free","Forfait Free 2€",2.00,0,0,"2h appels - SMS illimités - 50 Mo",5),
        # ---- TÉLÉCOM : Box / Fibre ----
        ("Télécom","Box / Fibre","Free","Freebox Pop Fibre",29.99,0,0,"Jusqu'à 5 Gbps - WiFi 7 - TV incluse",50),
        ("Télécom","Box / Fibre","Bouygues","Bbox Fibre Must",31.99,0,0,"2 Gbps - WiFi 6 - 180 chaînes",45),
        ("Télécom","Box / Fibre","SFR","SFR Fibre Power",34.99,0,0,"2 Gbps - décodeur 4K",42),
        ("Télécom","Box / Fibre","Orange","Livebox Fibre",39.99,0,0,"2 Gbps - WiFi 6 - réseau Orange",55),
        ("Télécom","Box / Fibre","Free","Freebox Ultra",49.99,0,0,"8 Gbps - WiFi 7 - Netflix/Disney+ inclus",60),
        # ---- TÉLÉCOM : Pack Box + Mobile ----
        ("Télécom","Pack Box + Mobile","Bouygues","Pack Bbox + Forfait 200 Go",42.99,0,0,"Fibre 2 Gbps + 200 Go 5G",60),
        ("Télécom","Pack Box + Mobile","SFR","Pack Fibre + RED 130 Go",44.99,0,0,"Fibre 2 Gbps + 130 Go",55),
        ("Télécom","Pack Box + Mobile","Free","Freebox Pop + Forfait 350 Go",39.98,0,0,"Fibre 5 Gbps + 350 Go 5G",70),
        ("Télécom","Pack Box + Mobile","Orange","Livebox + Forfait 150 Go",54.99,0,0,"Fibre 2 Gbps + 150 Go 5G",75),
        # ---- TÉLÉCOM : Multi-lignes ----
        ("Télécom","Multi-lignes","Free","2 lignes Free 350 Go",35.98,0,0,"2 forfaits 350 Go (-10% 2e ligne)",50),
        ("Télécom","Multi-lignes","Bouygues","Pack famille 4 lignes",49.99,0,0,"4 forfaits 100 Go - réduction famille",70),
        # ---- ÉNERGIE ----
        ("Énergie","Électricité","TotalEnergies","Offre Verte Fixe Élec",89.00,0,12,"Prix kWh bloqué 1 an - 100% renouvelable",40),
        ("Énergie","Électricité","Ekwateur","Élec 100% renouvelable",92.00,0,0,"Sans engagement - électricité verte",35),
        ("Énergie","Électricité","Engie","Élec Référence",95.00,0,12,"Prix indexé - service client FR",38),
        ("Énergie","Électricité","EDF","Tarif Bleu",99.00,0,0,"Tarif réglementé - sans engagement",25),
        ("Énergie","Gaz","TotalEnergies","Gaz Fixe",78.00,0,12,"Prix bloqué 1 an",35),
        ("Énergie","Gaz","Eni","Astucio Gaz",82.00,0,12,"Prix fixe - compensation carbone",33),
        ("Énergie","Gaz","Engie","Gaz Référence",85.00,0,0,"Indexé - sans engagement",30),
        # ---- ABONNEMENTS ----
        ("Abonnements","Streaming Vidéo","Netflix","Netflix Standard avec pub",5.99,0,0,"1080p - 2 écrans",0),
        ("Abonnements","Streaming Vidéo","Disney+","Disney+ Standard pub",5.99,0,0,"1080p",0),
        ("Abonnements","Streaming Vidéo","Prime Video","Amazon Prime Video",6.99,0,0,"Inclus dans Prime",0),
        ("Abonnements","Musique","Spotify","Spotify Premium",11.12,0,0,"Sans pub - hors ligne",0),
        ("Abonnements","Musique","Deezer","Deezer Premium",11.99,0,0,"Sans pub - HiFi option",0),
        ("Abonnements","Salle de sport","Basic-Fit","Abonnement Confort",29.99,30,12,"Accès illimité tous clubs",0),
        ("Abonnements","SaaS / Logiciel","Microsoft","Microsoft 365 Famille",10.00,0,0,"Office + 1 To OneDrive - 6 pers.",0),
    ]
    for u, cat, fourn, nom, prix, frais, eng, carac, comm in demo:
        ajouter_offre({"univers": u, "categorie": cat, "fournisseur": fourn, "nom_offre": nom,
                       "prix_mensuel": prix, "frais_activation": frais, "engagement_mois": eng,
                       "caracteristiques": carac, "commission_affiliation": comm})


def generer_ref() -> str:
    """Référence unique basée sur timestamp + 3 chiffres aléatoires.
    Évite les doublons en accès concurrent (deux conseillers simultanés)."""
    now    = datetime.now()
    suffix = secrets.randbelow(900) + 100   # 100–999
    return f"REF-{now.year}-{now.strftime('%m%d')}-{suffix}"


# ==============================================================================
#  8. ANALYSE PDF — FACTURE + SPEEDTEST
# ==============================================================================
def lire_pdf(fichier) -> str:
    try:
        reader = PdfReader(fichier)
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return ""


def analyser_facture(texte: str) -> dict:
    res = {"operateur": "Autre / Aucun", "fournisseur": "Autre / Aucun", "prix": 0.0,
           "cp": "", "ville": "", "prenom": "", "nom": "", "tel": "", "email": "", "data_go": ""}
    if not texte:
        return res
    t_low = texte.lower()
    t_up  = texte.upper()
    lignes = [l.strip() for l in texte.split("\n") if l.strip()]

    if re.search(r"you\s*price", t_low):              res["operateur"] = "YouPrice (Réseau Orange)"
    elif re.search(r"orange|sosh", t_low):             res["operateur"] = "Orange"
    elif re.search(r"sfr|red\s+by|red\s*sfr", t_low): res["operateur"] = "SFR"
    elif re.search(r"bouygues|b&you|b\s*&\s*you", t_low): res["operateur"] = "Bouygues"
    elif re.search(r"free|proxymity", t_low):          res["operateur"] = "Free"

    if re.search(r"\bedf\b", t_low):                  res["fournisseur"] = "EDF"
    elif re.search(r"engie|gdf", t_low):               res["fournisseur"] = "Engie"
    elif re.search(r"total\s*energies|total\s*direct", t_low): res["fournisseur"] = "TotalEnergies"
    elif re.search(r"\beni\b", t_low):                 res["fournisseur"] = "Eni"
    elif re.search(r"vattenfall", t_low):              res["fournisseur"] = "Vattenfall"
    elif re.search(r"ekwateur|ekwatour", t_low):       res["fournisseur"] = "Ekwateur"

    def to_float(v): return float(v.replace(" ", "").replace(",", "."))
    mots_prix = ["abonnement","forfait","mensuel","prélèvement","prelevement",
                 "facturé","total","ttc","à payer","a payer","montant","somme"]
    for ligne in lignes:
        ll = ligne.lower()
        if any(m in ll for m in mots_prix):
            mts = re.findall(r"(\d+(?:[\s,.]\d{1,2})?)\s*(?:€|eur)", ll)
            if mts:
                res["prix"] = to_float(mts[-1])
                break
    if res["prix"] == 0.0:
        allp = re.findall(r"(\d+(?:[\s,.]\d{1,2})?)\s*(?:€|eur)", t_low)
        if allp:
            res["prix"] = to_float(allp[-1])

    blacklist = ["RUE","AVENUE","BOULEVARD","BD","CHEMIN","ROUTE","ZA","ZI","BP","CEDEX",
                 "SIRET","SIREN","RCS","APE","TSA","CS","SERVICE","CLIENT","SOCIETE","BOUTIQUE"]
    for m in re.finditer(r"\b(\d{5})\b", t_up):
        cp = m.group(1)
        for ligne in lignes:
            if cp in ligne:
                lu = ligne.upper()
                if any(w in lu for w in ["TSA","CS","RCS","SIRET","SERVICE CLIENT","SOCIETE","BOUTIQUE"]):
                    continue
                sub  = re.sub(r"\bCEDEX\b.*", "", lu.replace(cp, "")).strip()
                cand = re.sub(r"[^A-ZÀ-ÿ\s\-]", "", sub).strip()
                cand = re.sub(r"\s+", " ", cand)
                if len(cand) > 2 and not any(w in cand.split() for w in blacklist):
                    res["cp"] = cp; res["ville"] = cand; break
        if res["ville"]:
            break

    for ligne in lignes[:25]:
        if any(w in ligne.upper() for w in ["SOCIETE","SERVICE","TSA","CS","BOUTIQUE","RCS","APE"]):
            continue
        mc = re.search(r"\b(M\.|MME|MR|MLLE|MONSIEUR|MADAME)\b\s+([A-ZÀ-ÿ\-]+)\s+([A-ZÀ-ÿ\-]+)", ligne.upper())
        if mc:
            res["prenom"] = mc.group(2).capitalize()
            res["nom"]    = mc.group(3).upper()
            break

    mt = re.search(r"\b(0[1-9])(?:[\s.-]?\d{2}){4}\b", texte)
    if mt: res["tel"] = mt.group(0)
    me = re.search(r"[a-zA-Z0-9-_\.]+@[a-zA-Z0-9-_\.]+\.[a-zA-Z]{2,5}", texte)
    if me: res["email"] = me.group(0)
    md = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:GO|GB)", t_up)
    if md: res["data_go"] = md.group(1).replace(",", ".")
    return res


def analyser_speedtest_pdf(texte: str):
    down, up = 0.0, 0.0
    if not texte:
        return down, up
    t = texte.lower()
    md = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:mbit/s|mbps)?\s*(?:téléchargement|download|descendant|réception)", t)
    if not md:
        md = re.search(r"(?:téléchargement|download|descendant|réception)\s*[:\s-]*\s*(\d+(?:[\.,]\d+)?)", t)
    if md: down = float(md.group(1).replace(",", "."))
    mu = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:mbit/s|mbps)?\s*(?:transfert|upload|montant|envoi)", t)
    if not mu:
        mu = re.search(r"(?:transfert|upload|montant|envoi)\s*[:\s-]*\s*(\d+(?:[\.,]\d+)?)", t)
    if mu: up = float(mu.group(1).replace(",", "."))
    return down, up


# ==============================================================================
#  9. MOTEUR DE COMPARAISON & RECOMMANDATIONS
# ==============================================================================
def comparer_offres(univers, categorie, cout_actuel_mensuel, fournisseurs_autorises=None):
    df = lire_offres(univers=univers, categorie=categorie)
    if df.empty:
        return []
    resultats = []
    for _, o in df.iterrows():
        if fournisseurs_autorises and o["fournisseur"] not in fournisseurs_autorises:
            continue
        prix     = float(o["prix_mensuel"] or 0)
        frais    = float(o["frais_activation"] or 0)
        eco_mens = round(cout_actuel_mensuel - prix, 2)
        resultats.append({
            "id": int(o["id"]), "nom": o["nom_offre"], "fournisseur": o["fournisseur"],
            "categorie": categorie, "univers": univers,
            "prix_mensuel": prix, "frais_activation": frais,
            "engagement": int(o["engagement_mois"] or 0),
            "caracteristiques": o["caracteristiques"] or "",
            "commission": float(o["commission_affiliation"] or 0),
            "economie_mensuelle": eco_mens, "economie_annuelle": round(eco_mens * 12, 2),
            "cout_1_an": round(prix * 12 + frais, 2),
        })
    resultats.sort(key=lambda x: x["economie_annuelle"], reverse=True)
    return resultats


def construire_recommandations(service_principal, cout_tel, fournisseurs_autorises=None):
    f   = fournisseurs_autorises
    top = lambda cat: comparer_offres("Télécom", cat, cout_tel, f)[:3]

    if service_principal == "Mobile uniquement":
        principal = ("📱 Vos meilleures offres Mobile", top("Mobile"))
        cross     = [("🏠 Et si vous regardiez aussi la Box / Fibre ?", top("Box / Fibre")),
                     ("📦 Nos packs Box + Mobile (pour aller plus loin)", top("Pack Box + Mobile"))]
    elif service_principal == "Box / Fibre uniquement":
        principal = ("🏠 Vos meilleures offres Box / Fibre", top("Box / Fibre"))
        cross     = [("📦 Top 3 de nos packs Box + Mobile", top("Pack Box + Mobile")),
                     ("📱 Nos 3 meilleurs forfaits Mobile", top("Mobile"))]
    elif service_principal == "Pack Box + Mobile":
        principal = ("📦 Vos meilleurs packs Box + Mobile", top("Pack Box + Mobile"))
        cross     = [("📱 Nos 3 meilleurs forfaits Mobile", top("Mobile")),
                     ("🏠 Nos 3 meilleures offres Box / Fibre", top("Box / Fibre"))]
    else:
        ml        = top("Multi-lignes") or top("Mobile")
        principal = ("📲 Vos meilleures offres Multi-lignes", ml)
        cross     = [("📦 Top 3 de nos packs Box + Mobile", top("Pack Box + Mobile")),
                     ("🏠 Nos 3 meilleures offres Box / Fibre", top("Box / Fibre"))]

    return {"principal": principal, "cross_sell": cross}


# ==============================================================================
#  10. GÉNÉRATION PDF DE RESTITUTION
# ==============================================================================
COULEUR_PRIMAIRE   = (26, 60, 110)
COULEUR_ACCENT     = (0, 150, 80)
COULEUR_GRIS       = (110, 110, 110)
COULEUR_FOND_CARTE = (244, 247, 251)


def _pdf_txt(txt):
    if txt is None:
        return ""
    rep = {"€":"EUR","'":"'","–":"-","—":"-","•":"-","œ":"oe",
           "🎯":"","📱":"","🏠":"","📦":"","📲":"","⚡":"","🎬":"",
           "😀":"","😐":"","😡":"","💰":"","💶":""}
    s = str(txt)
    for k, v in rep.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "ignore").decode("latin-1")


class PDFPro(FPDF):
    def __init__(self, nom_societe="IA CONSEIL"):
        super().__init__()
        self.nom_societe = nom_societe

    def header(self):
        self.set_fill_color(*COULEUR_PRIMAIRE)
        self.rect(0, 0, 210, 26, "F")
        self.set_y(7)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, _pdf_txt(self.nom_societe), ln=False)
        self.set_font("Helvetica", "", 10)
        self.set_xy(0, 10)
        self.cell(200, 8, _pdf_txt("Bilan d'economies personnalise   "), align="R")
        self.set_text_color(0, 0, 0)
        self.set_y(34)

    def footer(self):
        self.set_y(-18)
        self.set_draw_color(*COULEUR_PRIMAIRE)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*COULEUR_GRIS)
        self.multi_cell(0, 4, _pdf_txt(
            f"{self.nom_societe} - Document genere le {datetime.now().strftime('%d/%m/%Y')}. "
            "Estimations indicatives basees sur les informations communiquees et les offres "
            "disponibles a ce jour. Sans valeur contractuelle."), align="C")
        self.set_text_color(0, 0, 0)
        self.set_y(-10)
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")


def _carte_offre(pdf, titre_section, offre, cout_actuel):
    y0 = pdf.get_y()
    if y0 > 245:
        pdf.add_page(); y0 = pdf.get_y()
    pdf.set_fill_color(*COULEUR_FOND_CARTE)
    pdf.set_draw_color(220, 226, 235)
    pdf.rect(10, y0, 190, 34, "DF")
    pdf.set_xy(13, y0 + 2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*COULEUR_PRIMAIRE)
    pdf.cell(120, 6, _pdf_txt(titre_section), ln=True)
    pdf.set_xy(13, y0 + 9)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(120, 6, _pdf_txt(f"{offre.get('nom','')}"), ln=False)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.set_xy(13, y0 + 15)
    pdf.cell(120, 5, _pdf_txt(f"{offre.get('fournisseur','')}  -  {offre.get('caracteristiques','')[:70]}"), ln=False)
    pdf.set_xy(13, y0 + 22)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(120, 5, _pdf_txt(
        f"Avant : {cout_actuel} EUR/mois   ->   Apres : {offre.get('prix_mensuel',0)} EUR/mois"), ln=False)
    eco_an = offre.get("economie_annuelle", 0) or 0
    pdf.set_fill_color(*COULEUR_ACCENT)
    pdf.rect(150, y0 + 6, 47, 22, "F")
    pdf.set_xy(150, y0 + 9)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(47, 4, _pdf_txt("Economie estimee"), align="C", ln=True)
    pdf.set_x(150)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(47, 8, _pdf_txt(f"{eco_an} EUR"), align="C", ln=True)
    pdf.set_x(150)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(47, 4, _pdf_txt("par an"), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + 38)


def generer_pdf_restitution(client, recommandations, nom_societe="IA CONSEIL"):
    if not FPDF_OK:
        return None
    pdf = PDFPro(nom_societe)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    nom_complet = f"{client.get('prenom','')} {client.get('nom','')}".strip()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*COULEUR_PRIMAIRE)
    pdf.cell(0, 9, _pdf_txt(f"Etude preparee pour {nom_complet}"), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COULEUR_GRIS)
    ligne_loc = []
    if client.get("ville"):     ligne_loc.append(f"{client.get('ville')} ({client.get('code_postal','')})")
    if client.get("telephone"): ligne_loc.append(f"Tel : {client.get('telephone')}")
    if client.get("email"):     ligne_loc.append(client.get("email"))
    pdf.cell(0, 6, _pdf_txt("  -  ".join(ligne_loc)), ln=True)
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _pdf_txt(
        "Voici la synthese des offres que nous avons selectionnees pour votre situation, "
        "avec les economies estimees sur 12 mois. Notre equipe s'occupe de toutes les demarches."))
    pdf.ln(3)
    total_eco_an = 0.0
    for r in recommandations:
        offre = r.get("offre", {})
        total_eco_an += offre.get("economie_annuelle", 0) or 0
        _carte_offre(pdf, f"{r.get('univers','')} - {r.get('categorie','')}", offre, r.get("cout_actuel", 0))
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.ln(2)
    y = pdf.get_y()
    pdf.set_fill_color(*COULEUR_ACCENT)
    pdf.rect(10, y, 190, 18, "F")
    pdf.set_xy(10, y + 4)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 10, _pdf_txt(f"ECONOMIE TOTALE ESTIMEE : {round(total_eco_an,2)} EUR / AN"), align="C")
    pdf.set_text_color(0, 0, 0)
    return bytes(pdf.output())


# ==============================================================================
#  11. EMAIL
# ==============================================================================
def envoyer_email(destinataire, sujet, corps_html, pdf_bytes=None, nom_pdf="bilan.pdf"):
    cfg      = st.session_state.get("smtp_config", {})
    serveur  = cfg.get("serveur", "")
    port     = int(cfg.get("port", 587))
    user     = cfg.get("user", "")
    mdp      = cfg.get("mdp", "")
    expediteur = cfg.get("expediteur", user)
    if not (serveur and user and mdp):
        return False, "Configuration SMTP incomplète (voir Admin > Paramètres email)."
    try:
        msg = MIMEMultipart()
        msg["From"], msg["To"], msg["Subject"] = expediteur, destinataire, sujet
        msg.attach(MIMEText(corps_html, "html", "utf-8"))
        if pdf_bytes:
            piece = MIMEApplication(pdf_bytes, _subtype="pdf")
            piece.add_header("Content-Disposition", "attachment", filename=nom_pdf)
            msg.attach(piece)
        with smtplib.SMTP(serveur, port, timeout=15) as s:
            s.starttls(); s.login(user, mdp); s.send_message(msg)
        return True, "Email envoyé avec succès."
    except Exception as e:
        return False, f"Échec de l'envoi : {e}"


def construire_corps_email(client, recommandations, total_eco_an):
    nom   = client.get("prenom", "")
    lignes = ""
    for r in recommandations:
        o = r.get("offre", {})
        lignes += f"""<tr>
          <td style="padding:10px;border-bottom:1px solid #eee;">
            <b>{r.get('univers','')} – {r.get('categorie','')}</b></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">
            {o.get('nom','')}<br>
            <span style="color:#888;font-size:12px;">{o.get('fournisseur','')}</span></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{o.get('prix_mensuel',0)} €/mois</td>
          <td style="padding:10px;border-bottom:1px solid #eee;color:#009650;">
            <b>+{o.get('economie_annuelle',0)} €/an</b></td>
        </tr>"""
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:660px;margin:auto;
                border:1px solid #eee;border-radius:8px;overflow:hidden;">
      <div style="background:#1a3c6e;color:#fff;padding:24px;">
        <h1 style="margin:0;font-size:22px;">Votre bilan d'économies</h1>
        <p style="margin:6px 0 0;opacity:.85;">Préparé spécialement pour vous</p>
      </div>
      <div style="padding:24px;">
        <p style="font-size:15px;">Bonjour {nom},</p>
        <p>Suite à notre échange, voici les offres que nous avons sélectionnées :</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <thead><tr style="background:#f4f7fb;text-align:left;">
            <th style="padding:10px;">Univers</th><th style="padding:10px;">Offre</th>
            <th style="padding:10px;">Tarif</th><th style="padding:10px;">Économie</th>
          </tr></thead>
          <tbody>{lignes}</tbody>
        </table>
        <div style="background:#009650;color:#fff;padding:16px;border-radius:6px;
                    text-align:center;margin-top:20px;font-size:18px;">
          <b>Économie totale estimée : {round(total_eco_an,2)} € / an</b>
        </div>
        <p style="margin-top:20px;">Le détail complet est en pièce jointe.
           Nous nous occupons de toutes les démarches de changement.</p>
        <p style="color:#aaa;font-size:11px;margin-top:24px;">
          Estimations indicatives, sans valeur contractuelle.</p>
      </div>
    </div>"""


# ==============================================================================
#  12. SESSION STATE & VALEURS PAR DÉFAUT
# ==============================================================================
DEFAUTS = {
    # Authentification (NOUVEAU Étape 1)
    "auth_logged_in":   False,
    "auth_user_id":     None,
    "auth_username":    "",
    "auth_nom_complet": "",
    "auth_role":        "Lecture",
    # Navigation
    "menu": "📊 Tableau de bord",
    # Config
    "smtp_config": {"serveur": "", "port": 587, "user": "", "mdp": "", "expediteur": ""},
    "nom_societe": "IA CONSEIL",
    # Wizard diagnostic
    "w_etape": 1,
    "w_univers": ["Télécom"],
    "w_service_principal": "Mobile uniquement",
    "w_type_client": "Particulier",
    "w_prenom": "", "w_nom": "", "w_tel": "", "w_email": "", "w_cp": "", "w_ville": "",
    "w_tel_operateur": "Autre / Aucun", "w_tel_cout": 0.0, "w_tel_data": "50",
    "w_tel_techno": "FIBRE", "w_tel_offre": "", "w_tel_debit": DEBITS_OPTIONS[0],
    "w_sat_reseau": SATISFACTION_RESEAU[0], "w_veut_rester": False,
    "w_speed_down": 0.0, "w_speed_up": 0.0,
    "w_lignes_multi": [],
    "w_ener_fournisseur": "Autre / Aucun", "w_ener_cout_elec": 0.0, "w_ener_cout_gaz": 0.0,
    "w_abos": [],
    "facture_data": {},
}
for k, v in DEFAUTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def peut_modifier() -> bool:
    return st.session_state.get("auth_role") in ("Conseiller", "Admin")


def est_admin() -> bool:
    return st.session_state.get("auth_role") == "Admin"


# ==============================================================================
#  13. BARRE LATÉRALE — LOGIN NOMINATIF
# ==============================================================================
with st.sidebar:
    st.title("📡 IA Conseil")
    st.caption("CRM Intégral Pro — usage interne")

    if not st.session_state.auth_logged_in:
        # ---- Formulaire de connexion ----
        st.markdown("### 🔐 Connexion")
        login_u = st.text_input("Identifiant", key="sidebar_username")
        login_p = st.text_input("Mot de passe", type="password", key="sidebar_password")
        if st.button("Se connecter", type="primary", use_container_width=True):
            user = authentifier_utilisateur(login_u, login_p)
            if user:
                st.session_state.auth_logged_in   = True
                st.session_state.auth_user_id     = user["id"]
                st.session_state.auth_username    = user["username"]
                st.session_state.auth_nom_complet = user["nom_complet"]
                st.session_state.auth_role        = user["role"]
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")
    else:
        # ---- Utilisateur connecté ----
        st.markdown(f"**👤 {st.session_state.auth_nom_complet}**")
        st.caption(f"Rôle : {st.session_state.auth_role}")
        if st.button("🚪 Se déconnecter", use_container_width=True):
            for k in ["auth_logged_in","auth_user_id","auth_username","auth_nom_complet","auth_role"]:
                st.session_state[k] = DEFAUTS[k]
            st.session_state.menu = "📊 Tableau de bord"
            st.rerun()

        st.divider()
        options_menu = ["📊 Tableau de bord", "🧭 Nouveau diagnostic",
                        "📇 Prospects", "👥 Clients & contrats", "🛠️ Admin"]
        st.session_state.menu = st.radio(
            "Navigation", options_menu,
            index=options_menu.index(st.session_state.menu)
                  if st.session_state.menu in options_menu else 0
        )
        st.divider()
        df_p = lire_prospects(); df_c = lire_clients()
        moi  = st.session_state.auth_nom_complet
        mes_p = df_p[df_p["cree_par"] == moi] if not df_p.empty and "cree_par" in df_p.columns else df_p
        st.metric("Mes prospects", len(mes_p))
        a_relancer = len(mes_p[mes_p["statut"] == "À relancer"]) if not mes_p.empty and "statut" in mes_p.columns else 0
        st.metric("À relancer", a_relancer, delta="⚠️" if a_relancer > 0 else "✅ 0")
        mes_c = df_c[df_c["cree_par"] == moi] if not df_c.empty and "cree_par" in df_c.columns else df_c
        st.metric("Mes clients", len(mes_c))


# ==============================================================================
#  GARDE : tout le reste nécessite d'être connecté
# ==============================================================================
if not st.session_state.auth_logged_in:
    st.title("🔐 Connexion requise")
    st.info("Veuillez vous identifier via le panneau à gauche.")
    if _admin_cree:
        st.warning(
            "**Premier lancement détecté.** Un compte administrateur a été créé automatiquement :\n\n"
            "- Identifiant : `admin`\n"
            "- Mot de passe : `Admin2026!`\n\n"
            "⚠️ Changez ce mot de passe immédiatement dans **Admin > Utilisateurs** après connexion."
        )
    st.stop()

menu = st.session_state.menu


# ==============================================================================
#  14. NOUVEAU DIAGNOSTIC
# ==============================================================================
if menu == "🧭 Nouveau diagnostic":
    st.title("🧭 Diagnostic client guidé")
    barre = st.progress(0)

    # ---------- ÉTAPE 1 ----------
    if st.session_state.w_etape == 1:
        barre.progress(0.15)
        st.subheader("Étape 1 — Besoins + import de documents")
        st.session_state.w_univers = st.multiselect(
            "Univers à analyser :", UNIVERS, default=st.session_state.w_univers)

        if "Télécom" in st.session_state.w_univers:
            st.session_state.w_service_principal = st.radio(
                "Service principal recherché :", SERVICE_PRINCIPAL,
                index=SERVICE_PRINCIPAL.index(st.session_state.w_service_principal),
                horizontal=True)

        st.markdown("##### 📄 Facture PDF (optionnel — pré-remplit la fiche)")
        pdf_f = st.file_uploader("Facture Télécom ou Énergie", type=["pdf"], key="pdf_facture")
        if pdf_f is not None:
            data = analyser_facture(lire_pdf(pdf_f))
            st.session_state.facture_data = data
            for src, dst in [("prenom","w_prenom"),("nom","w_nom"),("tel","w_tel"),
                             ("email","w_email"),("cp","w_cp"),("ville","w_ville")]:
                if data[src]: st.session_state[dst] = data[src]
            if data["operateur"] != "Autre / Aucun": st.session_state.w_tel_operateur = data["operateur"]
            if data["fournisseur"] != "Autre / Aucun": st.session_state.w_ener_fournisseur = data["fournisseur"]
            if data["prix"] > 0: st.session_state.w_tel_cout = data["prix"]
            if data["data_go"]: st.session_state.w_tel_data = data["data_go"]
            st.success("Facture analysée — champs pré-remplis.")

        st.markdown("##### 📶 Speedtest PDF (optionnel)")
        pdf_s = st.file_uploader("PDF de test de débit (nPerf, Speedtest…)", type=["pdf"], key="pdf_speed")
        if pdf_s is not None:
            d, u = analyser_speedtest_pdf(lire_pdf(pdf_s))
            if d: st.session_state.w_speed_down = d
            if u: st.session_state.w_speed_up   = u
            st.success(f"Débits détectés — ⬇️ {d} Mbps / ⬆️ {u} Mbps")

        if st.button("Commencer ➡️", type="primary"):
            if not st.session_state.w_univers:
                st.warning("Cochez au moins un univers.")
            else:
                st.session_state.w_etape = 2; st.rerun()

    # ---------- ÉTAPE 2 : identité ----------
    elif st.session_state.w_etape == 2:
        barre.progress(0.30)
        st.subheader("Étape 2 — Coordonnées du client")
        st.session_state.w_type_client = st.radio(
            "Type :", ["Particulier", "Professionnel"], horizontal=True,
            index=0 if st.session_state.w_type_client == "Particulier" else 1)
        c1, c2 = st.columns(2)
        st.session_state.w_prenom = c1.text_input("Prénom", st.session_state.w_prenom)
        st.session_state.w_nom    = c2.text_input("Nom",    st.session_state.w_nom)
        st.session_state.w_tel    = c1.text_input("Téléphone", st.session_state.w_tel)
        st.session_state.w_email  = c2.text_input("Email",     st.session_state.w_email)
        st.session_state.w_cp     = c1.text_input("Code postal", st.session_state.w_cp)
        st.session_state.w_ville  = c2.text_input("Ville",       st.session_state.w_ville)
        # Validation en temps réel (non bloquante, juste indicative)
        if st.session_state.w_email and not valider_email(st.session_state.w_email):
            st.warning("⚠️ Format email invalide — vérifiez avant de continuer.")
        if st.session_state.w_tel and not valider_telephone(st.session_state.w_tel):
            st.warning("⚠️ Numéro de téléphone inhabituel — vérifiez.")

        a, b = st.columns(2)
        if a.button("⬅️ Retour"):    st.session_state.w_etape = 1; st.rerun()
        if b.button("Suivant ➡️", type="primary"): st.session_state.w_etape = 3; st.rerun()

    # ---------- ÉTAPE 3 : situation actuelle ----------
    elif st.session_state.w_etape == 3:
        barre.progress(0.55)
        st.subheader("Étape 3 — Situation actuelle du client")

        if "Télécom" in st.session_state.w_univers:
            with st.container(border=True):
                st.markdown("#### 📱 Télécom")
                box_seule = st.session_state.w_service_principal == "Box / Fibre uniquement"
                c1, c2 = st.columns(2)
                st.session_state.w_tel_operateur = c1.selectbox(
                    "Opérateur actuel", LISTE_OPERATEURS_TEL,
                    index=LISTE_OPERATEURS_TEL.index(st.session_state.w_tel_operateur)
                          if st.session_state.w_tel_operateur in LISTE_OPERATEURS_TEL
                          else len(LISTE_OPERATEURS_TEL)-1)
                st.session_state.w_tel_techno = c2.selectbox(
                    "Technologie", LISTE_TECHNO,
                    index=LISTE_TECHNO.index(st.session_state.w_tel_techno)
                          if st.session_state.w_tel_techno in LISTE_TECHNO else 0)
                st.session_state.w_tel_offre = c1.text_input("Offre / forfait actuel", st.session_state.w_tel_offre)
                st.session_state.w_tel_cout  = c2.number_input(
                    "Coût mensuel actuel (€)", min_value=0.0,
                    value=float(st.session_state.w_tel_cout), step=1.0)

                if box_seule or st.session_state.w_tel_techno in ("FIBRE","ADSL"):
                    st.session_state.w_tel_debit = c1.selectbox(
                        "Bande passante souhaitée", DEBITS_OPTIONS,
                        index=DEBITS_OPTIONS.index(st.session_state.w_tel_debit)
                              if st.session_state.w_tel_debit in DEBITS_OPTIONS else 0)
                else:
                    st.session_state.w_tel_data = c1.text_input("Data mobile (Go)", str(st.session_state.w_tel_data))

                cc1, cc2 = st.columns(2)
                st.session_state.w_sat_reseau = cc1.selectbox(
                    "Satisfaction réseau", SATISFACTION_RESEAU,
                    index=SATISFACTION_RESEAU.index(st.session_state.w_sat_reseau)
                          if st.session_state.w_sat_reseau in SATISFACTION_RESEAU else 0)
                st.session_state.w_veut_rester = cc2.checkbox(
                    "⚠️ Veut rester chez son opérateur actuel",
                    value=st.session_state.w_veut_rester)

                d1, d2 = st.columns(2)
                st.session_state.w_speed_down = d1.number_input(
                    "Débit descendant (Mbps)", min_value=0.0,
                    value=float(st.session_state.w_speed_down), step=1.0)
                st.session_state.w_speed_up = d2.number_input(
                    "Débit montant (Mbps)", min_value=0.0,
                    value=float(st.session_state.w_speed_up), step=1.0)
                if st.session_state.w_speed_down or st.session_state.w_speed_up:
                    st.caption(f"📶 Mesurés : ⬇️ {st.session_state.w_speed_down} Mbps  /  ⬆️ {st.session_state.w_speed_up} Mbps")

                st.markdown("**Lignes supplémentaires (multi-lignes) :**")
                m1, m2, m3 = st.columns(3)
                ml_label = m1.text_input("Libellé (ex: Ligne épouse)", key="ml_label")
                ml_op    = m2.selectbox("Opérateur", LISTE_OPERATEURS_TEL, key="ml_op")
                ml_techno = m3.selectbox("Techno", LISTE_TECHNO, key="ml_techno")
                m4, m5, m6 = st.columns(3)
                ml_data = m4.text_input("Data nécessaire (Go)", key="ml_data")
                ml_sat  = m5.selectbox("Satisfaction", SATISFACTION_RESEAU, key="ml_sat")
                ml_cout = m6.number_input("€/mois", min_value=0.0, step=1.0, key="ml_cout")
                if st.button("➕ Ajouter la ligne"):
                    if ml_label:
                        st.session_state.w_lignes_multi.append({
                            "label": ml_label, "operateur": ml_op, "techno": ml_techno,
                            "data": ml_data, "satisfaction": ml_sat, "cout": ml_cout})
                        st.rerun()
                if st.session_state.w_lignes_multi:
                    total_multi = sum(l["cout"] for l in st.session_state.w_lignes_multi)
                    for i, l in enumerate(st.session_state.w_lignes_multi):
                        cx, cy = st.columns([5, 1])
                        cx.write(f"• **{l['label']}** — {l['operateur']} / {l['techno']} / {l['data']} Go / {l['satisfaction']} — {l['cout']} €/mois")
                        if cy.button("🗑️", key=f"del_ml_{i}"):
                            st.session_state.w_lignes_multi.pop(i); st.rerun()
                    st.info(f"Total multi-lignes : **{round(total_multi,2)} €/mois** ({round(total_multi*12,2)} €/an)")

        if "Énergie" in st.session_state.w_univers:
            with st.container(border=True):
                st.markdown("#### ⚡ Énergie")
                e1, e2, e3 = st.columns(3)
                st.session_state.w_ener_fournisseur = e1.selectbox(
                    "Fournisseur actuel", LISTE_FOURNISSEURS_ENERGIE,
                    index=LISTE_FOURNISSEURS_ENERGIE.index(st.session_state.w_ener_fournisseur)
                          if st.session_state.w_ener_fournisseur in LISTE_FOURNISSEURS_ENERGIE
                          else len(LISTE_FOURNISSEURS_ENERGIE)-1)
                st.session_state.w_ener_cout_elec = e2.number_input(
                    "Élec — €/mois", min_value=0.0, value=float(st.session_state.w_ener_cout_elec), step=1.0)
                st.session_state.w_ener_cout_gaz = e3.number_input(
                    "Gaz — €/mois", min_value=0.0, value=float(st.session_state.w_ener_cout_gaz), step=1.0)

        if "Abonnements" in st.session_state.w_univers:
            with st.container(border=True):
                st.markdown("#### 🎬 Abonnements")
                a1, a2, a3 = st.columns([2, 1, 1])
                abo_nom  = a1.text_input("Nom de l'abonnement", key="abo_nom")
                abo_cout = a2.number_input("€/mois", min_value=0.0, step=1.0, key="abo_cout")
                if a3.button("➕ Ajouter l'abo"):
                    if abo_nom:
                        st.session_state.w_abos.append({"nom": abo_nom, "cout": abo_cout}); st.rerun()
                if st.session_state.w_abos:
                    total_abo = sum(a["cout"] for a in st.session_state.w_abos)
                    for i, a in enumerate(st.session_state.w_abos):
                        cx, cy = st.columns([5, 1])
                        cx.write(f"• {a['nom']} — {a['cout']} €/mois")
                        if cy.button("🗑️", key=f"del_abo_{i}"):
                            st.session_state.w_abos.pop(i); st.rerun()
                    st.info(f"Total abonnements : **{round(total_abo,2)} €/mois** ({round(total_abo*12,2)} €/an)")

        a, b = st.columns(2)
        if a.button("⬅️ Retour"): st.session_state.w_etape = 2; st.rerun()
        if b.button("🔍 Lancer la comparaison ➡️", type="primary"):
            with st.spinner("Analyse en cours…"):
                st.session_state.w_etape = 4
            st.rerun()

    # ---------- ÉTAPE 4 : RECOMMANDATIONS ----------
    elif st.session_state.w_etape == 4:
        barre.progress(1.0)
        nom_complet = f"{st.session_state.w_prenom} {st.session_state.w_nom}".strip() or "Client"
        st.subheader(f"🎯 Recommandations pour {nom_complet}")

        if st.session_state.w_veut_rester:
            st.warning(f"⚠️ Le client souhaite rester chez **{st.session_state.w_tel_operateur}** — adaptez votre argumentaire.")

        recommandations = []

        # ----- TÉLÉCOM -----
        if "Télécom" in st.session_state.w_univers:
            cout_tel = float(st.session_state.w_tel_cout) + sum(l["cout"] for l in st.session_state.w_lignes_multi)
            st.caption(f"Coût télécom actuel pris en compte : **{round(cout_tel,2)} €/mois**")
            reco = construire_recommandations(st.session_state.w_service_principal, cout_tel)

            titre_p, offres_p = reco["principal"]
            st.markdown(f"### {titre_p}")
            if not offres_p:
                st.info("Aucune offre dans cette catégorie au catalogue. Ajoutez-en dans 🛠️ Admin.")
            for o in offres_p:
                with st.container(border=True):
                    a, b, c = st.columns([3, 2, 1])
                    a.markdown(f"##### {o['nom']}")
                    a.caption(f"{o['fournisseur']} · {o['caracteristiques']}")
                    b.write(f"💶 **{o['prix_mensuel']} €/mois**")
                    b.caption(f"Coût 1ère année : {o['cout_1_an']} €")
                    c.metric("Économie/an", f"{o['economie_annuelle']} €")
            if offres_p:
                recommandations.append({
                    "univers": "Télécom", "categorie": titre_p.strip("📱🏠📦📲 "),
                    "cout_actuel": round(cout_tel, 2), "offre": offres_p[0]})

            st.markdown("---")
            st.markdown("#### 💡 Pour aller plus loin (à proposer au client)")
            for titre_cs, offres_cs in reco["cross_sell"]:
                if offres_cs:
                    with st.expander(f"{titre_cs}  —  à partir de {offres_cs[0]['prix_mensuel']} €/mois"):
                        for o in offres_cs:
                            cca, ccb = st.columns([4, 1])
                            cca.write(f"**{o['nom']}** — {o['fournisseur']}  ·  {o['caracteristiques']}")
                            ccb.write(f"**{o['prix_mensuel']} €/mois**")

        # ----- ÉNERGIE -----
        if "Énergie" in st.session_state.w_univers:
            st.markdown("### ⚡ Énergie")
            for cat, cout in [("Électricité", st.session_state.w_ener_cout_elec),
                              ("Gaz",          st.session_state.w_ener_cout_gaz)]:
                if cout > 0:
                    offres = comparer_offres("Énergie", cat, float(cout)) or \
                             comparer_offres("Énergie", cat + " Pro", float(cout))
                    if offres:
                        st.markdown(f"**{cat}** — actuel : {cout} €/mois")
                        for o in offres[:3]:
                            with st.container(border=True):
                                a, b, c = st.columns([3, 2, 1])
                                a.markdown(f"##### {o['nom']}")
                                a.caption(f"{o['fournisseur']} · {o['caracteristiques']}")
                                b.write(f"💶 {o['prix_mensuel']} €/mois")
                                c.metric("Économie/an", f"{o['economie_annuelle']} €")
                        recommandations.append({
                            "univers": "Énergie", "categorie": cat,
                            "cout_actuel": float(cout), "offre": offres[0]})
                    else:
                        st.info(f"Aucune offre {cat} au catalogue.")

        # ----- ABONNEMENTS -----
        if "Abonnements" in st.session_state.w_univers and st.session_state.w_abos:
            st.markdown("### 🎬 Abonnements")
            for a in st.session_state.w_abos:
                cout_abo = safe_float(a["cout"])
                offres   = comparer_offres("Abonnements", None, cout_abo)
                # Ne proposer que des alternatives moins chères ET du même type (approximation par catégorie)
                alt = [o for o in offres if safe_float(o["prix_mensuel"]) < cout_abo]
                st.markdown(f"**{a['nom']}** — actuel : {cout_abo} €/mois")
                if alt:
                    o = alt[0]
                    eco_reelle_an = round((cout_abo - safe_float(o["prix_mensuel"])) * 12, 2)
                    # On corrige economie_annuelle avec le vrai coût client
                    o = {**o, "economie_annuelle": eco_reelle_an}
                    with st.container(border=True):
                        x, y, z = st.columns([3, 2, 1])
                        x.markdown(f"##### {o['nom']}")
                        x.caption(f"{o['fournisseur']} · {o['caracteristiques']}")
                        y.write(f"💶 {o['prix_mensuel']} €/mois")
                        z.metric("Économie/an", f"{eco_reelle_an} €")
                    recommandations.append({
                        "univers": "Abonnements", "categorie": a["nom"],
                        "cout_actuel": cout_abo, "offre": o})
                else:
                    st.caption("Pas d'alternative moins chère au catalogue.")

        # ----- SYNTHÈSE -----
        total_eco = sum((r["offre"].get("economie_annuelle", 0) or 0) for r in recommandations)
        st.divider()
        if total_eco > 0:
            st.success(f"### 💰 Économie totale estimée : {round(total_eco,2)} € / an")
        else:
            st.info("Aucune économie chiffrée — vérifiez votre catalogue.")

        # ----- DICT CLIENT -----
        infos_client = {
            "ref":                  generer_ref(),
            "prenom":               st.session_state.w_prenom,
            "nom":                  st.session_state.w_nom,
            "telephone":            st.session_state.w_tel,
            "email":                st.session_state.w_email,
            "code_postal":          st.session_state.w_cp,
            "ville":                st.session_state.w_ville,
            "type_client":          st.session_state.w_type_client,
            "univers_interesse":    ", ".join(st.session_state.w_univers),
            "service_principal":    st.session_state.w_service_principal,
            "operateur_actuel":     st.session_state.w_tel_operateur,
            "techno":               st.session_state.w_tel_techno,
            "data_go":              st.session_state.w_tel_data,
            "offre_actuelle":       st.session_state.w_tel_offre,
            "cout_mensuel_actuel":  safe_float(st.session_state.w_tel_cout),
            "satisfaction_reseau":  st.session_state.w_sat_reseau,
            "veut_rester":          "Oui" if st.session_state.w_veut_rester else "Non",
            "speed_down":           safe_float(st.session_state.w_speed_down),
            "speed_up":             safe_float(st.session_state.w_speed_up),
            "cout_elec":            safe_float(st.session_state.w_ener_cout_elec),
            "cout_gaz":             safe_float(st.session_state.w_ener_cout_gaz),
            "fournisseur_energie":  st.session_state.w_ener_fournisseur,
            "abonnements":          json.dumps(st.session_state.w_abos, ensure_ascii=False),
            "lignes_multi":         json.dumps(st.session_state.w_lignes_multi, ensure_ascii=False),
            "economie_estimee_an":  round(total_eco, 2),
            "notes":                (f"Satisfaction réseau : {st.session_state.w_sat_reseau}. "
                                     f"Veut rester : {'Oui' if st.session_state.w_veut_rester else 'Non'}."),
            "cree_par":             st.session_state.auth_nom_complet,  # ← TRAÇABILITÉ
        }

        # ----- RESTITUTION -----
        st.divider()
        st.markdown("#### 📤 Restitution & suivi")
        pdf_bytes = None
        if recommandations:
            with st.spinner("Génération du PDF…"):
                pdf_bytes = generer_pdf_restitution(
                    infos_client, recommandations, st.session_state.nom_societe)

        col1, col2, col3, col4 = st.columns(4)
        if pdf_bytes:
            col1.download_button("📄 Télécharger le PDF", data=pdf_bytes,
                                 file_name=f"bilan_{nom_complet.replace(' ','_')}.pdf",
                                 mime="application/pdf")
        elif not FPDF_OK:
            col1.caption("PDF indispo (pip install fpdf2)")

        if col2.button("📧 Envoyer au client"):
            if not st.session_state.w_email:
                st.warning("Pas d'email client.")
            elif not recommandations:
                st.warning("Aucune recommandation.")
            else:
                corps = construire_corps_email(infos_client, recommandations, total_eco)
                ok, msg = envoyer_email(
                    st.session_state.w_email,
                    "Votre bilan d'économies personnalisé",
                    corps, pdf_bytes,
                    f"bilan_{nom_complet.replace(' ','_')}.pdf")
                (st.success if ok else st.error)(msg)

        if col3.button("📇 Enregistrer prospect"):
            if not peut_modifier():
                st.error("🔒 Action réservée aux conseillers et admins.")
            else:
                # Enrichissement auto des notes
                infos_client["notes"] = (
                    f"Satisfaction réseau : {st.session_state.w_sat_reseau}. "
                    f"Veut rester : {'Oui' if st.session_state.w_veut_rester else 'Non'}. "
                    f"Économie estimée : {round(total_eco,2)} €/an. "
                    f"Univers : {infos_client['univers_interesse']}."
                )
                ajouter_prospect(infos_client)
                st.success(f"✅ Prospect enregistré — économie estimée {round(total_eco,2)} €/an.")

        if col4.button("✅ Convertir en client", type="primary"):
            if not peut_modifier():
                st.error("🔒 Action réservée aux conseillers et admins.")
            else:
                st.session_state["_infos_client_conv"] = infos_client
                st.session_state["_reco_conv"]         = recommandations
                st.session_state.w_etape = 5
                st.rerun()

        st.divider()
        if st.button("🔄 Nouveau diagnostic (réinitialiser)"):
            for k in list(DEFAUTS.keys()):
                if k.startswith("w_") or k == "facture_data":
                    st.session_state[k] = DEFAUTS[k]
            st.session_state.w_etape = 1; st.rerun()

    # ---------- ÉTAPE 5 : CONFIRMATION CONVERSION CLIENT ----------
    elif st.session_state.w_etape == 5:
        st.subheader("✅ Création du client — validez les offres souscrites")
        infos = st.session_state.get("_infos_client_conv", {})
        recos = st.session_state.get("_reco_conv", [])
        st.write(f"**Client :** {infos.get('prenom','')} {infos.get('nom','')} — {infos.get('ville','')}")
        st.markdown("Cochez et ajustez les contrats réellement souscrits :")

        contrats_a_creer = []
        for i, r in enumerate(recos):
            o = r["offre"]
            with st.container(border=True):
                ch = st.checkbox(
                    f"{r['univers']} – {r['categorie']} : {o['nom']} ({o['fournisseur']})",
                    value=True, key=f"conv_ch_{i}")
                cc1, cc2 = st.columns(2)
                prix = cc1.number_input("Coût mensuel (€)", min_value=0.0,
                                        value=float(o["prix_mensuel"]), step=1.0, key=f"conv_prix_{i}")
                eco  = cc2.number_input("Économie mensuelle (€)", min_value=0.0,
                                        value=float(round(o.get("economie_annuelle",0)/12, 2)),
                                        step=1.0, key=f"conv_eco_{i}")
                if ch:
                    contrats_a_creer.append({
                        "univers": r["univers"], "categorie": r["categorie"],
                        "fournisseur": o["fournisseur"], "nom_offre": o["nom"],
                        "cout_mensuel": prix, "economie_mensuelle": eco,
                        "cree_par": st.session_state.auth_nom_complet,
                    })

        a, b = st.columns(2)
        if a.button("⬅️ Retour aux recommandations"):
            st.session_state.w_etape = 4; st.rerun()
        if b.button("💾 Créer le client + contrats", type="primary"):
            with st.spinner("Enregistrement en cours…"):
                cid = ajouter_client(infos)
                for ct in contrats_a_creer:
                    ajouter_contrat({**ct, "client_id": cid,
                                     "statut_contrat": "En cours d'ouverture",
                                     "notes": "Créé via diagnostic"})
            st.success(f"✅ Client créé avec {len(contrats_a_creer)} contrat(s). Retrouvez-le dans « Clients & contrats ».")
            st.balloons()
            for k in list(DEFAUTS.keys()):
                if k.startswith("w_") or k == "facture_data":
                    st.session_state[k] = DEFAUTS[k]
            st.session_state.w_etape = 1
            st.rerun()   # ← BUG FIX : sans ce rerun la page restait bloquée sur l'étape 5


# ==============================================================================
#  15. TABLEAU DE BORD
# ==============================================================================
elif menu == "📊 Tableau de bord":
    moi  = st.session_state.auth_nom_complet
    role = st.session_state.auth_role
    st.title(f"📊 Tableau de bord — {moi}")

    df_p_all = lire_prospects()
    df_c_all = lire_clients()
    today    = datetime.now().strftime("%d/%m/%Y")

    # Filtrer par conseiller (admin voit tout si souhaité)
    if role == "Admin":
        vue_admin = st.toggle("Vue globale (tous les conseillers)", value=False, key="tdb_global")
    else:
        vue_admin = False

    if vue_admin:
        df_p = df_p_all
        df_c = df_c_all
        st.caption("Mode global — vous voyez les données de toute l'équipe.")
    else:
        df_p = df_p_all[df_p_all["cree_par"] == moi] if not df_p_all.empty and "cree_par" in df_p_all.columns else df_p_all
        df_c = df_c_all[df_c_all["cree_par"] == moi] if not df_c_all.empty and "cree_par" in df_c_all.columns else df_c_all

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    total_prospects  = len(df_p)
    a_relancer       = len(df_p[df_p["statut"] == "À relancer"]) if not df_p.empty and "statut" in df_p.columns else 0
    total_clients    = len(df_c)
    eco_totale       = round(df_c["economie_estimee_an"].sum(), 2) if not df_c.empty and "economie_estimee_an" in df_c.columns else 0.0

    k1.metric("📋 Prospects total",    total_prospects)
    k2.metric("⏰ À relancer",          a_relancer,    delta="urgent" if a_relancer > 3 else None,
              delta_color="inverse" if a_relancer > 3 else "normal")
    k3.metric("✅ Clients signés",      total_clients)
    k4.metric("💰 Économies générées",  f"{eco_totale} €/an")

    st.divider()

    # ── Relances à faire aujourd'hui / en retard ───────────────────────────────
    st.markdown("### ⏰ Relances à traiter")
    if df_p.empty or "statut" not in df_p.columns:
        st.info("Aucun prospect enregistré.")
    else:
        relances = df_p[df_p["statut"].isin(["À relancer", "Relancé"])].copy()
        if relances.empty:
            st.success("✅ Aucune relance en attente — bon travail !")
        else:
            cols_rel = ["prenom","nom","telephone","email","operateur_actuel",
                        "cout_mensuel_actuel","economie_estimee_an","statut","date_relance","cree_par"]
            cols_rel = [c for c in cols_rel if c in relances.columns]
            st.dataframe(
                relances[cols_rel].sort_values("date_relance", ascending=True, na_position="last"),
                hide_index=True, use_container_width=True
            )
            # Actions rapides
            st.markdown("**Action rapide sur un prospect :**")
            ids_rel = relances["id"].tolist()
            sel = st.selectbox("Prospect", ids_rel,
                format_func=lambda i: f"{relances[relances['id']==i]['prenom'].values[0]} {relances[relances['id']==i]['nom'].values[0]} — {relances[relances['id']==i]['telephone'].values[0]}",
                key="tdb_sel_prospect")
            ca, cb, cc = st.columns(3)
            if ca.button("📞 Marqué relancé aujourd'hui", key="tdb_relance"):
                maj_prospect(int(sel), "date_relance", today)
                maj_prospect(int(sel), "statut", "Relancé")
                st.success("Statut mis à jour."); st.rerun()
            if cb.button("✅ Converti en client", key="tdb_convert"):
                p_row = relances[relances["id"] == sel].iloc[0]
                d = {k: p_row.get(k, "") for k in [
                    "ref","prenom","nom","telephone","email","code_postal","ville","type_client",
                    "operateur_actuel","techno","data_go","offre_actuelle","cout_mensuel_actuel",
                    "satisfaction_reseau","veut_rester","speed_down","speed_up",
                    "fournisseur_energie","cout_elec","cout_gaz","economie_estimee_an","notes"]}
                d["cree_par"] = moi
                ajouter_client(d); supprimer_prospect(int(sel))
                st.success("Converti en client !"); st.rerun()
            if cc.button("🗑️ Supprimer", key="tdb_del"):
                supprimer_prospect(int(sel)); st.warning("Supprimé."); st.rerun()

    st.divider()

    # ── Mes derniers clients ───────────────────────────────────────────────────
    st.markdown("### 👥 Derniers clients enregistrés")
    if df_c.empty:
        st.info("Aucun client enregistré.")
    else:
        cols_c = ["prenom","nom","telephone","operateur_actuel","offre_actuelle",
                  "cout_mensuel_actuel","economie_estimee_an","date_creation","cree_par"]
        cols_c = [c for c in cols_c if c in df_c.columns]
        st.dataframe(df_c[cols_c].head(10), hide_index=True, use_container_width=True)

    # ── Vue admin : répartition par conseiller ─────────────────────────────────
    if role == "Admin" and not df_p_all.empty and "cree_par" in df_p_all.columns:
        st.divider()
        st.markdown("### 🏆 Performance par conseiller (Admin)")
        conseillers = df_p_all["cree_par"].dropna().unique().tolist()
        rows = []
        for cons in conseillers:
            p_cons = df_p_all[df_p_all["cree_par"] == cons]
            c_cons = df_c_all[df_c_all["cree_par"] == cons] if not df_c_all.empty and "cree_par" in df_c_all.columns else pd.DataFrame()
            eco = round(c_cons["economie_estimee_an"].sum(), 2) if not c_cons.empty and "economie_estimee_an" in c_cons.columns else 0.0
            rows.append({
                "Conseiller":         cons,
                "Prospects":          len(p_cons),
                "À relancer":         len(p_cons[p_cons["statut"] == "À relancer"]) if "statut" in p_cons.columns else 0,
                "Clients":            len(c_cons),
                "Économie générée €": eco,
            })
        if rows:
            st.dataframe(pd.DataFrame(rows).sort_values("Clients", ascending=False),
                         hide_index=True, use_container_width=True)


# ==============================================================================
#  16-OLD → RENOMMÉ : anciennement section 15
# ==============================================================================
elif menu == "📇 Prospects":
    st.title("📇 Prospects à relancer")
    df = lire_prospects()
    if df.empty:
        st.info("Aucun prospect. Lancez un diagnostic puis « Enregistrer prospect ».")
    else:
        # Filtre par statut
        statuts_dispo = ["Tous"] + sorted(df["statut"].dropna().unique().tolist()) if "statut" in df.columns else ["Tous"]
        col_f1, col_f2 = st.columns([2, 3])
        filtre_statut = col_f1.selectbox("Filtrer par statut", statuts_dispo, key="filtre_statut_prospects")
        col_f2.metric("Total prospects", len(df),
                      delta=f"{len(df[df['statut']=='À relancer'])} à relancer" if 'statut' in df.columns else "")

        dff = df if filtre_statut == "Tous" else df[df["statut"] == filtre_statut]

        cols = ["ref","prenom","nom","telephone","email","ville","univers_interesse",
                "service_principal","operateur_actuel","cout_mensuel_actuel",
                "satisfaction_reseau","veut_rester","economie_estimee_an","statut",
                "cree_par","date_creation","date_relance"]
        cols = [c for c in cols if c in dff.columns]
        st.dataframe(dff[cols], hide_index=True, use_container_width=True)

        st.divider()
        st.markdown("#### Fiche prospect détaillée")
        if dff.empty:
            st.info("Aucun prospect avec ce statut.")
            st.stop()
        choix = st.selectbox("Prospect", dff["id"].tolist(),
            format_func=lambda i: (
                f"{df[df['id']==i]['prenom'].values[0]} "
                f"{df[df['id']==i]['nom'].values[0]} (#{i})"))
        p = df[df["id"] == choix].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Tél :** {p['telephone']}")
        c1.write(f"**Email :** {p['email']}")
        c2.write(f"**Opérateur :** {p['operateur_actuel']}")
        c2.write(f"**Offre actuelle :** {p['offre_actuelle']}")
        c3.write(f"**Satisfaction réseau :** {p['satisfaction_reseau']}")
        c3.write(f"**Veut rester :** {p['veut_rester']}")
        c1.write(f"**Coût actuel :** {p['cout_mensuel_actuel']} €/mois")
        c2.write(f"**Débits :** ⬇️ {p['speed_down']} / ⬆️ {p['speed_up']} Mbps")
        c3.write(f"**Économie estimée :** {p['economie_estimee_an']} €/an")
        if "cree_par" in p and p["cree_par"]:
            st.caption(f"Créé par : **{p['cree_par']}** le {p['date_creation']}")
        if p["lignes_multi"] and p["lignes_multi"] not in ("[]", None):
            with st.expander("Lignes supplémentaires"):
                try:    st.json(json.loads(p["lignes_multi"]))
                except: st.write(p["lignes_multi"])

        if peut_modifier():
            with st.expander("✏️ Modifier ce prospect"):
                champs = {"telephone":"Téléphone","email":"Email","operateur_actuel":"Opérateur",
                          "offre_actuelle":"Offre actuelle","cout_mensuel_actuel":"Coût (€)",
                          "notes":"Notes","statut":"Statut"}
                for champ, label in champs.items():
                    val = st.text_input(label, str(p[champ]), key=f"edit_p_{champ}")
                    if st.button(f"💾 {label}", key=f"btn_p_{champ}"):
                        v = float(val) if champ == "cout_mensuel_actuel" else val
                        maj_prospect(int(choix), champ, v); st.success("Mis à jour."); st.rerun()

            c1, c2, c3 = st.columns(3)
            if c1.button("✅ Convertir en client"):
                d = {k: p[k] for k in p.index if k in (
                    "ref","prenom","nom","telephone","email","code_postal","ville","type_client",
                    "operateur_actuel","techno","data_go","offre_actuelle","cout_mensuel_actuel",
                    "satisfaction_reseau","veut_rester","speed_down","speed_up",
                    "fournisseur_energie","cout_elec","cout_gaz","economie_estimee_an","notes")}
                d["cree_par"] = st.session_state.auth_nom_complet
                ajouter_client(d); supprimer_prospect(int(choix))
                st.success("Converti en client."); st.rerun()
            if c2.button("📞 Marqué relancé aujourd'hui"):
                maj_prospect(int(choix), "date_relance", datetime.now().strftime("%d/%m/%Y"))
                maj_prospect(int(choix), "statut", "Relancé"); st.success("OK."); st.rerun()
            with st.expander("🗑️ Supprimer ce prospect"):
                st.warning(f"Cette action est irréversible. Le prospect **{p.get('prenom','')} {p.get('nom','')}** sera définitivement supprimé.")
                if st.button("✅ Confirmer la suppression", key="confirm_del_prospect"):
                    supprimer_prospect(int(choix)); st.warning("Prospect supprimé."); st.rerun()
        else:
            st.caption("🔒 Rôle Lecture — connexion Conseiller ou Admin requise pour modifier.")


# ==============================================================================
#  17. CLIENTS & CONTRATS
# ==============================================================================
elif menu == "👥 Clients & contrats":
    st.title("👥 Clients & contrats")
    df = lire_clients()
    if df.empty:
        st.info("Aucun client signé.")
    else:
        recherche = st.text_input("🔎 Rechercher (nom, ville, email, réf., opérateur…)")
        dff = df.copy()
        if recherche:
            r   = recherche.lower()
            dff = df[df.apply(lambda row: r in str(row.to_dict()).lower(), axis=1)]

        col_m1, col_m2 = st.columns([3, 1])
        col_m2.metric("Clients trouvés", len(dff))

        cols_aff = ["ref","prenom","nom","telephone","email","ville","operateur_actuel",
                    "offre_actuelle","cout_mensuel_actuel","economie_estimee_an",
                    "cree_par","date_creation"]
        cols_aff = [c for c in cols_aff if c in dff.columns]
        st.dataframe(dff[cols_aff], hide_index=True, use_container_width=True)

        if dff.empty:
            st.info("Aucun client ne correspond à votre recherche.")
        st.divider()
        st.markdown("#### 📂 Fiche client")
        if not dff.empty:
            choix = st.selectbox("Client", dff["id"].tolist(),
                format_func=lambda i: (
                    f"{df[df['id']==i]['prenom'].values[0]} "
                    f"{df[df['id']==i]['nom'].values[0]} (#{i})"))
            cl = df[df["id"] == choix].iloc[0]

            # Accès sécurisé : .get() évite KeyError sur anciennes BDD
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Réf :** {cl.get('ref', '')}")
            c1.write(f"**Tél :** {cl.get('telephone', '')}")
            c1.write(f"**Email :** {cl.get('email', '')}")
            c2.write(f"**Ville :** {cl.get('ville', '')} ({cl.get('code_postal', '')})")
            c2.write(f"**Opérateur :** {cl.get('operateur_actuel', '—')}")
            c2.write(f"**Offre actuelle :** {cl.get('offre_actuelle', '—')}")
            c3.write(f"**Satisfaction réseau :** {cl.get('satisfaction_reseau', '—')}")
            c3.write(f"**Veut rester :** {cl.get('veut_rester', '—')}")
            c3.write(f"**Débits :** ⬇️ {cl.get('speed_down', 0)} / ⬆️ {cl.get('speed_up', 0)} Mbps")
            if cl.get("cree_par"):
                st.caption(f"Créé par : **{cl.get('cree_par')}** le {cl.get('date_creation', '')}")

            if peut_modifier():
                with st.expander("✏️ Modifier les informations du client"):
                    champs = {"telephone":"Téléphone","email":"Email","ville":"Ville",
                              "operateur_actuel":"Opérateur","offre_actuelle":"Offre actuelle",
                              "cout_mensuel_actuel":"Coût actuel (€)","satisfaction_reseau":"Satisfaction réseau",
                              "veut_rester":"Veut rester","notes":"Notes"}
                    for champ, label in champs.items():
                        # .get() avec fallback vide pour les colonnes ajoutées par migration
                        val = st.text_input(label, str(cl.get(champ, "")), key=f"edit_c_{champ}")
                        if st.button(f"💾 {label}", key=f"btn_c_{champ}"):
                            v = float(val) if champ == "cout_mensuel_actuel" else val
                            maj_client(int(choix), champ, v); st.success("Mis à jour."); st.rerun()

            st.markdown("##### 📑 Contrats du client")
            contrats = lire_contrats_client(int(choix))
            if contrats.empty:
                st.info("Aucun contrat rattaché.")
            else:
                cols_ct = ["id","univers","categorie","fournisseur","nom_offre",
                           "cout_mensuel","economie_mensuelle","statut_contrat",
                           "cree_par","date_souscription"]
                cols_ct = [c for c in cols_ct if c in contrats.columns]
                st.dataframe(contrats[cols_ct], hide_index=True, use_container_width=True)
                a, b = st.columns(2)
                a.metric("Total mensuel",    f"{round(contrats['cout_mensuel'].sum(),2)} €")
                b.metric("Économie mensuelle",f"{round(contrats['economie_mensuelle'].sum(),2)} €")

                if peut_modifier():
                    with st.expander("✏️ Modifier / supprimer un contrat"):
                        ctid = st.selectbox("Contrat", contrats["id"].tolist(),
                            format_func=lambda i: f"#{i} · {contrats[contrats['id']==i]['nom_offre'].values[0]}")
                        ct = contrats[contrats["id"] == ctid].iloc[0]
                        nv_offre  = st.text_input("Nom de l'offre", ct["nom_offre"], key="ct_nom")
                        nv_cout   = st.number_input("Coût mensuel (€)", min_value=0.0,
                                                    value=float(ct["cout_mensuel"]), step=1.0, key="ct_cout")
                        nv_statut = st.selectbox("Statut du contrat",
                            ["En cours d'ouverture","Actif","Résilié","En attente"], key="ct_statut")
                        cx, cy = st.columns(2)
                        if cx.button("💾 Enregistrer les modifs"):
                            maj_contrat(int(ctid), "nom_offre",      nv_offre)
                            maj_contrat(int(ctid), "cout_mensuel",   nv_cout)
                            maj_contrat(int(ctid), "statut_contrat", nv_statut)
                            st.success("Contrat mis à jour."); st.rerun()
                        if cy.button("🗑️ Supprimer ce contrat"):
                            supprimer_contrat(int(ctid)); st.warning("Contrat supprimé."); st.rerun()

            if peut_modifier():
                with st.expander("➕ Ajouter un contrat à ce client"):
                    u   = st.selectbox("Univers", UNIVERS, key="add_ctr_u")
                    cat_map = {"Télécom": CATEGORIES_TELECOM, "Énergie": CATEGORIES_ENERGIE,
                               "Abonnements": CATEGORIES_ABO}
                    cat = st.selectbox("Catégorie", cat_map[u], key="add_ctr_c")
                    f   = st.text_input("Fournisseur",   key="add_ctr_f")
                    no  = st.text_input("Nom de l'offre",key="add_ctr_no")
                    cm  = st.number_input("Coût mensuel (€)", min_value=0.0, step=1.0, key="add_ctr_cm")
                    em  = st.number_input("Économie mensuelle (€)", min_value=0.0, step=1.0, key="add_ctr_em")
                    ref_c = st.text_input("Référence contrat", key="add_ctr_ref")
                    if st.button("Ajouter le contrat"):
                        ajouter_contrat({
                            "client_id": int(choix), "univers": u, "categorie": cat,
                            "fournisseur": f, "nom_offre": no, "cout_mensuel": cm,
                            "economie_mensuelle": em, "reference_contrat": ref_c,
                            "statut_contrat": "En cours d'ouverture",
                            "notes": "Ajout manuel",
                            "cree_par": st.session_state.auth_nom_complet,
                        })
                        st.success("Contrat ajouté."); st.rerun()

                with st.expander("🗑️ Supprimer ce client"):
                    st.error(f"⚠️ Supprime **{cl.get('prenom','')} {cl.get('nom','')}** ET tous ses contrats. Irréversible.")
                    if st.button("✅ Confirmer la suppression du client", key="confirm_del_client"):
                        supprimer_client(int(choix)); st.warning("Client et contrats supprimés."); st.rerun()
            else:
                st.caption("🔒 Rôle Lecture — connexion Conseiller ou Admin requise pour modifier.")


# ==============================================================================
#  18. ADMIN
# ==============================================================================
elif menu == "🛠️ Admin":
    st.title("🛠️ Administration")
    if not est_admin():
        st.warning("Accès réservé à l'administrateur.")
        st.stop()

    st.success(f"Mode administrateur — connecté en tant que **{st.session_state.auth_nom_complet}**.")

    tab_users, tab_cat, tab_add, tab_demo, tab_mail = st.tabs(
        ["👤 Utilisateurs", "📚 Catalogue", "➕ Ajouter une offre", "⚡ Pré-remplir (démo)", "📧 Email"])

    # ---- UTILISATEURS (NOUVEAU Étape 1) ----
    with tab_users:
        st.markdown("### Gestion des utilisateurs")
        df_u = lire_utilisateurs()
        if not df_u.empty:
            st.dataframe(df_u, hide_index=True, use_container_width=True)

        st.divider()
        st.markdown("#### ➕ Créer un compte")
        cu1, cu2 = st.columns(2)
        new_login   = cu1.text_input("Identifiant (login)",          key="create_login")
        new_nom     = cu2.text_input("Nom complet",                   key="create_nom")
        new_pwd     = cu1.text_input("Mot de passe",   type="password", key="create_pwd")
        new_pwd2    = cu2.text_input("Confirmer le mot de passe", type="password", key="create_pwd2")
        new_role    = st.selectbox("Rôle", ROLES, index=1, key="create_role")
        if st.button("Créer le compte", type="primary", key="btn_create_user"):
            if not new_login or not new_nom or not new_pwd:
                st.warning("Tous les champs sont obligatoires.")
            elif new_pwd != new_pwd2:
                st.error("Les mots de passe ne correspondent pas.")
            elif len(new_pwd) < 8:
                st.error("Le mot de passe doit contenir au moins 8 caractères.")
            else:
                ok, msg = creer_utilisateur(new_login, new_nom, new_pwd, new_role)
                (st.success if ok else st.error)(msg)
                if ok: st.rerun()

        if not df_u.empty:
            st.divider()
            st.markdown("#### ✏️ Modifier un compte")
            uid_sel = st.selectbox("Utilisateur", df_u["id"].tolist(),
                format_func=lambda i: f"{df_u[df_u['id']==i]['nom_complet'].values[0]} (@{df_u[df_u['id']==i]['username'].values[0]})",
                key="sel_edit_user")
            user_sel = df_u[df_u["id"] == uid_sel].iloc[0]

            col_a, col_b = st.columns(2)
            nv_nom  = col_a.text_input("Nom complet (modifier)",    user_sel["nom_complet"], key="edit_u_nom")
            nv_role = col_b.selectbox("Rôle",                       ROLES,
                index=ROLES.index(user_sel["role"]) if user_sel["role"] in ROLES else 1, key="edit_u_role")
            nv_actif = st.checkbox("Compte actif", value=bool(user_sel["actif"]), key="edit_u_actif")

            col_c, col_d = st.columns(2)
            nv_pwd  = col_c.text_input("Nouveau mot de passe (vide = inchangé)", type="password", key="edit_u_pwd")
            nv_pwd2 = col_d.text_input("Confirmer le nouveau mot de passe",      type="password", key="edit_u_pwd2")

            if st.button("💾 Enregistrer les modifications", key="btn_save_user"):
                if uid_sel == st.session_state.auth_user_id and nv_role != "Admin":
                    st.error("Vous ne pouvez pas vous retirer le rôle Admin.")
                else:
                    maj_utilisateur(int(uid_sel), "nom_complet", nv_nom)
                    maj_utilisateur(int(uid_sel), "role",        nv_role)
                    maj_utilisateur(int(uid_sel), "actif",       1 if nv_actif else 0)
                    if nv_pwd:
                        if nv_pwd != nv_pwd2:
                            st.error("Les mots de passe ne correspondent pas.")
                        elif len(nv_pwd) < 8:
                            st.error("Minimum 8 caractères.")
                        else:
                            maj_utilisateur(int(uid_sel), "password_hash", hash_password(nv_pwd))
                            st.success("Mot de passe mis à jour.")
                    st.success("Compte mis à jour."); st.rerun()

            if st.button("🗑️ Supprimer ce compte", key="btn_del_user"):
                if uid_sel == st.session_state.auth_user_id:
                    st.error("Vous ne pouvez pas supprimer votre propre compte.")
                else:
                    supprimer_utilisateur(int(uid_sel)); st.warning("Compte supprimé."); st.rerun()

    # ---- CATALOGUE ----
    with tab_cat:
        filtre_u = st.selectbox("Filtrer par univers", ["Tous"] + UNIVERS)
        df_o = lire_offres(univers=None if filtre_u == "Tous" else filtre_u, actif_seulement=False)
        if df_o.empty:
            st.info("Catalogue vide.")
        else:
            st.dataframe(df_o[["id","univers","categorie","fournisseur","nom_offre","prix_mensuel",
                               "frais_activation","engagement_mois","commission_affiliation","actif"]],
                         hide_index=True, use_container_width=True)
            oid = st.selectbox("Offre à modifier", df_o["id"].tolist(),
                format_func=lambda i: f"#{i} · {df_o[df_o['id']==i]['nom_offre'].values[0]}")
            c1, c2, c3 = st.columns(3)
            nv_prix = c1.number_input("Nouveau prix (€)", min_value=0.0,
                value=float(df_o[df_o["id"]==oid]["prix_mensuel"].values[0]), step=1.0)
            if c1.button("💾 MàJ prix"):
                maj_offre(oid, "prix_mensuel", nv_prix); st.success("OK."); st.rerun()
            if c2.button("🔁 Activer/Désactiver"):
                etat = int(df_o[df_o["id"]==oid]["actif"].values[0])
                maj_offre(oid, "actif", 0 if etat else 1); st.rerun()
            if c3.button("🗑️ Supprimer"):
                supprimer_offre(oid); st.warning("Supprimé."); st.rerun()

    # ---- AJOUTER OFFRE ----
    with tab_add:
        st.caption("💡 Pour énergie/abonnements : relevez l'offre sur un comparateur, saisissez-la ici.")
        u = st.selectbox("Univers", UNIVERS, key="off_u")
        cat_map = {"Télécom": CATEGORIES_TELECOM, "Énergie": CATEGORIES_ENERGIE,
                   "Abonnements": CATEGORIES_ABO}
        liens = {"Énergie":      "https://comparateur-offres.energie-info.fr",
                 "Télécom":      "https://www.google.com/search?q=comparatif+forfait+mobile+box",
                 "Abonnements":  "https://www.google.com/search?q=prix+abonnement+streaming"}
        st.markdown(f"🔗 [Ouvrir un comparateur {u}]({liens[u]})")
        cat    = st.selectbox("Catégorie", cat_map[u], key="off_c")
        c1, c2 = st.columns(2)
        fourn  = c1.text_input("Fournisseur / Opérateur", key="add_off_fourn")
        nom    = c2.text_input("Nom de l'offre",           key="add_off_nom")
        prix   = c1.number_input("Prix mensuel (€)", min_value=0.0, step=1.0)
        frais  = c2.number_input("Frais d'activation (€)", min_value=0.0, step=1.0)
        engage = c1.number_input("Engagement (mois)", min_value=0, step=1)
        commiss= c2.number_input("Commission affiliation (€)", min_value=0.0, step=1.0)
        carac  = st.text_area("Caractéristiques (data, débit, options…)")
        if st.button("➕ Ajouter au catalogue", type="primary"):
            if nom and fourn:
                ajouter_offre({"univers": u, "categorie": cat, "fournisseur": fourn,
                               "nom_offre": nom, "prix_mensuel": prix,
                               "frais_activation": frais, "engagement_mois": engage,
                               "caracteristiques": carac, "commission_affiliation": commiss})
                st.success(f"« {nom} » ajoutée.")
            else:
                st.warning("Fournisseur et nom obligatoires.")

    # ---- DÉMO ----
    with tab_demo:
        st.markdown("### Pré-remplir le catalogue avec des offres de démonstration")
        st.caption("Ajoute un jeu d'offres types pour tester immédiatement. Vous pourrez tout modifier.")
        if st.button("⚡ Charger les offres de démo", type="primary"):
            inserer_offres_demo()
            st.success("Catalogue de démonstration chargé !"); st.rerun()

    # ---- EMAIL ----
    with tab_mail:
        st.session_state.nom_societe = st.text_input(
            "Nom de votre société (en-tête PDF/email)", st.session_state.nom_societe,
            key="smtp_nom_societe")
        st.markdown("### Configuration SMTP")
        st.caption("Gmail : smtp.gmail.com, port 587, mot de passe d'application.")
        cfg = st.session_state.smtp_config
        cfg["serveur"]    = st.text_input("Serveur SMTP",          cfg.get("serveur", ""),             key="smtp_serveur")
        cfg["port"]       = st.number_input("Port", min_value=1,   value=int(cfg.get("port", 587)),    key="smtp_port")
        cfg["user"]       = st.text_input("Identifiant SMTP",      cfg.get("user", ""),                key="smtp_user")
        cfg["mdp"]        = st.text_input("Mot de passe SMTP",     type="password",
                                          value=cfg.get("mdp", ""),                                    key="smtp_mdp")
        cfg["expediteur"] = st.text_input("Expéditeur affiché",    cfg.get("expediteur", cfg.get("user", "")), key="smtp_expediteur")
        st.session_state.smtp_config = cfg
        if st.button("💾 Enregistrer", key="btn_smtp_save"):
            st.success("Configuration enregistrée pour la session.")


# ==============================================================================
#  19. OFFRES DE DÉMONSTRATION
# ==============================================================================
# Fin du fichier