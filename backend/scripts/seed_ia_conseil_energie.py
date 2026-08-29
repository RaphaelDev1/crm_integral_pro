# ==============================================================================
#  SEED IA CONSEIL — ÉNERGIE (élec + gaz). Complète seed_ia_conseil.py (mobile)
#  et seed_ia_conseil_box.py pour les catégories "energie_elec" et
#  "energie_gaz" : deux trames adaptatives distinctes (le schéma lie une
#  session à une seule catégorie, §0.1), deux catalogues, deux jeux de règles.
#  PLAN_IMPLEMENTATION_4_PHASES.md §1.1. Prix/consommations indicatifs — usage
#  dev/test uniquement, ne pas exécuter en prod.
#
#  Offres "duales" (élec+gaz) : le schéma n'admet qu'un categorie_slug par
#  offre — elles sont rattachées à "energie_elec" avec
#  caracteristiques.duale=true (exploitable en cross-sell Phase 2, pas
#  actionnable dans une session mono-catégorie du MVP).
# ==============================================================================
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.ia_conseil import Categorie, Fournisseur, OffreConseil, RegleRecommandation, TrameTemplate

CATEGORIE_SLUG_ELEC = "energie_elec"
CATEGORIE_SLUG_GAZ = "energie_gaz"


def _questions_communes(prefixe_conso: str, unite_conso: str, question_conso_id: str) -> list[dict]:
    """Questions partagées par les deux trames énergie (structure identique,
    seul l'id/unité de la question de consommation change)."""
    return [
        {"id": "type_logement", "label": "Maison ou appartement ?", "type": "select", "options": ["Maison", "Appartement"], "cout_cognitif": 1},
        {"id": "surface_m2", "label": "Surface du logement (m²) ?", "type": "number", "unit": "m²", "cout_cognitif": 2},
        {"id": "nb_occupants", "label": "Combien d'occupants dans le foyer ?", "type": "number", "min": 1, "max": 15, "cout_cognitif": 1},
        {"id": f"fournisseur_actuel_{prefixe_conso}", "label": "Quel est votre fournisseur actuel ?", "type": "select", "options_ref": f"operateurs_{prefixe_conso}", "cout_cognitif": 1},
        {"id": f"cout_actuel_mensuel_{prefixe_conso}", "label": "Combien payez-vous par mois actuellement ?", "type": "number", "unit": "€", "cout_cognitif": 2},
        {
            "id": question_conso_id,
            "label": f"Consommation annuelle ({unite_conso}, voir facture ou estimation)",
            "type": "number", "unit": unite_conso,
            "help": "Astuce : l'estimation annuelle est indiquée sur la facture ou l'espace client du fournisseur.",
            "required": True, "cout_cognitif": 3, "poids_ethique": 10,
        },
    ]


def _questions_usage_communes(id_verte: str, id_sensibilite: str, regles_verte: list[str], regles_sensibilite: list[str]) -> list[dict]:
    return [
        {
            "id": id_verte, "label": "L'électricité/le gaz d'origine renouvelable est-il important pour vous ?", "type": "boolean",
            "cout_cognitif": 1, "poids_ethique": 2, "utilise_par_regles": regles_verte,
        },
        {
            "id": id_sensibilite, "label": "Ce qui compte le plus pour vous ?",
            "type": "select", "options": ["Prix avant tout", "Équilibre", "Origine renouvelable"],
            "cout_cognitif": 1, "poids_ethique": 2, "utilise_par_regles": regles_sensibilite,
        },
    ]


