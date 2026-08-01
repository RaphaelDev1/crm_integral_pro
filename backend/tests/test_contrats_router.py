# ==============================================================================
#  TESTS — routers/contrats.py. Session factice via
#  app.dependency_overrides[get_db], même approche que test_demarches_router.py.
# ==============================================================================
import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.contrat import Contrat
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


def test_lister_contrats_filtre_par_client(client, fake_db):
    fake_db.queue_result([Contrat(id=1, client_id=7, fournisseur="Orange")])

    reponse = client.get("/contrats", params={"client_id": 7})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert len(corps) == 1
    assert corps[0]["fournisseur"] == "Orange"


def test_creer_contrat(client, fake_db):
    reponse = client.post("/contrats", json={"client_id": 7, "fournisseur": "SFR", "cout_mensuel": 25.5})

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["fournisseur"] == "SFR"
    assert corps["client_id"] == 7
    assert corps["cree_par"] == "Test Conseiller"


def test_maj_contrat(client, fake_db):
    contrat = Contrat(id=1, client_id=7, fournisseur="Orange", cout_mensuel=20)
    fake_db.get_map[(Contrat, 1)] = contrat

    reponse = client.put("/contrats/1", json={"cout_mensuel": 18.9})

    assert reponse.status_code == 200
    assert reponse.json()["cout_mensuel"] == 18.9


def test_maj_contrat_introuvable(client, fake_db):
    reponse = client.put("/contrats/999", json={"cout_mensuel": 18.9})
    assert reponse.status_code == 404


def test_supprimer_contrat(client, fake_db):
    contrat = Contrat(id=1, client_id=7, fournisseur="Orange")
    fake_db.get_map[(Contrat, 1)] = contrat

    reponse = client.delete("/contrats/1")

    assert reponse.status_code == 204
    assert contrat in fake_db.deleted


def test_supprimer_contrat_introuvable(client, fake_db):
    reponse = client.delete("/contrats/999")
    assert reponse.status_code == 404


def test_sans_authentification_rejete():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        reponse = c.get("/contrats")
    assert reponse.status_code == 401
