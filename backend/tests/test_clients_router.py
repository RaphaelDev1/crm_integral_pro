# ==============================================================================
#  TESTS — routers/clients.py. Session factice via
#  app.dependency_overrides[get_db], même approche que test_demarches_router.py.
# ==============================================================================
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.client import Client
from backend.models.document import Document
from backend.models.historique_action import HistoriqueAction
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

    def scalar_one_or_none(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def first(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.execute_queue = []
        self.added = []
        self.deleted = []
        self._next_id = 1

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        pass

    async def flush(self):
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


def test_creer_client(client, fake_db):
    reponse = client.post("/clients", json={"prenom": "Jean", "nom": "Dupont"})

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["prenom"] == "Jean"
    assert corps["cree_par"] == "Test Conseiller"
    historique = [obj for obj in fake_db.added if isinstance(obj, HistoriqueAction)]
    assert len(historique) == 1
    assert historique[0].action == "Création client"


def test_maj_client(client, fake_db):
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont")

    reponse = client.put("/clients/1", json={"ville": "Lyon"})

    assert reponse.status_code == 200
    assert reponse.json()["ville"] == "Lyon"
    historique = [obj for obj in fake_db.added if isinstance(obj, HistoriqueAction)]
    assert len(historique) == 1
    assert historique[0].action == "Modification"


def test_maj_client_introuvable(client, fake_db):
    reponse = client.put("/clients/999", json={"ville": "Lyon"})
    assert reponse.status_code == 404


def test_supprimer_client(client, fake_db):
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont")

    reponse = client.delete("/clients/1")

    assert reponse.status_code == 204
    historique = [obj for obj in fake_db.added if isinstance(obj, HistoriqueAction)]
    assert len(historique) == 1
    assert historique[0].action == "Suppression"


def test_documents_client(client, fake_db):
    fake_db.queue_result([Document(id=1, client_id=1, type_document="cni", url_stockage="clients/1/cni.pdf", statut_kyc="valide")])

    with patch("backend.routers.clients.url_signee", return_value="https://s3.example/cni.pdf?sig=1"):
        reponse = client.get("/clients/1/documents")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert len(corps) == 1
    assert corps[0]["url"] == "https://s3.example/cni.pdf?sig=1"


def test_historique_client(client, fake_db):
    fake_db.queue_result([
        HistoriqueAction(id=1, entite_type="client", entite_id=1, action="Création client", date_action="01/01/2026 10:00"),
    ])

    reponse = client.get("/clients/1/historique")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert len(corps) == 1
    assert corps[0]["action"] == "Création client"


def test_generer_lien_portail_sans_dossier(client, fake_db):
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont")
    fake_db.queue_result([])  # aucun dossier

    reponse = client.post("/clients/1/token-portail")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert "url" in corps and corps["url"]


def test_generer_lien_portail_client_introuvable(client, fake_db):
    reponse = client.post("/clients/999/token-portail")
    assert reponse.status_code == 404


def test_sans_authentification_rejete():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        reponse = c.get("/clients")
    assert reponse.status_code == 401
