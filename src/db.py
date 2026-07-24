# ==============================================================================
#  BASE DE DONNÉES — CONNEXION, SCHÉMA, MIGRATIONS + HISTORIQUE (AUDIT TRAIL)
# ==============================================================================
import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ia_conseil_crm.db")


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
            adresse               TEXT,
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
            cree_par              TEXT,
            offres_interet        TEXT,
            score                 REAL DEFAULT 0,
            origine               TEXT DEFAULT 'Manuel'
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
            adresse               TEXT,
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
            date_fin_engagement TEXT,
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
            data_go               REAL DEFAULT 0,
            actif                 INTEGER DEFAULT 1,
            url_souscription      TEXT,
            code_affiliation      TEXT,
            date_maj              TEXT
        )
    """)

    # Table historique_actions (NOUVELLE en Étape 3) — audit trail, insert-only
    c.execute("""
        CREATE TABLE IF NOT EXISTS historique_actions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            entite_type   TEXT,
            entite_id     INTEGER,
            action        TEXT,
            details       TEXT,
            auteur        TEXT,
            date_action   TEXT
        )
    """)

    # Table login_tentatives — audit + rate limiting login (insert-only), une ligne
    # par tentative de connexion (succès ou échec), clé (identifiant, ip).
    c.execute("""
        CREATE TABLE IF NOT EXISTS login_tentatives (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            identifiant    TEXT,
            ip             TEXT,
            succes         INTEGER,
            date_tentative TEXT
        )
    """)

    # Table parametres — réglages clé/valeur génériques (ex. taux d'honoraires par défaut)
    c.execute("""
        CREATE TABLE IF NOT EXISTS parametres (
            cle    TEXT PRIMARY KEY,
            valeur TEXT
        )
    """)

    # Table factures — devis d'honoraires + mandat + suivi de paiement, rattachés à un prospect
    c.execute("""
        CREATE TABLE IF NOT EXISTS factures (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            reference             TEXT,
            prospect_id           INTEGER,
            client_id             INTEGER,
            prenom                TEXT,
            nom                   TEXT,
            email                 TEXT,
            telephone             TEXT,
            ville                 TEXT,
            economie_annuelle     REAL,
            taux_honoraires       REAL,
            montant_honoraires    REAL,
            statut                TEXT,
            date_creation         TEXT,
            date_paiement         TEXT,
            mandat_signe          INTEGER DEFAULT 0,
            mandat_signataire     TEXT,
            mandat_date_signature TEXT,
            notes                 TEXT,
            cree_par              TEXT
        )
    """)

    # Table chatbot_sessions — état de conversation du chatbot public (widget web),
    # indépendante de Streamlit (process FastAPI séparé, cf. chatbot_api.py)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_sessions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id     TEXT    UNIQUE NOT NULL,
            messages_json  TEXT,
            donnees_json   TEXT,
            statut         TEXT    DEFAULT 'en_cours',
            prospect_id    INTEGER,
            date_creation  TEXT,
            date_maj       TEXT
        )
    """)

    # Table sources_veille — pages tarifs opérateurs surveillées par le scraper
    # (cf. veille_prix_engine.py). Rattachée à une offre du catalogue (offre_id)
    # pour la mise à jour automatique du prix ; peut aussi rester non rattachée
    # (simple veille concurrentielle sans impact catalogue).
    c.execute("""
        CREATE TABLE IF NOT EXISTS sources_veille (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            univers             TEXT,
            categorie           TEXT,
            fournisseur         TEXT,
            nom_offre           TEXT,
            offre_id            INTEGER,
            url                 TEXT,
            selecteur_prix      TEXT,
            actif               INTEGER DEFAULT 1,
            dernier_prix        REAL,
            date_derniere_verif TEXT,
            date_creation       TEXT,
            FOREIGN KEY (offre_id) REFERENCES offres(id)
        )
    """)

    # Table veille_historique_prix — un relevé par vérification (insert-only),
    # sert à tracer les tendances de prix affichées au client.
    c.execute("""
        CREATE TABLE IF NOT EXISTS veille_historique_prix (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id    INTEGER,
            prix         REAL,
            date_releve  TEXT,
            FOREIGN KEY (source_id) REFERENCES sources_veille(id)
        )
    """)

    # Table veille_alertes — changement de prix détecté, en attente de validation
    # admin avant répercussion sur le catalogue (cf. valider_alerte()).
    c.execute("""
        CREATE TABLE IF NOT EXISTS veille_alertes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id        INTEGER,
            ancien_prix      REAL,
            nouveau_prix     REAL,
            statut           TEXT DEFAULT 'en_attente',
            date_detection   TEXT,
            date_traitement  TEXT,
            FOREIGN KEY (source_id) REFERENCES sources_veille(id)
        )
    """)

    # Table catalogue_sources — pages/flux à ingérer pour découvrir de nouvelles
    # offres (cf. catalogue_engine.py). À ne pas confondre avec sources_veille,
    # qui ne suit que le prix d'une offre déjà présente au catalogue : ici on
    # récupère la page entière et on laisse le LLM en extraire les offres.
    c.execute("""
        CREATE TABLE IF NOT EXISTS catalogue_sources (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            univers                 TEXT,
            categorie               TEXT,
            fournisseur             TEXT,
            url                     TEXT,
            type_source             TEXT DEFAULT 'page_officielle',
            methode                 TEXT DEFAULT 'requests',
            actif                   INTEGER DEFAULT 1,
            robots_ok               INTEGER,
            frequence_h             INTEGER DEFAULT 24,
            date_derniere_ingestion TEXT,
            date_creation           TEXT
        )
    """)

    # Table offres_staging — offres détectées par catalogue_engine.py, jamais
    # écrites directement dans `offres` : un admin valide/rejette/fusionne
    # depuis Admin > 📚 Catalogue > Offres détectées (même principe que
    # veille_alertes pour la veille prix).
    c.execute("""
        CREATE TABLE IF NOT EXISTS offres_staging (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id               INTEGER,
            univers                 TEXT,
            categorie               TEXT,
            fournisseur             TEXT,
            nom_offre               TEXT,
            prix_mensuel            REAL,
            frais_activation        REAL,
            engagement_mois         INTEGER,
            data_go                 REAL,
            caracteristiques        TEXT,
            commission_affiliation  REAL,
            url_souscription        TEXT,
            code_affiliation        TEXT,
            hash_contenu            TEXT,
            statut                  TEXT DEFAULT 'en_attente',
            confiance_llm           REAL,
            champs_incertains       TEXT,
            payload_brut            TEXT,
            offre_existante_id      INTEGER,
            date_detection          TEXT,
            date_traitement         TEXT,
            FOREIGN KEY (source_id) REFERENCES catalogue_sources(id),
            FOREIGN KEY (offre_existante_id) REFERENCES offres(id)
        )
    """)

    # Table tokens_prospects — lien à usage personnel (sans login) envoyé par
    # SMS/email à un prospect pour qu'il transmette lui-même sa facture et un
    # test de débit (cf. prospects_engine.creer_token_documents / chatbot_api.py
    # /portail/{token}), sur le même principe que le portail client du backend/.
    c.execute("""
        CREATE TABLE IF NOT EXISTS tokens_prospects (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id               INTEGER NOT NULL,
            token                     TEXT UNIQUE NOT NULL,
            date_creation             TEXT,
            date_expiration           TEXT,
            date_derniere_utilisation TEXT,
            nb_utilisations           INTEGER DEFAULT 0,
            revoque                   INTEGER DEFAULT 0,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id)
        )
    """)

    conn.commit()
    conn.close()
    _migrer_bdd()   # ← Ajoute les colonnes manquantes aux BDD existantes
    _initialiser_fts()   # ← Index de recherche full-text (SQLite FTS5)


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
        ("prospects", "offres_interet",       "TEXT"),
        ("prospects", "score",                "REAL DEFAULT 0"),
        ("prospects", "origine",              "TEXT DEFAULT 'Manuel'"),
        # Date de fin d'engagement du contrat actuel du prospect (chez son opérateur actuel) —
        # sert à programmer automatiquement la relance à l'approche de l'échéance au lieu d'une
        # date arbitraire, cf. prospects_engine.py::widget_relance.
        ("prospects", "date_fin_engagement",  "TEXT"),
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
        ("clients",   "date_relance",         "TEXT"),
        ("clients",   "statut_relance",       "TEXT DEFAULT 'Aucune'"),
        # backend_client_id : id du client miroir côté backend/ (Postgres) — backend/ et le
        # CRM Streamlit (SQLite) sont deux bases disjointes avec des id indépendants (voir
        # src/api_client.py::_backend_client_id_pour) ; ce champ mémorise le mapping une fois
        # le miroir créé, pour ne pas en recréer un à chaque nouveau dossier.
        ("clients",   "backend_client_id",    "INTEGER"),
        # ── utilisateurs ───────────────────────────────────────────────
        ("utilisateurs", "doit_changer_mdp",  "INTEGER DEFAULT 0"),
        ("prospects", "adresse",              "TEXT"),
        ("clients",   "adresse",              "TEXT"),
        # ── contrats (base créée avant l'ajout de ces colonnes → ALTER requis) ──
        ("contrats",  "univers",              "TEXT"),
        ("contrats",  "categorie",            "TEXT"),
        ("contrats",  "fournisseur",          "TEXT"),
        ("contrats",  "nom_offre",            "TEXT"),
        ("contrats",  "cout_mensuel",         "REAL DEFAULT 0"),
        ("contrats",  "economie_mensuelle",   "REAL DEFAULT 0"),
        ("contrats",  "reference_contrat",    "TEXT"),
        ("contrats",  "statut_contrat",       "TEXT"),
        ("contrats",  "date_souscription",    "TEXT"),
        ("contrats",  "date_fin_engagement",  "TEXT"),
        ("contrats",  "notes",                "TEXT"),
        ("contrats",  "cree_par",             "TEXT"),
        # prospect_id : contrat rattaché à un prospect (autre service déjà souscrit ailleurs,
        # appris par le conseiller) plutôt qu'à un client — client_id reste NULL dans ce cas.
        ("contrats",  "prospect_id",          "INTEGER"),
        # type_contrat : distingue, pour un contrat rattaché à un prospect, un simple service
        # déjà souscrit ailleurs ("reference_externe", sert de base de comparaison cross-sell,
        # cf. cout_reference_categorie) d'un dossier en cours de vente avec nous
        # ("dossier_cmr", suit ETAPES_CONTRAT et déclenche la conversion en client une fois
        # "Actif" — cf. app.py::finaliser_conversion_client). NULL = reference_externe (valeur
        # implicite des contrats prospect créés avant l'ajout de cette colonne).
        ("contrats",  "type_contrat",         "TEXT"),
        # ── offres ─────────────────────────────────────────────────────
        ("offres",    "data_go",              "REAL DEFAULT 0"),
        ("offres",    "url_souscription",     "TEXT"),
        ("offres",    "code_affiliation",     "TEXT"),
        # backend_client_id sur prospects : même mécanisme que pour les clients (voir
        # commentaire ci-dessus) — un prospect peut désormais avoir un dossier suivi côté
        # backend/ (stepper + mandats + historique) avant même sa conversion en client.
        ("prospects", "backend_client_id",    "INTEGER"),
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


