# ==============================================================================
#  TESTS — api_client.py (repli automatique sur les modules *_engine.py quand
#  l'API CRM interne est injoignable, et bon fonctionnement quand elle répond)
# ==============================================================================
import pytest

import api_client
import prospects_engine


class _FausseReponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise api_client.requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


def test_repli_sur_engine_quand_api_indisponible(tmp_db, monkeypatch):
    """Si l'API ne répond pas (connexion refusée), ajouter_prospect doit quand
    même écrire en base via prospects_engine — le logiciel ne doit jamais planter
    juste parce que le process crm_api.py n'est pas démarré."""
    def _echoue(*args, **kwargs):
        raise api_client.requests.ConnectionError("API non démarrée")
    monkeypatch.setattr(api_client.requests, "request", _echoue)

    pid = api_client.ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
    assert pid is not None

    df = prospects_engine.lire_prospects()
    assert df.loc[0, "prenom"] == "Jean"


def test_repli_lire_prospects_vide_garde_les_bonnes_colonnes(tmp_db, monkeypatch):
    monkeypatch.setattr(api_client.requests, "request",
                         lambda *a, **k: (_ for _ in ()).throw(api_client.requests.ConnectionError()))
    df = api_client.lire_prospects()
    assert list(df.columns) == list(prospects_engine.lire_prospects().columns)
    assert df.empty


def test_appel_api_reussi_utilise_la_reponse_http(tmp_db, monkeypatch):
    """Quand l'API répond, api_client ne doit pas retomber sur l'accès direct —
    on vérifie ça en faisant échouer le module *_engine.py sous-jacent : si le
    test passe, c'est bien la voie HTTP qui a été empruntée."""
    appelée = {"POST /prospects": False}

    def _requete(method, url, headers=None, timeout=None, **kwargs):
        assert method == "POST"
        assert url.endswith("/prospects")
        appelée["POST /prospects"] = True
        return _FausseReponse({"id": 42})

    monkeypatch.setattr(api_client.requests, "request", _requete)
    monkeypatch.setattr(api_client._prospects_db, "ajouter_prospect",
                         lambda d: (_ for _ in ()).throw(AssertionError("ne doit pas être appelé")))

    pid = api_client.ajouter_prospect({"prenom": "Test"})
    assert pid == 42
    assert appelée["POST /prospects"] is True


def test_lire_prospects_via_api_reconstruit_dataframe(monkeypatch):
    def _requete(method, url, headers=None, timeout=None, **kwargs):
        return _FausseReponse({"columns": ["id", "prenom"], "records": [{"id": 1, "prenom": "Ana"}]})
    monkeypatch.setattr(api_client.requests, "request", _requete)

    df = api_client.lire_prospects()
    assert list(df.columns) == ["id", "prenom"]
    assert df.iloc[0]["prenom"] == "Ana"


def test_erreur_http_retombe_aussi_sur_engine(tmp_db, monkeypatch):
    """Une erreur HTTP (ex. 500) doit déclencher le même repli qu'une panne réseau."""
    monkeypatch.setattr(api_client.requests, "request",
                         lambda *a, **k: _FausseReponse({"detail": "boom"}, status_code=500))
    pid = api_client.ajouter_prospect({"ref": "P2", "prenom": "Chloé", "nom": "Martin"})
    df = prospects_engine.lire_prospects()
    assert df.loc[0, "prenom"] == "Chloé"
    assert pid is not None
