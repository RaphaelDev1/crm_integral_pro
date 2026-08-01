# ==============================================================================
#  TESTS — routers/dossiers.py::obtenir_pdf_restitution. Même approche que
#  test_demarches_router.py (session factice via app.dependency_overrides).
# ==============================================================================
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.client import Client
from backend.models.comparaison_offre import ComparaisonOffre
from backend.models.dossier import Dossier
from backend.models.parametre import Parametre
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
        return self._value

    def first(self):
        return self._value[0] if self._value else None


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


def test_pdf_restitution_dossier_introuvable(client, fake_db):
    reponse = client.get("/dossiers/999/pdf-restitution")
    assert reponse.status_code == 404


def test_pdf_restitution_client_introuvable(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile")

    reponse = client.get("/dossiers/1/pdf-restitution")

    assert reponse.status_code == 404


def test_pdf_restitution_sans_comparaison_enregistree(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile")
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont")
    fake_db.queue_result([])  # aucune ComparaisonOffre

    reponse = client.get("/dossiers/1/pdf-restitution")

    assert reponse.status_code == 404
    assert "comparaison" in reponse.json()["detail"].lower()


def test_pdf_restitution_genere_le_pdf(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile", economie_annuelle_estimee=100.0)
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont")
    fake_db.queue_result([ComparaisonOffre(id=1, client_id=1, univers="Télécom", categorie="Mobile",
                                            offres_comparees=[], economie_annuelle_estimee=100.0)])
    fake_db.get_map[(Parametre, "pdf_logo_cle_stockage")] = None
    fake_db.get_map[(Parametre, "nom_societe")] = None
    fake_db.get_map[(Parametre, "pdf_couleur_primaire_hex")] = None
    fake_db.get_map[(Parametre, "pdf_couleur_accent_hex")] = None

    reponse = client.get("/dossiers/1/pdf-restitution")

    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "application/pdf"
    assert reponse.content.startswith(b"%PDF")


def test_pdf_restitution_dossier_prospect_non_converti(client, fake_db):
    """Un Dossier créé pré-conversion (est_prospect=True, statut='initie', rattaché
    au Client miroir, cf. backend/services/prospect_conversion.py) doit générer le
    PDF sans changement de code — confirme la section 1.5 du plan de migration."""
    fake_db.get_map[(Dossier, 1)] = Dossier(
        id=1, client_id=1, univers="telecom_mobile", statut="initie",
        est_prospect=True, economie_annuelle_estimee=100.0,
    )
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont")
    fake_db.queue_result([ComparaisonOffre(id=1, client_id=1, univers="Télécom", categorie="Mobile",
                                            offres_comparees=[], economie_annuelle_estimee=100.0)])
    fake_db.get_map[(Parametre, "pdf_logo_cle_stockage")] = None
    fake_db.get_map[(Parametre, "nom_societe")] = None
    fake_db.get_map[(Parametre, "pdf_couleur_primaire_hex")] = None
    fake_db.get_map[(Parametre, "pdf_couleur_accent_hex")] = None

    reponse = client.get("/dossiers/1/pdf-restitution")

    assert reponse.status_code == 200
    assert reponse.content.startswith(b"%PDF")


def test_sans_authentification_rejete():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        reponse = c.get("/dossiers/1/pdf-restitution")
    assert reponse.status_code == 401
