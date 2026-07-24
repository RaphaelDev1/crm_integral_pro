# ==============================================================================
#  TESTS — backend/services/demarches_engine.py : dérivation des démarches
#  requises par univers, champs manquants, et surtout le refus légal de
#  génération tant que le mandat de représentation n'est pas signé. Aucune
#  base de données réelle : une session factice suffit (même idiome que
#  test_dossier_engine.py). Fonctions async exécutées via asyncio.run()
#  (pytest-asyncio non installé dans ce projet).
# ==============================================================================
import asyncio
from unittest.mock import patch

import pytest

from backend.models.client import Client
from backend.models.demarche import Demarche
from backend.models.dossier import Dossier
from backend.models.mandat import Mandat
from backend.services import demarches_engine


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


class FakeSession:
    def __init__(self, get_map=None, execute_results=None):
        self.get_map = get_map or {}
        self._execute_results = execute_results or []
        self.committed = 0
        self.added = []

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        items = self._execute_results.pop(0) if self._execute_results else []
        return _FakeResult(items)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed += 1

    async def refresh(self, obj):
        pass


def _dossier(**kwargs):
    base = dict(id=1, client_id=1, univers="telecom_mobile", statut="mandat_signe")
    base.update(kwargs)
    return Dossier(**base)


# ------------------------------------------------------------------------------
#  demarches_requises()
# ------------------------------------------------------------------------------
def test_demarches_requises_telecom_mobile():
    assert demarches_engine.demarches_requises(_dossier(univers="telecom_mobile")) == ["mandat", "portabilite"]


def test_demarches_requises_telecom_box():
    assert demarches_engine.demarches_requises(_dossier(univers="telecom_box")) == ["mandat", "resiliation"]


def test_demarches_requises_energie():
    assert demarches_engine.demarches_requises(_dossier(univers="energie")) == ["mandat", "changement_fournisseur"]


def test_demarches_requises_univers_inconnu_repli_par_defaut():
    assert demarches_engine.demarches_requises(_dossier(univers="on_ne_sait_pas")) == ["mandat", "souscription"]


# ------------------------------------------------------------------------------
#  creer_demarche()
# ------------------------------------------------------------------------------
def test_creer_demarche_initialise_les_donnees_requises():
    dossier = _dossier(univers="telecom_mobile")
    db = FakeSession()

    demarche = _run(demarches_engine.creer_demarche(db, dossier, "portabilite"))

    assert demarche.dossier_id == 1
    assert demarche.univers == "telecom_mobile"
    assert demarche.statut == "a_generer"
    assert set(demarche.donnees_requises.keys()) == {"rio", "numero_ligne"}
    assert demarche.donnees_requises["rio"]["requis"] is True
    assert demarche.donnees_requises["rio"]["valeur"] is None
    assert db.committed


def test_creer_demarche_type_inconnu_leve_exception():
    dossier = _dossier()
    db = FakeSession()

    with pytest.raises(demarches_engine.DemarcheEngineError):
        _run(demarches_engine.creer_demarche(db, dossier, "type_bidon"))


# ------------------------------------------------------------------------------
#  champs_manquants()
# ------------------------------------------------------------------------------
def test_champs_manquants_detecte_un_champ_requis_vide():
    demarche = Demarche(
        id=1, dossier_id=1, type_demarche="portabilite",
        donnees_requises={
            "rio": {"valeur": None, "requis": True, "label": "RIO"},
            "numero_ligne": {"valeur": "0601020304", "requis": True, "label": "Numéro"},
        },
    )
    manquants = demarches_engine.champs_manquants(demarche)
    assert list(manquants.keys()) == ["rio"]


def test_champs_manquants_vide_si_tout_rempli():
    demarche = Demarche(
        id=1, dossier_id=1, type_demarche="portabilite",
        donnees_requises={
            "rio": {"valeur": "AB1234", "requis": True, "label": "RIO"},
            "numero_ligne": {"valeur": "0601020304", "requis": True, "label": "Numéro"},
        },
    )
    assert demarches_engine.champs_manquants(demarche) == {}


def test_champs_manquants_ignore_les_champs_facultatifs():
    demarche = Demarche(
        id=1, dossier_id=1, type_demarche="resiliation",
        donnees_requises={
            "numero_contrat": {"valeur": "CT-1", "requis": True, "label": "Contrat"},
            "date_effet_souhaitee": {"valeur": None, "requis": False, "label": "Date"},
        },
    )
    assert demarches_engine.champs_manquants(demarche) == {}


