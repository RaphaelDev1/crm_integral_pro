# ==============================================================================
#  TESTS — chatbot_engine.py (boucle agentique tool-use + finalisation)
# ==============================================================================
import chatbot_engine


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeMessages:
    def __init__(self, reponses):
        self._reponses = list(reponses)

    def create(self, **kwargs):
        return FakeResponse(self._reponses.pop(0))


class FakeAnthropicClient:
    def __init__(self, reponses):
        self.messages = FakeMessages(reponses)


def _patch_claude(monkeypatch, reponses):
    monkeypatch.setattr(chatbot_engine, "ANTHROPIC_OK", True)
    monkeypatch.setattr(chatbot_engine, "lire_parametre", lambda cle, defaut="": "fake-key")
    monkeypatch.setattr(
        chatbot_engine.anthropic, "Anthropic", lambda api_key: FakeAnthropicClient(reponses)
    )
    monkeypatch.setattr(
        chatbot_engine, "notifier_nouveau_prospect_chatbot", lambda *a, **k: False
    )


def test_maj_infos_puis_finalisation_cree_le_prospect(tmp_db, monkeypatch):
    reponses = [
        [{"type": "tool_use", "id": "tu1", "name": "maj_infos", "input": {
            "prenom": "Jean", "nom": "Dupont", "telephone": "0601020304",
            "univers_interesse": ["Télécom"], "operateur_actuel": "Orange",
            "cout_mensuel_actuel": 40.0, "satisfaction_reseau": "😐 Ça va",
        }}],
        [{"type": "tool_use", "id": "tu2", "name": "finaliser_diagnostic", "input": {}}],
        [{"type": "text", "text": "Merci Jean, un conseiller va vous recontacter !"}],
    ]
    _patch_claude(monkeypatch, reponses)

    resultat = chatbot_engine.traiter_message("session-1", "Bonjour, je paie 40€/mois chez Orange")

    assert resultat["termine"] is True
    assert resultat["prospect_id"] is not None
    assert "recontacter" in resultat["reply"]

    conn = tmp_db.get_conn()
    row = conn.execute("SELECT * FROM prospects WHERE id=?", (resultat["prospect_id"],)).fetchone()
    conn.close()
    assert row is not None
    assert row["origine"] == "Chatbot"
    assert row["prenom"] == "Jean"
    assert row["cree_par"] == "Chatbot IA"


def test_session_persistee_et_reprise(tmp_db, monkeypatch):
    reponses = [[{"type": "text", "text": "Sur quel univers souhaitez-vous une étude ?"}]]
    _patch_claude(monkeypatch, reponses)

    resultat = chatbot_engine.traiter_message("session-2", "Bonjour")
    assert resultat["termine"] is False

    session = chatbot_engine._charger_session("session-2")
    assert session is not None
    assert session["statut"] == "en_cours"
    assert len(session["messages"]) == 2   # message utilisateur + réponse assistant


def test_sans_cle_api_renvoie_message_clair(tmp_db, monkeypatch):
    monkeypatch.setattr(chatbot_engine, "lire_parametre", lambda cle, defaut="": "")

    resultat = chatbot_engine.traiter_message("session-3", "Bonjour")

    assert resultat["termine"] is False
    assert resultat["prospect_id"] is None
    assert "pas configuré" in resultat["reply"]
