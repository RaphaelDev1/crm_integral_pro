# ==============================================================================
#  PROSPECTS
# ==============================================================================
import json
import secrets
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from db import get_conn, enregistrer_action
from utils import safe_float

TOKEN_DOCUMENTS_DUREE_JOURS = 14

CHAMPS_PROSPECT = {
    "telephone", "email", "operateur_actuel", "offre_actuelle", "cout_mensuel_actuel",
    "notes", "statut", "date_relance", "satisfaction_reseau", "veut_rester",
    "ville", "code_postal", "adresse", "prenom", "nom", "fournisseur_energie",
    "techno", "data_go", "speed_down", "speed_up", "type_client",
    "economie_estimee_an", "offres_interet", "date_fin_engagement",
}

# Catégorie Télécom correspondant au service principal déclaré par le prospect — c'est la
# seule catégorie pour laquelle cout_mensuel_actuel est une base de comparaison valable
# (cf. cout_reference_categorie).
CATEGORIE_PAR_SERVICE_PRINCIPAL = {
    "Mobile uniquement": "Mobile",
    "Box / Fibre uniquement": "Box / Fibre",
    "Pack Box + Mobile": "Pack Box + Mobile",
    "Multi-lignes": "Multi-lignes",
}


def _iter_contrats(contrats):
    """Accepte indifféremment un DataFrame (lire_contrats_prospect) ou une liste de dicts
    (pratique pour les tests) — évite d'imposer pandas partout où cout_reference_categorie
    est appelée."""
    if contrats is None:
        return
    if hasattr(contrats, "iterrows"):
        for _, row in contrats.iterrows():
            yield row
        return
    yield from contrats


def cout_reference_categorie(offre: dict, prospect: dict, contrats_prospect=None) -> float | None:
    """Coût actuel de référence pour calculer l'économie d'une offre « intéresse le client »,
    selon son univers :
      - Télécom : si la catégorie de l'offre correspond au service principal déclaré par le
        prospect (ex. « Mobile uniquement » → catégorie « Mobile »), cout_mensuel_actuel est
        une vraie base de comparaison. Sinon (offre cross-sell — ex. Box proposée à un
        prospect qui n'a donné que son mobile), ce coût n'a rien à voir avec ce nouveau
        service : on cherche un contrat déjà connu du prospect dans la même catégorie
        (ajouté par le conseiller au fil des infos récoltées, cf. contrats_engine.
        lire_contrats_prospect). Sans ce contrat, aucune économie ne peut être calculée
        honnêtement — on renvoie None plutôt qu'un chiffre trompeur.
      - Énergie / Abonnements : chaque catégorie a déjà son propre coût réel sur le profil.
    """
    univers = offre.get("univers")
    categorie = offre.get("categorie")
    if univers == "Télécom":
        if categorie == CATEGORIE_PAR_SERVICE_PRINCIPAL.get(prospect.get("service_principal")):
            return safe_float(prospect.get("cout_mensuel_actuel"))
        for ct in _iter_contrats(contrats_prospect):
            if ct.get("categorie") == categorie:
                return safe_float(ct.get("cout_mensuel"))
        return None
    if univers == "Énergie":
        return safe_float(prospect.get("cout_gaz")) if "Gaz" in (categorie or "") \
            else safe_float(prospect.get("cout_elec"))
    if univers == "Abonnements":
        try:
            abos = json.loads(prospect.get("abonnements") or "[]")
        except Exception:
            abos = []
        match = next((a for a in abos if a.get("nom") == categorie), None)
        return safe_float(match.get("cout")) if match else None
    return None


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
    # Les tokens_prospects portent une FK NOT NULL vers prospects(id) : les
    # supprimer d'abord, sinon la suppression du prospect échoue avec
    # "FOREIGN KEY constraint failed" dès qu'un lien documents/facture a été
    # généré pour ce prospect (cf. creer_token_documents).
    c.execute("DELETE FROM tokens_prospects WHERE prospect_id=?", (pid,))
    c.execute("DELETE FROM prospects WHERE id=?", (pid,))
    conn.commit()
    conn.close()


