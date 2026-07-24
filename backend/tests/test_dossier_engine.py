# ==============================================================================
#  TESTS — backend/services/dossier_engine.py : transitions, notes manuelles,
#  détection de stagnation. Aucune base de données réelle : une session factice
#  (commit/refresh no-op, execute pré-rempli) suffit pour ces tests unitaires.
#  Les fonctions testées étant async, on les exécute via asyncio.run() (même
#  idiome que backend/workers/tasks.py::_run) plutôt que pytest-asyncio, non
#  installé dans ce projet.
# ==============================================================================
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from backend.models.dossier import Dossier
from backend.services import dossier_engine
from backend.services.dossier_engine import FORMAT_DATE


def _run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self, resultats=None):
        self.committed = False
        self._resultats = resultats or []

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        pass

    async def execute(self, _query):
        return _FakeResult(self._resultats)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


def _dossier(**kwargs):
    base = dict(id=1, client_id=1, univers="telecom_mobile", statut="initie", notes_workflow=[])
    base.update(kwargs)
    return Dossier(**base)


# ------------------------------------------------------------------------------
#  transiter()
# ------------------------------------------------------------------------------
def test_transiter_journalise_et_horodate():
    dossier = _dossier()
    db = FakeSession()

    _run(dossier_engine.transiter(db, dossier, "docs_demandes", par="conseiller1"))

    assert dossier.statut == "docs_demandes"
    assert dossier.date_derniere_transition is not None
    assert len(dossier.notes_workflow) == 1
    entree = dossier.notes_workflow[0]
    assert entree["type"] == "transition"
    assert entree["de"] == "initie"
    assert entree["vers"] == "docs_demandes"
    assert entree["par"] == "conseiller1"
    assert db.committed


def test_transiter_invalide_leve_exception():
    dossier = _dossier(statut="initie")
    db = FakeSession()

    with pytest.raises(dossier_engine.TransitionInvalide):
        _run(dossier_engine.transiter(db, dossier, "actif", par="conseiller1"))


def test_transiter_appelle_on_transition_callback():
    dossier = _dossier()
    db = FakeSession()
    appels = []

    _run(dossier_engine.transiter(
        db, dossier, "docs_demandes", par="conseiller1",
        on_transition=lambda d, ancien: appels.append((d.statut, ancien)),
    ))

    assert appels == [("docs_demandes", "initie")]


# ------------------------------------------------------------------------------
#  ajouter_note()
# ------------------------------------------------------------------------------
def test_ajouter_note_ne_change_pas_le_statut():
    dossier = _dossier(statut="mandat_a_signer")
    db = FakeSession()

    _run(dossier_engine.ajouter_note(db, dossier, "Client rappelé, ok pour signer demain.", par="conseiller1"))

    assert dossier.statut == "mandat_a_signer"
    assert len(dossier.notes_workflow) == 1
    entree = dossier.notes_workflow[0]
    assert entree["type"] == "note"
    assert entree["texte"] == "Client rappelé, ok pour signer demain."
    assert entree["par"] == "conseiller1"
    assert db.committed


# ------------------------------------------------------------------------------
#  dossiers_stagnants()
# ------------------------------------------------------------------------------
def _il_y_a(jours: float) -> str:
    return (datetime.now() - timedelta(days=jours)).strftime(FORMAT_DATE)


def test_dossiers_stagnants_detecte_le_depassement_de_seuil():
    # docs_demandes : seuil 3 jours (dossier_notifications.SEUILS_JOURS_PAR_STATUT)
    stagnant = _dossier(id=1, statut="docs_demandes", date_derniere_transition=_il_y_a(5))
    recent = _dossier(id=2, statut="docs_demandes", date_derniere_transition=_il_y_a(1))
    db = FakeSession(resultats=[stagnant, recent])

    resultat = _run(dossier_engine.dossiers_stagnants(db))

    assert resultat == [stagnant]


def test_dossiers_stagnants_exclut_les_relances_recentes():
    dossier = _dossier(
        id=1, statut="docs_demandes",
        date_derniere_transition=_il_y_a(10),
        derniere_relance_envoyee_le=_il_y_a(1),
    )
    db = FakeSession(resultats=[dossier])

    resultat = _run(dossier_engine.dossiers_stagnants(db))

    assert resultat == []


def test_dossiers_stagnants_relance_si_la_derniere_relance_est_ancienne():
    dossier = _dossier(
        id=1, statut="docs_demandes",
        date_derniere_transition=_il_y_a(10),
        derniere_relance_envoyee_le=_il_y_a(5),
    )
    db = FakeSession(resultats=[dossier])

    resultat = _run(dossier_engine.dossiers_stagnants(db))

    assert resultat == [dossier]


# ------------------------------------------------------------------------------
#  Dispatch des templates de notification sur transition (dossier_notifications)
# ------------------------------------------------------------------------------
def test_transiter_declenche_le_template_du_nouveau_statut():
    from backend.models.client import Client
    from backend.services import dossier_notifications

    dossier = _dossier(statut="docs_recus")
    client = Client(id=1, prenom="Alice", nom="Martin", email="alice@example.com", telephone="0600000000")
    db = FakeSession()

    with patch("backend.services.notification_engine.envoyer_email", return_value=True) as mock_email, \
         patch("backend.services.notification_engine.envoyer_sms", return_value=True) as mock_sms:
        _run(dossier_engine.transiter(
            db, dossier, "mandat_a_signer", par="conseiller1",
            on_transition=lambda d, _ancien: dossier_notifications.notifier_transition(d, client),
        ))

    mock_email.assert_called_once()
    mock_sms.assert_called_once()
    assert "Alice" in mock_email.call_args.args[2]


def test_transiter_ne_declenche_rien_pour_un_statut_sans_template():
    from backend.models.client import Client
    from backend.services import dossier_notifications

    # docs_recus n'a pas de template dans TEMPLATES_STATUT (contrairement à
    # mandat_a_signer, mandat_signe, etc.) — aucun envoi ne doit être déclenché.
    dossier = _dossier(statut="docs_demandes")
    client = Client(id=1, prenom="Alice", nom="Martin", email="alice@example.com", telephone="0600000000")
    db = FakeSession()

    with patch("backend.services.notification_engine.envoyer_email") as mock_email, \
         patch("backend.services.notification_engine.envoyer_sms") as mock_sms:
        _run(dossier_engine.transiter(
            db, dossier, "docs_recus", par="conseiller1",
            on_transition=lambda d, _ancien: dossier_notifications.notifier_transition(d, client),
        ))

    mock_email.assert_not_called()
    mock_sms.assert_not_called()
