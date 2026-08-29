# ==============================================================================
#  TESTS — routers/ia_conseil_sessions.py. Session factice via
#  app.dependency_overrides[get_db] (même approche que test_clients_router.py),
#  publication WS mockée (pas de Redis réel dans les tests).
# ==============================================================================
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import creer_session_view_token, decoder_session_view_token, get_current_user
from backend.main import app
from backend.models.ia_conseil import ClientConseil, OffreConseil, SessionTrame, TrameTemplate
from backend.models.user import User

FAKE_USER = User(id=1, username="conseiller", nom_complet="Test Conseiller", password_hash="x", role="Conseiller", actif=True)
FAKE_ADMIN = User(id=2, username="admin", nom_complet="Test Admin", password_hash="x", role="Admin", actif=True)

CATEGORIE = "mobile"
TRAME_SIMPLE = {
    "sections": [{"id": "s", "questions": [{"id": "conso_data_go", "cout_cognitif": 1, "poids_ethique": 5}]}],
    "branches": [],
}


class _FakeResult:
    def __init__(self, value):
        self._value = value if isinstance(value, list) else [value]

    def scalars(self):
        return self

    def all(self):
        return self._value

    def scalar_one_or_none(self):
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
        # Simule les defaults appliqués par la vraie base à l'INSERT (id
        # UUID généré, demarree_le horodatée) — FakeSession ne passe jamais
        # par le moteur SQLAlchemy réel qui les calculerait.
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if hasattr(obj, "demarree_le") and obj.demarree_le is None:
            obj.demarree_le = datetime.now(timezone.utc)
        if isinstance(obj, SessionTrame):
            if obj.reponses is None:
                obj.reponses = {}
            if obj.etat is None:
                obj.etat = "en_cours"
        if hasattr(obj, "cree_le") and obj.cree_le is None:
            obj.cree_le = datetime.now(timezone.utc)
        self.added.append(obj)

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
    with patch("backend.services.ia_conseil_ws.publier", new=AsyncMock()):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


