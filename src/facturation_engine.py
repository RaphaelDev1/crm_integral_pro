# ==============================================================================
#  FACTURATION — devis d'honoraires, mandat de représentation, suivi de paiement
# ==============================================================================
from datetime import datetime

import pandas as pd

from db import get_conn, enregistrer_action

CHAMPS_FACTURE = {"statut", "notes", "taux_honoraires", "montant_honoraires"}


def creer_facture(d: dict) -> int:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO factures
        (reference, prospect_id, client_id, prenom, nom, email, telephone, ville,
         economie_annuelle, taux_honoraires, montant_honoraires, statut,
         date_creation, date_paiement, mandat_signe, mandat_signataire,
         mandat_date_signature, notes, cree_par)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?)
    """, (
        d.get("reference"),      d.get("prospect_id"),    d.get("client_id"),
        d.get("prenom"),         d.get("nom"),             d.get("email"),
        d.get("telephone"),      d.get("ville"),
        d.get("economie_annuelle", 0.0), d.get("taux_honoraires", 0.0),
        d.get("montant_honoraires", 0.0),
        d.get("statut", "Devis envoyé"),
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        d.get("date_paiement"),
        d.get("mandat_signataire"), d.get("mandat_date_signature"),
        d.get("notes"),          d.get("cree_par", ""),
    ))
    fid = c.lastrowid
    conn.commit()
    conn.close()
    enregistrer_action("facture", fid, "Devis créé",
                        f"{d.get('reference','')} — {d.get('montant_honoraires', 0.0)} € "
                        f"({d.get('prenom','')} {d.get('nom','')})")
    return fid


def lire_factures(prospect_id: int = None, statut: str = None) -> pd.DataFrame:
    conn   = get_conn()
    q      = "SELECT * FROM factures WHERE 1=1"
    params = []
    if prospect_id is not None:
        q += " AND prospect_id=?"; params.append(prospect_id)
    if statut:
        q += " AND statut=?"; params.append(statut)
    q += " ORDER BY id DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def maj_facture(fid: int, champ: str, valeur):
    if champ not in CHAMPS_FACTURE:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE factures SET {champ}=? WHERE id=?", (valeur, fid))
    conn.commit()
    conn.close()
    enregistrer_action("facture", fid, "Modification", f"{champ} = {valeur}")


def changer_statut(fid: int, nouveau_statut: str):
    """Fait progresser le statut du devis. Fixe automatiquement la date de paiement
    lors du premier passage à 'Payé'."""
    conn = get_conn()
    c    = conn.cursor()
    row  = c.execute("SELECT date_paiement FROM factures WHERE id=?", (fid,)).fetchone()
    c.execute("UPDATE factures SET statut=? WHERE id=?", (nouveau_statut, fid))
    if nouveau_statut == "Payé" and row is not None and not row["date_paiement"]:
        c.execute("UPDATE factures SET date_paiement=? WHERE id=?",
                   (datetime.now().strftime("%d/%m/%Y"), fid))
    conn.commit()
    conn.close()
    enregistrer_action("facture", fid, "Changement de statut", nouveau_statut)


def marquer_mandat_signe(fid: int, signataire: str, date_signature: str):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        UPDATE factures SET mandat_signe=1, mandat_signataire=?, mandat_date_signature=?
        WHERE id=?
    """, (signataire, date_signature, fid))
    conn.commit()
    conn.close()
    enregistrer_action("facture", fid, "Mandat signé", f"{signataire} — {date_signature}")


def lier_facture_a_client(prospect_id: int, client_id: int):
    """Appelée à la conversion prospect→client : rattache les devis existants
    du prospect au nouveau client (le prospect_id devient une référence historique,
    potentiellement orpheline puisque le prospect est supprimé à la conversion)."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("UPDATE factures SET client_id=? WHERE prospect_id=?", (client_id, prospect_id))
    conn.commit()
    conn.close()
