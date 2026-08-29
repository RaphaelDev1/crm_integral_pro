# ==============================================================================
#  TESTS — routers/ia_conseil_souscriptions.py. Même approche que
#  test_ia_conseil_sessions_router.py (FakeSession via dependency_overrides).
# ==============================================================================
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.ia_conseil import Fournisseur, OffreConseil, Recommandation
from backend.models.user import User

FAKE_USER = User(id=1, username="conseiller", nom_complet="Test Conseiller", password_hash="x", role="Conseiller", actif=True)


class _FakeResult:
    def __init__(self, value):
        self._value = value if isinstance(value, list) else [value]

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
        self.added = []

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    def add(self, obj):
        # Simule les defaults appliqués par la vraie base à l'INSERT (id UUID
        # généré, statut par défaut) — FakeSession ne passe jamais par le
        # moteur SQLAlchemy réel qui les calculerait (voir même commentaire
        # dans test_ia_conseil_sessions_router.py::FakeSession.add).
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "statut", None) is None:
            obj.statut = "en_attente"
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


def _offre(**kwargs):
    defaults = dict(id=uuid.uuid4(), nom="Forfait Eco", categorie_slug="mobile", prix_mensuel=15.0, caracteristiques={}, fournisseur_id=None)
    defaults.update(kwargs)
    return OffreConseil(**defaults)


class TestCreerSouscription:
    def test_404_si_offre_introuvable(self, client, fake_db):
        reponse = client.post(
            "/api/v1/souscriptions",
            json={"client_id": str(uuid.uuid4()), "offre_id": str(uuid.uuid4())},
        )
        assert reponse.status_code == 404

    def test_creation_sans_session_id_ignore_le_blocage(self, client, fake_db):
        offre = _offre()
        fake_db.get_map[(OffreConseil, offre.id)] = offre

        reponse = client.post(
            "/api/v1/souscriptions",
            json={"client_id": str(uuid.uuid4()), "offre_id": str(offre.id)},
        )

        assert reponse.status_code == 201

    def test_409_si_alerte_critique_non_levee(self, client, fake_db):
        offre = _offre()
        session_id = uuid.uuid4()
        fake_db.get_map[(OffreConseil, offre.id)] = offre
        reco = Recommandation(alertes=[{"regle": "anti_survente", "severite": "critique", "message": "m"}])
        fake_db.queue_result([reco])  # dernière recommandation
        fake_db.queue_result([])  # aucun override

        reponse = client.post(
            "/api/v1/souscriptions",
            json={"client_id": str(uuid.uuid4()), "offre_id": str(offre.id), "session_id": str(session_id)},
        )

        assert reponse.status_code == 409
        assert reponse.json()["detail"]["alertes"][0]["regle"] == "anti_survente"

    def test_201_si_alerte_critique_levee_par_override(self, client, fake_db):
        offre = _offre()
        session_id = uuid.uuid4()
        fake_db.get_map[(OffreConseil, offre.id)] = offre
        reco = Recommandation(alertes=[{"regle": "anti_survente", "severite": "critique", "message": "m"}])
        fake_db.queue_result([reco])
        fake_db.queue_result(["anti_survente"])  # override déjà enregistré

        reponse = client.post(
            "/api/v1/souscriptions",
            json={"client_id": str(uuid.uuid4()), "offre_id": str(offre.id), "session_id": str(session_id)},
        )

        assert reponse.status_code == 201

    def test_commission_prevue_calculee_via_taux_fournisseur(self, client, fake_db):
        fournisseur = Fournisseur(id=uuid.uuid4(), nom="Free", taux_commission=10.0)
        offre = _offre(fournisseur_id=fournisseur.id)
        fake_db.get_map[(OffreConseil, offre.id)] = offre
        fake_db.get_map[(Fournisseur, fournisseur.id)] = fournisseur

        reponse = client.post(
            "/api/v1/souscriptions",
            json={"client_id": str(uuid.uuid4()), "offre_id": str(offre.id), "prix_mensuel_negocie": 20.0},
        )

        assert reponse.status_code == 201
        assert reponse.json()["commission_prevue"] == 2.0


class TestListerCommissions:
    def test_liste_vide(self, client, fake_db):
        fake_db.queue_result([])
        reponse = client.get("/api/v1/souscriptions/commissions")
        assert reponse.status_code == 200
        assert reponse.json() == []
