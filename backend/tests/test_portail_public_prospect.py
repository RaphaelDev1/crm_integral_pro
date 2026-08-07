# ==============================================================================
#  TESTS — routers/portail_public.py, chemin token scopé "prospect" (upload de
#  facture/speedtest avant conversion en client, cf. section 1.3 du plan de
#  migration). Session factice via app.dependency_overrides[get_db] ;
#  token_engine.valider_token patché — même approche que
#  test_portail_public_speedtest.py.
# ==============================================================================
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.main import app
from backend.models.document_prospect import DocumentProspect
from backend.models.prospect import Prospect
from backend.models.token_public import TokenPublic


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.committed = False
        self.added = []
        self.execute_queue = []

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

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


def _token_prospect(**kwargs):
    base = dict(id=1, token="p" * 32, client_id=None, prospect_id=1,
                peut_uploader_docs=True, peut_signer_mandat=False,
                peut_voir_suivi=False, peut_renseigner_demarches=False,
                peut_transmettre_speedtest=False)
    base.update(kwargs)
    return TokenPublic(**base)


def test_contexte_token_prospect_renvoie_un_contexte_reduit(api_client, fake_db):
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont", cree_par="Alice")
    fake_db.queue_result([])  # aucun DocumentProspect déjà transmis

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.get(f"/portail/{'p' * 32}")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["prenom_client"] == "Jean"
    assert corps["nom_client"] == "Dupont"
    assert corps["dossier_id"] is None
    assert corps["peut_signer_mandat"] is False
    # Le lien prospect propose la facture à l'upload (auparavant vide par
    # erreur — voir _contexte_token_prospect). Le test de débit n'y figure
    # volontairement pas : il a son propre parcours dédié (section "Votre
    # débit internet" + page /speedtest) pour laisser au client l'occasion
    # de cliquer sur "Tester mon débit" plutôt que de le marquer fait
    # automatiquement dès l'envoi des documents.
    types_proposes = {d["type_document"] for d in corps["documents_a_fournir"]}
    assert types_proposes == {"facture"}
    assert all(d["statut"] == "a_fournir" for d in corps["documents_a_fournir"])


def test_contexte_token_prospect_introuvable(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.get(f"/portail/{'p' * 32}")

    assert reponse.status_code == 404


def test_upload_document_prospect_cree_un_document_prospect(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())), \
         patch("backend.routers.portail_public.storage_engine.upload_fichier",
               return_value="prospects/1/2026/08/facture_abcd1234_efgh5678.pdf"):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/documents",
            params={"type_document": "facture"},
            files={"fichier": ("facture.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut_kyc"] == "recu"
    documents = [o for o in fake_db.added if isinstance(o, DocumentProspect)]
    assert len(documents) == 1
    assert documents[0].prospect_id == 1
    assert documents[0].type_document == "facture"


def test_upload_document_prospect_type_non_autorise_rejete(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/documents",
            params={"type_document": "cni"},
            files={"fichier": ("cni.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 422


def test_upload_document_prospect_refuse_si_non_autorise_par_le_token(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect(peut_uploader_docs=False))):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/documents",
            params={"type_document": "facture"},
            files={"fichier": ("facture.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 403
