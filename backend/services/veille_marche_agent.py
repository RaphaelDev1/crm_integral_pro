# ==============================================================================
#  VEILLE_MARCHE_AGENT — agent Claude autonome (boucle agentique tool-use,
#  même principe que backend/services/audit_agent.py) qui scanne le web une
#  fois par semaine, par catégorie IA Conseil, pour détecter des offres pas
#  encore présentes au catalogue `offre`. PLAN_IMPLEMENTATION_4_PHASES.md
#  §3.4.
#
#  Différence avec catalogue_engine.py (ingestion des sources déjà
#  configurées) et veille_souscriptions_engine.py (comparaison des
#  souscriptions actives au catalogue déjà connu) : ici l'agent découvre de
#  nouvelles offres sur le web ouvert (outil serveur `web_search`, exécuté
#  par Anthropic — pas de dispatch côté backend), sans source pré-configurée.
#
#  RÈGLE : comme audit_agent.py, aucun prix n'est inventé — une offre sans
#  prix clairement affiché sur la page trouvée est marquée confiance
#  'a_verifier' plutôt qu'un chiffre halluciné. N'écrit jamais directement
#  dans `offre` : chaque entrée détectée attend une revue admin (voir
#  routers/ia_conseil_catalogue.py::integrer_offre_veille_marche).
# ==============================================================================
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.ia_conseil import Categorie, Fournisseur, OffreConseil, RapportVeilleMarche

logger = logging.getLogger(__name__)

MODEL_DEFAUT = "claude-sonnet-5"
MAX_TOURS = 5
MAX_RECHERCHES = 8

SYSTEM_PROMPT = """Tu es l'agent de veille marché d'IA Conseil (cabinet de conseil en économies \
Mobile / Box / Énergie). Ta mission : chercher sur le web des offres commerciales actuellement \
disponibles dans la catégorie demandée qui ne figurent PAS déjà dans la liste des offres connues \
fournie, pour que l'équipe catalogue les intègre après vérification.

RÈGLE ABSOLUE : n'invente et n'estime JAMAIS un prix. Si le prix mensuel n'est pas clairement \
affiché sur la page que tu as consultée, laisse le champ prix_mensuel absent et mets confiance à \
"a_verifier". Chaque offre soumise doit citer l'URL de la page où tu l'as trouvée.

Démarche :
1. Utilise l'outil de recherche web pour identifier des offres actuelles de la catégorie demandée \
chez des fournisseurs pertinents (au moins 2-3 recherches ciblées : nom de fournisseurs connus du \
marché français + la catégorie, comparateurs, pages tarifs officielles).
2. Compare chaque offre trouvée à la liste des offres déjà connues (fournisseur + nom) — ignore \
celles qui correspondent déjà à une offre connue.
3. Termine TOUJOURS par un unique appel à l'outil `soumettre_rapport_veille`, avec la liste des \
offres nouvelles détectées (liste vide si aucune offre nouvelle trouvée — c'est un résultat valide, \
ne force pas des offres douteuses juste pour remplir la liste)."""

OUTIL_SOUMETTRE_RAPPORT = {
    "name": "soumettre_rapport_veille",
    "description": "Outil final : soumet le rapport de veille marché pour cette catégorie. À "
                    "appeler une seule fois, après avoir effectué les recherches nécessaires.",
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
                        "prix_mensuel": {
                            "type": "number",
                            "description": "Absent si le prix n'est pas clairement affiché — ne jamais deviner.",
                        },
                        "caracteristiques": {"type": "string", "description": "Résumé libre des caractéristiques principales."},
                        "url_source": {"type": "string"},
                        "confiance": {"type": "string", "enum": ["fiable", "a_verifier"]},
                    },
                    "required": ["fournisseur", "nom_offre", "url_source", "confiance"],
                },
            },
        },
        "required": ["offres"],
    },
}

TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_RECHERCHES},
    OUTIL_SOUMETTRE_RAPPORT,
]


def _debut_semaine(aujourdhui: date | None = None) -> date:
    jour = aujourdhui or date.today()
    return jour - timedelta(days=jour.weekday())


