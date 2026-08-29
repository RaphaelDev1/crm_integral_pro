# ==============================================================================
#  CHURN_ENGINE — prévision de churn et scoring client (§3.5). Modèle
#  scikit-learn baseline (RandomForest), persisté via joblib (pas de MLflow :
#  aucune infra ML existante dans ce repo, coût d'ajout disproportionné pour
#  un seul consommateur — voir PLAN_IMPLEMENTATION_4_PHASES.md §Décisions).
#
#  Avec très peu de Souscription réelles en dev, entraîner un modèle sur un
#  échantillon minuscule serait trompeur : entrainer_modele() refuse
#  d'entraîner (et le marque dans les métriques) sous SEUIL_MIN_ECHANTILLONS
#  lignes, et score_client() bascule alors sur un repli heuristique explicite
#  (`source: "heuristique"` dans la réponse) plutôt que d'appeler un modèle
#  non significatif.
#
#  proba_cross_sell reste toujours heuristique (pas de modèle dédié) : aucune
#  donnée historique d'acceptation/refus de suggestion cross-sell n'existe
#  dans ce schéma pour entraîner quoi que ce soit dessus.
# ==============================================================================
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ia_conseil import AlerteOverride, OffreConseil, SessionTrame, Souscription
from backend.services import cross_sell_engine

logger = logging.getLogger(__name__)

SEUIL_MIN_ECHANTILLONS = 30
STATUTS_CONCLUS = ("active", "resiliee", "annulee")
STATUTS_CHURN = ("resiliee", "annulee")

MODEL_DIR = Path(__file__).resolve().parent.parent / "ml_models"
MODEL_PATH = MODEL_DIR / "churn_model.joblib"
METRICS_PATH = MODEL_DIR / "churn_model_metrics.json"

FEATURE_ORDER = (
    "engagement_mois", "prix_mensuel_negocie", "nb_alertes_overridees",
    "canal_visio", "canal_telephone", "canal_physique",
)


def _features(souscription: Souscription, session: SessionTrame | None, offre: OffreConseil | None, nb_overrides: int) -> dict[str, float]:
    canal = session.canal if session else None
    return {
        "engagement_mois": float(offre.engagement_mois) if offre and offre.engagement_mois is not None else 0.0,
        "prix_mensuel_negocie": float(souscription.prix_mensuel_negocie or 0),
        "nb_alertes_overridees": float(nb_overrides),
        "canal_visio": 1.0 if canal == "visio" else 0.0,
        "canal_telephone": 1.0 if canal == "telephone" else 0.0,
        "canal_physique": 1.0 if canal == "physique" else 0.0,
    }


def _vecteur(features: dict[str, float]) -> list[float]:
    return [features[c] for c in FEATURE_ORDER]


async def _nb_alertes_overridees(db: AsyncSession, session_id) -> int:
    if session_id is None:
        return 0
    result = await db.execute(select(func.count()).select_from(AlerteOverride).where(AlerteOverride.session_id == session_id))
    return result.scalar_one() or 0


async def _lignes_entrainement(db: AsyncSession) -> list[tuple[dict[str, float], int]]:
    result = await db.execute(
        select(Souscription, SessionTrame, OffreConseil)
        .outerjoin(SessionTrame, Souscription.session_id == SessionTrame.id)
        .outerjoin(OffreConseil, Souscription.offre_id == OffreConseil.id)
        .where(Souscription.statut.in_(STATUTS_CONCLUS))
    )
    lignes: list[tuple[dict[str, float], int]] = []
    for souscription, session, offre in result.all():
        nb_overrides = await _nb_alertes_overridees(db, session.id if session else None)
        label = 1 if souscription.statut in STATUTS_CHURN else 0
        lignes.append((_features(souscription, session, offre, nb_overrides), label))
    return lignes


def _sauvegarder_metriques(metriques: dict[str, Any]) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metriques, ensure_ascii=False, indent=2), encoding="utf-8")


def _charger_metriques() -> dict[str, Any] | None:
    if not METRICS_PATH.is_file():
        return None
    try:
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _charger_modele():
    if not MODEL_PATH.is_file():
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        logger.exception("Échec du chargement du modèle de churn — repli heuristique.")
        return None


