# ==============================================================================
#  TESTS — routers/users.py. Session factice via app.dependency_overrides[get_db],
#  même approche que test_clients_router.py.
# ==============================================================================
import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user, verify_password
from backend.main import app
from backend.models.user import User

FAKE_ADMIN = User(
    id=1, username="admin", nom_complet="Test Admin",
    password_hash="x", role="Admin", actif=True, doit_changer_mdp=False,
)
FAKE_CONSEILLER = User(
    id=2, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True, doit_changer_mdp=False,
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


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.execute_queue = []
        self.added = []
        self._next_id = 10

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
        self.get_map[(User, obj.id)] = obj

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

    app.dependency_overrides[get_current_user] = lambda: FAKE_ADMIN
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_lister_utilisateurs(client, fake_db):
    fake_db.queue_result([FAKE_ADMIN, FAKE_CONSEILLER])

    reponse = client.get("/users")

    assert reponse.status_code == 200
    usernames = [u["username"] for u in reponse.json()]
    assert usernames == ["admin", "conseiller"]


def test_creer_utilisateur(client, fake_db):
    fake_db.queue_result([])  # aucun conflit de username

    reponse = client.post(
        "/users",
        json={"username": "Nouveau", "nom_complet": "Nouveau Conseiller", "password": "motdepasse123", "role": "Conseiller"},
    )

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["username"] == "nouveau"
    assert corps["doit_changer_mdp"] is True
    cree = fake_db.added[0]
    assert verify_password("motdepasse123", cree.password_hash)


def test_creer_utilisateur_conflit_username(client, fake_db):
    fake_db.queue_result([FAKE_CONSEILLER])  # username déjà pris

    reponse = client.post(
        "/users",
        json={"username": "conseiller", "nom_complet": "Doublon", "password": "motdepasse123"},
    )

    assert reponse.status_code == 409


def test_maj_utilisateur_role_et_desactivation(client, fake_db):
    cible = User(id=5, username="cible", nom_complet="Cible", password_hash="x", role="Conseiller", actif=True,
                 doit_changer_mdp=False)
    fake_db.get_map[(User, 5)] = cible

    reponse = client.put("/users/5", json={"role": "Admin", "actif": False})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["role"] == "Admin"
    assert corps["actif"] is False


def test_maj_utilisateur_introuvable(client, fake_db):
    reponse = client.put("/users/999", json={"actif": False})
    assert reponse.status_code == 404


def test_sans_role_admin_rejete():
    app.dependency_overrides.clear()

    async def _override_get_db():
        yield FakeSession()

    app.dependency_overrides[get_current_user] = lambda: FAKE_CONSEILLER
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        reponse = c.get("/users")
    app.dependency_overrides.clear()

    assert reponse.status_code == 403
