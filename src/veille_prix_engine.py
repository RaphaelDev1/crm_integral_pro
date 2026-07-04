# ==============================================================================
#  VEILLE PRIX (SCRAPING CONCURRENTIEL) — script autonome (cron / tâche planifiée)
#
#  Surveille les pages tarifs des opérateurs (Playwright, sans navigateur visible)
#  et détecte les changements de prix. Chaque changement crée une alerte en
#  attente : le catalogue n'est jamais modifié automatiquement, un admin doit
#  valider depuis Admin > 📈 Veille prix (cf. app.py) avant répercussion.
#
#  Utilisation :
#     python veille_prix_engine.py     # lance une vérification de toutes les
#                                       # sources actives + notifie l'admin
#
#  Planification Windows (Terminal) :
#     schtasks /create /tn "IA Conseil - Veille prix" /sc daily /st 07:00 ^
#       /tr "python C:\chemin\vers\src\veille_prix_engine.py"
#
#  Planification cron (Linux/macOS) :
#     0 7 * * *   cd /chemin/vers/src && python veille_prix_engine.py
# ==============================================================================
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from db import enregistrer_action, get_conn

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_OK = True
except Exception:
    PLAYWRIGHT_OK = False

# Tolérance en dessous de laquelle deux prix relevés sont considérés identiques
# (évite de créer une alerte pour un arrondi de centime sans intérêt).
SEUIL_ECART_PRIX = 0.01

_RE_PRIX = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*€|€\s*(\d{1,4}(?:[.,]\d{1,2})?)")


# ------------------------------------------------------------------------------
#  EXTRACTION DE PRIX DANS UN TEXTE (regex — pas de dépendance IA ici)
# ------------------------------------------------------------------------------
def extraire_prix(texte: str):
    """Cherche le premier montant en euros dans `texte` (ex. « 19,99 € »,
    « à partir de 24.99€ »). Renvoie un float ou None si aucun prix trouvé."""
    if not texte:
        return None
    m = _RE_PRIX.search(texte)
    if not m:
        return None
    brut = m.group(1) or m.group(2)
    try:
        return float(brut.replace(",", "."))
    except ValueError:
        return None


# ------------------------------------------------------------------------------
#  SOURCES SURVEILLÉES (CRUD)
# ------------------------------------------------------------------------------
def ajouter_source(d: dict) -> int:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO sources_veille
        (univers, categorie, fournisseur, nom_offre, offre_id, url, selecteur_prix,
         actif, dernier_prix, date_derniere_verif, date_creation)
        VALUES (?,?,?,?,?,?,?,1,NULL,NULL,?)
    """, (
        d.get("univers"), d.get("categorie"), d.get("fournisseur"), d.get("nom_offre"),
        d.get("offre_id"), d.get("url"), d.get("selecteur_prix"),
        datetime.now().strftime("%d/%m/%Y %H:%M"),
    ))
    conn.commit()
    sid = c.lastrowid
    conn.close()
    lire_sources.clear()
    return sid


@st.cache_data(ttl=60)
def lire_sources(actif_seulement: bool = False) -> pd.DataFrame:
    conn = get_conn()
    q    = "SELECT * FROM sources_veille"
    if actif_seulement:
        q += " WHERE actif=1"
    q += " ORDER BY fournisseur, nom_offre"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


def maj_source(sid: int, champ: str, valeur):
    champs_autorises = {"univers", "categorie", "fournisseur", "nom_offre", "offre_id",
                         "url", "selecteur_prix", "actif", "dernier_prix", "date_derniere_verif"}
    if champ not in champs_autorises:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE sources_veille SET {champ}=? WHERE id=?", (valeur, sid))
    conn.commit()
    conn.close()
    lire_sources.clear()


def supprimer_source(sid: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM sources_veille WHERE id=?", (sid,))
    c.execute("DELETE FROM veille_historique_prix WHERE source_id=?", (sid,))
    c.execute("DELETE FROM veille_alertes WHERE source_id=?", (sid,))
    conn.commit()
    conn.close()
    lire_sources.clear()


# ------------------------------------------------------------------------------
#  SCRAPING (Playwright headless)
# ------------------------------------------------------------------------------
def _recuperer_texte_page(url: str, selecteur: str, timeout_ms: int = 20000):
    """Ouvre `url` dans un Chromium headless et renvoie le texte de la première
    correspondance de `selecteur` (CSS). Isolée dans sa propre fonction pour
    pouvoir être simulée (monkeypatch) dans les tests sans navigateur réel.
    Renvoie None si Playwright est indisponible ou en cas d'échec réseau/sélecteur."""
    if not PLAYWRIGHT_OK:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                locator = page.locator(selecteur).first
                locator.wait_for(timeout=timeout_ms)
                return locator.inner_text()
            finally:
                browser.close()
    except Exception:
        return None


def scraper_source(source: dict):
    """Récupère et parse le prix courant d'une source surveillée. Renvoie un
    float ou None si la page/le sélecteur n'a pas produit de prix exploitable."""
    texte = _recuperer_texte_page(source["url"], source["selecteur_prix"])
    return extraire_prix(texte)


