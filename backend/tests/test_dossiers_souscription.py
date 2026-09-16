# ==============================================================================
#  TESTS — routers/dossiers.py::pre_remplir_souscription
#  (POST /dossiers/{id}/souscription/pre-remplir). `souscription_engine` est
#  mocké : ces tests vérifient la logique propre à l'endpoint (garde sur
#  l'offre cible/le client, transmission des bons champs), pas le lancement
#  réel de Playwright (couvert séparément si besoin, comme l'ancien
#  src/tests/test_souscription_engine.py pour la version Streamlit).
# ==============================================================================
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.client import Client
from backend.models.contrat import Contrat
from backend.models.dossier import Dossier
from backend.models.offre import Offre
from backend.models.user import User

FAKE_USER = User(
    id=1, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True,
)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.added = []
        self.execute_results = []

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        items = self.execute_results.pop(0) if self.execute_results else []
        return _FakeResult(items)

    def add(self, obj):
        self.added.append(obj)

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


def test_pre_remplir_dossier_introuvable(client, fake_db):
    reponse = client.post("/dossiers/999/souscription/pre-remplir")
    assert reponse.status_code == 404


def test_pre_remplir_sans_offre_cible(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile", offre_cible_id=None)

    reponse = client.post("/dossiers/1/souscription/pre-remplir")

    assert reponse.status_code == 200
    assert reponse.json()["ok"] is False
    assert "offre cible" in reponse.json()["message"].lower()


def test_pre_remplir_offre_introuvable(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile", offre_cible_id=5)

    reponse = client.post("/dossiers/1/souscription/pre-remplir")

    assert reponse.status_code == 200
    assert reponse.json()["ok"] is False


def test_pre_remplir_client_introuvable(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile", offre_cible_id=5)
    fake_db.get_map[(Offre, 5)] = Offre(id=5, fournisseur="Free", nom_offre="Freebox Ultra", url_souscription="https://free.fr")

    reponse = client.post("/dossiers/1/souscription/pre-remplir")

    assert reponse.status_code == 404


def test_pre_remplir_lance_le_navigateur(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile", offre_cible_id=5)
    fake_db.get_map[(Offre, 5)] = Offre(
        id=5, fournisseur="Free", nom_offre="Freebox Ultra",
        url_souscription="https://free.fr/abo", code_affiliation="ABC123",
    )
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont", email="jean@test.fr")

    with patch(
        "backend.routers.dossiers.souscription_engine.lancer_souscription",
        return_value=(True, "Navigateur ouvert."),
    ) as fake_lancer:
        reponse = client.post("/dossiers/1/souscription/pre-remplir")

    assert reponse.status_code == 200
    assert reponse.json() == {"ok": True, "message": "Navigateur ouvert.", "url_manuelle": None}
    fake_lancer.assert_called_once_with(
        "Free", "https://free.fr/abo", {
            "civilite": "", "prenom": "Jean", "nom": "Dupont", "email": "jean@test.fr",
            "email_confirmation": "jean@test.fr",
            "telephone": "", "adresse": "", "code_postal": "", "ville": "",
            "date_naissance": "", "departement_naissance": "", "ville_naissance": "",
        },
        code_affiliation="ABC123", nom_offre="Freebox Ultra", categorie="",
        position=None, taille=None,
    )


def test_pre_remplir_offre_mobile_transmet_la_ligne_mobile_de_reference(client, fake_db):
    """Free Mobile forfait seul (Offre.categorie == "Mobile") : la ligne mobile
    de référence du client (conserver_numero/type_sim) doit être recherchée et
    transmise, pour piloter le tunnel d'options côté souscription_engine."""
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile", offre_cible_id=5)
    fake_db.get_map[(Offre, 5)] = Offre(
        id=5, fournisseur="Free", categorie="Mobile", nom_offre="Forfait 5G 150 Go",
        url_souscription="https://mobile.free.fr/souscription/options", code_affiliation="ABC123",
    )
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont", email="jean@test.fr")
    ligne_mobile = Contrat(
        id=9, client_id=1, categorie="Forfait mobile", ligne_principale=True,
        conserver_numero="non", type_sim="esim",
    )
    fake_db.execute_results.append([ligne_mobile])

    with patch(
        "backend.routers.dossiers.souscription_engine.lancer_souscription",
        return_value=(True, "Navigateur ouvert."),
    ) as fake_lancer:
        reponse = client.post("/dossiers/1/souscription/pre-remplir")

    assert reponse.status_code == 200
    donnees_transmises = fake_lancer.call_args.args[2]
    assert donnees_transmises["conserver_numero"] == "non"
    assert donnees_transmises["type_sim"] == "esim"
    assert fake_lancer.call_args.kwargs["categorie"] == "Mobile"


def test_pre_remplir_offre_box_ne_cherche_pas_de_ligne_mobile(client, fake_db):
    """Une offre Box/Fibre ne doit pas déclencher la recherche de ligne mobile
    (execute_results resterait vide et FakeSession.execute lèverait un IndexError
    silencieux transformé en liste vide — ce test garantit surtout l'absence des
    clés conserver_numero/type_sim dans les données transmises)."""
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_box", offre_cible_id=5)
    fake_db.get_map[(Offre, 5)] = Offre(
        id=5, fournisseur="Free", categorie="Box / Fibre", nom_offre="Freebox Pop",
        url_souscription="https://free.fr/abo", code_affiliation="ABC123",
    )
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont", email="jean@test.fr")

    with patch(
        "backend.routers.dossiers.souscription_engine.lancer_souscription",
        return_value=(True, "Navigateur ouvert."),
    ) as fake_lancer:
        reponse = client.post("/dossiers/1/souscription/pre-remplir")

    assert reponse.status_code == 200
    donnees_transmises = fake_lancer.call_args.args[2]
    assert "conserver_numero" not in donnees_transmises
    assert "type_sim" not in donnees_transmises
    assert len(fake_db.added) == 1  # HistoriqueAction journalisé


def test_pre_remplir_transmet_la_position_et_la_taille_de_fenetre(client, fake_db):
    fake_db.get_map[(Dossier, 1)] = Dossier(id=1, client_id=1, univers="telecom_mobile", offre_cible_id=5)
    fake_db.get_map[(Offre, 5)] = Offre(
        id=5, fournisseur="Free", nom_offre="Freebox Ultra", url_souscription="https://free.fr/abo",
    )
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont")

    with patch(
        "backend.routers.dossiers.souscription_engine.lancer_souscription",
        return_value=(True, "Navigateur ouvert."),
    ) as fake_lancer:
        reponse = client.post(
            "/dossiers/1/souscription/pre-remplir",
            json={"window_position": [960, 0], "window_size": [960, 1080]},
        )

    assert reponse.status_code == 200
    assert fake_lancer.call_args.kwargs["position"] == (960, 0)
    assert fake_lancer.call_args.kwargs["taille"] == (960, 1080)
