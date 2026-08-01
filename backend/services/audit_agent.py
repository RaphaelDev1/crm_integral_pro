# ==============================================================================
#  AGENT D'AUDIT AUTONOME — boucle agentique Claude (tool-use), porté de
#  src/audit_agent.py vers un service async utilisable par
#  backend/routers/audit_agent.py.
#
#  RÈGLE NON NÉGOCIABLE : le LLM ne calcule et n'affirme JAMAIS un montant.
#  Il choisit quels outils appeler (avec quels paramètres) et rédige
#  l'explication ; chaque chiffre affiché provient d'un appel réel à une
#  fonction déjà testée (offres_engine.comparer_offres, cout_reference_categorie…).
#  La traçabilité n'est pas non plus rédigée par le LLM : elle est reconstruite
#  par ce module à partir du journal réel des appels d'outils effectués
#  pendant la boucle — un offre_id que le LLM soumettrait sans être passé par
#  `comparer_offres` est ignoré.
#
#  Écart assumé vs. src/audit_agent.py : l'outil `extraire_facture` n'est pas
#  porté — dans le nouveau parcours, la situation est toujours déjà collectée
#  par le wizard Diagnostic (frontend-conseiller) avant que l'agent ne soit
#  invoqué, contrairement au flux legacy où l'agent pouvait recevoir du texte
#  brut de facture.
# ==============================================================================
from __future__ import annotations

import json
import logging
from collections import defaultdict

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.client import Client
from backend.models.prospect import Prospect
from backend.services import offres_engine

logger = logging.getLogger(__name__)

MODEL_DEFAUT = "claude-sonnet-5"
MAX_TOURS = 8

SATISFACTION_SCORE = {"😀 Très content": 3, "😐 Ça va": 2, "😡 Pas du tout": 1}

CATEGORIE_PAR_SERVICE_PRINCIPAL = {
    "Mobile uniquement": "Mobile",
    "Box / Fibre uniquement": "Box / Fibre",
    "Pack Box + Mobile": "Pack Box + Mobile",
    "Multi-lignes": "Multi-lignes",
}

SYSTEM_PROMPT = """Tu es l'agent d'audit interne d'IA Conseil (cabinet de conseil en économies \
Télécom / Énergie / Abonnements). Ta mission : produire une recommandation chiffrée, sourcée et \
argumentée à partir de la situation d'un client, déjà collectée par un conseiller.

RÈGLE ABSOLUE, NON NÉGOCIABLE : tu n'as PAS le droit de calculer, estimer ou affirmer toi-même un \
montant en euros (prix, économie, coût). Chaque chiffre affiché DOIT provenir d'un appel à l'un des \
outils ci-dessous. Tu choisis quels outils appeler, avec quels paramètres, et tu rédiges \
l'explication — jamais les chiffres eux-mêmes.

Démarche :
1. Pour chaque univers concerné par la situation (Télécom, Énergie, Abonnements), appelle \
`comparer_offres` avec la bonne catégorie et le coût actuel mensuel fourni.
2. Si une offre envisagée est un cross-sell (catégorie différente du service télécom principal du \
client), appelle `cout_reference_categorie` avec son offre_id pour vérifier qu'une base de \
comparaison fiable existe avant de la recommander. Si elle renvoie null, NE recommande PAS cette \
offre — signale-le dans points_attention plutôt que d'inventer un chiffre.
3. Si une ville est renseignée et que le client n'est pas pleinement satisfait de son opérateur \
actuel, appelle `couverture_reseau` pour enrichir ton argumentaire (satisfaction/débit constatés \
localement par d'autres clients).
4. Termine TOUJOURS par un unique appel à l'outil `soumettre_audit`, avec les offre_id retenus \
(exclusivement ceux renvoyés par `comparer_offres`) et, pour chacun, une explication (`pourquoi`) qui \
cite sa source. Ajoute les points d'attention pertinents (client qui veut rester chez son opérateur, \
aucune offre disponible, base de comparaison manquante…) et un niveau de confiance global (0 à 1).

N'invente jamais un offre_id qui ne vient pas d'un appel à `comparer_offres`. Ne recalcule jamais une \
économie toi-même : le total est calculé automatiquement à partir des offres que tu retiens."""

