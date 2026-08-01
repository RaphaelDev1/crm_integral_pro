# ==============================================================================
#  TESTS — api_client.py::login/changer_mot_de_passe (bascule de l'auth sur
#  backend/). requests.post/mock, aucun réseau réel.
# ==============================================================================
import api_client


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_login_succes_renvoie_le_meme_contrat_que_authentifier_avec_limite(monkeypatch):
    payload = {
        "access_token": "jeton-acces",
        "refresh_token": "jeton-refresh",
        "token_type": "bearer",
        "user": {
            "id": 1, "username": "conseiller1", "nom_complet": "Jean Conseiller",
            "role": "Conseiller", "actif": True, "doit_changer_mdp": False,
        },
    }
    monkeypatch.setattr(api_client.requests, "post", lambda *a, **k: _FakeResponse(200, payload))

    user, err = api_client.login("conseiller1", "Secret123!", "1.2.3.4")

    assert err is None
    assert user["id"] == 1
    assert user["nom_complet"] == "Jean Conseiller"
    assert user["role"] == "Conseiller"
    assert user["access_token"] == "jeton-acces"
    assert user["refresh_token"] == "jeton-refresh"


def test_login_mot_de_passe_incorrect(monkeypatch):
    monkeypatch.setattr(
        api_client.requests, "post",
        lambda *a, **k: _FakeResponse(401, {"detail": "Identifiant ou mot de passe incorrect."}),
    )

    user, err = api_client.login("conseiller1", "mauvais")

    assert user is None
    assert err == "Identifiant ou mot de passe incorrect."


def test_login_verrouille_transmet_le_message_backend(monkeypatch):
    monkeypatch.setattr(
        api_client.requests, "post",
        lambda *a, **k: _FakeResponse(429, {"detail": "Trop de tentatives échouées. Réessayez dans 5 min."}),
    )

    user, err = api_client.login("conseiller1", "x")

    assert user is None
    assert "5 min" in err


def test_login_backend_injoignable(monkeypatch):
    def _boom(*a, **k):
        raise ConnectionError("connexion refusée")
    monkeypatch.setattr(api_client.requests, "post", _boom)

    user, err = api_client.login("conseiller1", "x")

    assert user is None
    assert "injoignable" in err


def test_login_identifiant_vide_ne_declenche_aucun_appel_reseau(monkeypatch):
    appele = []
    monkeypatch.setattr(api_client.requests, "post", lambda *a, **k: appele.append(1))

    user, err = api_client.login("", "x")

    assert user is None
    assert err == "Identifiant ou mot de passe incorrect."
    assert appele == []


def test_changer_mot_de_passe_succes(monkeypatch):
    monkeypatch.setattr(api_client, "_requete", lambda *a, **k: {"message": "Mot de passe mis à jour."})

    ok, err = api_client.changer_mot_de_passe("NouveauSecret123!")

    assert ok is True
    assert err is None


def test_changer_mot_de_passe_echec(monkeypatch):
    def _boom(*a, **k):
        raise api_client._ApiIndisponible("backend down")
    monkeypatch.setattr(api_client, "_requete", _boom)

    ok, err = api_client.changer_mot_de_passe("x")

    assert ok is False
    assert err == "backend down"
