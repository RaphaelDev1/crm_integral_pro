# ==============================================================================
#  TESTS — backend/services/anti_biais_engine.py : détection du biais
#  commercial (offre souscrite plus commissionnée que la mieux recommandée).
#  Même idiome FakeSession que backend/tests/test_alertes_offres_engine.py.
# ==============================================================================
import asyncio
import uuid
from unittest.mock import AsyncMock, patch

from backend.models.ia_conseil import Fournisseur, OffreConseil, Recommandation, Souscription
from backend.models.parametre import Parametre
from backend.models.user import User
from backend.services import anti_biais_engine as engine


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

    async def execute(self, _query):
        valeur = self._execute_queue.pop(0) if self._execute_queue else []
        return _FakeResult(valeur)

    async def get(self, model, id_):
        return self._objets.get((model, id_))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


def _fournisseur(taux, **kwargs):
    defaults = dict(id=uuid.uuid4(), nom="F", taux_commission=taux)
    defaults.update(kwargs)
    return Fournisseur(**defaults)


def _offre(fournisseur_id, prix=20.0, **kwargs):
    defaults = dict(id=uuid.uuid4(), nom="O", prix_mensuel=prix, fournisseur_id=fournisseur_id)
    defaults.update(kwargs)
    return OffreConseil(**defaults)


class TestAuditerBiaisCommercial:
    def test_offre_souscrite_est_le_rang_1_jamais_un_biais(self):
        session_id = uuid.uuid4()
        offre_id = uuid.uuid4()
        souscription = Souscription(id=uuid.uuid4(), session_id=session_id, offre_id=offre_id, conseiller_id=1)
        reco = Recommandation(session_id=session_id, offre_id=offre_id, rang=1)
        db = FakeSession(execute_queue=[[souscription], [reco]])

        resultats = _run(engine.auditer_biais_commercial(db))

        assert resultats[0]["nb_biais_possible"] == 0
        assert resultats[0]["nb_souscriptions_avec_session"] == 1

    def test_offre_souscrite_differente_et_plus_commissionnee_est_un_biais(self):
        session_id = uuid.uuid4()
        offre_rang1_id = uuid.uuid4()
        offre_souscrite_id = uuid.uuid4()
        souscription = Souscription(id=uuid.uuid4(), session_id=session_id, offre_id=offre_souscrite_id, conseiller_id=1)
        reco_rang1 = Recommandation(session_id=session_id, offre_id=offre_rang1_id, rang=1)

        fournisseur_faible = _fournisseur(taux=5.0)
        fournisseur_fort = _fournisseur(taux=20.0)
        offre_rang1 = _offre(fournisseur_faible.id, prix=20.0)
        offre_souscrite = _offre(fournisseur_fort.id, prix=20.0)

        db = FakeSession(
            execute_queue=[[souscription], [reco_rang1]],
            objets={
                (OffreConseil, offre_souscrite_id): offre_souscrite,
                (Fournisseur, fournisseur_fort.id): fournisseur_fort,
                (OffreConseil, offre_rang1_id): offre_rang1,
                (Fournisseur, fournisseur_faible.id): fournisseur_faible,
            },
        )

        resultats = _run(engine.auditer_biais_commercial(db))

        assert resultats[0]["nb_biais_possible"] == 1
        assert resultats[0]["ratio"] == 1.0
        assert resultats[0]["au_dela_du_seuil"] is True  # ratio 1.0 > seuil défaut 0.3

    def test_offre_souscrite_differente_mais_moins_commissionnee_n_est_pas_un_biais(self):
        session_id = uuid.uuid4()
        offre_rang1_id = uuid.uuid4()
        offre_souscrite_id = uuid.uuid4()
        souscription = Souscription(id=uuid.uuid4(), session_id=session_id, offre_id=offre_souscrite_id, conseiller_id=1)
        reco_rang1 = Recommandation(session_id=session_id, offre_id=offre_rang1_id, rang=1)

        fournisseur_faible = _fournisseur(taux=5.0)
        fournisseur_fort = _fournisseur(taux=20.0)
        offre_rang1 = _offre(fournisseur_fort.id, prix=20.0)
        offre_souscrite = _offre(fournisseur_faible.id, prix=20.0)

        db = FakeSession(
            execute_queue=[[souscription], [reco_rang1]],
            objets={
                (OffreConseil, offre_souscrite_id): offre_souscrite,
                (Fournisseur, fournisseur_faible.id): fournisseur_faible,
                (OffreConseil, offre_rang1_id): offre_rang1,
                (Fournisseur, fournisseur_fort.id): fournisseur_fort,
            },
        )

        resultats = _run(engine.auditer_biais_commercial(db))

        assert resultats[0]["nb_biais_possible"] == 0

    def test_sans_recommandation_ignore_la_souscription(self):
        souscription = Souscription(id=uuid.uuid4(), session_id=uuid.uuid4(), offre_id=uuid.uuid4(), conseiller_id=1)
        db = FakeSession(execute_queue=[[souscription], []])

        resultats = _run(engine.auditer_biais_commercial(db))

        assert resultats == []

    def test_utilise_le_seuil_configure(self):
        session_id = uuid.uuid4()
        offre_rang1_id = uuid.uuid4()
        offre_souscrite_id = uuid.uuid4()
        souscription = Souscription(id=uuid.uuid4(), session_id=session_id, offre_id=offre_souscrite_id, conseiller_id=1)
        reco_rang1 = Recommandation(session_id=session_id, offre_id=offre_rang1_id, rang=1)

        fournisseur_faible = _fournisseur(taux=5.0)
        fournisseur_fort = _fournisseur(taux=20.0)
        offre_rang1 = _offre(fournisseur_faible.id, prix=20.0)
        offre_souscrite = _offre(fournisseur_fort.id, prix=20.0)

        db = FakeSession(
            execute_queue=[[souscription], [reco_rang1]],
            objets={
                (OffreConseil, offre_souscrite_id): offre_souscrite,
                (Fournisseur, fournisseur_fort.id): fournisseur_fort,
                (OffreConseil, offre_rang1_id): offre_rang1,
                (Fournisseur, fournisseur_faible.id): fournisseur_faible,
                (Parametre, engine.CLE_PARAMETRE_SEUIL_RATIO): Parametre(valeur="2"),
            },
        )

        resultats = _run(engine.auditer_biais_commercial(db))

        assert resultats[0]["au_dela_du_seuil"] is False  # ratio 1.0 <= seuil configuré 2.0


