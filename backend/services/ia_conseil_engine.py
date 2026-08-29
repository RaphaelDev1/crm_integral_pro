# ==============================================================================
#  IA_CONSEIL_ENGINE — orchestration entre la persistance (session_trame,
#  offre, regle_recommandation...) et le moteur pur backend/rules_engine/.
#  PLAN_IMPLEMENTATION_4_PHASES.md §0.5.
# ==============================================================================
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.client import Client
from backend.models.ia_conseil import (
    OffreConseil,
    Recommandation,
    RegleRecommandation,
    SessionTrame,
    TrameTemplate,
)
from backend.models.prospect import Prospect
from backend.rules_engine import alertes, question_selector, scoring
from backend.services.alertes_engine import severite_normalisee

NB_RECOMMANDATIONS_MAX = 5

# Question "ville" (voir seed_ia_conseil.py / seed_ia_conseil_box.py) -> clé
# reponses sur laquelle la règle de scoring existante s'appuie déjà. Pas
# besoin d'ajouter d'autres catégories tant qu'elles n'ont pas de question
# équivalente à "qualité réseau/service perçue".
CIBLE_QUALITE_RESEAU_PAR_CATEGORIE: dict[str, str] = {
    "mobile": "qualite_reseau",
    "box": "qualite_service_actuelle",
}

SEUIL_QUALITE_BONNE_MBPS = 100.0
SEUIL_QUALITE_MOYENNE_MBPS = 30.0


async def _moyenne_speedtests(db: AsyncSession, ville_normalisee: str, operateur_normalise: str | None) -> tuple[float, int]:
    """Moyenne pondérée Prospect+Client.speed_down pour une ville (et, si fourni,
    un opérateur) donnés. Retourne (0.0, 0) si aucun échantillon."""
    filtres_prospect = [
        func.lower(func.trim(Prospect.ville)) == ville_normalisee,
        Prospect.speed_down.is_not(None),
        Prospect.speed_down > 0,
    ]
    filtres_client = [
        func.lower(func.trim(Client.ville)) == ville_normalisee,
        Client.speed_down.is_not(None),
        Client.speed_down > 0,
    ]
    if operateur_normalise:
        filtres_prospect.append(func.lower(func.trim(Prospect.operateur_actuel)) == operateur_normalise)
        filtres_client.append(func.lower(func.trim(Client.operateur_actuel)) == operateur_normalise)

    stats_prospects = (await db.execute(select(func.avg(Prospect.speed_down), func.count(Prospect.id)).where(*filtres_prospect))).one()
    stats_clients = (await db.execute(select(func.avg(Client.speed_down), func.count(Client.id)).where(*filtres_client))).one()

    total_pondere = 0.0
    total_echantillons = 0
    for moyenne, effectif in (stats_prospects, stats_clients):
        if moyenne is not None and effectif:
            total_pondere += float(moyenne) * effectif
            total_echantillons += effectif
    return total_pondere, total_echantillons


async def _inferer_qualite_reseau(db: AsyncSession, ville: str, operateur_actuel: str | None = None) -> str | None:
    """Déduit "Bonne"/"Moyenne"/"Mauvaise" à partir des speedtests déjà
    renseignés sur les fiches Prospect/Client de cette ville (Prospect.
    speed_down / Client.speed_down), plutôt que de faire deviner une réponse
    au client (remplace l'ancienne question auto-déclarée "Qualité réseau
    perçue à votre domicile ?"). Si `operateur_actuel` est fourni, on
    restreint d'abord aux speedtests de fiches déclarant le même opérateur
    dans la même ville (donnée bien plus pertinente qu'une moyenne tous
    opérateurs confondus) et on ne retombe sur la moyenne ville entière que
    faute d'échantillon pour cet opérateur. Renvoie None si aucune donnée
    n'est disponible pour cette ville — on n'invente pas de valeur, la règle
    de boost associée ne se déclenche alors simplement pas."""
    ville_normalisee = ville.strip().lower()
    if not ville_normalisee:
        return None

    operateur_normalise = operateur_actuel.strip().lower() if operateur_actuel and operateur_actuel.strip() else None

    total_pondere, total_echantillons = 0.0, 0
    if operateur_normalise:
        total_pondere, total_echantillons = await _moyenne_speedtests(db, ville_normalisee, operateur_normalise)
    if total_echantillons == 0:
        total_pondere, total_echantillons = await _moyenne_speedtests(db, ville_normalisee, None)

    if total_echantillons == 0:
        return None

    moyenne_globale = total_pondere / total_echantillons
    if moyenne_globale >= SEUIL_QUALITE_BONNE_MBPS:
        return "Bonne"
    if moyenne_globale >= SEUIL_QUALITE_MOYENNE_MBPS:
        return "Moyenne"
    return "Mauvaise"


class TrameIntrouvableError(Exception):
    """Aucun trame_template actif pour la catégorie demandée."""

    def __init__(self, categorie_slug: str):
        super().__init__(f"Aucune trame active pour la catégorie « {categorie_slug} ».")
        self.categorie_slug = categorie_slug


def _offre_vers_dict(offre: OffreConseil) -> dict[str, Any]:
    return {
        "id": str(offre.id),
        "nom": offre.nom,
        "prix_mensuel": float(offre.prix_mensuel) if offre.prix_mensuel is not None else None,
        "prix_apres_promo": float(offre.prix_apres_promo) if offre.prix_apres_promo is not None else None,
        "engagement_mois": offre.engagement_mois,
        "caracteristiques": offre.caracteristiques or {},
        "conditions": offre.conditions or {},
    }


