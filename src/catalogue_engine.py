# ==============================================================================
#  CATALOGUE AUTO-ALIMENTÉ (INGESTION D'OFFRES) — script autonome (cron / tâche planifiée)
#
#  À la différence de veille_prix_engine.py (qui ne fait que suivre le prix
#  d'une offre déjà connue), ce module DÉCOUVRE de nouvelles offres : il
#  récupère des pages tarifs/flux, en extrait les offres via un LLM (Claude),
#  les normalise, les dédoublonne, puis les dépose dans `offres_staging`.
#  Le catalogue (`offres`) n'est JAMAIS modifié directement — un admin valide,
#  rejette ou fusionne chaque ligne depuis Admin > 📚 Catalogue > Offres détectées.
#
#  Utilisation :
#     python catalogue_engine.py     # ingère toutes les sources actives et
#                                      # notifie l'admin si de nouvelles offres
#                                      # attendent une validation
#
#  Planification Windows (Terminal) :
#     schtasks /create /tn "IA Conseil - Catalogue" /sc daily /st 03:00 ^
#       /tr "python C:\chemin\vers\src\catalogue_engine.py"
#
#  Planification cron (Linux/macOS) :
#     0 3 * * *   cd /chemin/vers/src && python catalogue_engine.py
# ==============================================================================
import hashlib
import json
import re
import time
import unicodedata
import urllib.robotparser
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st

from constants import CATEGORIES_ABO, CATEGORIES_ENERGIE, CATEGORIES_TELECOM, LISTE_FOURNISSEURS_ENERGIE, LISTE_OPERATEURS_TEL
from db import enregistrer_action, get_conn

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except Exception:
    BS4_OK = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_OK = True
except Exception:
    PLAYWRIGHT_OK = False

try:
    import anthropic
    ANTHROPIC_OK = True
except Exception:
    ANTHROPIC_OK = False

USER_AGENT = "IAConseilBot/1.0 (+veille catalogue offres, respect robots.txt)"
TIMEOUT_S = 15
MAX_TENTATIVES = 3

MODELE_EXTRACTION = "claude-haiku-4-5-20251001"

CATEGORIES_PAR_UNIVERS = {
    "Télécom": CATEGORIES_TELECOM,
    "Énergie": CATEGORIES_ENERGIE,
    "Abonnements": CATEGORIES_ABO,
}
FOURNISSEURS_CONNUS = list(LISTE_OPERATEURS_TEL) + list(LISTE_FOURNISSEURS_ENERGIE)

PROMPT_EXTRACTION = (
    "Tu extrais des offres commerciales (télécom, énergie, abonnements) depuis le "
    "texte d'une page web fournie. Réponds UNIQUEMENT via l'outil `soumettre_offres`, "
    "avec une liste d'offres. Pour chaque offre : fournisseur, nom_offre, univers "
    "(Télécom/Énergie/Abonnements), categorie, prix_mensuel (nombre, en euros TTC/mois), "
    "frais_activation, engagement_mois, data_go (0 si non applicable), caracteristiques "
    "(texte court), url_souscription (si visible), confiance (0 à 1), champs_incertains "
    "(liste des noms de champs dont tu n'es pas sûr). IMPORTANT : si tu ne trouves AUCUN "
    "prix mensuel numérique clair pour une offre, mets prix_mensuel à null plutôt que "
    "d'inventer un chiffre — n'invente jamais de prix."
)

OUTIL_EXTRACTION = {
    "name": "soumettre_offres",
    "description": "Soumet la liste des offres commerciales extraites de la page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "offres": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "fournisseur": {"type": "string"},
                        "nom_offre": {"type": "string"},
                        "univers": {"type": "string"},
                        "categorie": {"type": "string"},
                        "prix_mensuel": {"type": ["number", "null"]},
                        "frais_activation": {"type": "number"},
                        "engagement_mois": {"type": "integer"},
                        "data_go": {"type": "number"},
                        "caracteristiques": {"type": "string"},
                        "url_souscription": {"type": "string"},
                        "confiance": {"type": "number"},
                        "champs_incertains": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["fournisseur", "nom_offre"],
                },
            },
        },
        "required": ["offres"],
    },
}


