# ==============================================================================
#  TESTS — routers/mandats.py.
#  - valider_mandat (POST /mandats/{id}/valider) : étape de validation
#    manuelle ajoutée entre la réception Yousign ("recu") et la finalisation
#    ("signe") — même principe que la validation manuelle des documents KYC.
#  - generer_mandat (POST /dossiers/{id}/mandat) puis envoyer_mandat
#    (POST /mandats/{id}/envoyer) : la génération du PDF (statut "brouillon")
#    est désormais séparée de l'envoi en signature Yousign, pour permettre au
#    conseiller de relire le PDF avant qu'il ne parte chez le client.
#  `mandat_engine` est mocké dans tous les cas : ces tests vérifient la
#  logique propre à chaque endpoint (garde sur le statut, 404/409), pas les
#  effets de bord déjà couverts ailleurs.
# ==============================================================================
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.main import app
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.models.user import User
from backend.services import mandat_engine

FAKE_USER = User(
    id=1, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True,
)


class FakeSession:
    def __init__(self):
        self.get_map = {}

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

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


def test_valider_mandat_recu_le_passe_signe(client, fake_db):
    mandat = Mandat(id=1, client_id=1, statut="recu")
    fake_db.get_map[(Mandat, 1)] = mandat

    with patch("backend.routers.mandats.mandat_engine.traiter_mandat_signe", new=AsyncMock()) as fake_traiter:
        reponse = client.post("/mandats/1/valider")

    assert reponse.status_code == 200
    assert mandat.statut == "signe"
    assert mandat.date_signature is not None
    fake_traiter.assert_awaited_once()
    _, kwargs = fake_traiter.call_args
    assert kwargs["par"] == "Test Conseiller"


def test_valider_mandat_introuvable(client, fake_db):
    reponse = client.post("/mandats/999/valider")
    assert reponse.status_code == 404


def test_valider_mandat_refuse_si_pas_recu(client, fake_db):
    mandat = Mandat(id=1, client_id=1, statut="envoye")
    fake_db.get_map[(Mandat, 1)] = mandat

    reponse = client.post("/mandats/1/valider")

    assert reponse.status_code == 409
    assert mandat.statut == "envoye"


def test_valider_mandat_deja_signe_refuse(client, fake_db):
    mandat = Mandat(id=1, client_id=1, statut="signe")
    fake_db.get_map[(Mandat, 1)] = mandat

    reponse = client.post("/mandats/1/valider")

    assert reponse.status_code == 409


def test_generer_mandat_ne_l_envoie_pas(client, fake_db):
    dossier = Dossier(id=1, client_id=1)
    fake_db.get_map[(Dossier, 1)] = dossier
    mandat_genere = Mandat(id=1, client_id=1, statut="brouillon", pdf_url="clients/1/mandat/x.pdf")

    with patch(
        "backend.routers.mandats.mandat_engine.generer_mandat", new=AsyncMock(return_value=mandat_genere)
    ) as fake_generer:
        reponse = client.post("/dossiers/1/mandat")

    assert reponse.status_code == 201
    assert reponse.json()["statut"] == "brouillon"
    fake_generer.assert_awaited_once_with(fake_db, dossier, FAKE_USER)


def test_generer_mandat_dossier_introuvable(client, fake_db):
    reponse = client.post("/dossiers/999/mandat")
    assert reponse.status_code == 404


def test_envoyer_mandat_brouillon(client, fake_db):
    mandat = Mandat(id=1, client_id=1, statut="brouillon", pdf_url="x.pdf")
    fake_db.get_map[(Mandat, 1)] = mandat
    mandat_envoye = Mandat(id=1, client_id=1, statut="envoye")

    with patch(
        "backend.routers.mandats.mandat_engine.envoyer_mandat_en_signature",
        new=AsyncMock(return_value=mandat_envoye),
    ) as fake_envoyer:
        reponse = client.post("/mandats/1/envoyer")

    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "envoye"
    fake_envoyer.assert_awaited_once_with(fake_db, mandat)


def test_envoyer_mandat_introuvable(client, fake_db):
    reponse = client.post("/mandats/999/envoyer")
    assert reponse.status_code == 404


def test_envoyer_mandat_deja_envoye_refuse(client, fake_db):
    mandat = Mandat(id=1, client_id=1, statut="envoye", pdf_url="x.pdf")
    fake_db.get_map[(Mandat, 1)] = mandat

    with patch(
        "backend.routers.mandats.mandat_engine.envoyer_mandat_en_signature",
        new=AsyncMock(side_effect=mandat_engine.MandatEngineError("Ce mandat a déjà été envoyé en signature.")),
    ):
        reponse = client.post("/mandats/1/envoyer")

    assert reponse.status_code == 422