def _regle_vers_dict(regle: RegleRecommandation) -> dict[str, Any]:
    return {
        "nom": regle.nom,
        "type": regle.type,
        "priorite": regle.priorite,
        "condition": regle.condition,
        "action": regle.action,
        "actif": regle.actif,
    }


async def charger_offres_actives(db: AsyncSession, categorie_slug: str) -> list[OffreConseil]:
    result = await db.execute(
        select(OffreConseil).where(OffreConseil.categorie_slug == categorie_slug, OffreConseil.valide.is_(True))
    )
    return list(result.scalars().all())


async def charger_regles_actives(db: AsyncSession, categorie_slug: str) -> list[RegleRecommandation]:
    result = await db.execute(
        select(RegleRecommandation).where(
            RegleRecommandation.categorie_slug == categorie_slug, RegleRecommandation.actif.is_(True)
        )
    )
    return list(result.scalars().all())


async def creer_session(
    db: AsyncSession, client_id: uuid.UUID, categorie_slug: str, conseiller_id: int | None, canal: str | None
) -> SessionTrame:
    result = await db.execute(
        select(TrameTemplate)
        .where(TrameTemplate.categorie_slug == categorie_slug, TrameTemplate.actif.is_(True))
        .order_by(TrameTemplate.version.desc())
        .limit(1)
    )
    trame = result.scalar_one_or_none()
    if trame is None:
        raise TrameIntrouvableError(categorie_slug)

    session = SessionTrame(
        client_id=client_id,
        conseiller_id=conseiller_id,
        categorie_slug=categorie_slug,
        trame_template_id=trame.id,
        canal=canal,
    )
    db.add(session)
    await db.flush()
    return session


async def prochaine_question_session(db: AsyncSession, session: SessionTrame) -> question_selector.ResultatSelection:
    trame = await db.get(TrameTemplate, session.trame_template_id)
    offres = await charger_offres_actives(db, session.categorie_slug)
    regles = await charger_regles_actives(db, session.categorie_slug)
    return question_selector.prochaine_question(
        trame.definition,
        session.reponses,
        offres=[_offre_vers_dict(o) for o in offres],
        regles=[_regle_vers_dict(r) for r in regles],
    )


async def enregistrer_reponse(db: AsyncSession, session: SessionTrame, question_id: str, valeur: Any) -> None:
    # Réassignation complète du dict (plutôt qu'une mutation en place) :
    # SQLAlchemy ne détecte pas les mutations in-place d'une colonne JSONB
    # sans sqlalchemy.ext.mutable, la réassignation garantit que le UPDATE
    # est bien émis.
    reponses = {**(session.reponses or {}), question_id: valeur}

    if question_id == "ville" and isinstance(valeur, str):
        cible = CIBLE_QUALITE_RESEAU_PAR_CATEGORIE.get(session.categorie_slug)
        if cible:
            operateur_actuel = reponses.get("operateur_actuel")
            qualite_inferee = await _inferer_qualite_reseau(
                db, valeur, operateur_actuel if isinstance(operateur_actuel, str) else None
            )
            if qualite_inferee is not None:
                reponses[cible] = qualite_inferee

    session.reponses = reponses
    await db.flush()


async def calculer_recommandations(db: AsyncSession, session: SessionTrame) -> list[dict[str, Any]]:
    """Calcule le classement d'offres + alertes pour l'état courant de la
    session et le persiste (remplace les recommandations précédentes de
    cette session — pas d'historisation des scores intermédiaires en MVP)."""
    offres_orm = await charger_offres_actives(db, session.categorie_slug)
    regles_orm = await charger_regles_actives(db, session.categorie_slug)
    regles = [_regle_vers_dict(r) for r in regles_orm]
    offres_dict = [_offre_vers_dict(o) for o in offres_orm]
    offres_par_id = {str(o.id): o for o in offres_orm}

    classement = scoring.score_offres(offres_dict, session.reponses, regles)[:NB_RECOMMANDATIONS_MAX]

    await db.execute(delete(Recommandation).where(Recommandation.session_id == session.id))

    # Reponse conventionnelle optionnelle "cout_actuel_mensuel" — permet de
    # chiffrer l'économie quand la trame la collecte ; absente, l'économie
    # reste simplement non calculée (pas d'erreur).
    cout_actuel = (session.reponses or {}).get("cout_actuel_mensuel")

    resultats: list[dict[str, Any]] = []
    for entree in classement:
        offre_orm = offres_par_id[entree["offre"]["id"]]
        alertes_offre = severite_normalisee(alertes.generer_alertes(entree["offre"], session.reponses, regles))

        economie_mensuelle = None
        if cout_actuel is not None and offre_orm.prix_mensuel is not None:
            economie_mensuelle = float(cout_actuel) - float(offre_orm.prix_mensuel)
        economie_annuelle = economie_mensuelle * 12 if economie_mensuelle is not None else None

        db.add(
            Recommandation(
                session_id=session.id,
                offre_id=offre_orm.id,
                score=entree["score"],
                rang=entree["rang"],
                justifications=entree["justifications"],
                alertes=alertes_offre,
                economie_mensuelle=economie_mensuelle,
                economie_annuelle=economie_annuelle,
            )
        )
        resultats.append(
            {
                "offre": offre_orm,
                "offre_id": offre_orm.id,
                "score": entree["score"],
                "rang": entree["rang"],
                "justifications": entree["justifications"],
                "alertes": alertes_offre,
                "economie_mensuelle": economie_mensuelle,
                "economie_annuelle": economie_annuelle,
            }
        )
    await db.flush()
    return resultats


async def finaliser_session(db: AsyncSession, session: SessionTrame) -> None:
    session.etat = "terminee"
    session.terminee_le = datetime.now(timezone.utc)
    await db.flush()