TOOLS = [
    {
        "name": "comparer_offres",
        "description": "Renvoie les offres du catalogue triées par économie annuelle décroissante "
                        "pour un univers/catégorie donnés, comparées à un coût mensuel actuel. Chaque "
                        "offre renvoyée inclut son offre_id (champ id) et sa source.",
        "input_schema": {
            "type": "object",
            "properties": {
                "univers": {"type": "string", "enum": ["Télécom", "Énergie", "Abonnements"]},
                "categorie": {"type": "string"},
                "cout_actuel_mensuel": {"type": "number"},
                "fournisseur_exclu": {"type": "string"},
                "data_go_min": {"type": "number"},
            },
            "required": ["univers", "categorie", "cout_actuel_mensuel"],
        },
    },
    {
        "name": "cout_reference_categorie",
        "description": "Vérifie s'il existe une base de comparaison fiable pour une offre déjà "
                        "renvoyée par comparer_offres — indispensable avant de recommander une offre "
                        "cross-sell (catégorie différente du service principal du client). Renvoie "
                        "cout_reference=null si aucune base fiable n'existe : dans ce cas, ne "
                        "recommande pas cette offre.",
        "input_schema": {
            "type": "object",
            "properties": {"offre_id": {"type": "integer"}},
            "required": ["offre_id"],
        },
    },
    {
        "name": "couverture_reseau",
        "description": "Renvoie la satisfaction réseau moyenne et les débits mesurés par opérateur "
                        "pour une ville donnée (autres prospects/clients connus).",
        "input_schema": {
            "type": "object",
            "properties": {"ville": {"type": "string"}},
            "required": ["ville"],
        },
    },
    {
        "name": "soumettre_audit",
        "description": "Outil final : soumet la recommandation d'audit. À appeler une seule fois, "
                        "après avoir consulté les outils nécessaires. N'invente aucun offre_id : "
                        "utilise uniquement ceux renvoyés par comparer_offres.",
        "input_schema": {
            "type": "object",
            "properties": {
                "situation_detectee": {"type": "string"},
                "offres_retenues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "offre_id": {"type": "integer"},
                            "pourquoi": {"type": "string"},
                        },
                        "required": ["offre_id", "pourquoi"],
                    },
                },
                "points_attention": {"type": "array", "items": {"type": "string"}},
                "niveau_confiance": {"type": "number"},
            },
            "required": ["situation_detectee", "offres_retenues"],
        },
    },
]


def safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def economie_totale_groupee(items: list[dict]) -> float:
    """Économie annuelle totale d'une liste d'offres retenues : par (univers,
    catégorie), on ne retient que la meilleure offre, puis on additionne
    entre catégories différentes (gains réellement cumulables)."""
    par_groupe: dict[tuple, float] = {}
    for it in items:
        cle = (it.get("univers"), it.get("categorie"))
        eco = safe_float(it.get("economie_annuelle"))
        par_groupe[cle] = max(par_groupe.get(cle, 0.0), eco)
    return round(sum(max(0.0, v) for v in par_groupe.values()), 2)


# ------------------------------------------------------------------------------
#  OUTILS — wrappers minces autour des services backend existants, chacun sourcé
# ------------------------------------------------------------------------------
async def outil_comparer_offres(
    db: AsyncSession, univers, categorie, cout_actuel_mensuel,
    fournisseur_exclu=None, data_go_min=None,
) -> list[dict]:
    offres = await offres_engine.comparer_offres(
        db, univers, categorie, cout_actuel_mensuel,
        fournisseur_exclu=fournisseur_exclu, data_go_min=data_go_min,
    )
    return [{**o, "source": f"offre catalogue id={o['id']}"} for o in offres]


def outil_cout_reference_categorie(offre: dict, situation: dict, contrats: list[dict] | None = None) -> dict:
    """Coût actuel de référence pour calculer l'économie d'une offre, selon
    son univers :
      - Télécom : si la catégorie de l'offre correspond au service principal
        déclaré par le client, cout_mensuel_actuel est une vraie base de
        comparaison. Sinon (offre cross-sell), on cherche un contrat déjà
        connu du client dans la même catégorie ; sans lui, aucune économie ne
        peut être calculée honnêtement — on renvoie None plutôt qu'un chiffre
        trompeur.
      - Énergie / Abonnements : chaque catégorie a déjà son propre coût réel
        directement dans la situation collectée par le wizard."""
    univers = offre.get("univers")
    categorie = offre.get("categorie")

    if univers == "Télécom":
        if categorie == CATEGORIE_PAR_SERVICE_PRINCIPAL.get(situation.get("service_principal")):
            source = "cout_mensuel_actuel déclaré par le client (service télécom principal)"
            return {"cout_reference": safe_float(situation.get("cout_mensuel_actuel")), "source": source}
        for ct in (contrats or []):
            if ct.get("categorie") == categorie:
                return {
                    "cout_reference": safe_float(ct.get("cout_mensuel")),
                    "source": f"contrat existant du client dans la catégorie « {categorie} »",
                }
        return {"cout_reference": None, "source": "aucune base de comparaison connue pour cette catégorie"}

    if univers == "Énergie":
        valeur = situation.get("cout_gaz") if "Gaz" in (categorie or "") else situation.get("cout_elec")
        return {"cout_reference": safe_float(valeur), "source": "coût déclaré par le client pour cette catégorie"}

    if univers == "Abonnements":
        abos = situation.get("abonnements") or []
        match = next((a for a in abos if a.get("categorie") == categorie), None)
        if match is None:
            return {"cout_reference": None, "source": "aucun abonnement de cette catégorie déclaré par le client"}
        return {"cout_reference": safe_float(match.get("cout")), "source": f"abonnement « {match.get('nom', categorie)} » déclaré par le client"}

    return {"cout_reference": None, "source": "aucune base de comparaison connue pour cette catégorie"}


