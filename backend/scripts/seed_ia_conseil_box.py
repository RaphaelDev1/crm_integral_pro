# ==============================================================================
#  SEED IA CONSEIL — BOX INTERNET. Complète seed_ia_conseil.py (mobile) pour
#  la catégorie "box" : trame adaptative, offres et règles de recommandation.
#  PLAN_IMPLEMENTATION_4_PHASES.md §1.1. Prix/débits indicatifs — usage
#  dev/test uniquement, ne pas exécuter en prod.
#
#  Module autonome (mêmes conventions que seed_ia_conseil.py) : peut être
#  exécuté seul (`python -m backend.scripts.seed_ia_conseil_box`) ou via
#  l'orchestrateur `seed_ia_conseil.main()`.
# ==============================================================================
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.ia_conseil import Categorie, Fournisseur, OffreConseil, RegleRecommandation, TrameTemplate

CATEGORIE_SLUG = "box"

# ==============================================================================
#  TRAME BOX — même principe escargot que la trame mobile (§0.2/§0.1.bis) :
#  la question "eligibilite_fibre" est le pivot (poids éthique fort, élimine
#  les offres fibre si la réponse est négative) au même titre que
#  "conso_data_go" pour le mobile.
# ==============================================================================
TRAME_BOX_V1 = {
    "id": "trame_box_v1",
    "categorie": "box",
    "sections": [
        {
            "id": "decouverte",
            "titre": "Découverte",
            "questions": [
                {"id": "type_logement", "label": "Maison ou appartement ?", "type": "select", "options": ["Maison", "Appartement"], "cout_cognitif": 1},
                {"id": "operateur_actuel", "label": "Quel est votre opérateur box actuel ?", "type": "select", "options_ref": "operateurs_box", "cout_cognitif": 1},
                {"id": "cout_actuel_mensuel", "label": "Combien payez-vous par mois actuellement ?", "type": "number", "unit": "€", "cout_cognitif": 2},
                {
                    "id": "eligibilite_fibre",
                    "label": "Votre logement est-il éligible à la fibre ?",
                    "type": "select", "options": ["Oui", "Non", "Ne sait pas"],
                    "required": True, "cout_cognitif": 2, "poids_ethique": 10,
                    "elimine_offres_si": {
                        "reponse_non": {"offre.caracteristiques.technologie": {"$eq": "fibre"}},
                    },
                    "utilise_par_regles": ["exclure_fibre_si_non_eligible", "boost_fibre_si_eligible"],
                },
            ],
        },
        {
            "id": "usages",
            "titre": "Vos usages",
            "questions": [
                {
                    "id": "nb_utilisateurs_simultanes",
                    "label": "Combien de personnes utilisent internet en même temps au pic de la journée ?",
                    "type": "number", "min": 1, "max": 15,
                    "cout_cognitif": 1, "poids_ethique": 4,
                    "utilise_par_regles": ["anti_survente_debit_box", "boost_haut_debit_famille_nombreuse"],
                },
                {
                    "id": "teletravail",
                    "label": "Télétravaillez-vous régulièrement (visio, gros transferts) ?",
                    "type": "boolean",
                    "cout_cognitif": 1, "poids_ethique": 3,
                    "utilise_par_regles": ["boost_upload_teletravail"],
                },
                {
                    "id": "tv_incluse_souhaitee",
                    "label": "Souhaitez-vous la TV incluse (box TV, chaînes) ?",
                    "type": "boolean",
                    "cout_cognitif": 1, "poids_ethique": 1,
                    "utilise_par_regles": ["boost_tv_incluse"],
                },
                {
                    # Voir seed_ia_conseil.py::TRAME_MOBILE_V1 (question "ville") pour le
                    # raisonnement : la ville suffit à inférer la qualité de service depuis
                    # les speedtests déjà en base (backend/services/ia_conseil_engine.py::
                    # _inferer_qualite_reseau), écrite dans reponses["qualite_service_actuelle"].
                    "id": "ville",
                    "label": "Dans quelle ville habite le client ?",
                    "type": "text",
                    "cout_cognitif": 1, "poids_ethique": 2,
                    "utilise_par_regles": ["boost_qualite_si_insatisfait_box"],
                },
                {
                    # Même capture informationnelle que seed_ia_conseil.py::TRAME_MOBILE_V1
                    # (satisfaction_reseau/defaut_technique/veut_rester) — pas de nouvelle
                    # règle de scoring, reportée sur la fiche prospect/client à la clôture.
                    "id": "satisfaction_reseau",
                    "label": "Satisfaction du client vis-à-vis de son opérateur actuel ?",
                    "type": "select", "options": ["😀 Très content", "😐 Ça va", "😡 Pas du tout"],
                    "cout_cognitif": 1, "poids_ethique": 2,
                },
                {
                    "id": "defaut_technique",
                    "label": "Défaut technique potentiel constaté sur le réseau actuel ?",
                    "type": "select", "options": ["Aucun signalé", "Faible", "Moyen", "Critique"],
                    "cout_cognitif": 1, "poids_ethique": 1,
                },
                {
                    "id": "veut_rester",
                    "label": "Le client souhaite-t-il rester chez son opérateur actuel ?",
                    "type": "select", "options": ["Oui", "Pas spécialement", "Non"],
                    "cout_cognitif": 1, "poids_ethique": 1,
                },
                {
                    "id": "sensibilite_prix",
                    "label": "Ce qui compte le plus pour vous ?",
                    "type": "select", "options": ["Prix avant tout", "Équilibre", "Qualité avant tout"],
                    "cout_cognitif": 1, "poids_ethique": 2,
                    "utilise_par_regles": ["boost_sans_engagement_box", "boost_qualite_avant_prix_box"],
                },
            ],
        },
    ],
    "branches": [
        {
            "when": {"eligibilite_fibre": {"$eq": "Non"}},
            "flags": ["proposer_4g_5g_box"],
        },
        {
            "when": {"nb_utilisateurs_simultanes": {"$gte": 4}},
            "insert_after": "nb_utilisateurs_simultanes",
            "questions": [
                {"id": "usage_streaming_4k_gaming", "label": "Usages exigeants réguliers (streaming 4K, gaming en ligne, cloud gaming) ?", "type": "boolean", "cout_cognitif": 1, "poids_ethique": 2, "utilise_par_regles": ["boost_haut_debit_famille_nombreuse"]},
            ],
        },
    ],
}


