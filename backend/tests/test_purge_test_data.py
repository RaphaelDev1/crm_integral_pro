# ==============================================================================
#  TESTS — routers/admin.py + services/purge_test_data.py.
# ==============================================================================
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.user import User

FAKE_CONSEILLER = User(
    id=1, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True,
)
FAKE_ADMIN = User(
    id=2, username="admin", nom_complet="Test Admin",
    password_hash="x", role="Admin", actif=True,
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
        self.execute_queue = []
        self.executed_statements = []
        self.committed = False

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def execute(self, statement):
        self.executed_statements.append(statement)
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    async def commit(self):
        self.committed = True


@pytest.fixture
def fake_db():
    return FakeSession()


@pytest.fixture
def client(fake_db):
    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[get_current_user] = lambda: FAKE_ADMIN
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_purge_refusee_pour_conseiller(client):
    app.dependency_overrides[get_current_user] = lambda: FAKE_CONSEILLER

    reponse = client.delete("/admin/donnees-test")

    assert reponse.status_code == 403


def test_purge_supprime_clients_prospects_et_fichiers(client, fake_db):
    fake_db.queue_result([1, 2])  # ids clients
    fake_db.queue_result([10])  # ids prospects
    fake_db.queue_result(["clients/1/cni.pdf"])  # Document.url_stockage
    fake_db.queue_result([])  # DocumentProspect.cle_stockage
    fake_db.queue_result([])  # Mandat.pdf_url
    fake_db.queue_result([])  # Mandat.pdf_signe_url
    fake_db.queue_result([])  # Demarche.document_url
    fake_db.queue_result([])  # Demarche.preuve_url

    with patch("backend.services.purge_test_data.supprimer_document") as mock_supprimer:
        reponse = client.delete("/admin/donnees-test")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps == {"clients_supprimes": 2, "prospects_supprimes": 1, "fichiers_supprimes": 1}
    mock_supprimer.assert_called_once_with("clients/1/cni.pdf")
    assert fake_db.committed is True


def test_purge_interdite_en_production(client, fake_db):
    fake_db.queue_result([])
    fake_db.queue_result([])

    with patch.object(type(settings), "is_production", new_callable=lambda: property(lambda self: True)):
        reponse = client.delete("/admin/donnees-test")

    assert reponse.status_code == 403
    assert "production" in reponse.json()["detail"].lower()
