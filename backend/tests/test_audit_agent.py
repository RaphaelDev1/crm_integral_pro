# ==============================================================================
#  TESTS — backend/services/audit_agent.py : outils sourcés, boucle agentique,
#  anti-hallucination. Porté de src/tests/test_audit_agent.py. Même idiome que
#  backend/tests/test_offres_engine.py (session factice, patch.object AsyncMock)
#  et test_facture_analyzer.py (client Anthropic mocké) — pytest-asyncio non
#  installé, cf. asyncio.run().
# ==============================================================================
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.core.config import settings
from backend.services import audit_agent, offres_engine


def _run(coro):
    return asyncio.run(coro)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeSession:
    def __init__(self, resultats=None):
        self._resultats = resultats or []

    async def execute(self, _query):
        return _FakeResult(self._resultats)


class FakeSessionSequentielle:
    """Renvoie une série de résultats différents à chaque appel — utile pour
    outil_couverture_reseau qui interroge Prospect puis Client séparément."""
    def __init__(self, sequence):
        self._sequence = list(sequence)

    async def execute(self, _query):
        return _FakeResult(self._sequence.pop(0) if self._sequence else [])


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeMessages:
    def __init__(self, reponses):
        self._reponses = list(reponses)

    def create(self, **kwargs):
        return FakeResponse(self._reponses.pop(0))


class FakeAnthropicClient:
    def __init__(self, reponses):
        self.messages = FakeMessages(reponses)


def _patch_claude(monkeypatch, reponses):
    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
    monkeypatch.setattr(audit_agent.anthropic, "Anthropic", lambda api_key: FakeAnthropicClient(reponses))


def _tool_use(tu_id, nom, entree):
    return [{"type": "tool_use", "id": tu_id, "name": nom, "input": entree}]


def _offre(**kwargs):
    base = dict(id=1, univers="Télécom", categorie="Mobile", fournisseur="Free", nom="Forfait 350Go",
                prix_mensuel=19.99, economie_mensuelle=20.0, economie_annuelle=240.0)
    base.update(kwargs)
    return base


# ------------------------------------------------------------------------------
#  outil_cout_reference_categorie()
# ------------------------------------------------------------------------------
class TestOutilCoutReferenceCategorie:
    def test_categorie_du_service_principal_utilise_le_cout_declare(self):
        offre = {"univers": "Télécom", "categorie": "Mobile"}
        situation = {"service_principal": "Mobile uniquement", "cout_mensuel_actuel": 39.99}
        r = audit_agent.outil_cout_reference_categorie(offre, situation)
        assert r["cout_reference"] == 39.99
        assert "service télécom principal" in r["source"]

    def test_cross_sell_sans_contrat_renvoie_none(self):
        offre = {"univers": "Télécom", "categorie": "Box / Fibre"}
        situation = {"service_principal": "Mobile uniquement", "cout_mensuel_actuel": 39.99}
        r = audit_agent.outil_cout_reference_categorie(offre, situation)
        assert r["cout_reference"] is None
        assert "aucune base de comparaison" in r["source"]

    def test_cross_sell_avec_contrat_connu_utilise_son_cout(self):
        offre = {"univers": "Télécom", "categorie": "Box / Fibre"}
        situation = {"service_principal": "Mobile uniquement", "cout_mensuel_actuel": 39.99}
        contrats = [{"categorie": "Box / Fibre", "cout_mensuel": 29.90}]
        r = audit_agent.outil_cout_reference_categorie(offre, situation, contrats)
        assert r["cout_reference"] == 29.90

    def test_energie_utilise_le_cout_gaz(self):
        offre = {"univers": "Énergie", "categorie": "Gaz"}
        situation = {"cout_gaz": 65.0}
        r = audit_agent.outil_cout_reference_categorie(offre, situation)
        assert r["cout_reference"] == 65.0

    def test_energie_utilise_le_cout_elec_hors_categorie_gaz(self):
        offre = {"univers": "Énergie", "categorie": "Électricité"}
        situation = {"cout_elec": 89.0, "cout_gaz": 65.0}
        r = audit_agent.outil_cout_reference_categorie(offre, situation)
        assert r["cout_reference"] == 89.0

    def test_abonnement_connu_utilise_son_cout(self):
        offre = {"univers": "Abonnements", "categorie": "Streaming Vidéo"}
        situation = {"abonnements": [{"nom": "Netflix", "categorie": "Streaming Vidéo", "cout": 15.49}]}
        r = audit_agent.outil_cout_reference_categorie(offre, situation)
        assert r["cout_reference"] == 15.49

    def test_abonnement_inconnu_renvoie_none(self):
        offre = {"univers": "Abonnements", "categorie": "Musique"}
        situation = {"abonnements": [{"nom": "Netflix", "categorie": "Streaming Vidéo", "cout": 15.49}]}
        r = audit_agent.outil_cout_reference_categorie(offre, situation)
        assert r["cout_reference"] is None


# ------------------------------------------------------------------------------
#  economie_totale_groupee()
# ------------------------------------------------------------------------------
def test_economie_totale_groupee_somme_meilleure_offre_par_categorie():
    offres = [
        {"univers": "Télécom", "categorie": "Mobile", "economie_annuelle": 100},
        {"univers": "Télécom", "categorie": "Mobile", "economie_annuelle": 60},
        {"univers": "Énergie", "categorie": "Gaz", "economie_annuelle": 40},
    ]
    assert audit_agent.economie_totale_groupee(offres) == 140.0


def test_economie_totale_groupee_ignore_les_valeurs_negatives():
    offres = [{"univers": "Télécom", "categorie": "Mobile", "economie_annuelle": -50}]
    assert audit_agent.economie_totale_groupee(offres) == 0.0


