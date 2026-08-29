# ==============================================================================
#  TESTS — services/churn_engine.py (§3.5 : prévision de churn + scoring
#  client). Même idiome que les autres tests ia_conseil : asyncio.run(),
#  FakeSession qui consomme une file de résultats préparés à l'avance.
#  Le modèle/les métriques sont isolés dans un répertoire temporaire
#  (monkeypatch de MODEL_PATH/METRICS_PATH) pour ne jamais toucher/lire un
#  vrai modèle entraîné localement.
# ==============================================================================
import asyncio
import uuid
from datetime import date, timedelta

import pytest

from backend.models.ia_conseil import OffreConseil, SessionTrame, Souscription
from backend.services import churn_engine as svc


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _isoler_modele(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "MODEL_PATH", tmp_path / "churn_model.joblib")
    monkeypatch.setattr(svc, "METRICS_PATH", tmp_path / "churn_model_metrics.json")
    monkeypatch.setattr(svc, "MODEL_DIR", tmp_path)


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _FakeRowsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, execute_queue=None, get_map=None):
        self.execute_queue = list(execute_queue or [])
        self.get_map = get_map or {}

    async def execute(self, _query):
        return self.execute_queue.pop(0)

    async def get(self, model, id_):
        return self.get_map.get((model, id_))


# ------------------------------------------------------------------------------
#  _features / _segmenter (fonctions pures)
# ------------------------------------------------------------------------------
def test_features_sans_session_ni_offre():
    souscription = Souscription(id=uuid.uuid4(), prix_mensuel_negocie=25.5, statut="active")
    f = svc._features(souscription, None, None, 0)
    assert f["engagement_mois"] == 0.0
    assert f["prix_mensuel_negocie"] == 25.5
    assert f["canal_visio"] == f["canal_telephone"] == f["canal_physique"] == 0.0


def test_features_canal_one_hot():
    souscription = Souscription(id=uuid.uuid4(), prix_mensuel_negocie=10.0, statut="active")
    session = SessionTrame(id=uuid.uuid4(), canal="visio")
    offre = OffreConseil(id=uuid.uuid4(), nom="X", categorie_slug="mobile", engagement_mois=12, caracteristiques={})
    f = svc._features(souscription, session, offre, 2)
    assert f["engagement_mois"] == 12.0
    assert f["canal_visio"] == 1.0
    assert f["canal_telephone"] == 0.0
    assert f["nb_alertes_overridees"] == 2.0


def test_segmenter_infidele_prioritaire_si_resiliation():
    souscriptions = [Souscription(id=uuid.uuid4(), statut="resiliee")]
    assert svc._segmenter([], souscriptions) == "infidele"


def test_segmenter_econome():
    sessions = [SessionTrame(id=uuid.uuid4(), reponses={"sensibilite_prix": "Prix avant tout"})]
    assert svc._segmenter(sessions, []) == "econome"


def test_segmenter_ethique():
    sessions = [SessionTrame(id=uuid.uuid4(), reponses={"energie_verte_importante": True})]
    assert svc._segmenter(sessions, []) == "ethique"


def test_segmenter_equilibre_par_defaut():
    sessions = [SessionTrame(id=uuid.uuid4(), reponses={"nb_lignes": 2})]
    assert svc._segmenter(sessions, []) == "equilibre"


# ------------------------------------------------------------------------------
#  _proba_churn_heuristique
# ------------------------------------------------------------------------------
def test_proba_churn_heuristique_sans_souscription_active():
    assert svc._proba_churn_heuristique([Souscription(id=uuid.uuid4(), statut="resiliee")]) is None


def test_proba_churn_heuristique_fin_engagement_proche():
    s = Souscription(id=uuid.uuid4(), statut="active", fin_engagement=date.today() + timedelta(days=30))
    assert svc._proba_churn_heuristique([s]) == 0.55


def test_proba_churn_heuristique_fin_engagement_lointaine():
    s = Souscription(id=uuid.uuid4(), statut="active", fin_engagement=date.today() + timedelta(days=400))
    assert svc._proba_churn_heuristique([s]) == 0.10


# ------------------------------------------------------------------------------
#  entrainer_modele
# ------------------------------------------------------------------------------
def test_entrainer_modele_echantillon_insuffisant():
    db = FakeSession(execute_queue=[_FakeRowsResult([])])  # aucune souscription conclue
    resultat = _run(svc.entrainer_modele(db))
    assert resultat["suffisant"] is False
    assert resultat["nb_echantillons"] == 0
    assert not svc.MODEL_PATH.exists()
    assert svc.METRICS_PATH.exists()


def test_entrainer_modele_avec_echantillon_suffisant(monkeypatch):
    lignes = []
    for i in range(40):
        souscription = Souscription(id=uuid.uuid4(), prix_mensuel_negocie=20.0 + i, statut="active" if i % 3 else "resiliee")
        lignes.append((souscription, None, None))

    # _lignes_entrainement fait 1 execute() (la requête jointe) + 1 execute()
    # par ligne (comptage AlerteOverride) — on prépare la file en conséquence.
    execute_queue = [_FakeRowsResult(lignes)] + [_FakeScalarResult(0) for _ in lignes]
    db = FakeSession(execute_queue=execute_queue)

    resultat = _run(svc.entrainer_modele(db))

    assert resultat["suffisant"] is True
    assert resultat["nb_echantillons"] == 40
    assert svc.MODEL_PATH.exists()
    assert svc.METRICS_PATH.exists()


# ------------------------------------------------------------------------------
#  score_client
# ------------------------------------------------------------------------------
def test_score_client_sans_modele_utilise_heuristique(monkeypatch):
    client_id = uuid.uuid4()
    souscription = Souscription(
        id=uuid.uuid4(), client_id=client_id, statut="active",
        fin_engagement=date.today() + timedelta(days=10), date_souscription=date.today(),
    )
    db = FakeSession(execute_queue=[_FakeRowsResult([souscription]), _FakeRowsResult([])])

    async def _fake_cross_sell(_db, _client_id):
        return []
    monkeypatch.setattr(svc.cross_sell_engine, "suggestions_cross_sell", _fake_cross_sell)

    resultat = _run(svc.score_client(db, client_id))
    assert resultat["source"] == "heuristique"
    assert resultat["proba_churn"] == 0.55
    assert resultat["proba_cross_sell"] == 0.0
    assert resultat["segment"] == "equilibre"


def test_score_client_sans_souscription_proba_churn_none(monkeypatch):
    client_id = uuid.uuid4()
    db = FakeSession(execute_queue=[_FakeRowsResult([]), _FakeRowsResult([])])

    async def _fake_cross_sell(_db, _client_id):
        return [{"type": "convergence", "message": "..."}]
    monkeypatch.setattr(svc.cross_sell_engine, "suggestions_cross_sell", _fake_cross_sell)

    resultat = _run(svc.score_client(db, client_id))
    assert resultat["proba_churn"] is None
    assert resultat["proba_cross_sell"] == 0.2
