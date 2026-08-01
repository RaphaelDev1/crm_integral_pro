# ==============================================================================
#  TESTS — backend/services/veille_engine.py : extraction de prix, relevé
#  périodique (scraping mocké), validation/rejet d'alerte. Porté de
#  src/tests/test_veille_prix_engine.py. Même idiome que test_dossier_engine.py.
# ==============================================================================
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.models.offre import Offre
from backend.models.veille import SourceVeille, VeilleAlerte, VeilleHistoriquePrix
from backend.services import veille_engine


def _run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self, resultats=None, objets=None):
        self._resultats = resultats or []
        self._objets = objets or {}
        self.added = []
        self.committed = False

    async def execute(self, _query):
        return _FakeResult(self._resultats)

    async def get(self, model, id_):
        return self._objets.get((model, id_))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


# ------------------------------------------------------------------------------
#  extraire_prix()
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("texte,attendu", [
    ("19,99 €", 19.99),
    ("à partir de 24.99€", 24.99),
    ("€ 12,50 par mois", 12.50),
    (None, None),
    ("aucun prix ici", None),
])
def test_extraire_prix(texte, attendu):
    assert veille_engine.extraire_prix(texte) == attendu


# ------------------------------------------------------------------------------
#  lancer_veille()
# ------------------------------------------------------------------------------
def _source(**kwargs):
    base = dict(id=1, fournisseur="Free", nom_offre="Forfait Free", url="https://free.fr",
                selecteur_prix=".prix", actif=True, dernier_prix=None, offre_id=None)
    base.update(kwargs)
    return SourceVeille(**base)


def test_lancer_veille_cree_une_alerte_si_le_prix_change():
    source = _source(dernier_prix=10.0)
    db = FakeSession(resultats=[source])

    with patch.object(veille_engine, "scraper_source", new=AsyncMock(return_value=15.0)):
        alertes = _run(veille_engine.lancer_veille(db))

    assert len(alertes) == 1
    assert alertes[0]["ancien_prix"] == 10.0 and alertes[0]["nouveau_prix"] == 15.0
    assert source.dernier_prix == 15.0
    assert any(isinstance(o, VeilleHistoriquePrix) for o in db.added)
    assert any(isinstance(o, VeilleAlerte) for o in db.added)
    assert db.committed


def test_lancer_veille_pas_dalerte_si_prix_stable():
    source = _source(dernier_prix=10.0)
    db = FakeSession(resultats=[source])

    with patch.object(veille_engine, "scraper_source", new=AsyncMock(return_value=10.0)):
        alertes = _run(veille_engine.lancer_veille(db))

    assert alertes == []
    assert not any(isinstance(o, VeilleAlerte) for o in db.added)


def test_lancer_veille_ignore_une_source_sans_prix_extractible():
    source = _source(dernier_prix=10.0)
    db = FakeSession(resultats=[source])

    with patch.object(veille_engine, "scraper_source", new=AsyncMock(return_value=None)):
        alertes = _run(veille_engine.lancer_veille(db))

    assert alertes == []
    assert db.added == []
    assert source.dernier_prix == 10.0


def test_lancer_veille_premier_releve_sans_ancien_prix_ne_cree_pas_dalerte():
    source = _source(dernier_prix=None)
    db = FakeSession(resultats=[source])

    with patch.object(veille_engine, "scraper_source", new=AsyncMock(return_value=12.0)):
        alertes = _run(veille_engine.lancer_veille(db))

    assert alertes == []
    assert source.dernier_prix == 12.0


# ------------------------------------------------------------------------------
#  valider_alerte() / rejeter_alerte()
# ------------------------------------------------------------------------------
def test_valider_alerte_repercute_le_prix_sur_loffre_liee():
    offre = Offre(id=5, prix_mensuel=10.0)
    source = _source(offre_id=5)
    alerte = VeilleAlerte(id=1, source_id=1, ancien_prix=10.0, nouveau_prix=15.0, statut="en_attente")
    db = FakeSession(objets={(VeilleAlerte, 1): alerte, (SourceVeille, 1): source, (Offre, 5): offre})

    ok, message = _run(veille_engine.valider_alerte(db, 1))

    assert ok is True
    assert offre.prix_mensuel == 15.0
    assert alerte.statut == "validee"
    assert "catalogue" in message


def test_valider_alerte_deja_traitee_est_refusee():
    alerte = VeilleAlerte(id=1, source_id=1, statut="validee")
    db = FakeSession(objets={(VeilleAlerte, 1): alerte})

    ok, message = _run(veille_engine.valider_alerte(db, 1))

    assert ok is False
    assert "déjà" in message


def test_rejeter_alerte_marque_le_statut():
    alerte = VeilleAlerte(id=1, source_id=1, statut="en_attente")
    db = FakeSession(objets={(VeilleAlerte, 1): alerte})

    ok = _run(veille_engine.rejeter_alerte(db, 1))

    assert ok is True
    assert alerte.statut == "rejetee"
