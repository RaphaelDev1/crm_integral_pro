# ==============================================================================
#  TESTS — backend/core/security.py : compte_verrouille/enregistrer_tentative
#  (rate limiting login, porté depuis src/auth.py qui n'avait pas d'équivalent
#  côté backend/ avant l'unification de l'auth). Session factice, pas de
#  Postgres réel — même idiome que test_dossier_engine.py.
# ==============================================================================
import asyncio
from datetime import datetime, timedelta, timezone

from backend.core.security import FENETRE_MINUTES, compte_verrouille, enregistrer_tentative

_FMT = "%Y-%m-%d %H:%M:%S"


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rows=None):
        self.added = []
        self.committed = False
        self._rows = rows or []

    async def execute(self, _query):
        return _FakeResult(self._rows)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


def _echecs_recents(n: int, decalage_minutes: int = 1):
    maintenant = datetime.now(timezone.utc)
    return [(False, (maintenant - timedelta(minutes=i * decalage_minutes)).strftime(_FMT)) for i in range(n)]


def test_enregistrer_tentative_ajoute_une_ligne_et_commit():
    session = FakeSession()

    _run(enregistrer_tentative(session, "Conseiller1", "1.2.3.4", True))

    assert session.committed is True
    assert len(session.added) == 1
    tentative = session.added[0]
    assert tentative.identifiant == "conseiller1"   # normalisé en minuscules
    assert tentative.ip == "1.2.3.4"
    assert tentative.succes is True


def test_compte_verrouille_sous_le_seuil_autorise():
    session = FakeSession(rows=_echecs_recents(3))

    verrouille, minutes = _run(compte_verrouille(session, "conseiller1", "1.2.3.4"))

    assert verrouille is False
    assert minutes == 0


def test_compte_verrouille_apres_max_tentatives_bloque():
    session = FakeSession(rows=_echecs_recents(5))

    verrouille, minutes = _run(compte_verrouille(session, "conseiller1", "1.2.3.4"))

    assert verrouille is True
    assert 1 <= minutes <= FENETRE_MINUTES


def test_compte_verrouille_reinitialise_par_un_succes_plus_recent():
    maintenant = datetime.now(timezone.utc)
    rows = [(True, maintenant.strftime(_FMT))] + _echecs_recents(5, decalage_minutes=1)
    session = FakeSession(rows=rows)

    verrouille, minutes = _run(compte_verrouille(session, "conseiller1", "1.2.3.4"))

    assert verrouille is False
    assert minutes == 0
