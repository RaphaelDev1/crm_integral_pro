# ==============================================================================
#  TESTS — notifications.py (envoyer_demande_documents_prospect) : compose et
#  envoie le lien « facture + test de débit » par SMS et/ou email selon les
#  coordonnées disponibles sur la fiche prospect.
# ==============================================================================
import notifications
import sms_engine


def test_envoie_sms_et_email_si_coordonnees_completes(monkeypatch):
    appels_sms = []
    appels_email = []
    monkeypatch.setattr(sms_engine, "envoyer_sms", lambda tel, msg: appels_sms.append((tel, msg)) or True)
    monkeypatch.setattr(notifications, "_envoyer_email_html",
                         lambda dest, sujet, corps: appels_email.append((dest, sujet, corps)) or True)

    prospect = {"prenom": "Jean", "telephone": "0601020304", "email": "jean@example.fr"}
    resultat = notifications.envoyer_demande_documents_prospect(prospect, "https://x.test/portail/abc")

    assert resultat == {"sms_envoye": True, "email_envoye": True}
    assert appels_sms[0][0] == "0601020304"
    assert "https://x.test/portail/abc" in appels_sms[0][1]
    assert appels_email[0][0] == "jean@example.fr"
    assert "https://x.test/portail/abc" in appels_email[0][2]


def test_pas_de_telephone_naapelle_pas_le_sms(monkeypatch):
    appele = []
    monkeypatch.setattr(sms_engine, "envoyer_sms", lambda tel, msg: appele.append(1) or True)
    monkeypatch.setattr(notifications, "_envoyer_email_html", lambda *a: True)

    prospect = {"prenom": "Jean", "telephone": "", "email": "jean@example.fr"}
    resultat = notifications.envoyer_demande_documents_prospect(prospect, "https://x.test/p/abc")

    assert resultat["sms_envoye"] is False
    assert appele == []


def test_pas_demail_naapelle_pas_lemail(monkeypatch):
    appele = []
    monkeypatch.setattr(sms_engine, "envoyer_sms", lambda tel, msg: True)
    monkeypatch.setattr(notifications, "_envoyer_email_html", lambda *a: appele.append(1) or True)

    prospect = {"prenom": "Jean", "telephone": "0601020304", "email": ""}
    resultat = notifications.envoyer_demande_documents_prospect(prospect, "https://x.test/p/abc")

    assert resultat["email_envoye"] is False
    assert appele == []