# ==============================================================================
#  TRAME ÉLECTRICITÉ — la question pivot est la consommation annuelle en kWh
#  (équivalent du "conso_data_go" mobile pour le principe escargot).
# ==============================================================================
TRAME_ENERGIE_ELEC_V1 = {
    "id": "trame_energie_elec_v1",
    "categorie": CATEGORIE_SLUG_ELEC,
    "sections": [
        {
            "id": "decouverte",
            "titre": "Découverte",
            "questions": [
                *_questions_communes("elec", "kWh/an", "consommation_elec_kwh_an"),
                {
                    "id": "puissance_compteur_kva",
                    "label": "Puissance de votre compteur électrique (kVA) ?",
                    "type": "select", "options": ["3", "6", "9", "12", "15", "18"],
                    "cout_cognitif": 2, "poids_ethique": 3,
                    "utilise_par_regles": ["alerte_puissance_compteur_inadaptee"],
                },
            ],
        },
        {
            "id": "usages",
            "titre": "Vos usages",
            "questions": [
                {
                    "id": "chauffage_electrique",
                    "label": "Votre chauffage principal est-il électrique ?",
                    "type": "boolean", "cout_cognitif": 1, "poids_ethique": 3,
                    "utilise_par_regles": ["boost_heures_creuses_chauffage_elec"],
                },
                {
                    "id": "heures_creuses_interessant",
                    "label": "Utilisez-vous des appareils la nuit (voiture électrique, ballon d'eau chaude programmable) ?",
                    "type": "boolean", "show_if": {"chauffage_electrique": {"$exists": True}},
                    "cout_cognitif": 1, "poids_ethique": 2,
                    "utilise_par_regles": ["boost_heures_creuses_chauffage_elec"],
                },
                *_questions_usage_communes(
                    "energie_verte_importante", "sensibilite_prix_energie",
                    ["boost_offre_verte_elec"], ["boost_sans_engagement_elec", "boost_offre_verte_elec"],
                ),
            ],
        },
    ],
    "branches": [
        {
            "when": {"consommation_elec_kwh_an": {"$lt": 2000}},
            "flags": ["petit_consommateur_elec"],
        },
    ],
}


# ==============================================================================
#  TRAME GAZ — même structure, adaptée au gaz (pas de puissance de compteur,
#  mais une zone tarifaire et le type de chauffage).
# ==============================================================================
TRAME_ENERGIE_GAZ_V1 = {
    "id": "trame_energie_gaz_v1",
    "categorie": CATEGORIE_SLUG_GAZ,
    "sections": [
        {
            "id": "decouverte",
            "titre": "Découverte",
            "questions": [
                *_questions_communes("gaz", "kWh/an", "consommation_gaz_kwh_an"),
                {
                    "id": "usage_gaz",
                    "label": "Usage principal du gaz ?",
                    "type": "select", "options": ["Chauffage + eau chaude + cuisson", "Chauffage + eau chaude", "Cuisson uniquement"],
                    "cout_cognitif": 1, "poids_ethique": 3,
                    "utilise_par_regles": ["anti_survente_conso_gaz", "boost_petit_consommateur_gaz"],
                },
            ],
        },
        {
            "id": "usages",
            "titre": "Vos usages",
            "questions": [
                *_questions_usage_communes(
                    "energie_verte_importante_gaz", "sensibilite_prix_energie_gaz",
                    ["boost_offre_verte_gaz"], ["boost_sans_engagement_gaz", "boost_offre_verte_gaz"],
                ),
            ],
        },
    ],
    "branches": [
        {
            "when": {"consommation_gaz_kwh_an": {"$lt": 6000}},
            "flags": ["petit_consommateur_gaz"],
        },
    ],
}


# ==============================================================================
#  FOURNISSEURS + OFFRES — 18 élec (dont 4 duales) + 12 gaz.
# ==============================================================================
_FOURNISSEURS_ELEC = [
    ("EDF", 0.95, 15),
    ("TotalEnergies", 0.88, 20),
    ("Engie", 0.90, 18),
    ("Ekwateur", 0.85, 22),
    ("Mint Énergie", 0.80, 20),
    ("OHM Énergie", 0.78, 20),
    ("Alpiq", 0.82, 18),
    ("Vattenfall", 0.83, 18),
]

