# ==============================================================================
#  TESTS — services/ia_conseil_pdf.py, paragraphe de synthèse LLM (§3.3).
#  Même idiome que les autres tests ia_conseil : asyncio.run(), FakeSession
#  minimale, mock du client anthropic (pas d'appel réseau réel).
# ==============================================================================
import asyncio
import uuid

import pytest

from backend.models.ia_conseil import ClientConseil, OffreConseil, SessionTrame
from backend.services import ia_conseil_pdf as svc


def _run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self):
        self.committed = 0

    async def commit(self):
        self.committed += 1


def _client(prenom="Alice"):
    return ClientConseil(id=uuid.uuid4(), prenom=prenom, nom="Dupont")


def _session_trame(categorie="mobile", synthese=None):
    return SessionTrame(id=uuid.uuid4(), categorie_slug=categorie, synthese_llm_texte=synthese)


def _recommandation(nom="Eco 20Go", prix=15.0, eco_an=120.0):
    offre = OffreConseil(id=uuid.uuid4(), nom=nom, categorie_slug="mobile", prix_mensuel=prix, caracteristiques={})
    return {
        "offre": offre, "offre_id": offre.id, "score": 88.0, "rang": 1,
        "justifications": ["moins cher de 12EUR/mois"], "alertes": [],
        "economie_mensuelle": 10.0, "economie_annuelle": eco_an,
    }


# ------------------------------------------------------------------------------
#  _paragraphe_repli / generer_paragraphe_synthese (sans clé API)
# ------------------------------------------------------------------------------
def test_paragraphe_repli_sans_recommandation():
    texte = svc._paragraphe_repli(_client(), _session_trame(), [])
    assert "Alice" in texte or "Bonjour" in texte
    assert "Mobile" in texte


def test_paragraphe_repli_mentionne_offre_et_economie():
    texte = svc._paragraphe_repli(_client(), _session_trame(), [_recommandation()])
    assert "Eco 20Go" in texte
    assert "120" in texte


def test_generer_paragraphe_sans_cle_api_utilise_le_repli(monkeypatch):
    monkeypatch.setattr(svc.settings, "anthropic_api_key", "")
    texte = svc.generer_paragraphe_synthese(_client(), _session_trame(), [_recommandation()], api_key="")
    assert "Eco 20Go" in texte


# ------------------------------------------------------------------------------
#  generer_paragraphe_synthese avec LLM mocké
# ------------------------------------------------------------------------------
class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessages:
    def __init__(self, texte):
        self._texte = texte

    def create(self, **_kwargs):
        class _R:
            pass
        r = _R()
        r.content = [_FakeTextBlock(self._texte)]
        return r


class _FakeAnthropicClient:
    def __init__(self, texte):
        self.messages = _FakeMessages(texte)


def test_generer_paragraphe_utilise_le_texte_llm(monkeypatch):
    monkeypatch.setattr(svc.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient("Bonjour Alice, ..."))
    texte = svc.generer_paragraphe_synthese(_client(), _session_trame(), [_recommandation()], api_key="sk-test")
    assert texte == "Bonjour Alice, ..."


def test_generer_paragraphe_repli_si_appel_echoue(monkeypatch):
    class _ExplosiveClient:
        class messages:
            @staticmethod
            def create(**_kwargs):
                raise svc.anthropic.APIError("boom", request=None, body=None)

    monkeypatch.setattr(svc.anthropic, "Anthropic", lambda api_key: _ExplosiveClient())
    texte = svc.generer_paragraphe_synthese(_client(), _session_trame(), [_recommandation()], api_key="sk-test")
    assert "Eco 20Go" in texte  # repli, pas d'exception


# ------------------------------------------------------------------------------
#  Cache sur session.synthese_llm_texte
# ------------------------------------------------------------------------------
def test_generer_pdf_synthese_genere_et_met_en_cache_le_paragraphe(monkeypatch):
    monkeypatch.setattr(svc.settings, "anthropic_api_key", "")
    db = FakeSession()
    session = _session_trame(synthese=None)

    pdf_bytes = _run(svc.generer_pdf_synthese(db, _client(), session, [_recommandation()], None))

    assert isinstance(pdf_bytes, bytes) and len(pdf_bytes) > 0
    assert session.synthese_llm_texte  # rempli
    assert db.committed == 1


def test_generer_pdf_synthese_reutilise_le_cache_sans_recommitter(monkeypatch):
    monkeypatch.setattr(svc.settings, "anthropic_api_key", "")
    db = FakeSession()
    session = _session_trame(synthese="Texte déjà généré la semaine dernière.")

    _run(svc.generer_pdf_synthese(db, _client(), session, [_recommandation()], None))

    assert session.synthese_llm_texte == "Texte déjà généré la semaine dernière."
    assert db.committed == 0
