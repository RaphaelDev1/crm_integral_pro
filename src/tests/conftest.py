# ==============================================================================
#  CONFIGURATION PYTEST — fixtures partagées
# ==============================================================================
import os
import sys

# Permet `import db`, `import utils`, etc. depuis les modules de src/ sans les
# installer en package — les tests vivent dans src/tests/, le code dans src/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import db as db_module


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Redirige toute la couche db.py vers une base SQLite jetable dans tmp_path,
    pour qu'aucun test ne touche jamais ia_conseil_crm.db (la base réelle)."""
    db_file = tmp_path / "test_ia_conseil.db"
    monkeypatch.setattr(db_module, "DB_NAME", str(db_file))
    db_module.initialiser_bdd()

    # Les caches @st.cache_data (lire_offres/comparer_offres) sont globaux au
    # process Python — on les vide pour qu'un test ne voie jamais un résultat
    # mis en cache par un test précédent (base différente, mêmes arguments).
    from offres_engine import lire_offres, comparer_offres
    from veille_prix_engine import lire_sources
    lire_offres.clear()
    comparer_offres.clear()
    lire_sources.clear()

    yield db_module

    lire_offres.clear()
    comparer_offres.clear()
    lire_sources.clear()
