# ==============================================================================
#  TESTS D'INTÉGRITÉ — migration 0032 (fondations IA Conseil, §0.1).
#
#  Deux niveaux :
#  - test_structure_* : hors-ligne, sans DB (même idiome que le reste du
#    projet où « Postgres non provisionné en dev/CI », voir conftest.py) —
#    monkeypatch les fonctions `alembic.op.*` pour enregistrer les opérations
#    DDL réellement émises par upgrade()/downgrade(), puis vérifie tables,
#    colonnes, FK, contraintes, index, et la symétrie up/down.
#  - test_migration_reelle_up_down_up : contre une vraie base Postgres,
#    ignoré par défaut (IA_CONSEIL_MIGRATION_DB_TEST=1 pour l'activer) — a
#    déjà été exécuté manuellement avec succès contre la base Neon de
#    backend/.env (upgrade head → downgrade -1 → upgrade head), voir
#    historique de la tâche 1 du plan.
# ==============================================================================
import importlib.util
import os

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Le nom de fichier commence par un chiffre (convention de revision Alembic) :
# pas importable via `import backend.alembic.versions.0032_...` (identifiant
# Python invalide). On charge le module par chemin de fichier, comme le fait
# Alembic lui-même en interne (alembic.script.base.Script._load_python_file).
_MIGRATION_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "alembic", "versions", "0032_ia_conseil_fondations.py",
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_0032_ia_conseil", _MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

EXPECTED_TABLE_ORDER = [
    "categorie",
    "fournisseur",
    "offre",
    "trame_template",
    "regle_recommandation",
    "client",
    "session_trame",
    "recommandation",
    "souscription",
]

EXPECTED_COLUMNS = {
    "categorie": {"id", "slug", "nom", "ordre", "actif"},
    "fournisseur": {"id", "nom", "categorie_slug", "note_fiabilite", "logo_url", "site_url", "affilie", "taux_commission"},
    "offre": {
        "id", "fournisseur_id", "categorie_slug", "nom", "prix_mensuel", "prix_apres_promo",
        "duree_promo_mois", "engagement_mois", "frais_mise_en_service", "caracteristiques",
        "conditions", "source", "source_ref", "valide", "date_maj",
    },
    "trame_template": {"id", "categorie_slug", "version", "definition", "actif"},
    "regle_recommandation": {"id", "categorie_slug", "nom", "type", "priorite", "condition", "action", "actif"},
    "client": {"id", "conseiller_id", "prenom", "nom", "email", "telephone", "adresse", "foyer", "profil", "cree_le"},
    "session_trame": {
        "id", "client_id", "conseiller_id", "categorie_slug", "trame_template_id", "reponses",
        "etat", "canal", "demarree_le", "terminee_le",
    },
    "recommandation": {
        "id", "session_id", "offre_id", "score", "rang", "justifications", "alertes",
        "economie_mensuelle", "economie_annuelle",
    },
    "souscription": {
        "id", "client_id", "offre_id", "session_id", "conseiller_id", "date_souscription",
        "date_activation", "prix_mensuel_negocie", "commission_prevue", "commission_encaissee",
        "statut", "fin_engagement",
    },
}

# (colonne, table_cible, colonne_cible) — d'après §0.1 (conseiller_id -> utilisateurs.id
# en Integer : décision produit, voir docstring de la migration).
EXPECTED_FOREIGN_KEYS = {
    "fournisseur": {("categorie_slug", "categorie.slug")},
    "offre": {("categorie_slug", "categorie.slug"), ("fournisseur_id", "fournisseur.id")},
    "trame_template": {("categorie_slug", "categorie.slug")},
    "regle_recommandation": {("categorie_slug", "categorie.slug")},
    "client": {("conseiller_id", "utilisateurs.id")},
    "session_trame": {
        ("client_id", "client.id"),
        ("conseiller_id", "utilisateurs.id"),
        ("categorie_slug", "categorie.slug"),
        ("trame_template_id", "trame_template.id"),
    },
    "recommandation": {("session_id", "session_trame.id"), ("offre_id", "offre.id")},
    "souscription": {
        ("client_id", "client.id"),
        ("offre_id", "offre.id"),
        ("session_id", "session_trame.id"),
        ("conseiller_id", "utilisateurs.id"),
    },
}