# ==============================================================================
#  FOURNISSEURS + OFFRES box (24 offres, 10 fournisseurs) — mix fibre / ADSL /
#  4G-5G box pour que les règles anti-survente et boost fibre aient un effet
#  observable.
# ==============================================================================
_FOURNISSEURS = [
    ("Orange", 0.95, 20),
    ("Sosh", 0.90, 15),
    ("SFR", 0.90, 18),
    ("RED by SFR", 0.85, 12),
    ("Bouygues Telecom", 0.92, 18),
    ("Free", 0.90, 15),
    ("Coriolis Telecom", 0.75, 10),
    ("Nordnet", 0.78, 10),
    ("La Poste Mobile", 0.80, 10),
    ("Ozone", 0.72, 8),
]

# (fournisseur, nom, prix_mensuel, technologie, debit_down_mbps, debit_up_mbps, tv_incluse, engagement_mois)
_OFFRES = [
    ("Orange", "Orange Livebox Fibre", 39.99, "fibre", 500, 500, True, 12),
    ("Orange", "Orange Livebox Fibre Plus", 49.99, "fibre", 2000, 700, True, 12),
    ("Orange", "Orange Livebox ADSL", 29.99, "adsl", 20, 1, False, 12),
    ("Sosh", "Sosh Fibre", 29.99, "fibre", 500, 500, False, 0),
    ("Sosh", "Sosh Fibre XL", 34.99, "fibre", 1000, 600, False, 0),
    ("SFR", "SFR Fibre Power", 33.99, "fibre", 1000, 500, True, 12),
    ("SFR", "SFR Fibre Starter", 25.99, "fibre", 300, 300, False, 12),
    ("RED by SFR", "RED Fibre", 27.99, "fibre", 500, 500, False, 0),
    ("RED by SFR", "RED ADSL", 22.99, "adsl", 20, 1, False, 0),
    ("Bouygues Telecom", "Bbox Fibre", 30.99, "fibre", 500, 500, True, 12),
    ("Bouygues Telecom", "Bbox Fibre Ultym", 41.99, "fibre", 2000, 700, True, 12),
    ("Bouygues Telecom", "Bbox 4G", 34.99, "4g_5g", 100, 20, False, 0),
    ("Free", "Freebox Pop", 29.99, "fibre", 900, 600, True, 0),
    ("Free", "Freebox Ultra", 39.99, "fibre", 8000, 8000, True, 0),
    ("Free", "Freebox 4G", 29.99, "4g_5g", 100, 20, False, 0),
    ("Coriolis Telecom", "Coriolis Fibre", 24.90, "fibre", 500, 500, False, 0),
    ("Coriolis Telecom", "Coriolis ADSL", 19.90, "adsl", 20, 1, False, 0),
    ("Nordnet", "Nordnet Fibre", 26.90, "fibre", 500, 500, False, 12),
    ("Nordnet", "Nordnet Satellite", 44.90, "satellite", 100, 15, False, 24),
    ("La Poste Mobile", "La Poste Mobile Fibre", 28.90, "fibre", 500, 500, False, 12),
    ("La Poste Mobile", "La Poste Mobile 5G Box", 32.90, "4g_5g", 150, 30, False, 0),
    ("Ozone", "Ozone Fibre Eco", 21.90, "fibre", 300, 300, False, 0),
    ("Ozone", "Ozone 4G Box", 26.90, "4g_5g", 80, 15, False, 0),
    ("Orange", "Orange 5G Box", 36.99, "4g_5g", 200, 50, False, 0),
]


