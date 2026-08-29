# ==============================================================================
#  TESTS — question_selector (cœur "escargot" : sélection par score_info,
#  terminaison anticipée dès que le seuil n'est plus atteint).
# ==============================================================================
from backend.rules_engine.question_selector import prochaine_question, trame_terminee

TRAME = {
    "sections": [
        {
            "id": "s1",
            "questions": [
                {"id": "nb_lignes", "poids_ethique": 0, "cout_cognitif": 1},
                {"id": "conso_data_go", "poids_ethique": 10, "cout_cognitif": 3, "utilise_par_regles": ["r1", "r2"]},
                {"id": "qualite_reseau", "poids_ethique": 0, "cout_cognitif": 1},
            ],
        }
    ],
    "branches": [],
}


class TestSelectionParScoreMax:
    def test_choisit_la_question_de_score_info_maximal(self):
        # conso_data_go : 10 + 2 - 3 = 9 ; nb_lignes : 0 ; qualite_reseau : -1
        resultat = prochaine_question(TRAME, {})
        assert resultat.question["id"] == "conso_data_go"

    def test_question_choisie_disparait_une_fois_repondue(self):
        # une fois conso_data_go répondue, il ne reste que nb_lignes (-1) et
        # qualite_reseau (-1), toutes deux sous le seuil par défaut (0) : la
        # trame s'arrête plutôt que de poser des questions à faible valeur
        # d'information — exactement le principe "escargot".
        resultat = prochaine_question(TRAME, {"conso_data_go": 20})
        assert resultat.question is None

    def test_compteur_questions_restantes_estimees(self):
        # nb_lignes (0+0-1=-1) et qualite_reseau (0+0-1=-1) sont sous le seuil
        # par défaut ; seule conso_data_go (10+2-3=9) le dépasse.
        resultat = prochaine_question(TRAME, {})
        assert resultat.questions_restantes_estimees == 1


class TestTerminaisonAnticipee:
    def test_trame_terminee_quand_scores_restants_sous_le_seuil(self):
        reponses = {"nb_lignes": 2, "conso_data_go": 20}
        # il ne reste que qualite_reseau, score -1 < seuil 0 → terminée
        assert trame_terminee(TRAME, reponses) is True
        assert prochaine_question(TRAME, reponses).question is None

    def test_trame_non_terminee_tant_qu_une_question_est_au_dessus_du_seuil(self):
        assert trame_terminee(TRAME, {}) is False

    def test_seuil_personnalise_termine_plus_tot(self):
        # avec un seuil de 5, seule conso_data_go (9) dépasse initialement
        resultat = prochaine_question(TRAME, {}, seuil=5)
        assert resultat.question["id"] == "conso_data_go"
        assert resultat.questions_restantes_estimees == 1

        # une fois conso_data_go répondue, plus aucune question n'atteint le seuil 5
        assert trame_terminee(TRAME, {"conso_data_go": 20}, seuil=5) is True

    def test_toutes_questions_repondues_termine_la_trame(self):
        reponses = {"nb_lignes": 1, "conso_data_go": 5, "qualite_reseau": "Bonne"}
        assert trame_terminee(TRAME, reponses) is True


class TestIntegrationAvecBranchesEtOffres:
    def test_offres_et_regles_influencent_la_selection(self):
        trame = {
            "sections": [
                {
                    "id": "s1",
                    "questions": [
                        {"id": "a", "cout_cognitif": 1, "poids_ethique": 0},
                        {
                            "id": "b",
                            "cout_cognitif": 1,
                            "poids_ethique": 0,
                            "elimine_offres_si": {"x": {"offre.data_go": {"$gt": 10}}},
                        },
                    ],
                }
            ],
            "branches": [],
        }
        offres = [{"data_go": 20}, {"data_go": 30}]
        resultat = prochaine_question(trame, {}, offres=offres)
        assert resultat.question["id"] == "b"  # score 2 - 1 = 1 > score de "a" (0 - 1 = -1)
