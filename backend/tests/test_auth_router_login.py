# ==============================================================================
#  TESTS — routers/auth.py::login. Base remplacée par une session factice
#  (get_db surchargé), aucun Postgres réel — même approche que
#  test_honoraires_router.py.
# ==============================================================================
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import hash_password
from backend.main import app
from backend.models.user import User

_FMT = "%Y-%m-%d %H:%M:%S"

FAKE_USER = User(
    id=7, username="conseiller1", nom_complet="Jean Conseiller",
    password_hash=hash_password("Secret123!"), role="Conseiller", actif=True,
    doit_changer_mdp=False,
)


class _FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar


class FakeSession:
    """Simule les 3 appels db.execute() de login() dans l'ordre : (1) le
    SELECT de compte_verrouille, (2) le SELECT du User, (3) le DELETE de purge
    dans enregistrer_tentative — puis add()/commit()."""

    def __init__(self, user=None, tentatives_rows=None):
        self.user = user
        self.tentatives_rows = tentatives_rows or []
        self.added = []
        self.committed = False
        self._appel = 0

    async def execute(self, _query):
        self._appel += 1
        if self._appel == 1:
            return _FakeResult(rows=self.tentatives_rows)
        if self._appel == 2:
            return _FakeResult(scalar=self.user)
        return _FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


@pytest.fixture
def client_avec_session():
    sessions = {}

    def _make(user=None, tentatives_rows=None):
        fake_db = FakeSession(user=user, tentatives_rows=tentatives_rows)
        sessions["db"] = fake_db

        async def _override_get_db():
            yield fake_db

        app.dependency_overrides[get_db] = _override_get_db
        return TestClient(app)

    yield _make, sessions
    app.dependency_overrides.clear()


def test_login_succes_renvoie_token_et_profil(client_avec_session):
    make_client, sessions = client_avec_session
    client = make_client(user=FAKE_USER)

    reponse = client.post("/auth/login", json={"username": "conseiller1", "password": "Secret123!"})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["user"]["nom_complet"] == "Jean Conseiller"
    assert corps["user"]["role"] == "Conseiller"
    assert "password_hash" not in corps["user"]

    payload = jwt.decode(corps["access_token"], options={"verify_signature": False})
    assert payload["nom_complet"] == "Jean Conseiller"  # régression-guard (voir security.py::_creer_token)
    assert payload["user_id"] == 7

    assert sessions["db"].committed is True
    assert sessions["db"].added[0].succes is True


def test_login_mot_de_passe_incorrect(client_avec_session):
    make_client, sessions = client_avec_session
    client = make_client(user=FAKE_USER)

    reponse = client.post("/auth/login", json={"username": "conseiller1", "password": "mauvais"})

    assert reponse.status_code == 401
    assert sessions["db"].added[0].succes is False


def test_login_verrouille_apres_5_echecs(client_avec_session):
    maintenant = datetime.now(timezone.utc)
    rows = [(False, (maintenant - timedelta(minutes=i)).strftime(_FMT)) for i in range(5)]
    make_client, _sessions = client_avec_session
    client = make_client(user=FAKE_USER, tentatives_rows=rows)

    reponse = client.post("/auth/login", json={"username": "conseiller1", "password": "Secret123!"})

    assert reponse.status_code == 429


def test_login_utilisateur_inconnu(client_avec_session):
    make_client, _sessions = client_avec_session
    client = make_client(user=None)

    reponse = client.post("/auth/login", json={"username": "inconnu", "password": "x"})

    assert reponse.status_code == 401
