# ==============================================================================
#  SEED IA CONSEIL — peuple le sous-système neuf (categorie/fournisseur/offre/
#  trame_template/regle_recommandation, migration 0032) avec un jeu de données
#  de test pour la catégorie "mobile" : la trame adaptative complète, 20
#  offres et 15 règles de recommandation. PLAN_IMPLEMENTATION_4_PHASES.md
#  §Phase 0, tâche 7. Prix et caractéristiques indicatifs — usage dev/test
#  uniquement, ne pas exécuter en prod.
#
#  Usage :
#      python -m backend.scripts.seed_ia_conseil
# ==============================================================================
from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.ia_conseil import Categorie, Fournisseur, OffreConseil, RegleRecommandation, TrameTemplate

CATEGORIE_SLUG = "mobile"


def _pg_engine():
    # psycopg2 attend `sslmode=require`, pas le `ssl=require` d'asyncpg/Neon —
    # sans cette traduction, psycopg2 rejette le DSN (voir seed_catalogue.py).
    url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("ssl=require", "sslmode=require")
    return create_engine(url)


# ==============================================================================
#  TRAME MOBILE (definition JSONB de trame_template) — §0.2, enrichie des
#  métadonnées escargot §0.1.bis (cout_cognitif, poids_ethique,
#  elimine_offres_si, utilise_par_regles) sur les questions qui font vraiment
#  varier le score de recommandation.
# ==============================================================================
TRAME_MOBILE_V1 = {
    "id": "trame_mobile_v1",
    "categorie": "mobile",
    "sections": [
        {
            "id": "decouverte",
            "titre": "Découverte",
            "questions": [
                {"id": "nb_lignes", "label": "Combien de lignes mobiles dans votre foyer ?", "type": "number", "min": 1, "max": 20, "required": True, "cout_cognitif": 1},
                {"id": "operateur_actuel", "label": "Quel est votre opérateur actuel ?", "type": "select", "options_ref": "operateurs_mobiles", "cout_cognitif": 1},
                {
                    "id": "cout_actuel_mensuel",
                    "label": "Combien payez-vous par mois actuellement ?",
                    "type": "number", "unit": "€",
                    "cout_cognitif": 2,
                },
                {
                    "id": "conso_data_go",
                    "label": "Consommation data mensuelle (regarder facture 3 derniers mois)",
                    "type": "number", "unit": "Go",
                    "help": "Astuce : la moyenne est indiquée en bas de la facture",
                    "required": True,
                    "cout_cognitif": 3,
                    "poids_ethique": 10,
                    "elimine_offres_si": {
                        "reponse_lt_5": {"offre.caracteristiques.data_go": {"$gt": 40}},
                        "reponse_lt_30": {"offre.caracteristiques.data_go": {"$gt": 100}},
                    },
                    "utilise_par_regles": ["anti_survente_data_mobile", "boost_petit_rouleur_mobile", "boost_gros_rouleur_mobile"],
                },
            ],
        },
        {
            "id": "usages",
            "titre": "Vos usages",
            "questions": [
                {
                    "id": "roaming_ue",
                    "label": "Voyagez-vous en Europe ?",
                    "type": "select", "options": ["Jamais", "Occasionnellement", "Souvent"],
                    "cout_cognitif": 1, "poids_ethique": 3,
                    "utilise_par_regles": ["boost_roaming_ue"],
                },
                {
                    "id": "roaming_hors_ue",
                    "label": "Voyagez-vous hors UE ?",
                    "type": "select", "options": ["Jamais", "Occasionnellement", "Souvent"],
                    "show_if": {"roaming_ue": {"$ne": "Jamais"}},
                    "cout_cognitif": 1, "poids_ethique": 2,
                    "utilise_par_regles": ["boost_roaming_hors_ue"],
                },
                {
                    # Remplace l'ancienne question auto-déclarée "Qualité réseau perçue à
                    # votre domicile ?" : on connaît déjà, via les speedtests saisis sur les
                    # fiches prospect/client existantes (Prospect.speed_down, voir
                    # backend/services/ia_conseil_engine.py::_inferer_qualite_reseau), le
                    # débit moyen constaté dans une ville donnée — demander la ville suffit,
                    # inutile de faire deviner une réponse au client. La réponse dérivée est
                    # écrite dans reponses["qualite_reseau"], donc la règle ci-dessous n'a pas
                    # besoin de changer.
                    "id": "ville",
                    "label": "Dans quelle ville habite le client ?",
                    "type": "text",
                    "cout_cognitif": 1, "poids_ethique": 1,
                    "utilise_par_regles": ["boost_qualite_reseau_si_insatisfait"],
                },
                {
                    # Capture informationnelle demandée en plus de l'inférence par ville
                    # ci-dessus (pas de nouvelle règle de scoring) — reportée sur la fiche
                    # prospect/client à la clôture du diagnostic, comme l'étaient les champs
                    # équivalents de l'ancien wizard /diagnostic (Prospect/Client.satisfaction_reseau).
                    "id": "satisfaction_reseau",
                    "label": "Satisfaction du client vis-à-vis de son opérateur actuel ?",
                    "type": "select", "options": ["😀 Très content", "😐 Ça va", "😡 Pas du tout"],
                    "cout_cognitif": 1, "poids_ethique": 2,
                },
                {
                    "id": "defaut_technique",
                    "label": "Défaut technique potentiel constaté sur le réseau actuel ?",
                    "type": "select", "options": ["Faible", "Moyen", "Critique"],
                    "cout_cognitif": 1, "poids_ethique": 1,
                },
                {
                    "id": "veut_rester",
                    "label": "Le client souhaite-t-il rester chez son opérateur actuel ?",
                    "type": "select", "options": ["Oui", "Pas spécialement", "Non"],
                    "cout_cognitif": 1, "poids_ethique": 1,
                },
                {
                    "id": "5g_importante",
                    "label": "La 5G est-elle importante pour vous ?",
                    "type": "boolean",
                    "cout_cognitif": 1, "poids_ethique": 1,
                    "utilise_par_regles": ["boost_5g"],
                },
                {
                    "id": "partage_connexion",
                    "label": "Utilisez-vous le partage de connexion régulièrement ?",
                    "type": "boolean",
                    "cout_cognitif": 1, "poids_ethique": 1,
                    "utilise_par_regles": ["boost_partage_connexion"],
                },
                {
                    "id": "sensibilite_prix",
                    "label": "Ce qui compte le plus pour vous ?",
                    "type": "select", "options": ["Prix avant tout", "Équilibre", "Qualité avant tout"],
                    "cout_cognitif": 1, "poids_ethique": 2,
                    "utilise_par_regles": ["boost_sans_engagement", "boost_qualite_avant_prix"],
                },
            ],
        },
    ],
    "branches": [
        {
            "when": {"nb_lignes": {"$gte": 2}},
            "insert_after": "nb_lignes",
            "questions": [
                {"id": "meme_operateur_famille", "label": "Toutes les lignes chez le même opérateur ?", "type": "boolean", "cout_cognitif": 1, "poids_ethique": 1, "utilise_par_regles": ["boost_meme_operateur_famille"]},
            ],
        },
        {
            "when": {"conso_data_go": {"$lt": 5}},
            "skip": ["5g_importante", "partage_connexion"],
            "flags": ["anti_survente_mobile"],
        },
    ],
}


