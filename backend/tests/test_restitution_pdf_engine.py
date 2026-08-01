# ==============================================================================
#  TESTS — backend/services/restitution_pdf_engine.py : génération ne doit
#  jamais lever, avec ou sans logo, avec ou sans offres comparées. Même
#  approche « smoke test » que backend/tests/test_document_engine.py.
# ==============================================================================
import io

from PIL import Image

from backend.models.client import Client
from backend.models.comparaison_offre import ComparaisonOffre
from backend.models.dossier import Dossier
from backend.services import restitution_pdf_engine as rpe


def _client(**kwargs):
    base = dict(id=1, prenom="Jean", nom="Dupont", telephone="0600000000", email="jean@example.com")
    base.update(kwargs)
    return Client(**base)


def _dossier(**kwargs):
    base = dict(id=1, client_id=1, univers="telecom_mobile", economie_annuelle_estimee=0.0)
    base.update(kwargs)
    return Dossier(**base)


def _comparaison(**kwargs):
    base = dict(
        id=1, client_id=1, univers="Télécom", categorie="Mobile",
        offre_recommandee_id=2,
        offres_comparees=[
            {"offre_id": 1, "nom": "Forfait Eco", "fournisseur": "Free", "prix_mensuel": 9.99, "economie_mensuelle": 10.0},
            {"offre_id": 2, "nom": "Forfait Premium", "fournisseur": "Sosh", "prix_mensuel": 14.99, "economie_mensuelle": 20.0},
        ],
        economie_annuelle_estimee=240.0,
    )
    base.update(kwargs)
    return ComparaisonOffre(**base)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 80), (10, 80, 200)).save(buf, format="PNG")
    return buf.getvalue()


def test_generation_avec_offres_et_sans_logo():
    pdf_bytes = rpe.generer_pdf_restitution_dossier(
        _dossier(), _client(), _comparaison(), branding={"nom_societe": "IA Conseil"},
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_generation_avec_logo_et_couleurs_personnalisees():
    branding = {
        "nom_societe": "Ma Societe",
        "couleur_primaire_hex": "#102A52",
        "couleur_accent_hex": "#009650",
        "logo_bytes": _png_bytes(),
    }
    pdf_bytes = rpe.generer_pdf_restitution_dossier(_dossier(), _client(), _comparaison(), branding)
    assert pdf_bytes.startswith(b"%PDF")


def test_generation_sans_offres_comparees():
    comparaison = _comparaison(offres_comparees=[], offre_recommandee_id=None)
    pdf_bytes = rpe.generer_pdf_restitution_dossier(_dossier(), _client(), comparaison, branding={})
    assert pdf_bytes.startswith(b"%PDF")


def test_hex_vers_rgb_repli_sur_defaut_si_invalide():
    assert rpe._hex_vers_rgb(None, (1, 2, 3)) == (1, 2, 3)
    assert rpe._hex_vers_rgb("pas-une-couleur", (1, 2, 3)) == (1, 2, 3)
    assert rpe._hex_vers_rgb("#102A52", (1, 2, 3)) == (16, 42, 82)
