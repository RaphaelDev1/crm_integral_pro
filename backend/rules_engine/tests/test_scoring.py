# ==============================================================================
#  TESTS — scoring (filtre puis scoring, bornes 0-100, tri par score).
# ==============================================================================
from backend.rules_engine.scoring import score_offres

OFFRES = [
    {"id": "eco", "caracteristiques": {"data_go": 20, "prix": 10}},
    {"id": "xl", "caracteristiques": {"data_go": 200, "prix": 40}},
    {"id": "resiliable", "caracteristiques": {"data_go": 50, "prix": 15, "engagement_mois": 24}},
]


class TestFiltre:
    def test_regle_exclude_retire_l_offre(self):
        regles = [
            {
                "nom": "exclure_engagement",
                "type": "filtre",
                "condition": {"offre.caracteristiques.engagement_mois": {"$exists": True}},
                "action": {"kind": "exclude"},
            }
        ]
        resultats = score_offres(OFFRES, {}, regles)
        ids = [r["offre"]["id"] for r in resultats]
        assert "resiliable" not in ids
        assert len(ids) == 2

    def test_regle_filtre_inactive_est_ignoree(self):
        regles = [
            {
                "nom": "x",
                "type": "filtre",
                "actif": False,
                "condition": {"offre.caracteristiques.engagement_mois": {"$exists": True}},
                "action": {"kind": "exclude"},
            }
        ]
        resultats = score_offres(OFFRES, {}, regles)
        assert len(resultats) == 3


class TestScoringAjustementConstant:
    def test_boost_petit_rouleur_favorise_les_petits_forfaits(self):
        regles = [
            {
                "nom": "anti_survente",
                "type": "scoring",
                "condition": {
                    "$and": [
                        {"reponses.conso_data_go": {"$lt": 10}},
                        {"offre.caracteristiques.data_go": {"$gt": 50}},
                    ]
                },
                "action": {"kind": "score_adjust", "valeur": -50},
            }
        ]
        resultats = score_offres(OFFRES, {"conso_data_go": 3}, regles)
        par_id = {r["offre"]["id"]: r for r in resultats}
        assert par_id["xl"]["score"] < par_id["eco"]["score"]

    def test_score_borne_a_100(self):
        regles = [
            {"nom": "boost", "type": "scoring", "condition": {}, "action": {"kind": "score_adjust", "valeur": 1000}}
        ]
        resultats = score_offres(OFFRES, {}, regles)
        assert all(r["score"] == 100.0 for r in resultats)

    def test_score_borne_a_0(self):
        regles = [
            {"nom": "malus", "type": "scoring", "condition": {}, "action": {"kind": "score_adjust", "valeur": -1000}}
        ]
        resultats = score_offres(OFFRES, {}, regles)
        assert all(r["score"] == 0.0 for r in resultats)


class TestScoringBareme:
    def test_bareme_premiere_tranche_qui_matche_gagne(self):
        # équivalent du IF(data_go<=40,+30, IF(data_go<=100,0,-50)) du plan
        regles = [
            {
                "nom": "boost_petit_rouleur",
                "type": "scoring",
                "condition": {"reponses.conso_data_go": {"$lt": 5}},
                "action": {
                    "kind": "score_adjust",
                    "bareme": [
                        {"si": {"offre.caracteristiques.data_go": {"$lte": 40}}, "valeur": 30},
                        {"si": {"offre.caracteristiques.data_go": {"$lte": 100}}, "valeur": 0},
                    ],
                    "defaut": -50,
                },
            }
        ]
        resultats = score_offres(OFFRES, {"conso_data_go": 2}, regles)
        par_id = {r["offre"]["id"]: r for r in resultats}
        assert par_id["eco"]["score"] == 80.0  # data_go=20 <= 40 → +30
        assert par_id["resiliable"]["score"] == 50.0  # data_go=50 <= 100 → +0
        assert par_id["xl"]["score"] == 0.0  # data_go=200 → defaut -50


class TestTriEtRangEtJustifications:
    def test_resultats_tries_par_score_decroissant_avec_rang(self):
        regles = [
            {
                "nom": "boost_eco",
                "type": "scoring",
                "condition": {"offre.caracteristiques.prix": {"$lt": 15}},
                "action": {"kind": "score_adjust", "valeur": 20},
            }
        ]
        resultats = score_offres(OFFRES, {}, regles)
        assert [r["rang"] for r in resultats] == [1, 2, 3]
        assert resultats[0]["score"] >= resultats[1]["score"] >= resultats[2]["score"]
        assert resultats[0]["offre"]["id"] == "eco"

    def test_justifications_listent_les_regles_scoring_declenchees(self):
        regles = [
            {
                "nom": "regle_a",
                "type": "scoring",
                "condition": {"offre.caracteristiques.prix": {"$lt": 15}},
                "action": {"kind": "score_adjust", "valeur": 5},
            }
        ]
        resultats = score_offres(OFFRES, {}, regles)
        eco = next(r for r in resultats if r["offre"]["id"] == "eco")
        autre = next(r for r in resultats if r["offre"]["id"] == "xl")
        assert eco["justifications"] == ["regle_a"]
        assert autre["justifications"] == []


def test_sans_regles_toutes_les_offres_gardent_le_score_de_base():
    resultats = score_offres(OFFRES, {}, [])
    assert all(r["score"] == 50.0 for r in resultats)


def test_regle_scoring_avec_kind_non_reconnu_est_ignoree():
    regles = [{"nom": "x", "type": "scoring", "condition": {}, "action": {"kind": "autre_chose", "valeur": 30}}]
    resultats = score_offres(OFFRES, {}, regles)
    assert all(r["score"] == 50.0 for r in resultats)
