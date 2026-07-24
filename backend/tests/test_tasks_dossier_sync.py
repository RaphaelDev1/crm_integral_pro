# ==============================================================================
#  TESTS — backend/workers/tasks.py::_telecharger_mandat_signe : vérifie que la
#  réception du mandat signé (webhook Yousign) fait automatiquement avancer le
#  stepper du dossier correspondant vers "mandat_signe", sans action manuelle
#  du conseiller. AsyncSessionLocal est remplacée par une session factice —
#  aucune connexion Postgres réelle.
# ==============================================================================
import asyncio
from unittest.mock import AsyncMock, patch

from backend.models.client import Client
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.workers import tasks


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def first(self):
        return self._items[0] if self._items else None


class FakeSession:
    def __init__(self, get_map=None, execute_results=None):
        self.get_map = get_map or {}
        self._execute_results = execute_results or []
        self.committed = 0

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        items = self._execute_results.pop(0) if self._execute_results else []
        return _FakeResult(items)

    async def commit(self):
        self.committed += 1

    async def refresh(self, obj):
        pass


class _FakeSessionCM:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


def test_mandat_signe_fait_avancer_le_dossier_correspondant():
    mandat = Mandat(id=1, client_id=1, statut="envoye",
                     yousign_signature_request_id="req1", yousign_document_id="doc1")
    dossier = Dossier(id=1, client_id=1, univers="telecom_mobile", statut="mandat_a_signer", notes_workflow=[])
    client_obj = Client(id=1, prenom="Alice", nom="Martin", email="alice@example.com", telephone="0600000000")

    fake_db = FakeSession(
        get_map={(Mandat, 1): mandat, (Client, 1): client_obj},
        execute_results=[[dossier]],
    )

    with patch("backend.workers.tasks.AsyncSessionLocal", lambda: _FakeSessionCM(fake_db)), \
         patch("backend.services.signature_engine.telecharger_document_signe",
               new=AsyncMock(return_value=b"pdf-bytes")), \
         patch("backend.services.notification_engine.envoyer_email", return_value=True), \
         patch("backend.services.notification_engine.envoyer_sms", return_value=True):
        _run(tasks._telecharger_mandat_signe(1))

    assert mandat.statut == "signe"
    assert dossier.statut == "mandat_signe"
    assert dossier.notes_workflow[-1]["par"] == "webhook_yousign"
    assert dossier.notes_workflow[-1]["vers"] == "mandat_signe"


def test_mandat_signe_sans_dossier_correspondant_ne_leve_pas():
    mandat = Mandat(id=1, client_id=1, statut="envoye",
                     yousign_signature_request_id="req1", yousign_document_id="doc1")

    fake_db = FakeSession(get_map={(Mandat, 1): mandat}, execute_results=[[]])

    with patch("backend.workers.tasks.AsyncSessionLocal", lambda: _FakeSessionCM(fake_db)), \
         patch("backend.services.signature_engine.telecharger_document_signe",
               new=AsyncMock(return_value=b"pdf-bytes")):
        _run(tasks._telecharger_mandat_signe(1))

    assert mandat.statut == "signe"
