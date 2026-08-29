# ==============================================================================
#  TESTS — backend/services/cross_sell_engine.py : suggestions inter-catégories
#  (convergence mobile/box, roaming fréquent, conso énergie + télétravail).
#  Même idiome FakeSession que backend/tests/test_ia_conseil_engine.py.
# ==============================================================================
import asyncio
import uuid

from backend.models.ia_conseil import OffreConseil, SessionTrame, Souscription
from backend.services import cross_sell_engine as engine


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
    def __init__(self, execute_queue=None):
        self._execute_queue = list(execute_queue or [])

    async def execute(self, _query):
        valeur = self._execute_queue.pop(0) if self._execute_queue else []
        return _FakeResult(valeur)


def _offre(categorie, fournisseur_id, **kwargs):
    defaults = dict(id=uuid.uuid4(), nom="O", categorie_slug=categorie, fournisseur_id=fournisseur_id, caracteristiques={})
    defaults.update(kwargs)
    return OffreConseil(**defaults)


def _session(categorie, reponses):
    return SessionTrame(id=uuid.uuid4(), categorie_slug=categorie, reponses=reponses)


class TestSuggestionConvergence:
    def test_deux_fournisseurs_differents_declenche_la_convergence(self):
        f1, f2 = uuid.uuid4(), uuid.uuid4()
        offre_mobile = _offre("mobile", f1)
        offre_box = _offre("box", f2)
        paires = [(Souscription(offre_id=offre_mobile.id), offre_mobile), (Souscription(offre_id=offre_box.id), offre_box)]

        resultat = engine._suggestion_convergence(paires)

        assert resultat is not None
        assert resultat["type"] == engine.TYPE_CONVERGENCE

    def test_meme_fournisseur_ne_declenche_rien(self):
        f1 = uuid.uuid4()
        offre_mobile = _offre("mobile", f1)
        offre_box = _offre("box", f1)
        paires = [(Souscription(offre_id=offre_mobile.id), offre_mobile), (Souscription(offre_id=offre_box.id), offre_box)]

        assert engine._suggestion_convergence(paires) is None

    def test_une_seule_categorie_ne_declenche_rien(self):
        offre_mobile = _offre("mobile", uuid.uuid4())
        paires = [(Souscription(offre_id=offre_mobile.id), offre_mobile)]

        assert engine._suggestion_convergence(paires) is None

    def test_liste_vide_ne_declenche_rien(self):
        assert engine._suggestion_convergence([]) is None


class TestSuggestionRoaming:
    def test_roaming_ue_souvent_declenche_la_suggestion(self):
        sessions = [_session("mobile", {"roaming_ue": "Souvent"})]
        resultat = engine._suggestion_roaming(sessions)
        assert resultat is not None
        assert resultat["categorie_source"] == "mobile"

    def test_roaming_occasionnel_ne_declenche_rien(self):
        sessions = [_session("mobile", {"roaming_ue": "Occasionnellement"})]
        assert engine._suggestion_roaming(sessions) is None

    def test_question_absente_ne_leve_pas_d_erreur(self):
        sessions = [_session("mobile", {})]
        assert engine._suggestion_roaming(sessions) is None

    def test_ignore_les_sessions_hors_mobile(self):
        sessions = [_session("box", {"roaming_ue": "Souvent"})]
        assert engine._suggestion_roaming(sessions) is None

    def test_reponses_none_ne_leve_pas_d_erreur(self):
        sessions = [SessionTrame(id=uuid.uuid4(), categorie_slug="mobile", reponses=None)]
        assert engine._suggestion_roaming(sessions) is None


class TestSuggestionRenovation:
    def test_conso_forte_et_teletravail_declenche_la_suggestion(self):
        sessions = [_session("energie_elec", {"conso_kwh_annuelle": 9000, "teletravail": True})]
        resultat = engine._suggestion_renovation(sessions)
        assert resultat is not None
        assert resultat["categorie_source"] == "energie_elec"

    def test_conso_forte_sans_teletravail_ne_declenche_rien(self):
        sessions = [_session("energie_elec", {"conso_kwh_annuelle": 9000})]
        assert engine._suggestion_renovation(sessions) is None

    def test_questions_absentes_ne_leve_pas_d_erreur(self):
        sessions = [_session("energie_gaz", {})]
        assert engine._suggestion_renovation(sessions) is None

    def test_ignore_les_sessions_hors_energie(self):
        sessions = [_session("mobile", {"conso_kwh_annuelle": 9000, "teletravail": True})]
        assert engine._suggestion_renovation(sessions) is None


class TestSuggestionsCrossSell:
    def test_agrege_toutes_les_suggestions_declenchees(self):
        f1, f2 = uuid.uuid4(), uuid.uuid4()
        offre_mobile = _offre("mobile", f1)
        offre_box = _offre("box", f2)
        paires = [(Souscription(offre_id=offre_mobile.id), offre_mobile), (Souscription(offre_id=offre_box.id), offre_box)]
        sessions = [_session("mobile", {"roaming_ue": "Souvent"})]
        db = FakeSession(execute_queue=[paires, sessions])

        resultats = _run(engine.suggestions_cross_sell(db, uuid.uuid4()))

        assert {r["type"] for r in resultats} == {engine.TYPE_CONVERGENCE, engine.TYPE_CONSEIL}

    def test_rien_de_declenche_renvoie_liste_vide(self):
        db = FakeSession(execute_queue=[[], []])

        resultats = _run(engine.suggestions_cross_sell(db, uuid.uuid4()))

        assert resultats == []
