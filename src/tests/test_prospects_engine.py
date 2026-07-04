# ==============================================================================
#  TESTS — prospects_engine.py (calculer_score_prospect, indicateur_score,
#  recalculer_scores_prospects) : scoring de priorisation des relances
# ==============================================================================
from datetime import datetime, timedelta

from prospects_engine import (
    ajouter_prospect, lire_prospects, calculer_score_prospect,
    indicateur_score, recalculer_scores_prospects, SATISFACTION_BASSE,
)


def _prospect(**overrides):
    base = {
        "economie_estimee_an": 100.0,
        "date_creation": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "satisfaction_reseau": "😀 Très content",
        "veut_rester": "Non",
        "type_client": "Particulier",
    }
    base.update(overrides)
    return base


class TestCalculerScoreProspect:
    def test_score_de_base_sur_economie_seule(self):
        score = calculer_score_prospect(_prospect(economie_estimee_an=100.0))
        assert score == 200.0   # 100 * 2, aucun jour écoulé, aucun bonus/malus

    def test_satisfaction_basse_ajoute_20(self):
        avec = calculer_score_prospect(_prospect(satisfaction_reseau=SATISFACTION_BASSE))
        sans = calculer_score_prospect(_prospect())
        assert avec - sans == 20

    def test_veut_rester_retire_15(self):
        avec = calculer_score_prospect(_prospect(veut_rester="Oui"))
        sans = calculer_score_prospect(_prospect())
        assert sans - avec == 15

    def test_type_professionnel_ajoute_10(self):
        avec = calculer_score_prospect(_prospect(type_client="Professionnel"))
        sans = calculer_score_prospect(_prospect())
        assert avec - sans == 10

    def test_jours_depuis_dernier_contact_pondere_par_3(self):
        ancien = datetime.now() - timedelta(days=10)
        score = calculer_score_prospect(_prospect(economie_estimee_an=0.0), dernier_contact=ancien)
        assert score == 30.0   # 10 jours * 3, aucun autre facteur

    def test_dernier_contact_futur_ne_produit_pas_de_score_negatif(self):
        futur = datetime.now() + timedelta(days=5)
        score = calculer_score_prospect(_prospect(economie_estimee_an=0.0), dernier_contact=futur)
        assert score == 0.0

    def test_date_creation_invalide_ne_plante_pas(self):
        score = calculer_score_prospect(_prospect(economie_estimee_an=50.0, date_creation=None))
        assert score == 100.0


class TestIndicateurScore:
    def test_score_eleve_est_chaud(self):
        assert indicateur_score(200) == "🔴 chaud"

    def test_score_moyen_est_tiede(self):
        assert indicateur_score(80) == "🟡 tiède"

    def test_score_faible_est_froid(self):
        assert indicateur_score(10) == "🟢 froid"


class TestRecalculerScoresProspects:
    def test_persiste_le_score_en_base(self, tmp_db):
        ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont",
                           "economie_estimee_an": 100.0, "type_client": "Professionnel"})
        recalculer_scores_prospects()
        df = lire_prospects()
        assert df.loc[0, "score"] == calculer_score_prospect(df.iloc[0])

    def test_tri_par_score_decroissant(self, tmp_db):
        ajouter_prospect({"ref": "P_FROID", "prenom": "A", "nom": "A", "economie_estimee_an": 10.0})
        ajouter_prospect({"ref": "P_CHAUD", "prenom": "B", "nom": "B", "economie_estimee_an": 500.0})
        recalculer_scores_prospects()
        df = lire_prospects().sort_values("score", ascending=False)
        assert df.iloc[0]["ref"] == "P_CHAUD"
