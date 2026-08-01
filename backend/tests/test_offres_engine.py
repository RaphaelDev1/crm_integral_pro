# ==============================================================================
#  TESTS — backend/services/offres_engine.py : comparaison et recommandations,
#  porté de src/offres_engine.py (Streamlit) et de src/tests/test_offres_engine.py.
#  Même idiome que backend/tests/test_dossier_engine.py : session factice
#  (execute() pré-rempli) + asyncio.run() (pytest-asyncio non installé).
# ==============================================================================
import asyncio
from unittest.mock import AsyncMock, patch

from backend.models.offre import Offre
from backend.services import offres_engine


def _run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self, resultats=None):
        self._resultats = resultats or []

    async def execute(self, _query):
        return _FakeResult(self._resultats)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


def _offre(**kwargs):
    base = dict(
        id=1, univers="Télécom", categorie="Mobile", fournisseur="Free", nom_offre="Forfait Free",
        prix_mensuel=10.0, frais_activation=0.0, engagement_mois=0, caracteristiques="", commission_affiliation=0.0,
        data_go=100.0, actif=True, url_souscription="https://free.fr", code_affiliation="FREE",
    )
    base.update(kwargs)
    return Offre(**base)


# ------------------------------------------------------------------------------
#  comparer_offres()
# ------------------------------------------------------------------------------
def test_comparer_offres_calcule_les_economies_et_trie_par_economie_annuelle():
    moins_cher = _offre(id=1, fournisseur="Free", prix_mensuel=10.0)
    plus_cher = _offre(id=2, fournisseur="SFR", prix_mensuel=15.0)
    db = FakeSession(resultats=[plus_cher, moins_cher])

    resultats = _run(offres_engine.comparer_offres(db, "Télécom", "Mobile", 20.0))

    assert [r["fournisseur"] for r in resultats] == ["Free", "SFR"]
    assert resultats[0]["economie_mensuelle"] == 10.0
    assert resultats[0]["economie_annuelle"] == 120.0


def test_comparer_offres_filtre_fournisseur_exclu():
    db = FakeSession(resultats=[_offre(id=1, fournisseur="Free"), _offre(id=2, fournisseur="SFR")])

    resultats = _run(offres_engine.comparer_offres(db, "Télécom", "Mobile", 20.0, fournisseur_exclu="Free"))

    assert [r["fournisseur"] for r in resultats] == ["SFR"]


def test_comparer_offres_filtre_fournisseurs_autorises():
    db = FakeSession(resultats=[_offre(id=1, fournisseur="Free"), _offre(id=2, fournisseur="SFR")])

    resultats = _run(offres_engine.comparer_offres(db, "Télécom", "Mobile", 20.0, fournisseurs_autorises=["SFR"]))

    assert [r["fournisseur"] for r in resultats] == ["SFR"]


def test_comparer_offres_exclut_data_go_insuffisant():
    suffisant = _offre(id=1, fournisseur="Free", data_go=200.0)
    insuffisant = _offre(id=2, fournisseur="SFR", data_go=50.0)
    db = FakeSession(resultats=[suffisant, insuffisant])

    resultats = _run(offres_engine.comparer_offres(db, "Télécom", "Mobile", 20.0, data_go_min=100.0))

    assert [r["fournisseur"] for r in resultats] == ["Free"]


def test_comparer_offres_data_go_min_sans_effet_si_offre_sans_quota():
    # Box/Fibre : data_go=0 en catalogue (non applicable) — jamais exclue par data_go_min.
    offre = _offre(id=1, categorie="Box / Fibre", fournisseur="Free", data_go=0.0)
    db = FakeSession(resultats=[offre])

    resultats = _run(offres_engine.comparer_offres(db, "Télécom", "Box / Fibre", 30.0, data_go_min=100.0))

    assert len(resultats) == 1


# ------------------------------------------------------------------------------
#  construire_recommandations()
# ------------------------------------------------------------------------------
def test_construire_recommandations_mobile_uniquement_propose_du_cross_sell():
    db = FakeSession()
    with patch.object(offres_engine, "comparer_offres", new=AsyncMock(return_value=[{"id": 1}])):
        resultat = _run(offres_engine.construire_recommandations(db, "Mobile uniquement", 20.0))

    assert resultat["principal"][0].startswith("📱")
    assert len(resultat["cross_sell"]) == 2


def test_construire_recommandations_pack_sans_cross_sell():
    db = FakeSession()
    with patch.object(offres_engine, "comparer_offres", new=AsyncMock(return_value=[{"id": 1}])):
        resultat = _run(offres_engine.construire_recommandations(db, "Pack Box + Mobile", 40.0))

    assert resultat["cross_sell"] == []


def test_construire_recommandations_multi_lignes_repli_sur_mobile_si_vide():
    db = FakeSession()

    async def comparer_offres_stub(_db, _univers, categorie, *args, **kwargs):
        return [] if categorie == "Multi-lignes" else [{"id": 1, "categorie": categorie}]

    with patch.object(offres_engine, "comparer_offres", new=AsyncMock(side_effect=comparer_offres_stub)):
        resultat = _run(offres_engine.construire_recommandations(db, "Autre", 20.0))

    titre, offres = resultat["principal"]
    assert titre.startswith("📲")
    assert offres and offres[0]["categorie"] == "Mobile"
