# ==============================================================================
#  TESTS — information_scorer (formule score_info, §Principe #1).
# ==============================================================================
from backend.rules_engine.information_scorer import score_info

OFFRES = [
    {"id": "1", "caracteristiques": {"data_go": 20}},
    {"id": "2", "caracteristiques": {"data_go": 60}},
    {"id": "3", "caracteristiques": {"data_go": 150}},
    {"id": "4", "caracteristiques": {"data_go": 200}},
]


class TestDejaRepondueOuIncompatible:
    def test_question_deja_repondue_score_zero(self):
        question = {"id": "conso_data_go", "cout_cognitif": 1, "poids_ethique": 10}
        assert score_info(question, {"conso_data_go": 5}) == 0.0

    def test_question_deja_repondue_avec_valeur_falsy_reste_zero(self):
        # 0 est une réponse valide (pas "manquante") : la question ne doit
        # pas se représenter juste parce que la valeur est falsy.
        question = {"id": "nb_lignes"}
        assert score_info(question, {"nb_lignes": 0}) == 0.0

    def test_question_incompatible_avec_show_if_score_zero(self):
        question = {
            "id": "roaming_hors_ue",
            "show_if": {"roaming_ue": {"$ne": "Jamais"}},
            "poids_ethique": 5,
        }
        assert score_info(question, {"roaming_ue": "Jamais"}) == 0.0

    def test_question_non_repondue_et_compatible_score_non_nul(self):
        question = {"id": "roaming_hors_ue", "show_if": {"roaming_ue": {"$ne": "Jamais"}}, "poids_ethique": 5}
        assert score_info(question, {"roaming_ue": "Souvent"}) != 0.0


class TestFormule:
    def test_formule_sans_offres_ni_regles(self):
        question = {"id": "x", "poids_ethique": 10, "cout_cognitif": 3}
        assert score_info(question, {}) == 10 - 3

    def test_regles_utilisatrices_augmentent_le_score(self):
        question = {"id": "x", "utilise_par_regles": ["r1", "r2", "r3"], "cout_cognitif": 1}
        assert score_info(question, {}) == 3 - 1

    def test_cout_cognitif_par_defaut_est_un(self):
        question = {"id": "x", "poids_ethique": 5}
        assert score_info(question, {}) == 5 - 1

    def test_elimination_offres_moyenne_scenarios(self):
        question = {
            "id": "conso_data_go",
            "cout_cognitif": 3,
            "poids_ethique": 10,
            "elimine_offres_si": {
                "reponse_lt_5": {"offre.caracteristiques.data_go": {"$gt": 40}},  # élimine 3 offres (60,150,200)
                "reponse_lt_30": {"offre.caracteristiques.data_go": {"$gt": 100}},  # élimine 2 offres (150,200)
            },
        }
        score = score_info(question, {}, offres=OFFRES)
        # moyenne(3, 2) + 0 règle + 10 poids - 3 coût = 2.5 + 10 - 3
        assert score == 2.5 + 10 - 3

    def test_elimination_scenario_texte_libre_ignore_sans_erreur(self):
        question = {
            "id": "x",
            "elimine_offres_si": {"reponse_lt_5": "offres.data_go > 40"},  # forme texte du plan, non supportée
        }
        assert score_info(question, {}, offres=OFFRES) == -1.0  # 0 élimination - 1 coût cognitif par défaut

    def test_sans_offres_catalogue_elimination_est_nulle(self):
        question = {
            "id": "x",
            "elimine_offres_si": {"reponse_lt_5": {"offre.caracteristiques.data_go": {"$gt": 40}}},
        }
        assert score_info(question, {}, offres=[]) == -1.0


def test_score_haut_pour_question_anti_survente_type_conso_data():
    # Reproduit l'esprit de l'exemple §0.1.bis : question anti-survente à
    # coût cognitif élevé mais poids éthique fort + très discriminante.
    question = {
        "id": "conso_data_go",
        "cout_cognitif": 3,
        "poids_ethique": 10,
        "utilise_par_regles": ["anti_survente_data_mobile", "boost_petit_rouleur"],
        "elimine_offres_si": {"reponse_lt_5": {"offre.caracteristiques.data_go": {"$gt": 40}}},
    }
    autre = {"id": "qualite_reseau", "cout_cognitif": 1, "poids_ethique": 0}
    assert score_info(question, {}, offres=OFFRES) > score_info(autre, {}, offres=OFFRES)
