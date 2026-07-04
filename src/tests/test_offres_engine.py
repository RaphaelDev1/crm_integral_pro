# ==============================================================================
#  TESTS — offres_engine.py (comparer_offres) : tri, exclusions, économies
# ==============================================================================
from offres_engine import ajouter_offre, comparer_offres


def _catalogue_mobile(tmp_db):
    ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
                   "nom_offre": "Free 350Go", "prix_mensuel": 19.99, "frais_activation": 10,
                   "engagement_mois": 0, "caracteristiques": "350Go",
                   "commission_affiliation": 30, "data_go": 350,
                   "url_souscription": "https://free.fr", "code_affiliation": "F1"})
    ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Orange",
                   "nom_offre": "Orange 150Go", "prix_mensuel": 24.99, "frais_activation": 0,
                   "engagement_mois": 0, "caracteristiques": "150Go",
                   "commission_affiliation": 35, "data_go": 150,
                   "url_souscription": "https://orange.fr", "code_affiliation": "O1"})
    ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "SFR",
                   "nom_offre": "SFR 130Go", "prix_mensuel": 12.99, "frais_activation": 0,
                   "engagement_mois": 0, "caracteristiques": "130Go",
                   "commission_affiliation": 22, "data_go": 130,
                   "url_souscription": "https://sfr.fr", "code_affiliation": "S1"})


class TestComparerOffresTri:
    def test_tri_par_economie_annuelle_decroissante(self, tmp_db):
        _catalogue_mobile(tmp_db)
        res = comparer_offres("Télécom", "Mobile", 40.0)
        fournisseurs = [r["fournisseur"] for r in res]
        assert fournisseurs == ["SFR", "Free", "Orange"]
        economies = [r["economie_annuelle"] for r in res]
        assert economies == sorted(economies, reverse=True)

    def test_calcul_economie(self, tmp_db):
        _catalogue_mobile(tmp_db)
        res = comparer_offres("Télécom", "Mobile", 40.0)
        sfr = next(r for r in res if r["fournisseur"] == "SFR")
        assert sfr["economie_mensuelle"] == round(40.0 - 12.99, 2)
        assert sfr["economie_annuelle"] == round((40.0 - 12.99) * 12, 2)

    def test_categorie_sans_offres_renvoie_liste_vide(self, tmp_db):
        _catalogue_mobile(tmp_db)
        assert comparer_offres("Énergie", "Gaz", 50.0) == []


class TestComparerOffresExclusions:
    def test_fournisseur_exclu(self, tmp_db):
        _catalogue_mobile(tmp_db)
        res = comparer_offres("Télécom", "Mobile", 40.0, fournisseur_exclu="Free")
        assert "Free" not in [r["fournisseur"] for r in res]
        assert len(res) == 2

    def test_fournisseurs_autorises(self, tmp_db):
        _catalogue_mobile(tmp_db)
        res = comparer_offres("Télécom", "Mobile", 40.0, fournisseurs_autorises=["Orange", "SFR"])
        assert set(r["fournisseur"] for r in res) == {"Orange", "SFR"}

    def test_data_go_min_exclut_les_forfaits_insuffisants(self, tmp_db):
        _catalogue_mobile(tmp_db)
        res = comparer_offres("Télécom", "Mobile", 40.0, data_go_min=200)
        assert [r["fournisseur"] for r in res] == ["Free"]
