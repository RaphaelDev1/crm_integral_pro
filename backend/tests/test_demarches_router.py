# ==============================================================================
#  TESTS — routers/demarches.py. Base de données remplacée par une session
#  factice via app.dependency_overrides[get_db] — même approche que
#  test_honoraires_router.py, aucune connexion Postgres réelle nécessaire.
#  Les tâches Celery sont patchées (.delay) : jamais de worker réel démarré.
# ==============================================================================
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.demarche import Demarche
from backend.models.dossier import Dossier
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


def _dossier(**kwargs):
    base = dict(id=1, client_id=1, univers="telecom_mobile", statut="mandat_signe")
    base.update(kwargs)
    return Dossier(**base)


def test_lister_demarches_dossier(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = _dossier()
    fake_db.queue_result([])  # aucune démarche existante

    reponse = client.get("/dossiers/1/demarches")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["existantes"] == []
    types_requis = {d["type_demarche"] for d in corps["requises_non_creees"]}
    assert types_requis == {"audit_mobile", "mandat", "portabilite"}


def test_lister_demarches_dossier_introuvable(client, fake_db):
    reponse = client.get("/dossiers/999/demarches")
    assert reponse.status_code == 404


def test_creer_demarche(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = _dossier()

    reponse = client.post("/dossiers/1/demarches", json={"type_demarche": "portabilite"})

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["type_demarche"] == "portabilite"
    assert corps["statut"] == "a_generer"
    assert set(corps["donnees_requises"].keys()) == {"conserver_numero", "rio", "numero_ligne", "type_sim"}


def test_creer_demarche_dossier_introuvable(client, fake_db):
    reponse = client.post("/dossiers/999/demarches", json={"type_demarche": "portabilite"})
    assert reponse.status_code == 404


def test_creer_demarche_type_invalide(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = _dossier()
    reponse = client.post("/dossiers/1/demarches", json={"type_demarche": "type_bidon"})
    assert reponse.status_code == 422


def test_generer_demarche_dispatch_celery(client, fake_db):
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="a_generer",
                         univers="telecom_mobile", canal="lre")
    fake_db.get_map[(Demarche, 1)] = demarche

    with patch("backend.workers.tasks.generer_document_demarche.delay") as mock_delay:
        reponse = client.post("/demarches/1/generer")

    assert reponse.status_code == 202
    mock_delay.assert_called_once_with(1)


def test_generer_demarche_introuvable(client, fake_db):
    reponse = client.post("/demarches/999/generer")
    assert reponse.status_code == 404


def test_envoyer_demarche_refuse_si_pas_generee(client, fake_db):
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="a_generer",
                         univers="telecom_mobile", canal="lre")
    fake_db.get_map[(Demarche, 1)] = demarche

    reponse = client.post("/demarches/1/envoyer")

    assert reponse.status_code == 409


def test_envoyer_demarche_dispatch_celery(client, fake_db):
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="generee",
                         univers="telecom_mobile", canal="lre",
                         document_url="dossiers/1/demarches/mandat.pdf")
    fake_db.get_map[(Demarche, 1)] = demarche

    with patch("backend.workers.tasks.envoyer_demarche_lre.delay") as mock_delay:
        reponse = client.post("/demarches/1/envoyer")

    assert reponse.status_code == 202
    mock_delay.assert_called_once_with(1)


def test_patch_champs_demarche(client, fake_db):
    demarche = Demarche(
        id=1, dossier_id=1, type_demarche="portabilite", statut="a_generer",
        univers="telecom_mobile", canal="lre",
        donnees_requises={
            "rio": {"valeur": None, "requis": True, "label": "RIO"},
            "numero_ligne": {"valeur": None, "requis": True, "label": "Numéro"},
        },
    )
    fake_db.get_map[(Demarche, 1)] = demarche

    reponse = client.patch("/demarches/1/champs", json={"valeurs": {"rio": "AB1234"}})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["donnees_requises"]["rio"]["valeur"] == "AB1234"
    assert corps["donnees_requises"]["numero_ligne"]["valeur"] is None


def test_obtenir_document_demarche_url_signee(client, fake_db):
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="generee",
                         document_url="dossiers/1/demarches/mandat.pdf")
    fake_db.get_map[(Demarche, 1)] = demarche

    with patch("backend.services.storage_engine.url_signee", return_value="https://s3.example/x?sig=1"):
        reponse = client.get("/demarches/1/document")

    assert reponse.status_code == 200
    assert reponse.json()["url"] == "https://s3.example/x?sig=1"


def test_obtenir_document_demarche_pas_encore_generee(client, fake_db):
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="a_generer", document_url=None)
    fake_db.get_map[(Demarche, 1)] = demarche

    reponse = client.get("/demarches/1/document")

    assert reponse.status_code == 404


def test_sans_authentification_rejete():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        reponse = c.get("/dossiers/1/demarches")
    assert reponse.status_code == 401
