# ==============================================================================
#  TESTS — routers/alertes_offres.py. Session factice via
#  app.dependency_overrides[get_db], même approche que test_demarches_router.py.
# ==============================================================================
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.alerte_offre import AlerteOffre
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


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.execute_queue = []

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    async def commit(self):
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


def test_lister_alertes_filtre_par_statut_par_defaut(client, fake_db):
    fake_db.queue_result([AlerteOffre(id=1, client_id=1, statut="en_attente")])

    reponse = client.get("/alertes-offres")

    assert reponse.status_code == 200
    assert len(reponse.json()) == 1


def test_valider_alerte_ok(client, fake_db):
    alerte = AlerteOffre(id=1, client_id=1, statut="en_attente")
    fake_db.get_map[(AlerteOffre, 1)] = alerte

    with patch("backend.services.notification_engine.envoyer_email", return_value=False), \
         patch("backend.services.notification_engine.envoyer_sms", return_value=False):
        reponse = client.post("/alertes-offres/1/valider")

    assert reponse.status_code == 200
    assert reponse.json()["ok"] is True
    assert alerte.statut == "validee"


def test_valider_alerte_introuvable(client, fake_db):
    reponse = client.post("/alertes-offres/999/valider")
    assert reponse.status_code == 422


def test_rejeter_alerte_ok(client, fake_db):
    alerte = AlerteOffre(id=1, client_id=1, statut="en_attente")
    fake_db.get_map[(AlerteOffre, 1)] = alerte

    reponse = client.post("/alertes-offres/1/rejeter")

    assert reponse.status_code == 200
    assert alerte.statut == "rejetee"


def test_rejeter_alerte_deja_traitee(client, fake_db):
    alerte = AlerteOffre(id=1, client_id=1, statut="rejetee")
    fake_db.get_map[(AlerteOffre, 1)] = alerte

    reponse = client.post("/alertes-offres/1/rejeter")

    assert reponse.status_code == 422


def test_sans_authentification_rejete():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        reponse = c.get("/alertes-offres")
    assert reponse.status_code == 401
