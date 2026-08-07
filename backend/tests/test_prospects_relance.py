# ==============================================================================
#  TESTS — routers/prospects.py::relance_effectuee. Session factice via
#  app.dependency_overrides[get_db], même approche que test_clients_router.py.
# ==============================================================================
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.historique_action import HistoriqueAction
from backend.models.prospect import Prospect
from backend.models.user import User

FAKE_USER = User(
    id=1, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True,
)


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else [self._value]

    def first(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def scalar_one_or_none(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.execute_queue = []
        self.added = []

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.fixture
def fake_db():
    return FakeSession()


@pytest.fixture
def client(fake_db):
    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_relance_effectuee_journalise_et_programme_j_plus_7(client, fake_db):
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont")
    fake_db.queue_result(None)  # prospect_scoring.dernier_contact : aucune action antérieure

    reponse = client.post("/prospects/1/relance-effectuee")

    assert reponse.status_code == 200
    prospect = fake_db.get_map[(Prospect, 1)]
    date_attendue = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    assert prospect.date_relance == date_attendue

    historique = [obj for obj in fake_db.added if isinstance(obj, HistoriqueAction)]
    assert len(historique) == 1
    assert historique[0].entite_type == "prospect"
    assert historique[0].entite_id == 1
    assert historique[0].action == "Relance effectuée"
    assert historique[0].auteur == "Test Conseiller"


def test_relance_effectuee_prospect_introuvable(client, fake_db):
    reponse = client.post("/prospects/999/relance-effectuee")
    assert reponse.status_code == 404
