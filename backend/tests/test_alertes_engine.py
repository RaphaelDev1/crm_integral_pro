# ==============================================================================
#  TESTS — backend/services/alertes_engine.py : normalisation des niveaux
#  d'alerte (info/attention/critique) et blocage souscription tant qu'une
#  alerte critique n'est pas levée (override + justification). Même idiome
#  FakeSession que backend/tests/test_ia_conseil_engine.py.
# ==============================================================================
import asyncio
import uuid

from backend.models.ia_conseil import AlerteOverride, Recommandation
from backend.services import alertes_engine


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, value):
        self._value = value if isinstance(value, list) else [value]

    def scalars(self):
        return self

    def all(self):
        return self._value

    def first(self):
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


class TestNormaliserNiveau:
    def test_valeurs_connues_inchangees(self):
        assert alertes_engine.normaliser_niveau("info") == "info"
        assert alertes_engine.normaliser_niveau("attention") == "attention"
        assert alertes_engine.normaliser_niveau("critique") == "critique"

    def test_valeur_inconnue_retombe_sur_info(self):
        assert alertes_engine.normaliser_niveau("urgent") == "info"

    def test_valeur_absente_retombe_sur_info(self):
        assert alertes_engine.normaliser_niveau(None) == "info"


class TestSeveriteNormalisee:
    def test_normalise_chaque_alerte_de_la_liste(self):
        alertes = [
            {"regle": "a", "severite": "critique", "message": "x"},
            {"regle": "b", "severite": "grave", "message": "y"},
        ]
        resultat = alertes_engine.severite_normalisee(alertes)
        assert resultat[0]["severite"] == "critique"
        assert resultat[1]["severite"] == "info"
        # ne mute pas les dicts d'origine
        assert alertes[1]["severite"] == "grave"


class TestAlertesCritiquesNonLevees:
    def test_aucune_recommandation_aucune_alerte(self):
        db = FakeSession()
        db.queue_result([])

        resultat = _run(alertes_engine.alertes_critiques_non_levees(db, uuid.uuid4(), uuid.uuid4()))

        assert resultat == []

    def test_recommandation_sans_alerte_critique(self):
        db = FakeSession()
        reco = Recommandation(alertes=[{"regle": "x", "severite": "attention", "message": "m"}])
        db.queue_result([reco])

        resultat = _run(alertes_engine.alertes_critiques_non_levees(db, uuid.uuid4(), uuid.uuid4()))

        assert resultat == []

    def test_alerte_critique_non_levee_est_bloquante(self):
        db = FakeSession()
        reco = Recommandation(alertes=[{"regle": "anti_survente", "severite": "critique", "message": "m"}])
        db.queue_result([reco])  # dernière recommandation
        db.queue_result([])  # aucun override enregistré

        resultat = _run(alertes_engine.alertes_critiques_non_levees(db, uuid.uuid4(), uuid.uuid4()))

        assert len(resultat) == 1
        assert resultat[0]["regle"] == "anti_survente"

    def test_alerte_critique_levee_par_override_n_est_plus_bloquante(self):
        db = FakeSession()
        reco = Recommandation(alertes=[{"regle": "anti_survente", "severite": "critique", "message": "m"}])
        db.queue_result([reco])
        db.queue_result(["anti_survente"])  # override déjà enregistré pour cette règle

        resultat = _run(alertes_engine.alertes_critiques_non_levees(db, uuid.uuid4(), uuid.uuid4()))

        assert resultat == []

    def test_override_d_une_autre_regle_ne_leve_pas_celle_ci(self):
        db = FakeSession()
        reco = Recommandation(alertes=[{"regle": "anti_survente", "severite": "critique", "message": "m"}])
        db.queue_result([reco])
        db.queue_result(["autre_regle"])

        resultat = _run(alertes_engine.alertes_critiques_non_levees(db, uuid.uuid4(), uuid.uuid4()))

        assert len(resultat) == 1
        assert resultat[0]["regle"] == "anti_survente"


class TestEnregistrerOverride:
    def test_cree_et_retourne_l_override(self):
        db = FakeSession()
        session_id, offre_id = uuid.uuid4(), uuid.uuid4()

        override = _run(
            alertes_engine.enregistrer_override(db, session_id, offre_id, "anti_survente", "Client informé, accepte le risque.", conseiller_id=1)
        )

        assert isinstance(override, AlerteOverride)
        assert override in db.added
        assert override.session_id == session_id
        assert override.offre_id == offre_id
        assert override.regle_nom == "anti_survente"
        assert override.conseiller_id == 1
