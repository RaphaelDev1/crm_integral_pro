# ==============================================================================
#  MISE À NIVEAU TRAME v2 — RÉSEAU. `seed_ia_conseil()`/`seed_ia_conseil_box()`
#  sont idempotents en s'arrêtant dès que la `Categorie` existe déjà (voir
#  seed_ia_conseil.py::seed_ia_conseil) : rééditer TRAME_MOBILE_V1/TRAME_BOX_V1
#  dans ces modules ne met donc à jour QUE les installations pas encore
#  seedées. Ce script complète les installations déjà seedées : il insère une
#  nouvelle version de trame_template (mobile + box) reprenant la définition
#  à jour (avec satisfaction_reseau/defaut_technique/veut_rester, voir PLAN
#  "Fusionner la trame IA Conseil dans Nouveau diagnostic"), et désactive
#  l'ancienne version — pattern version/actif déjà prévu par TrameTemplate.
#  Idempotent : ne fait rien si la dernière version active contient déjà
#  "satisfaction_reseau".
#
#  Usage :
#      python -m backend.scripts.seed_ia_conseil_trame_reseau_v2
# ==============================================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.ia_conseil import TrameTemplate
from backend.scripts.seed_ia_conseil import TRAME_MOBILE_V1, _pg_engine
from backend.scripts.seed_ia_conseil_box import TRAME_BOX_V1

_DEFINITIONS = {"mobile": TRAME_MOBILE_V1, "box": TRAME_BOX_V1}


def _contient_questions_reseau(definition: dict) -> bool:
    ids = {q["id"] for section in definition.get("sections", []) for q in section.get("questions", [])}
    return "satisfaction_reseau" in ids


def mettre_a_niveau(categorie_slug: str, nouvelle_definition: dict, session: Session) -> bool:
    derniere = session.execute(
        select(TrameTemplate)
        .where(TrameTemplate.categorie_slug == categorie_slug, TrameTemplate.actif.is_(True))
        .order_by(TrameTemplate.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    if derniere is None or _contient_questions_reseau(derniere.definition):
        return False

    session.add(
        TrameTemplate(
            categorie_slug=categorie_slug,
            version=derniere.version + 1,
            definition=nouvelle_definition,
            actif=True,
        )
    )
    derniere.actif = False
    return True


def main() -> None:
    engine = _pg_engine()
    with Session(engine) as session:
        maj = [slug for slug, defn in _DEFINITIONS.items() if mettre_a_niveau(slug, defn, session)]
        session.commit()
        if maj:
            print(f"Trame(s) mise(s) à niveau : {', '.join(maj)}.")
        else:
            print("Aucune trame à mettre à niveau (déjà à jour ou pas encore seedée).")


if __name__ == "__main__":
    main()
