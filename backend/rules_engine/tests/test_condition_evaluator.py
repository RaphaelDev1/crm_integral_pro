# ==============================================================================
#  TESTS — condition_evaluator (DSL §0.3). Un opérateur par cas, chaînage
#  profond, chemin pointé, valeurs null/manquantes.
# ==============================================================================
import pytest

from backend.rules_engine.condition_evaluator import evaluate, get_path


class TestGetPath:
    def test_chemin_simple(self):
        assert get_path({"a": 1}, "a") == 1

    def test_chemin_pointe_profond(self):
        assert get_path({"reponses": {"conso_data_go": 3}}, "reponses.conso_data_go") == 3

    def test_chemin_manquant_renvoie_sentinel_distinct_de_none(self):
        from backend.rules_engine.condition_evaluator import _MISSING

        assert get_path({"a": {}}, "a.b") is _MISSING
        assert get_path({"a": {"b": None}}, "a.b") is None
        assert get_path({"a": {}}, "a.b") is not get_path({"a": {"b": None}}, "a.b")

    def test_chemin_traverse_un_non_dict(self):
        from backend.rules_engine.condition_evaluator import _MISSING

        assert get_path({"a": 3}, "a.b") is _MISSING


class TestConditionVide:
    def test_condition_none_toujours_vraie(self):
        assert evaluate(None, {}) is True

    def test_condition_dict_vide_toujours_vraie(self):
        assert evaluate({}, {}) is True


class TestRaccourciEq:
    def test_valeur_litterale_equivaut_a_eq(self):
        assert evaluate({"statut": "actif"}, {"statut": "actif"}) is True
        assert evaluate({"statut": "actif"}, {"statut": "inactif"}) is False


@pytest.mark.parametrize(
    "operateur,attendu,valeur_contexte,resultat",
    [
        ("$eq", 5, 5, True),
        ("$eq", 5, 6, False),
        ("$ne", 5, 6, True),
        ("$ne", 5, 5, False),
        ("$gt", 5, 6, True),
        ("$gt", 5, 5, False),
        ("$gte", 5, 5, True),
        ("$gte", 5, 4, False),
        ("$lt", 5, 4, True),
        ("$lt", 5, 5, False),
        ("$lte", 5, 5, True),
        ("$lte", 5, 6, False),
        ("$in", [1, 2, 3], 2, True),
        ("$in", [1, 2, 3], 9, False),
        ("$nin", [1, 2, 3], 9, True),
        ("$nin", [1, 2, 3], 2, False),
    ],
)
def test_chaque_operateur_de_comparaison(operateur, attendu, valeur_contexte, resultat):
    assert evaluate({"x": {operateur: attendu}}, {"x": valeur_contexte}) is resultat


class TestExists:
    def test_exists_true_quand_present_meme_si_null(self):
        assert evaluate({"x": {"$exists": True}}, {"x": None}) is True

    def test_exists_true_quand_present_avec_valeur(self):
        assert evaluate({"x": {"$exists": True}}, {"x": 3}) is True

    def test_exists_false_quand_absent(self):
        assert evaluate({"x": {"$exists": False}}, {}) is True
        assert evaluate({"x": {"$exists": True}}, {}) is False


class TestValeursNullEtManquantes:
    def test_ordre_sur_valeur_manquante_est_faux(self):
        assert evaluate({"x": {"$gt": 5}}, {}) is False
        assert evaluate({"x": {"$lte": 5}}, {}) is False

    def test_ordre_sur_valeur_null_explicite_est_faux(self):
        assert evaluate({"x": {"$gt": 5}}, {"x": None}) is False

    def test_eq_null_explicite_vs_manquant(self):
        assert evaluate({"x": {"$eq": None}}, {"x": None}) is True
        assert evaluate({"x": {"$eq": None}}, {}) is True  # manquant traité comme None

    def test_ne_sur_manquant(self):
        assert evaluate({"x": {"$ne": "a"}}, {}) is True

    def test_types_incompatibles_ne_leve_pas(self):
        assert evaluate({"x": {"$gt": 5}}, {"x": "abc"}) is False


class TestOperateursLogiques:
    def test_and_toutes_vraies(self):
        cond = {"$and": [{"a": 1}, {"b": 2}]}
        assert evaluate(cond, {"a": 1, "b": 2}) is True
        assert evaluate(cond, {"a": 1, "b": 3}) is False

    def test_or_au_moins_une_vraie(self):
        cond = {"$or": [{"a": 1}, {"b": 2}]}
        assert evaluate(cond, {"a": 9, "b": 2}) is True
        assert evaluate(cond, {"a": 9, "b": 9}) is False

    def test_not_inverse(self):
        cond = {"$not": {"a": 1}}
        assert evaluate(cond, {"a": 1}) is False
        assert evaluate(cond, {"a": 2}) is True

    def test_chainage_profond_and_dans_or_dans_and(self):
        cond = {
            "$and": [
                {"a": {"$gte": 1}},
                {
                    "$or": [
                        {"b": {"$lt": 10}},
                        {"$and": [{"c": {"$exists": True}}, {"c": {"$in": [1, 2]}}]},
                    ]
                },
            ]
        }
        assert evaluate(cond, {"a": 1, "b": 5}) is True
        assert evaluate(cond, {"a": 1, "b": 50, "c": 2}) is True
        assert evaluate(cond, {"a": 1, "b": 50, "c": 99}) is False
        assert evaluate(cond, {"a": 0, "b": 5}) is False

    def test_plusieurs_operateurs_sur_meme_champ_est_un_et_implicite(self):
        cond = {"x": {"$gte": 10, "$lte": 20}}
        assert evaluate(cond, {"x": 15}) is True
        assert evaluate(cond, {"x": 5}) is False
        assert evaluate(cond, {"x": 25}) is False

    def test_plusieurs_cles_top_level_est_un_et_implicite(self):
        cond = {"a": 1, "b": 2}
        assert evaluate(cond, {"a": 1, "b": 2}) is True
        assert evaluate(cond, {"a": 1, "b": 3}) is False


class TestOperateurInconnu:
    def test_operateur_inconnu_leve_value_error(self):
        with pytest.raises(ValueError):
            evaluate({"x": {"$foo": 1}}, {"x": 1})


class TestCheminsPointesDansCondition:
    def test_condition_sur_chemin_pointe(self):
        cond = {"reponses.conso_data_go": {"$lt": 10}}
        assert evaluate(cond, {"reponses": {"conso_data_go": 3}}) is True
        assert evaluate(cond, {"reponses": {"conso_data_go": 50}}) is False

    def test_condition_regle_recommandation_exemple_plan(self):
        # Reproduit l'exemple §0.3 (anti_survente_data_mobile).
        cond = {
            "$and": [
                {"reponses.conso_data_go": {"$lt": 10}},
                {"offre.caracteristiques.data_go": {"$gt": 50}},
            ]
        }
        contexte = {"reponses": {"conso_data_go": 3}, "offre": {"caracteristiques": {"data_go": 100}}}
        assert evaluate(cond, contexte) is True
        contexte["offre"]["caracteristiques"]["data_go"] = 40
        assert evaluate(cond, contexte) is False
