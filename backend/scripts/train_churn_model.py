# ==============================================================================
#  TRAIN_CHURN_MODEL — entraîne (ou ré-entraîne) le modèle de churn IA Conseil
#  (§3.5, backend/services/churn_engine.py) à partir des souscriptions
#  conclues en base. Invocation manuelle, pas de tâche Celery planifiée —
#  contrairement aux autres jobs périodiques, ré-entraîner un modèle est une
#  décision qu'on ne veut pas déclencher automatiquement sans supervision.
#
#  Usage :
#      python -m backend.scripts.train_churn_model
#
#  Avec très peu de souscriptions conclues (< SEUIL_MIN_ECHANTILLONS), le
#  script n'entraîne PAS de modèle non significatif — il l'indique
#  clairement et backend/services/churn_engine.py::score_client() bascule
#  alors sur son repli heuristique.
# ==============================================================================
from __future__ import annotations

import asyncio

from backend.core.database import AsyncSessionLocal
from backend.services import churn_engine


async def _entrainer() -> dict:
    async with AsyncSessionLocal() as db:
        return await churn_engine.entrainer_modele(db)


def main() -> None:
    resultat = asyncio.run(_entrainer())

    if not resultat.get("suffisant"):
        print(f"[churn] {resultat['message']}")
        print(f"[churn] Échantillon actuel : {resultat['nb_echantillons']} souscription(s) conclue(s).")
        return

    print(f"[churn] Modèle entraîné sur {resultat['nb_echantillons']} souscription(s) conclue(s).")
    if resultat.get("accuracy_holdout") is not None:
        print(f"[churn] Précision (holdout) : {resultat['accuracy_holdout']:.2%}")
    print(f"[churn] Modèle sauvegardé : {churn_engine.MODEL_PATH}")
    print(f"[churn] Métriques sauvegardées : {churn_engine.METRICS_PATH}")


if __name__ == "__main__":
    main()
