# ==============================================================================
#  TESTS — backend/services/catalogue_engine.py : normalisation/hash (fonctions
#  pures) et extraction LLM (client Anthropic mocké, aucun appel réseau réel).
#  Même idiome que backend/tests/test_facture_analyzer.py.
# ==============================================================================
from backend.core.config import settings
from backend.services import catalogue_engine


# ------------------------------------------------------------------------------
#  normaliser_offre() / hash_contenu()
# ------------------------------------------------------------------------------
def test_normaliser_offre_reconnait_categorie_et_fournisseur_canoniques():
    brute = {"fournisseur": "free", "nom_offre": "Forfait 5G", "categorie": "mobile", "prix_mensuel": 19.99}
    source = {"univers": "Télécom", "categorie": "Mobile"}

    offre = catalogue_engine.normaliser_offre(brute, source)

    assert offre["fournisseur"] == "Free"
    assert offre["categorie"] == "Mobile"
    assert offre["univers"] == "Télécom"
    assert offre["prix_mensuel"] == 19.99


def test_normaliser_offre_conserve_libelle_brut_si_aucune_correspondance():
    brute = {"fournisseur": "Opérateur Inconnu SAS", "nom_offre": "Offre X", "categorie": "Mobile"}
    source = {"univers": "Télécom", "categorie": "Mobile"}

    offre = catalogue_engine.normaliser_offre(brute, source)

    assert offre["fournisseur"] == "Opérateur Inconnu SAS"


def test_normaliser_offre_prix_manquant_reste_none():
    brute = {"fournisseur": "Free", "nom_offre": "Forfait X", "prix_mensuel": None}
    source = {"univers": "Télécom", "categorie": "Mobile"}

    offre = catalogue_engine.normaliser_offre(brute, source)

    assert offre["prix_mensuel"] is None


def test_hash_contenu_stable_et_sensible_au_prix():
    offre1 = {"fournisseur": "Free", "nom_offre": "Forfait 5G", "prix_mensuel": 19.99, "engagement_mois": 0}
    offre2 = dict(offre1)
    offre3 = {**offre1, "prix_mensuel": 24.99}

    assert catalogue_engine.hash_contenu(offre1) == catalogue_engine.hash_contenu(offre2)
    assert catalogue_engine.hash_contenu(offre1) != catalogue_engine.hash_contenu(offre3)


def test_hash_contenu_insensible_a_la_casse_et_aux_accents():
    offre_a = {"fournisseur": "Free", "nom_offre": "Forfait Été", "prix_mensuel": 10.0, "engagement_mois": 0}
    offre_b = {"fournisseur": "FREE", "nom_offre": "forfait ete", "prix_mensuel": 10.0, "engagement_mois": 0}

    assert catalogue_engine.hash_contenu(offre_a) == catalogue_engine.hash_contenu(offre_b)


# ------------------------------------------------------------------------------
#  html_vers_texte()
# ------------------------------------------------------------------------------
def test_html_vers_texte_retire_scripts_et_balises():
    html = "<html><head><script>alert(1)</script></head><body><p>19,99 €/mois</p></body></html>"
    texte = catalogue_engine.html_vers_texte(html)
    assert "alert" not in texte
    assert "19,99 €/mois" in texte


# ------------------------------------------------------------------------------
#  extraire_offres_llm() — client Anthropic mocké
# ------------------------------------------------------------------------------
class FakeToolUseBlock:
    def __init__(self, name, input_):
        self.type = "tool_use"
        self.name = name
        self.input = input_


class FakeResponse:
    def __init__(self, offres):
        self.content = [FakeToolUseBlock("soumettre_offres", {"offres": offres})]


class FakeMessages:
    def __init__(self, offres):
        self._offres = offres

    def create(self, **kwargs):
        return FakeResponse(self._offres)


class FakeAnthropicClient:
    def __init__(self, offres):
        self.messages = FakeMessages(offres)


def test_extraire_offres_llm_renvoie_liste_du_tool_use(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")
    offres_attendues = [{"fournisseur": "Free", "nom_offre": "Forfait 5G", "prix_mensuel": 19.99}]
    monkeypatch.setattr(catalogue_engine.anthropic, "Anthropic", lambda api_key: FakeAnthropicClient(offres_attendues))

    resultat = catalogue_engine.extraire_offres_llm("texte de la page", {"univers": "Télécom", "categorie": "Mobile"})

    assert resultat == offres_attendues


def test_extraire_offres_llm_sans_cle_renvoie_liste_vide(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    resultat = catalogue_engine.extraire_offres_llm("texte", {"univers": "Télécom"})
    assert resultat == []


def test_extraire_offres_llm_echec_reseau_renvoie_liste_vide(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "fake-key")

    class ClientEnErreur:
        class messages:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("réseau indisponible")

    monkeypatch.setattr(catalogue_engine.anthropic, "Anthropic", lambda api_key: ClientEnErreur())

    resultat = catalogue_engine.extraire_offres_llm("texte", {"univers": "Télécom"})
    assert resultat == []