# ------------------------------------------------------------------------------
#  ROBOTS.TXT
# ------------------------------------------------------------------------------
def verifier_robots(url: str) -> bool:
    """Renvoie False si robots.txt interdit explicitement `url` pour notre agent
    (ou pour '*'). Renvoie True si robots.txt est absent/inaccessible (on ne
    bloque pas une source par excès de prudence sur une simple erreur réseau)."""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


# ------------------------------------------------------------------------------
#  RÉCUPÉRATION DE PAGE (requests d'abord, repli Playwright si JS requis)
# ------------------------------------------------------------------------------
def _recuperer_page(url: str, methode: str = "requests", timeout_s: int = TIMEOUT_S):
    """Récupère le HTML brut de `url`. Isolée dans sa propre fonction pour être
    simulée (monkeypatch) dans les tests sans requête réseau réelle. Renvoie
    None en cas d'échec après retries."""
    if methode == "playwright":
        return _recuperer_page_playwright(url, timeout_s)

    headers = {"User-Agent": USER_AGENT}
    for tentative in range(MAX_TENTATIVES):
        try:
            r = requests.get(url, headers=headers, timeout=timeout_s)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        if tentative < MAX_TENTATIVES - 1:
            time.sleep(2 ** tentative)
    return None


def _recuperer_page_playwright(url: str, timeout_ms_s: int = TIMEOUT_S):
    if not PLAYWRIGHT_OK:
        return None
    timeout_ms = timeout_ms_s * 1000
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                return page.content()
            finally:
                browser.close()
    except Exception:
        return None


def html_vers_texte(html: str) -> str:
    """Réduit une page HTML à son texte lisible avant envoi au LLM (évite de
    gaspiller des tokens sur les balises/scripts/styles)."""
    if not html:
        return ""
    if not BS4_OK:
        return re.sub(r"<[^>]+>", " ", html)
    soup = BeautifulSoup(html, "html.parser")
    for balise in soup(["script", "style", "noscript"]):
        balise.decompose()
    texte = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", texte).strip()


# ------------------------------------------------------------------------------
#  EXTRACTION LLM STRUCTURÉE (Claude, tool-use)
# ------------------------------------------------------------------------------
def extraire_offres_llm(texte: str, source: dict, api_key: str = "", model: str = MODELE_EXTRACTION) -> list[dict]:
    """Envoie `texte` (page tarifs) à Claude et renvoie une liste d'offres brutes
    (dicts). Échoue silencieusement ([]) si le package/la clé sont absents ou si
    la réponse n'est pas exploitable — même philosophie de repli que pdf_engine.py.
    Ne renvoie jamais de prix inventé : si le LLM ne trouve pas de prix clair,
    prix_mensuel vaut None (l'appelant route alors l'offre en statut 'a_verifier')."""
    if not ANTHROPIC_OK or not api_key or not texte:
        return []
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            tools=[OUTIL_EXTRACTION],
            tool_choice={"type": "tool", "name": "soumettre_offres"},
            messages=[{
                "role": "user",
                "content": f"{PROMPT_EXTRACTION}\n\nUnivers/catégorie attendus pour cette page : "
                           f"{source.get('univers')} / {source.get('categorie')}.\n\nTexte de la page :\n{texte[:15000]}",
            }],
        )
        for bloc in msg.content:
            if getattr(bloc, "type", "") == "tool_use" and bloc.name == "soumettre_offres":
                return bloc.input.get("offres", []) or []
    except Exception:
        return []
    return []


# ------------------------------------------------------------------------------
#  NORMALISATION & HASH
# ------------------------------------------------------------------------------
def _sans_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower().strip()


