# ==============================================================================
#  TESTS — backend/routers/leads_public.py (landing publique /economiser).
#  Pattern identique à test_portail_public_prospect.py : FakeSession via
#  app.dependency_overrides[get_db] (pas d'auth, ce router est public), les
#  intégrations externes (estimation, Slack/SMS, Twilio Lookup, IP, fibre,
#  Turnstile) sont patchées pour isoler la logique du router.
# ==============================================================================
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.core.database import get_db
from backend.core.rate_limit import limiter
from backend.main import app
from backend.models.prospect import Prospect
from backend.services.estimation_publique import Estimation, LigneEstimation
from backend.services.eligibilite_fibre import ResultatFibre
from backend.services.geo_ip import ResultatGeoIp


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Le limiter slowapi est une instance module-level partagée par tout le
    process de test (storage mémoire) — la réinitialiser avant chaque test
    évite qu'un test pollue le quota des suivants (même clé `get_remote_address`
    pour toutes les requêtes de TestClient)."""
    limiter.reset()
    yield
    limiter.reset()


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value


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

    async def flush(self):
        pass

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


def _estimation_factice() -> Estimation:
    return Estimation(
        lignes=[
            LigneEstimation(
                categorie="Mobile", cout_actuel_mensuel=30.0, notre_moyenne_mensuel=15.0,
                economie_mensuelle_basse=10.0, economie_mensuelle_haute=20.0,
                economie_annuelle_typique=180.0, source="marche_public", echantillon=0,
            ),
        ],
        economie_annuelle_totale_basse=120.0,
        economie_annuelle_totale_haute=240.0,
        economie_annuelle_totale_typique=180.0,
        calculee_le="2026-08-26T10:00:00Z",
    )


def _payload_valide(**overrides) -> dict:
    base = {
        "prenom": "Jean",
        "telephone": "0612345678",
        "email": "jean@example.com",
        "depenses": {"mobile": 30},
        "consentement_rgpd": True,
        "consentement_demarchage": False,
        "hp_field": "",
    }
    base.update(overrides)
    return base


def _patches_defaut():
    """Isole toutes les intégrations externes du chemin nominal — chaque test
    peut surcharger un patch précis en l'ajoutant après cette liste."""
    return [
        patch("backend.routers.leads_public.estimation_publique.estimer", new=AsyncMock(return_value=_estimation_factice())),
        patch("backend.routers.leads_public.eligibilite_fibre.verifier", new=AsyncMock(return_value=ResultatFibre())),
        patch("backend.routers.leads_public.audit_engine.enregistrer_action", new=AsyncMock()),
        patch("backend.routers.leads_public.captcha.verifier", new=AsyncMock(return_value=True)),
        patch("backend.routers.leads_public._enrichir_lead_arriere_plan", new=AsyncMock()),
        patch("backend.routers.leads_public._declencher_sequence_relance"),
    ]


def test_capture_lead_nominal_cree_un_prospect_chaud(api_client, fake_db):
    patches = _patches_defaut()
    for p in patches:
        p.start()
    try:
        reponse = api_client.post("/public/leads/capture", json=_payload_valide())
    finally:
        for p in patches:
            p.stop()

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["ok"] is True
    assert corps["ref"].startswith("L-")
    assert corps["fibre"] == {"disponible": None, "taux_couverture": None}

    prospects = [o for o in fake_db.added if isinstance(o, Prospect)]
    assert len(prospects) == 1
    assert prospects[0].score == 200.0
    assert prospects[0].statut == "À relancer"
    assert prospects[0].origine == "Landing direct"


def test_capture_lead_honeypot_rempli_ne_cree_rien(api_client, fake_db):
    patches = _patches_defaut()
    for p in patches:
        p.start()
    try:
        reponse = api_client.post("/public/leads/capture", json=_payload_valide(hp_field="je-suis-un-bot"))
    finally:
        for p in patches:
            p.stop()

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["ref"] == "honeypot"
    assert fake_db.added == []


def test_capture_lead_sans_consentement_rgpd_est_rejete(api_client, fake_db):
    reponse = api_client.post("/public/leads/capture", json=_payload_valide(consentement_rgpd=False))
    assert reponse.status_code == 422
    assert fake_db.added == []