# ==============================================================================
#  HISTORIQUE DES ACTIONS — audit trail, insert-only, partagé par tous les modules
# ==============================================================================
def enregistrer_action(entite_type: str, entite_id: int, action: str, details: str = "",
                        auteur: str = None):
    """Ajoute une ligne à l'historique d'audit (insert-only, jamais modifiée/supprimée).

    `auteur` : nom de l'auteur de l'action. Si non fourni (appel depuis une page
    Streamlit), déduit de la session utilisateur connectée. Un appelant hors
    contexte Streamlit (ex. l'API CRM interne, crm_api.py) doit le fournir
    explicitement — l'accès à st.session_state y échouerait sinon."""
    if auteur is None:
        try:
            auteur = st.session_state.get("auth_nom_complet", "")
        except Exception:
            auteur = ""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO historique_actions (entite_type, entite_id, action, details, auteur, date_action)
        VALUES (?,?,?,?,?,?)
    """, (
        entite_type, entite_id, action, details, auteur,
        datetime.now().strftime("%d/%m/%Y %H:%M"),
    ))
    conn.commit()
    conn.close()


def lire_historique(entite_type: str, entite_id: int):
    conn = get_conn()
    df   = pd.read_sql_query(
        "SELECT * FROM historique_actions WHERE entite_type=? AND entite_id=? ORDER BY id DESC",
        conn, params=(entite_type, entite_id)
    )
    conn.close()
    return df


# ==============================================================================
#  PARAMÈTRES — réglages clé/valeur génériques (ex. taux d'honoraires par défaut)
# ==============================================================================
def lire_parametre(cle: str, defaut: str = "") -> str:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT valeur FROM parametres WHERE cle=?", (cle,))
    row = c.fetchone()
    conn.close()
    return row["valeur"] if row is not None else defaut


def ecrire_parametre(cle: str, valeur: str):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO parametres (cle, valeur) VALUES (?,?)
        ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur
    """, (cle, str(valeur)))
    conn.commit()
    conn.close()