# ------------------------------------------------------------------------------
#  LANCEMENT DE LA VEILLE — relevé + détection de changement + alerte
# ------------------------------------------------------------------------------
def lancer_veille() -> list[dict]:
    """Relève le prix de chaque source active. Enregistre toujours le relevé
    dans l'historique (pour les tendances) ; crée une alerte 'en_attente'
    uniquement si le prix a changé depuis le dernier relevé connu. Ne modifie
    JAMAIS le catalogue directement — cf. valider_alerte(). Renvoie la liste
    des nouvelles alertes créées (pour notification admin)."""
    df = lire_sources(actif_seulement=True)
    nouvelles_alertes = []
    conn = get_conn()
    c    = conn.cursor()
    maintenant = datetime.now().strftime("%d/%m/%Y %H:%M")

    for _, s in df.iterrows():
        prix = scraper_source(s)
        if prix is None:
            continue

        c.execute("INSERT INTO veille_historique_prix (source_id, prix, date_releve) VALUES (?,?,?)",
                   (int(s["id"]), prix, maintenant))

        ancien_prix = s["dernier_prix"]
        ancien_prix = float(ancien_prix) if ancien_prix is not None and str(ancien_prix) != "nan" else None

        if ancien_prix is not None and abs(prix - ancien_prix) >= SEUIL_ECART_PRIX:
            c.execute("""
                INSERT INTO veille_alertes (source_id, ancien_prix, nouveau_prix, statut, date_detection)
                VALUES (?,?,?, 'en_attente', ?)
            """, (int(s["id"]), ancien_prix, prix, maintenant))
            nouvelles_alertes.append({
                "source_id": int(s["id"]), "fournisseur": s["fournisseur"],
                "nom_offre": s["nom_offre"], "ancien_prix": ancien_prix, "nouveau_prix": prix,
            })

        c.execute("UPDATE sources_veille SET dernier_prix=?, date_derniere_verif=? WHERE id=?",
                   (prix, maintenant, int(s["id"])))

    conn.commit()
    conn.close()
    lire_sources.clear()
    return nouvelles_alertes


# ------------------------------------------------------------------------------
#  HISTORIQUE DE PRIX (tendances)
# ------------------------------------------------------------------------------
def lire_historique_prix(source_id: int) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM veille_historique_prix WHERE source_id=? ORDER BY id ASC",
        conn, params=(source_id,))
    conn.close()
    return df


# ------------------------------------------------------------------------------
#  ALERTES — validation / rejet (mise à jour catalogue avec accord admin)
# ------------------------------------------------------------------------------
def lire_alertes(statut: str = "en_attente") -> pd.DataFrame:
    conn = get_conn()
    q = """
        SELECT a.*, s.fournisseur, s.nom_offre, s.univers, s.categorie, s.offre_id, s.url
        FROM veille_alertes a JOIN sources_veille s ON s.id = a.source_id
    """
    params = []
    if statut:
        q += " WHERE a.statut=?"
        params.append(statut)
    q += " ORDER BY a.id DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def valider_alerte(alerte_id: int, auteur: str = ""):
    """Applique le nouveau prix à l'offre du catalogue rattachée (si `offre_id`
    est renseigné sur la source) et marque l'alerte comme validée. Renvoie
    (ok: bool, message: str)."""
    from offres_engine import maj_offre

    conn = get_conn()
    c    = conn.cursor()
    row = c.execute("""
        SELECT a.*, s.offre_id, s.fournisseur, s.nom_offre FROM veille_alertes a
        JOIN sources_veille s ON s.id = a.source_id WHERE a.id=?
    """, (alerte_id,)).fetchone()
    conn.close()

    if row is None:
        return False, "Alerte introuvable."
    if row["statut"] != "en_attente":
        return False, "Cette alerte a déjà été traitée."

    if row["offre_id"]:
        maj_offre(int(row["offre_id"]), "prix_mensuel", float(row["nouveau_prix"]))
        enregistrer_action("offre", int(row["offre_id"]), "Prix mis à jour (veille)",
                            f"{row['fournisseur']} {row['nom_offre']} — "
                            f"{row['ancien_prix']:.2f} € → {row['nouveau_prix']:.2f} €")

    conn = get_conn()
    c    = conn.cursor()
    c.execute("UPDATE veille_alertes SET statut='validee', date_traitement=? WHERE id=?",
              (datetime.now().strftime("%d/%m/%Y %H:%M"), alerte_id))
    conn.commit()
    conn.close()
    return True, "Prix validé et répercuté au catalogue." if row["offre_id"] else "Alerte validée."


def rejeter_alerte(alerte_id: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("UPDATE veille_alertes SET statut='rejetee', date_traitement=? WHERE id=? AND statut='en_attente'",
              (datetime.now().strftime("%d/%m/%Y %H:%M"), alerte_id))
    conn.commit()
    conn.close()


def main():
    from notifications import notifier_changement_prix
    alertes = lancer_veille()
    if alertes:
        notifier_changement_prix(alertes)
    print(f"{len(alertes)} changement(s) de prix détecté(s).")


if __name__ == "__main__":
    main()