class _Recorder:
    """Enregistre les appels op.create_table/create_index/drop_index/drop_table
    sans jamais toucher de connexion réelle (les fonctions alembic.op sont
    remplacées entièrement, donc aucun contexte de migration n'est requis)."""

    def __init__(self):
        self.created_tables = []  # [(name, [Column|Constraint, ...])]
        self.dropped_tables = []  # [name]
        self.created_indexes = []  # [(name, table, columns, kwargs)]
        self.dropped_indexes = []  # [(name, table)]

    def create_table(self, name, *cols_and_constraints, **_kwargs):
        self.created_tables.append((name, list(cols_and_constraints)))

    def drop_table(self, name, **_kwargs):
        self.dropped_tables.append(name)

    def create_index(self, name, table_name, columns, **kwargs):
        self.created_indexes.append((name, table_name, tuple(columns), kwargs))

    def drop_index(self, name, table_name=None, **_kwargs):
        self.dropped_indexes.append((name, table_name))


@pytest.fixture
def migration(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr("alembic.op.create_table", recorder.create_table)
    monkeypatch.setattr("alembic.op.drop_table", recorder.drop_table)
    monkeypatch.setattr("alembic.op.create_index", recorder.create_index)
    monkeypatch.setattr("alembic.op.drop_index", recorder.drop_index)

    mod = _load_migration_module()
    return mod, recorder


def _columns_of(created_tables, table_name):
    for name, cols in created_tables:
        if name == table_name:
            return [c for c in cols if isinstance(c, sa.Column)]
    raise AssertionError(f"table {table_name} non créée")


def _constraints_of(created_tables, table_name, cls):
    for name, cols in created_tables:
        if name == table_name:
            return [c for c in cols if isinstance(c, cls)]
    raise AssertionError(f"table {table_name} non créée")


def test_upgrade_creates_all_tables_in_dependency_order(migration):
    mod, recorder = migration
    mod.upgrade()
    created_names = [name for name, _ in recorder.created_tables]
    assert created_names == EXPECTED_TABLE_ORDER


def test_downgrade_drops_all_tables_in_reverse_order(migration):
    mod, recorder = migration
    mod.downgrade()
    assert recorder.dropped_tables == list(reversed(EXPECTED_TABLE_ORDER))


def test_upgrade_column_sets_match_plan(migration):
    mod, recorder = migration
    mod.upgrade()
    for table, expected in EXPECTED_COLUMNS.items():
        actual = {c.name for c in _columns_of(recorder.created_tables, table)}
        assert actual == expected, f"{table}: {actual} != {expected}"


def test_upgrade_primary_keys_are_uuid_except_conseiller_ref(migration):
    mod, recorder = migration
    mod.upgrade()
    for table in EXPECTED_TABLE_ORDER:
        cols = {c.name: c for c in _columns_of(recorder.created_tables, table)}
        pk = cols["id"]
        assert pk.primary_key is True
        assert isinstance(pk.type, postgresql.UUID), f"{table}.id devrait être UUID"
    # conseiller_id référence utilisateurs.id (Integer), pas UUID — décision produit.
    for table in ("client", "session_trame", "souscription"):
        cols = {c.name: c for c in _columns_of(recorder.created_tables, table)}
        assert isinstance(cols["conseiller_id"].type, sa.Integer)


def test_upgrade_foreign_keys_match_plan(migration):
    mod, recorder = migration
    mod.upgrade()
    for table, expected_fks in EXPECTED_FOREIGN_KEYS.items():
        cols = {c.name: c for c in _columns_of(recorder.created_tables, table)}
        actual_fks = set()
        for col_name, col in cols.items():
            for fk in col.foreign_keys:
                actual_fks.add((col_name, fk.target_fullname))
        assert actual_fks == expected_fks, f"{table}: {actual_fks} != {expected_fks}"


def test_upgrade_regle_recommandation_has_type_check_constraint(migration):
    mod, recorder = migration
    mod.upgrade()
    cols = {c.name: c for c in _columns_of(recorder.created_tables, "regle_recommandation")}
    checks = [c for c in cols["type"].constraints if isinstance(c, sa.CheckConstraint)]
    assert len(checks) == 1
    assert "filtre" in str(checks[0].sqltext) and "scoring" in str(checks[0].sqltext) and "alerte" in str(checks[0].sqltext)


def test_upgrade_unique_constraints(migration):
    mod, recorder = migration
    mod.upgrade()
    offre_uniques = _constraints_of(recorder.created_tables, "offre", sa.UniqueConstraint)
    assert any(set(u._pending_colargs) == {"fournisseur_id", "nom"} for u in offre_uniques)

    trame_uniques = _constraints_of(recorder.created_tables, "trame_template", sa.UniqueConstraint)
    assert any(set(u._pending_colargs) == {"categorie_slug", "version"} for u in trame_uniques)

    categorie_slug_col = next(c for c in _columns_of(recorder.created_tables, "categorie") if c.name == "slug")
    assert categorie_slug_col.unique is True


def test_upgrade_indexes_match_plan(migration):
    mod, recorder = migration
    mod.upgrade()
    by_name = {name: (table, cols, kwargs) for name, table, cols, kwargs in recorder.created_indexes}

    table, cols, kwargs = by_name["idx_offre_categorie"]
    assert table == "offre" and cols == ("categorie_slug",)
    assert "valide = true" in str(kwargs.get("postgresql_where"))

    table, cols, kwargs = by_name["idx_offre_caract"]
    assert table == "offre" and cols == ("caracteristiques",)
    assert kwargs.get("postgresql_using") == "gin"

    table, cols, kwargs = by_name["idx_souscription_conseiller"]
    assert table == "souscription" and cols == ("conseiller_id", "date_souscription")

    table, cols, kwargs = by_name["idx_souscription_fin_engagement"]
    assert table == "souscription" and cols == ("fin_engagement",)
    assert "statut = 'active'" in str(kwargs.get("postgresql_where"))


def test_downgrade_drops_every_index_created_by_upgrade(migration):
    mod, recorder = migration
    mod.upgrade()
    created_index_names = {name for name, *_ in recorder.created_indexes}
    mod.downgrade()
    dropped_index_names = {name for name, _ in recorder.dropped_indexes}
    assert dropped_index_names == created_index_names


def test_offre_caracteristiques_is_jsonb_not_json(migration):
    mod, recorder = migration
    mod.upgrade()
    cols = {c.name: c for c in _columns_of(recorder.created_tables, "offre")}
    # GIN index sur caracteristiques : nécessite JSONB (JSON simple non indexable en GIN).
    assert isinstance(cols["caracteristiques"].type, postgresql.JSONB)
    assert cols["caracteristiques"].nullable is False


@pytest.mark.skipif(
    not os.environ.get("IA_CONSEIL_MIGRATION_DB_TEST"),
    reason="Vérification contre une vraie base Postgres — opt-in via IA_CONSEIL_MIGRATION_DB_TEST=1 "
    "(déjà exécutée manuellement avec succès contre Neon lors de la tâche 1, voir docstring du module).",
)
def test_migration_reelle_up_down_up():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cfg = Config(os.path.join(repo_root, "alembic.ini"))

    sync_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    cfg.set_main_option("sqlalchemy.url", sync_url)

    command.upgrade(cfg, "0031:0032")
    engine = create_engine(sync_url)
    try:
        tables = inspect(engine).get_table_names()
        for t in EXPECTED_TABLE_ORDER:
            assert t in tables
    finally:
        engine.dispose()

    command.downgrade(cfg, "0032:0031")
    engine = create_engine(sync_url)
    try:
        tables = inspect(engine).get_table_names()
        for t in EXPECTED_TABLE_ORDER:
            assert t not in tables
    finally:
        engine.dispose()

    command.upgrade(cfg, "0031:0032")
