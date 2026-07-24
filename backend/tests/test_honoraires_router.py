# ==============================================================================
#  TESTS — routers/honoraires.py. Base de données remplacée par une session
#  factice (get/execute pré-remplis, add/commit/refresh no-op) via
#  app.dependency_overrides[get_db] — même approche que get_current_user dans
#  test_factures_router.py, aucune connexion Postgres réelle nécessaire.
# ==============================================================================
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.dossier import Dossier
from backend.models.mandat_honoraires import MandatHonoraires
from backend.models.user import User

FAKE_USER = User(
    id=1, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True,
)


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.execute_queue = []
        self.added = []
        self._next_id = 1

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else None
        return _FakeResult(value)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = self._next_id
            self._next_id += 1
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


def test_obtenir_mandat_honoraires_inexistant(client, fake_db):
    fake_db.queue_result(None)
    reponse = client.get("/dossiers/1/mandat-honoraires")
    assert reponse.status_code == 200
    assert reponse.json() is None


def test_creer_mandat_honoraires(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile", statut="mandat_a_signer")
    fake_db.queue_result(None)  # pas de mandat existant

    reponse = client.post("/dossiers/1/mandat-honoraires", json={"montant": 120.0, "taux": 15.0})

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["dossier_id"] == 1
    assert corps["montant"] == 120.0
    assert corps["taux"] == 15.0
    assert corps["statut"] == "envoye"


def test_creer_mandat_honoraires_dossier_introuvable(client, fake_db):
    reponse = client.post("/dossiers/999/mandat-honoraires", json={"montant": 100.0, "taux": 10.0})
    assert reponse.status_code == 404


def test_creer_mandat_honoraires_conflit_si_deja_existant(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile", statut="mandat_a_signer")
    fake_db.queue_result(MandatHonoraires(id=5, dossier_id=1, montant=50.0, taux=10.0, statut="envoye"))

    reponse = client.post("/dossiers/1/mandat-honoraires", json={"montant": 120.0, "taux": 15.0})

    assert reponse.status_code == 409


def test_marquer_signe_honoraires(client, fake_db):
    mandat = MandatHonoraires(
        id=5, dossier_id=1, montant=120.0, taux=15.0, statut="envoye",
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )
    fake_db.queue_result(mandat)

    reponse = client.post("/dossiers/1/mandat-honoraires/marquer-signe", json={"signataire": "M. Dupont"})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "signe"
    assert corps["signataire"] == "M. Dupont"
    assert corps["date_signature"] is not None


def test_marquer_signe_honoraires_introuvable(client, fake_db):
    fake_db.queue_result(None)
    reponse = client.post("/dossiers/1/mandat-honoraires/marquer-signe", json={"signataire": "M. Dupont"})
    assert reponse.status_code == 404


def test_sans_authentification_rejete():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        reponse = c.get("/dossiers/1/mandat-honoraires")
    assert reponse.status_code == 401