class TestAuditerEtNotifierSuperviseurs:
    def test_notifie_les_admins_si_conseiller_au_dela_du_seuil(self):
        session_id = uuid.uuid4()
        offre_rang1_id = uuid.uuid4()
        offre_souscrite_id = uuid.uuid4()
        souscription = Souscription(id=uuid.uuid4(), session_id=session_id, offre_id=offre_souscrite_id, conseiller_id=1)
        reco_rang1 = Recommandation(session_id=session_id, offre_id=offre_rang1_id, rang=1)

        fournisseur_faible = _fournisseur(taux=5.0)
        fournisseur_fort = _fournisseur(taux=20.0)
        offre_rang1 = _offre(fournisseur_faible.id, prix=20.0)
        offre_souscrite = _offre(fournisseur_fort.id, prix=20.0)
        admin = User(id=2, username="admin", nom_complet="Admin", password_hash="x", role="Admin", actif=True)

        db = FakeSession(
            execute_queue=[[souscription], [reco_rang1], [admin]],
            objets={
                (OffreConseil, offre_souscrite_id): offre_souscrite,
                (Fournisseur, fournisseur_fort.id): fournisseur_fort,
                (OffreConseil, offre_rang1_id): offre_rang1,
                (Fournisseur, fournisseur_faible.id): fournisseur_faible,
            },
        )

        with patch.object(engine.notification_engine, "creer_notification_generique", new=AsyncMock()) as mock_notif:
            resultats = _run(engine.auditer_et_notifier_superviseurs(db))

        assert resultats[0]["au_dela_du_seuil"] is True
        mock_notif.assert_awaited_once()
        assert mock_notif.call_args.args[1] == admin.id

    def test_aucune_notification_si_personne_au_dela_du_seuil(self):
        session_id = uuid.uuid4()
        offre_id = uuid.uuid4()
        souscription = Souscription(id=uuid.uuid4(), session_id=session_id, offre_id=offre_id, conseiller_id=1)
        reco = Recommandation(session_id=session_id, offre_id=offre_id, rang=1)
        db = FakeSession(execute_queue=[[souscription], [reco]])

        with patch.object(engine.notification_engine, "creer_notification_generique", new=AsyncMock()) as mock_notif:
            _run(engine.auditer_et_notifier_superviseurs(db))

        mock_notif.assert_not_awaited()
