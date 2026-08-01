# ==============================================================================
#  VEILLE PRIX — moteur de scraping concurrentiel, porté de
#  src/veille_prix_engine.py (script cron/schtasks autonome) vers un service
#  async déclenché par une tâche Celery Beat périodique
#  (backend/workers/tasks.py::lancer_veille_periodique).
#
#  Surveille les pages tarifs des opérateurs (Playwright, navigateur headless)
#  et détecte les changements de prix. Chaque changement crée une alerte en
#  attente : le catalogue n'est jamais modifié automatiquement, un admin doit
#  la valider (voir `valider_alerte`) avant répercussion.
# ==============================================================================
from __future__ import annotations

import logging
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.offre import Offre
from backend.models.veille import SourceVeille, VeilleAlerte, VeilleHistoriquePrix

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_OK = True
except Exception:
    PLAYWRIGHT_OK = False

logger = logging.getLogger(__name__)

# Tolérance en dessous de laquelle deux prix relevés sont considérés identiques
# (évite de créer une alerte pour un arrondi de centime sans intérêt).
SEUIL_ECART_PRIX = 0.01

_RE_PRIX = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*€|€\s*(\d{1,4}(?:[.,]\d{1,2})?)")

_MAINTENANT = lambda: datetime.now().strftime("%d/%m/%Y %H:%M")  # noqa: E731


# ------------------------------------------------------------------------------
#  EXTRACTION DE PRIX DANS UN TEXTE (regex — pas de dépendance IA ici)
# ------------------------------------------------------------------------------
def extraire_prix(texte: str | None) -> float | None:
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
#  SCRAPING (Playwright headless, async)
# ------------------------------------------------------------------------------
async def _recuperer_texte_page(url: str, selecteur: str, timeout_ms: int = 20000) -> str | None:
    """Ouvre `url` dans un Chromium headless et renvoie le texte de la première
    correspondance de `selecteur` (CSS). Renvoie None si Playwright est
    indisponible ou en cas d'échec réseau/sélecteur."""
    if not PLAYWRIGHT_OK:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                locator = page.locator(selecteur).first
                await locator.wait_for(timeout=timeout_ms)
                return await locator.inner_text()
            finally:
                await browser.close()
    except Exception:
        logger.exception("Échec du scraping de %s.", url)
        return None


async def scraper_source(source: SourceVeille) -> float | None:
    """Récupère et parse le prix courant d'une source surveillée. Renvoie un
    float ou None si la page/le sélecteur n'a pas produit de prix exploitable."""
    texte = await _recuperer_texte_page(source.url, source.selecteur_prix)
    return extraire_prix(texte)


# ------------------------------------------------------------------------------
#  LANCEMENT DE LA VEILLE — relevé + détection de changement + alerte
# ------------------------------------------------------------------------------
async def lancer_veille(db: AsyncSession) -> list[dict]:
    """Relève le prix de chaque source active. Enregistre toujours le relevé
    dans l'historique (pour les tendances) ; crée une alerte 'en_attente'
    uniquement si le prix a changé depuis le dernier relevé connu. Ne modifie
    JAMAIS le catalogue directement — cf. `valider_alerte`. Renvoie la liste
    des nouvelles alertes créées (pour la notification admin)."""
    sources = (
        await db.execute(select(SourceVeille).where(SourceVeille.actif.is_(True)))
    ).scalars().all()

    nouvelles_alertes: list[dict] = []
    maintenant = _MAINTENANT()

    for source in sources:
        prix = await scraper_source(source)
        if prix is None:
            continue

        db.add(VeilleHistoriquePrix(source_id=source.id, prix=prix, date_releve=maintenant))

        ancien_prix = source.dernier_prix
        if ancien_prix is not None and abs(prix - ancien_prix) >= SEUIL_ECART_PRIX:
            db.add(VeilleAlerte(
                source_id=source.id, ancien_prix=ancien_prix, nouveau_prix=prix,
                statut="en_attente", date_detection=maintenant,
            ))
            nouvelles_alertes.append({
                "source_id": source.id, "fournisseur": source.fournisseur,
                "nom_offre": source.nom_offre, "ancien_prix": ancien_prix, "nouveau_prix": prix,
            })

        source.dernier_prix = prix
        source.date_derniere_verif = maintenant

    await db.commit()
    return nouvelles_alertes


# ------------------------------------------------------------------------------
#  ALERTES — validation / rejet (mise à jour catalogue avec accord admin)
# ------------------------------------------------------------------------------
async def valider_alerte(db: AsyncSession, alerte_id: int) -> tuple[bool, str]:
    """Applique le nouveau prix à l'offre du catalogue rattachée (si `offre_id`
    est renseigné sur la source) et marque l'alerte comme validée. Renvoie
    (ok, message)."""
    alerte = await db.get(VeilleAlerte, alerte_id)
    if alerte is None:
        return False, "Alerte introuvable."
    if alerte.statut != "en_attente":
        return False, "Cette alerte a déjà été traitée."

    source = await db.get(SourceVeille, alerte.source_id)
    if source is not None and source.offre_id:
        offre = await db.get(Offre, source.offre_id)
        if offre is not None:
            offre.prix_mensuel = alerte.nouveau_prix
            offre.date_maj = datetime.now().strftime("%d/%m/%Y")

    alerte.statut = "validee"
    alerte.date_traitement = _MAINTENANT()
    await db.commit()
    return True, "Prix validé et répercuté au catalogue." if (source and source.offre_id) else "Alerte validée."


async def rejeter_alerte(db: AsyncSession, alerte_id: int) -> bool:
    alerte = await db.get(VeilleAlerte, alerte_id)
    if alerte is None or alerte.statut != "en_attente":
        return False
    alerte.statut = "rejetee"
    alerte.date_traitement = _MAINTENANT()
    await db.commit()
    return True