def _correspondance(libelle: str, liste_canonique: list[str]) -> str:
    """Cherche `libelle` dans `liste_canonique` en ignorant casse/accents.
    Renvoie le libellé canonique si trouvé, sinon `libelle` tel quel."""
    if not libelle:
        return libelle
    cible = _sans_accents(libelle)
    for candidat in liste_canonique:
        if _sans_accents(candidat) == cible:
            return candidat
    for candidat in liste_canonique:
        if cible in _sans_accents(candidat) or _sans_accents(candidat) in cible:
            return candidat
    return libelle


def normaliser_offre(offre_brute: dict, source: dict) -> dict:
    """Mappe les libellés fournisseur/catégorie vers les listes canoniques de
    constants.py quand une correspondance existe ; conserve le libellé brut
    du LLM sinon (mieux vaut une valeur non standardisée que perdue)."""
    univers = offre_brute.get("univers") or source.get("univers") or ""
    categories_univers = CATEGORIES_PAR_UNIVERS.get(univers, [])
    return {
        "univers": univers,
        "categorie": _correspondance(offre_brute.get("categorie") or source.get("categorie") or "", categories_univers),
        "fournisseur": _correspondance(offre_brute.get("fournisseur") or "", FOURNISSEURS_CONNUS),
        "nom_offre": offre_brute.get("nom_offre") or "",
        "prix_mensuel": offre_brute.get("prix_mensuel"),
        "frais_activation": offre_brute.get("frais_activation") or 0.0,
        "engagement_mois": offre_brute.get("engagement_mois") or 0,
        "data_go": offre_brute.get("data_go") or 0.0,
        "caracteristiques": offre_brute.get("caracteristiques") or "",
        "commission_affiliation": offre_brute.get("commission_affiliation") or 0.0,
        "url_souscription": offre_brute.get("url_souscription") or "",
        "code_affiliation": offre_brute.get("code_affiliation") or "",
        "confiance": offre_brute.get("confiance"),
        "champs_incertains": offre_brute.get("champs_incertains") or [],
    }


