# ==============================================================================
#  TESTS — chatbot_api.py (endpoints FastAPI : prospects, offres, bilan, chat)
# ==============================================================================
from fastapi.testclient import TestClient

import chatbot_api
from offres_engine import ajouter_offre

client = TestClient(chatbot_api.app)


def test_creer_prospect_ok(tmp_db):
    reponse = client.post("/api/prospects", json={
        "prenom": "Marie", "nom": "Curie", "telephone": "0601020304",
        "univers_interesse": "Télécom", "operateur_actuel": "Orange",
        "cout_mensuel_actuel": 35.0,
    })
    assert reponse.status_code == 200
    prospect_id = reponse.json()["prospect_id"]
    assert prospect_id is not None

    conn = tmp_db.get_conn()
    row = conn.execute("SELECT * FROM prospects WHERE id=?", (prospect_id,)).fetchone()
    conn.close()
    assert row["origine"] == "Chatbot"
    assert row["prenom"] == "Marie"


def test_creer_prospect_sans_contact_rejete(tmp_db):
    reponse = client.post("/api/prospects", json={"prenom": "Sans Contact"})
    assert reponse.status_code == 422


def test_creer_prospect_email_invalide_rejete(tmp_db):
    reponse = client.post("/api/prospects", json={"prenom": "Test", "email": "pas-un-email"})
    assert reponse.status_code == 422


def test_offres_comparer(tmp_db):
    ajouter_offre({
        "univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
        "nom_offre": "Forfait Test", "prix_mensuel": 10.0, "frais_activation": 0.0,
        "engagement_mois": 0, "caracteristiques": "Test", "commission_affiliation": 5.0,
        "data_go": 100.0,
    })
    reponse = client.post("/api/offres/comparer", json={
        "univers": "Télécom", "categorie": "Mobile", "cout_actuel_mensuel": 30.0,
    })
    assert reponse.status_code == 200
    resultats = reponse.json()["resultats"]
    assert len(resultats) == 1
    assert resultats[0]["fournisseur"] == "Free"
    assert resultats[0]["economie_annuelle"] == 240.0


def test_bilan(tmp_db):
    ajouter_offre({
        "univers": "Télécom", "categorie": "Mobile", "fournisseur": "Bouygues",
        "nom_offre": "Forfait Bilan", "prix_mensuel": 15.0, "frais_activation": 0.0,
        "engagement_mois": 0, "caracteristiques": "Test", "commission_affiliation": 5.0,
        "data_go": 100.0,
    })
    reponse = client.post("/api/bilan", json={
        "service_principal": "Mobile uniquement", "cout_tel": 35.0,
    })
    assert reponse.status_code == 200
    data = reponse.json()
    assert data["economie_max_annuelle"] == 240.0


def test_chat_sans_cle_api_renvoie_message_clair(tmp_db):
    reponse = client.post("/api/chat", json={"session_id": "s-api-1", "message": "Bonjour"})
    assert reponse.status_code == 200
    assert "pas configuré" in reponse.json()["reply"]


def test_chat_message_vide_rejete(tmp_db):
    reponse = client.post("/api/chat", json={"session_id": "s-api-2", "message": "   "})
    assert reponse.status_code == 422