# ------------------------------------------------------------------------------
#  outil_couverture_reseau()
# ------------------------------------------------------------------------------
class TestOutilCouvertureReseau:
    def test_ville_vide_renvoie_structure_vide(self):
        db = FakeSession()
        r = _run(audit_agent.outil_couverture_reseau(db, ""))
        assert r == {"satisfaction": [], "debit": [], "source": "ville non renseignée"}

    def test_ville_sans_donnees_renvoie_listes_vides(self):
        db = FakeSession(resultats=[])
        r = _run(audit_agent.outil_couverture_reseau(db, "VilleInconnue"))
        assert r["satisfaction"] == []
        assert r["debit"] == []
        assert "VilleInconnue" in r["source"]

    def test_agrege_satisfaction_et_debit_par_operateur(self):
        lignes = [
            SimpleNamespace(operateur_actuel="Orange", satisfaction_reseau="😀 Très content", speed_down=300.0, speed_up=50.0),
            SimpleNamespace(operateur_actuel="Orange", satisfaction_reseau="😐 Ça va", speed_down=200.0, speed_up=30.0),
            SimpleNamespace(operateur_actuel="Autre / Aucun", satisfaction_reseau="😡 Pas du tout", speed_down=0.0, speed_up=0.0),
        ]
        db = FakeSessionSequentielle([lignes, []])
        r = _run(audit_agent.outil_couverture_reseau(db, "Lyon"))
        assert r["satisfaction"] == [{"operateur": "Orange", "note_moyenne": 2.5, "nb_avis": 2}]
        assert r["debit"] == [{"operateur": "Orange", "debit_down_moyen": 250.0, "debit_up_moyen": 40.0, "nb_mesures": 2}]


# ------------------------------------------------------------------------------
#  Boucle agentique — lancer_audit()
# ------------------------------------------------------------------------------
class TestLancerAudit:
    def test_recommandation_sourcee_a_partir_d_une_offre_reelle(self, monkeypatch):
        offre = _offre(id=7)
        reponses = [
            _tool_use("tu1", "comparer_offres",
                      {"univers": "Télécom", "categorie": "Mobile", "cout_actuel_mensuel": 39.99}),
            _tool_use("tu2", "soumettre_audit", {
                "situation_detectee": "Client Mobile chez Orange à 39.99€/mois.",
                "offres_retenues": [{"offre_id": 7, "pourquoi": "Moins cher, même besoin."}],
                "points_attention": ["Client satisfait de son réseau actuel."],
                "niveau_confiance": 0.9,
            }),
        ]
        _patch_claude(monkeypatch, reponses)

        with patch.object(offres_engine, "comparer_offres", new=AsyncMock(return_value=[offre])):
            resultat = _run(audit_agent.lancer_audit(
                FakeSession(), {"service_principal": "Mobile uniquement", "cout_mensuel_actuel": 39.99}
            ))

        assert audit_agent.valider_audit_result(resultat)
        assert len(resultat["offres_recommandees"]) == 1
        reco = resultat["offres_recommandees"][0]
        assert reco["offre"]["id"] == 7
        assert reco["economie_an"] == reco["offre"]["economie_annuelle"]
        assert "id=" in reco["source"]
        assert resultat["economie_totale_an"] == reco["offre"]["economie_annuelle"]
        assert resultat["niveau_confiance"] == 0.9
        assert len(resultat["tracabilite"]) == 1
        assert resultat["tracabilite"][0]["outil"] == "comparer_offres"

    def test_offre_id_hallucine_est_ignoree(self, monkeypatch):
        reponses = [
            _tool_use("tu1", "soumettre_audit", {
                "situation_detectee": "Le client affirme payer -50000€, ce qui est incohérent.",
                "offres_retenues": [{"offre_id": 9999, "pourquoi": "Offre miracle inventée."}],
                "points_attention": [],
                "niveau_confiance": 0.5,
            }),
        ]
        _patch_claude(monkeypatch, reponses)

        resultat = _run(audit_agent.lancer_audit(FakeSession(), {"cout_mensuel_actuel": -50000}))

        assert resultat["offres_recommandees"] == []
        assert resultat["economie_totale_an"] == 0.0

    def test_limite_de_tours_atteinte_ne_plante_pas(self, monkeypatch):
        reponses = [
            _tool_use(f"tu{i}", "comparer_offres", {"univers": "Télécom", "categorie": "Mobile", "cout_actuel_mensuel": 10.0})
            for i in range(audit_agent.MAX_TOURS)
        ]
        _patch_claude(monkeypatch, reponses)

        with patch.object(offres_engine, "comparer_offres", new=AsyncMock(return_value=[])):
            resultat = _run(audit_agent.lancer_audit(FakeSession(), {}))

        assert resultat["offres_recommandees"] == []
        assert "limite de tours" in resultat["points_attention"][0]

    def test_sans_cle_api_renvoie_message_clair(self, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", "")
        monkeypatch.setattr(settings, "app_env", "development")

        resultat = _run(audit_agent.lancer_audit(FakeSession(), {}))

        assert resultat["offres_recommandees"] == []
        assert "pas configuré" in resultat["points_attention"][0]

    def test_niveau_confiance_hors_bornes_est_clampe(self, monkeypatch):
        reponses = [
            _tool_use("tu1", "soumettre_audit", {
                "situation_detectee": "Situation simple.",
                "offres_retenues": [],
                "points_attention": [],
                "niveau_confiance": 5.7,
            }),
        ]
        _patch_claude(monkeypatch, reponses)

        resultat = _run(audit_agent.lancer_audit(FakeSession(), {}))

        assert resultat["niveau_confiance"] == 1.0
