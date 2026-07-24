# ==============================================================================
#  TESTS — backend/services/document_engine.py : couverture des champs requis
#  par template et génération effective d'un PDF valide pour chaque type de
#  démarche.
# ==============================================================================
from backend.models.client import Client
from backend.models.demarche import TYPES_DEMARCHE
from backend.models.dossier import Dossier
from backend.services import document_engine


def _dossier(**kwargs):
    base = dict(id=1, client_id=1, univers="telecom_mobile", statut="mandat_signe")
    base.update(kwargs)
    return Dossier(**base)


def _client(**kwargs):
    base = dict(id=1, prenom="Alice", nom="Martin", email="alice@example.com", telephone="0600000000")
    base.update(kwargs)
    return Client(**base)


def test_champs_requis_portabilite_contient_rio():
    assert "rio" in document_engine.CHAMPS_REQUIS_PAR_TEMPLATE["portabilite"]
    assert document_engine.CHAMPS_REQUIS_PAR_TEMPLATE["portabilite"]["rio"]["requis"] is True


def test_champs_requis_changement_fournisseur_contient_rib():
    assert "rib" in document_engine.CHAMPS_REQUIS_PAR_TEMPLATE["changement_fournisseur"]
    assert document_engine.CHAMPS_REQUIS_PAR_TEMPLATE["changement_fournisseur"]["rib"]["requis"] is True


def test_generateurs_par_type_couvre_tous_les_types_demarche():
    assert set(document_engine.GENERATEURS_PAR_TYPE.keys()) == set(TYPES_DEMARCHE)


def test_champs_requis_par_template_couvre_tous_les_types_demarche():
    assert set(document_engine.CHAMPS_REQUIS_PAR_TEMPLATE.keys()) == set(TYPES_DEMARCHE)


def test_generer_pdf_mandat_representation_retourne_des_bytes_pdf():
    pdf = document_engine.generer_pdf_mandat_representation(_dossier(), _client())
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")


def test_generer_pdf_resiliation_box_retourne_des_bytes_pdf():
    pdf = document_engine.generer_pdf_resiliation_box(
        _dossier(univers="telecom_box"), _client(), {"numero_contrat": "CT-123"}
    )
    assert pdf.startswith(b"%PDF")


def test_generer_pdf_demande_portabilite_mobile_retourne_des_bytes_pdf():
    pdf = document_engine.generer_pdf_demande_portabilite_mobile(
        _dossier(), _client(), {"rio": "AB1234", "numero_ligne": "0601020304"}
    )
    assert pdf.startswith(b"%PDF")


def test_generer_pdf_changement_fournisseur_energie_retourne_des_bytes_pdf():
    pdf = document_engine.generer_pdf_changement_fournisseur_energie(
        _dossier(univers="energie"), _client(), {"pdl": "12345", "rib": "FR76..."}
    )
    assert pdf.startswith(b"%PDF")


def test_tous_les_generateurs_produisent_un_pdf_valide():
    dossier = _dossier()
    client = _client()
    for type_demarche, generateur in document_engine.GENERATEURS_PAR_TYPE.items():
        donnees = {cle: "valeur-test" for cle in document_engine.CHAMPS_REQUIS_PAR_TEMPLATE[type_demarche]}
        pdf = generateur(dossier, client, donnees)
        assert pdf.startswith(b"%PDF"), f"Échec pour le type {type_demarche}"