def hash_contenu(offre: dict) -> str:
    brut = f"{offre.get('fournisseur', '')}|{offre.get('nom_offre', '')}|" \
           f"{offre.get('prix_mensuel', '')}|{offre.get('engagement_mois', '')}"
    return hashlib.sha256(_sans_accents(brut).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------
#  SOURCES CATALOGUE (CRUD)
# ------------------------------------------------------------------------------
def ajouter_source_catalogue(d: dict) -> int:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO catalogue_sources
        (univers, categorie, fournisseur, url, type_source, methode, actif, robots_ok,
         frequence_h, date_derniere_ingestion, date_creation)
        VALUES (?,?,?,?,?,?,1,?,?,NULL,?)
    """, (
        d.get("univers"), d.get("categorie"), d.get("fournisseur"), d.get("url"),
        d.get("type_source", "page_officielle"), d.get("methode", "requests"),
        int(bool(verifier_robots(d.get("url", "")))), d.get("frequence_h", 24),
        datetime.now().strftime("%d/%m/%Y %H:%M"),
    ))
    conn.commit()
    sid = c.lastrowid
    conn.close()
    lire_sources_catalogue.clear()
    return sid


@st.cache_data(ttl=60)
def lire_sources_catalogue(actif_seulement: bool = False) -> pd.DataFrame:
    conn = get_conn()
    q    = "SELECT * FROM catalogue_sources"
    if actif_seulement:
        q += " WHERE actif=1"
    q += " ORDER BY univers, categorie, fournisseur"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


def maj_source_catalogue(sid: int, champ: str, valeur):
    champs_autorises = {"univers", "categorie", "fournisseur", "url", "type_source",
                         "methode", "actif", "robots_ok", "frequence_h", "date_derniere_ingestion"}
    if champ not in champs_autorises:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE catalogue_sources SET {champ}=? WHERE id=?", (valeur, sid))
    conn.commit()
    conn.close()
    lire_sources_catalogue.clear()


def supprimer_source_catalogue(sid: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM catalogue_sources WHERE id=?", (sid,))
    c.execute("DELETE FROM offres_staging WHERE source_id=?", (sid,))
    conn.commit()
    conn.close()
    lire_sources_catalogue.clear()


# ------------------------------------------------------------------------------
#  INGESTION — fetch → extraction LLM → normalisation → dédoublonnage → staging
# ------------------------------------------------------------------------------
def ingerer_source(source_id: int, api_key: str = "") -> dict:
    """Ingère une source : renvoie un résumé {detectees, doublons, a_verifier,
    changements}. N'écrit jamais dans `offres` — uniquement dans `offres_staging`."""
    resume = {"detectees": 0, "doublons": 0, "a_verifier": 0, "changements": 0}

    conn = get_conn()
    c    = conn.cursor()
    row = c.execute("SELECT * FROM catalogue_sources WHERE id=?", (source_id,)).fetchone()
    if row is None:
        conn.close()
        return resume
    source = dict(row)
    conn.close()

    if not source.get("robots_ok"):
        return resume

    html = _recuperer_page(source["url"], source.get("methode", "requests"))
    if not html:
        return resume
    texte = html_vers_texte(html)
    offres_brutes = extraire_offres_llm(texte, source, api_key=api_key)

    conn = get_conn()
    c    = conn.cursor()
    maintenant = datetime.now().strftime("%d/%m/%Y %H:%M")

    for offre_brute in offres_brutes:
        offre = normaliser_offre(offre_brute, source)
        prix_manquant = offre["prix_mensuel"] is None
        h = hash_contenu(offre)

        deja_staging = c.execute(
            "SELECT id FROM offres_staging WHERE hash_contenu=? AND statut='en_attente'", (h,)
        ).fetchone()
        if deja_staging:
            resume["doublons"] += 1
            continue

        existante = c.execute("""
            SELECT id, prix_mensuel FROM offres
            WHERE fournisseur=? AND nom_offre=? AND actif=1
        """, (offre["fournisseur"], offre["nom_offre"])).fetchone()

        offre_existante_id = None
        statut = "a_verifier" if prix_manquant else "en_attente"
        if existante:
            ancien_prix = float(existante["prix_mensuel"] or 0)
            if not prix_manquant and abs(ancien_prix - float(offre["prix_mensuel"])) < 0.01:
                resume["doublons"] += 1
                continue
            offre_existante_id = int(existante["id"])
            statut = "en_attente"
            resume["changements"] += 1
        elif prix_manquant:
            resume["a_verifier"] += 1
        else:
            resume["detectees"] += 1

        c.execute("""
            INSERT INTO offres_staging
            (source_id, univers, categorie, fournisseur, nom_offre, prix_mensuel,
             frais_activation, engagement_mois, data_go, caracteristiques,
             commission_affiliation, url_souscription, code_affiliation, hash_contenu,
             statut, confiance_llm, champs_incertains, payload_brut, offre_existante_id,
             date_detection)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            source_id, offre["univers"], offre["categorie"], offre["fournisseur"], offre["nom_offre"],
            offre["prix_mensuel"], offre["frais_activation"], offre["engagement_mois"], offre["data_go"],
            offre["caracteristiques"], offre["commission_affiliation"], offre["url_souscription"],
            offre["code_affiliation"], h, statut, offre.get("confiance"),
            json.dumps(offre.get("champs_incertains") or [], ensure_ascii=False),
            json.dumps(offre_brute, ensure_ascii=False, default=str), offre_existante_id, maintenant,
        ))

    c.execute("UPDATE catalogue_sources SET date_derniere_ingestion=? WHERE id=?", (maintenant, source_id))
    conn.commit()
    conn.close()
    return resume


def ingerer_toutes_sources_actives(api_key: str = "") -> dict:
    """Ingère toutes les sources actives et agrège les résumés. Notifie l'admin
    si au moins une offre attend une validation."""
    df = lire_sources_catalogue(actif_seulement=True)
    total = {"detectees": 0, "doublons": 0, "a_verifier": 0, "changements": 0}
    for sid in df["id"].tolist():
        r = ingerer_source(int(sid), api_key=api_key)
        for k in total:
            total[k] += r[k]
    return total


# ------------------------------------------------------------------------------
#  OFFRES DÉTECTÉES — validation / rejet
# ------------------------------------------------------------------------------
def lire_offres_staging(statut: str = "en_attente") -> pd.DataFrame:
    conn = get_conn()
    q = """
        SELECT s.*, cs.url AS source_url FROM offres_staging s
        LEFT JOIN catalogue_sources cs ON cs.id = s.source_id
    """
    params = []
    if statut:
        q += " WHERE s.statut=?"
        params.append(statut)
    q += " ORDER BY s.id DESC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def valider_offre_staging(staging_id: int, auteur: str = ""):
    """Copie l'offre en staging vers le catalogue : met à jour l'offre existante
    si `offre_existante_id` est renseigné (cas 'changement'), sinon crée une
    nouvelle offre. Renvoie (ok: bool, message: str)."""
    from offres_engine import ajouter_offre, maj_offre

    conn = get_conn()
    c    = conn.cursor()
    row = c.execute("SELECT * FROM offres_staging WHERE id=?", (staging_id,)).fetchone()
    conn.close()

    if row is None:
        return False, "Offre en attente introuvable."
    if row["statut"] not in ("en_attente", "a_verifier"):
        return False, "Cette offre a déjà été traitée."

    d = dict(row)
    if d["offre_existante_id"]:
        maj_offre(int(d["offre_existante_id"]), "prix_mensuel", float(d["prix_mensuel"]))
        enregistrer_action("offre", int(d["offre_existante_id"]), "Offre mise à jour (catalogue auto)",
                            f"{d['fournisseur']} {d['nom_offre']} — nouveau prix {d['prix_mensuel']:.2f} €")
        message = "Prix mis à jour sur l'offre existante."
    else:
        ajouter_offre({
            "univers": d["univers"], "categorie": d["categorie"], "fournisseur": d["fournisseur"],
            "nom_offre": d["nom_offre"], "prix_mensuel": d["prix_mensuel"] or 0.0,
            "frais_activation": d["frais_activation"] or 0.0, "engagement_mois": d["engagement_mois"] or 0,
            "caracteristiques": d["caracteristiques"], "commission_affiliation": d["commission_affiliation"] or 0.0,
            "data_go": d["data_go"] or 0.0, "url_souscription": d["url_souscription"] or "",
            "code_affiliation": d["code_affiliation"] or "",
        })
        enregistrer_action("offre", staging_id, "Nouvelle offre validée (catalogue auto)",
                            f"{d['fournisseur']} {d['nom_offre']}")
        message = "Nouvelle offre ajoutée au catalogue."

    conn = get_conn()
    c    = conn.cursor()
    c.execute("UPDATE offres_staging SET statut='validee', date_traitement=? WHERE id=?",
              (datetime.now().strftime("%d/%m/%Y %H:%M"), staging_id))
    conn.commit()
    conn.close()
    return True, message


def rejeter_offre_staging(staging_id: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        UPDATE offres_staging SET statut='rejetee', date_traitement=?
        WHERE id=? AND statut IN ('en_attente', 'a_verifier')
    """, (datetime.now().strftime("%d/%m/%Y %H:%M"), staging_id))
    conn.commit()
    conn.close()


def main():
    from notifications import notifier_nouvelles_offres_staging
    from secrets_config import anthropic_api_key

    resume = ingerer_toutes_sources_actives(api_key=anthropic_api_key())
    if resume["detectees"] or resume["a_verifier"] or resume["changements"]:
        notifier_nouvelles_offres_staging(resume)
    print(f"Ingestion catalogue terminée : {resume}")


if __name__ == "__main__":
    main()
