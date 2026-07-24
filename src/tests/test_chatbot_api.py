# ==============================================================================
#  TESTS — chatbot_api.py (endpoints FastAPI : prospects, offres, bilan, chat)
# ==============================================================================
import io

from fastapi.testclient import TestClient
from fpdf import FPDF

import chatbot_api
from offres_engine import ajouter_offre
from prospects_engine import ajouter_prospect, creer_token_documents

client = TestClient(chatbot_api.app)


def _pdf_bytes(lignes: list[str]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for ligne in lignes:
        pdf.cell(0, 10, ligne)
        pdf.ln(10)
    return bytes(pdf.output())


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


class TestPortailProspect:
    """Lien « envoyer facture + test de débit » — bouton fiche prospect (app.py),
    mini-page publique servie ici (GET /portail/{token}) et endpoints d'upload."""

    def test_page_html_servie_meme_avec_token_invalide(self, tmp_db):
        # La page est statique : la validation du token se fait côté /api/portail/{token},
        # pas au chargement de la page elle-même.
        reponse = client.get("/portail/nimportequoi")
        assert reponse.status_code == 200
        assert "text/html" in reponse.headers["content-type"]

    def test_contexte_token_invalide_404(self, tmp_db):
        reponse = client.get("/api/portail/nimportequoi")
        assert reponse.status_code == 404

    def test_contexte_token_valide(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        tok = creer_token_documents(pid)
        reponse = client.get(f"/api/portail/{tok['token']}")
        assert reponse.status_code == 200
        assert reponse.json()["prenom"] == "Jean"

    def test_upload_facture_token_invalide_404(self, tmp_db):
        reponse = client.post(
            "/api/portail/nimportequoi/facture",
            files={"fichier": ("f.pdf", _pdf_bytes(["Orange"]), "application/pdf")},
        )
        assert reponse.status_code == 404

    def test_upload_facture_extension_refusee(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        tok = creer_token_documents(pid)
        reponse = client.post(
            f"/api/portail/{tok['token']}/facture",
            files={"fichier": ("f.txt", b"contenu", "text/plain")},
        )
        assert reponse.status_code == 422

    def test_upload_facture_pdf_lisible_met_a_jour_le_prospect(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont",
                                 "telephone": "0601020304"})
        tok = creer_token_documents(pid)
        contenu = _pdf_bytes(["Orange SA", "Montant TTC a payer : 45,99 EUR"])
        reponse = client.post(
            f"/api/portail/{tok['token']}/facture",
            files={"fichier": ("facture.pdf", contenu, "application/pdf")},
        )
        assert reponse.status_code == 200
        assert reponse.json()["ok"] is True

        conn = tmp_db.get_conn()
        row = conn.execute("SELECT operateur_actuel, cout_mensuel_actuel FROM prospects WHERE id=?",
                            (pid,)).fetchone()
        conn.close()
        assert row["operateur_actuel"] == "Orange"
        assert row["cout_mensuel_actuel"] == 45.99

    def test_upload_facture_illisible_rejetee(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        tok = creer_token_documents(pid)
        contenu = _pdf_bytes(["Un document qui n'est pas une facture"])
        reponse = client.post(
            f"/api/portail/{tok['token']}/facture",
            files={"fichier": ("f.pdf", contenu, "application/pdf")},
        )
        assert reponse.status_code == 422

    def test_upload_speedtest_pdf_lisible_met_a_jour_le_prospect(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        tok = creer_token_documents(pid)
        contenu = _pdf_bytes(["Resultat du test", "150 Mbps descendant", "20 Mbps montant"])
        reponse = client.post(
            f"/api/portail/{tok['token']}/speedtest",
            files={"fichier": ("speed.pdf", contenu, "application/pdf")},
        )
        assert reponse.status_code == 200

        conn = tmp_db.get_conn()
        row = conn.execute("SELECT speed_down, speed_up FROM prospects WHERE id=?", (pid,)).fetchone()
        conn.close()
        assert row["speed_down"] == 150.0
        assert row["speed_up"] == 20.0

    def test_upload_speedtest_illisible_rejete(self, tmp_db):
        pid = ajouter_prospect({"ref": "P1", "prenom": "Jean", "nom": "Dupont"})
        tok = creer_token_documents(pid)
        contenu = _pdf_bytes(["Rien d'exploitable ici"])
        reponse = client.post(
            f"/api/portail/{tok['token']}/speedtest",
            files={"fichier": ("f.pdf", contenu, "application/pdf")},
        )
        assert reponse.status_code == 422