# (fournisseur, nom, prix_abonnement_mensuel, prix_kwh_c, verte, duale, engagement_mois)
_OFFRES_ELEC = [
    ("EDF", "EDF Tarif Bleu", 13.50, 20.16, False, False, 0),
    ("EDF", "EDF Vert Électrique", 14.90, 20.50, True, False, 0),
    ("TotalEnergies", "TotalEnergies Standard", 12.90, 19.80, False, False, 0),
    ("TotalEnergies", "TotalEnergies Verte Fixe 1 an", 13.90, 19.50, True, False, 12),
    ("TotalEnergies", "TotalEnergies Duo Élec+Gaz", 12.50, 19.60, False, True, 12),
    ("Engie", "Engie Élec Référence", 13.20, 20.00, False, False, 0),
    ("Engie", "Engie Duo Verte", 13.90, 19.90, True, True, 12),
    ("Ekwateur", "Ekwateur 100% Verte", 12.90, 19.20, True, False, 0),
    ("Ekwateur", "Ekwateur Duo Verte", 12.50, 19.10, True, True, 0),
    ("Mint Énergie", "Mint Charge Nocturne", 12.90, 18.90, True, False, 0),
    ("Mint Énergie", "Mint Weekend", 13.10, 19.00, True, False, 0),
    ("OHM Énergie", "OHM Éco", 11.90, 18.70, False, False, 0),
    ("OHM Énergie", "OHM Éco Verte", 12.20, 18.90, True, False, 0),
    ("Alpiq", "Alpiq Fixe 2 ans", 13.50, 19.40, False, False, 24),
    ("Alpiq", "Alpiq Duo", 13.00, 19.30, False, True, 12),
    ("Vattenfall", "Vattenfall Online", 11.50, 18.60, False, False, 0),
    ("Vattenfall", "Vattenfall Éco Verte", 12.00, 18.80, True, False, 0),
    ("EDF", "EDF Zen Fixe", 14.50, 20.30, False, False, 12),
]

_FOURNISSEURS_GAZ = [
    ("EDF", 0.95, 15),
    ("TotalEnergies", 0.88, 20),
    ("Engie", 0.90, 18),
    ("Ekwateur", 0.85, 22),
    ("Mint Énergie", 0.80, 20),
    ("Vattenfall", 0.83, 18),
]

# (fournisseur, nom, prix_abonnement_mensuel, prix_kwh_c, verte_biomethane, engagement_mois)
_OFFRES_GAZ = [
    ("EDF", "EDF Gaz Tarif Repère", 21.90, 9.80, False, 0),
    ("TotalEnergies", "TotalEnergies Gaz Standard", 20.50, 9.50, False, 0),
    ("TotalEnergies", "TotalEnergies Gaz Vert", 21.90, 9.90, True, 12),
    ("Engie", "Engie Gaz Référence", 20.90, 9.60, False, 0),
    ("Engie", "Engie Gaz Naturel Vert", 22.50, 10.00, True, 12),
    ("Ekwateur", "Ekwateur Biométhane 100%", 21.20, 9.85, True, 0),
    ("Ekwateur", "Ekwateur Gaz Éco", 19.90, 9.40, False, 0),
    ("Mint Énergie", "Mint Gaz Vert", 20.90, 9.55, True, 0),
    ("Vattenfall", "Vattenfall Gaz Online", 19.50, 9.30, False, 0),
    ("Vattenfall", "Vattenfall Gaz Vert", 21.00, 9.70, True, 0),
    ("EDF", "EDF Gaz Zen Fixe 1 an", 22.90, 10.10, False, 12),
    ("Engie", "Engie Gaz Standard Fixe 2 ans", 21.50, 9.75, False, 24),
]


def _construire_fournisseurs(liste: list[tuple], categorie_slug: str) -> dict[str, Fournisseur]:
    fournisseurs: dict[str, Fournisseur] = {}
    for nom, fiabilite, commission in liste:
        cle = f"{categorie_slug}:{nom}"
        fournisseurs[cle] = Fournisseur(nom=nom, categorie_slug=categorie_slug, note_fiabilite=fiabilite, affilie=True, taux_commission=commission)
    return fournisseurs


def _construire_offres_elec(fournisseurs: dict[str, Fournisseur]) -> list[OffreConseil]:
    offres = []
    for fournisseur_nom, nom, abo, prix_kwh, verte, duale, engagement in _OFFRES_ELEC:
        offres.append(
            OffreConseil(
                fournisseur_id=fournisseurs[f"{CATEGORIE_SLUG_ELEC}:{fournisseur_nom}"].id,
                categorie_slug=CATEGORIE_SLUG_ELEC,
                nom=nom,
                prix_mensuel=round(abo, 2),
                engagement_mois=engagement,
                caracteristiques={
                    "prix_abonnement_mensuel": abo,
                    "prix_kwh_centimes": prix_kwh,
                    "origine_verte": verte,
                    "duale": duale,
                    "inclut_gaz": duale,
                    "heures_creuses": nom.lower().find("nocturne") >= 0 or nom.lower().find("weekend") >= 0,
                },
                source="manuel",
                valide=True,
            )
        )
    return offres


