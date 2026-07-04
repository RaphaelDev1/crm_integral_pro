# ==============================================================================
#  CLIENTS
# ==============================================================================
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from constants import SATISFACTION_SCORE
from db import get_conn, enregistrer_action

CHAMPS_CLIENT = {
    "telephone", "email", "ville", "code_postal", "adresse", "operateur_actuel", "offre_actuelle",
    "cout_mensuel_actuel", "satisfaction_reseau", "veut_rester", "notes",
    "fournisseur_energie", "techno", "data_go", "speed_down", "speed_up",
    "economie_estimee_an", "date_relance", "statut_relance",
}


def ajouter_client(d: dict) -> int:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO clients
        (ref, prenom, nom, telephone, email, code_postal, ville, adresse, type_client,
         operateur_actuel, techno, data_go, offre_actuelle, cout_mensuel_actuel,
         satisfaction_reseau, veut_rester, speed_down, speed_up,
         fournisseur_energie, cout_elec, cout_gaz, economie_estimee_an,
         notes, date_creation, cree_par)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get("ref"),             d.get("prenom"),          d.get("nom"),
        d.get("telephone"),       d.get("email"),           d.get("code_postal"),
        d.get("ville"),           d.get("adresse"),         d.get("type_client"),
        d.get("operateur_actuel"),
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
    enregistrer_action("client", cid, "Création client",
                        f"{d.get('prenom','')} {d.get('nom','')}", auteur=d.get("cree_par") or None)
    return cid


def lire_clients():
    conn = get_conn()
    df   = pd.read_sql_query("SELECT * FROM clients ORDER BY id DESC", conn)
    conn.close()
    return df


def note_couverture_par_zone(ville: str) -> pd.DataFrame:
    """Agrège la satisfaction réseau moyenne par opérateur pour une ville donnée
    (prospects + clients confondus) — sert à orienter vers le meilleur opérateur local."""
    if not ville or not ville.strip():
        return pd.DataFrame()
    conn = get_conn()
    dfp = pd.read_sql_query(
        "SELECT operateur_actuel, satisfaction_reseau FROM prospects WHERE ville=? COLLATE NOCASE",
        conn, params=(ville.strip(),))
    dfc = pd.read_sql_query(
        "SELECT operateur_actuel, satisfaction_reseau FROM clients WHERE ville=? COLLATE NOCASE",
        conn, params=(ville.strip(),))
    conn.close()
    df = pd.concat([dfp, dfc], ignore_index=True)
    df = df[df["operateur_actuel"].notna() & (df["operateur_actuel"] != "Autre / Aucun")]
    if df.empty:
        return pd.DataFrame()
    df["score"] = df["satisfaction_reseau"].map(SATISFACTION_SCORE)
    df = df.dropna(subset=["score"])
    if df.empty:
        return pd.DataFrame()
    agg = df.groupby("operateur_actuel")["score"].agg(["mean", "count"]).reset_index()
    agg.columns = ["operateur", "note_moyenne", "nb_avis"]
    return agg.sort_values("note_moyenne", ascending=False)


def meilleur_debit_par_zone(ville: str) -> pd.DataFrame:
    """Agrège les débits mesurés (⬇️/⬆️ Mbps) par opérateur pour une ville donnée
    (prospects + clients confondus) — recommande l'opérateur au meilleur débit réel
    constaté localement, en complément de la satisfaction subjective."""
    if not ville or not ville.strip():
        return pd.DataFrame()
    conn = get_conn()
    dfp = pd.read_sql_query(
        "SELECT operateur_actuel, speed_down, speed_up FROM prospects WHERE ville=? COLLATE NOCASE",
        conn, params=(ville.strip(),))
    dfc = pd.read_sql_query(
        "SELECT operateur_actuel, speed_down, speed_up FROM clients WHERE ville=? COLLATE NOCASE",
        conn, params=(ville.strip(),))
    conn.close()
    df = pd.concat([dfp, dfc], ignore_index=True)
    df = df[df["operateur_actuel"].notna() & (df["operateur_actuel"] != "Autre / Aucun")]
    df = df[(df["speed_down"].fillna(0) > 0) | (df["speed_up"].fillna(0) > 0)]
    if df.empty:
        return pd.DataFrame()
    agg = df.groupby("operateur_actuel").agg(
        debit_down_moyen=("speed_down", "mean"),
        debit_up_moyen=("speed_up", "mean"),
        nb_mesures=("speed_down", "count"),
    ).reset_index()
    agg = agg.rename(columns={"operateur_actuel": "operateur"})
    agg["debit_down_moyen"] = agg["debit_down_moyen"].round(1)
    agg["debit_up_moyen"]   = agg["debit_up_moyen"].round(1)
    return agg.sort_values("debit_down_moyen", ascending=False)


def maj_client(cid: int, champ: str, valeur, auteur: str = None):
    if champ not in CHAMPS_CLIENT:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE clients SET {champ}=? WHERE id=?", (valeur, cid))
    conn.commit()
    conn.close()
    enregistrer_action("client", cid, "Modification", f"{champ} = {valeur}", auteur=auteur)


def widget_relance_client(client_id, key_prefix: str, jours_auto: int = 30) -> bool:
    """UI de relance client : bouton principal « Relance effectuée » qui reprogramme
    automatiquement à +jours_auto (30 jours = 1 mois par défaut, pour avoir le temps
    d'appeler/faire le point), + une option de date précise repliée pour les cas
    particuliers. Renvoie True si une action a été effectuée (à l'appelant de faire
    le st.rerun())."""
    fait = st.button(f"✅ Relance effectuée (reprogrammer +{jours_auto} j)",
                      key=f"{key_prefix}_fait", type="primary")
    with st.expander("📅 Date précise"):
        date_cible = st.date_input(
            "Date de relance", value=datetime.now().date() + timedelta(days=jours_auto),
            key=f"{key_prefix}_date")
        programmer = st.button("Programmer cette date", key=f"{key_prefix}_prog")

    if fait:
        nv_date = datetime.now().date() + timedelta(days=jours_auto)
        maj_client(int(client_id), "date_relance", nv_date.strftime("%d/%m/%Y"))
        maj_client(int(client_id), "statut_relance", "À relancer")
        return True
    if programmer:
        maj_client(int(client_id), "date_relance", date_cible.strftime("%d/%m/%Y"))
        maj_client(int(client_id), "statut_relance", "À relancer")
        return True
    return False


def supprimer_client(cid: int, auteur: str = None):
    conn = get_conn()
    c    = conn.cursor()
    row  = c.execute("SELECT prenom, nom FROM clients WHERE id=?", (cid,)).fetchone()
    c.execute("DELETE FROM contrats WHERE client_id=?", (cid,))
    c.execute("DELETE FROM clients WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    nom_aff = f"{row['prenom']} {row['nom']}" if row else ""
    enregistrer_action("client", cid, "Suppression", nom_aff, auteur=auteur)
