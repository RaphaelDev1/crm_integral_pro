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


def test_transiter_vers_le_meme_statut_est_un_noop():
    # Ex. le conseiller confirme manuellement "docs_recus" pile au moment où
    # la validation du dernier document vient de déclencher la même
    # transition automatiquement (clients.py::valider_document) — ne doit pas
    # lever TransitionInvalide, juste ne rien changer.
    dossier = _dossier(statut="docs_recus", notes_workflow=[{"deja": "present"}])
    db = FakeSession()

    resultat = _run(dossier_engine.transiter(db, dossier, "docs_recus", par="conseiller1"))

    assert resultat is dossier
    assert dossier.statut == "docs_recus"
    assert dossier.notes_workflow == [{"deja": "present"}]
    assert not db.committed


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


# ------------------------------------------------------------------------------
#  construire_timeline() — statuts dérivés affichés au client/conseiller
# ------------------------------------------------------------------------------
def _etape(etapes, cle):
    return next(e for e in etapes if e["cle"] == cle)


def test_docs_demandes_orange_des_la_creation_du_dossier():
    # Avant toute action du conseiller (dossier encore "initie"), l'étape ne
    # doit plus rester grise ("a_venir") : c'est la première chose à faire.
    dossier = _dossier(statut="initie")
    etapes = dossier_engine.construire_timeline(dossier)
    assert _etape(etapes, "docs_demandes")["statut"] == "en_cours"


def test_docs_demandes_vert_une_fois_la_demande_envoyee():
    dossier = _dossier(statut="docs_demandes")
    etapes = dossier_engine.construire_timeline(dossier)
    assert _etape(etapes, "docs_demandes")["statut"] == "termine"


def test_docs_recus_orange_puis_vert_selon_documents_valides():
    dossier = _dossier(statut="docs_recus")

    avant = dossier_engine.construire_timeline(dossier, documents_valides=False)
    assert _etape(avant, "docs_recus")["statut"] == "en_cours"

    apres = dossier_engine.construire_timeline(dossier, documents_valides=True)
    assert _etape(apres, "docs_recus")["statut"] == "termine"


def test_mandat_representation_orange_sur_envoi_vert_seulement_sur_signature():
    # Envoyé mais pas encore signé : orange ("Mandat envoyé"), jamais vert —
    # avant ce correctif, l'étape passait vert dès l'envoi (voir item #9,
    # "j'ai signé le mandat, ce n'est pas vert").
    dossier = _dossier(statut="mandat_a_signer")

    envoye = dossier_engine.construire_timeline(dossier, mandat_envoye=True, mandat_representation_signe=False)
    assert _etape(envoye, "mandat_a_signer")["statut"] == "en_cours"
    assert _etape(envoye, "mandat_a_signer")["label"] == "Mandat envoyé"

    signe = dossier_engine.construire_timeline(dossier, mandat_envoye=True, mandat_representation_signe=True)
    assert _etape(signe, "mandat_a_signer")["statut"] == "termine"
    assert _etape(signe, "mandat_a_signer")["label"] == "Mandat de représentation signé"


def test_mandat_representation_signe_vert_meme_si_statut_dossier_en_retard():
    # Le conseiller a généré/envoyé et le client a signé, mais le statut
    # grossier du dossier n'a jamais été avancé manuellement au-delà de
    # "docs_recus" — l'étape doit quand même passer verte, indépendamment de
    # la position de dossier.statut (root cause de l'item #9).
    dossier = _dossier(statut="docs_recus")

    etapes = dossier_engine.construire_timeline(
        dossier, mandat_envoye=True, mandat_representation_signe=True, documents_valides=True,
    )
    assert _etape(etapes, "mandat_a_signer")["statut"] == "termine"


def test_mandat_honoraires_orange_sur_envoi_vert_sur_signature():
    dossier = _dossier(statut="mandat_signe")

    envoye = dossier_engine.construire_timeline(dossier, mandat_honoraires_envoye=True, mandat_honoraires_signe=False)
    assert _etape(envoye, "mandat_signe")["statut"] == "en_cours"

    signe = dossier_engine.construire_timeline(dossier, mandat_honoraires_envoye=True, mandat_honoraires_signe=True)
    assert _etape(signe, "mandat_signe")["statut"] == "termine"


def test_mandat_honoraires_signe_vert_sans_mandat_representation_envoye():
    # Les deux mandats sont indépendants : un dossier peut avoir son mandat
    # honoraires signé (etape "mandat_signe") sans que mandat_envoye (mandat
    # de représentation) ne soit vrai.
    dossier = _dossier(statut="docs_recus")

    etapes = dossier_engine.construire_timeline(
        dossier, mandat_envoye=False, mandat_honoraires_envoye=True, mandat_honoraires_signe=True,
    )
    assert _etape(etapes, "mandat_signe")["statut"] == "termine"
    assert _etape(etapes, "mandat_a_signer")["statut"] != "termine"


def test_docs_recus_vert_meme_si_statut_dossier_en_retard():
    dossier = _dossier(statut="docs_demandes")

    etapes = dossier_engine.construire_timeline(dossier, documents_recus=True, documents_valides=True)
    assert _etape(etapes, "docs_recus")["statut"] == "termine"
