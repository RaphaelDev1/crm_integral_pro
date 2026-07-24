# ==============================================================================
#  TESTS — sms_engine.py (envoi SMS OVH/Twilio, repli gracieux si non configuré)
# ==============================================================================
import secrets_config
import sms_engine


def _config_vide(provider="ovh"):
    return {
        "provider": provider, "ovh_endpoint": "ovh-eu", "ovh_service_name": "",
        "ovh_application_key": "", "ovh_application_secret": "", "ovh_consumer_key": "",
        "twilio_account_sid": "", "twilio_auth_token": "", "twilio_from_number": "",
    }


def _config_ovh_complete():
    cfg = _config_vide("ovh")
    cfg.update({
        "ovh_service_name": "sms-abc", "ovh_application_key": "ak",
        "ovh_application_secret": "as", "ovh_consumer_key": "ck",
    })
    return cfg


def _config_twilio_complete():
    cfg = _config_vide("twilio")
    cfg.update({
        "twilio_account_sid": "sid", "twilio_auth_token": "token",
        "twilio_from_number": "+33600000000",
    })
    return cfg


def test_pas_de_destinataire_renvoie_false(monkeypatch):
    monkeypatch.setattr(secrets_config, "sms_config", lambda: _config_ovh_complete())
    assert sms_engine.envoyer_sms("", "Bonjour") is False


def test_ovh_non_configure_renvoie_false_sans_appel_reseau(monkeypatch):
    monkeypatch.setattr(secrets_config, "sms_config", lambda: _config_vide("ovh"))
    assert sms_engine.envoyer_sms("0601020304", "Bonjour") is False


def test_twilio_non_configure_renvoie_false_sans_appel_reseau(monkeypatch):
    monkeypatch.setattr(secrets_config, "sms_config", lambda: _config_vide("twilio"))
    assert sms_engine.envoyer_sms("0601020304", "Bonjour") is False


def test_ovh_configure_appelle_lapi_et_renvoie_true(monkeypatch):
    appels = []

    class _ReponseOk:
        def raise_for_status(self):
            pass

    def _fake_post(url, data=None, headers=None, timeout=None):
        appels.append((url, headers))
        return _ReponseOk()

    monkeypatch.setattr(secrets_config, "sms_config", lambda: _config_ovh_complete())
    monkeypatch.setattr(sms_engine.requests, "post", _fake_post)

    assert sms_engine.envoyer_sms("0601020304", "Bonjour") is True
    assert len(appels) == 1
    assert "sms-abc" in appels[0][0]
    assert appels[0][1]["X-Ovh-Application"] == "ak"


def test_twilio_configure_appelle_lapi_et_renvoie_true(monkeypatch):
    appels = []

    class _ReponseOk:
        def raise_for_status(self):
            pass

    def _fake_post(url, data=None, auth=None, timeout=None):
        appels.append((url, data, auth))
        return _ReponseOk()

    monkeypatch.setattr(secrets_config, "sms_config", lambda: _config_twilio_complete())
    monkeypatch.setattr(sms_engine.requests, "post", _fake_post)

    assert sms_engine.envoyer_sms("0601020304", "Bonjour") is True
    assert len(appels) == 1
    assert appels[0][2] == ("sid", "token")


def test_erreur_reseau_renvoie_false(monkeypatch):
    def _fake_post(*a, **k):
        raise ConnectionError("boom")

    monkeypatch.setattr(secrets_config, "sms_config", lambda: _config_ovh_complete())
    monkeypatch.setattr(sms_engine.requests, "post", _fake_post)

    assert sms_engine.envoyer_sms("0601020304", "Bonjour") is False
