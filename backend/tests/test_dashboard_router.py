# ==============================================================================
#  TESTS — routers/dashboard.py::resume_dashboard. Session factice via
#  app.dependency_overrides[get_db] (même approche que
#  test_dossiers_pdf_restitution.py) : 5 appels execute() dans l'ordre
#  (clients, prospects, historique_actions, count(clients), count(dossiers)).
# ==============================================================================
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.client import Client
from backend.models.prospect import Prospect
from backend.models.user import User

FAKE_USER = User(
    id=1, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True,
)

FORMAT_DATE_RELANCE = "%d/%m/%Y"


def _il_y_a(jours: int) -> str:
    return (datetime.now() - timedelta(days=jours)).strftime(FORMAT_DATE_RELANCE)


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value

    def scalar_one(self):
        return self._value


class FakeSession:
    def __init__(self):
        self.execute_queue = []

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)


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


def test_relances_classees_par_fenetre(client, fake_db):
    client_venir = Client(id=1, prenom="E", nom="F", date_relance=_il_y_a(-2))
    prospect_retard = Prospect(id=1, prenom="A", nom="B", date_relance=_il_y_a(3), converti_at=None,
                                economie_estimee_an=0.0)
    prospect_jour = Prospect(id=2, prenom="C", nom="D", date_relance=_il_y_a(0), converti_at=None,
                              economie_estimee_an=0.0)

    fake_db.queue_result([client_venir])                       # clients
    fake_db.queue_result([prospect_retard, prospect_jour])      # prospects non convertis
    fake_db.queue_result([])                                    # historique_actions
    fake_db.queue_result(1)                                     # count(clients)
    fake_db.queue_result(0)                                      # count(dossiers en cours)

    reponse = client.get("/dashboard/summary")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["relances_retard"] == 1
    assert corps["relances_jour"] == 1
    assert corps["relances_venir"] == 1


def test_kpis_compte_clients_prospects_et_dossiers(client, fake_db):
    prospect_froid = Prospect(id=1, prenom="A", nom="B", economie_estimee_an=0.0,
                               date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"), converti_at=None)

    fake_db.queue_result([Client(id=1, prenom="X", nom="Y"), Client(id=2, prenom="Z", nom="W")])  # clients
    fake_db.queue_result([prospect_froid])   # prospects non convertis
    fake_db.queue_result([])                 # historique_actions
    fake_db.queue_result(2)                   # count(clients)
    fake_db.queue_result(3)                   # count(dossiers en cours)

    reponse = client.get("/dashboard/summary")

    assert reponse.status_code == 200
    kpis = reponse.json()["kpis"]
    assert kpis["total_clients"] == 2
    assert kpis["total_prospects"] == 1
    assert kpis["prospects_froids"] == 1
    assert kpis["prospects_chauds"] == 0
    assert kpis["dossiers_en_cours"] == 3


def test_sans_authentification_rejete():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        reponse = c.get("/dashboard/summary")
    assert reponse.status_code == 401
