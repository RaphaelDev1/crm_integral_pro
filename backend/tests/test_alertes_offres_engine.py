# ==============================================================================
#  TESTS — backend/services/alertes_offres_engine.py : détection d'offres
#  moins chères que le contrat actif d'un client, validation/rejet d'alerte.
#  Même idiome que backend/tests/test_veille_engine.py.
# ==============================================================================
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.models.alerte_offre import AlerteOffre
from backend.models.client import Client
from backend.models.contrat import Contrat
from backend.models.parametre import Parametre
from backend.services import alertes_offres_engine


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class FakeSession:
    def __init__(self, execute_queue=None, objets=None):
        self._execute_queue = list(execute_queue or [])
        self._objets = objets or {}
        self.added = []
        self.committed = False

    async def execute(self, _query):
        valeur = self._execute_queue.pop(0) if self._execute_queue else []
        return _FakeResult(valeur)

    async def get(self, model, id_):
        return self._objets.get((model, id_))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


def _contrat(**kwargs):
    base = dict(id=1, client_id=1, univers="Télécom", categorie="Mobile",
                fournisseur="SFR", cout_mensuel=30.0)
    base.update(kwargs)
    return Contrat(**base)


def _meilleure_offre(**kwargs):
    base = dict(id=99, nom="Forfait Eco", fournisseur="Free", prix_mensuel=15.0,
                economie_mensuelle=15.0, economie_annuelle=180.0)
    base.update(kwargs)
    return base


# ------------------------------------------------------------------------------
#  detecter_offres_moins_cheres()
# ------------------------------------------------------------------------------
def test_detecter_offres_moins_cheres_cree_une_alerte_si_economie_depasse_le_seuil():
    contrat = _contrat()
    client = Client(id=1, prenom="Jean", nom="Dupont")
    db = FakeSession(
        execute_queue=[[contrat], []],  # contrats actifs, puis alertes existantes
        objets={(Client, 1): client},
    )

    with patch.object(alertes_offres_engine.offres_engine, "comparer_offres",
                       new=AsyncMock(return_value=[_meilleure_offre()])):
        creees = _run(alertes_offres_engine.detecter_offres_moins_cheres(db))

    assert len(creees) == 1
    assert creees[0]["fournisseur"] == "Free"
    assert any(isinstance(o, AlerteOffre) for o in db.added)
    alerte = next(o for o in db.added if isinstance(o, AlerteOffre))
    assert alerte.client_id == 1 and alerte.offre_id == 99
    assert alerte.statut == "en_attente"
    assert db.committed


def test_detecter_offres_moins_cheres_ignore_si_economie_sous_le_seuil():
    contrat = _contrat()
    db = FakeSession(execute_queue=[[contrat], []])

    with patch.object(alertes_offres_engine.offres_engine, "comparer_offres",
                       new=AsyncMock(return_value=[_meilleure_offre(economie_mensuelle=1.0)])):
        creees = _run(alertes_offres_engine.detecter_offres_moins_cheres(db))

    assert creees == []
    assert db.added == []


def test_detecter_offres_moins_cheres_ignore_si_deja_une_alerte_en_attente():
    contrat = _contrat()
    alerte_existante = AlerteOffre(id=1, client_id=1, offre_id=99, statut="en_attente")
    db = FakeSession(execute_queue=[[contrat], [alerte_existante]])

    with patch.object(alertes_offres_engine.offres_engine, "comparer_offres",
                       new=AsyncMock(return_value=[_meilleure_offre()])):
        creees = _run(alertes_offres_engine.detecter_offres_moins_cheres(db))

    assert creees == []
    assert db.added == []


def test_detecter_offres_moins_cheres_utilise_le_seuil_configure():
    contrat = _contrat()
    db = FakeSession(
        execute_queue=[[contrat], []],
        objets={(Parametre, alertes_offres_engine.CLE_PARAMETRE_SEUIL): Parametre(valeur="20")},
    )

    # économie de 15€ < seuil configuré de 20€ -> aucune alerte, alors que
    # le seuil par défaut (5€) l'aurait laissée passer.
    with patch.object(alertes_offres_engine.offres_engine, "comparer_offres",
                       new=AsyncMock(return_value=[_meilleure_offre(economie_mensuelle=15.0)])):
        creees = _run(alertes_offres_engine.detecter_offres_moins_cheres(db))

    assert creees == []


# ------------------------------------------------------------------------------
#  valider_alerte() / rejeter_alerte()
# ------------------------------------------------------------------------------
def test_valider_alerte_notifie_le_client_par_email_et_sms():
    alerte = AlerteOffre(id=1, client_id=1, cout_propose=15.0, economie_annuelle=180.0, statut="en_attente")
    client = Client(id=1, prenom="Jean", nom="Dupont", email="jean@example.com", telephone="0600000000")
    db = FakeSession(objets={(AlerteOffre, 1): alerte, (Client, 1): client})

    with patch.object(alertes_offres_engine.notification_engine, "envoyer_email", return_value=True) as mock_email, \
         patch.object(alertes_offres_engine.notification_engine, "envoyer_sms", return_value=True) as mock_sms:
        ok, message = _run(alertes_offres_engine.valider_alerte(db, 1))

    assert ok is True
    assert alerte.statut == "validee"
    mock_email.assert_called_once()
    mock_sms.assert_called_once()
    assert "notifié" in message


def test_valider_alerte_deja_traitee_est_refusee():
    alerte = AlerteOffre(id=1, client_id=1, statut="validee")
    db = FakeSession(objets={(AlerteOffre, 1): alerte})

    ok, message = _run(alertes_offres_engine.valider_alerte(db, 1))

    assert ok is False
    assert "déjà" in message


def test_valider_alerte_introuvable():
    db = FakeSession()

    ok, message = _run(alertes_offres_engine.valider_alerte(db, 999))

    assert ok is False
    assert "introuvable" in message


def test_rejeter_alerte_marque_le_statut():
    alerte = AlerteOffre(id=1, client_id=1, statut="en_attente")
    db = FakeSession(objets={(AlerteOffre, 1): alerte})

    ok = _run(alertes_offres_engine.rejeter_alerte(db, 1))

    assert ok is True
    assert alerte.statut == "rejetee"


def test_rejeter_alerte_deja_traitee_est_refusee():
    alerte = AlerteOffre(id=1, client_id=1, statut="rejetee")
    db = FakeSession(objets={(AlerteOffre, 1): alerte})

    ok = _run(alertes_offres_engine.rejeter_alerte(db, 1))

    assert ok is False