# ==============================================================================
#  FOURNISSEURS + OFFRES mobiles (20 offres, 10 fournisseurs, 2 chacun) —
#  spectre volontairement large de data_go (2 à 200 Go) et de prix pour que
#  les règles de scoring/alertes ci-dessous aient un effet observable.
# ==============================================================================
_FOURNISSEURS = [
    ("Orange", 0.95, 25),
    ("Sosh", 0.90, 18),
    ("SFR", 0.90, 22),
    ("RED by SFR", 0.85, 15),
    ("Bouygues Telecom", 0.92, 22),
    ("B&You", 0.85, 15),
    ("Free Mobile", 0.90, 20),
    ("Prixtel", 0.80, 12),
    ("YouPrice", 0.75, 12),
    ("Coriolis Telecom", 0.75, 12),
]

# (fournisseur, nom, prix_mensuel, data_go, 5g, roaming_ue, roaming_hors_ue, partage_connexion, reseau_qualite, engagement_mois)
_OFFRES = [
    ("Orange", "Orange 40 Go", 19.99, 40, True, True, False, True, "bonne", 0),
    ("Orange", "Orange 200 Go 5G", 29.99, 200, True, True, True, True, "bonne", 0),
    ("Sosh", "Sosh 40 Go", 14.99, 40, True, True, False, True, "moyenne", 0),
    ("Sosh", "Sosh 100 Go", 19.99, 100, True, True, False, True, "moyenne", 0),
    ("SFR", "SFR 60 Go 5G", 17.99, 60, True, True, False, True, "bonne", 0),
    ("SFR", "SFR 130 Go 5G", 24.99, 130, True, True, True, True, "bonne", 0),
    ("RED by SFR", "RED 90 Go", 12.99, 90, False, True, False, True, "moyenne", 0),
    ("RED by SFR", "RED 200 Go", 15.99, 200, True, True, False, True, "moyenne", 0),
    ("Bouygues Telecom", "Bouygues 60 Go 5G", 14.99, 60, True, True, False, True, "bonne", 0),
    ("Bouygues Telecom", "Bouygues 100 Go 5G", 19.99, 100, True, True, True, True, "bonne", 0),
    ("B&You", "B&You 130 Go", 12.99, 130, True, True, False, True, "moyenne", 0),
    ("B&You", "B&You 200 Go 5G", 17.99, 200, True, True, False, True, "moyenne", 0),
    ("Free Mobile", "Free 2 Go", 2.00, 2, False, False, False, False, "bonne", 0),
    ("Free Mobile", "Free 150 Go 5G", 19.99, 150, True, True, True, True, "bonne", 0),
    ("Prixtel", "Prixtel Le S 5 Go", 6.99, 5, False, False, False, False, "moyenne", 0),
    ("Prixtel", "Prixtel Le XL 130 Go", 15.99, 130, True, True, False, True, "moyenne", 0),
    ("YouPrice", "YouPrice 20 Go", 6.99, 20, False, False, False, False, "moyenne", 0),
    ("YouPrice", "YouPrice 60 Go", 9.99, 60, False, True, False, True, "moyenne", 0),
    ("Coriolis Telecom", "Coriolis 50 Go", 9.99, 50, False, True, False, True, "moyenne", 0),
    ("Coriolis Telecom", "Coriolis 130 Go 5G", 14.99, 130, True, True, False, True, "moyenne", 0),
]


