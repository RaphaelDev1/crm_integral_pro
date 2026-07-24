# ==============================================================================
#  TESTS — backend/workers/tasks.py : generer_document_demarche,
#  envoyer_demarche_lre, verifier_accuses_lre_en_attente. Même idiome que
#  test_tasks_dossier_sync.py (AsyncSessionLocal remplacée par une session
#  factice, aucune connexion Postgres réelle).
# ==============================================================================
import asyncio
from unittest.mock import patch

from backend.models.client import Client
from backend.models.demarche import Demarche
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.services import lre_engine
from backend.workers import tasks


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

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


# ------------------------------------------------------------------------------
#  generer_document_demarche
# ------------------------------------------------------------------------------
def test_generer_document_demarche_marque_echouee_si_mandat_non_signe():
    dossier = Dossier(id=1, client_id=1, univers="telecom_mobile", statut="mandat_signe")
    demarche = Demarche(id=1, dossier_id=1, type_demarche="resiliation",
                         donnees_requises={"numero_contrat": {"valeur": "CT-1", "requis": True, "label": "x"}})
    fake_db = FakeSession(get_map={(Demarche, 1): demarche, (Dossier, 1): dossier}, execute_results=[[]])

    with patch("backend.workers.tasks.AsyncSessionLocal", lambda: _FakeSessionCM(fake_db)):
        _run(tasks._generer_document_demarche(1))

    assert demarche.statut == "echouee"
    assert "Mandat de représentation non signé" in demarche.notes


def test_generer_document_demarche_ok():
    dossier = Dossier(id=1, client_id=1, univers="telecom_mobile", statut="mandat_signe")
    client_obj = Client(id=1, prenom="Alice", nom="Martin")
    mandat = Mandat(id=9, client_id=1, statut="signe")
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", donnees_requises={})
    fake_db = FakeSession(
        get_map={(Demarche, 1): demarche, (Dossier, 1): dossier, (Client, 1): client_obj},
        execute_results=[[mandat]],
    )

    with patch("backend.workers.tasks.AsyncSessionLocal", lambda: _FakeSessionCM(fake_db)), \
         patch("backend.services.storage_engine.upload_fichier", return_value="dossiers/1/demarches/mandat.pdf"):
        _run(tasks._generer_document_demarche(1))

    assert demarche.statut == "generee"
    assert demarche.document_url == "dossiers/1/demarches/mandat.pdf"


# ------------------------------------------------------------------------------
#  envoyer_demarche_lre
# ------------------------------------------------------------------------------
def test_envoyer_demarche_lre_marque_echouee_si_lre_engine_leve():
    dossier = Dossier(id=1, client_id=1, univers="telecom_mobile", statut="mandat_signe")
    client_obj = Client(id=1, prenom="Alice", nom="Martin", email="alice@example.com")
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="generee",
                         document_url="dossiers/1/demarches/mandat.pdf")
    fake_db = FakeSession(get_map={(Demarche, 1): demarche, (Dossier, 1): dossier, (Client, 1): client_obj})

    with patch("backend.workers.tasks.AsyncSessionLocal", lambda: _FakeSessionCM(fake_db)), \
         patch("backend.services.storage_engine.telecharger_document", return_value=b"pdf-bytes"), \
         patch("backend.services.lre_engine.envoyer_lre",
               side_effect=lre_engine.LreEngineError("AR24_API_KEY absente")):
        _run(tasks._envoyer_demarche_lre(1))

    assert demarche.statut == "echouee"
    assert "AR24_API_KEY absente" in demarche.notes


def test_envoyer_demarche_lre_ok_stocke_preuve_envoi():
    dossier = Dossier(id=1, client_id=1, univers="telecom_mobile", statut="mandat_signe")
    client_obj = Client(id=1, prenom="Alice", nom="Martin", email="alice@example.com")
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="generee",
                         document_url="dossiers/1/demarches/mandat.pdf")
    fake_db = FakeSession(get_map={(Demarche, 1): demarche, (Dossier, 1): dossier, (Client, 1): client_obj})

    with patch("backend.workers.tasks.AsyncSessionLocal", lambda: _FakeSessionCM(fake_db)), \
         patch("backend.services.storage_engine.telecharger_document", return_value=b"pdf-bytes"), \
         patch("backend.services.lre_engine.envoyer_lre",
               return_value={"lre_id": "lre-42", "statut": "envoyee"}):
        _run(tasks._envoyer_demarche_lre(1))

    assert demarche.statut == "envoyee"
    assert demarche.preuve_envoi == "lre-42"
    assert demarche.date_envoi is not None


def test_envoyer_demarche_lre_marque_echouee_si_client_sans_email():
    dossier = Dossier(id=1, client_id=1, univers="telecom_mobile", statut="mandat_signe")
    client_obj = Client(id=1, prenom="Alice", nom="Martin", email=None)
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="generee",
                         document_url="dossiers/1/demarches/mandat.pdf")
    fake_db = FakeSession(get_map={(Demarche, 1): demarche, (Dossier, 1): dossier, (Client, 1): client_obj})

    with patch("backend.workers.tasks.AsyncSessionLocal", lambda: _FakeSessionCM(fake_db)):
        _run(tasks._envoyer_demarche_lre(1))

    assert demarche.statut == "echouee"


# ------------------------------------------------------------------------------
#  verifier_accuses_lre_en_attente
# ------------------------------------------------------------------------------
def test_verifier_accuses_lre_en_attente_marque_accusee():
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="envoyee", preuve_envoi="lre-42")
    fake_db = FakeSession(execute_results=[[demarche]])

    with patch("backend.workers.tasks.AsyncSessionLocal", lambda: _FakeSessionCM(fake_db)), \
         patch("backend.services.lre_engine.verifier_statut_lre",
               return_value={"lre_id": "lre-42", "statut": "distribue"}), \
         patch("backend.services.lre_engine.telecharger_preuve_depot", return_value=b"preuve-bytes"), \
         patch("backend.services.storage_engine.upload_fichier", return_value="dossiers/1/demarches/preuve.pdf"):
        nb = _run(tasks._verifier_accuses_lre_en_attente())

    assert nb == 1
    assert demarche.statut == "accusee"
    assert demarche.preuve_url == "dossiers/1/demarches/preuve.pdf"


def test_verifier_accuses_lre_en_attente_ignore_si_pas_encore_distribue():
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", statut="envoyee", preuve_envoi="lre-42")
    fake_db = FakeSession(execute_results=[[demarche]])

    with patch("backend.workers.tasks.AsyncSessionLocal", lambda: _FakeSessionCM(fake_db)), \
         patch("backend.services.lre_engine.verifier_statut_lre",
               return_value={"lre_id": "lre-42", "statut": "en_transit"}):
        nb = _run(tasks._verifier_accuses_lre_en_attente())

    assert nb == 0
    assert demarche.statut == "envoyee"