def test_capture_lead_turnstile_invalide_est_rejete(api_client, fake_db):
    with patch("backend.routers.leads_public.estimation_publique.estimer", new=AsyncMock(return_value=_estimation_factice())), \
         patch("backend.routers.leads_public.eligibilite_fibre.verifier", new=AsyncMock(return_value=ResultatFibre())), \
         patch("backend.routers.leads_public.audit_engine.enregistrer_action", new=AsyncMock()), \
         patch("backend.routers.leads_public.captcha.verifier", new=AsyncMock(return_value=False)), \
         patch("backend.routers.leads_public._enrichir_lead_arriere_plan", new=AsyncMock()), \
         patch("backend.routers.leads_public._declencher_sequence_relance"):
        reponse = api_client.post(
            "/public/leads/capture", json=_payload_valide(turnstile_token="token-invalide")
        )

    assert reponse.status_code == 422
    assert fake_db.added == []


def test_capture_lead_avec_adresse_interroge_la_fibre(api_client, fake_db):
    with patch("backend.routers.leads_public.estimation_publique.estimer", new=AsyncMock(return_value=_estimation_factice())), \
         patch("backend.routers.leads_public.eligibilite_fibre.verifier", new=AsyncMock(
             return_value=ResultatFibre(disponible=True, taux_couverture=0.82))) as mock_fibre, \
         patch("backend.routers.leads_public.audit_engine.enregistrer_action", new=AsyncMock()), \
         patch("backend.routers.leads_public.captcha.verifier", new=AsyncMock(return_value=True)), \
         patch("backend.routers.leads_public._enrichir_lead_arriere_plan", new=AsyncMock()), \
         patch("backend.routers.leads_public._declencher_sequence_relance"):
        reponse = api_client.post(
            "/public/leads/capture",
            json=_payload_valide(adresse_selection={"code_insee": "75056", "label": "Paris"}),
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["fibre"] == {"disponible": True, "taux_couverture": 0.82}
    mock_fibre.assert_awaited_once_with("75056")

    prospects = [o for o in fake_db.added if isinstance(o, Prospect)]
    assert prospects[0].code_insee == "75056"
    assert prospects[0].fibre_disponible is True


def test_methodologie_reste_accessible(api_client, fake_db):
    fake_db.queue_result([])
    reponse = api_client.get("/public/leads/methodologie")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert "principe" in corps
    assert "fourchette" in corps


def test_adresse_autocomplete_proxy_ban(api_client):
    payload_ban = {
        "features": [
            {
                "properties": {"label": "1 Rue de Paris 75001 Paris", "postcode": "75001", "city": "Paris", "citycode": "75101"},
                "geometry": {"coordinates": [2.34, 48.86]},
            }
        ]
    }

    class _FakeHttpResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload_ban

    class _FakeHttpClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            return _FakeHttpResponse()

    with patch("backend.routers.leads_public.httpx.AsyncClient", return_value=_FakeHttpClient()):
        reponse = api_client.get("/public/leads/adresse-autocomplete", params={"q": "1 rue de paris"})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert len(corps) == 1
    assert corps[0]["code_insee"] == "75101"


def test_adresse_autocomplete_requete_trop_courte_renvoie_liste_vide(api_client):
    reponse = api_client.get("/public/leads/adresse-autocomplete", params={"q": "a"})
    assert reponse.status_code == 200
    assert reponse.json() == []


def test_detecter_fai_renvoie_operateur_probable(api_client):
    with patch("backend.routers.leads_public.geo_ip.detecter", new=AsyncMock(
            return_value=ResultatGeoIp(organisation="Orange SA", operateur_probable="Orange"))):
        reponse = api_client.get("/public/leads/detecter-fai")

    assert reponse.status_code == 200
    assert reponse.json() == {"operateur_probable": "Orange"}


def test_telephone_verification_e164_et_fail_open():
    import asyncio

    from backend.services import telephone_verification

    assert telephone_verification._vers_e164("0612345678") == "+33612345678"
    assert telephone_verification._vers_e164("+33612345678") == "+33612345678"

    # Pas de credentials Twilio dans l'environnement de test -> fail-open (None).
    resultat = asyncio.run(telephone_verification.verifier("0612345678"))
    assert resultat.verifie is None


def test_capture_lead_rate_limit_quotidien_renvoie_429(api_client, fake_db):
    patches = _patches_defaut()
    for p in patches:
        p.start()
    try:
        # LIMITE_MINUTE = "10/minute" — la 11e requête dans la même minute
        # depuis la même IP (get_remote_address -> "testclient" pour TestClient)
        # doit être rejetée avec le message français existant.
        for _ in range(10):
            reponse = api_client.post("/public/leads/capture", json=_payload_valide())
            assert reponse.status_code == 200
        reponse = api_client.post("/public/leads/capture", json=_payload_valide())
    finally:
        for p in patches:
            p.stop()

    assert reponse.status_code == 429
    assert reponse.json()["detail"] == "Trop de requêtes, réessayez dans 1 minute."