def _construire_fournisseurs() -> dict[str, Fournisseur]:
    return {
        nom: Fournisseur(nom=nom, categorie_slug=CATEGORIE_SLUG, note_fiabilite=fiabilite, affilie=True, taux_commission=commission)
        for nom, fiabilite, commission in _FOURNISSEURS
    }


def _construire_offres(fournisseurs: dict[str, Fournisseur]) -> list[OffreConseil]:
    offres = []
    for fournisseur_nom, nom, prix, data_go, cinq_g, roaming_ue, roaming_hors_ue, partage, reseau, engagement in _OFFRES:
        offres.append(
            OffreConseil(
                fournisseur_id=fournisseurs[fournisseur_nom].id,
                categorie_slug=CATEGORIE_SLUG,
                nom=nom,
                prix_mensuel=prix,
                engagement_mois=engagement,
                caracteristiques={
                    "data_go": data_go,
                    "appels_illim": True,
                    "sms_illim": True,
                    "5g": cinq_g,
                    "roaming_ue": roaming_ue,
                    "roaming_hors_ue": roaming_hors_ue,
                    "partage_connexion": partage,
                    "reseau_qualite": reseau,
                },
                source="manuel",
                valide=True,
            )
        )
    return offres


# ==============================================================================
#  RÈGLES DE RECOMMANDATION mobiles (15) — §0.3.
# ==============================================================================
def _construire_regles() -> list[RegleRecommandation]:
    return [
        RegleRecommandation(
            nom="anti_survente_data_mobile", categorie_slug=CATEGORIE_SLUG, type="alerte", priorite=100,
            condition={"$and": [{"reponses.conso_data_go": {"$lt": 10}}, {"offre.caracteristiques.data_go": {"$gt": 50}}]},
            action={
                "kind": "warn", "severite": "critique",
                "message": "Forfait {{offre.caracteristiques.data_go}} Go proposé alors que le client consomme "
                "{{reponses.conso_data_go}} Go/mois — privilégier un forfait ≤ 40 Go.",
            },
        ),
        RegleRecommandation(
            nom="anti_sous_couverture_data_mobile", categorie_slug=CATEGORIE_SLUG, type="alerte", priorite=100,
            condition={"reponses.conso_data_go": {"$exists": True}},
            action={
                "kind": "warn", "severite": "attention",
                "message": "Vérifier que {{offre.caracteristiques.data_go}} Go couvre bien une consommation de "
                "{{reponses.conso_data_go}} Go/mois.",
            },
        ),
        RegleRecommandation(
            nom="alerte_engagement_si_prix_avant_tout", categorie_slug=CATEGORIE_SLUG, type="alerte", priorite=90,
            # Comparaison à deux chemins dynamiques (prix offre vs coût actuel
            # déclaré) hors de portée du DSL actuel (une seule valeur littérale
            # par opérateur, voir rules_engine/README.md) — alerte formulée
            # uniquement sur des littéraux connus à l'avance.
            condition={"$and": [{"reponses.sensibilite_prix": {"$eq": "Prix avant tout"}}, {"offre.engagement_mois": {"$gt": 0}}]},
            action={
                "kind": "warn", "severite": "attention",
                "message": "Offre avec engagement de {{offre.engagement_mois}} mois alors que le client priorise le prix "
                "— vérifier qu'elle reste la plus avantageuse.",
            },
        ),
        RegleRecommandation(
            nom="boost_petit_rouleur_mobile", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=10,
            condition={"reponses.conso_data_go": {"$lt": 5}},
            action={
                "kind": "score_adjust",
                "bareme": [
                    {"si": {"offre.caracteristiques.data_go": {"$lte": 40}}, "valeur": 30},
                    {"si": {"offre.caracteristiques.data_go": {"$lte": 100}}, "valeur": 0},
                ],
                "defaut": -30,
            },
        ),
        RegleRecommandation(
            nom="boost_gros_rouleur_mobile", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=10,
            condition={"$and": [{"reponses.conso_data_go": {"$gte": 50}}, {"offre.caracteristiques.data_go": {"$gte": 100}}]},
            action={"kind": "score_adjust", "valeur": 20},
        ),
        RegleRecommandation(
            nom="boost_roaming_ue", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=20,
            condition={"$and": [{"reponses.roaming_ue": {"$ne": "Jamais"}}, {"offre.caracteristiques.roaming_ue": True}]},
            action={"kind": "score_adjust", "valeur": 15},
        ),
        RegleRecommandation(
            nom="exclure_sans_roaming_ue_si_souvent", categorie_slug=CATEGORIE_SLUG, type="filtre", priorite=0,
            condition={"$and": [{"reponses.roaming_ue": {"$eq": "Souvent"}}, {"offre.caracteristiques.roaming_ue": False}]},
            action={"kind": "exclude"},
        ),
        RegleRecommandation(
            nom="boost_roaming_hors_ue", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=20,
            condition={"$and": [{"reponses.roaming_hors_ue": {"$ne": "Jamais"}}, {"offre.caracteristiques.roaming_hors_ue": True}]},
            action={"kind": "score_adjust", "valeur": 10},
        ),
        RegleRecommandation(
            nom="boost_qualite_reseau_si_insatisfait", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=15,
            condition={"$and": [{"reponses.qualite_reseau": {"$eq": "Mauvaise"}}, {"offre.caracteristiques.reseau_qualite": {"$eq": "bonne"}}]},
            action={"kind": "score_adjust", "valeur": 15},
        ),
        RegleRecommandation(
            nom="boost_5g", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=10,
            condition={"reponses.5g_importante": {"$eq": True}},
            action={
                "kind": "score_adjust",
                "bareme": [{"si": {"offre.caracteristiques.5g": True}, "valeur": 10}],
                "defaut": -10,
            },
        ),
        RegleRecommandation(
            nom="boost_partage_connexion", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=10,
            condition={"$and": [{"reponses.partage_connexion": {"$eq": True}}, {"offre.caracteristiques.partage_connexion": True}]},
            action={"kind": "score_adjust", "valeur": 8},
        ),
        RegleRecommandation(
            nom="boost_sans_engagement", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=5,
            condition={"$and": [{"reponses.sensibilite_prix": {"$eq": "Prix avant tout"}}, {"offre.engagement_mois": {"$eq": 0}}]},
            action={"kind": "score_adjust", "valeur": 10},
        ),
        RegleRecommandation(
            nom="boost_qualite_avant_prix", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=5,
            condition={"$and": [{"reponses.sensibilite_prix": {"$eq": "Qualité avant tout"}}, {"offre.caracteristiques.reseau_qualite": {"$eq": "bonne"}}]},
            action={"kind": "score_adjust", "valeur": 10},
        ),
        RegleRecommandation(
            nom="boost_meme_operateur_famille", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=1,
            condition={"$and": [{"reponses.meme_operateur_famille": {"$eq": True}}, {"offre.engagement_mois": {"$eq": 0}}]},
            action={"kind": "score_adjust", "valeur": 5},
        ),
        RegleRecommandation(
            nom="boost_petit_prix", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=1,
            condition={"$and": [{"offre.prix_mensuel": {"$lte": 15}}, {"reponses.sensibilite_prix": {"$ne": "Qualité avant tout"}}]},
            action={"kind": "score_adjust", "valeur": 5},
        ),
    ]