def _correspond_a_une_offre_connue(offre: dict, connues: set[tuple[str, str]]) -> bool:
    cle = ((offre.get("fournisseur") or "").strip().lower(), (offre.get("nom_offre") or "").strip().lower())
    return cle in connues


async def _offres_connues(db: AsyncSession, categorie_slug: str) -> set[tuple[str, str]]:
    result = await db.execute(
        select(OffreConseil.nom, Fournisseur.nom)
        .join(Fournisseur, OffreConseil.fournisseur_id == Fournisseur.id, isouter=True)
        .where(OffreConseil.categorie_slug == categorie_slug, OffreConseil.valide.is_(True))
    )
    return {((fournisseur or "").strip().lower(), (nom or "").strip().lower()) for nom, fournisseur in result.all()}


def _construire_message_utilisateur(categorie_slug: str, offres_connues: list[dict]) -> str:
    return (
        f"Catégorie à surveiller : {categorie_slug}.\n\n"
        "Offres déjà connues du catalogue (ne les re-soumets pas) :\n"
        + json.dumps(offres_connues, ensure_ascii=False)
        + "\n\nCherche des offres nouvelles de cette catégorie et soumets le rapport."
    )


async def generer_rapport_hebdomadaire(
    db: AsyncSession, categorie_slug: str, api_key: str | None = None, model: str = MODEL_DEFAUT,
) -> RapportVeilleMarche:
    """Point d'entrée principal : lance l'agent pour une catégorie, persiste
    un RapportVeilleMarche (offres_detectees vide si la clé API est absente,
    l'appel échoue, ou l'agent ne soumet aucune offre nouvelle — ne lève
    jamais d'exception, cohérent avec audit_agent.py/facture_analyzer.py)."""
    connues = await _offres_connues(db, categorie_slug)
    cle = api_key or settings.anthropic_api_key

    offres_detectees: list[dict] = []
    if not cle:
        logger.warning("ANTHROPIC_API_KEY absente — veille marché simulée (dev) pour %s.", categorie_slug)
    else:
        offres_connues_payload = [{"fournisseur": f, "nom_offre": n} for f, n in connues]
        messages = [{"role": "user", "content": _construire_message_utilisateur(categorie_slug, offres_connues_payload)}]
        try:
            client = anthropic.Anthropic(api_key=cle)
            soumission = None
            for _ in range(MAX_TOURS):
                response = client.messages.create(
                    model=model, max_tokens=4096, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
                )
                content_blocks = [(b.model_dump() if hasattr(b, "model_dump") else b) for b in response.content]
                messages.append({"role": "assistant", "content": content_blocks})

                tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]
                soumission_bloc = next((tu for tu in tool_uses if tu["name"] == "soumettre_rapport_veille"), None)
                if soumission_bloc is not None:
                    soumission = soumission_bloc.get("input", {})
                    break
                if not tool_uses:
                    break
                # Seuls des outils serveur (web_search) restent en jeu : rien à
                # dispatcher côté backend, l'API a déjà résolu leurs résultats
                # dans content_blocks — on relance simplement un tour.

            if soumission is not None:
                offres_brutes = soumission.get("offres") or []
                offres_detectees = [
                    o for o in offres_brutes
                    if isinstance(o, dict) and not _correspond_a_une_offre_connue(o, connues)
                ]
        except anthropic.APIError:
            logger.exception("Échec de la veille marché autonome pour %s.", categorie_slug)

    rapport = RapportVeilleMarche(
        categorie_slug=categorie_slug,
        semaine_debut=_debut_semaine(),
        offres_detectees=offres_detectees,
        statut="en_attente",
    )
    db.add(rapport)
    await db.flush()
    return rapport


async def generer_rapports_toutes_categories(
    db: AsyncSession, api_key: str | None = None, model: str = MODEL_DEFAUT,
) -> list[RapportVeilleMarche]:
    categories = (await db.execute(select(Categorie.slug).where(Categorie.actif.is_(True)))).scalars().all()
    rapports = [
        await generer_rapport_hebdomadaire(db, slug, api_key=api_key, model=model) for slug in categories
    ]
    await db.commit()
    return rapports