def _session_en_cours(**kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        conseiller_id=1,
        categorie_slug=CATEGORIE,
        trame_template_id=uuid.uuid4(),
        reponses={},
        etat="en_cours",
        canal="visio",
        demarree_le=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return SessionTrame(**defaults)


def _trame(session):
    return TrameTemplate(id=session.trame_template_id, categorie_slug=CATEGORIE, version=1, definition=TRAME_SIMPLE, actif=True)


class TestCreerSession:
    def test_cree_la_session(self, client, fake_db):
        client_id = uuid.uuid4()
        fake_db.queue_result(TrameTemplate(id=uuid.uuid4(), categorie_slug=CATEGORIE, version=1, definition=TRAME_SIMPLE, actif=True))

        reponse = client.post("/api/v1/sessions", json={"client_id": str(client_id), "categorie_slug": CATEGORIE, "canal": "visio"})

        assert reponse.status_code == 201
        corps = reponse.json()
        assert corps["categorie_slug"] == CATEGORIE
        assert corps["etat"] == "en_cours"

    def test_422_si_aucune_trame_active(self, client, fake_db):
        fake_db.queue_result(None)

        reponse = client.post("/api/v1/sessions", json={"client_id": str(uuid.uuid4()), "categorie_slug": "inconnue"})

        assert reponse.status_code == 422


class TestObtenirSession:
    def test_404_si_absente(self, client):
        reponse = client.get(f"/api/v1/sessions/{uuid.uuid4()}")
        assert reponse.status_code == 404

    def test_403_si_autre_conseiller(self, client, fake_db):
        session = _session_en_cours(conseiller_id=99)
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.get(f"/api/v1/sessions/{session.id}")

        assert reponse.status_code == 403

    def test_200_pour_le_conseiller_proprietaire(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.get(f"/api/v1/sessions/{session.id}")

        assert reponse.status_code == 200
        assert reponse.json()["id"] == str(session.id)

    def test_200_pour_admin_meme_autre_conseiller(self, client, fake_db):
        app.dependency_overrides[get_current_user] = lambda: FAKE_ADMIN
        session = _session_en_cours(conseiller_id=99)
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.get(f"/api/v1/sessions/{session.id}")

        assert reponse.status_code == 200


class TestNextQuestion:
    def test_retourne_la_question_de_score_maximal(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session
        fake_db.get_map[(TrameTemplate, session.trame_template_id)] = _trame(session)
        fake_db.queue_result([])  # offres
        fake_db.queue_result([])  # regles

        reponse = client.get(f"/api/v1/sessions/{session.id}/next-question")

        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["question"]["id"] == "conso_data_go"
        assert corps["terminee"] is False


class TestRepondre:
    def test_enregistre_la_reponse_et_retourne_le_nouvel_etat(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session
        fake_db.get_map[(TrameTemplate, session.trame_template_id)] = _trame(session)
        fake_db.queue_result([])  # offres (next-question)
        fake_db.queue_result([])  # regles (next-question)
        fake_db.queue_result([])  # offres (calculer_recommandations)
        fake_db.queue_result([])  # regles (calculer_recommandations)
        fake_db.queue_result([])  # delete recommandation

        reponse = client.post(f"/api/v1/sessions/{session.id}/answer", json={"question_id": "conso_data_go", "valeur": 3})

        assert reponse.status_code == 200
        assert session.reponses == {"conso_data_go": 3}
        assert reponse.json()["terminee"] is True  # plus aucune question dans TRAME_SIMPLE une fois répondue

    def test_409_si_session_deja_terminee(self, client, fake_db):
        session = _session_en_cours(etat="terminee")
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.post(f"/api/v1/sessions/{session.id}/answer", json={"question_id": "x", "valeur": 1})

        assert reponse.status_code == 409


class TestRecommandations:
    def test_retourne_le_classement(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session
        fake_db.queue_result([])  # offres
        fake_db.queue_result([])  # regles
        fake_db.queue_result([])  # delete recommandation

        reponse = client.get(f"/api/v1/sessions/{session.id}/recommandations")

        assert reponse.status_code == 200
        assert reponse.json() == []


class TestFinaliser:
    def test_marque_terminee(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session
        fake_db.queue_result([])  # offres
        fake_db.queue_result([])  # regles
        fake_db.queue_result([])  # delete recommandation

        reponse = client.post(f"/api/v1/sessions/{session.id}/finalize")

        assert reponse.status_code == 200
        assert reponse.json()["etat"] == "terminee"
        assert session.etat == "terminee"

    def test_409_si_deja_terminee(self, client, fake_db):
        session = _session_en_cours(etat="terminee")
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.post(f"/api/v1/sessions/{session.id}/finalize")

        assert reponse.status_code == 409


class TestOverrideAlerte:
    def test_cree_l_override_et_renvoie_201(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session
        offre_id = uuid.uuid4()

        reponse = client.post(
            f"/api/v1/sessions/{session.id}/override-alerte",
            json={"offre_id": str(offre_id), "regle_nom": "anti_survente", "justification": "Client informé du risque."},
        )

        assert reponse.status_code == 201
        corps = reponse.json()
        assert corps["regle_nom"] == "anti_survente"
        assert corps["session_id"] == str(session.id)

    def test_403_si_autre_conseiller(self, client, fake_db):
        session = _session_en_cours(conseiller_id=99)
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.post(
            f"/api/v1/sessions/{session.id}/override-alerte",
            json={"offre_id": str(uuid.uuid4()), "regle_nom": "x", "justification": "Justification suffisamment longue."},
        )

        assert reponse.status_code == 403

    def test_422_si_justification_trop_courte(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.post(
            f"/api/v1/sessions/{session.id}/override-alerte",
            json={"offre_id": str(uuid.uuid4()), "regle_nom": "x", "justification": "court"},
        )

        assert reponse.status_code == 422


def _offre_pour_pdf():
    return OffreConseil(
        id=uuid.uuid4(),
        nom="Forfait Eco 40 Go",
        categorie_slug=CATEGORIE,
        prix_mensuel=15.0,
        engagement_mois=0,
        caracteristiques={"data_go": 40},
        valide=True,
    )


class TestTelechargerPdf:
    def test_200_retourne_un_pdf(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session
        fake_db.get_map[(ClientConseil, session.client_id)] = ClientConseil(id=session.client_id, prenom="Jean", nom="Dupont")
        fake_db.get_map[(User, session.conseiller_id)] = FAKE_USER
        fake_db.queue_result([_offre_pour_pdf()])  # offres (calculer_recommandations)
        fake_db.queue_result([])  # regles
        fake_db.queue_result([])  # delete recommandation

        reponse = client.get(f"/api/v1/sessions/{session.id}/pdf")

        assert reponse.status_code == 200
        assert reponse.headers["content-type"] == "application/pdf"
        assert reponse.content.startswith(b"%PDF")

    def test_422_si_session_sans_client(self, client, fake_db):
        session = _session_en_cours(client_id=None)
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.get(f"/api/v1/sessions/{session.id}/pdf")

        assert reponse.status_code == 422

    def test_422_si_aucune_recommandation(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session
        fake_db.get_map[(ClientConseil, session.client_id)] = ClientConseil(id=session.client_id, prenom="Jean", nom="Dupont")
        fake_db.queue_result([])  # offres vides
        fake_db.queue_result([])  # regles
        fake_db.queue_result([])  # delete recommandation

        reponse = client.get(f"/api/v1/sessions/{session.id}/pdf")

        assert reponse.status_code == 422


class TestLienPartage:
    def test_emet_un_jeton_valide_pour_la_session(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.post(f"/api/v1/sessions/{session.id}/share-token")

        assert reponse.status_code == 200
        token = reponse.json()["token"]
        assert decoder_session_view_token(token) == session.id

    def test_403_si_autre_conseiller(self, client, fake_db):
        session = _session_en_cours(conseiller_id=99)
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.post(f"/api/v1/sessions/{session.id}/share-token")

        assert reponse.status_code == 403


class TestSessionPublique:
    def test_200_avec_jeton_valide(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session
        fake_db.get_map[(TrameTemplate, session.trame_template_id)] = _trame(session)
        fake_db.queue_result([])  # offres (next-question)
        fake_db.queue_result([])  # regles (next-question)
        fake_db.queue_result([])  # offres (calculer_recommandations)
        fake_db.queue_result([])  # regles (calculer_recommandations)
        fake_db.queue_result([])  # delete recommandation
        token = creer_session_view_token(session.id)

        # Pas de get_current_user overridé nécessaire : endpoint public.
        reponse = client.get(f"/api/v1/sessions/{session.id}/public", params={"token": token})

        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["id"] == str(session.id)
        assert "conseiller_id" not in corps

    def test_401_si_jeton_invalide(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session

        reponse = client.get(f"/api/v1/sessions/{session.id}/public", params={"token": "invalide"})

        assert reponse.status_code == 401

    def test_401_si_jeton_pour_une_autre_session(self, client, fake_db):
        session = _session_en_cours()
        fake_db.get_map[(SessionTrame, session.id)] = session
        autre_token = creer_session_view_token(uuid.uuid4())

        reponse = client.get(f"/api/v1/sessions/{session.id}/public", params={"token": autre_token})

        assert reponse.status_code == 401
