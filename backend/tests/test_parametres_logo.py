# ==============================================================================
#  TESTS — routers/parametres.py::uploader_logo. Même approche que
#  test_demarches_router.py (session factice via app.dependency_overrides).
# ==============================================================================
import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.parametre import Parametre
from backend.models.user import User

FAKE_ADMIN = User(
    id=1, username="admin", nom_complet="Test Admin",
    password_hash="x", role="Admin", actif=True,
)


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.added = []

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    def add(self, obj):
        self.added.append(obj)
        self.get_map[(Parametre, obj.cle)] = obj

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

    app.dependency_overrides[get_current_user] = lambda: FAKE_ADMIN
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 40), (0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_uploader_logo_rejette_un_contenu_usurpe(client, fake_db):
    reponse = client.post(
        "/parametres/logo",
        files={"fichier": ("logo.png", b"pas une vraie image", "image/png")},
    )
    assert reponse.status_code == 415


def test_uploader_logo_accepte_une_vraie_image(client, fake_db):
    with patch("backend.routers.parametres.storage_engine.upload_fichier",
               return_value="branding/2026/07/logo_abcd1234_efgh5678.png") as mock_upload:
        reponse = client.post(
            "/parametres/logo",
            files={"fichier": ("logo.png", _png_bytes(), "image/png")},
        )

    assert reponse.status_code == 200
    assert reponse.json()["valeur"] == "branding/2026/07/logo_abcd1234_efgh5678.png"
    mock_upload.assert_called_once()
    assert fake_db.get_map[(Parametre, "pdf_logo_cle_stockage")].valeur == \
        "branding/2026/07/logo_abcd1234_efgh5678.png"


def test_uploader_logo_sans_role_admin_rejete():
    app.dependency_overrides.clear()

    async def _override_get_db():
        yield FakeSession()

    app.dependency_overrides[get_current_user] = lambda: User(
        id=2, username="conseiller", nom_complet="Test", password_hash="x", role="Conseiller", actif=True,
    )
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        reponse = c.post("/parametres/logo", files={"fichier": ("logo.png", _png_bytes(), "image/png")})
    app.dependency_overrides.clear()

    assert reponse.status_code == 403