def seed_ia_conseil() -> int:
    """Insère categorie/fournisseur/offre/trame_template/regle_recommandation
    pour "mobile" si la catégorie n'existe pas déjà. Renvoie le nombre total
    de lignes créées (0 si déjà seedé)."""
    engine = _pg_engine()
    with Session(engine) as session:
        deja_seede = session.execute(
            select(func.count()).select_from(Categorie).where(Categorie.slug == CATEGORIE_SLUG)
        ).scalar()
        if deja_seede:
            return 0

        categorie = Categorie(slug=CATEGORIE_SLUG, nom="Mobile", ordre=1, actif=True)
        session.add(categorie)

        fournisseurs = _construire_fournisseurs()
        session.add_all(fournisseurs.values())
        session.flush()  # peuple fournisseur.id (default Python uuid4) avant de le référencer

        offres = _construire_offres(fournisseurs)
        session.add_all(offres)

        trame = TrameTemplate(categorie_slug=CATEGORIE_SLUG, version=1, definition=TRAME_MOBILE_V1, actif=True)
        session.add(trame)

        regles = _construire_regles()
        session.add_all(regles)

        session.commit()
        return 1 + len(fournisseurs) + len(offres) + 1 + len(regles)


def main() -> None:
    """Orchestrateur multi-catégories (§1.1) : mobile (ce module) puis box et
    énergie (élec + gaz), chacun idempotent indépendamment. Un seul point
    d'entrée : `python -m backend.scripts.seed_ia_conseil`."""
    n_mobile = seed_ia_conseil()
    if n_mobile == 0:
        print(f"La catégorie « {CATEGORIE_SLUG} » existe déjà — rien créé.")
    else:
        print(f"{n_mobile} lignes insérées (1 catégorie, {len(_FOURNISSEURS)} fournisseurs, {len(_OFFRES)} offres, "
              f"1 trame, {len(_construire_regles())} règles).")

    from backend.scripts.seed_ia_conseil_box import seed_ia_conseil_box
    from backend.scripts.seed_ia_conseil_energie import seed_ia_conseil_energie

    engine = _pg_engine()
    with Session(engine) as session:
        n_box = seed_ia_conseil_box(session)
        n_energie = seed_ia_conseil_energie(session)
        session.commit()

    print(f"Box : {n_box} lignes insérées." if n_box else "Box : catégorie déjà seedée, rien créé.")
    print(f"Énergie : {n_energie} lignes insérées." if n_energie else "Énergie : catégories déjà seedées, rien créé.")


if __name__ == "__main__":
    main()