def definir_backend_client_id(pid: int, backend_id: int):
    """Mémorise l'id du client miroir créé côté backend/ (Postgres) pour ce prospect SQLite —
    équivalent de clients_engine.definir_backend_client_id, nécessaire pour permettre à un
    prospect (pas encore converti en client) d'avoir un dossier suivi côté backend/ (stepper +
    mandats + historique). Voir src/api_client.py::_backend_client_id_pour."""
    conn = get_conn()
    c    = conn.cursor()
    c.execute("UPDATE prospects SET backend_client_id=? WHERE id=?", (backend_id, pid))
    conn.commit()
    conn.close()


# ==============================================================================
#  LIEN « ENVOYER FACTURE + TEST DE DÉBIT » — token à usage personnel, sans
#  login, donnant accès à la mini-page publique servie par chatbot_api.py
#  (GET /portail/{token}). Permet au prospect de transmettre lui-même sa
#  facture et un test de débit, au lieu que le conseiller les lui redemande
#  par téléphone (cf. notifications.envoyer_demande_documents_prospect).
# ==============================================================================
def creer_token_documents(prospect_id: int, duree_jours: int = TOKEN_DOCUMENTS_DUREE_JOURS) -> dict:
    """Génère un nouveau token (n'invalide pas les précédents) et le persiste."""
    token = secrets.token_urlsafe(24)
    maintenant = datetime.now()
    expiration = maintenant + timedelta(days=duree_jours)
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO tokens_prospects (prospect_id, token, date_creation, date_expiration)
        VALUES (?,?,?,?)
    """, (
        prospect_id, token,
        maintenant.strftime("%d/%m/%Y %H:%M"),
        expiration.strftime("%d/%m/%Y %H:%M"),
    ))
    conn.commit()
    conn.close()
    return {"token": token, "date_expiration": expiration.strftime("%d/%m/%Y %H:%M")}


def valider_token_documents(token: str):
    """Retourne le prospect (sqlite3.Row) correspondant si le token est valide
    (existe, non révoqué, non expiré), sinon None. Journalise l'utilisation."""
    conn = get_conn()
    c    = conn.cursor()
    ligne = c.execute("SELECT * FROM tokens_prospects WHERE token=?", (token,)).fetchone()
    if ligne is None or ligne["revoque"]:
        conn.close()
        return None
    try:
        expiration = datetime.strptime(ligne["date_expiration"], "%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        expiration = None
    if expiration is not None and datetime.now() > expiration:
        conn.close()
        return None

    c.execute("""
        UPDATE tokens_prospects SET nb_utilisations = nb_utilisations + 1,
               date_derniere_utilisation = ? WHERE id = ?
    """, (datetime.now().strftime("%d/%m/%Y %H:%M"), ligne["id"]))
    conn.commit()
    prospect = c.execute("SELECT * FROM prospects WHERE id=?", (ligne["prospect_id"],)).fetchone()
    conn.close()
    return prospect


RELANCE_JOURS_AVANT_ENGAGEMENT = 14


def date_relance_avant_engagement(date_fin_engagement, jours_avant: int = RELANCE_JOURS_AVANT_ENGAGEMENT,
                                   aujourdhui=None):
    """Date à laquelle relancer un prospect encore engagé, pour le recontacter en avance sur
    la fin de son engagement (le temps d'agir) plutôt que pile le jour J. Si l'échéance moins
    la marge tombe déjà dans le passé (engagement qui se termine bientôt ou saisi en retard),
    la relance est programmée aujourd'hui plutôt que dans le passé."""
    aujourdhui = aujourdhui or datetime.now().date()
    cible = date_fin_engagement - timedelta(days=jours_avant)
    return max(cible, aujourdhui)


def widget_relance(prospect_id, key_prefix: str, jours_auto: int = 7) -> bool:
    """UI de relance prospect : bouton principal « Relance effectuée » qui reprogramme
    automatiquement à +jours_auto (le prospect reste une urgence du jour tant qu'il n'est
    pas traité), + une option « Date de fin d'engagement » repliée pour les prospects encore
    engagés chez leur opérateur actuel — la relance est alors programmée automatiquement
    RELANCE_JOURS_AVANT_ENGAGEMENT jours avant cette échéance (cf. date_relance_avant_engagement),
    pour recontacter le prospect en temps utile plutôt qu'à une date arbitraire.
    Renvoie True si une action a été effectuée (à l'appelant de faire le st.rerun())."""
    fait = st.button(f"✅ Relance effectuée (reprogrammer +{jours_auto} j)",
                      key=f"{key_prefix}_fait", type="primary")
    with st.expander("📅 Date de fin d'engagement (contrat actuel du prospect)"):
        date_fin = st.date_input(
            "Date de fin d'engagement", value=datetime.now().date() + timedelta(days=jours_auto),
            key=f"{key_prefix}_date")
        st.caption(f"La relance sera programmée {RELANCE_JOURS_AVANT_ENGAGEMENT} jours avant cette date.")
        programmer = st.button("Programmer cette échéance", key=f"{key_prefix}_prog")

    if fait:
        nv_date = datetime.now().date() + timedelta(days=jours_auto)
        maj_prospect(int(prospect_id), "date_relance", nv_date.strftime("%d/%m/%Y"))
        maj_prospect(int(prospect_id), "statut", "À relancer")
        enregistrer_action("prospect", int(prospect_id), "Relance effectuée",
                            f"Prochaine relance programmée au {nv_date.strftime('%d/%m/%Y')}")
        return True
    if programmer:
        date_cible = date_relance_avant_engagement(date_fin)
        maj_prospect(int(prospect_id), "date_fin_engagement", date_fin.strftime("%d/%m/%Y"))
        maj_prospect(int(prospect_id), "date_relance", date_cible.strftime("%d/%m/%Y"))
        maj_prospect(int(prospect_id), "statut", "À relancer")
        enregistrer_action("prospect", int(prospect_id), "Relance programmée",
                            f"Fin d'engagement le {date_fin.strftime('%d/%m/%Y')} — "
                            f"relance programmée au {date_cible.strftime('%d/%m/%Y')}")
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


def expliquer_score_prospect(prospect, dernier_contact: datetime = None) -> list:
    """Détail des composantes du score (mêmes règles que `calculer_score_prospect`) sous forme
    de lignes lisibles, pour affichage au conseiller — évite de dupliquer la formule."""
    def _val(champ):
        return prospect[champ] if champ in prospect.keys() else prospect.get(champ)

    economie = safe_float(_val("economie_estimee_an"))

    if dernier_contact is None:
        try:
            dernier_contact = datetime.strptime(_val("date_creation"), "%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            dernier_contact = None
    jours = max(0, (datetime.now() - dernier_contact).days) if dernier_contact else 0

    lignes = [
        f"💰 Économie estimée : {economie:.0f} €/an × 2 = **{economie * 2:.0f} pts**",
        f"📅 Dernier contact il y a {jours} j × 3 = **{jours * 3:.0f} pts**",
    ]
    if _val("satisfaction_reseau") == SATISFACTION_BASSE:
        lignes.append("😡 Faible satisfaction réseau : **+20 pts**")
    if _val("veut_rester") == "Oui":
        lignes.append("🔒 Souhaite rester chez son opérateur actuel : **-15 pts**")
    if _val("type_client") == "Professionnel":
        lignes.append("💼 Client professionnel : **+10 pts**")
    lignes.append(
        f"Seuils : 🔴 chaud ≥ {SEUIL_SCORE_CHAUD} pts · 🟡 tiède ≥ {SEUIL_SCORE_TIEDE} pts · 🟢 froid en dessous"
    )
    return lignes


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
