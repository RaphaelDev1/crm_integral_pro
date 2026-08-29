# ==============================================================================
#  TESTS — backend/services/evenement_planifie_engine.py : planification
#  idempotente des relances (fin d'engagement, bilan annuel, NPS) et
#  exécution des événements échus. Même idiome FakeSession que
#  backend/tests/test_alertes_offres_engine.py.
# ==============================================================================
import asyncio
import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from backend.models.ia_conseil import ClientConseil, EvenementPlanifie, Souscription
from backend.services import evenement_planifie_engine as engine


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, value):
        self._value = value if isinstance(value, list) else [value]

    def scalars(self):
        return self

    def all(self):
        return self._value


class FakeSession:
    def __init__(self, execute_queue=None, objets=None):
        self._execute_queue = list(execute_queue or [])
        self._objets = objets or {}
        self.added = []
        self.committed = False

    async def execute(self, _query):
        valeur = self._execute_queue.pop(0) if self._execute_queue else []
        return _FakeResult(valeur)

    async def get(self, model, id_):
        return self._objets.get((model, id_))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


class TestPlanifierEvenementsManquants:
    def test_cree_les_trois_evenements_pour_une_souscription_active_complete(self):
        souscription = Souscription(
            id=uuid.uuid4(), client_id=uuid.uuid4(), conseiller_id=1, statut="active",
            fin_engagement=date(2027, 1, 1), date_activation=date(2026, 1, 1),
        )
        db = FakeSession(execute_queue=[[souscription], []])  # souscriptions, événements existants

        crees = _run(engine.planifier_evenements_manquants(db))

        assert crees == 3
        types = {e.type for e in db.added}
        assert types == {engine.TYPE_FIN_ENGAGEMENT, engine.TYPE_BILAN_ANNUEL, engine.TYPE_NPS_J30}
        assert db.committed

    def test_ignore_les_evenements_deja_planifies(self):
        client_id = uuid.uuid4()
        souscription = Souscription(
            id=uuid.uuid4(), client_id=client_id, conseiller_id=1, statut="active",
            fin_engagement=date(2027, 1, 1), date_activation=None,
        )
        date_prevue_existante = date(2027, 1, 1) - timedelta(days=60)
        db = FakeSession(execute_queue=[[souscription], [(client_id, engine.TYPE_FIN_ENGAGEMENT, date_prevue_existante)]])

        crees = _run(engine.planifier_evenements_manquants(db))

        assert crees == 0
        assert db.added == []

    def test_ignore_souscription_sans_date(self):
        souscription = Souscription(id=uuid.uuid4(), client_id=uuid.uuid4(), statut="active", fin_engagement=None, date_activation=None)
        db = FakeSession(execute_queue=[[souscription], []])

        crees = _run(engine.planifier_evenements_manquants(db))

        assert crees == 0


class TestExecuterEvenementsDuJour:
    def test_envoie_email_et_notification_puis_marque_execute(self):
        client_id = uuid.uuid4()
        client = ClientConseil(id=client_id, prenom="Jean", email="jean@example.com")
        evenement = EvenementPlanifie(
            id=uuid.uuid4(), client_id=client_id, conseiller_id=1,
            type=engine.TYPE_FIN_ENGAGEMENT, date_prevue=date.today(), payload={}, execute=False,
        )
        db = FakeSession(execute_queue=[[evenement]], objets={(ClientConseil, client_id): client})

        with patch.object(engine.notification_engine, "envoyer_email", return_value=True) as mock_email, \
             patch.object(engine.notification_engine, "creer_notification_generique", new=AsyncMock()) as mock_notif:
            n = _run(engine.executer_evenements_du_jour(db))

        assert n == 1
        assert evenement.execute is True
        assert evenement.execute_le is not None
        mock_email.assert_called_once()
        mock_notif.assert_awaited_once()
        assert db.committed

    def test_sans_client_ne_leve_pas_et_notifie_quand_meme_le_conseiller(self):
        evenement = EvenementPlanifie(
            id=uuid.uuid4(), client_id=None, conseiller_id=1,
            type=engine.TYPE_NPS_J30, date_prevue=date.today(), payload={}, execute=False,
        )
        db = FakeSession(execute_queue=[[evenement]])

        with patch.object(engine.notification_engine, "envoyer_email") as mock_email, \
             patch.object(engine.notification_engine, "creer_notification_generique", new=AsyncMock()) as mock_notif:
            n = _run(engine.executer_evenements_du_jour(db))

        assert n == 1
        mock_email.assert_not_called()
        mock_notif.assert_awaited_once()

    def test_aucun_evenement_echu_ne_fait_rien(self):
        db = FakeSession(execute_queue=[[]])

        n = _run(engine.executer_evenements_du_jour(db))

        assert n == 0
        assert db.committed
