# ==============================================================================
#  TESTS — backend/services/souscription_engine.py : garde-fous et logique pure
#  (pas de vrai lancement de navigateur, hors test dédié de résilience de
#  _executer qui simule Playwright). Portage de src/tests/test_souscription_engine.py.
# ==============================================================================
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.services import souscription_engine as se


class FakeClient:
    def __init__(self, **kwargs):
        for cle, val in kwargs.items():
            setattr(self, cle, val)

    # Un vrai Client (ORM) renvoie None pour toute colonne non renseignée à la
    # construction — ce faux objet fait pareil pour les champs non passés en
    # kwargs, plutôt que de lever AttributeError comme le ferait un objet Python
    # nu (évite de devoir mettre à jour chaque test à chaque champ ajouté à
    # construire_donnees_client).
    def __getattr__(self, nom):
        return None


def test_construire_donnees_client_normalise_les_champs():
    client = FakeClient(prenom="Alice", nom="Martin", email="alice@test.fr",
                         telephone="0601020304", adresse="1 rue Test",
                         code_postal="75001", ville="Paris")
    donnees = se.construire_donnees_client(client)
    assert donnees["prenom"] == "Alice"
    assert donnees["ville"] == "Paris"
    assert donnees["civilite"] == ""


def test_construire_donnees_client_tolere_les_champs_absents():
    client = FakeClient(prenom=None, nom=None, email=None, telephone=None,
                         adresse=None, code_postal=None, ville=None)
    donnees = se.construire_donnees_client(client)
    assert all(v == "" for v in donnees.values())


class FakeContrat:
    def __init__(self, **kwargs):
        for cle, val in kwargs.items():
            setattr(self, cle, val)


def test_construire_donnees_client_inclut_portabilite_si_contrat_mobile_fourni():
    """Free Mobile forfait seul : conserver_numero/type_sim pilotent le tunnel
    d'options (_remplir_options_mobile_free), pas un champ de formulaire
    générique — voir dossiers.py::pre_remplir_souscription."""
    client = FakeClient(prenom="Alice", nom="Martin", email="alice@test.fr",
                         telephone="0601020304", adresse="1 rue Test",
                         code_postal="75001", ville="Paris")
    contrat_mobile = FakeContrat(conserver_numero="non", type_sim="esim")

    donnees = se.construire_donnees_client(client, contrat_mobile)

    assert donnees["conserver_numero"] == "non"
    assert donnees["type_sim"] == "esim"
    assert donnees["email_confirmation"] == "alice@test.fr"


def test_construire_donnees_client_sans_contrat_mobile_omet_la_portabilite():
    client = FakeClient(prenom="Alice", nom=None, email=None, telephone=None,
                         adresse=None, code_postal=None, ville=None)
    donnees = se.construire_donnees_client(client)
    assert "conserver_numero" not in donnees
    assert "type_sim" not in donnees


def test_fournisseur_non_supporte_refuse_sans_lancer_de_navigateur():
    ok, msg = se.lancer_souscription("Orange", "https://boutique.orange.fr", {})
    assert ok is False
    assert "Orange" in msg


def test_url_manquante_refuse_sans_lancer_de_navigateur():
    assert "Free" in se.OPERATEURS_SUPPORTES
    ok, msg = se.lancer_souscription("Free", "", {})
    assert ok is False
    assert "URL" in msg


def test_construire_lien_affilie_ajoute_le_code_sans_ecraser_la_query():
    lien = se.construire_lien_affilie("https://free.fr/abo?promo=x", code_affiliation="AFF1")
    assert "aff=AFF1" in lien
    assert "promo=x" in lien


def test_lancement_reussi_lance_le_sous_process_detache(monkeypatch):
    lance = {}

    def faux_popen(args, **kwargs):
        lance["args"] = args
        return MagicMock()

    monkeypatch.setattr(se.subprocess, "Popen", faux_popen)

    ok, msg = se.lancer_souscription(
        "Free", "https://mobile.free.fr", {"prenom": "Alice"}, code_affiliation="AFF1", categorie="Mobile",
    )
    assert ok is True
    assert "args" in lance
    assert lance["args"][:4] == [se.sys.executable, "-m", "backend.services.souscription_engine", "--run"]

    chemin_payload = lance["args"][4]
    payload = json.loads(Path(chemin_payload).read_text(encoding="utf-8"))
    assert payload["categorie"] == "Mobile"


# ------------------------------------------------------------------------------
#  _choisir_option_texte() / _remplir_options_mobile_free() — tunnel d'options
#  Free Mobile forfait seul (mobile.free.fr/souscription/options).
# ------------------------------------------------------------------------------
def _fake_page_avec_clics(textes_visibles: set[str], textes_cliques: list[str]):
    """Simule page.get_by_text(texte).first : présent (`.count()`/`.is_visible()`
    vrais) seulement pour un texte de `textes_visibles` ; un clic sur un texte
    présent l'ajoute à `textes_cliques`."""
    page = MagicMock()

    def get_by_text(texte, exact=False):
        locator = MagicMock()
        present = texte in textes_visibles
        locator.first.count.return_value = 1 if present else 0
        locator.first.is_visible.return_value = present
        locator.first.click.side_effect = lambda timeout=None: textes_cliques.append(texte)
        return locator

    page.get_by_text.side_effect = get_by_text
    return page


