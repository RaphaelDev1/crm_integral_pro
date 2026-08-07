# ==============================================================================
#  TESTS — routers/prospects.py::supprimer_document_prospect. Même approche
#  de session factice que test_prospects_relance.py.
# ==============================================================================
import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.document_prospect import DocumentProspect
from backend.models.historique_action import HistoriqueAction
from backend.models.user import User

FAKE_USER = User(
    id=1, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True,
)


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.added = []
        self.deleted = []

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

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


def test_supprimer_document_prospect_journalise_et_supprime(client, fake_db):
    document = DocumentProspect(id=10, prospect_id=1, type_document="facture", cle_stockage="clients/1/x.pdf")
    fake_db.get_map[(DocumentProspect, 10)] = document

    reponse = client.delete("/prospects/1/documents/10")

    assert reponse.status_code == 204
    assert fake_db.deleted == [document]
    historique = [obj for obj in fake_db.added if isinstance(obj, HistoriqueAction)]
    assert len(historique) == 1
    assert historique[0].action == "Document supprimé"
    assert historique[0].entite_type == "prospect"
    assert historique[0].entite_id == 1


def test_supprimer_document_prospect_introuvable(client, fake_db):
    reponse = client.delete("/prospects/1/documents/999")
    assert reponse.status_code == 404


def test_supprimer_document_prospect_mauvais_prospect_id(client, fake_db):
    document = DocumentProspect(id=10, prospect_id=2, type_document="facture", cle_stockage="clients/2/x.pdf")
    fake_db.get_map[(DocumentProspect, 10)] = document

    reponse = client.delete("/prospects/1/documents/10")

    assert reponse.status_code == 404
    assert fake_db.deleted == []
