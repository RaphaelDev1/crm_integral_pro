# ==============================================================================
#  PROSPECTS
# ==============================================================================
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from db import get_conn, enregistrer_action
from utils import safe_float

CHAMPS_PROSPECT = {
    "telephone", "email", "operateur_actuel", "offre_actuelle", "cout_mensuel_actuel",
    "notes", "statut", "date_relance", "satisfaction_reseau", "veut_rester",
    "ville", "code_postal", "adresse", "prenom", "nom", "fournisseur_energie",
    "techno", "data_go", "speed_down", "speed_up", "type_client",
    "economie_estimee_an", "offres_interet",
}


def ajouter_prospect(d: dict):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO prospects
        (ref, prenom, nom, telephone, email, code_postal, ville, adresse, type_client,
         univers_interesse, service_principal, operateur_actuel, techno, data_go,
         cout_mensuel_actuel, offre_actuelle, satisfaction_reseau, veut_rester,
         speed_down, speed_up, cout_elec, cout_gaz, fournisseur_energie,
         abonnements, lignes_multi, economie_estimee_an, notes, statut,
         date_creation, date_relance, cree_par, offres_interet, origine)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get("ref"),             d.get("prenom"),          d.get("nom"),
        d.get("telephone"),       d.get("email"),           d.get("code_postal"),
        d.get("ville"),           d.get("adresse"),         d.get("type_client"),
        d.get("univers_interesse"),
        d.get("service_principal"),d.get("operateur_actuel"),d.get("techno"),
        d.get("data_go"),         d.get("cout_mensuel_actuel", 0.0),
        d.get("offre_actuelle"),  d.get("satisfaction_reseau"),d.get("veut_rester"),
        d.get("speed_down", 0.0), d.get("speed_up", 0.0),  d.get("cout_elec", 0.0),
        d.get("cout_gaz", 0.0),   d.get("fournisseur_energie"),d.get("abonnements"),
        d.get("lignes_multi"),    d.get("economie_estimee_an", 0.0),d.get("notes"),
        d.get("statut", "À relancer"),
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        # Un prospect fraîchement créé doit être relancé aujourd'hui (jour-J) sauf date explicite fournie
        d.get("date_relance") or datetime.now().strftime("%d/%m/%Y"),
        d.get("cree_par", ""),
        d.get("offres_interet", "[]"),
        d.get("origine", "Manuel"),
    ))
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid


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


def widget_relance(prospect_id, key_prefix: str, jours_auto: int = 7) -> bool:
    """UI de relance prospect : bouton principal « Relance effectuée » qui reprogramme
    automatiquement à +jours_auto (le prospect reste une urgence du jour tant qu'il n'est
    pas traité), + une option de date précise repliée pour les offres avec engagement.
    Renvoie True si une action a été effectuée (à l'appelant de faire le st.rerun())."""
    fait = st.button(f"✅ Relance effectuée (reprogrammer +{jours_auto} j)",
                      key=f"{key_prefix}_fait", type="primary")
    with st.expander("📅 Date précise (offre avec engagement)"):
        date_cible = st.date_input(
            "Date de relance", value=datetime.now().date() + timedelta(days=jours_auto),
            key=f"{key_prefix}_date")
        programmer = st.button("Programmer cette date", key=f"{key_prefix}_prog")

    if fait:
        nv_date = datetime.now().date() + timedelta(days=jours_auto)
        maj_prospect(int(prospect_id), "date_relance", nv_date.strftime("%d/%m/%Y"))
        maj_prospect(int(prospect_id), "statut", "À relancer")
        enregistrer_action("prospect", int(prospect_id), "Relance effectuée",
                            f"Prochaine relance programmée au {nv_date.strftime('%d/%m/%Y')}")
        return True
    if programmer:
        maj_prospect(int(prospect_id), "date_relance", date_cible.strftime("%d/%m/%Y"))
        maj_prospect(int(prospect_id), "statut", "À relancer")
        enregistrer_action("prospect", int(prospect_id), "Relance programmée",
                            f"Prochaine relance programmée au {date_cible.strftime('%d/%m/%Y')}")
        return True
    return False


# ==============================================================================
#  SCORING — priorisation automatique des relances (économie, ancienneté du
#  dernier contact, satisfaction, intention de rester, type de client)
# ==============================================================================
SATISFACTION_BASSE = "😡 Pas du tout"

SEUIL_SCORE_CHAUD  = 150   # score >= ce seuil → 🔴 chaud
SEUIL_SCORE_TIEDE  = 60    # score >= ce seuil → 🟡 tiède (sinon 🟢 froid)


def _dates_dernier_contact() -> dict:
    """{prospect_id: datetime du dernier contact} d'après l'historique d'audit
    (relances effectuées/programmées) — une seule requête pour tous les prospects."""
    conn = get_conn()
    c    = conn.cursor()
    rows = c.execute(
        "SELECT entite_id, date_action FROM historique_actions WHERE entite_type='prospect'"
    ).fetchall()
    conn.close()
    derniers = {}
    for r in rows:
        try:
            dt = datetime.strptime(r["date_action"], "%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            continue
        pid = r["entite_id"]
        if pid not in derniers or dt > derniers[pid]:
            derniers[pid] = dt
    return derniers


def calculer_score_prospect(prospect, dernier_contact: datetime = None) -> float:
    """Score de priorité d'un prospect (plus il est élevé, plus la relance est
    urgente/rentable) :

        score = economie_estimee_an*2 + jours_depuis_dernier_contact*3
              + (satisfaction_basse ? +20 : 0) + (veut_rester ? -15 : 0)
              + (type_pro ? +10 : 0)

    `prospect` accepte tout objet indexable par nom de colonne (sqlite3.Row,
    pandas.Series, dict). Si `dernier_contact` n'est pas fourni, il est déduit
    de l'historique d'audit du prospect, ou à défaut de sa date de création.
    """
    def _val(champ):
        return prospect[champ] if champ in prospect.keys() else prospect.get(champ)

    economie = safe_float(_val("economie_estimee_an"))

    if dernier_contact is None:
        try:
            dernier_contact = datetime.strptime(_val("date_creation"), "%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            dernier_contact = None
    jours = max(0, (datetime.now() - dernier_contact).days) if dernier_contact else 0

    score  = (economie * 2) + (jours * 3)
    score += 20 if _val("satisfaction_reseau") == SATISFACTION_BASSE else 0
    score -= 15 if _val("veut_rester") == "Oui" else 0
    score += 10 if _val("type_client") == "Professionnel" else 0
    return round(score, 2)


def indicateur_score(score: float) -> str:
    """Étiquette visuelle de température de la relance à partir du score."""
    if score >= SEUIL_SCORE_CHAUD:
        return "🔴 chaud"
    if score >= SEUIL_SCORE_TIEDE:
        return "🟡 tiède"
    return "🟢 froid"


def recalculer_scores_prospects():
    """Recalcule et persiste (colonne `score`) le score de tous les prospects —
    à appeler avant chaque affichage des listes/relances triées par priorité."""
    conn = get_conn()
    c    = conn.cursor()
    prospects = c.execute("SELECT * FROM prospects").fetchall()
    derniers  = _dates_dernier_contact()
    for p in prospects:
        score = calculer_score_prospect(p, dernier_contact=derniers.get(p["id"]))
        c.execute("UPDATE prospects SET score=? WHERE id=?", (score, p["id"]))
    conn.commit()
    conn.close()
