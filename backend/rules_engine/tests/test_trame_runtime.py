# ==============================================================================
#  TESTS — trame_runtime. Scénarios "trame en Y" (branche roaming mobile) et
#  "trame avec skip", d'après l'exemple §0.2 du plan.
# ==============================================================================
from backend.rules_engine.trame_runtime import (
    flags_actifs,
    is_terminee,
    next_question,
    questions_eligibles,
)

TRAME_MOBILE = {
    "id": "trame_mobile_v1",
    "categorie": "mobile",
    "sections": [
        {
            "id": "decouverte",
            "questions": [
                {"id": "nb_lignes", "label": "Combien de lignes ?", "type": "number"},
                {"id": "operateur_actuel", "label": "Opérateur actuel ?", "type": "select"},
                {"id": "conso_data_go", "label": "Conso data (Go) ?", "type": "number"},
            ],
        },
        {
            "id": "usages",
            "questions": [
                {"id": "roaming_ue", "label": "Voyages en Europe ?", "type": "select"},
                {
                    "id": "roaming_hors_ue",
                    "label": "Voyages hors UE ?",
                    "type": "select",
                    "show_if": {"roaming_ue": {"$ne": "Jamais"}},
                },
                {"id": "qualite_reseau", "label": "Qualité réseau ?", "type": "select"},
                {"id": "5g_importante", "label": "5G importante ?", "type": "boolean"},
                {"id": "partage_connexion", "label": "Partage de connexion ?", "type": "boolean"},
            ],
        },
    ],
    "branches": [
        {
            "when": {"nb_lignes": {"$gte": 2}},
            "insert_after": "nb_lignes",
            "questions": [{"id": "meme_operateur_famille", "label": "Même opérateur pour toute la famille ?"}],
        },
        {
            "when": {"conso_data_go": {"$lt": 5}},
            "skip": ["5g_importante", "partage_connexion"],
            "flags": ["anti_survente_mobile"],
        },
    ],
}


def _ids(questions):
    return [q["id"] for q in questions]


class TestShowIfTrameEnY:
    def test_roaming_hors_ue_absente_quand_roaming_ue_jamais(self):
        reponses = {"nb_lignes": 1, "operateur_actuel": "Orange", "conso_data_go": 20, "roaming_ue": "Jamais"}
        eligibles = _ids(questions_eligibles(TRAME_MOBILE, reponses))
        assert "roaming_hors_ue" not in eligibles

    def test_roaming_hors_ue_eligible_quand_roaming_ue_repondu_differemment(self):
        reponses = {"nb_lignes": 1, "operateur_actuel": "Orange", "conso_data_go": 20, "roaming_ue": "Souvent"}
        eligibles = _ids(questions_eligibles(TRAME_MOBILE, reponses))
        assert "roaming_hors_ue" in eligibles

    def test_roaming_hors_ue_absente_tant_que_roaming_ue_non_repondue(self):
        reponses = {"nb_lignes": 1, "operateur_actuel": "Orange", "conso_data_go": 20}
        eligibles = _ids(questions_eligibles(TRAME_MOBILE, reponses))
        assert "roaming_hors_ue" not in eligibles


class TestBrancheInsertion:
    def test_meme_operateur_famille_absente_si_une_seule_ligne(self):
        reponses = {"nb_lignes": 1}
        eligibles = _ids(questions_eligibles(TRAME_MOBILE, reponses))
        assert "meme_operateur_famille" not in eligibles

    def test_meme_operateur_famille_eligible_si_plusieurs_lignes(self):
        reponses = {"nb_lignes": 3}
        eligibles = _ids(questions_eligibles(TRAME_MOBILE, reponses))
        assert "meme_operateur_famille" in eligibles

    def test_question_repondue_disparait_meme_si_inseree_par_branche(self):
        reponses = {"nb_lignes": 3, "meme_operateur_famille": True}
        eligibles = _ids(questions_eligibles(TRAME_MOBILE, reponses))
        assert "meme_operateur_famille" not in eligibles


