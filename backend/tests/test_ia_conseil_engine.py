# ==============================================================================
#  TESTS — services/ia_conseil_engine.py (orchestration DB <-> rules_engine).
#  Session factice (même approche que test_dossier_engine.py) : db.execute()
#  consomme une file de résultats préparés à l'avance, indépendamment du SQL
#  réellement émis (on connaît l'ordre d'appel de chaque fonction testée).
#  Fonctions testées async -> exécutées via asyncio.run() (pytest-asyncio non
#  installé dans ce projet, voir test_dossier_engine.py).
# ==============================================================================
import asyncio
import uuid

import pytest

from backend.models.ia_conseil import OffreConseil, Recommandation, RegleRecommandation, SessionTrame, TrameTemplate
from backend.services import ia_conseil_engine as engine


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, value):
        self._value = value if isinstance(value, list) else [value]

    def scalars(self):
        return self

    def all(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value[0] if self._value else None


class FakeSession:
    def __init__(self):
        self.execute_queue = []
        self.added = []

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


CATEGORIE = "mobile"

TRAME_SIMPLE = {
    "sections": [{"id": "s", "questions": [{"id": "conso_data_go", "cout_cognitif": 1, "poids_ethique": 5}]}],
    "branches": [],
}


def _offre(nom="Eco 20Go", prix=15.0, data_go=20, fournisseur_id=None):
    return OffreConseil(
        id=uuid.uuid4(),
        nom=nom,
        categorie_slug=CATEGORIE,
        prix_mensuel=prix,
        caracteristiques={"data_go": data_go},
        valide=True,
        fournisseur_id=fournisseur_id,
    )


class TestCreerSession:
    def test_cree_la_session_avec_la_trame_active_la_plus_recente(self):
        db = FakeSession()
        trame_v2 = TrameTemplate(id=uuid.uuid4(), categorie_slug=CATEGORIE, version=2, definition=TRAME_SIMPLE, actif=True)
        db.queue_result(trame_v2)

        session = _run(engine.creer_session(db, uuid.uuid4(), CATEGORIE, conseiller_id=1, canal="visio"))

        assert session.categorie_slug == CATEGORIE
        assert session.trame_template_id == trame_v2.id
        assert session.canal == "visio"
        assert session in db.added

    def test_leve_si_aucune_trame_active(self):
        db = FakeSession()
        db.queue_result(None)

        with pytest.raises(engine.TrameIntrouvableError):
            _run(engine.creer_session(db, uuid.uuid4(), "categorie_inconnue", conseiller_id=1, canal=None))


class TestEnregistrerReponse:
    def test_ajoute_la_reponse_sans_ecraser_les_precedentes(self):
        db = FakeSession()
        session = SessionTrame(id=uuid.uuid4(), reponses={"nb_lignes": 2})

        _run(engine.enregistrer_reponse(db, session, "conso_data_go", 5))

        assert session.reponses == {"nb_lignes": 2, "conso_data_go": 5}

    def test_reponses_none_initiales_geree(self):
        db = FakeSession()
        session = SessionTrame(id=uuid.uuid4(), reponses=None)

        _run(engine.enregistrer_reponse(db, session, "a", 1))

        assert session.reponses == {"a": 1}


class TestCalculerRecommandations:
    def test_persiste_et_retourne_le_classement(self):
        db = FakeSession()
        offre_eco = _offre("Eco", prix=15.0, data_go=20)
        offre_xl = _offre("XL", prix=40.0, data_go=200)
        regle = RegleRecommandation(
            nom="anti_survente",
            type="scoring",
            categorie_slug=CATEGORIE,
            priorite=0,
            condition={
                "$and": [
                    {"reponses.conso_data_go": {"$lt": 10}},
                    {"offre.caracteristiques.data_go": {"$gt": 50}},
                ]
            },
            action={"kind": "score_adjust", "valeur": -50},
            actif=True,
        )
        db.queue_result([offre_eco, offre_xl])  # charger_offres_actives
        db.queue_result([regle])  # charger_regles_actives
        db.queue_result([])  # delete Recommandation (résultat ignoré)

        session = SessionTrame(id=uuid.uuid4(), categorie_slug=CATEGORIE, reponses={"conso_data_go": 3})

        resultats = _run(engine.calculer_recommandations(db, session))

        assert resultats[0]["offre"] is offre_eco  # score le plus élevé (pas pénalisée)
        assert resultats[1]["offre"] is offre_xl
        recommandations_persistees = [o for o in db.added if isinstance(o, Recommandation)]
        assert len(recommandations_persistees) == 2
        assert recommandations_persistees[0].session_id == session.id

    def test_calcule_l_economie_si_cout_actuel_declare(self):
        db = FakeSession()
        offre = _offre("Eco", prix=15.0, data_go=20)
        db.queue_result([offre])
        db.queue_result([])
        db.queue_result([])

        session = SessionTrame(id=uuid.uuid4(), categorie_slug=CATEGORIE, reponses={"cout_actuel_mensuel": 25})

        resultats = _run(engine.calculer_recommandations(db, session))

        assert resultats[0]["economie_mensuelle"] == pytest.approx(10.0)
        assert resultats[0]["economie_annuelle"] == pytest.approx(120.0)

    def test_sans_cout_actuel_economie_est_none(self):
        db = FakeSession()
        offre = _offre("Eco", prix=15.0, data_go=20)
        db.queue_result([offre])
        db.queue_result([])
        db.queue_result([])

        session = SessionTrame(id=uuid.uuid4(), categorie_slug=CATEGORIE, reponses={})

        resultats = _run(engine.calculer_recommandations(db, session))

        assert resultats[0]["economie_mensuelle"] is None
        assert resultats[0]["economie_annuelle"] is None


class TestFinaliserSession:
    def test_marque_la_session_terminee(self):
        db = FakeSession()
        session = SessionTrame(id=uuid.uuid4(), etat="en_cours", terminee_le=None)

        _run(engine.finaliser_session(db, session))

        assert session.etat == "terminee"
        assert session.terminee_le is not None
