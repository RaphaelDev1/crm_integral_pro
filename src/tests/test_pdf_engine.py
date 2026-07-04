# ==============================================================================
#  TESTS — pdf_engine.py (analyser_facture) sur 5 factures types
#  (Orange, Free, SFR/RED, Bouygues/B&You, EDF)
# ==============================================================================
from pdf_engine import analyser_facture

FACTURE_ORANGE = """Orange SA
Service Client Orange
TSA 12345 75800 PARIS CEDEX 08

Facture du 05/06/2026
M. Jean Dupont
12 RUE DE LA PAIX
75001 PARIS

Votre forfait 5G 150 Go
Montant TTC a payer : 45,99 EUR
Data mobile : 150 Go
Tel : 0601020304
Email : jean.dupont@example.fr
"""

FACTURE_FREE = """Free Mobile
Proxymity SAS
BP 90001 75311 PARIS CEDEX 09

Facture Free Mobile
MME Amelie Durand
8 AVENUE DES CHAMPS
69002 LYON

Forfait Free 5G 350 Go
Montant du prelevement : 19,99 EUR
Data : 350 Go
Tel : 0605060708
Email : amelie.durand@example.fr
"""

FACTURE_SFR = """SFR - RED by SFR
Societe Francaise du Radiotelephone
TSA 71875 75800 PARIS CEDEX 08

Facture RED SFR
MR MARC PETIT
5 RUE DU COMMERCE
33000 BORDEAUX

Forfait RED 130 Go
Total facture TTC : 12,99 EUR
Data mobile 130 Go
Tel : 0607080910
marc.petit@example.fr
"""

FACTURE_BOUYGUES = """Bouygues Telecom
B&You
CS 91234 75015 PARIS CEDEX 15

Facture B&You
MME SOPHIE MARTIN
3 BOULEVARD VOLTAIRE
44000 NANTES

Forfait B&You 200 Go
Montant a payer ce mois : 13,99 EUR
Data 200 Go
Tel : 0611223344
sophie.martin@example.fr
"""

FACTURE_EDF = """EDF
Electricite de France
TSA 60001 75757 PARIS CEDEX 15

Facture d electricite
MONSIEUR PIERRE DURAND
20 RUE DE LA REPUBLIQUE
13001 MARSEILLE

Abonnement + consommation
Montant TTC : 89,00 EUR
Tel : 0622334455
pierre.durand@example.fr
"""


class TestAnalyserFactureOrange:
    def setup_method(self):
        self.res = analyser_facture(FACTURE_ORANGE)

    def test_operateur(self):
        assert self.res["operateur"] == "Orange"

    def test_fournisseur_non_concerne(self):
        assert self.res["fournisseur"] == "Autre / Aucun"

    def test_prix(self):
        assert self.res["prix"] == 45.99

    def test_adresse(self):
        assert self.res["cp"] == "75001"
        assert self.res["ville"] == "PARIS"

    def test_coordonnees(self):
        assert self.res["tel"] == "0601020304"
        assert self.res["email"] == "jean.dupont@example.fr"

    def test_data_go(self):
        assert self.res["data_go"] == "150"

    def test_identite_avec_civilite_a_point(self):
        # "M. Prénom Nom" — format le plus courant sur les factures FR.
        assert self.res["prenom"] == "Jean"
        assert self.res["nom"] == "DUPONT"


class TestAnalyserFactureFree:
    def setup_method(self):
        self.res = analyser_facture(FACTURE_FREE)

    def test_operateur(self):
        assert self.res["operateur"] == "Free"

    def test_prix(self):
        assert self.res["prix"] == 19.99

    def test_adresse(self):
        assert self.res["cp"] == "69002"
        assert self.res["ville"] == "LYON"

    def test_identite(self):
        assert self.res["prenom"] == "Amelie"
        assert self.res["nom"] == "DURAND"

    def test_data_go(self):
        assert self.res["data_go"] == "350"


class TestAnalyserFactureSFR:
    def setup_method(self):
        self.res = analyser_facture(FACTURE_SFR)

    def test_operateur(self):
        assert self.res["operateur"] == "SFR"

    def test_prix(self):
        assert self.res["prix"] == 12.99

    def test_adresse(self):
        assert self.res["cp"] == "33000"
        assert self.res["ville"] == "BORDEAUX"

    def test_identite(self):
        assert self.res["prenom"] == "Marc"
        assert self.res["nom"] == "PETIT"

    def test_data_go(self):
        assert self.res["data_go"] == "130"


class TestAnalyserFactureBouygues:
    def setup_method(self):
        self.res = analyser_facture(FACTURE_BOUYGUES)

    def test_operateur(self):
        assert self.res["operateur"] == "Bouygues"

    def test_prix(self):
        assert self.res["prix"] == 13.99

    def test_adresse(self):
        assert self.res["cp"] == "44000"
        assert self.res["ville"] == "NANTES"

    def test_identite(self):
        assert self.res["prenom"] == "Sophie"
        assert self.res["nom"] == "MARTIN"


class TestAnalyserFactureEDF:
    def setup_method(self):
        self.res = analyser_facture(FACTURE_EDF)

    def test_fournisseur(self):
        assert self.res["fournisseur"] == "EDF"

    def test_operateur_non_concerne(self):
        assert self.res["operateur"] == "Autre / Aucun"

    def test_prix(self):
        assert self.res["prix"] == 89.0

    def test_adresse(self):
        assert self.res["cp"] == "13001"
        assert self.res["ville"] == "MARSEILLE"

    def test_identite(self):
        assert self.res["prenom"] == "Pierre"
        assert self.res["nom"] == "DURAND"

    def test_pas_de_data_go_sur_facture_energie(self):
        assert self.res["data_go"] == ""


class TestAnalyserFactureCasLimites:
    def test_texte_vide(self):
        res = analyser_facture("")
        assert res["operateur"] == "Autre / Aucun"
        assert res["fournisseur"] == "Autre / Aucun"
        assert res["prix"] == 0.0

    def test_texte_none(self):
        res = analyser_facture(None)
        assert res["prix"] == 0.0

    def test_mrs_ne_declenche_pas_de_faux_positif_sur_mr(self):
        # "MRS" ne doit pas être reconnu comme la civilité "MR" suivie du reste du mot
        # (l'espace obligatoire après la civilité empêche ce faux positif).
        res = analyser_facture("MRS DUPONT MARIE\n")
        assert res["prenom"] == ""
        assert res["nom"] == ""