async def outil_couverture_reseau(db: AsyncSession, ville: str) -> dict:
    if not ville or not ville.strip():
        return {"satisfaction": [], "debit": [], "source": "ville non renseignée"}
    ville_norm = ville.strip()

    lignes = []
    for Modele in (Prospect, Client):
        resultat = await db.execute(
            select(Modele.operateur_actuel, Modele.satisfaction_reseau, Modele.speed_down, Modele.speed_up)
            .where(Modele.ville.ilike(ville_norm))
        )
        lignes.extend(resultat.all())

    pertinentes = [l for l in lignes if l.operateur_actuel and l.operateur_actuel != "Autre / Aucun"]

    scores_par_operateur: dict[str, list[int]] = defaultdict(list)
    for l in pertinentes:
        score = SATISFACTION_SCORE.get(l.satisfaction_reseau)
        if score is not None:
            scores_par_operateur[l.operateur_actuel].append(score)
    satisfaction = sorted(
        (
            {"operateur": op, "note_moyenne": round(sum(scores) / len(scores), 2), "nb_avis": len(scores)}
            for op, scores in scores_par_operateur.items()
        ),
        key=lambda d: d["note_moyenne"], reverse=True,
    )

    debits_par_operateur: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for l in pertinentes:
        down, up = safe_float(l.speed_down), safe_float(l.speed_up)
        if down > 0 or up > 0:
            debits_par_operateur[l.operateur_actuel].append((down, up))
    debit = sorted(
        (
            {
                "operateur": op,
                "debit_down_moyen": round(sum(d for d, _ in valeurs) / len(valeurs), 1),
                "debit_up_moyen": round(sum(u for _, u in valeurs) / len(valeurs), 1),
                "nb_mesures": len(valeurs),
            }
            for op, valeurs in debits_par_operateur.items()
        ),
        key=lambda d: d["debit_down_moyen"], reverse=True,
    )

    return {"satisfaction": satisfaction, "debit": debit, "source": f"moyenne des prospects/clients enregistrés à {ville_norm}"}


# ------------------------------------------------------------------------------
#  DISPATCH — exécute un outil demandé par le LLM et journalise l'appel
# ------------------------------------------------------------------------------
def _retrouver_offre(journal: list, offre_id) -> dict | None:
    if offre_id is None:
        return None
    try:
        offre_id = int(offre_id)
    except (TypeError, ValueError):
        return None
    for entree in journal:
        if entree["outil"] == "comparer_offres":
            for o in entree["sortie"]:
                if int(o["id"]) == offre_id:
                    return o
    return None


async def _executer_tool_audit(
    db: AsyncSession, nom: str, entree: dict, journal: list, situation: dict, contrats: list[dict] | None = None,
) -> dict:
    if nom == "comparer_offres":
        sortie = await outil_comparer_offres(
            db, entree.get("univers"), entree.get("categorie"),
            safe_float(entree.get("cout_actuel_mensuel")),
            fournisseur_exclu=entree.get("fournisseur_exclu") or None,
            data_go_min=entree.get("data_go_min"),
        )
    elif nom == "cout_reference_categorie":
        offre = _retrouver_offre(journal, entree.get("offre_id")) or {}
        sortie = outil_cout_reference_categorie(offre, situation, contrats)
    elif nom == "couverture_reseau":
        sortie = await outil_couverture_reseau(db, entree.get("ville") or situation.get("ville", ""))
    else:
        sortie = {"erreur": f"outil inconnu : {nom}"}
    journal.append({"outil": nom, "entree": entree, "sortie": sortie})
    return sortie


# ------------------------------------------------------------------------------
#  ASSEMBLAGE DU RÉSULTAT — jamais de montant qui ne vienne pas du journal
# ------------------------------------------------------------------------------
def _clamp01(v) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