# ==============================================================================
#  RECHERCHE FULL-TEXT (SQLite FTS5) — clients_fts / prospects_fts
# ==============================================================================
# Colonnes indexées (tables externes 'clients' / 'prospects' — FTS5 en mode
# "external content" : l'index ne duplique pas les données, juste le texte tokenisé).
_FTS_COLS_CLIENTS   = ["prenom", "nom", "telephone", "email", "ville", "code_postal",
                       "adresse", "ref", "operateur_actuel", "offre_actuelle",
                       "fournisseur_energie", "notes"]
_FTS_COLS_PROSPECTS = _FTS_COLS_CLIENTS + ["statut", "univers_interesse"]

FTS_OK = True   # Passe à False si FTS5 n'est pas compilé dans le SQLite de l'environnement


def _fts_triggers(table: str, fts: str, cols: list) -> list:
    """Génère les triggers qui gardent `<table>_fts` synchronisée avec `<table>`
    à chaque INSERT/UPDATE/DELETE (pattern standard FTS5 en 'external content')."""
    cols_csv = ", ".join(cols)
    new_vals = ", ".join(f"new.{c}" for c in cols)
    old_vals = ", ".join(f"old.{c}" for c in cols)
    return [
        f"""CREATE TRIGGER IF NOT EXISTS {table}_fts_ai AFTER INSERT ON {table} BEGIN
              INSERT INTO {fts}(rowid, {cols_csv}) VALUES (new.id, {new_vals});
            END;""",
        f"""CREATE TRIGGER IF NOT EXISTS {table}_fts_ad AFTER DELETE ON {table} BEGIN
              INSERT INTO {fts}({fts}, rowid, {cols_csv}) VALUES('delete', old.id, {old_vals});
            END;""",
        f"""CREATE TRIGGER IF NOT EXISTS {table}_fts_au AFTER UPDATE ON {table} BEGIN
              INSERT INTO {fts}({fts}, rowid, {cols_csv}) VALUES('delete', old.id, {old_vals});
              INSERT INTO {fts}(rowid, {cols_csv}) VALUES (new.id, {new_vals});
            END;""",
    ]


