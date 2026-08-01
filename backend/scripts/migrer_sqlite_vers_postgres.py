# ==============================================================================
#  MIGRATION SQLITE → POSTGRES (à usage unique) — bascule les données du CRM
#  Streamlit (src/ia_conseil_crm.db) vers le backend/ (Postgres). Voir
#  backend/scripts/README.md pour la démarche complète.
#
#  Ne dépend pas de src/db.py (module couplé à Streamlit, `import streamlit`
#  au niveau module) : lit directement le fichier SQLite via sqlite3.
#
#  Usage :
#      python -m backend.scripts.migrer_sqlite_vers_postgres --sqlite-path src/ia_conseil_crm.db
# ==============================================================================
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from sqlalchemy import Column, MetaData, String, Table, create_engine, func, select, text
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.client import Client
from backend.models.contrat import Contrat
from backend.models.document_prospect import DocumentProspect
from backend.models.offre import Offre
from backend.models.parametre import Parametre
from backend.models.prospect import Prospect
from backend.models.user import User
from backend.models.veille import SourceVeille, VeilleAlerte, VeilleHistoriquePrix
from backend.services.storage_engine import StorageError, upload_fichier

# Table de correspondance d'ids — hors Alembic (artefact opérationnel de la
# migration, pas du schéma applicatif). `ancien_id`/`nouvel_id` en texte pour
# accueillir aussi bien des ids entiers (SQLite → Postgres) qu'une clé texte
# (parametres.cle, qui n'a pas besoin de remapping mais profite du même
# mécanisme de déduplication ligne par ligne).
_MIGRATION_META = MetaData()
MIGRATION_ID_MAP = Table(
    "migration_id_map",
    _MIGRATION_META,
    Column("entity_type", String, primary_key=True),
    Column("ancien_id", String, primary_key=True),
    Column("nouvel_id", String, nullable=False),
)

# Tables Postgres ciblées par la migration, dans l'ordre des dépendances FK.
# Hors périmètre (aucune source SQLite) : dossiers, mandats, demarches,
# documents (KYC), commissions, mandat_honoraires, factures_analysees,
# tokens_publics — natifs backend/.
TABLES_CIBLES = [
    "utilisateurs", "offres", "clients", "prospects", "contrats",
    "parametres", "sources_veille", "veille_historique_prix",
    "veille_alertes", "documents_prospect",
]


def _pg_engine():
    # psycopg2 attend `sslmode=require`, pas le `ssl=require` d'asyncpg/Neon —
    # sans cette traduction, psycopg2 rejette le DSN ("invalid connection
    # option \"ssl\"").
    url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("ssl=require", "sslmode=require")
    return create_engine(url)


def _val(row: sqlite3.Row, col: str, default=None):
    """Lecture tolérante d'une colonne SQLite — certaines colonnes n'existent
    que sur des bases ayant reçu la migration incrémentale src/db.py::_migrer_bdd()."""
    try:
        return row[col]
    except (IndexError, KeyError):
        return default


def _bool(v, default: bool = False) -> bool:
    if v is None:
        return default
    return bool(v)


def _deja_mappe(session: Session, entity_type: str, ancien_id) -> str | None:
    """Retourne le nouvel id Postgres si `ancien_id` a déjà été migré pour ce
    type d'entité (déduplication ligne par ligne, permet de relancer le
    script après un arrêt sans dupliquer ce qui a déjà été écrit). Sert aussi
    de résolveur de FK inter-entités (ex. contrats.client_id)."""
    if ancien_id is None:
        return None
    row = session.execute(
        select(MIGRATION_ID_MAP.c.nouvel_id).where(
            MIGRATION_ID_MAP.c.entity_type == entity_type,
            MIGRATION_ID_MAP.c.ancien_id == str(ancien_id),
        )
    ).first()
    return row[0] if row else None


def _enregistrer_mapping(session: Session, entity_type: str, ancien_id, nouvel_id) -> None:
    session.execute(
        MIGRATION_ID_MAP.insert().values(
            entity_type=entity_type, ancien_id=str(ancien_id), nouvel_id=str(nouvel_id),
        )
    )