def _resultat_vide(message: str) -> dict:
    return {
        "situation_detectee": "", "offres_recommandees": [], "economie_totale_an": 0.0,
        "points_attention": [message], "niveau_confiance": 0.0, "tracabilite": [],
    }


def _assembler_resultat(soumission: dict, journal: list) -> dict:
    offres_recommandees = []
    for item in (soumission.get("offres_retenues") or []):
        offre = _retrouver_offre(journal, item.get("offre_id"))
        if offre is None:
            continue  # offre_id inconnu/halluciné par le LLM : ignoré, jamais affiché
        offres_recommandees.append({
            "offre": offre,
            "economie_an": offre.get("economie_annuelle", 0) or 0,
            "pourquoi": str(item.get("pourquoi", ""))[:500],
            "source": offre.get("source", ""),
        })

    economie_totale_an = economie_totale_groupee([r["offre"] for r in offres_recommandees])

    return {
        "situation_detectee": str(soumission.get("situation_detectee", ""))[:1000],
        "offres_recommandees": offres_recommandees,
        "economie_totale_an": economie_totale_an,
        "points_attention": [str(p)[:300] for p in (soumission.get("points_attention") or [])][:10],
        "niveau_confiance": _clamp01(soumission.get("niveau_confiance")),
        "tracabilite": journal,
    }


def valider_audit_result(d: dict) -> bool:
    """Vérifie que le résultat a la forme attendue avant retour HTTP."""
    if not isinstance(d, dict):
        return False
    champs_requis = {"situation_detectee", "offres_recommandees", "economie_totale_an",
                      "points_attention", "niveau_confiance", "tracabilite"}
    if not champs_requis.issubset(d.keys()):
        return False
    if not isinstance(d["offres_recommandees"], list) or not isinstance(d["points_attention"], list):
        return False
    try:
        return 0.0 <= float(d["niveau_confiance"]) <= 1.0
    except (TypeError, ValueError):
        return False


# ------------------------------------------------------------------------------
#  ORCHESTRATION — boucle agentique Claude (tool-use)
# ------------------------------------------------------------------------------
def _construire_message_utilisateur(situation: dict) -> str:
    return (
        "Voici la situation du client, telle que collectée par le conseiller. Utilise les outils "
        "pour construire une recommandation chiffrée et sourcée :\n\n"
        + json.dumps(situation, ensure_ascii=False, default=str)
    )


async def lancer_audit(
    db: AsyncSession, situation: dict, contrats: list[dict] | None = None,
    api_key: str | None = None, model: str = MODEL_DEFAUT,
) -> dict:
    """Point d'entrée principal : produit un AuditResult (dict) à partir de la
    situation déjà collectée par le conseiller (wizard Diagnostic). Ne lève
    jamais d'exception : toute erreur produit un résultat vide avec un
    message clair dans points_attention."""
    cle = api_key or settings.anthropic_api_key
    if not cle:
        if settings.is_production:
            return _resultat_vide("L'audit automatique n'est pas configuré (clé API Anthropic manquante).")
        logger.warning("ANTHROPIC_API_KEY absente — audit automatique simulé (dev).")
        return _resultat_vide("L'audit automatique n'est pas configuré (clé API Anthropic manquante).")

    journal: list = []
    messages = [{"role": "user", "content": _construire_message_utilisateur(situation)}]
    soumission = None

    try:
        client = anthropic.Anthropic(api_key=cle)
        for _ in range(MAX_TOURS):
            response = client.messages.create(
                model=model, max_tokens=2048, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
            )
            content_blocks = [
                (b.model_dump() if hasattr(b, "model_dump") else b) for b in response.content
            ]
            messages.append({"role": "assistant", "content": content_blocks})

            tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]
            if not tool_uses:
                break

            soumission_bloc = next((tu for tu in tool_uses if tu["name"] == "soumettre_audit"), None)
            if soumission_bloc is not None:
                soumission = soumission_bloc.get("input", {})
                break

            tool_results = []
            for tu in tool_uses:
                sortie = await _executer_tool_audit(db, tu["name"], tu.get("input", {}), journal, situation, contrats)
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu["id"],
                    "content": json.dumps(sortie, ensure_ascii=False, default=str),
                })
            messages.append({"role": "user", "content": tool_results})
    except anthropic.APIError as exc:
        logger.exception("Échec de l'audit automatique.")
        return _resultat_vide(f"Erreur lors de l'audit automatique : {exc}")

    if soumission is None:
        return _resultat_vide("L'agent n'a pas produit de recommandation exploitable (limite de tours atteinte).")

    return _assembler_resultat(soumission, journal)
