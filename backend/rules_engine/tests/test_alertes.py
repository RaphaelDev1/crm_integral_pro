# ==============================================================================
#  TESTS — alertes (règles type='alerte', templating {{...}}).
# ==============================================================================
from backend.rules_engine.alertes import generer_alertes

OFFRE = {"id": "xl", "caracteristiques": {"data_go": 200}}

REGLE_ANTI_SURVENTE = {
    "nom": "anti_survente_data_mobile",
    "type": "alerte",
    "condition": {
        "$and": [
            {"reponses.conso_data_go": {"$lt": 10}},
            {"offre.caracteristiques.data_go": {"$gt": 50}},
        ]
    },
    "action": {
        "kind": "warn",
        "severite": "critique",
        "message": "Forfait {{offre.caracteristiques.data_go}} Go proposé alors que le client consomme "
        "{{reponses.conso_data_go}} Go/mois.",
    },
}


class TestDeclenchement:
    def test_alerte_declenchee_quand_condition_vraie(self):
        alertes = generer_alertes(OFFRE, {"conso_data_go": 3}, [REGLE_ANTI_SURVENTE])
        assert len(alertes) == 1
        assert alertes[0]["regle"] == "anti_survente_data_mobile"
        assert alertes[0]["severite"] == "critique"

    def test_pas_d_alerte_quand_condition_fausse(self):
        alertes = generer_alertes(OFFRE, {"conso_data_go": 50}, [REGLE_ANTI_SURVENTE])
        assert alertes == []

    def test_regle_alerte_inactive_ignoree(self):
        regle = {**REGLE_ANTI_SURVENTE, "actif": False}
        assert generer_alertes(OFFRE, {"conso_data_go": 3}, [regle]) == []

    def test_regle_non_alerte_ignoree(self):
        regle = {**REGLE_ANTI_SURVENTE, "type": "scoring"}
        assert generer_alertes(OFFRE, {"conso_data_go": 3}, [regle]) == []

    def test_plusieurs_regles_produisent_plusieurs_alertes(self):
        regle2 = {
            "nom": "prix_eleve",
            "type": "alerte",
            "condition": {"offre.caracteristiques.data_go": {"$gt": 100}},
            "action": {"kind": "warn", "severite": "attention", "message": "Offre volumineuse."},
        }
        alertes = generer_alertes(OFFRE, {"conso_data_go": 3}, [REGLE_ANTI_SURVENTE, regle2])
        assert {a["regle"] for a in alertes} == {"anti_survente_data_mobile", "prix_eleve"}


class TestTemplating:
    def test_placeholders_remplaces_par_les_valeurs_du_contexte(self):
        alertes = generer_alertes(OFFRE, {"conso_data_go": 3}, [REGLE_ANTI_SURVENTE])
        assert alertes[0]["message"] == "Forfait 200 Go proposé alors que le client consomme 3 Go/mois."

    def test_placeholder_manquant_devient_chaine_vide(self):
        regle = {
            "nom": "x",
            "type": "alerte",
            "condition": {},
            "action": {"kind": "warn", "severite": "info", "message": "Valeur: {{offre.inexistant}}."},
        }
        alertes = generer_alertes(OFFRE, {}, [regle])
        assert alertes[0]["message"] == "Valeur: ."

    def test_severite_par_defaut_info(self):
        regle = {"nom": "x", "type": "alerte", "condition": {}, "action": {}}
        alertes = generer_alertes(OFFRE, {}, [regle])
        assert alertes[0]["severite"] == "info"


def test_sans_regles_aucune_alerte():
    assert generer_alertes(OFFRE, {}, []) == []
