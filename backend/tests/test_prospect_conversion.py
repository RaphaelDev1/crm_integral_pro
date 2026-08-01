# ==============================================================================
#  TESTS — backend/services/prospect_conversion.py. Aucune base de données
#  réelle : une session factice (commit/refresh no-op, execute()/get()
#  pré-remplis) suffit — même idiome que test_dossier_engine.py. Les
#  fonctions testées étant async, exécutées via asyncio.run() (pytest-asyncio
#  non installé dans ce projet).
# ==============================================================================
import asyncio

import pytest

from backend.models.client import Client
from backend.models.prospect import Prospect
from backend.services.prospect_conversion import ProspectDejaConverti, convertir_prospect


def _run(coro):
    return asyncio.run(coro)


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
        self.execute_queue = []
        self.added = []
        self.committed = False
        self._next_id = 100

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        pass


def _prospect(**kwargs):
    base = dict(id=1, prenom="Jean", nom="Dupont", telephone="0600000000",
                economie_estimee_an=100.0, client_id=None, converti_at=None)
    base.update(kwargs)
    return Prospect(**base)


def test_convertit_sans_miroir_existant_cree_un_client():
    db = FakeSession()
    prospect = _prospect()

    client = _run(convertir_prospect(db, prospect, par="Conseiller Test"))

    assert isinstance(client, Client)
    assert client.prenom == "Jean" and client.nom == "Dupont"
    assert any(isinstance(o, Client) for o in db.added)
    assert prospect.client_id == client.id
    assert prospect.converti_at is not None
    assert db.committed is True


def test_convertit_reutilise_le_miroir_existant():
    db = FakeSession()
    miroir = Client(id=7, prenom="Jean", nom="Dupont")
    db.get_map[(Client, 7)] = miroir
    prospect = _prospect(client_id=7)

    client = _run(convertir_prospect(db, prospect, par="Conseiller Test"))

    assert client is miroir
    assert not any(isinstance(o, Client) for o in db.added)  # aucun second Client créé
    assert prospect.client_id == 7


def test_convertit_deja_converti_leve_erreur_et_ne_commit_pas():
    db = FakeSession()
    prospect = _prospect(client_id=7, converti_at="01/01/2026 10:00")

    with pytest.raises(ProspectDejaConverti):
        _run(convertir_prospect(db, prospect, par="Conseiller Test"))

    assert db.added == []
    assert db.committed is False
