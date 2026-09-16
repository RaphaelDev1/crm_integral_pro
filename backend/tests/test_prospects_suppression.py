# ==============================================================================
#  TESTS — backend/services/prospect_conversion.py::supprimer_prospect.
#  Régression pour le 500 de DELETE /prospects/{id} : un `db.delete(prospect)`
#  seul échouait dès qu'une ligne dépendante (contrat, document, touchpoint...)
#  existait, faute de cascade (violation de contrainte FK non gérée).
# ==============================================================================
import asyncio
from unittest.mock import patch

from sqlalchemy import Delete, Update

from backend.models.document_prospect import DocumentProspect
from backend.models.prospect import Prospect
from backend.services import prospect_conversion


def _run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self, documents=None):
        self._documents = documents or []
        self.executed = []
        self.deleted = []
        self.committed = False

    async def execute(self, stmt):
        self.executed.append(stmt)
        return _FakeResult(self._documents)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.committed = True


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


def _tables_supprimees(executed, cls):
    return [stmt.table.name for stmt in executed if isinstance(stmt, cls)]


def test_supprimer_prospect_jamais_converti_supprime_ses_contrats():
    prospect = Prospect(id=1, client_id=None)
    document = DocumentProspect(id=10, prospect_id=1, type_document="facture", cle_stockage="prospects/1/x.pdf")
    db = FakeSession(documents=[document])

    with patch.object(prospect_conversion, "supprimer_document") as mock_supprimer_document:
        _run(prospect_conversion.supprimer_prospect(db, prospect))

    mock_supprimer_document.assert_called_once_with("prospects/1/x.pdf")
    assert document in db.deleted
    assert prospect in db.deleted
    assert db.committed is True

    tables_supprimees = _tables_supprimees(db.executed, Delete)
    assert "touchpoints" in tables_supprimees
    assert "comparaisons_offres" in tables_supprimees
    assert "tokens_publics" in tables_supprimees
    assert "contrats" in tables_supprimees  # jamais converti -> contrats supprimés avec lui


def test_supprimer_prospect_continue_si_suppression_stockage_echoue():
    """Une erreur de stockage (S3 indisponible, clé corrompue...) ne doit pas
    faire échouer (500) toute la suppression du prospect — voir le
    `except Exception` best-effort dans supprimer_prospect."""
    prospect = Prospect(id=3, client_id=None)
    document = DocumentProspect(id=11, prospect_id=3, type_document="facture", cle_stockage="prospects/3/x.pdf")
    db = FakeSession(documents=[document])

    with patch.object(prospect_conversion, "supprimer_document", side_effect=RuntimeError("S3 down")):
        _run(prospect_conversion.supprimer_prospect(db, prospect))

    assert document in db.deleted
    assert prospect in db.deleted
    assert db.committed is True


def test_supprimer_prospect_converti_detache_ses_contrats_au_lieu_de_les_supprimer():
    prospect = Prospect(id=2, client_id=99)
    db = FakeSession(documents=[])

    with patch.object(prospect_conversion, "supprimer_document"):
        _run(prospect_conversion.supprimer_prospect(db, prospect))

    tables_supprimees = _tables_supprimees(db.executed, Delete)
    tables_detachees = _tables_supprimees(db.executed, Update)
    assert "contrats" not in tables_supprimees  # converti -> contrats du client conservés
    assert "contrats" in tables_detachees