class TestSkip:
    def test_5g_et_partage_skippees_si_petite_conso(self):
        reponses = {"conso_data_go": 3}
        eligibles = _ids(questions_eligibles(TRAME_MOBILE, reponses))
        assert "5g_importante" not in eligibles
        assert "partage_connexion" not in eligibles

    def test_5g_et_partage_eligibles_si_grosse_conso(self):
        reponses = {"conso_data_go": 50}
        eligibles = _ids(questions_eligibles(TRAME_MOBILE, reponses))
        assert "5g_importante" in eligibles
        assert "partage_connexion" in eligibles

    def test_flags_actifs_expose_les_flags_de_branche(self):
        assert flags_actifs(TRAME_MOBILE, {"conso_data_go": 3}) == ["anti_survente_mobile"]
        assert flags_actifs(TRAME_MOBILE, {"conso_data_go": 50}) == []


class TestChampsRequisPourShowIf:
    def test_show_if_and_exige_toutes_les_reponses_dont_il_depend(self):
        trame = {
            "sections": [
                {
                    "id": "s",
                    "questions": [
                        {"id": "a"},
                        {"id": "b"},
                        {"id": "derivee", "show_if": {"$and": [{"a": {"$eq": 1}}, {"b": {"$eq": 2}}]}},
                    ],
                }
            ],
            "branches": [],
        }
        assert "derivee" not in _ids(questions_eligibles(trame, {"a": 1}))
        assert "derivee" in _ids(questions_eligibles(trame, {"a": 1, "b": 2}))

    def test_show_if_or_n_exige_pas_l_existence_prealable(self):
        # limitation connue et documentée : sous $or, on ne peut pas déterminer
        # un champ requis unique, donc pas de garde d'existence.
        trame = {
            "sections": [
                {
                    "id": "s",
                    "questions": [
                        {"id": "a"},
                        {"id": "derivee", "show_if": {"$or": [{"a": {"$eq": 1}}, {"a": {"$eq": 2}}]}},
                    ],
                }
            ],
            "branches": [],
        }
        assert "derivee" not in _ids(questions_eligibles(trame, {}))

    def test_show_if_exists_seul_ne_requiert_pas_de_garde_supplementaire(self):
        trame = {
            "sections": [
                {
                    "id": "s",
                    "questions": [
                        {"id": "a"},
                        {"id": "derivee", "show_if": {"a": {"$exists": True}}},
                    ],
                }
            ],
            "branches": [],
        }
        assert "derivee" not in _ids(questions_eligibles(trame, {}))
        assert "derivee" in _ids(questions_eligibles(trame, {"a": 1}))


class TestNextQuestionEtTerminaison:
    def test_next_question_renvoie_premiere_eligible(self):
        q = next_question(TRAME_MOBILE, {})
        assert q["id"] == "nb_lignes"

    def test_next_question_avance_au_fil_des_reponses(self):
        reponses = {"nb_lignes": 1, "operateur_actuel": "Orange"}
        q = next_question(TRAME_MOBILE, reponses)
        assert q["id"] == "conso_data_go"

    def test_next_question_none_quand_tout_repondu(self):
        reponses = {
            "nb_lignes": 1,
            "operateur_actuel": "Orange",
            "conso_data_go": 3,
            "roaming_ue": "Jamais",
            "qualite_reseau": "Bonne",
        }
        assert next_question(TRAME_MOBILE, reponses) is None
        assert is_terminee(TRAME_MOBILE, reponses) is True

    def test_non_terminee_quand_branche_ajoute_une_question(self):
        reponses = {
            "nb_lignes": 2,
            "operateur_actuel": "Orange",
            "conso_data_go": 3,
            "roaming_ue": "Jamais",
            "qualite_reseau": "Bonne",
        }
        assert is_terminee(TRAME_MOBILE, reponses) is False
        assert next_question(TRAME_MOBILE, reponses)["id"] == "meme_operateur_famille"
