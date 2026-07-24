# ==============================================================================
#  TESTS — facture_analyzer.py (extraction structurée via Claude Haiku).
#  Le client Anthropic est mocké : aucun appel réseau réel n'est effectué.
# ==============================================================================
import json

import pytest

from backend.core.config import settings
from backend.services import facture_analyzer


class FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, texte: str):
        self.content = [FakeTextBlock(texte)]


class FakeMessages:
    def __init__(self, texte: str):
        self._texte = texte
        self.dernier_appel: dict | None = None

    def create(self, **kwargs):
        self.dernier_appel = kwargs
        return FakeResponse(self._texte)


class FakeAnthropicClient:
    def __init__(self, texte: str):
        self.messages = FakeMessages(texte)


def _patch_claude(monkeypatch, payload: dict | None = None, texte: str | None = None) -> FakeAnthropicClient:
    """Redirige facture_analyzer.anthropic.Anthropic vers un faux client qui
    renvoie soit le JSON de `payload`, soit le texte brut `texte` (pour tester
    les réponses malformées)."""
    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
    corps = texte if texte is not None else json.dumps(payload)
    fake_client = FakeAnthropicClient(corps)
    monkeypatch.setattr(facture_analyzer.anthropic, "Anthropic", lambda api_key: fake_client)
    return fake_client


# ------------------------------------------------------------------------------
#  3 fixtures de factures anonymisées (mobile, box/fibre, énergie). Le contenu
#  binaire est factice : facture_analyzer envoie le fichier tel quel à Claude
#  vision (mocké dans ces tests), il n'y a pas de parsing PDF côté Python.
# ------------------------------------------------------------------------------
@pytest.fixture
def facture_mobile_pdf(tmp_path):
    chemin = tmp_path / "facture_mobile_anonymisee.pdf"
    chemin.write_bytes(b"%PDF-1.4 FACTURE ORANGE FORFAIT 5G 150GO ENGAGEMENT 12 MOIS")
    return chemin


@pytest.fixture
def facture_box_pdf(tmp_path):
    chemin = tmp_path / "facture_box_anonymisee.pdf"
    chemin.write_bytes(b"%PDF-1.4 FACTURE SFR BOX FIBRE SANS ENGAGEMENT")
    return chemin


@pytest.fixture
def facture_energie_pdf(tmp_path):
    chemin = tmp_path / "facture_energie_anonymisee.pdf"
    chemin.write_bytes(b"%PDF-1.4 FACTURE EDF ABONNEMENT CONSOMMATION")
    return chemin


class TestExtractionParUnivers:
    def test_facture_mobile_avec_engagement(self, facture_mobile_pdf, monkeypatch):
        fake_client = _patch_claude(monkeypatch, {
            "operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99,
            "data_conso_go": 150.0, "options": ["Appels illimités", "Cloud 100 Go"],
            "engagement_mois": 12, "date_fin_engagement": "15/03/2027",
            "iban_prelevement": "FR7630001007941234567890185",
        })
        res = facture_analyzer.analyser_facture(facture_mobile_pdf)

        assert res == {
            "operateur": "Orange", "prix_ht": 38.33, "prix_ttc": 45.99,
            "data_conso_go": 150.0, "options": ["Appels illimités", "Cloud 100 Go"],
            "engagement_mois": 12, "date_fin_engagement": "15/03/2027",
            "iban_prelevement": "FR7630001007941234567890185",
        }
        # Le prompt système (avec ses exemples few-shot) doit bien être transmis.
        assert "few-shot" not in fake_client.messages.dernier_appel["system"]  # pas de méta-texte qui fuite
        assert "JSON" in fake_client.messages.dernier_appel["system"]

    def test_facture_box_sans_engagement(self, facture_box_pdf, monkeypatch):
        _patch_claude(monkeypatch, {
            "operateur": "SFR", "prix_ht": 27.49, "prix_ttc": 32.99,
            "data_conso_go": 0.0, "options": ["Fibre 1Gb/s", "TV incluse"],
            "engagement_mois": 0, "date_fin_engagement": "",
            "iban_prelevement": "",
        })
        res = facture_analyzer.analyser_facture(facture_box_pdf)

        assert res["operateur"] == "SFR"
        assert res["engagement_mois"] == 0
        assert res["data_conso_go"] == 0.0
        assert res["options"] == ["Fibre 1Gb/s", "TV incluse"]

    def test_facture_energie_normalise_types_texte_en_nombres(self, facture_energie_pdf, monkeypatch):
        # Le modèle répond parfois des nombres sous forme de chaîne ("89,00")
        # ou omet des clés — la normalisation doit rester robuste.
        _patch_claude(monkeypatch, {
            "operateur": "EDF", "prix_ht": "", "prix_ttc": "89,00",
            "data_conso_go": None, "options": None,
            "engagement_mois": None, "date_fin_engagement": None,
            "iban_prelevement": None,
        })
        res = facture_analyzer.analyser_facture(facture_energie_pdf)

        assert res["operateur"] == "EDF"
        assert res["prix_ht"] == 0.0
        assert res["prix_ttc"] == 89.0
        assert res["data_conso_go"] == 0.0
        assert res["options"] == []
        assert res["engagement_mois"] == 0
        assert res["date_fin_engagement"] == ""
        assert res["iban_prelevement"] == ""


class TestParsingReponse:
    def test_reponse_entouree_de_balises_markdown(self, facture_mobile_pdf, monkeypatch):
        payload = {
            "operateur": "Free", "prix_ht": 16.66, "prix_ttc": 19.99,
            "data_conso_go": 350.0, "options": [], "engagement_mois": 0,
            "date_fin_engagement": "", "iban_prelevement": "",
        }
        _patch_claude(monkeypatch, texte=f"```json\n{json.dumps(payload)}\n```")
        res = facture_analyzer.analyser_facture(facture_mobile_pdf)
        assert res["operateur"] == "Free"
        assert res["prix_ttc"] == 19.99


class TestGestionErreurs:
    def test_fichier_introuvable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(tmp_path / "absent.pdf")

    def test_extension_non_pdf_rejetee(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
        chemin = tmp_path / "facture.jpg"
        chemin.write_bytes(b"donnees-image")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(chemin)

    def test_fichier_vide(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
        chemin = tmp_path / "facture_vide.pdf"
        chemin.write_bytes(b"")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(chemin)

    def test_sans_cle_api(self, facture_mobile_pdf, monkeypatch):
        monkeypatch.setattr(settings, "anthropic_api_key", "")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(facture_mobile_pdf)

    def test_reponse_json_invalide(self, facture_mobile_pdf, monkeypatch):
        _patch_claude(monkeypatch, texte="Désolé, je ne peux pas analyser ce document.")
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(facture_mobile_pdf)

    def test_erreur_api_anthropic_est_convertie(self, facture_mobile_pdf, monkeypatch):
        import anthropic

        class ClientEnErreur:
            class messages:
                @staticmethod
                def create(**kwargs):
                    raise anthropic.APIConnectionError(request=None)

        monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
        monkeypatch.setattr(facture_analyzer.anthropic, "Anthropic", lambda api_key: ClientEnErreur())
        with pytest.raises(facture_analyzer.FactureAnalyzerError):
            facture_analyzer.analyser_facture(facture_mobile_pdf)
