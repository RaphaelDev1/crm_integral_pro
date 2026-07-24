# ==============================================================================
#  TESTS — prospects_engine.py (calculer_score_prospect, indicateur_score,
#  recalculer_scores_prospects) : scoring de priorisation des relances
# ==============================================================================
from datetime import datetime, timedelta

from db import get_conn
from contrats_engine import ajouter_contrat, lire_contrats_prospect
from prospects_engine import (
    ajouter_prospect, lire_prospects, calculer_score_prospect,
    indicateur_score, recalculer_scores_prospects, SATISFACTION_BASSE,
    creer_token_documents, valider_token_documents,
    cout_reference_categorie, date_relance_avant_engagement, RELANCE_JOURS_AVANT_ENGAGEMENT,
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


class TestTokenDocuments:
    """Lien « envoyer facture + test de débit » — cf. app.py (bouton fiche
    prospect) et chatbot_api.py (portail public /portail/{token})."""

    def test_token_valide_renvoie_le_bon_prospect(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        tok = creer_token_documents(pid)
        prospect = valider_token_documents(tok["token"])
        assert prospect is not None
        assert prospect["id"] == pid

    def test_token_inconnu_renvoie_none(self, tmp_db):
        assert valider_token_documents("token-qui-nexiste-pas") is None

    def test_token_expire_renvoie_none(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        tok = creer_token_documents(pid, duree_jours=-1)   # déjà expiré
        assert valider_token_documents(tok["token"]) is None

    def test_token_revoque_renvoie_none(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        tok = creer_token_documents(pid)
        conn = get_conn()
        conn.execute("UPDATE tokens_prospects SET revoque=1 WHERE token=?", (tok["token"],))
        conn.commit()
        conn.close()
        assert valider_token_documents(tok["token"]) is None

    def test_utilisation_incremente_le_compteur(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        tok = creer_token_documents(pid)
        valider_token_documents(tok["token"])
        valider_token_documents(tok["token"])
        conn = get_conn()
        row = conn.execute("SELECT nb_utilisations FROM tokens_prospects WHERE token=?",
                            (tok["token"],)).fetchone()
        conn.close()
        assert row["nb_utilisations"] == 2


class TestCoutReferenceCategorie:
    """Base de comparaison utilisée pour calculer l'économie d'une offre « intéresse le
    client » — ne doit jamais mélanger le coût d'un service avec celui d'un autre (ex. offre
    Box comparée au coût du mobile)."""

    def test_categorie_correspond_au_service_principal_utilise_le_cout_du_profil(self):
        offre = {"univers": "Télécom", "categorie": "Mobile"}
        prospect = {"service_principal": "Mobile uniquement", "cout_mensuel_actuel": 25.0}
        assert cout_reference_categorie(offre, prospect) == 25.0

    def test_offre_cross_sell_sans_contrat_connu_renvoie_none(self):
        # Prospect Mobile uniquement, mais l'offre proposée est une Box — cout_mensuel_actuel
        # (le coût du mobile) n'a rien à voir avec un service Box, aucune base connue.
        offre = {"univers": "Télécom", "categorie": "Box / Fibre"}
        prospect = {"service_principal": "Mobile uniquement", "cout_mensuel_actuel": 25.0}
        assert cout_reference_categorie(offre, prospect, contrats_prospect=[]) is None

    def test_offre_cross_sell_avec_contrat_connu_utilise_le_cout_du_contrat(self):
        offre = {"univers": "Télécom", "categorie": "Box / Fibre"}
        prospect = {"service_principal": "Mobile uniquement", "cout_mensuel_actuel": 25.0}
        contrats = [{"categorie": "Box / Fibre", "cout_mensuel": 39.9}]
        assert cout_reference_categorie(offre, prospect, contrats_prospect=contrats) == 39.9

    def test_avec_contrats_en_dataframe_pandas(self, tmp_db):
        import pandas as pd
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont",
                                 "service_principal": "Mobile uniquement"})
        ajouter_contrat({"prospect_id": pid, "univers": "Télécom", "categorie": "Box / Fibre",
                          "fournisseur": "Orange", "nom_offre": "Livebox", "cout_mensuel": 35.0})
        contrats = lire_contrats_prospect(pid)
        assert isinstance(contrats, pd.DataFrame)
        offre = {"univers": "Télécom", "categorie": "Box / Fibre"}
        prospect = {"service_principal": "Mobile uniquement", "cout_mensuel_actuel": 25.0}
        assert cout_reference_categorie(offre, prospect, contrats_prospect=contrats) == 35.0

    def test_energie_utilise_le_cout_elec_ou_gaz_selon_la_categorie(self):
        prospect = {"cout_elec": 60.0, "cout_gaz": 40.0}
        assert cout_reference_categorie({"univers": "Énergie", "categorie": "Électricité"}, prospect) == 60.0
        assert cout_reference_categorie({"univers": "Énergie", "categorie": "Gaz"}, prospect) == 40.0

    def test_abonnement_correspondant_trouve_son_cout(self):
        prospect = {"abonnements": '[{"nom": "Netflix", "cout": 15.5}]'}
        offre = {"univers": "Abonnements", "categorie": "Netflix"}
        assert cout_reference_categorie(offre, prospect) == 15.5

    def test_abonnement_sans_correspondance_renvoie_none(self):
        prospect = {"abonnements": '[{"nom": "Netflix", "cout": 15.5}]'}
        offre = {"univers": "Abonnements", "categorie": "Spotify"}
        assert cout_reference_categorie(offre, prospect) is None


class TestDateRelanceAvantEngagement:
    def test_relance_programmee_14_jours_avant_la_fin(self):
        aujourdhui = datetime(2026, 1, 1).date()
        fin = datetime(2026, 3, 1).date()
        assert date_relance_avant_engagement(fin, aujourdhui=aujourdhui) == fin - timedelta(days=14)

    def test_echeance_trop_proche_programme_la_relance_aujourdhui(self):
        aujourdhui = datetime(2026, 1, 1).date()
        fin = datetime(2026, 1, 5).date()   # J-14 tomberait dans le passé
        assert date_relance_avant_engagement(fin, aujourdhui=aujourdhui) == aujourdhui

    def test_marge_personnalisee(self):
        aujourdhui = datetime(2026, 1, 1).date()
        fin = datetime(2026, 2, 1).date()
        assert date_relance_avant_engagement(fin, jours_avant=30, aujourdhui=aujourdhui) == fin - timedelta(days=30)


class TestAjouterContratProspect:
    def test_contrat_rattache_a_un_prospect_existant(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        ajouter_contrat({"prospect_id": pid, "univers": "Télécom", "categorie": "Box / Fibre",
                          "fournisseur": "SFR", "nom_offre": "Box SFR", "cout_mensuel": 30.0,
                          "date_fin_engagement": "01/06/2026"})
        contrats = lire_contrats_prospect(pid)
        assert len(contrats) == 1
        assert contrats.iloc[0]["fournisseur"] == "SFR"
        assert contrats.iloc[0]["client_id"] is None

    def test_contrat_rattache_a_un_prospect_inexistant_leve_valueerror(self, tmp_db):
        import pytest
        with pytest.raises(ValueError):
            ajouter_contrat({"prospect_id": 999999, "univers": "Télécom", "categorie": "Mobile",
                              "fournisseur": "Orange", "nom_offre": "Forfait", "cout_mensuel": 10.0})
