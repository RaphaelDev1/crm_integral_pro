# ==============================================================================
#  TESTS — routers/portail_public.py::uploader_document, chemin client (pas
#  prospect). Vérifie qu'un document uploadé démarre toujours à "en_attente"
#  et n'est plus jamais validé/rejeté automatiquement par l'analyse KYC — seul
#  un conseiller peut désormais le faire passer "valide" (voir
#  backend/routers/clients.py::valider_document_client). Session factice via
#  app.dependency_overrides[get_db] ; token_engine.valider_token patché —
#  même approche que test_portail_public_prospect.py.
# ==============================================================================
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.main import app
from backend.models.demarche import Demarche
from backend.models.document import Document
from backend.models.dossier import Dossier
from backend.models.token_public import TokenPublic
from backend.services.kyc_engine import KycError


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


def _token_client(**kwargs):
    base = dict(id=1, token="c" * 32, client_id=5, prospect_id=None, dossier_id=None,
                peut_uploader_docs=True, peut_signer_mandat=False,
                peut_voir_suivi=False, peut_renseigner_demarches=False,
                peut_transmettre_speedtest=False)
    base.update(kwargs)
    return TokenPublic(**base)


def test_upload_document_client_reste_en_attente_meme_si_lanalyse_juge_valide(api_client, fake_db):
    # Avant : l'analyse KYC automatique posait directement statut_kyc="valide"
    # dès qu'elle jugeait le document conforme — le conseiller n'avait alors
    # plus rien à vérifier. Un document doit désormais toujours passer par le
    # clic "Valider" du conseiller avant de devenir vert.
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_client())), \
         patch("backend.routers.portail_public.storage_engine.upload_document",
               return_value="clients/5/2026/08/cni_abcd1234.pdf"), \
         patch("backend.routers.portail_public.valider_document",
               return_value={"type": "cni", "valide": True, "motif_rejet": None}):
        reponse = api_client.post(
            f"/portail/{'c' * 32}/documents",
            params={"type_document": "cni"},
            files={"fichier": ("cni.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut_kyc"] == "en_attente"
    documents = [o for o in fake_db.added if isinstance(o, Document)]
    assert len(documents) == 1
    assert documents[0].statut_kyc == "en_attente"


def test_upload_document_client_reste_en_attente_meme_si_lanalyse_juge_non_conforme(api_client, fake_db):
    # Non plus rejeté automatiquement non plus : seul le conseiller décide,
    # via le bouton "Rejeter" (PATCH /clients/{id}/documents/{id}/statut).
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_client())), \
         patch("backend.routers.portail_public.storage_engine.upload_document",
               return_value="clients/5/2026/08/cni_abcd1234.pdf"), \
         patch("backend.routers.portail_public.valider_document",
               return_value={"type": "cni", "valide": False, "motif_rejet": "Photo floue"}):
        reponse = api_client.post(
            f"/portail/{'c' * 32}/documents",
            params={"type_document": "cni"},
            files={"fichier": ("cni.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut_kyc"] == "en_attente"
    assert corps["motif_rejet"] is None


def test_upload_document_client_erreur_technique_garde_le_statut_erreur(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_client())), \
         patch("backend.routers.portail_public.storage_engine.upload_document",
               return_value="clients/5/2026/08/cni_abcd1234.pdf"), \
         patch("backend.routers.portail_public.valider_document",
               side_effect=KycError("fichier illisible")):
        reponse = api_client.post(
            f"/portail/{'c' * 32}/documents",
            params={"type_document": "cni"},
            files={"fichier": ("cni.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut_kyc"] == "erreur"
    assert corps["motif_rejet"] == "fichier illisible"


# ------------------------------------------------------------------------------
#  Blocage tant que le questionnaire secteur (audit_*/portabilite) n'est pas
#  complet — voir demarches_engine.audit_secteur_complet.
# ------------------------------------------------------------------------------
def test_upload_document_refuse_si_questionnaire_secteur_incomplet(api_client, fake_db):
    fake_db.get_map[(Dossier, 7)] = Dossier(id=7, client_id=5, univers="telecom_mobile")
    demarche_incomplete = Demarche(
        id=1, dossier_id=7, type_demarche="audit_mobile", statut="a_generer",
        donnees_requises={"nb_lignes_mobiles": {"valeur": None, "requis": True, "label": "x"}},
    )
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_client(dossier_id=7))), \
         patch("backend.routers.portail_public.demarches_engine.demarches_pour_dossier",
               new=AsyncMock(return_value=[demarche_incomplete])):
        reponse = api_client.post(
            f"/portail/{'c' * 32}/documents",
            params={"type_document": "cni"},
            files={"fichier": ("cni.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 403


def test_upload_document_autorise_si_questionnaire_secteur_complet(api_client, fake_db):
    fake_db.get_map[(Dossier, 7)] = Dossier(id=7, client_id=5, univers="telecom_mobile")
    demarche_complete = Demarche(
        id=1, dossier_id=7, type_demarche="audit_mobile", statut="a_generer",
        donnees_requises={"nb_lignes_mobiles": {"valeur": "1", "requis": True, "label": "x"}},
    )
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_client(dossier_id=7))), \
         patch("backend.routers.portail_public.demarches_engine.demarches_pour_dossier",
               new=AsyncMock(return_value=[demarche_complete])), \
         patch("backend.routers.portail_public.storage_engine.upload_document",
               return_value="clients/5/2026/08/cni_abcd1234.pdf"), \
         patch("backend.routers.portail_public.valider_document",
               return_value={"type": "cni", "valide": True, "motif_rejet": None}):
        reponse = api_client.post(
            f"/portail/{'c' * 32}/documents",
            params={"type_document": "cni"},
            files={"fichier": ("cni.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 200