def _construire_offres_gaz(fournisseurs: dict[str, Fournisseur]) -> list[OffreConseil]:
    offres = []
    for fournisseur_nom, nom, abo, prix_kwh, verte, engagement in _OFFRES_GAZ:
        offres.append(
            OffreConseil(
                fournisseur_id=fournisseurs[f"{CATEGORIE_SLUG_GAZ}:{fournisseur_nom}"].id,
                categorie_slug=CATEGORIE_SLUG_GAZ,
                nom=nom,
                prix_mensuel=round(abo, 2),
                engagement_mois=engagement,
                caracteristiques={
                    "prix_abonnement_mensuel": abo,
                    "prix_kwh_centimes": prix_kwh,
                    "origine_verte_biomethane": verte,
                },
                source="manuel",
                valide=True,
            )
        )
    return offres


# ==============================================================================
#  RÈGLES DE RECOMMANDATION — 11 élec + 9 gaz (20 au total).
# ==============================================================================
def _construire_regles_elec() -> list[RegleRecommandation]:
    return [
        RegleRecommandation(
            nom="boost_offre_verte_elec", categorie_slug=CATEGORIE_SLUG_ELEC, type="scoring", priorite=15,
            condition={"$and": [{"reponses.energie_verte_importante": {"$eq": True}}, {"offre.caracteristiques.origine_verte": True}]},
            action={"kind": "score_adjust", "valeur": 15},
        ),
        RegleRecommandation(
            nom="boost_heures_creuses_chauffage_elec", categorie_slug=CATEGORIE_SLUG_ELEC, type="scoring", priorite=15,
            condition={"$and": [{"reponses.heures_creuses_interessant": {"$eq": True}}, {"offre.caracteristiques.heures_creuses": True}]},
            action={"kind": "score_adjust", "valeur": 15},
        ),
        RegleRecommandation(
            nom="boost_sans_engagement_elec", categorie_slug=CATEGORIE_SLUG_ELEC, type="scoring", priorite=5,
            condition={"$and": [{"reponses.sensibilite_prix_energie": {"$eq": "Prix avant tout"}}, {"offre.engagement_mois": {"$eq": 0}}]},
            action={"kind": "score_adjust", "valeur": 10},
        ),
        RegleRecommandation(
            nom="boost_petit_prix_kwh_elec", categorie_slug=CATEGORIE_SLUG_ELEC, type="scoring", priorite=1,
            condition={"$and": [{"offre.caracteristiques.prix_kwh_centimes": {"$lte": 19}}, {"reponses.sensibilite_prix_energie": {"$ne": "Origine renouvelable"}}]},
            action={"kind": "score_adjust", "valeur": 8},
        ),
        RegleRecommandation(
            nom="boost_duale_si_chauffage_non_electrique", categorie_slug=CATEGORIE_SLUG_ELEC, type="scoring", priorite=8,
            condition={"$and": [{"reponses.chauffage_electrique": {"$eq": False}}, {"offre.caracteristiques.duale": True}]},
            action={"kind": "score_adjust", "valeur": 5},
        ),
        RegleRecommandation(
            nom="alerte_puissance_compteur_inadaptee", categorie_slug=CATEGORIE_SLUG_ELEC, type="alerte", priorite=90,
            condition={"$and": [{"reponses.puissance_compteur_kva": {"$eq": "3"}}, {"reponses.chauffage_electrique": {"$eq": True}}]},
            action={
                "kind": "warn", "severite": "attention",
                "message": "Puissance de compteur ({{reponses.puissance_compteur_kva}} kVA) potentiellement sous-dimensionnée pour un chauffage électrique — vérifier avec le client.",
            },
        ),
        RegleRecommandation(
            nom="anti_survente_abonnement_petit_consommateur_elec", categorie_slug=CATEGORIE_SLUG_ELEC, type="alerte", priorite=100,
            condition={"$and": [{"reponses.consommation_elec_kwh_an": {"$lt": 2000}}, {"offre.caracteristiques.prix_abonnement_mensuel": {"$gt": 14}}]},
            action={
                "kind": "warn", "severite": "attention",
                "message": "Petite consommation annuelle ({{reponses.consommation_elec_kwh_an}} kWh) — privilégier un abonnement à faible coût fixe.",
            },
        ),
        RegleRecommandation(
            nom="boost_petit_abonnement_petit_consommateur_elec", categorie_slug=CATEGORIE_SLUG_ELEC, type="scoring", priorite=10,
            condition={"$and": [{"reponses.consommation_elec_kwh_an": {"$lt": 2000}}, {"offre.caracteristiques.prix_abonnement_mensuel": {"$lte": 12.5}}]},
            action={"kind": "score_adjust", "valeur": 12},
        ),
        RegleRecommandation(
            nom="boost_gros_consommateur_prix_kwh_bas", categorie_slug=CATEGORIE_SLUG_ELEC, type="scoring", priorite=10,
            condition={"$and": [{"reponses.consommation_elec_kwh_an": {"$gte": 8000}}, {"offre.caracteristiques.prix_kwh_centimes": {"$lte": 19}}]},
            action={"kind": "score_adjust", "valeur": 12},
        ),
        RegleRecommandation(
            nom="alerte_engagement_elec_si_prix_avant_tout", categorie_slug=CATEGORIE_SLUG_ELEC, type="alerte", priorite=85,
            condition={"$and": [{"reponses.sensibilite_prix_energie": {"$eq": "Prix avant tout"}}, {"offre.engagement_mois": {"$gt": 0}}]},
            action={
                "kind": "warn", "severite": "info",
                "message": "Offre avec engagement de {{offre.engagement_mois}} mois alors que le client priorise le prix.",
            },
        ),
        RegleRecommandation(
            nom="exclure_non_verte_si_origine_renouvelable_prioritaire", categorie_slug=CATEGORIE_SLUG_ELEC, type="filtre", priorite=0,
            condition={"$and": [{"reponses.sensibilite_prix_energie": {"$eq": "Origine renouvelable"}}, {"offre.caracteristiques.origine_verte": False}]},
            action={"kind": "exclude"},
        ),
    ]


