# ==============================================================================
#  CHATBOT — diagnostic conversationnel public (widget web), tool-use Claude
#
#  Indépendant de Streamlit (comme notifications.py) : importable et exécutable
#  depuis un process FastAPI séparé (voir chatbot_api.py). Pilote une conversation
#  en français qui collecte progressivement les mêmes champs que le wizard interne
#  (app.py, étapes 2-4), puis crée un prospect pré-qualifié via prospects_engine.
# ==============================================================================
import json
from datetime import datetime

try:
    import anthropic
    ANTHROPIC_OK = True
except Exception:
    ANTHROPIC_OK = False

from db import get_conn, lire_parametre, enregistrer_action
from utils import generer_ref, safe_float
from offres_engine import comparer_offres, construire_recommandations
from prospects_engine import ajouter_prospect
from notifications import notifier_nouveau_prospect_chatbot

MODEL_DEFAUT = "claude-sonnet-5"

SYSTEM_PROMPT = """Tu es l'assistant virtuel d'IA Conseil, un cabinet de conseil en économies \
Télécom / Énergie / Abonnements. Tu discutes en français, avec un ton chaleureux et concis, \
avec un prospect sur le site web du cabinet.

Ton objectif : faire un mini-diagnostic pour identifier des économies possibles, en posant \
UNE OU DEUX questions à la fois (jamais un long formulaire d'un coup). Dès qu'une information \
utile apparaît dans la réponse du client, appelle l'outil `maj_infos` pour l'enregistrer \
(même partiellement) — n'attends pas d'avoir tout pour l'appeler.

Informations à collecter, dans cet ordre :
1. Quel(s) univers intéresse(nt) le client : Télécom, Énergie et/ou Abonnements (univers_interesse).
2. Coordonnées : prénom, nom, téléphone ou email (au moins un des deux), ville et code postal.
3. Si Télécom : opérateur actuel (operateur_actuel), coût mensuel actuel (cout_mensuel_actuel), \
et son niveau de satisfaction (satisfaction_reseau : "😀 Très content", "😐 Ça va" ou "😡 Pas du tout").
4. Si Énergie : fournisseur actuel (fournisseur_energie), coût mensuel électricité (cout_elec) \
et/ou gaz (cout_gaz).

Quand tu as réuni les coordonnées minimales (prénom + téléphone ou email) et la situation \
actuelle pour au moins un univers choisi, résume ce que tu as compris et demande une \
confirmation. Une fois le client d'accord, appelle l'outil `finaliser_diagnostic` — ne \
l'appelle jamais avant confirmation explicite du client. Après cet appel, remercie le client \
et annonce qu'un conseiller va le recontacter avec une proposition chiffrée.

Ne donne jamais toi-même de chiffre d'économie ou de nom d'offre : seul le conseiller, après \
le diagnostic, communique ces informations."""

