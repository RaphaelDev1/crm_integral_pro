# ==============================================================================
#  TESTS — audit_agent.py : outils sourcés, boucle agentique, anti-hallucination
# ==============================================================================
import audit_agent
from offres_engine import ajouter_offre, lire_offres


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
    monkeypatch.setattr(audit_agent, "ANTHROPIC_OK", True)
    monkeypatch.setattr(audit_agent.secrets_config, "anthropic_api_key", lambda: "fake-key")
    monkeypatch.setattr(
        audit_agent.anthropic, "Anthropic", lambda api_key: FakeAnthropicClient(reponses)
    )


def _tool_use(tu_id, nom, entree):
    return [{"type": "tool_use", "id": tu_id, "name": nom, "input": entree}]


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

    def test_energie_utilise_le_cout_gaz(self):
        offre = {"univers": "Énergie", "categorie": "Gaz"}
        situation = {"cout_gaz": 65.0}
        r = audit_agent.outil_cout_reference_categorie(offre, situation)
        assert r["cout_reference"] == 65.0


class TestOutilCalculEconomie:
    def test_somme_par_meilleure_offre_et_categorie(self):
        offres = [
            {"univers": "Télécom", "categorie": "Mobile", "economie_annuelle": 100},
            {"univers": "Télécom", "categorie": "Mobile", "economie_annuelle": 60},
            {"univers": "Énergie", "categorie": "Gaz", "economie_annuelle": 40},
        ]
        r = audit_agent.outil_calcul_economie(offres)
        assert r["economie_totale_an"] == 140.0
        assert "economie_totale_groupee" in r["source"]


class TestOutilCouvertureReseau:
    def test_ville_vide_renvoie_structure_vide(self, tmp_db):
        r = audit_agent.outil_couverture_reseau("")
        assert r == {"satisfaction": [], "debit": [], "source": "ville non renseignée"}

    def test_ville_sans_donnees_renvoie_listes_vides(self, tmp_db):
        r = audit_agent.outil_couverture_reseau("VilleInconnue")
        assert r["satisfaction"] == []
        assert r["debit"] == []
        assert "VilleInconnue" in r["source"]


class TestOutilComparerOffres:
    def test_offre_reelle_est_sourcee(self, tmp_db):
        ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
                       "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99})
        resultats = audit_agent.outil_comparer_offres("Télécom", "Mobile", 39.99)
        assert len(resultats) == 1
        assert resultats[0]["fournisseur"] == "Free"
        assert f"id={resultats[0]['id']}" in resultats[0]["source"]


class TestLancerAudit:
    def test_recommandation_sourcee_a_partir_d_une_offre_reelle(self, tmp_db, monkeypatch):
        ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
                       "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99})
        offre_id = int(lire_offres(actif_seulement=False).iloc[0]["id"])

        reponses = [
            _tool_use("tu1", "comparer_offres",
                      {"univers": "Télécom", "categorie": "Mobile", "cout_actuel_mensuel": 39.99}),
            _tool_use("tu2", "soumettre_audit", {
                "situation_detectee": "Client Mobile chez Orange à 39.99€/mois.",
                "offres_retenues": [{"offre_id": offre_id, "pourquoi": "Moins cher, même besoin."}],
                "points_attention": ["Client satisfait de son réseau actuel."],
                "niveau_confiance": 0.9,
            }),
        ]
        _patch_claude(monkeypatch, reponses)

        resultat = audit_agent.lancer_audit({"univers_interesse": ["Télécom"], "cout_mensuel_actuel": 39.99})

        assert audit_agent.valider_audit_result(resultat)
        assert len(resultat["offres_recommandees"]) == 1
        reco = resultat["offres_recommandees"][0]
        assert reco["offre"]["id"] == offre_id
        assert reco["economie_an"] == reco["offre"]["economie_annuelle"]
        assert "id=" in reco["source"]
        assert resultat["economie_totale_an"] == reco["offre"]["economie_annuelle"]
        assert resultat["niveau_confiance"] == 0.9
        assert len(resultat["tracabilite"]) == 1
        assert resultat["tracabilite"][0]["outil"] == "comparer_offres"

    def test_offre_id_hallucine_est_ignoree(self, tmp_db, monkeypatch):
        reponses = [
            _tool_use("tu1", "soumettre_audit", {
                "situation_detectee": "Le client affirme payer -50000€, ce qui est incohérent.",
                "offres_retenues": [{"offre_id": 9999, "pourquoi": "Offre miracle inventée."}],
                "points_attention": [],
                "niveau_confiance": 0.5,
            }),
        ]
        _patch_claude(monkeypatch, reponses)

        resultat = audit_agent.lancer_audit({"cout_mensuel_actuel": -50000})

        assert resultat["offres_recommandees"] == []
        assert resultat["economie_totale_an"] == 0.0

    def test_limite_de_tours_atteinte_ne_plante_pas(self, tmp_db, monkeypatch):
        reponses = [
            _tool_use(f"tu{i}", "comparer_offres", {"cout_actuel_mensuel": 10.0})
            for i in range(audit_agent.MAX_TOURS)
        ]
        _patch_claude(monkeypatch, reponses)

        resultat = audit_agent.lancer_audit({})

        assert resultat["offres_recommandees"] == []
        assert "limite de tours" in resultat["points_attention"][0]

    def test_sans_cle_api_renvoie_message_clair(self, tmp_db, monkeypatch):
        monkeypatch.setattr(audit_agent.secrets_config, "anthropic_api_key", lambda: "")

        resultat = audit_agent.lancer_audit({})

        assert resultat["offres_recommandees"] == []
        assert "pas configuré" in resultat["points_attention"][0]

    def test_niveau_confiance_hors_bornes_est_clampe(self, tmp_db, monkeypatch):
        reponses = [
            _tool_use("tu1", "soumettre_audit", {
                "situation_detectee": "Situation simple.",
                "offres_retenues": [],
                "points_attention": [],
                "niveau_confiance": 5.7,
            }),
        ]
        _patch_claude(monkeypatch, reponses)

        resultat = audit_agent.lancer_audit({})

        assert resultat["niveau_confiance"] == 1.0
