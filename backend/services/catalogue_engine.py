# ==============================================================================
#  CATALOGUE AUTO-ALIMENTÉ (INGESTION D'OFFRES) — porté de
#  src/catalogue_engine.py (script cron autonome) vers un service async
#  déclenché par une tâche Celery Beat périodique
#  (backend/workers/tasks.py::ingerer_catalogue_periodique) ou manuellement
#  depuis Admin > Catalogue (backend/routers/catalogue.py).
#
#  À la différence de veille_engine.py (qui ne fait que suivre le prix d'une
#  offre déjà connue), ce module DÉCOUVRE de nouvelles offres : il récupère
#  des pages tarifs/flux, en extrait les offres via un LLM (Claude), les
#  normalise, les dédoublonne, puis les dépose dans `offres_staging`. Le
#  catalogue (`offres`) n'est JAMAIS modifié directement — un admin valide,
#  rejette ou fusionne chaque ligne (voir `valider_offre_staging`).
# ==============================================================================
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import unicodedata
import urllib.robotparser
from datetime import datetime
from urllib.parse import urlparse

import anthropic
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.catalogue_source import CatalogueSource
from backend.models.offre import Offre
from backend.models.offre_staging import OffreStaging
from backend.services import offres_engine

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except Exception:
    BS4_OK = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_OK = True
except Exception:
    PLAYWRIGHT_OK = False

logger = logging.getLogger(__name__)

USER_AGENT = "IAConseilBot/1.0 (+veille catalogue offres, respect robots.txt)"
TIMEOUT_S = 15
MAX_TENTATIVES = 3

MODELE_EXTRACTION = "claude-haiku-4-5-20251001"

CATEGORIES_TELECOM = ["Mobile", "Box / Fibre", "Pack Box + Mobile", "Multi-lignes"]
CATEGORIES_ENERGIE = ["Électricité", "Gaz", "Électricité Pro", "Gaz Pro"]
CATEGORIES_ABO = ["Streaming Vidéo", "Musique", "Salle de sport", "SaaS / Logiciel", "Assurance", "Autre"]
LISTE_OPERATEURS_TEL = ["Orange", "YouPrice (Réseau Orange)", "SFR", "Bouygues", "Free", "Autre / Aucun"]
LISTE_FOURNISSEURS_ENERGIE = ["EDF", "Engie", "TotalEnergies", "Eni", "Vattenfall", "Ekwateur", "OHM Énergie", "Autre / Aucun"]

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
#  RÉCUPÉRATION DE PAGE (httpx d'abord, repli Playwright si JS requis)
# ------------------------------------------------------------------------------
async def _recuperer_page(url: str, methode: str = "requests", timeout_s: int = TIMEOUT_S) -> str | None:
    """Récupère le HTML brut de `url`. Renvoie None en cas d'échec après
    retries."""
    if methode == "playwright":
        return await _recuperer_page_playwright(url, timeout_s)

    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for tentative in range(MAX_TENTATIVES):
            try:
                r = await client.get(url, headers=headers)
                if r.status_code == 200:
                    return r.text
            except httpx.HTTPError:
                pass
            if tentative < MAX_TENTATIVES - 1:
                await asyncio.sleep(2 ** tentative)
    return None


