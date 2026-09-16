# ==============================================================================
#  TESTS — routers/portail_public.py, chemin token scopé "prospect" (upload de
#  facture/speedtest avant conversion en client, cf. section 1.3 du plan de
#  migration). Session factice via app.dependency_overrides[get_db] ;
#  token_engine.valider_token patché — même approche que
#  test_portail_public_speedtest.py.
# ==============================================================================
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.main import app
from backend.models.contrat import Contrat
from backend.models.document_prospect import DocumentProspect
from backend.models.prospect import Prospect
from backend.models.token_public import TokenPublic


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value

    def first(self):
        return self._value[0] if self._value else None


class FakeSession:
    def __init__(self):
        self.get_map = {}
        self.committed = False
        self.added = []
        self.execute_queue = []

    def queue_result(self, value):
        self.execute_queue.append(value)

    async def get(self, model, id_):
        return self.get_map.get((model, id_))

    async def execute(self, _query):
        value = self.execute_queue.pop(0) if self.execute_queue else []
        return _FakeResult(value)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 42


@pytest.fixture
def fake_db():
    return FakeSession()


@pytest.fixture
def api_client(fake_db):
    async def _override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token_prospect(**kwargs):
    base = dict(id=1, token="p" * 32, client_id=None, prospect_id=1,
                peut_uploader_docs=True, peut_signer_mandat=False,
                peut_voir_suivi=False, peut_renseigner_demarches=False,
                peut_transmettre_speedtest=False, remplissage_autonome=True)
    base.update(kwargs)
    return TokenPublic(**base)


def test_contexte_token_prospect_renvoie_un_contexte_reduit(api_client, fake_db):
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont", cree_par="Alice")
    fake_db.queue_result([])  # aucun DocumentProspect déjà transmis

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.get(f"/portail/{'p' * 32}")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["prenom_client"] == "Jean"
    assert corps["nom_client"] == "Dupont"
    assert corps["dossier_id"] is None
    assert corps["peut_signer_mandat"] is False
    # Le lien prospect propose la facture à l'upload (auparavant vide par
    # erreur — voir _contexte_token_prospect). Le test de débit n'y figure
    # volontairement pas : il a son propre parcours dédié (section "Votre
    # débit internet" + page /speedtest) pour laisser au client l'occasion
    # de cliquer sur "Tester mon débit" plutôt que de le marquer fait
    # automatiquement dès l'envoi des documents.
    types_proposes = {d["type_document"] for d in corps["documents_a_fournir"]}
    assert types_proposes == {"facture"}
    assert all(d["statut"] == "a_fournir" for d in corps["documents_a_fournir"])


