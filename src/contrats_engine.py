# ==============================================================================
#  CONTRATS
# ==============================================================================
from datetime import datetime

import pandas as pd

from db import get_conn, enregistrer_action
from utils import parser_date_relance

CHAMPS_CONTRAT = {
    "nom_offre", "cout_mensuel", "economie_mensuelle", "statut_contrat",
    "reference_contrat", "fournisseur", "notes", "date_souscription", "date_fin_engagement",
}

# Étapes du dossier après conversion prospect → client, dans l'ordre où elles se déroulent
# normalement (progression via un bouton « étape suivante », cf. app.py). « Résilié » est un
# statut terminal accessible à part, hors de cette progression.
ETAPES_CONTRAT = ["Documents reçus", "Mandat envoyé", "Mandat signé", "Souscription en cours", "Actif"]
STATUT_CONTRAT_INITIAL = ETAPES_CONTRAT[0]


def ajouter_contrat(d: dict):
    """Un contrat est rattaché soit à un client (d['client_id']), soit à un prospect
    (d['prospect_id']) — ce second cas sert à enregistrer un service que le prospect a déjà
    souscrit ailleurs (appris par le conseiller), pour que l'économie affichée sur les offres
    cross-sell (ex. Box proposée à un prospect Mobile uniquement) ait une vraie base de
    comparaison au lieu d'être calculée contre un coût qui n'a rien à voir."""
    prospect_id = d.get("prospect_id")
    conn = get_conn()
    c    = conn.cursor()
    if prospect_id:
        if not c.execute("SELECT 1 FROM prospects WHERE id=?", (prospect_id,)).fetchone():
            conn.close()
            raise ValueError(f"Prospect #{prospect_id} introuvable — impossible d'y rattacher un contrat.")
    elif not c.execute("SELECT 1 FROM clients WHERE id=?", (d.get("client_id"),)).fetchone():
        conn.close()
        raise ValueError(
            f"Client #{d.get('client_id')} introuvable dans la base locale — impossible d'y "
            "rattacher un contrat. Si backend/main.py (Postgres) tourne en parallèle, ce client "
            "a peut-être été créé là-bas : arrêtez backend/ ou utilisez CRM_API_URL/BACKEND_API_URL "
            "pour ne pas mélanger les deux bases (voir api_client.py)."
        )
    c.execute("""
        INSERT INTO contrats
        (client_id, prospect_id, univers, categorie, fournisseur, nom_offre, cout_mensuel,
         economie_mensuelle, reference_contrat, statut_contrat, date_souscription,
         date_fin_engagement, notes, cree_par, type_contrat)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get("client_id"),       prospect_id,               d.get("univers"),
        d.get("categorie"),
        d.get("fournisseur"),     d.get("nom_offre"),       d.get("cout_mensuel", 0.0),
        d.get("economie_mensuelle", 0.0),d.get("reference_contrat"),
        d.get("statut_contrat", STATUT_CONTRAT_INITIAL),
        datetime.now().strftime("%d/%m/%Y"),
        d.get("date_fin_engagement", ""),
        d.get("notes"),           d.get("cree_par", ""),
        d.get("type_contrat"),
    ))
    conn.commit()
    conn.close()
    entite_type, entite_id = ("prospect", prospect_id) if prospect_id else ("client", d.get("client_id"))
    enregistrer_action(entite_type, entite_id, "Ajout contrat",
                        f"{d.get('fournisseur','')} — {d.get('nom_offre','')} ({d.get('cout_mensuel', 0.0)} €/mois)",
                        auteur=d.get("cree_par") or None)


def lire_contrats_client(cid: int):
    conn = get_conn()
    df   = pd.read_sql_query(
        "SELECT * FROM contrats WHERE client_id=? ORDER BY id DESC", conn, params=(cid,)
    )
    conn.close()
    return df


def lire_contrats_prospect(pid: int):
    """Autres contrats déjà souscrits par le prospect (ailleurs) — cf. ajouter_contrat."""
    conn = get_conn()
    df   = pd.read_sql_query(
        "SELECT * FROM contrats WHERE prospect_id=? ORDER BY id DESC", conn, params=(pid,)
    )
    conn.close()
    return df


def maj_contrat(ctid: int, champ: str, valeur, auteur: str = None):
    if champ not in CHAMPS_CONTRAT:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    row  = c.execute("SELECT client_id, nom_offre FROM contrats WHERE id=?", (ctid,)).fetchone()
    c.execute(f"UPDATE contrats SET {champ}=? WHERE id=?", (valeur, ctid))
    conn.commit()
    conn.close()
    if row:
        enregistrer_action("client", row["client_id"], "Modification contrat",
                            f"Contrat {row['nom_offre']} (#{ctid}) : {champ} = {valeur}", auteur=auteur)


def lire_contrats_echeance(jours: int = 90) -> pd.DataFrame:
    """Contrats dont la date de fin d'engagement tombe dans les `jours` prochains jours
    (aujourd'hui inclus), toutes clients confondus — alimente le dashboard « contrats à
    échéance » et l'alerte de fin d'engagement (2 mois avant, cf. notifications.py)."""
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT ct.*, cl.prenom AS client_prenom, cl.nom AS client_nom,
               cl.email AS client_email, cl.telephone AS client_telephone,
               cl.cree_par AS client_conseiller
        FROM contrats ct
        JOIN clients cl ON cl.id = ct.client_id
        WHERE ct.date_fin_engagement IS NOT NULL AND ct.date_fin_engagement != ''
    """, conn)
    conn.close()
    if df.empty:
        return df
    today = datetime.now().date()
    df["_date_fin"] = df["date_fin_engagement"].apply(parser_date_relance)
    df = df[df["_date_fin"].notna()].copy()
    df["jours_restants"] = df["_date_fin"].apply(lambda d: (d - today).days)
    df = df[(df["jours_restants"] >= 0) & (df["jours_restants"] <= jours)]
    return df.sort_values("jours_restants")


def transferer_contrats_dossier_vers_client(pid: int, cid: int):
    """Finalise la conversion prospect → client côté contrats : les dossiers en cours
    (type_contrat='dossier_cmr', cf. app.py::creer_dossier_prospect_ui) sont repointés vers
    le nouveau client, les éventuels contrats de simple référence externe restants (services
    déjà souscrits ailleurs, sans utilité une fois le prospect devenu client) sont supprimés
    pour ne pas laisser de lignes orphelines (prospect_id pointant vers un prospect supprimé)."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute(
        "UPDATE contrats SET client_id=?, prospect_id=NULL "
        "WHERE prospect_id=? AND type_contrat='dossier_cmr'", (cid, pid))
    c.execute("DELETE FROM contrats WHERE prospect_id=?", (pid,))
    conn.commit()
    conn.close()


def supprimer_contrat(ctid: int, auteur: str = None):
    conn = get_conn()
    c    = conn.cursor()
    row  = c.execute(
        "SELECT client_id, prospect_id, nom_offre FROM contrats WHERE id=?", (ctid,)
    ).fetchone()
    c.execute("DELETE FROM contrats WHERE id=?", (ctid,))
    conn.commit()
    conn.close()
    if row:
        entite_type, entite_id = (
            ("prospect", row["prospect_id"]) if row["prospect_id"] else ("client", row["client_id"])
        )
        enregistrer_action(entite_type, entite_id, "Suppression contrat", f"{row['nom_offre']} (#{ctid})",
                            auteur=auteur)
