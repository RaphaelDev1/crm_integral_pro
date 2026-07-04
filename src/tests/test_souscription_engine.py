# ==============================================================================
#  TESTS — souscription_engine.py : garde-fous (pas de lancement Playwright réel)
# ==============================================================================
from db import lire_historique
from souscription_engine import (
    OPERATEURS_SUPPORTES, construire_donnees_client, lancer_souscription,
)


def test_construire_donnees_client_normalise_les_champs():
    record = {"prenom": "Alice", "nom": "Martin", "email": "alice@test.fr",
              "telephone": "0601020304", "adresse": "1 rue Test",
              "code_postal": "75001", "ville": "Paris"}
    donnees = construire_donnees_client(record)
    assert donnees["prenom"] == "Alice"
    assert donnees["ville"] == "Paris"
    assert donnees["civilite"] == ""


def test_construire_donnees_client_tolere_les_champs_absents():
    donnees = construire_donnees_client({})
    assert all(v == "" for v in donnees.values())


def test_fournisseur_non_supporte_refuse_sans_lancer_de_navigateur():
    ok, msg = lancer_souscription("Orange", "https://boutique.orange.fr", {})
    assert ok is False
    assert "Orange" in msg


def test_url_manquante_refuse_sans_lancer_de_navigateur():
    assert "Free" in OPERATEURS_SUPPORTES
    ok, msg = lancer_souscription("Free", "", {})
    assert ok is False
    assert "URL" in msg


def test_lancement_reussi_journalise_dans_historique(tmp_db, monkeypatch):
    lance = {}

    def faux_popen(args, **kwargs):
        lance["args"] = args
        class FauxProcessus:
            pass
        return FauxProcessus()

    monkeypatch.setattr("souscription_engine.subprocess.Popen", faux_popen)

    ok, msg = lancer_souscription(
        "Free", "https://mobile.free.fr", {"prenom": "Alice"},
        code_affiliation="AFF1", entite_type="prospect", entite_id=42,
        nom_offre="Forfait Free 5G 350 Go",
    )
    assert ok is True
    assert "args" in lance

    hist = lire_historique("prospect", 42)
    assert len(hist) == 1
    assert "Free" in hist.iloc[0]["details"]
