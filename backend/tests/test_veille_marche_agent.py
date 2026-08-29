# ==============================================================================
#  TESTS — services/veille_marche_agent.py (§3.4 : agent Claude autonome,
#  outil serveur web_search + outil custom soumettre_rapport_veille). Même
#  idiome que test_ia_conseil_engine.py/test_ia_conseil_facture.py :
#  FakeSession + asyncio.run(), mock du client anthropic.Anthropic (pas
#  d'appel réseau réel dans les tests).
# ==============================================================================
import asyncio
import uuid
from datetime import date

import pytest

from backend.models.ia_conseil import RapportVeilleMarche
from backend.services import veille_marche_agent as svc


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, execute_queue=None):
        self.execute_queue = execute_queue or []
        self.added = []
        self.committed = 0

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self.committed += 1


# ------------------------------------------------------------------------------
#  helpers purs
# ------------------------------------------------------------------------------
def test_debut_semaine_renvoie_le_lundi():
    # Jeudi 2026-08-27 -> lundi 2026-08-24
    assert svc._debut_semaine(date(2026, 8, 27)) == date(2026, 8, 24)


def test_correspond_a_une_offre_connue_insensible_a_la_casse():
    connues = {("orange", "forfait 100go")}
    assert svc._correspond_a_une_offre_connue({"fournisseur": "Orange", "nom_offre": "Forfait 100Go"}, connues)
    assert not svc._correspond_a_une_offre_connue({"fournisseur": "Free", "nom_offre": "Forfait 100Go"}, connues)


# ------------------------------------------------------------------------------
#  generer_rapport_hebdomadaire
# ------------------------------------------------------------------------------
def test_sans_cle_api_produit_un_rapport_vide(monkeypatch):
    monkeypatch.setattr(svc.settings, "anthropic_api_key", "")
    db = FakeSession(execute_queue=[[]])  # _offres_connues -> aucune ligne

    rapport = _run(svc.generer_rapport_hebdomadaire(db, "mobile", api_key=""))

    assert isinstance(rapport, RapportVeilleMarche)
    assert rapport.categorie_slug == "mobile"
    assert rapport.offres_detectees == []
    assert rapport.statut == "en_attente"
    assert db.added == [rapport]


class _FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, **_kwargs):
        return self._responses.pop(0)


class _FakeAnthropicClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


class _FakeResponse:
    def __init__(self, content):
        self.content = content


def test_soumission_filtre_les_offres_deja_connues(monkeypatch):
    # Une offre déjà connue (Orange / Forfait 100Go) + une offre nouvelle.
    db = FakeSession(execute_queue=[[("Forfait 100Go", "Orange")]])

    reponse = _FakeResponse([
        {
            "type": "tool_use", "id": "t1", "name": "soumettre_rapport_veille",
            "input": {
                "offres": [
                    {"fournisseur": "Orange", "nom_offre": "Forfait 100Go", "url_source": "https://orange.fr", "confiance": "fiable"},
                    {"fournisseur": "Free", "nom_offre": "Forfait 200Go", "prix_mensuel": 19.99, "url_source": "https://free.fr", "confiance": "fiable"},
                ],
            },
        },
    ])
    monkeypatch.setattr(svc.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient([reponse]))

    rapport = _run(svc.generer_rapport_hebdomadaire(db, "mobile", api_key="sk-test"))

    assert len(rapport.offres_detectees) == 1
    assert rapport.offres_detectees[0]["fournisseur"] == "Free"


def test_aucun_tool_use_produit_un_rapport_vide_sans_boucler_indefiniment(monkeypatch):
    db = FakeSession(execute_queue=[[]])
    reponse = _FakeResponse([{"type": "text", "text": "Rien trouvé."}])
    monkeypatch.setattr(svc.anthropic, "Anthropic", lambda api_key: _FakeAnthropicClient([reponse]))

    rapport = _run(svc.generer_rapport_hebdomadaire(db, "box", api_key="sk-test"))
    assert rapport.offres_detectees == []


def test_echec_api_ne_leve_jamais_et_produit_un_rapport_vide(monkeypatch):
    db = FakeSession(execute_queue=[[]])

    class _ExplosiveClient:
        class messages:
            @staticmethod
            def create(**_kwargs):
                raise svc.anthropic.APIError("boom", request=None, body=None)

    monkeypatch.setattr(svc.anthropic, "Anthropic", lambda api_key: _ExplosiveClient())

    rapport = _run(svc.generer_rapport_hebdomadaire(db, "energie_elec", api_key="sk-test"))
    assert rapport.offres_detectees == []
    assert rapport.categorie_slug == "energie_elec"


# ------------------------------------------------------------------------------
#  generer_rapports_toutes_categories
# ------------------------------------------------------------------------------
def test_generer_rapports_toutes_categories_une_par_categorie_active(monkeypatch):
    monkeypatch.setattr(svc.settings, "anthropic_api_key", "")
    # 1er execute -> liste des slugs actifs, puis un execute (offres connues
    # vides) par catégorie appelée depuis generer_rapport_hebdomadaire.
    db = FakeSession(execute_queue=[["mobile", "box"], [], []])

    rapports = _run(svc.generer_rapports_toutes_categories(db, api_key=""))

    assert [r.categorie_slug for r in rapports] == ["mobile", "box"]
    assert db.committed == 1
