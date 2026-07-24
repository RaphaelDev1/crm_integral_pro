# ==============================================================================
#  AGENT D'AUDIT AUTONOME — boucle agentique Claude (tool-use)
#
#  Assemble les briques existantes (comparaison d'offres, base de comparaison
#  cross-sell, couverture réseau, calcul d'économie) en un seul pipeline :
#  situation client → recommandation chiffrée, sourcée, argumentée.
#
#  RÈGLE NON NÉGOCIABLE : le LLM ne calcule et n'affirme JAMAIS un montant.
#  Il choisit quels outils appeler (avec quels paramètres) et rédige
#  l'explication ; chaque chiffre affiché provient d'un appel réel à une
#  fonction Python déjà testée (offres_engine.comparer_offres, utils.
#  economie_totale_groupee…). La traçabilité n'est pas non plus rédigée par le
#  LLM : elle est reconstruite par ce module à partir du journal réel des
#  appels d'outils effectués pendant la boucle — un offre_id que le LLM
#  soumettrait sans être passé par `comparer_offres` est ignoré.
#
#  Même architecture que chatbot_engine.traiter_message() (boucle tool-use
#  avec garde-fou de tours), appliquée ici à l'audit plutôt qu'à la collecte.
# ==============================================================================
import json

try:
    import anthropic
    ANTHROPIC_OK = True
except Exception:
    ANTHROPIC_OK = False

import secrets_config
from clients_engine import meilleur_debit_par_zone, note_couverture_par_zone
from offres_engine import comparer_offres, lire_offres
from pdf_engine import analyser_facture
from prospects_engine import CATEGORIE_PAR_SERVICE_PRINCIPAL, cout_reference_categorie
from utils import economie_totale_groupee, safe_float

MODEL_DEFAUT = "claude-sonnet-5"
MAX_TOURS = 8

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
        "name": "extraire_facture",
        "description": "Extrait opérateur/fournisseur/prix/data à partir du texte brut d'une facture "
                        "(usage ponctuel : la situation fournie a en général déjà été extraite).",
        "input_schema": {
            "type": "object",
            "properties": {"texte_facture": {"type": "string"}},
            "required": ["texte_facture"],
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


# ------------------------------------------------------------------------------
#  OUTILS — wrappers minces autour du code métier existant, chacun sourcé
# ------------------------------------------------------------------------------
def outil_comparer_offres(univers, categorie, cout_actuel_mensuel,
                           fournisseur_exclu=None, data_go_min=None) -> list[dict]:
    offres = comparer_offres(univers, categorie, cout_actuel_mensuel,
                              fournisseur_exclu=fournisseur_exclu, data_go_min=data_go_min)
    if not offres:
        return []
    df = lire_offres(univers=univers, categorie=categorie, actif_seulement=True)
    dates_maj = {int(r["id"]): r["date_maj"] for _, r in df.iterrows()} if not df.empty else {}
    resultat = []
    for o in offres:
        o = dict(o)
        o["source"] = f"offre catalogue id={o['id']}, maj le {dates_maj.get(o['id'], '?')}"
        resultat.append(o)
    return resultat


def outil_cout_reference_categorie(offre: dict, situation: dict, contrats=None) -> dict:
    valeur = cout_reference_categorie(offre, situation, contrats)
    if valeur is None:
        source = "aucune base de comparaison connue pour cette catégorie (ni cout_mensuel_actuel, ni contrat existant)"
    elif offre.get("categorie") == CATEGORIE_PAR_SERVICE_PRINCIPAL.get(situation.get("service_principal")):
        source = "cout_mensuel_actuel déclaré par le client (service télécom principal)"
    else:
        source = f"contrat existant du prospect dans la catégorie « {offre.get('categorie')} »"
    return {"cout_reference": valeur, "source": source}


def outil_couverture_reseau(ville: str) -> dict:
    if not ville:
        return {"satisfaction": [], "debit": [], "source": "ville non renseignée"}
    df_sat = note_couverture_par_zone(ville)
    df_deb = meilleur_debit_par_zone(ville)
    return {
        "satisfaction": df_sat.to_dict("records") if not df_sat.empty else [],
        "debit": df_deb.to_dict("records") if not df_deb.empty else [],
        "source": f"moyenne des prospects/clients enregistrés à {ville}",
    }


def outil_calcul_economie(offres_choisies: list[dict]) -> dict:
    total = economie_totale_groupee(offres_choisies)
    return {"economie_totale_an": total,
            "source": "utils.economie_totale_groupee (meilleure offre par univers/catégorie, sommée)"}


def outil_extraire_facture(texte_facture: str) -> dict:
    resultat = dict(analyser_facture(texte_facture))
    resultat["source"] = "extraction regex sur texte de facture (pdf_engine.analyser_facture)"
    return resultat


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


def _executer_tool_audit(nom: str, entree: dict, journal: list, situation: dict, contrats=None) -> dict:
    if nom == "comparer_offres":
        sortie = outil_comparer_offres(
            entree.get("univers"), entree.get("categorie"),
            safe_float(entree.get("cout_actuel_mensuel")),
            fournisseur_exclu=entree.get("fournisseur_exclu") or None,
            data_go_min=entree.get("data_go_min"),
        )
    elif nom == "cout_reference_categorie":
        offre = _retrouver_offre(journal, entree.get("offre_id")) or {}
        sortie = outil_cout_reference_categorie(offre, situation, contrats)
    elif nom == "couverture_reseau":
        sortie = outil_couverture_reseau(entree.get("ville") or situation.get("ville", ""))
    elif nom == "extraire_facture":
        sortie = outil_extraire_facture(entree.get("texte_facture", ""))
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
    """Vérifie que le résultat a la forme attendue avant affichage/restitution."""
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
#  ORCHESTRATION — boucle agentique Claude (tool-use), même pattern que
#  chatbot_engine.traiter_message()
# ------------------------------------------------------------------------------
def _construire_message_utilisateur(situation: dict) -> str:
    return (
        "Voici la situation du client, telle que collectée par le conseiller. Utilise les outils "
        "pour construire une recommandation chiffrée et sourcée :\n\n"
        + json.dumps(situation, ensure_ascii=False, default=str)
    )


def lancer_audit(situation: dict, contrats=None, api_key: str = "", model: str = MODEL_DEFAUT) -> dict:
    """Point d'entrée principal : produit un AuditResult (dict) à partir de la situation
    déjà collectée par le conseiller (mêmes champs que ceux utilisés par
    construire_recommandations/comparer_offres dans le wizard). Ne lève jamais d'exception :
    toute erreur produit un résultat vide avec un message clair dans points_attention."""
    if not api_key:
        api_key = secrets_config.anthropic_api_key()
    if not ANTHROPIC_OK or not api_key:
        return _resultat_vide("L'audit automatique n'est pas configuré (clé API Anthropic manquante).")

    journal: list = []
    messages = [{"role": "user", "content": _construire_message_utilisateur(situation)}]
    soumission = None

    try:
        client = anthropic.Anthropic(api_key=api_key)
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
                sortie = _executer_tool_audit(tu["name"], tu.get("input", {}), journal, situation, contrats)
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu["id"],
                    "content": json.dumps(sortie, ensure_ascii=False, default=str),
                })
            messages.append({"role": "user", "content": tool_results})
    except Exception as e:
        return _resultat_vide(f"Erreur lors de l'audit automatique : {e}")

    if soumission is None:
        return _resultat_vide("L'agent n'a pas produit de recommandation exploitable "
                               "(limite de tours atteinte).")

    return _assembler_resultat(soumission, journal)