def test_choisir_option_texte_clique_le_premier_texte_present():
    cliques: list[str] = []
    page = _fake_page_avec_clics({"eSIM"}, cliques)
    assert se._choisir_option_texte(page, ["Carte SIM", "eSIM"]) is True
    assert cliques == ["eSIM"]


def test_choisir_option_texte_renvoie_false_si_aucun_texte_present():
    page = _fake_page_avec_clics(set(), [])
    assert se._choisir_option_texte(page, ["Carte SIM", "eSIM"]) is False


def test_remplir_options_mobile_free_choisit_non_abonne_et_nouveau_numero_et_esim():
    cliques: list[str] = []
    page = _fake_page_avec_clics(
        {"Non, je ne suis pas abonné", "Je choisis un nouveau numéro", "eSIM", "Carte SIM"}, cliques
    )

    se._remplir_options_mobile_free(page, {"conserver_numero": "non", "type_sim": "esim"})

    assert "Non, je ne suis pas abonné" in cliques
    assert "Je choisis un nouveau numéro" in cliques
    assert "eSIM" in cliques
    assert "Carte SIM" not in cliques


def test_remplir_options_mobile_free_garde_le_numero_par_defaut_si_conserve():
    cliques: list[str] = []
    page = _fake_page_avec_clics(
        {"Non, je ne suis pas abonné", "Je choisis un nouveau numéro", "eSIM", "Carte SIM"}, cliques
    )

    se._remplir_options_mobile_free(page, {"conserver_numero": "oui", "type_sim": "carte_sim"})

    assert "Je choisis un nouveau numéro" not in cliques
    assert "Carte SIM" in cliques


def test_remplir_options_mobile_free_choisit_toujours_sans_solution_mcafee():
    cliques: list[str] = []
    page = _fake_page_avec_clics({"Non, je ne suis pas abonné", "Sans solution"}, cliques)

    se._remplir_options_mobile_free(page, {})

    assert "Sans solution" in cliques


# ------------------------------------------------------------------------------
#  _verifier_offre_panier_free() — panier free.fr (« Votre panier »), atteint
#  avant le tunnel d'options mobile.
# ------------------------------------------------------------------------------
def test_verifier_offre_panier_free_ne_clique_rien_si_offre_deja_affichee():
    cliques: list[str] = []
    page = _fake_page_avec_clics({"Forfait Free 150 Go"}, cliques)

    se._verifier_offre_panier_free(page, "Forfait Free 150 Go")

    assert cliques == []


def test_verifier_offre_panier_free_clique_modifier_si_offre_differente():
    cliques: list[str] = []
    page = _fake_page_avec_clics({"Modifier"}, cliques)

    se._verifier_offre_panier_free(page, "Forfait Free 150 Go")

    assert cliques == ["Modifier"]


def test_verifier_offre_panier_free_ne_fait_rien_sans_bouton_modifier():
    cliques: list[str] = []
    page = _fake_page_avec_clics(set(), cliques)

    se._verifier_offre_panier_free(page, "Forfait Free 150 Go")

    assert cliques == []


def test_verifier_offre_panier_free_ignore_nom_offre_vide():
    cliques: list[str] = []
    page = _fake_page_avec_clics({"Modifier"}, cliques)

    se._verifier_offre_panier_free(page, "")

    assert cliques == []


def test_executer_survit_a_un_echec_de_navigation(monkeypatch, tmp_path):
    """Une navigation en échec (URL de catalogue injoignable, timeout...) ne doit
    jamais faire planter le process détaché avant que le navigateur ait pu
    afficher quoi que ce soit au conseiller — cf. le bug « rien ne se passe »."""
    monkeypatch.setattr(se, "RACINE_REPO", tmp_path)
    se.JOURNAL.handlers.clear()

    chemin = tmp_path / "payload.json"
    chemin.write_text(
        '{"fournisseur": "Bouygues", "url": "https://exemple-injoignable.invalid", '
        '"donnees": {"prenom": "Alice"}, "nom_offre": ""}',
        encoding="utf-8",
    )

    fake_page = MagicMock()
    fake_page.goto.side_effect = Exception("net::ERR_NAME_NOT_RESOLVED")
    fake_page.wait_for_event.side_effect = Exception("pas d'evenement en test")
    fake_browser = MagicMock()
    fake_browser.new_page.return_value = fake_page
    fake_p = MagicMock()
    fake_p.chromium.launch.return_value = fake_browser
    fake_sync_playwright_cm = MagicMock()
    fake_sync_playwright_cm.__enter__.return_value = fake_p
    fake_sync_playwright_cm.__exit__.return_value = False

    with patch("playwright.sync_api.sync_playwright", return_value=fake_sync_playwright_cm):
        se._executer(str(chemin))  # ne doit pas lever

    # Le navigateur doit malgré tout être fermé proprement en sortie (pas de fenêtre
    # ni de process Chromium orphelin), et l'échec doit être journalisé plutôt
    # qu'invisible (cf. process détaché sans console).
    fake_browser.close.assert_called_once()
    journal = (tmp_path / "souscription_assistee.log").read_text(encoding="utf-8")
    assert "Échec de navigation" in journal