# ------------------------------------------------------------------------------
#  marquer_champs()
# ------------------------------------------------------------------------------
def test_marquer_champs_fusionne_sans_ecraser_les_autres_cles():
    demarche = Demarche(
        id=1, dossier_id=1, type_demarche="changement_fournisseur",
        donnees_requises={
            "pdl": {"valeur": None, "requis": False, "label": "PDL"},
            "rib": {"valeur": None, "requis": True, "label": "RIB"},
        },
    )
    db = FakeSession()

    _run(demarches_engine.marquer_champs(db, demarche, {"rib": "FR7612345"}))

    assert demarche.donnees_requises["rib"]["valeur"] == "FR7612345"
    assert demarche.donnees_requises["pdl"]["valeur"] is None
    assert db.committed


# ------------------------------------------------------------------------------
#  generer_document() — la règle légale
# ------------------------------------------------------------------------------
def test_generer_document_refuse_si_aucun_mandat():
    dossier = _dossier()
    demarche = Demarche(id=1, dossier_id=1, type_demarche="resiliation",
                         donnees_requises={"numero_contrat": {"valeur": "CT-1", "requis": True, "label": "x"}})
    db = FakeSession(get_map={(Dossier, 1): dossier}, execute_results=[[]])

    with pytest.raises(demarches_engine.DemarcheEngineError, match="Mandat de représentation non signé"):
        _run(demarches_engine.generer_document(db, demarche))


def test_generer_document_refuse_si_mandat_non_signe():
    dossier = _dossier()
    mandat = Mandat(id=9, client_id=1, statut="envoye")
    demarche = Demarche(id=1, dossier_id=1, type_demarche="resiliation",
                         donnees_requises={"numero_contrat": {"valeur": "CT-1", "requis": True, "label": "x"}})
    db = FakeSession(get_map={(Dossier, 1): dossier}, execute_results=[[mandat]])

    with pytest.raises(demarches_engine.DemarcheEngineError, match="Mandat de représentation non signé"):
        _run(demarches_engine.generer_document(db, demarche))

    assert demarche.statut != "generee"


def test_generer_document_refuse_si_champs_manquants():
    dossier = _dossier()
    mandat = Mandat(id=9, client_id=1, statut="signe")
    demarche = Demarche(
        id=1, dossier_id=1, type_demarche="portabilite",
        donnees_requises={"rio": {"valeur": None, "requis": True, "label": "RIO"}},
    )
    db = FakeSession(get_map={(Dossier, 1): dossier}, execute_results=[[mandat]])

    with pytest.raises(demarches_engine.DemarcheEngineError, match="Champs manquants"):
        _run(demarches_engine.generer_document(db, demarche))


def test_generer_document_ok_si_mandat_signe_et_champs_complets():
    dossier = _dossier()
    client = Client(id=1, prenom="Alice", nom="Martin")
    mandat = Mandat(id=9, client_id=1, statut="signe")
    demarche = Demarche(
        id=1, dossier_id=1, type_demarche="portabilite",
        donnees_requises={
            "rio": {"valeur": "AB1234", "requis": True, "label": "RIO"},
            "numero_ligne": {"valeur": "0601020304", "requis": True, "label": "Numéro"},
        },
    )
    db = FakeSession(
        get_map={(Dossier, 1): dossier, (Client, 1): client},
        execute_results=[[mandat]],
    )

    with patch("backend.services.storage_engine.upload_fichier", return_value="dossiers/1/demarches/x.pdf") as mock_upload:
        _run(demarches_engine.generer_document(db, demarche))

    assert demarche.statut == "generee"
    assert demarche.document_url == "dossiers/1/demarches/x.pdf"
    assert demarche.date_generation is not None
    mock_upload.assert_called_once()


def test_generer_document_type_mandat_lie_le_mandat_signe():
    dossier = _dossier()
    client = Client(id=1, prenom="Alice", nom="Martin")
    mandat = Mandat(id=9, client_id=1, statut="signe")
    demarche = Demarche(id=1, dossier_id=1, type_demarche="mandat", donnees_requises={})
    db = FakeSession(
        get_map={(Dossier, 1): dossier, (Client, 1): client},
        execute_results=[[mandat]],
    )

    with patch("backend.services.storage_engine.upload_fichier", return_value="dossiers/1/demarches/mandat.pdf"):
        _run(demarches_engine.generer_document(db, demarche))

    assert demarche.mandat_id == 9
