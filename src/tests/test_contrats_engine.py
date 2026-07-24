# ==============================================================================
#  TESTS — contrats_engine.py : type_contrat (dossier en cours vs référence externe) et
#  transferer_contrats_dossier_vers_client (finalisation de la conversion prospect → client)
# ==============================================================================
from clients_engine import ajouter_client
from contrats_engine import (
    ajouter_contrat, lire_contrats_client, lire_contrats_prospect,
    transferer_contrats_dossier_vers_client,
)
from prospects_engine import ajouter_prospect


class TestTypeContrat:
    def test_type_contrat_dossier_cmr_est_persiste(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        ajouter_contrat({"prospect_id": pid, "univers": "Télécom", "categorie": "Mobile",
                          "fournisseur": "Orange", "nom_offre": "Forfait 50Go", "cout_mensuel": 15.0,
                          "type_contrat": "dossier_cmr"})
        contrats = lire_contrats_prospect(pid)
        assert contrats.iloc[0]["type_contrat"] == "dossier_cmr"

    def test_contrat_sans_type_contrat_reste_none(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        ajouter_contrat({"prospect_id": pid, "univers": "Télécom", "categorie": "Box / Fibre",
                          "fournisseur": "SFR", "nom_offre": "Box SFR", "cout_mensuel": 30.0})
        contrats = lire_contrats_prospect(pid)
        assert contrats.iloc[0]["type_contrat"] is None


class TestTransfererContratsDossierVersClient:
    def test_dossier_cmr_migre_vers_le_client(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        ajouter_contrat({"prospect_id": pid, "univers": "Télécom", "categorie": "Mobile",
                          "fournisseur": "Orange", "nom_offre": "Forfait 50Go", "cout_mensuel": 15.0,
                          "type_contrat": "dossier_cmr"})
        cid = ajouter_client({"prenom": "Jean", "nom": "Dupont"})

        transferer_contrats_dossier_vers_client(pid, cid)

        contrats_client = lire_contrats_client(cid)
        assert len(contrats_client) == 1
        assert contrats_client.iloc[0]["nom_offre"] == "Forfait 50Go"
        assert contrats_client.iloc[0]["prospect_id"] is None

        assert lire_contrats_prospect(pid).empty

    def test_contrats_reference_externe_restants_sont_supprimes(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        ajouter_contrat({"prospect_id": pid, "univers": "Télécom", "categorie": "Mobile",
                          "fournisseur": "Orange", "nom_offre": "Forfait 50Go", "cout_mensuel": 15.0,
                          "type_contrat": "dossier_cmr"})
        ajouter_contrat({"prospect_id": pid, "univers": "Énergie", "categorie": "Électricité",
                          "fournisseur": "EDF", "nom_offre": "Tarif Bleu", "cout_mensuel": 60.0,
                          "type_contrat": "reference_externe"})
        cid = ajouter_client({"prenom": "Jean", "nom": "Dupont"})

        transferer_contrats_dossier_vers_client(pid, cid)

        contrats_client = lire_contrats_client(cid)
        assert len(contrats_client) == 1
        assert contrats_client.iloc[0]["nom_offre"] == "Forfait 50Go"
        assert lire_contrats_prospect(pid).empty
