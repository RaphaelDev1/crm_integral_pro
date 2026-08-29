# ==============================================================================
#  TESTS — services/ia_conseil_facture.py (§3.1 : upload facture pendant une
#  session, analyse via facture_analyzer.py réutilisé tel quel, proposition
#  d'auto-remplissage). Même idiome que test_ia_conseil_engine.py : FakeSession
#  + asyncio.run() (pas de pytest-asyncio dans ce projet).
# ==============================================================================
import asyncio
import uuid

import pytest

from backend.models.ia_conseil import SessionFacture, SessionTrame
from backend.services import ia_conseil_facture as svc
from backend.services.facture_analyzer import FactureAnalyzerError
from backend.services.storage_engine import StorageError


def _run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self):
        self.added = []
        self.flushed = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed += 1


def _session(categorie="mobile"):
    return SessionTrame(id=uuid.uuid4(), categorie_slug=categorie, reponses={})


# ------------------------------------------------------------------------------
#  mapper_extraction_vers_reponses
# ------------------------------------------------------------------------------
def test_mapper_mobile_mappe_operateur_prix_et_conso():
    extraction = {"operateur": "Orange", "prix_ttc": 45.99, "data_conso_go": 150.0}
    propositions = svc.mapper_extraction_vers_reponses("mobile", extraction)
    assert propositions == {
        "operateur_actuel": "Orange",
        "cout_actuel_mensuel": 45.99,
        "conso_data_go": 150.0,
    }


def test_mapper_ignore_champs_vides_ou_nuls():
    extraction = {"operateur": "", "prix_ttc": 0.0, "data_conso_go": None}
    assert svc.mapper_extraction_vers_reponses("mobile", extraction) == {}


def test_mapper_box_ne_propose_pas_de_conso_data():
    extraction = {"operateur": "Free", "prix_ttc": 39.99, "data_conso_go": 999.0}
    propositions = svc.mapper_extraction_vers_reponses("box", extraction)
    assert propositions == {"operateur_actuel": "Free", "cout_actuel_mensuel": 39.99}


def test_mapper_energie_elec_utilise_les_ids_suffixes():
    extraction = {"operateur": "EDF", "prix_ttc": 89.0}
    propositions = svc.mapper_extraction_vers_reponses("energie_elec", extraction)
    assert propositions == {"fournisseur_actuel_elec": "EDF", "cout_actuel_mensuel_elec": 89.0}


def test_mapper_categorie_inconnue_renvoie_vide():
    assert svc.mapper_extraction_vers_reponses("inconnue", {"operateur": "X", "prix_ttc": 10}) == {}


# ------------------------------------------------------------------------------
#  televerser
# ------------------------------------------------------------------------------
def test_televerser_rejette_fichier_vide():
    with pytest.raises(ValueError):
        _run(svc.televerser(FakeSession(), _session(), b"", "facture.pdf"))


def test_televerser_rejette_format_non_pdf():
    with pytest.raises(ValueError):
        _run(svc.televerser(FakeSession(), _session(), b"contenu", "facture.jpg"))


def test_televerser_stocke_et_cree_la_ligne(monkeypatch):
    monkeypatch.setattr(svc.storage_engine, "upload_fichier", lambda *a, **kw: "cle/fake.pdf")
    db = FakeSession()
    session = _session()
    facture = _run(svc.televerser(db, session, b"%PDF-1.4 ...", "facture.pdf"))

    assert facture.storage_key == "cle/fake.pdf"
    assert facture.session_id == session.id
    assert facture.categorie_slug == "mobile"
    assert facture.statut == "en_attente"
    assert db.added == [facture]


# ------------------------------------------------------------------------------
#  analyser
# ------------------------------------------------------------------------------
def _facture(categorie="mobile"):
    return SessionFacture(id=uuid.uuid4(), session_id=uuid.uuid4(), categorie_slug=categorie, storage_key="k", statut="en_attente")


def test_analyser_statut_echouee_si_telechargement_impossible(monkeypatch):
    def _echoue(_cle):
        raise StorageError("introuvable")
    monkeypatch.setattr(svc.storage_engine, "telecharger_document", _echoue)

    facture = _run(svc.analyser(FakeSession(), _facture()))
    assert facture.statut == "echouee"
    assert "introuvable" in facture.erreur


def test_analyser_statut_echouee_si_extraction_echoue(monkeypatch, tmp_path):
    monkeypatch.setattr(svc.storage_engine, "telecharger_document", lambda cle: b"%PDF-1.4 ...")

    def _echoue(_chemin):
        raise FactureAnalyzerError("clé API absente")
    monkeypatch.setattr(svc, "analyser_facture", _echoue)

    facture = _run(svc.analyser(FakeSession(), _facture()))
    assert facture.statut == "echouee"
    assert "clé API" in facture.erreur


def test_analyser_succes_construit_extraction_et_propositions(monkeypatch):
    monkeypatch.setattr(svc.storage_engine, "telecharger_document", lambda cle: b"%PDF-1.4 ...")
    resultat = {
        "operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99, "data_conso_go": 150.0,
        "options": [], "engagement_mois": 12, "date_fin_engagement": "15/03/2027",
        "iban_prelevement": "", "type_couverture": "", "bonus_malus": "",
    }
    monkeypatch.setattr(svc, "analyser_facture", lambda chemin: resultat)

    facture = _run(svc.analyser(FakeSession(), _facture()))
    assert facture.statut == "analysee"
    assert facture.analysee_le is not None
    assert facture.extraction["operateur"] == "Orange"
    assert facture.extraction["propositions_reponses"] == {
        "operateur_actuel": "Orange", "cout_actuel_mensuel": 45.99, "conso_data_go": 150.0,
    }


# ------------------------------------------------------------------------------
#  appliquer
# ------------------------------------------------------------------------------
def test_appliquer_enregistre_chaque_reponse_et_marque_la_facture(monkeypatch):
    appels = []

    async def _fake_enregistrer(_db, _session, question_id, valeur):
        appels.append((question_id, valeur))
    monkeypatch.setattr(svc.engine, "enregistrer_reponse", _fake_enregistrer)

    db = FakeSession()
    session = _session()
    facture = _facture()
    reponses = {"operateur_actuel": "Orange", "cout_actuel_mensuel": 45.99}

    _run(svc.appliquer(db, session, facture, reponses))

    assert set(appels) == set(reponses.items())
    assert facture.reponses_appliquees == reponses
