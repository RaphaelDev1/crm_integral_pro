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


def ajouter_contrat(d: dict):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO contrats
        (client_id, univers, categorie, fournisseur, nom_offre, cout_mensuel,
         economie_mensuelle, reference_contrat, statut_contrat, date_souscription,
         date_fin_engagement, notes, cree_par)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get("client_id"),       d.get("univers"),         d.get("categorie"),
        d.get("fournisseur"),     d.get("nom_offre"),       d.get("cout_mensuel", 0.0),
        d.get("economie_mensuelle", 0.0),d.get("reference_contrat"),
        d.get("statut_contrat", "En cours d'ouverture"),
        datetime.now().strftime("%d/%m/%Y"),
        d.get("date_fin_engagement", ""),
        d.get("notes"),           d.get("cree_par", ""),
    ))
    conn.commit()
    conn.close()
    enregistrer_action("client", d.get("client_id"), "Ajout contrat",
                        f"{d.get('fournisseur','')} — {d.get('nom_offre','')} ({d.get('cout_mensuel', 0.0)} €/mois)",
                        auteur=d.get("cree_par") or None)


def lire_contrats_client(cid: int):
    conn = get_conn()
    df   = pd.read_sql_query(
        "SELECT * FROM contrats WHERE client_id=? ORDER BY id DESC", conn, params=(cid,)
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


def supprimer_contrat(ctid: int, auteur: str = None):
    conn = get_conn()
    c    = conn.cursor()
    row  = c.execute("SELECT client_id, nom_offre FROM contrats WHERE id=?", (ctid,)).fetchone()
    c.execute("DELETE FROM contrats WHERE id=?", (ctid,))
    conn.commit()
    conn.close()
    if row:
        enregistrer_action("client", row["client_id"], "Suppression contrat", f"{row['nom_offre']} (#{ctid})",
                            auteur=auteur)
