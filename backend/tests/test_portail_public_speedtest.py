# ==============================================================================
#  TESTS — routers/portail_public.py::soumettre_speedtest. Session factice via
#  app.dependency_overrides[get_db] (même approche que test_demarches_router.py) ;
#  token_engine.valider_token patché pour éviter toute requête réelle.
# ==============================================================================
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.core.database import get_db
from backend.main import app
from backend.models.client import Client
from backend.models.prospect import Prospect
from backend.models.token_public import TokenPublic


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.committed = False
        self.added = []

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 42


@pytest.fixture
def fake_db():
    return FakeSession()


@pytest.fixture
def api_client(fake_db):
    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(**kwargs):
    base = dict(id=1, token="x" * 32, client_id=1, prospect_id=None, peut_transmettre_speedtest=True)
    base.update(kwargs)
    return TokenPublic(**base)


def _token_prospect(**kwargs):
    base = dict(id=2, token="y" * 32, client_id=None, prospect_id=1, peut_transmettre_speedtest=True)
    base.update(kwargs)
    return TokenPublic(**base)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def test_soumettre_speedtest_numerique_met_a_jour_le_client(api_client, fake_db):
    fake_db.get_map[(TokenPublic, "x" * 32)] = None  # non utilisé : valider_token est patché
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont")

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token())):
        reponse = api_client.post(
            f"/portail/{'x' * 32}/speedtest",
            data={"download_mbps": "123.4", "upload_mbps": "45.6"},
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["speed_down"] == 123.4
    assert corps["speed_up"] == 45.6
    assert fake_db.get_map[(Client, 1)].speed_down == 123.4
    assert fake_db.committed


def test_soumettre_speedtest_numerique_met_a_jour_le_prospect(api_client, fake_db):
    """Un lien prospect (pas encore client) doit aussi pouvoir transmettre un
    test de débit mesuré en direct — voir
    token_engine.generer_token_prospect_documents (peut_transmettre_speedtest=True)."""
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont")

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.post(
            f"/portail/{'y' * 32}/speedtest",
            data={"download_mbps": "80.0", "upload_mbps": "20.0"},
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["speed_down"] == 80.0
    assert fake_db.get_map[(Prospect, 1)].speed_down == 80.0
    assert fake_db.committed


def test_soumettre_speedtest_refuse_si_non_autorise_par_le_token(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token(peut_transmettre_speedtest=False))):
        reponse = api_client.post(
            f"/portail/{'x' * 32}/speedtest",
            data={"download_mbps": "10", "upload_mbps": "5"},
        )

    assert reponse.status_code == 403


def test_soumettre_speedtest_token_invalide(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=None)):
        reponse = api_client.post(
            f"/portail/{'x' * 32}/speedtest",
            data={"download_mbps": "10", "upload_mbps": "5"},
        )

    assert reponse.status_code == 404


def test_soumettre_speedtest_fichier_usurpe_rejete_malgre_extension_pdf(api_client, fake_db):
    """Un contenu texte brut renommé en .pdf doit être rejeté : la
    vérification se fait par magic bytes, jamais par l'extension déclarée."""
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token())):
        reponse = api_client.post(
            f"/portail/{'x' * 32}/speedtest",
            files={"fichier": ("resultat.pdf", b"ceci n'est pas un vrai PDF", "application/pdf")},
        )

    assert reponse.status_code == 415


def test_soumettre_speedtest_fichier_image_reelle_accepte(api_client, fake_db):
    fake_db.get_map[(Client, 1)] = Client(id=1, prenom="Jean", nom="Dupont")

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token())), \
         patch("backend.routers.portail_public.storage_engine.upload_document",
               return_value="clients/1/2026/07/speedtest_abcd1234_efgh5678.png"):
        reponse = api_client.post(
            f"/portail/{'x' * 32}/speedtest",
            files={"fichier": ("capture.png", _png_bytes(), "image/png")},
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["document_id"] == 42
    assert any(o.type_document == "speedtest" for o in fake_db.added)


def test_soumettre_speedtest_sans_rien_transmis_est_rejete(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token())):
        reponse = api_client.post(f"/portail/{'x' * 32}/speedtest")

    assert reponse.status_code == 422