def _construire_regles_gaz() -> list[RegleRecommandation]:
    return [
        RegleRecommandation(
            nom="boost_offre_verte_gaz", categorie_slug=CATEGORIE_SLUG_GAZ, type="scoring", priorite=15,
            condition={"$and": [{"reponses.energie_verte_importante_gaz": {"$eq": True}}, {"offre.caracteristiques.origine_verte_biomethane": True}]},
            action={"kind": "score_adjust", "valeur": 15},
        ),
        RegleRecommandation(
            nom="boost_sans_engagement_gaz", categorie_slug=CATEGORIE_SLUG_GAZ, type="scoring", priorite=5,
            condition={"$and": [{"reponses.sensibilite_prix_energie_gaz": {"$eq": "Prix avant tout"}}, {"offre.engagement_mois": {"$eq": 0}}]},
            action={"kind": "score_adjust", "valeur": 10},
        ),
        RegleRecommandation(
            nom="boost_petit_prix_kwh_gaz", categorie_slug=CATEGORIE_SLUG_GAZ, type="scoring", priorite=1,
            condition={"$and": [{"offre.caracteristiques.prix_kwh_centimes": {"$lte": 9.6}}, {"reponses.sensibilite_prix_energie_gaz": {"$ne": "Origine renouvelable"}}]},
            action={"kind": "score_adjust", "valeur": 8},
        ),
        RegleRecommandation(
            nom="anti_survente_conso_gaz", categorie_slug=CATEGORIE_SLUG_GAZ, type="alerte", priorite=100,
            condition={"$and": [{"reponses.usage_gaz": {"$eq": "Cuisson uniquement"}}, {"offre.caracteristiques.prix_abonnement_mensuel": {"$gt": 20}}]},
            action={
                "kind": "warn", "severite": "attention",
                "message": "Usage cuisson uniquement — un abonnement à faible coût fixe suffit généralement.",
            },
        ),
        RegleRecommandation(
            nom="boost_petit_consommateur_gaz", categorie_slug=CATEGORIE_SLUG_GAZ, type="scoring", priorite=10,
            condition={"$and": [{"reponses.consommation_gaz_kwh_an": {"$lt": 6000}}, {"offre.caracteristiques.prix_abonnement_mensuel": {"$lte": 20}}]},
            action={"kind": "score_adjust", "valeur": 10},
        ),
        RegleRecommandation(
            nom="boost_gros_consommateur_gaz_prix_bas", categorie_slug=CATEGORIE_SLUG_GAZ, type="scoring", priorite=10,
            condition={"$and": [{"reponses.consommation_gaz_kwh_an": {"$gte": 15000}}, {"offre.caracteristiques.prix_kwh_centimes": {"$lte": 9.6}}]},
            action={"kind": "score_adjust", "valeur": 12},
        ),
        RegleRecommandation(
            nom="alerte_engagement_gaz_si_prix_avant_tout", categorie_slug=CATEGORIE_SLUG_GAZ, type="alerte", priorite=85,
            condition={"$and": [{"reponses.sensibilite_prix_energie_gaz": {"$eq": "Prix avant tout"}}, {"offre.engagement_mois": {"$gt": 0}}]},
            action={
                "kind": "warn", "severite": "info",
                "message": "Offre avec engagement de {{offre.engagement_mois}} mois alors que le client priorise le prix.",
            },
        ),
        RegleRecommandation(
            nom="exclure_non_verte_gaz_si_origine_renouvelable_prioritaire", categorie_slug=CATEGORIE_SLUG_GAZ, type="filtre", priorite=0,
            condition={"$and": [{"reponses.sensibilite_prix_energie_gaz": {"$eq": "Origine renouvelable"}}, {"offre.caracteristiques.origine_verte_biomethane": False}]},
            action={"kind": "exclude"},
        ),
        RegleRecommandation(
            nom="boost_petit_prix_gaz_equilibre", categorie_slug=CATEGORIE_SLUG_GAZ, type="scoring", priorite=2,
            condition={"$and": [{"reponses.sensibilite_prix_energie_gaz": {"$eq": "Équilibre"}}, {"offre.engagement_mois": {"$lte": 12}}]},
            action={"kind": "score_adjust", "valeur": 5},
        ),
    ]


