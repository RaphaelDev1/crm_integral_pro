# ==============================================================================
#  TESTS — services/copilot_engine.py (§3.2 : copilote conseiller streaming
#  SSE). Même idiome que les autres tests ia_conseil : asyncio.run(),
#  FakeSession, mock du client anthropic (pas d'appel réseau réel, pas de
#  vrai streaming HTTP).
# ==============================================================================
import asyncio
import uuid

import pytest

from backend.models.ia_conseil import OffreConseil, SessionTrame
from backend.services import copilot_engine as svc


def _run(coro):
    return asyncio.run(coro)


def test_prompts_charges_pour_les_3_modes():
    assert set(svc.PROMPTS.keys()) == set(svc.MODES)
    for mode, texte in svc.PROMPTS.items():
        assert texte.strip(), f"prompt vide pour le mode {mode}"


def test_mode_invalide_leve_une_erreur_explicite():
    with pytest.raises(svc.ModeInvalideError):
        list(svc.stream_copilot("mode_inconnu", {}, api_key="sk-test"))


def test_sans_cle_api_yield_un_evenement_error():
    evenements = list(svc.stream_copilot("suggestion", {"categorie": "mobile"}, api_key=""))
    assert len(evenements) == 1
    assert evenements[0].startswith("event: error\n")


# ------------------------------------------------------------------------------
#  construire_contexte
# ------------------------------------------------------------------------------
class FakeSession:
    pass


def _session_trame(reponses=None):
    return SessionTrame(id=uuid.uuid4(), categorie_slug="mobile", reponses=reponses or {"conso_data_go": 20})


def test_construire_contexte_reprend_reponses_et_top_offres(monkeypatch):
    offre = OffreConseil(id=uuid.uuid4(), nom="Eco 20Go", categorie_slug="mobile", prix_mensuel=15.0, caracteristiques={})

    async def _fake_calculer(_db, _session):
        return [{"offre": offre, "score": 90.0, "rang": 1, "justifications": [], "alertes": []}]
    monkeypatch.setattr(svc.engine, "calculer_recommandations", _fake_calculer)

    contexte = _run(svc.construire_contexte(FakeSession(), _session_trame()))
    assert contexte["categorie"] == "mobile"
    assert contexte["reponses"] == {"conso_data_go": 20}
    assert contexte["offres_candidates"] == [{"nom": "Eco 20Go", "prix_mensuel": 15.0, "score": 90.0}]


# ------------------------------------------------------------------------------
#  stream_copilot avec LLM mocké (streaming)
# ------------------------------------------------------------------------------
class _FakeStreamContext:
    def __init__(self, chunks):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        return iter(self._chunks)


class _FakeMessages:
    def __init__(self, chunks):
        self._chunks = chunks

    def stream(self, **_kwargs):
        return _FakeStreamContext(self._chunks)


class _FakeAnthropicClient:
    def __init__(self, chunks):
        self.messages = _FakeMessages(chunks)


def test_stream_copilot_yield_un_delta_par_chunk_puis_done(monkeypatch):
    monkeypatch.setattr(svc.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient(["Bonjour", ", posez ", "la question X."]))

    evenements = list(svc.stream_copilot("suggestion", {"categorie": "mobile"}, api_key="sk-test"))

    assert len(evenements) == 4  # 3 deltas + done
    assert all(e.startswith("event: delta\n") for e in evenements[:3])
    assert evenements[-1].startswith("event: done\n")
    assert "Bonjour" in evenements[0]


def test_stream_copilot_yield_error_si_appel_echoue(monkeypatch):
    class _ExplosiveClient:
        class messages:
            @staticmethod
            def stream(**_kwargs):
                raise svc.anthropic.APIError("boom", request=None, body=None)

    monkeypatch.setattr(svc.anthropic, "Anthropic", lambda api_key: _ExplosiveClient())

    evenements = list(svc.stream_copilot("incoherence", {"categorie": "mobile"}, api_key="sk-test"))
    assert len(evenements) == 1
    assert evenements[0].startswith("event: error\n")