async def _recuperer_page_playwright(url: str, timeout_s: int = TIMEOUT_S) -> str | None:
    if not PLAYWRIGHT_OK:
        return None
    timeout_ms = timeout_s * 1000
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=USER_AGENT)
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                return await page.content()
            finally:
                await browser.close()
    except Exception:
        logger.exception("Échec de la récupération Playwright de %s.", url)
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
    (dicts). Échoue silencieusement ([]) si la clé est absente ou si la réponse
    n'est pas exploitable — même philosophie de repli que facture_analyzer.py.
    Ne renvoie jamais de prix inventé : si le LLM ne trouve pas de prix clair,
    prix_mensuel vaut None (l'appelant route alors l'offre en statut 'a_verifier')."""
    cle = api_key or settings.anthropic_api_key
    if not cle or not texte:
        return []
    try:
        client = anthropic.Anthropic(api_key=cle)
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
        logger.exception("Échec de l'extraction LLM du catalogue pour la source %s.", source.get("url"))
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
    """Mappe les libellés fournisseur/catégorie vers les listes canoniques
    ci-dessus quand une correspondance existe ; conserve le libellé brut du
    LLM sinon (mieux vaut une valeur non standardisée que perdue)."""
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
#  INGESTION — fetch → extraction LLM → normalisation → dédoublonnage → staging
# ------------------------------------------------------------------------------
async def ingerer_source(db: AsyncSession, source_id: int, api_key: str = "") -> dict:
    """Ingère une source : renvoie un résumé {detectees, doublons, a_verifier,
    changements}. N'écrit jamais dans `offres` — uniquement dans
    `offres_staging`."""
    resume = {"detectees": 0, "doublons": 0, "a_verifier": 0, "changements": 0}

    source = await db.get(CatalogueSource, source_id)
    if source is None or not source.robots_ok:
        return resume

    html = await _recuperer_page(source.url, source.methode or "requests")
    if not html:
        return resume
    texte = html_vers_texte(html)
    offres_brutes = extraire_offres_llm(
        texte, {"univers": source.univers, "categorie": source.categorie}, api_key=api_key
    )

    maintenant = datetime.now().strftime("%d/%m/%Y %H:%M")

    for offre_brute in offres_brutes:
        offre = normaliser_offre(offre_brute, {"univers": source.univers, "categorie": source.categorie})
        prix_manquant = offre["prix_mensuel"] is None
        h = hash_contenu(offre)

        deja_staging = (await db.execute(
            select(OffreStaging).where(OffreStaging.hash_contenu == h, OffreStaging.statut == "en_attente")
        )).scalars().first()
        if deja_staging:
            resume["doublons"] += 1
            continue

        existante = (await db.execute(
            select(Offre).where(
                Offre.fournisseur == offre["fournisseur"], Offre.nom_offre == offre["nom_offre"], Offre.actif.is_(True)
            )
        )).scalars().first()

        offre_existante_id = None
        statut = "a_verifier" if prix_manquant else "en_attente"
        if existante is not None:
            ancien_prix = float(existante.prix_mensuel or 0)
            if not prix_manquant and abs(ancien_prix - float(offre["prix_mensuel"])) < 0.01:
                resume["doublons"] += 1
                continue
            offre_existante_id = existante.id
            statut = "en_attente"
            resume["changements"] += 1
        elif prix_manquant:
            resume["a_verifier"] += 1
        else:
            resume["detectees"] += 1

        db.add(OffreStaging(
            source_id=source.id, univers=offre["univers"], categorie=offre["categorie"],
            fournisseur=offre["fournisseur"], nom_offre=offre["nom_offre"], prix_mensuel=offre["prix_mensuel"],
            frais_activation=offre["frais_activation"], engagement_mois=offre["engagement_mois"],
            data_go=offre["data_go"], caracteristiques=offre["caracteristiques"],
            commission_affiliation=offre["commission_affiliation"], url_souscription=offre["url_souscription"],
            code_affiliation=offre["code_affiliation"], hash_contenu=h, statut=statut,
            confiance_llm=offre.get("confiance"), champs_incertains=offre.get("champs_incertains") or [],
            payload_brut=offre_brute, offre_existante_id=offre_existante_id, date_detection=maintenant,
        ))

    source.date_derniere_ingestion = maintenant
    await db.commit()
    return resume


async def ingerer_toutes_sources_actives(db: AsyncSession, api_key: str = "") -> dict:
    """Ingère toutes les sources actives et agrège les résumés."""
    sources = (await db.execute(select(CatalogueSource).where(CatalogueSource.actif.is_(True)))).scalars().all()
    total = {"detectees": 0, "doublons": 0, "a_verifier": 0, "changements": 0}
    for source in sources:
        r = await ingerer_source(db, source.id, api_key=api_key)
        for k in total:
            total[k] += r[k]
    return total


# ------------------------------------------------------------------------------
#  OFFRES DÉTECTÉES — validation / rejet
# ------------------------------------------------------------------------------
async def valider_offre_staging(db: AsyncSession, staging_id: int) -> tuple[bool, str]:
    """Copie l'offre en staging vers le catalogue : met à jour l'offre
    existante si `offre_existante_id` est renseigné (cas 'changement'), sinon
    crée une nouvelle offre. Renvoie (ok, message)."""
    staging = await db.get(OffreStaging, staging_id)
    if staging is None:
        return False, "Offre en attente introuvable."
    if staging.statut not in ("en_attente", "a_verifier"):
        return False, "Cette offre a déjà été traitée."

    if staging.offre_existante_id:
        await offres_engine.maj_offre(db, staging.offre_existante_id, "prix_mensuel", float(staging.prix_mensuel or 0))
        message = "Prix mis à jour sur l'offre existante."
    else:
        await offres_engine.ajouter_offre(db, {
            "univers": staging.univers, "categorie": staging.categorie, "fournisseur": staging.fournisseur,
            "nom_offre": staging.nom_offre, "prix_mensuel": staging.prix_mensuel or 0.0,
            "frais_activation": staging.frais_activation or 0.0, "engagement_mois": staging.engagement_mois or 0,
            "caracteristiques": staging.caracteristiques, "commission_affiliation": staging.commission_affiliation or 0.0,
            "data_go": staging.data_go or 0.0, "url_souscription": staging.url_souscription or "",
            "code_affiliation": staging.code_affiliation or "",
        })
        message = "Nouvelle offre ajoutée au catalogue."

    staging.statut = "validee"
    staging.date_traitement = datetime.now().strftime("%d/%m/%Y %H:%M")
    await db.commit()
    return True, message


async def rejeter_offre_staging(db: AsyncSession, staging_id: int) -> bool:
    staging = await db.get(OffreStaging, staging_id)
    if staging is None or staging.statut not in ("en_attente", "a_verifier"):
        return False
    staging.statut = "rejetee"
    staging.date_traitement = datetime.now().strftime("%d/%m/%Y %H:%M")
    await db.commit()
    return True