def _construire_fournisseurs() -> dict[str, Fournisseur]:
    return {
        nom: Fournisseur(nom=nom, categorie_slug=CATEGORIE_SLUG, note_fiabilite=fiabilite, affilie=True, taux_commission=commission)
        for nom, fiabilite, commission in _FOURNISSEURS
    }


def _construire_offres(fournisseurs: dict[str, Fournisseur]) -> list[OffreConseil]:
    offres = []
    for fournisseur_nom, nom, prix, techno, debit_down, debit_up, tv, engagement in _OFFRES:
        offres.append(
            OffreConseil(
                fournisseur_id=fournisseurs[fournisseur_nom].id,
                categorie_slug=CATEGORIE_SLUG,
                nom=nom,
                prix_mensuel=prix,
                engagement_mois=engagement,
                caracteristiques={
                    "technologie": techno,
                    "debit_down_mbps": debit_down,
                    "debit_up_mbps": debit_up,
                    "tv_incluse": tv,
                    "qualite_service": "bonne" if techno == "fibre" else "moyenne",
                },
                source="manuel",
                valide=True,
            )
        )
    return offres


# ==============================================================================
#  RÈGLES DE RECOMMANDATION box (20) — §0.3.
# ==============================================================================
def _construire_regles() -> list[RegleRecommandation]:
    return [
        RegleRecommandation(
            nom="exclure_fibre_si_non_eligible", categorie_slug=CATEGORIE_SLUG, type="filtre", priorite=0,
            condition={"$and": [{"reponses.eligibilite_fibre": {"$eq": "Non"}}, {"offre.caracteristiques.technologie": {"$eq": "fibre"}}]},
            action={"kind": "exclude"},
        ),
        RegleRecommandation(
            nom="anti_survente_debit_box", categorie_slug=CATEGORIE_SLUG, type="alerte", priorite=100,
            condition={"$and": [{"reponses.nb_utilisateurs_simultanes": {"$lte": 2}}, {"offre.caracteristiques.debit_down_mbps": {"$gt": 1000}}]},
            action={
                "kind": "warn", "severite": "attention",
                "message": "Débit {{offre.caracteristiques.debit_down_mbps}} Mbps proposé pour seulement "
                "{{reponses.nb_utilisateurs_simultanes}} utilisateur(s) simultané(s) — un débit plus modeste suffirait probablement.",
            },
        ),
        RegleRecommandation(
            nom="alerte_engagement_box_si_prix_avant_tout", categorie_slug=CATEGORIE_SLUG, type="alerte", priorite=90,
            condition={"$and": [{"reponses.sensibilite_prix": {"$eq": "Prix avant tout"}}, {"offre.engagement_mois": {"$gt": 0}}]},
            action={
                "kind": "warn", "severite": "attention",
                "message": "Offre avec engagement de {{offre.engagement_mois}} mois alors que le client priorise le prix.",
            },
        ),
        RegleRecommandation(
            nom="boost_fibre_si_eligible", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=20,
            condition={"$and": [{"reponses.eligibilite_fibre": {"$eq": "Oui"}}, {"offre.caracteristiques.technologie": {"$eq": "fibre"}}]},
            action={"kind": "score_adjust", "valeur": 15},
        ),
        RegleRecommandation(
            nom="boost_haut_debit_famille_nombreuse", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=15,
            condition={"$and": [{"reponses.nb_utilisateurs_simultanes": {"$gte": 4}}, {"offre.caracteristiques.debit_down_mbps": {"$gte": 500}}]},
            action={"kind": "score_adjust", "valeur": 15},
        ),
        RegleRecommandation(
            nom="boost_upload_teletravail", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=15,
            condition={"$and": [{"reponses.teletravail": {"$eq": True}}, {"offre.caracteristiques.debit_up_mbps": {"$gte": 300}}]},
            action={"kind": "score_adjust", "valeur": 15},
        ),
        RegleRecommandation(
            nom="boost_tv_incluse", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=10,
            condition={"$and": [{"reponses.tv_incluse_souhaitee": {"$eq": True}}, {"offre.caracteristiques.tv_incluse": True}]},
            action={"kind": "score_adjust", "valeur": 12},
        ),
        RegleRecommandation(
            nom="boost_qualite_si_insatisfait_box", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=10,
            condition={"$and": [{"reponses.qualite_service_actuelle": {"$eq": "Mauvaise"}}, {"offre.caracteristiques.qualite_service": {"$eq": "bonne"}}]},
            action={"kind": "score_adjust", "valeur": 15},
        ),
        RegleRecommandation(
            nom="boost_sans_engagement_box", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=5,
            condition={"$and": [{"reponses.sensibilite_prix": {"$eq": "Prix avant tout"}}, {"offre.engagement_mois": {"$eq": 0}}]},
            action={"kind": "score_adjust", "valeur": 10},
        ),
        RegleRecommandation(
            nom="boost_qualite_avant_prix_box", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=5,
            condition={"$and": [{"reponses.sensibilite_prix": {"$eq": "Qualité avant tout"}}, {"offre.caracteristiques.qualite_service": {"$eq": "bonne"}}]},
            action={"kind": "score_adjust", "valeur": 10},
        ),
        RegleRecommandation(
            nom="boost_petit_prix_box", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=1,
            condition={"$and": [{"offre.prix_mensuel": {"$lte": 25}}, {"reponses.sensibilite_prix": {"$ne": "Qualité avant tout"}}]},
            action={"kind": "score_adjust", "valeur": 5},
        ),
        RegleRecommandation(
            nom="penalite_debit_faible_teletravail", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=15,
            condition={"$and": [{"reponses.teletravail": {"$eq": True}}, {"offre.caracteristiques.debit_up_mbps": {"$lt": 20}}]},
            action={"kind": "score_adjust", "valeur": -20},
        ),
        RegleRecommandation(
            nom="alerte_technologie_4g5g_secours", categorie_slug=CATEGORIE_SLUG, type="alerte", priorite=80,
            condition={"$and": [{"reponses.eligibilite_fibre": {"$eq": "Non"}}, {"offre.caracteristiques.technologie": {"$eq": "4g_5g"}}]},
            action={
                "kind": "warn", "severite": "info",
                "message": "Box 4G/5G proposée en alternative à la fibre (non éligible) — vérifier la couverture réseau à l'adresse du client.",
            },
        ),
        RegleRecommandation(
            nom="boost_adsl_dernier_recours", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=25,
            condition={"$and": [{"reponses.eligibilite_fibre": {"$eq": "Non"}}, {"offre.caracteristiques.technologie": {"$eq": "adsl"}}]},
            action={"kind": "score_adjust", "valeur": -10},
        ),
        RegleRecommandation(
            nom="boost_streaming_4k_gaming", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=12,
            condition={"$and": [{"reponses.usage_streaming_4k_gaming": {"$eq": True}}, {"offre.caracteristiques.debit_down_mbps": {"$gte": 1000}}]},
            action={"kind": "score_adjust", "valeur": 10},
        ),
        RegleRecommandation(
            nom="alerte_satellite_engagement_long", categorie_slug=CATEGORIE_SLUG, type="alerte", priorite=70,
            condition={"offre.caracteristiques.technologie": {"$eq": "satellite"}},
            action={
                "kind": "warn", "severite": "attention",
                "message": "Offre satellite — latence élevée, peu adaptée à la visio ou au gaming en ligne.",
            },
        ),
        RegleRecommandation(
            nom="exclure_satellite_si_teletravail_visio", categorie_slug=CATEGORIE_SLUG, type="filtre", priorite=0,
            condition={"$and": [{"reponses.teletravail": {"$eq": True}}, {"offre.caracteristiques.technologie": {"$eq": "satellite"}}]},
            action={"kind": "exclude"},
        ),
        RegleRecommandation(
            nom="boost_engagement_court_si_equilibre", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=3,
            condition={"$and": [{"reponses.sensibilite_prix": {"$eq": "Équilibre"}}, {"offre.engagement_mois": {"$lte": 12}}]},
            action={"kind": "score_adjust", "valeur": 5},
        ),
        RegleRecommandation(
            nom="boost_tv_et_qualite_maison", categorie_slug=CATEGORIE_SLUG, type="scoring", priorite=4,
            condition={"$and": [{"reponses.type_logement": {"$eq": "Maison"}}, {"offre.caracteristiques.tv_incluse": True}]},
            action={"kind": "score_adjust", "valeur": 5},
        ),
        RegleRecommandation(
            nom="anti_sous_couverture_debit_box", categorie_slug=CATEGORIE_SLUG, type="alerte", priorite=95,
            condition={"$and": [{"reponses.nb_utilisateurs_simultanes": {"$gte": 4}}, {"offre.caracteristiques.debit_down_mbps": {"$lt": 300}}]},
            action={
                "kind": "warn", "severite": "critique",
                "message": "Débit {{offre.caracteristiques.debit_down_mbps}} Mbps probablement insuffisant pour "
                "{{reponses.nb_utilisateurs_simultanes}} utilisateurs simultanés.",
            },
        ),
    ]


