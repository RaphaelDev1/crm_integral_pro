# ==============================================================================
#  TESTS — backend/services/veille_souscriptions_engine.py : détection
#  d'alternatives moins chères pour les souscriptions IA Conseil actives
#  proches de leur fin d'engagement. Même idiome FakeSession que
#  backend/tests/test_alertes_offres_engine.py.
# ==============================================================================
import asyncio
import uuid
from datetime import date, timedelta

from backend.models.ia_conseil import EvenementPlanifie, OffreConseil, Souscription
from backend.models.parametre import Parametre
from backend.services import veille_souscriptions_engine as engine


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


CATEGORIE = "mobile"


def _souscription(**kwargs):
    defaults = dict(
        id=uuid.uuid4(), client_id=uuid.uuid4(), conseiller_id=1, offre_id=uuid.uuid4(),
        statut="active", prix_mensuel_negocie=30.0, fin_engagement=date.today() + timedelta(days=30),
    )
    defaults.update(kwargs)
    return Souscription(**defaults)


def _offre(**kwargs):
    defaults = dict(id=uuid.uuid4(), nom="Eco", categorie_slug=CATEGORIE, prix_mensuel=20.0, valide=True)
    defaults.update(kwargs)
    return OffreConseil(**defaults)


class TestDetecterAlternativesSouscriptions:
    def test_cree_un_evenement_si_economie_depasse_le_seuil(self):
        souscription = _souscription(prix_mensuel_negocie=30.0)
        offre_actuelle = _offre(id=souscription.offre_id, prix_mensuel=30.0)
        offre_alternative = _offre(prix_mensuel=20.0)  # -33%, > seuil 15% par défaut
        db = FakeSession(
            execute_queue=[[souscription], [], [offre_alternative]],  # souscriptions, événements en attente, alternatives
            objets={(OffreConseil, souscription.offre_id): offre_actuelle},
        )

        detectees = _run(engine.detecter_alternatives_souscriptions(db))

        assert len(detectees) == 1
        assert detectees[0]["offre_alternative_id"] == str(offre_alternative.id)
        assert detectees[0]["economie_pourcentage"] == 33.3
        evenement = next(o for o in db.added if isinstance(o, EvenementPlanifie))
        assert evenement.type == engine.TYPE_VEILLE_ALERTE
        assert db.committed

    def test_ignore_si_economie_sous_le_seuil(self):
        souscription = _souscription(prix_mensuel_negocie=30.0)
        offre_actuelle = _offre(id=souscription.offre_id, prix_mensuel=30.0)
        offre_alternative = _offre(prix_mensuel=28.0)  # ~7%, < seuil 15%
        db = FakeSession(
            execute_queue=[[souscription], [], [offre_alternative]],
            objets={(OffreConseil, souscription.offre_id): offre_actuelle},
        )

        detectees = _run(engine.detecter_alternatives_souscriptions(db))

        assert detectees == []
        assert db.added == []

    def test_ignore_si_deja_une_alerte_en_attente_pour_cette_souscription(self):
        souscription = _souscription()
        db = FakeSession(execute_queue=[[souscription], [{"souscription_id": str(souscription.id)}]])

        detectees = _run(engine.detecter_alternatives_souscriptions(db))

        assert detectees == []
        assert db.added == []

    def test_ignore_si_aucune_offre_alternative(self):
        souscription = _souscription()
        offre_actuelle = _offre(id=souscription.offre_id)
        db = FakeSession(
            execute_queue=[[souscription], [], []],
            objets={(OffreConseil, souscription.offre_id): offre_actuelle},
        )

        detectees = _run(engine.detecter_alternatives_souscriptions(db))

        assert detectees == []

    def test_utilise_le_seuil_configure(self):
        souscription = _souscription(prix_mensuel_negocie=30.0)
        offre_actuelle = _offre(id=souscription.offre_id, prix_mensuel=30.0)
        offre_alternative = _offre(prix_mensuel=27.0)  # -10%
        db = FakeSession(
            execute_queue=[[souscription], [], [offre_alternative]],
            objets={
                (OffreConseil, souscription.offre_id): offre_actuelle,
                (Parametre, engine.CLE_PARAMETRE_SEUIL_POURCENTAGE): Parametre(valeur="5"),
            },
        )

        # économie de 10% > seuil configuré de 5% -> une alerte, alors que le
        # seuil par défaut (15%) l'aurait laissée passer.
        detectees = _run(engine.detecter_alternatives_souscriptions(db))

        assert len(detectees) == 1