TOOLS = [
    {
        "name": "maj_infos",
        "description": "Enregistre ou met à jour les informations connues sur le prospect, "
                        "au fur et à mesure de la conversation. Appeler dès qu'une info apparaît.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prenom":              {"type": "string"},
                "nom":                 {"type": "string"},
                "telephone":           {"type": "string"},
                "email":               {"type": "string"},
                "ville":               {"type": "string"},
                "code_postal":         {"type": "string"},
                "type_client":         {"type": "string", "enum": ["Particulier", "Professionnel"]},
                "univers_interesse":   {"type": "array", "items": {
                    "type": "string", "enum": ["Télécom", "Énergie", "Abonnements"]}},
                "service_principal":   {"type": "string", "enum": [
                    "Mobile uniquement", "Box / Fibre uniquement", "Pack Box + Mobile", "Multi-lignes"]},
                "operateur_actuel":    {"type": "string"},
                "techno":              {"type": "string", "enum": ["FIBRE", "ADSL", "5G", "4G"]},
                "data_go":             {"type": "string"},
                "cout_mensuel_actuel": {"type": "number"},
                "satisfaction_reseau": {"type": "string", "enum": [
                    "😀 Très content", "😐 Ça va", "😡 Pas du tout"]},
                "veut_rester":         {"type": "string", "enum": ["Oui", "Non"]},
                "fournisseur_energie": {"type": "string"},
                "cout_elec":           {"type": "number"},
                "cout_gaz":            {"type": "number"},
            },
        },
    },
    {
        "name": "finaliser_diagnostic",
        "description": "Clôture la conversation et crée le prospect dans le CRM. "
                        "À appeler uniquement après confirmation explicite du client.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

_CHAMPS_MAJ_INFOS = {
    "prenom", "nom", "telephone", "email", "ville", "code_postal", "type_client",
    "univers_interesse", "service_principal", "operateur_actuel", "techno", "data_go",
    "cout_mensuel_actuel", "satisfaction_reseau", "veut_rester", "fournisseur_energie",
    "cout_elec", "cout_gaz",
}


# ------------------------------------------------------------------------------
#  PERSISTANCE DE SESSION (table chatbot_sessions)
# ------------------------------------------------------------------------------
def _charger_session(session_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM chatbot_sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "session_id": row["session_id"],
        "messages": json.loads(row["messages_json"] or "[]"),
        "donnees": json.loads(row["donnees_json"] or "{}"),
        "statut": row["statut"],
        "prospect_id": row["prospect_id"],
    }


def _creer_session(session_id: str) -> dict:
    conn = get_conn()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn.execute(
        "INSERT INTO chatbot_sessions (session_id, messages_json, donnees_json, statut, date_creation, date_maj) "
        "VALUES (?, '[]', '{}', 'en_cours', ?, ?)",
        (session_id, now, now),
    )
    conn.commit()
    conn.close()
    return {"session_id": session_id, "messages": [], "donnees": {}, "statut": "en_cours", "prospect_id": None}


def _sauvegarder_session(session: dict):
    conn = get_conn()
    conn.execute(
        "UPDATE chatbot_sessions SET messages_json=?, donnees_json=?, statut=?, prospect_id=?, date_maj=? "
        "WHERE session_id=?",
        (
            json.dumps(session["messages"], ensure_ascii=False),
            json.dumps(session["donnees"], ensure_ascii=False),
            session["statut"], session.get("prospect_id"),
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            session["session_id"],
        ),
    )
    conn.commit()
    conn.close()


# ------------------------------------------------------------------------------
#  FINALISATION — recommandations + création du prospect + notification conseiller
# ------------------------------------------------------------------------------
def _calculer_recommandations(donnees: dict):
    """Reproduit la logique de l'étape 4 du wizard interne (app.py) à partir des
    données collectées par le chatbot. Renvoie (recommandations, offres_interet, total_eco)."""
    recommandations, offres_interet, total_eco = [], [], 0.0
    univers = donnees.get("univers_interesse") or []

    if "Télécom" in univers and donnees.get("cout_mensuel_actuel"):
        cout_tel = safe_float(donnees.get("cout_mensuel_actuel"))
        fournisseur_exclu = None
        if (donnees.get("satisfaction_reseau") == "😡 Pas du tout"
                and donnees.get("operateur_actuel")):
            fournisseur_exclu = donnees["operateur_actuel"]
        reco = construire_recommandations(
            donnees.get("service_principal") or "Mobile uniquement", cout_tel,
            fournisseur_exclu=fournisseur_exclu,
            data_go_min=safe_float(donnees.get("data_go")) or None,
        )
        titre_p, offres_p = reco["principal"]
        categorie_p = titre_p.strip("📱🏠📦📲 ")
        if offres_p:
            meilleure = offres_p[0]
            offres_interet.append({"univers": "Télécom", "categorie": categorie_p, **meilleure})
            recommandations.append({"univers": "Télécom", "categorie": categorie_p,
                                     "cout_actuel": round(cout_tel, 2), "offre": meilleure})
            total_eco += meilleure.get("economie_annuelle", 0) or 0

    if "Énergie" in univers:
        for cat, champ in (("Électricité", "cout_elec"), ("Gaz", "cout_gaz")):
            cout = safe_float(donnees.get(champ))
            if cout <= 0:
                continue
            offres = comparer_offres("Énergie", cat, cout) or comparer_offres("Énergie", cat + " Pro", cout)
            if offres:
                meilleure = offres[0]
                offres_interet.append({"univers": "Énergie", "categorie": cat, **meilleure})
                recommandations.append({"univers": "Énergie", "categorie": cat,
                                         "cout_actuel": cout, "offre": meilleure})
                total_eco += meilleure.get("economie_annuelle", 0) or 0

    return recommandations, offres_interet, round(total_eco, 2)


def _finaliser_diagnostic(session: dict) -> int:
    donnees = session["donnees"]
    _, offres_interet, total_eco = _calculer_recommandations(donnees)

    infos_client = {
        "ref": generer_ref(),
        "prenom": donnees.get("prenom", ""),
        "nom": donnees.get("nom", ""),
        "telephone": donnees.get("telephone", ""),
        "email": donnees.get("email", ""),
        "code_postal": donnees.get("code_postal", ""),
        "ville": donnees.get("ville", ""),
        "type_client": donnees.get("type_client", "Particulier"),
        "univers_interesse": ", ".join(donnees.get("univers_interesse") or []),
        "service_principal": donnees.get("service_principal", ""),
        "operateur_actuel": donnees.get("operateur_actuel", ""),
        "techno": donnees.get("techno", ""),
        "data_go": donnees.get("data_go", ""),
        "cout_mensuel_actuel": safe_float(donnees.get("cout_mensuel_actuel")),
        "satisfaction_reseau": donnees.get("satisfaction_reseau", ""),
        "veut_rester": donnees.get("veut_rester", "Non"),
        "cout_elec": safe_float(donnees.get("cout_elec")),
        "cout_gaz": safe_float(donnees.get("cout_gaz")),
        "fournisseur_energie": donnees.get("fournisseur_energie", ""),
        "economie_estimee_an": total_eco,
        "notes": "Prospect créé automatiquement par le chatbot IA Conseil.",
        "cree_par": "Chatbot IA",
        "offres_interet": json.dumps(offres_interet, ensure_ascii=False),
        "origine": "Chatbot",
    }
    prospect_id = ajouter_prospect(infos_client)
    enregistrer_action("prospect", prospect_id, "Création via chatbot",
                        f"{infos_client['prenom']} {infos_client['nom']} — session {session['session_id']}")
    notifier_nouveau_prospect_chatbot(prospect_id, infos_client, total_eco)
    return prospect_id


# ------------------------------------------------------------------------------
#  ORCHESTRATION — boucle agentique Claude (tool-use)
# ------------------------------------------------------------------------------
def _executer_tool(nom: str, entree: dict, session: dict) -> str:
    if nom == "maj_infos":
        for champ, valeur in entree.items():
            if champ in _CHAMPS_MAJ_INFOS:
                session["donnees"][champ] = valeur
        return "Informations enregistrées."
    if nom == "finaliser_diagnostic":
        prospect_id = _finaliser_diagnostic(session)
        session["statut"] = "termine"
        session["prospect_id"] = prospect_id
        return f"Prospect #{prospect_id} créé avec succès dans le CRM."
    return "Outil inconnu."


def traiter_message(session_id: str, message_utilisateur: str, model: str = MODEL_DEFAUT) -> dict:
    """Point d'entrée principal du chatbot : fait progresser la conversation d'un tour,
    renvoie {session_id, reply, termine, prospect_id}. Ne lève jamais d'exception vers
    l'appelant HTTP — les erreurs de configuration/réseau produisent un message clair."""
    api_key = lire_parametre("anthropic_api_key", "")
    if not ANTHROPIC_OK or not api_key:
        return {
            "session_id": session_id,
            "reply": "Le chatbot n'est pas configuré (clé API Anthropic manquante côté Admin). "
                      "Merci de contacter directement le cabinet.",
            "termine": False, "prospect_id": None,
        }

    session = _charger_session(session_id) or _creer_session(session_id)
    if session["statut"] == "termine":
        return {"session_id": session_id,
                "reply": "Ce diagnostic est déjà terminé, un conseiller va vous recontacter.",
                "termine": True, "prospect_id": session.get("prospect_id")}

    session["messages"].append({"role": "user", "content": message_utilisateur})

    client = anthropic.Anthropic(api_key=api_key)
    reply_text = ""
    try:
        for _ in range(6):  # garde-fou : au plus 6 aller-retours d'outils par message utilisateur
            response = client.messages.create(
                model=model, max_tokens=1024, system=SYSTEM_PROMPT,
                tools=TOOLS, messages=session["messages"],
            )
            content_blocks = [
                (b.model_dump() if hasattr(b, "model_dump") else b) for b in response.content
            ]
            session["messages"].append({"role": "assistant", "content": content_blocks})

            tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]
            if not tool_uses:
                reply_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
                break

            tool_results = []
            for tu in tool_uses:
                resultat = _executer_tool(tu["name"], tu.get("input", {}), session)
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu["id"], "content": resultat,
                })
            session["messages"].append({"role": "user", "content": tool_results})
    except Exception as e:
        reply_text = f"Une erreur est survenue, merci de réessayer dans un instant. ({e})"

    _sauvegarder_session(session)
    return {
        "session_id": session_id, "reply": reply_text,
        "termine": session["statut"] == "termine", "prospect_id": session.get("prospect_id"),
    }
