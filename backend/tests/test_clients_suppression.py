# ==============================================================================
#  TESTS — backend/services/client_suppression.py::supprimer_client.
#  Régression pour le 500 de DELETE /clients/{id} : un `db.delete(client)` seul
#  échouait dès qu'une ligne dépendante (dossier, contrat, mandat...) existait,
#  faute de cascade (violation de contrainte FK non gérée).
# ==============================================================================
import asyncio

import pytest
from sqlalchemy import Delete, Select, Update

from backend.models.client import Client
from backend.services import client_suppression


def _run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self, tables_avec_lignes=None):
        self._tables_avec_lignes = set(tables_avec_lignes or ())
        self.executed = []
        self.deleted = []
        self.committed = False

    async def execute(self, stmt):
        self.executed.append(stmt)
        if isinstance(stmt, Select):
            table_name = list(stmt.selected_columns)[0].table.name
            valeur = 1 if table_name in self._tables_avec_lignes else None
            return _FakeScalarResult(valeur)
        return _FakeResult([])

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.committed = True


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


def _tables_touchees(executed, cls):
    return [stmt.table.name for stmt in executed if isinstance(stmt, cls)]


def test_supprimer_client_sans_donnees_bloquantes_supprime_et_nettoie_les_annexes():
    client = Client(id=5)
    db = FakeSession(tables_avec_lignes=set())

    _run(client_suppression.supprimer_client(db, client))

    assert client in db.deleted
    assert db.committed is True

    tables_supprimees = _tables_touchees(db.executed, Delete)
    assert "tokens_publics" in tables_supprimees
    assert "alertes_offres" in tables_supprimees
    assert "comparaisons_offres" in tables_supprimees

    tables_detachees = _tables_touchees(db.executed, Update)
    assert "prospects" in tables_detachees  # prospects historiques -> client_id=None


@pytest.mark.parametrize(
    "table_bloquante",
    ["dossiers", "mandats", "contrats", "factures_analysees", "abonnements", "documents"],
)
def test_supprimer_client_bloque_si_donnee_importante_liee(table_bloquante):
    client = Client(id=7)
    db = FakeSession(tables_avec_lignes={table_bloquante})

    with pytest.raises(client_suppression.ClientSuppressionBloquee):
        _run(client_suppression.supprimer_client(db, client))

    assert client not in db.deleted
    assert db.committed is False