def seed_ia_conseil_box(session: Session) -> int:
    """Insère categorie/fournisseur/offre/trame_template/regle_recommandation
    pour "box" si la catégorie n'existe pas déjà dans la session donnée.
    Renvoie le nombre de lignes créées (0 si déjà seedé). Ne commit pas —
    laissé à l'appelant (voir seed_ia_conseil.main() pour l'orchestration
    multi-catégories dans une seule transaction)."""
    deja_seede = session.execute(
        select(func.count()).select_from(Categorie).where(Categorie.slug == CATEGORIE_SLUG)
    ).scalar()
    if deja_seede:
        return 0

    categorie = Categorie(slug=CATEGORIE_SLUG, nom="Box Internet", ordre=2, actif=True)
    session.add(categorie)

    fournisseurs = _construire_fournisseurs()
    session.add_all(fournisseurs.values())
    session.flush()

    offres = _construire_offres(fournisseurs)
    session.add_all(offres)

    trame = TrameTemplate(categorie_slug=CATEGORIE_SLUG, version=1, definition=TRAME_BOX_V1, actif=True)
    session.add(trame)

    regles = _construire_regles()
    session.add_all(regles)

    session.flush()
    return 1 + len(fournisseurs) + len(offres) + 1 + len(regles)


def main() -> None:
    from backend.scripts.seed_ia_conseil import _pg_engine

    engine = _pg_engine()
    with Session(engine) as session:
        n = seed_ia_conseil_box(session)
        session.commit()
    if n == 0:
        print(f"La catégorie « {CATEGORIE_SLUG} » existe déjà — rien créé.")
        return
    print(f"{n} lignes insérées (1 catégorie, {len(_FOURNISSEURS)} fournisseurs, {len(_OFFRES)} offres, 1 trame, "
          f"{len(_construire_regles())} règles).")


if __name__ == "__main__":
    main()