def test_contexte_token_prospect_introuvable(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.get(f"/portail/{'p' * 32}")

    assert reponse.status_code == 404


def test_upload_document_prospect_cree_un_document_prospect(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())), \
         patch("backend.routers.portail_public.storage_engine.upload_fichier",
               return_value="prospects/1/2026/08/facture_abcd1234_efgh5678.pdf"):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/documents",
            params={"type_document": "facture"},
            files={"fichier": ("facture.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut_kyc"] == "recu"
    documents = [o for o in fake_db.added if isinstance(o, DocumentProspect)]
    assert len(documents) == 1
    assert documents[0].prospect_id == 1
    assert documents[0].type_document == "facture"


def test_upload_document_prospect_notifie_le_conseiller_createur(api_client, fake_db):
    utilisateur_fake = type("U", (), {"username": "alice", "nom_complet": "Alice Martin"})()
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont", cree_par="Alice Martin")
    fake_db.queue_result([utilisateur_fake])  # creer_notification_prospect : User.nom_complet

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())), \
         patch("backend.routers.portail_public.storage_engine.upload_fichier",
               return_value="prospects/1/2026/08/facture_abcd1234_efgh5678.pdf"):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/documents",
            params={"type_document": "facture"},
            files={"fichier": ("facture.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 200
    from backend.models.notification import Notification
    notifications = [o for o in fake_db.added if isinstance(o, Notification)]
    assert len(notifications) == 1
    assert notifications[0].conseiller_username == "alice"


def test_upload_document_prospect_type_non_autorise_rejete(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/documents",
            params={"type_document": "cni"},
            files={"fichier": ("cni.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 422


def test_upload_document_prospect_refuse_si_non_autorise_par_le_token(api_client, fake_db):
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect(peut_uploader_docs=False))):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/documents",
            params={"type_document": "facture"},
            files={"fichier": ("facture.pdf", b"%PDF-1.4 contenu factice", "application/pdf")},
        )

    assert reponse.status_code == 403


def test_speedtest_fait_vrai_si_debit_mesure_sur_un_contrat_seulement(api_client, fake_db):
    # Le conseiller a saisi le débit mesuré directement sur la ligne (via
    # ContratForm.tsx) sans que ça remonte sur Prospect.speed_down — le lien
    # ne doit pas redemander un test déjà disponible (item #7).
    contrat_avec_debit = Contrat(
        id=9, prospect_id=1, categorie="Forfait box", chez_nous=False, speed_down=180.0,
    )
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont")
    fake_db.queue_result([])  # aucun DocumentProspect déjà transmis
    fake_db.queue_result([contrat_avec_debit])  # _debit_deja_mesure_sur_un_contrat
    fake_db.queue_result([])  # contrat_situation

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.get(f"/portail/{'p' * 32}")

    assert reponse.json()["speedtest_fait"] is True


def test_contexte_token_prospect_expose_peut_renseigner_situation(api_client, fake_db):
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont")
    fake_db.queue_result([])

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.get(f"/portail/{'p' * 32}")

    corps = reponse.json()
    assert corps["peut_renseigner_situation"] is True
    assert corps["situation_renseignee"] is False


def test_renseigner_situation_actuelle_met_a_jour_le_prospect(api_client, fake_db):
    # Champs rattachés au contrat concurrent (chez_nous=False) du prospect
    # plutôt qu'aux colonnes Prospect — voir migration 0040. Le contrat
    # existant est renvoyé deux fois : une fois pour le lookup fait par
    # _contrat_situation_actuelle_prospect (mis à jour en place), une fois
    # pour le recalcul de situation_renseignee dans _contexte_token_prospect.
    contrat_existant = Contrat(id=5, prospect_id=1, categorie="Forfait mobile", chez_nous=False)
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont")
    fake_db.queue_result([contrat_existant])
    fake_db.queue_result([])  # documents déjà transmis, relus par _contexte_token_prospect
    fake_db.queue_result([])  # _debit_deja_mesure_sur_un_contrat : aucun débit mesuré sur un contrat
    fake_db.queue_result([contrat_existant])

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/situation",
            json={
                "operateur_actuel": "Orange",
                "satisfaction_reseau": "😐 Ça va",
                "veut_rester": "Non",
                "defaut_technique": "Moyen",
            },
        )

    assert reponse.status_code == 200
    assert contrat_existant.fournisseur == "Orange"
    assert contrat_existant.veut_rester == "Non"
    corps = reponse.json()
    assert corps["situation_renseignee"] is True


def test_renseigner_situation_actuelle_avec_categorie_cree_la_ligne_correspondante(api_client, fake_db):
    # Ligne "montant exact" par univers (documents/page.tsx) : sans contrat_id,
    # une categorie inconnue jusque-là doit créer la ligne concurrente
    # correspondante plutôt que de retomber sur le défaut mobile.
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont")
    fake_db.queue_result([])  # aucune ligne "Énergie électricité" existante -> création
    fake_db.queue_result([])  # documents déjà transmis, relus par _contexte_token_prospect
    fake_db.queue_result([])  # _debit_deja_mesure_sur_un_contrat
    fake_db.queue_result([])  # contrat_situation (categorie énergie hors CATEGORIES_CONTRAT_TELECOM)

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/situation",
            json={"categorie": "Énergie électricité", "cout_mensuel": 89.5},
        )

    assert reponse.status_code == 200
    nouveaux_contrats = [o for o in fake_db.added if isinstance(o, Contrat)]
    assert len(nouveaux_contrats) == 1
    assert nouveaux_contrats[0].categorie == "Énergie électricité"
    assert nouveaux_contrats[0].cout_mensuel == 89.5
    assert nouveaux_contrats[0].chez_nous is False


def test_renseigner_situation_actuelle_notifie_le_conseiller_createur(api_client, fake_db):
    contrat_existant = Contrat(id=5, prospect_id=1, categorie="Forfait mobile", chez_nous=False)
    utilisateur_fake = type("U", (), {"username": "alice", "nom_complet": "Alice Martin"})()
    fake_db.get_map[(Prospect, 1)] = Prospect(id=1, prenom="Jean", nom="Dupont", cree_par="Alice Martin")
    fake_db.queue_result([contrat_existant])  # _contrat_situation_actuelle_prospect
    # creer_notification_prospect (appelé juste après le commit, avant
    # _contexte_token_prospect) : résolution de l'utilisateur via User.nom_complet
    fake_db.queue_result([utilisateur_fake])
    fake_db.queue_result([])  # documents déjà transmis
    fake_db.queue_result([])  # _debit_deja_mesure_sur_un_contrat
    fake_db.queue_result([contrat_existant])  # contrat_situation

    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=_token_prospect())):
        reponse = api_client.post(
            f"/portail/{'p' * 32}/situation",
            json={"operateur_actuel": "Orange"},
        )

    assert reponse.status_code == 200
    from backend.models.notification import Notification
    notifications = [o for o in fake_db.added if isinstance(o, Notification)]
    assert len(notifications) == 1
    assert notifications[0].conseiller_username == "alice"
    assert "Jean" in notifications[0].message


def test_renseigner_situation_actuelle_refuse_sur_lien_client(api_client, fake_db):
    token_client = TokenPublic(
        id=2, token="c" * 32, client_id=1, prospect_id=None,
        peut_uploader_docs=True, peut_signer_mandat=False,
        peut_voir_suivi=False, peut_renseigner_demarches=False,
        peut_transmettre_speedtest=False,
    )
    with patch("backend.routers.portail_public.token_engine.valider_token",
               new=AsyncMock(return_value=token_client)):
        reponse = api_client.post(
            f"/portail/{'c' * 32}/situation",
            json={"operateur_actuel": "Orange"},
        )

    assert reponse.status_code == 403