def _initialiser_fts():
    """Crée les tables virtuelles FTS5 (clients_fts, prospects_fts) + leurs triggers
    de synchronisation, et réindexe si l'index est vide alors que la table source
    contient déjà des lignes (première installation de la fonctionnalité)."""
    global FTS_OK
    conn = get_conn()
    c    = conn.cursor()
    try:
        c.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS clients_fts USING fts5("
            f"{', '.join(_FTS_COLS_CLIENTS)}, "
            "content='clients', content_rowid='id', tokenize=\"unicode61 remove_diacritics 2\")"
        )
        c.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS prospects_fts USING fts5("
            f"{', '.join(_FTS_COLS_PROSPECTS)}, "
            "content='prospects', content_rowid='id', tokenize=\"unicode61 remove_diacritics 2\")"
        )
        for sql in _fts_triggers("clients", "clients_fts", _FTS_COLS_CLIENTS):
            c.execute(sql)
        for sql in _fts_triggers("prospects", "prospects_fts", _FTS_COLS_PROSPECTS):
            c.execute(sql)
        conn.commit()

        for table, fts in (("clients", "clients_fts"), ("prospects", "prospects_fts")):
            nb_source = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            nb_index  = c.execute(f"SELECT COUNT(*) FROM {fts}").fetchone()[0]
            if nb_source > 0 and nb_index == 0:
                c.execute(f"INSERT INTO {fts}({fts}) VALUES ('rebuild')")
        conn.commit()
        FTS_OK = True
    except Exception:
        conn.rollback()
        FTS_OK = False
    finally:
        conn.close()


def recherche_fts(table: str, requete: str):
    """Recherche full-text (FTS5) sur 'clients' ou 'prospects'. Renvoie la liste des
    id correspondants, triés par pertinence — ou None si FTS5 est indisponible
    (à l'appelant de retomber sur une recherche Python classique dans ce cas)."""
    if not FTS_OK or not requete or not requete.strip():
        return None
    termes = [t.strip().replace('"', '') for t in requete.split() if t.strip()]
    if not termes:
        return None
    match = " ".join(f'"{t}"*' for t in termes)   # préfixe sur chaque terme → recherche partielle
    conn = get_conn()
    c    = conn.cursor()
    try:
        rows = c.execute(
            f"SELECT rowid FROM {table}_fts WHERE {table}_fts MATCH ? ORDER BY rank", (match,)
        ).fetchall()
        return [r["rowid"] for r in rows]
    except Exception:
        return None
    finally:
        conn.close()
