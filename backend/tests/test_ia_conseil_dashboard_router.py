# ==============================================================================
#  TESTS — routers/ia_conseil_dashboard.py : audit anti-biais réservé Admin
#  (§2.6) et résumé agrégé conseiller (§2.5).
# ==============================================================================
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.ia_conseil import EvenementPlanifie
from backend.models.user import User

FAKE_USER = User(id=1, username="conseiller", nom_complet="Test Conseiller", password_hash="x", role="Conseiller", actif=True)
FAKE_ADMIN = User(id=2, username="admin", nom_complet="Test Admin", password_hash="x", role="Admin", actif=True)


class _FakeResult:
    def __init__(self, value):
        self._value = value if isinstance(value, list) else [value]

    def scalars(self):
        return self

    def all(self):
        return self._value


class FakeSession:
    def __init__(self):
        self.execute_queue = []

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    async def get(self, model, id_):
        return None


@pytest.fixture
def fake_db():
    return FakeSession()


@pytest.fixture
def client(fake_db):
    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestAntiBiais:
    def test_403_pour_un_conseiller(self, client, fake_db):
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER

        reponse = client.get("/api/v1/dashboard/anti-biais")

        assert reponse.status_code == 403

    def test_200_pour_un_admin(self, client, fake_db):
        app.dependency_overrides[get_current_user] = lambda: FAKE_ADMIN
        fake_db.queue_result([])  # souscriptions

        reponse = client.get("/api/v1/dashboard/anti-biais")

        assert reponse.status_code == 200
        assert reponse.json() == []


class TestResumeIaConseil:
    def test_agrege_economies_pipeline_alertes_commissions(self, client, fake_db):
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER
        evenement = EvenementPlanifie(
            id=uuid.uuid4(), client_id=uuid.uuid4(), conseiller_id=1, type="fin_engagement_J-60",
            date_prevue=date.today(), payload={}, execute=False,
        )
        fake_db.queue_result([("mobile", 240.0)])  # économies par catégorie
        fake_db.queue_result([("active", 3), ("en_attente", 1)])  # pipeline
        fake_db.queue_result([evenement])  # evenements_a_venir
        fake_db.queue_result([("2026-08", 50.0, 20.0)])  # commissions mensuelles

        reponse = client.get("/api/v1/dashboard/ia-conseil")

        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["economies_ytd_total"] == 240.0
        assert corps["economies_ytd_par_categorie"] == [{"categorie_slug": "mobile", "economie_annuelle_totale": 240.0}]
        assert corps["pipeline"] == {"en_attente": 1, "active": 3, "resiliee": 0, "annulee": 0}
        assert len(corps["alertes_clients"]) == 1
        assert corps["commissions_mensuelles"] == [{"mois": "2026-08", "prevue": 50.0, "encaissee": 20.0}]

    def test_sans_donnees_renvoie_des_valeurs_par_defaut(self, client, fake_db):
        app.dependency_overrides[get_current_user] = lambda: FAKE_USER
        fake_db.queue_result([])
        fake_db.queue_result([])
        fake_db.queue_result([])
        fake_db.queue_result([])

        reponse = client.get("/api/v1/dashboard/ia-conseil")

        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["economies_ytd_total"] == 0
        assert corps["pipeline"] == {"en_attente": 0, "active": 0, "resiliee": 0, "annulee": 0}
        assert corps["alertes_clients"] == []
        assert corps["commissions_mensuelles"] == []
