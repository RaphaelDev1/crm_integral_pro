# ==============================================================================
#  TESTS — backend/services/notification_engine.py (partie métier ajoutée) :
#  relances du jour, alerte fin d'engagement, digest admin, lien portail
#  prospect. Porté de src/tests/test_notifications.py. Même idiome que
#  test_dossier_engine.py (session factice + asyncio.run()).
# ==============================================================================
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from backend.models.client import Client
from backend.models.contrat import Contrat
from backend.models.parametre import Parametre
from backend.models.prospect import Prospect
from backend.services import notification_engine


def _run(coro):
    return asyncio.run(coro)


class FakeSession:
    """`file_attente` : une liste de résultats consommée dans l'ordre par
    execute() successifs (une entrée par requête, ex. Prospect puis Client)."""

    def __init__(self, file_attente=None, objets=None):
        self._file_attente = list(file_attente or [])
        self._objets = objets or {}
        self.committed = False

    async def execute(self, _query):
        return _FakeResult(self._file_attente.pop(0) if self._file_attente else [])

    async def get(self, model, id_):
        return self._objets.get((model, id_))

    async def commit(self):
        self.committed = True


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


def _date_courte(jours_ecart: int) -> str:
    return (datetime.now().date() + timedelta(days=jours_ecart)).strftime("%d/%m/%Y")


# ------------------------------------------------------------------------------
#  relances_du_jour()
# ------------------------------------------------------------------------------
def test_relances_du_jour_combine_prospects_et_clients_en_retard():
    prospect = Prospect(id=1, prenom="Alice", nom="Martin", telephone="0600", statut="À relancer",
                         date_relance=_date_courte(-2), economie_estimee_an=120.0)
    client = Client(id=2, prenom="Bob", nom="Durand", telephone="0601", statut_relance="Relancé",
                     date_relance=_date_courte(0), economie_estimee_an=80.0)
    db = FakeSession(file_attente=[[prospect], [client]])

    relances = _run(notification_engine.relances_du_jour(db))

    assert len(relances) == 2
    # Trié par retard décroissant : le prospect (2 jours de retard) avant le client (0 jour).
    assert relances[0]["type"] == "Prospect" and relances[0]["retard_jours"] == 2
    assert relances[1]["type"] == "Client" and relances[1]["retard_jours"] == 0


def test_relances_du_jour_exclut_les_relances_futures():
    prospect = Prospect(id=1, prenom="Alice", nom="Martin", telephone="0600", statut="À relancer",
                         date_relance=_date_courte(3), economie_estimee_an=120.0)
    db = FakeSession(file_attente=[[prospect], []])

    relances = _run(notification_engine.relances_du_jour(db))

    assert relances == []


def test_construire_message_relances_vide():
    assert "Aucune relance" in notification_engine.construire_message_relances([])


def test_construire_message_relances_liste_chaque_entree():
    relances = [{"type": "Prospect", "nom": "Alice Martin", "telephone": "0600",
                 "economie": 120.0, "retard_jours": 2}]
    message = notification_engine.construire_message_relances(relances)
    assert "Alice Martin" in message and "120" in message


# ------------------------------------------------------------------------------
#  alerter_fin_engagement()
# ------------------------------------------------------------------------------
def test_alerter_fin_engagement_envoie_un_email_au_seuil_exact():
    client = Client(id=1, prenom="Alice", nom="Martin", email="alice@example.com")
    contrat = Contrat(id=1, client_id=1, univers="Télécom", categorie="Mobile", fournisseur="SFR",
                       nom_offre="RED", cout_mensuel=20.0,
                       date_fin_engagement=_date_courte(notification_engine.JOURS_AVANT_ALERTE_ENGAGEMENT))
    db = FakeSession(file_attente=[[contrat]], objets={(Client, 1): client})

    alternative = {"nom": "Free", "fournisseur": "Free", "prix_mensuel": 15.0, "economie_annuelle": 60.0}
    with patch("backend.services.offres_engine.comparer_offres", new=AsyncMock(return_value=[alternative])), \
         patch.object(notification_engine, "envoyer_email", return_value=True) as mock_email:
        traites = _run(notification_engine.alerter_fin_engagement(db))

    assert len(traites) == 1
    assert traites[0]["email_envoye"] is True
    mock_email.assert_called_once()
    assert "Alice" in mock_email.call_args.args[2]


def test_alerter_fin_engagement_ignore_hors_seuil():
    contrat = Contrat(id=1, client_id=1, univers="Télécom", categorie="Mobile", fournisseur="SFR",
                       cout_mensuel=20.0, date_fin_engagement=_date_courte(30))
    db = FakeSession(file_attente=[[contrat]])

    with patch("backend.services.offres_engine.comparer_offres", new=AsyncMock(return_value=[])):
        traites = _run(notification_engine.alerter_fin_engagement(db))

    assert traites == []


# ------------------------------------------------------------------------------
#  notifier_changement_prix() / envoyer_digest_admin()
# ------------------------------------------------------------------------------
def test_notifier_changement_prix_sans_alertes_ne_fait_rien():
    db = FakeSession()
    assert _run(notification_engine.notifier_changement_prix(db, [])) is False


def test_notifier_changement_prix_envoie_au_destinataire_configure():
    parametre = Parametre(cle="notif_email_destinataire", valeur="admin@example.com")
    db = FakeSession(objets={(Parametre, "notif_email_destinataire"): parametre})
    alertes = [{"fournisseur": "Free", "nom_offre": "Forfait", "ancien_prix": 10.0, "nouveau_prix": 15.0}]

    with patch.object(notification_engine, "envoyer_email", return_value=True) as mock_email:
        envoye = _run(notification_engine.notifier_changement_prix(db, alertes))

    assert envoye is True
    mock_email.assert_called_once()
    assert mock_email.call_args.args[0] == "admin@example.com"


def test_envoyer_digest_admin_sans_destinataire_configure():
    db = FakeSession()
    with patch.object(notification_engine, "envoyer_email") as mock_email:
        envoye = _run(notification_engine.envoyer_digest_admin("texte", "sujet", db))

    assert envoye is False
    mock_email.assert_not_called()


# ------------------------------------------------------------------------------
#  envoyer_demande_documents_prospect()
# ------------------------------------------------------------------------------
def test_envoyer_demande_documents_prospect_envoie_sms_et_email():
    prospect = {"prenom": "Alice", "telephone": "0600000000", "email": "alice@example.com"}
    with patch.object(notification_engine, "envoyer_sms", return_value=True) as mock_sms, \
         patch.object(notification_engine, "envoyer_email", return_value=True) as mock_email:
        resultat = notification_engine.envoyer_demande_documents_prospect(
            prospect, "https://exemple.fr/doc/abc", 7
        )

    assert resultat == {"sms_envoye": True, "email_envoye": True}
    mock_sms.assert_called_once()
    mock_email.assert_called_once()
    assert "Alice" in mock_sms.call_args.args[1]


def test_envoyer_demande_documents_prospect_sans_coordonnees():
    resultat = notification_engine.envoyer_demande_documents_prospect({}, "https://exemple.fr/doc/abc", 7)
    assert resultat == {"sms_envoye": False, "email_envoye": False}
