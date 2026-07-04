# ==============================================================================
#  TESTS — crm_api.py (API CRM interne : auth JWT, CRUD, diagnostic)
# ==============================================================================
from fastapi.testclient import TestClient

import crm_api
from auth import creer_utilisateur
from offres_engine import ajouter_offre

client = TestClient(crm_api.app)


def _token(role="Conseiller", username="conseiller1"):
    creer_utilisateur(username, "Jean Conseiller", "Password2026!", role)
    reponse = client.post("/auth/login", json={"username": username, "password": "Password2026!"})
    assert reponse.status_code == 200
    return reponse.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_ok(tmp_db):
    creer_utilisateur("alice", "Alice Admin", "Password2026!", "Admin")
    reponse = client.post("/auth/login", json={"username": "alice", "password": "Password2026!"})
    assert reponse.status_code == 200
    data = reponse.json()
    assert data["token_type"] == "bearer"
    assert "password_hash" not in data["user"]
    assert data["user"]["role"] == "Admin"


def test_login_mauvais_mot_de_passe(tmp_db):
    creer_utilisateur("bob", "Bob", "Password2026!", "Conseiller")
    reponse = client.post("/auth/login", json={"username": "bob", "password": "faux"})
    assert reponse.status_code == 401


def test_endpoint_sans_jeton_refuse(tmp_db):
    reponse = client.get("/prospects")
    assert reponse.status_code == 401


def test_endpoint_jeton_invalide_refuse(tmp_db):
    reponse = client.get("/prospects", headers=_auth("pas-un-jeton"))
    assert reponse.status_code == 401


def test_prospects_crud_avec_role_conseiller(tmp_db):
    token = _token("Conseiller")
    r = client.post("/prospects", json={"prenom": "Marie", "nom": "Curie", "telephone": "0601020304"},
                     headers=_auth(token))
    assert r.status_code == 200
    pid = r.json()["id"]

    r = client.get("/prospects", headers=_auth(token))
    assert r.status_code == 200
    payload = r.json()
    assert "columns" in payload and "records" in payload
    assert any(p["id"] == pid for p in payload["records"])

    r = client.patch(f"/prospects/{pid}", json={"champ": "statut", "valeur": "Converti"},
                      headers=_auth(token))
    assert r.status_code == 200

    r = client.patch(f"/prospects/{pid}", json={"champ": "password_hash", "valeur": "x"},
                      headers=_auth(token))
    assert r.status_code == 422

    r = client.delete(f"/prospects/{pid}", headers=_auth(token))
    assert r.status_code == 200


def test_role_lecture_ne_peut_pas_creer_prospect(tmp_db):
    token = _token("Lecture", "lecteur1")
    r = client.post("/prospects", json={"prenom": "X", "nom": "Y"}, headers=_auth(token))
    assert r.status_code == 403


def test_role_lecture_peut_lire(tmp_db):
    token = _token("Lecture", "lecteur2")
    r = client.get("/prospects", headers=_auth(token))
    assert r.status_code == 200


def test_offres_reservees_admin(tmp_db):
    token_conseiller = _token("Conseiller", "conseiller2")
    r = client.post("/offres", json={
        "univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free", "nom_offre": "Test",
    }, headers=_auth(token_conseiller))
    assert r.status_code == 403

    token_admin = _token("Admin", "admin2")
    r = client.post("/offres", json={
        "univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free", "nom_offre": "Test",
    }, headers=_auth(token_admin))
    assert r.status_code == 200


def test_clients_et_contrats_crud(tmp_db):
    token = _token("Conseiller", "conseiller3")
    r = client.post("/clients", json={"prenom": "Paul", "nom": "Martin"}, headers=_auth(token))
    assert r.status_code == 200
    cid = r.json()["id"]

    r = client.post(f"/clients/{cid}/contrats", json={
        "univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
        "nom_offre": "Forfait", "cout_mensuel": 15.0,
    }, headers=_auth(token))
    assert r.status_code == 200

    r = client.get(f"/clients/{cid}/contrats", headers=_auth(token))
    assert r.status_code == 200
    assert len(r.json()["records"]) == 1

    r = client.delete(f"/clients/{cid}", headers=_auth(token))
    assert r.status_code == 200


def test_diagnostic_comparer_et_bilan(tmp_db):
    ajouter_offre({
        "univers": "Télécom", "categorie": "Mobile", "fournisseur": "Bouygues",
        "nom_offre": "Forfait Diag", "prix_mensuel": 15.0, "frais_activation": 0.0,
        "engagement_mois": 0, "caracteristiques": "Test", "commission_affiliation": 5.0,
        "data_go": 100.0,
    })
    token = _token("Lecture", "lecteur3")

    r = client.post("/diagnostic/comparer", json={
        "univers": "Télécom", "categorie": "Mobile", "cout_actuel_mensuel": 35.0,
    }, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["resultats"][0]["economie_annuelle"] == 240.0

    r = client.post("/diagnostic/bilan", json={
        "service_principal": "Mobile uniquement", "cout_tel": 35.0,
    }, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["principal"]["offres"][0]["fournisseur"] == "Bouygues"

    r = client.post("/diagnostic/complet", json={
        "service_principal": "Mobile uniquement", "cout_tel": 35.0, "cout_elec": 90.0,
    }, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["economie_max_annuelle"] == 240.0
