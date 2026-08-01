# ==============================================================================
#  TESTS — backend/services/prospect_scoring.py : mêmes 3 cas gold que la
#  version SQLite (src/prospects_engine.py::calculer_score_prospect). Aucune
#  base de données réelle pour calculer_score/indicateur_score (fonctions
#  pures) ; une session factice pour dernier_contact/derniers_contacts (async,
#  exécutées via asyncio.run() — pytest-asyncio non installé dans ce projet,
#  cf. test_dossier_engine.py).
# ==============================================================================
import asyncio
from datetime import datetime, timedelta

from backend.models.prospect import Prospect
from backend.services import prospect_scoring
from backend.services.prospect_scoring import FORMAT_DATE, SATISFACTION_BASSE


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items


class FakeSession:
    def __init__(self, resultat=None):
        self._resultat = resultat

    async def execute(self, _query):
        return _FakeResult(self._resultat)


def _prospect(**kwargs):
    base = dict(id=1, economie_estimee_an=0.0, satisfaction_reseau=None,
                veut_rester=None, type_client=None, date_creation=None)
    base.update(kwargs)
    return Prospect(**base)


# ------------------------------------------------------------------------------
#  Cas gold 1 : prospect vide
# ------------------------------------------------------------------------------
def test_score_prospect_vide_est_froid():
    prospect = _prospect()
    score = prospect_scoring.calculer_score(prospect)
    assert score == 0.0
    assert prospect_scoring.indicateur_score(score) == "🟢 froid"


# ------------------------------------------------------------------------------
#  Cas gold 2 : prospect complet, chaud
# ------------------------------------------------------------------------------
def test_score_prospect_complet_est_chaud():
    dernier_contact = datetime.now() - timedelta(days=60)
    prospect = _prospect(
        economie_estimee_an=1000.0,
        satisfaction_reseau=SATISFACTION_BASSE,
        veut_rester=None,
        type_client="Professionnel",
    )
    score = prospect_scoring.calculer_score(prospect, dernier_contact)
    # 1000*2 + 60*3 + 20 (satisfaction) + 10 (pro) = 2210
    assert score == 2210.0
    assert prospect_scoring.indicateur_score(score) == "🔴 chaud"

    details = prospect_scoring.details_score(prospect, dernier_contact)
    facteurs = {d["facteur"] for d in details}
    assert "Faible satisfaction réseau" in facteurs
    assert "Client professionnel" in facteurs
    assert "Souhaite rester chez son opérateur actuel" not in facteurs


# ------------------------------------------------------------------------------
#  Cas gold 3 : prospect déjà converti — le scoring reste calculable
# ------------------------------------------------------------------------------
def test_score_prospect_converti_ne_plante_pas():
    prospect = _prospect(
        economie_estimee_an=200.0,
        converti_at=datetime.now().strftime(FORMAT_DATE),
    )
    score = prospect_scoring.calculer_score(prospect)
    assert score == 400.0
    assert prospect_scoring.indicateur_score(score) in {"🔴 chaud", "🟡 tiède", "🟢 froid"}


# ------------------------------------------------------------------------------
#  dernier_contact() / derniers_contacts() — lecture historique_actions
# ------------------------------------------------------------------------------
def test_dernier_contact_absent_retourne_none():
    session = FakeSession(resultat=None)
    resultat = _run(prospect_scoring.dernier_contact(session, prospect_id=1))
    assert resultat is None


def test_derniers_contacts_garde_la_date_la_plus_recente():
    ancienne = (datetime.now() - timedelta(days=10)).strftime(FORMAT_DATE)
    recente = (datetime.now() - timedelta(days=1)).strftime(FORMAT_DATE)
    session = FakeSession(resultat=[(1, ancienne), (1, recente), (2, ancienne)])

    derniers = _run(prospect_scoring.derniers_contacts(session))

    assert derniers[1].strftime(FORMAT_DATE) == recente
    assert derniers[2].strftime(FORMAT_DATE) == ancienne