def _lignes(sqlite_conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608 — table name from fixed internal list


def _verifier_migration_possible(session: Session, sqlite_conn: sqlite3.Connection) -> None:
    """Migration à usage unique : si `migration_id_map` est vide (premier
    lancement), les tables cibles Postgres doivent l'être aussi — on refuse
    d'écrire par-dessus des données existantes non issues de cette migration.
    Si `migration_id_map` contient déjà des entrées, c'est une reprise après
    un arrêt précédent : pas de nouvelle vérification globale, la
    déduplication se fait ligne par ligne via _deja_mappe()."""
    deja_commence = session.execute(select(func.count()).select_from(MIGRATION_ID_MAP)).scalar()
    if deja_commence:
        print(f"Reprise : {deja_commence} ligne(s) déjà migrée(s) précédemment (migration_id_map).")
        return
    for table in TABLES_CIBLES:
        count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()  # noqa: S608
        if count:
            raise RuntimeError(
                f"La table Postgres « {table} » contient déjà {count} ligne(s). "
                "Cette migration est à usage unique et refuse d'écrire sur des données "
                "existantes. Si c'est une reprise après un arrêt, ne supprimez pas "
                "la table migration_id_map."
            )


def migrer_utilisateurs(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    n = 0
    for row in _lignes(sqlite_conn, "utilisateurs"):
        if _deja_mappe(session, "utilisateur", row["id"]):
            continue
        user = User(
            username=row["username"],
            nom_complet=row["nom_complet"],
            password_hash=row["password_hash"],
            role=_val(row, "role") or "Conseiller",
            actif=_bool(_val(row, "actif", 1), True),
            date_creation=_val(row, "date_creation"),
            doit_changer_mdp=_bool(_val(row, "doit_changer_mdp", 0)),
        )
        session.add(user)
        session.flush()
        _enregistrer_mapping(session, "utilisateur", row["id"], user.id)
        n += 1
    session.commit()
    print(f"utilisateurs : {n} migré(s)")


def migrer_offres(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    n = 0
    for row in _lignes(sqlite_conn, "offres"):
        if _deja_mappe(session, "offre", row["id"]):
            continue
        offre = Offre(
            univers=_val(row, "univers"),
            categorie=_val(row, "categorie"),
            fournisseur=_val(row, "fournisseur"),
            nom_offre=_val(row, "nom_offre"),
            prix_mensuel=_val(row, "prix_mensuel"),
            frais_activation=_val(row, "frais_activation"),
            engagement_mois=_val(row, "engagement_mois"),
            caracteristiques=_val(row, "caracteristiques"),
            commission_affiliation=_val(row, "commission_affiliation"),
            data_go=_val(row, "data_go", 0),
            actif=_bool(_val(row, "actif", 1), True),
            url_souscription=_val(row, "url_souscription"),
            code_affiliation=_val(row, "code_affiliation"),
            date_maj=_val(row, "date_maj"),
        )
        session.add(offre)
        session.flush()
        _enregistrer_mapping(session, "offre", row["id"], offre.id)
        n += 1
    session.commit()
    print(f"offres : {n} migrée(s)")


def migrer_clients(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    n_crees = 0
    n_reutilises = 0
    c = sqlite_conn.cursor()
    for row in _lignes(sqlite_conn, "clients"):
        if _deja_mappe(session, "client", row["id"]):
            continue
        # Cohabitation avec src/api_client.py::_backend_client_id_pour() : si ce
        # client a déjà un miroir Postgres créé à la volée avant la migration,
        # on réutilise cet id plutôt que d'en créer un second.
        backend_id_existant = _val(row, "backend_client_id")
        if backend_id_existant:
            _enregistrer_mapping(session, "client", row["id"], backend_id_existant)
            n_reutilises += 1
            continue
        client = Client(
            ref=_val(row, "ref"), prenom=_val(row, "prenom"), nom=_val(row, "nom"),
            telephone=_val(row, "telephone"), email=_val(row, "email"),
            code_postal=_val(row, "code_postal"), ville=_val(row, "ville"),
            adresse=_val(row, "adresse"), type_client=_val(row, "type_client"),
            operateur_actuel=_val(row, "operateur_actuel"), techno=_val(row, "techno"),
            data_go=_val(row, "data_go"), offre_actuelle=_val(row, "offre_actuelle"),
            cout_mensuel_actuel=_val(row, "cout_mensuel_actuel", 0),
            satisfaction_reseau=_val(row, "satisfaction_reseau"), veut_rester=_val(row, "veut_rester"),
            speed_down=_val(row, "speed_down", 0), speed_up=_val(row, "speed_up", 0),
            fournisseur_energie=_val(row, "fournisseur_energie"),
            cout_elec=_val(row, "cout_elec", 0), cout_gaz=_val(row, "cout_gaz", 0),
            economie_estimee_an=_val(row, "economie_estimee_an", 0),
            notes=_val(row, "notes"), date_creation=_val(row, "date_creation"),
            cree_par=_val(row, "cree_par"), date_relance=_val(row, "date_relance"),
            statut_relance=_val(row, "statut_relance") or "Aucune",
        )
        session.add(client)
        session.flush()
        _enregistrer_mapping(session, "client", row["id"], client.id)
        c.execute("UPDATE clients SET backend_client_id=? WHERE id=?", (client.id, row["id"]))
        n_crees += 1
    sqlite_conn.commit()
    session.commit()
    print(f"clients : {n_crees} créé(s), {n_reutilises} réutilisé(s) (déjà mirorés par _backend_client_id_pour)")


def migrer_prospects(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    n_crees = 0
    n_reutilises = 0
    c = sqlite_conn.cursor()
    for row in _lignes(sqlite_conn, "prospects"):
        if _deja_mappe(session, "prospect", row["id"]):
            continue
        backend_id_existant = _val(row, "backend_client_id")
        if backend_id_existant:
            _enregistrer_mapping(session, "prospect", row["id"], backend_id_existant)
            n_reutilises += 1
            continue
        prospect = Prospect(
            ref=_val(row, "ref"), prenom=_val(row, "prenom"), nom=_val(row, "nom"),
            telephone=_val(row, "telephone"), email=_val(row, "email"),
            code_postal=_val(row, "code_postal"), ville=_val(row, "ville"),
            adresse=_val(row, "adresse"), type_client=_val(row, "type_client"),
            univers_interesse=_val(row, "univers_interesse"),
            service_principal=_val(row, "service_principal"),
            operateur_actuel=_val(row, "operateur_actuel"), techno=_val(row, "techno"),
            data_go=_val(row, "data_go"),
            cout_mensuel_actuel=_val(row, "cout_mensuel_actuel", 0),
            offre_actuelle=_val(row, "offre_actuelle"),
            satisfaction_reseau=_val(row, "satisfaction_reseau"), veut_rester=_val(row, "veut_rester"),
            speed_down=_val(row, "speed_down", 0), speed_up=_val(row, "speed_up", 0),
            cout_elec=_val(row, "cout_elec", 0), cout_gaz=_val(row, "cout_gaz", 0),
            fournisseur_energie=_val(row, "fournisseur_energie"),
            abonnements=_val(row, "abonnements"), lignes_multi=_val(row, "lignes_multi"),
            economie_estimee_an=_val(row, "economie_estimee_an", 0),
            notes=_val(row, "notes"), statut=_val(row, "statut") or "À relancer",
            date_creation=_val(row, "date_creation"), date_relance=_val(row, "date_relance"),
            cree_par=_val(row, "cree_par"), offres_interet=_val(row, "offres_interet"),
            score=_val(row, "score", 0), origine=_val(row, "origine") or "Manuel",
        )
        session.add(prospect)
        session.flush()
        _enregistrer_mapping(session, "prospect", row["id"], prospect.id)
        c.execute("UPDATE prospects SET backend_client_id=? WHERE id=?", (prospect.id, row["id"]))
        n_crees += 1
    sqlite_conn.commit()
    session.commit()
    print(f"prospects : {n_crees} créé(s), {n_reutilises} réutilisé(s) (déjà mirorés par _backend_client_id_pour)")


def migrer_contrats(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    n = 0
    n_ignores = 0
    for row in _lignes(sqlite_conn, "contrats"):
        if _deja_mappe(session, "contrat", row["id"]):
            continue
        ancien_client_id = _val(row, "client_id")
        if not ancien_client_id:
            # Contrat rattaché uniquement à un prospect (type_contrat="reference_externe") —
            # backend/models/contrat.py n'a pas de colonne prospect_id, hors périmètre ici.
            n_ignores += 1
            continue
        nouveau_client_id = _deja_mappe(session, "client", ancien_client_id)
        if nouveau_client_id is None:
            print(f"  ! contrat {row['id']} ignoré : client {ancien_client_id} non migré")
            n_ignores += 1
            continue
        contrat = Contrat(
            client_id=int(nouveau_client_id),
            univers=_val(row, "univers"), categorie=_val(row, "categorie"),
            fournisseur=_val(row, "fournisseur"), nom_offre=_val(row, "nom_offre"),
            cout_mensuel=_val(row, "cout_mensuel", 0), economie_mensuelle=_val(row, "economie_mensuelle", 0),
            reference_contrat=_val(row, "reference_contrat"), statut_contrat=_val(row, "statut_contrat"),
            date_souscription=_val(row, "date_souscription"), date_fin_engagement=_val(row, "date_fin_engagement"),
            notes=_val(row, "notes"), cree_par=_val(row, "cree_par"),
        )
        session.add(contrat)
        session.flush()
        _enregistrer_mapping(session, "contrat", row["id"], contrat.id)
        n += 1
    session.commit()
    print(f"contrats : {n} migré(s), {n_ignores} ignoré(s) (rattachés à un prospect uniquement, ou client non migré)")


def migrer_parametres(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    n = 0
    for row in _lignes(sqlite_conn, "parametres"):
        if _deja_mappe(session, "parametre", row["cle"]):
            continue
        existant = session.get(Parametre, row["cle"])
        if existant is None:
            session.add(Parametre(cle=row["cle"], valeur=row["valeur"]))
        else:
            existant.valeur = row["valeur"]
        _enregistrer_mapping(session, "parametre", row["cle"], row["cle"])
        n += 1
    session.commit()
    print(f"parametres : {n} migré(s)")


def migrer_sources_veille(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    n = 0
    for row in _lignes(sqlite_conn, "sources_veille"):
        if _deja_mappe(session, "source_veille", row["id"]):
            continue
        ancien_offre_id = _val(row, "offre_id")
        nouvel_offre_id = None
        if ancien_offre_id:
            m = _deja_mappe(session, "offre", ancien_offre_id)
            nouvel_offre_id = int(m) if m else None
        source = SourceVeille(
            univers=_val(row, "univers"), categorie=_val(row, "categorie"),
            fournisseur=_val(row, "fournisseur"), nom_offre=_val(row, "nom_offre"),
            offre_id=nouvel_offre_id, url=_val(row, "url"), selecteur_prix=_val(row, "selecteur_prix"),
            actif=_bool(_val(row, "actif", 1), True), dernier_prix=_val(row, "dernier_prix"),
            date_derniere_verif=_val(row, "date_derniere_verif"), date_creation=_val(row, "date_creation"),
        )
        session.add(source)
        session.flush()
        _enregistrer_mapping(session, "source_veille", row["id"], source.id)
        n += 1
    session.commit()
    print(f"sources_veille : {n} migrée(s)")


def migrer_veille_historique(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    n = 0
    n_ignores = 0
    for row in _lignes(sqlite_conn, "veille_historique_prix"):
        if _deja_mappe(session, "veille_historique_prix", row["id"]):
            continue
        m = _deja_mappe(session, "source_veille", _val(row, "source_id"))
        if m is None:
            n_ignores += 1
            continue
        historique = VeilleHistoriquePrix(
            source_id=int(m), prix=_val(row, "prix"), date_releve=_val(row, "date_releve"),
        )
        session.add(historique)
        session.flush()
        _enregistrer_mapping(session, "veille_historique_prix", row["id"], historique.id)
        n += 1
    session.commit()
    print(f"veille_historique_prix : {n} migré(s), {n_ignores} ignoré(s) (source non migrée)")


def migrer_veille_alertes(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    n = 0
    n_ignores = 0
    for row in _lignes(sqlite_conn, "veille_alertes"):
        if _deja_mappe(session, "veille_alerte", row["id"]):
            continue
        m = _deja_mappe(session, "source_veille", _val(row, "source_id"))
        if m is None:
            n_ignores += 1
            continue
        alerte = VeilleAlerte(
            source_id=int(m), ancien_prix=_val(row, "ancien_prix"), nouveau_prix=_val(row, "nouveau_prix"),
            statut=_val(row, "statut") or "en_attente", date_detection=_val(row, "date_detection"),
            date_traitement=_val(row, "date_traitement"),
        )
        session.add(alerte)
        session.flush()
        _enregistrer_mapping(session, "veille_alerte", row["id"], alerte.id)
        n += 1
    session.commit()
    print(f"veille_alertes : {n} migrée(s), {n_ignores} ignorée(s) (source non migrée)")


def migrer_documents_prospect(sqlite_conn: sqlite3.Connection, session: Session) -> None:
    """Étape la plus lente/fragile (upload S3 par fichier) — commit ligne par
    ligne pour qu'un échec en cours de route ne perde pas les fichiers déjà
    uploadés (la déduplication via migration_id_map rend le relancement sûr)."""
    n = 0
    n_ignores = 0
    for row in _lignes(sqlite_conn, "documents_prospect"):
        if _deja_mappe(session, "document_prospect", row["id"]):
            continue
        nouveau_prospect_id = _deja_mappe(session, "prospect", _val(row, "prospect_id"))
        if nouveau_prospect_id is None:
            print(f"  ! document {row['id']} ignoré : prospect {_val(row, 'prospect_id')} non migré")
            n_ignores += 1
            continue
        contenu = _val(row, "contenu")
        if not contenu:
            n_ignores += 1
            continue
        nom_fichier = _val(row, "nom_fichier") or f"document_{row['id']}.bin"
        type_document = _val(row, "type_document") or "facture"
        try:
            cle = upload_fichier(
                prefixe=f"prospects/{nouveau_prospect_id}", type_document=type_document,
                contenu=bytes(contenu), nom_fichier=nom_fichier,
            )
        except StorageError as exc:
            print(f"  ! document {row['id']} ignoré : échec upload ({exc})")
            n_ignores += 1
            continue
        doc = DocumentProspect(
            prospect_id=int(nouveau_prospect_id), type_document=type_document, nom_fichier=nom_fichier,
            cle_stockage=cle, mime=_val(row, "mime"), date_upload=_val(row, "date_upload"),
        )
        session.add(doc)
        session.flush()
        _enregistrer_mapping(session, "document_prospect", row["id"], doc.id)
        session.commit()
        n += 1
    print(f"documents_prospect : {n} migré(s), {n_ignores} ignoré(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        default=str(Path(__file__).resolve().parent.parent.parent / "src" / "ia_conseil_crm.db"),
        help="Chemin vers la base SQLite source (défaut : src/ia_conseil_crm.db).",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.is_file():
        raise SystemExit(f"Base SQLite introuvable : {sqlite_path}")

    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    engine = _pg_engine()
    MIGRATION_ID_MAP.create(engine, checkfirst=True)

    with Session(engine) as session:
        _verifier_migration_possible(session, sqlite_conn)

        migrer_utilisateurs(sqlite_conn, session)
        migrer_offres(sqlite_conn, session)
        migrer_clients(sqlite_conn, session)
        migrer_prospects(sqlite_conn, session)
        migrer_contrats(sqlite_conn, session)
        migrer_parametres(sqlite_conn, session)
        migrer_sources_veille(sqlite_conn, session)
        migrer_veille_historique(sqlite_conn, session)
        migrer_veille_alertes(sqlite_conn, session)
        migrer_documents_prospect(sqlite_conn, session)

    sqlite_conn.close()
    print("Migration terminée.")


if __name__ == "__main__":
    main()
