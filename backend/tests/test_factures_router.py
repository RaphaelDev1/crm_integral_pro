# ==============================================================================
#  TESTS — routers/factures.py (endpoint POST /factures/analyze). Le service
#  facture_analyzer et l'authentification JWT sont tous deux mockés/surchargés :
#  aucun appel réseau réel (Claude ni Postgres) n'est nécessaire.
# ==============================================================================
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.security import get_current_user
from backend.main import app
from backend.models.user import User
from backend.services.facture_analyzer import FactureAnalyzerError

FAKE_USER = User(
    id=1, username="conseiller", nom_complet="Test Conseiller",
    password_hash="x", role="Conseiller", actif=True,
)

RESULTAT_ATTENDU = {
    "operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99, "data_conso_go": 150.0,
    "options": ["Appels illimités"], "engagement_mois": 12,
    "date_fin_engagement": "15/03/2027", "iban_prelevement": "FR7630001007941234567890185",
}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_analyse_facture_pdf_valide(client):
    with patch("backend.routers.factures.analyser_facture", return_value=RESULTAT_ATTENDU) as mock_analyse:
        reponse = client.post(
            "/factures/analyze",
            files={"fichier": ("facture.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 200
    assert reponse.json() == RESULTAT_ATTENDU
    mock_analyse.assert_called_once()
    # Le chemin passé au service est un fichier temporaire réel, supprimé après l'appel.
    chemin_tmp = mock_analyse.call_args.args[0]
    import os
    assert not os.path.exists(chemin_tmp)


def test_rejette_extension_non_pdf(client):
    reponse = client.post(
        "/factures/analyze",
        files={"fichier": ("facture.jpg", b"donnees-image", "image/jpeg")},
    )
    assert reponse.status_code == 422


def test_erreur_analyse_devient_422(client):
    with patch("backend.routers.factures.analyser_facture", side_effect=FactureAnalyzerError("boom")):
        reponse = client.post(
            "/factures/analyze",
            files={"fichier": ("facture.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert reponse.status_code == 422
    assert "boom" in reponse.json()["detail"]


def test_sans_authentification_rejete():
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        reponse = c.post(
            "/factures/analyze",
            files={"fichier": ("facture.pdf", b"%PDF-1.4", "application/pdf")},
        )
    assert reponse.status_code == 401
