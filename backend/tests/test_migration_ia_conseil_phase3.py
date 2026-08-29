# ==============================================================================
#  TESTS D'INTÉGRITÉ — migrations 0035 (session_facture + colonne PDF) et 0036
#  (rapport_veille_marche), PLAN_IMPLEMENTATION_4_PHASES.md §3.1/§3.3/§3.4.
#  Même idiome hors-ligne que test_migration_ia_conseil.py : monkeypatch des
#  fonctions alembic.op.* pour enregistrer les opérations DDL, pas de
#  connexion réelle requise (Postgres non provisionné en dev/CI).
# ==============================================================================
import importlib.util
import os

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

_VERSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic", "versions",
)


def _load_migration_module(filename: str, modname: str):
    path = os.path.join(_VERSIONS_DIR, filename)
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Recorder:
    def __init__(self):
        self.created_tables = []
        self.dropped_tables = []
        self.created_indexes = []
        self.dropped_indexes = []
        self.added_columns = []
        self.dropped_columns = []

    def create_table(self, name, *cols_and_constraints, **_kwargs):
        self.created_tables.append((name, list(cols_and_constraints)))

    def drop_table(self, name, **_kwargs):
        self.dropped_tables.append(name)

    def create_index(self, name, table_name, columns, **kwargs):
        self.created_indexes.append((name, table_name, tuple(columns), kwargs))

    def drop_index(self, name, table_name=None, **_kwargs):
        self.dropped_indexes.append((name, table_name))

    def add_column(self, table_name, column, **_kwargs):
        self.added_columns.append((table_name, column))

    def drop_column(self, table_name, column_name, **_kwargs):
        self.dropped_columns.append((table_name, column_name))


@pytest.fixture
def patched_op(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr("alembic.op.create_table", recorder.create_table)
    monkeypatch.setattr("alembic.op.drop_table", recorder.drop_table)
    monkeypatch.setattr("alembic.op.create_index", recorder.create_index)
    monkeypatch.setattr("alembic.op.drop_index", recorder.drop_index)
    monkeypatch.setattr("alembic.op.add_column", recorder.add_column)
    monkeypatch.setattr("alembic.op.drop_column", recorder.drop_column)
    return recorder


def _columns_of(created_tables, table_name):
    for name, cols in created_tables:
        if name == table_name:
            return [c for c in cols if isinstance(c, sa.Column)]
    raise AssertionError(f"table {table_name} non créée")


# ------------------------------------------------------------------------------
#  0035 — session_facture + session_trame.synthese_llm_texte
# ------------------------------------------------------------------------------
@pytest.fixture
def migration_0035(patched_op):
    mod = _load_migration_module("0035_session_facture.py", "migration_0035_session_facture")
    return mod, patched_op


def test_0035_upgrade_creates_session_facture(migration_0035):
    mod, recorder = migration_0035
    mod.upgrade()
    assert [n for n, _ in recorder.created_tables] == ["session_facture"]

    cols = {c.name: c for c in _columns_of(recorder.created_tables, "session_facture")}
    expected = {
        "id", "session_id", "categorie_slug", "storage_key", "nom_fichier", "statut",
        "extraction", "reponses_appliquees", "erreur", "cree_le", "analysee_le",
    }
    assert set(cols) == expected
    assert isinstance(cols["id"].type, postgresql.UUID)
    assert cols["storage_key"].nullable is False
    assert cols["statut"].server_default is not None


def test_0035_upgrade_foreign_keys(migration_0035):
    mod, recorder = migration_0035
    mod.upgrade()
    cols = {c.name: c for c in _columns_of(recorder.created_tables, "session_facture")}
    fks = {(name, fk.target_fullname) for name, c in cols.items() for fk in c.foreign_keys}
    assert ("session_id", "session_trame.id") in fks
    assert ("categorie_slug", "categorie.slug") in fks


def test_0035_upgrade_adds_synthese_llm_texte_column(migration_0035):
    mod, recorder = migration_0035
    mod.upgrade()
    assert len(recorder.added_columns) == 1
    table_name, column = recorder.added_columns[0]
    assert table_name == "session_trame"
    assert column.name == "synthese_llm_texte"
    assert isinstance(column.type, sa.Text)
    assert column.nullable is True


def test_0035_downgrade_reverses_upgrade(migration_0035):
    mod, recorder = migration_0035
    mod.upgrade()
    created_index_names = {name for name, *_ in recorder.created_indexes}
    mod.downgrade()
    assert recorder.dropped_tables == ["session_facture"]
    assert {name for name, _ in recorder.dropped_indexes} == created_index_names
    assert recorder.dropped_columns == [("session_trame", "synthese_llm_texte")]


# ------------------------------------------------------------------------------
#  0036 — rapport_veille_marche
# ------------------------------------------------------------------------------
@pytest.fixture
def migration_0036(patched_op):
    mod = _load_migration_module("0036_rapport_veille_marche.py", "migration_0036_rapport_veille_marche")
    return mod, patched_op


def test_0036_upgrade_creates_rapport_veille_marche(migration_0036):
    mod, recorder = migration_0036
    mod.upgrade()
    assert [n for n, _ in recorder.created_tables] == ["rapport_veille_marche"]

    cols = {c.name: c for c in _columns_of(recorder.created_tables, "rapport_veille_marche")}
    expected = {"id", "categorie_slug", "semaine_debut", "offres_detectees", "statut", "cree_le"}
    assert set(cols) == expected
    assert isinstance(cols["id"].type, postgresql.UUID)
    assert isinstance(cols["offres_detectees"].type, postgresql.JSONB)
    assert cols["semaine_debut"].nullable is False


def test_0036_upgrade_foreign_key_and_index(migration_0036):
    mod, recorder = migration_0036
    mod.upgrade()
    cols = {c.name: c for c in _columns_of(recorder.created_tables, "rapport_veille_marche")}
    fks = {(name, fk.target_fullname) for name, c in cols.items() for fk in c.foreign_keys}
    assert ("categorie_slug", "categorie.slug") in fks

    name, table, columns, kwargs = recorder.created_indexes[0]
    assert name == "idx_rapport_veille_marche_statut"
    assert table == "rapport_veille_marche"
    assert columns == ("statut",)
    assert "en_attente" in str(kwargs.get("postgresql_where"))


def test_0036_downgrade_reverses_upgrade(migration_0036):
    mod, recorder = migration_0036
    mod.upgrade()
    mod.downgrade()
    assert recorder.dropped_tables == ["rapport_veille_marche"]
    assert recorder.dropped_indexes == [("idx_rapport_veille_marche_statut", "rapport_veille_marche")]