def seed_ia_conseil_energie(session: Session) -> int:
    """Insère les deux catégories énergie (elec + gaz) — chacune indépendamment
    idempotente. Ne commit pas — laissé à l'appelant."""
    total = 0

    deja_seede_elec = session.execute(
        select(func.count()).select_from(Categorie).where(Categorie.slug == CATEGORIE_SLUG_ELEC)
    ).scalar()
    if not deja_seede_elec:
        session.add(Categorie(slug=CATEGORIE_SLUG_ELEC, nom="Électricité", ordre=3, actif=True))
        fournisseurs_elec = _construire_fournisseurs(_FOURNISSEURS_ELEC, CATEGORIE_SLUG_ELEC)
        session.add_all(fournisseurs_elec.values())
        session.flush()
        offres_elec = _construire_offres_elec(fournisseurs_elec)
        session.add_all(offres_elec)
        session.add(TrameTemplate(categorie_slug=CATEGORIE_SLUG_ELEC, version=1, definition=TRAME_ENERGIE_ELEC_V1, actif=True))
        regles_elec = _construire_regles_elec()
        session.add_all(regles_elec)
        total += 1 + len(fournisseurs_elec) + len(offres_elec) + 1 + len(regles_elec)

    deja_seede_gaz = session.execute(
        select(func.count()).select_from(Categorie).where(Categorie.slug == CATEGORIE_SLUG_GAZ)
    ).scalar()
    if not deja_seede_gaz:
        session.add(Categorie(slug=CATEGORIE_SLUG_GAZ, nom="Gaz", ordre=4, actif=True))
        fournisseurs_gaz = _construire_fournisseurs(_FOURNISSEURS_GAZ, CATEGORIE_SLUG_GAZ)
        session.add_all(fournisseurs_gaz.values())
        session.flush()
        offres_gaz = _construire_offres_gaz(fournisseurs_gaz)
        session.add_all(offres_gaz)
        session.add(TrameTemplate(categorie_slug=CATEGORIE_SLUG_GAZ, version=1, definition=TRAME_ENERGIE_GAZ_V1, actif=True))
        regles_gaz = _construire_regles_gaz()
        session.add_all(regles_gaz)
        total += 1 + len(fournisseurs_gaz) + len(offres_gaz) + 1 + len(regles_gaz)

    session.flush()
    return total


def main() -> None:
    from backend.scripts.seed_ia_conseil import _pg_engine

    engine = _pg_engine()
    with Session(engine) as session:
        n = seed_ia_conseil_energie(session)
        session.commit()
    if n == 0:
        print("Les catégories « energie_elec » et « energie_gaz » existent déjà — rien créé.")
        return
    print(f"{n} lignes insérées au total (energie_elec + energie_gaz).")


if __name__ == "__main__":
    main()