async def entrainer_modele(db: AsyncSession) -> dict[str, Any]:
    """Entraîne un RandomForest baseline sur les souscriptions conclues
    (active/résiliée/annulée). Sous SEUIL_MIN_ECHANTILLONS lignes, refuse
    d'entraîner (échantillon non significatif) et le documente dans les
    métriques — score_client() bascule alors sur le repli heuristique."""
    lignes = await _lignes_entrainement(db)
    resultat: dict[str, Any] = {
        "entraine_le": datetime.now(timezone.utc).isoformat(),
        "nb_echantillons": len(lignes),
        "seuil_min_echantillons": SEUIL_MIN_ECHANTILLONS,
    }

    if len(lignes) < SEUIL_MIN_ECHANTILLONS:
        resultat["suffisant"] = False
        resultat["message"] = (
            f"Échantillon insuffisant ({len(lignes)} < {SEUIL_MIN_ECHANTILLONS} souscriptions conclues) — "
            "repli heuristique utilisé par score_client()."
        )
        _sauvegarder_metriques(resultat)
        return resultat

    X = [_vecteur(f) for f, _ in lignes]
    y = [label for _, label in lignes]
    peut_stratifier = len(set(y)) > 1
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y if peut_stratifier else None
    )

    modele = RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")
    modele.fit(X_train, y_train)

    resultat["suffisant"] = True
    resultat["accuracy_holdout"] = float(accuracy_score(y_test, modele.predict(X_test))) if X_test else None
    resultat["feature_order"] = list(FEATURE_ORDER)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(modele, MODEL_PATH)
    _sauvegarder_metriques(resultat)
    return resultat


def _proba_churn_heuristique(souscriptions: list[Souscription]) -> float | None:
    """Repli simple sans modèle : proximité de la fin d'engagement de la
    souscription active la plus proche. None si le client n'a aucune
    souscription active (rien à prédire)."""
    actives = [s for s in souscriptions if s.statut == "active"]
    if not actives:
        return None
    fins = [s.fin_engagement for s in actives if s.fin_engagement is not None]
    if not fins:
        return 0.15
    jours_restants = (min(fins) - date.today()).days
    if jours_restants <= 60:
        return 0.55
    if jours_restants <= 180:
        return 0.30
    return 0.10


SEGMENTS = ("infidele", "econome", "premium", "ethique", "equilibre")


def _segmenter(sessions: list[SessionTrame], souscriptions: list[Souscription]) -> str:
    """Segmentation heuristique simple (pas un modèle) : priorité à
    'infidele' si une souscription a déjà été résiliée, sinon le trait
    dominant observé dans les réponses de trame du client."""
    if any(s.statut == "resiliee" for s in souscriptions):
        return "infidele"

    compteurs = {"econome": 0, "premium": 0, "ethique": 0}
    for session in sessions:
        for cle, valeur in (session.reponses or {}).items():
            if valeur == "Prix avant tout":
                compteurs["econome"] += 1
            elif valeur in ("Qualité avant tout", "Origine renouvelable"):
                compteurs["premium"] += 1
            if "verte" in cle and valeur is True:
                compteurs["ethique"] += 1

    if not any(compteurs.values()):
        return "equilibre"
    return max(compteurs, key=compteurs.get)


async def score_client(db: AsyncSession, client_id) -> dict[str, Any]:
    """Score un client : proba_churn (modèle si suffisamment entraîné, sinon
    repli heuristique explicite), proba_cross_sell (toujours heuristique) et
    segment (toujours heuristique). Ne lève jamais d'exception — un client
    sans souscription reçoit proba_churn=None plutôt qu'une erreur."""
    souscriptions = (
        await db.execute(select(Souscription).where(Souscription.client_id == client_id))
    ).scalars().all()
    sessions = (
        await db.execute(select(SessionTrame).where(SessionTrame.client_id == client_id))
    ).scalars().all()

    metriques = _charger_metriques()
    modele = _charger_modele() if metriques and metriques.get("suffisant") else None

    proba_churn: float | None
    source: str
    plus_recente = max(souscriptions, key=lambda s: s.date_souscription or date.min, default=None) if souscriptions else None

    if modele is not None and plus_recente is not None:
        session = await db.get(SessionTrame, plus_recente.session_id) if plus_recente.session_id else None
        offre = await db.get(OffreConseil, plus_recente.offre_id) if plus_recente.offre_id else None
        nb_overrides = await _nb_alertes_overridees(db, session.id if session else None)
        features = _features(plus_recente, session, offre, nb_overrides)
        proba_churn = float(modele.predict_proba([_vecteur(features)])[0][1])
        source = "modele"
    else:
        proba_churn = _proba_churn_heuristique(souscriptions)
        source = "heuristique"

    suggestions = await cross_sell_engine.suggestions_cross_sell(db, client_id)
    proba_cross_sell = round(min(1.0, 0.2 * len(suggestions)), 2)

    return {
        "client_id": client_id,
        "proba_churn": proba_churn,
        "proba_cross_sell": proba_cross_sell,
        "segment": _segmenter(sessions, souscriptions),
        "source": source,
    }
