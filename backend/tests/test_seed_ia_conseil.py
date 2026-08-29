# ==============================================================================
#  TESTS — scripts/seed_ia_conseil.py. Vérifications structurelles hors-ligne
#  (pas de Postgres) : les données de seed sont cohérentes et la trame mobile
#  réelle, une fois injectée dans rules_engine, produit bien un parcours qui
#  se termine (principe "escargot", pas de boucle infinie ni de blocage).
# ==============================================================================
from backend.rules_engine import question_selector, scoring, trame_runtime
from backend.scripts.seed_ia_conseil import (
    CATEGORIE_SLUG,
    TRAME_MOBILE_V1,
    _construire_fournisseurs,
    _construire_offres,
    _construire_regles,
)


def test_vingt_fournisseurs_mobiles_uniques():
    fournisseurs = _construire_fournisseurs()
    assert len(fournisseurs) == 10
    assert all(f.categorie_slug == CATEGORIE_SLUG for f in fournisseurs.values())


def test_vingt_offres_mobiles_referencent_un_fournisseur_connu():
    fournisseurs = _construire_fournisseurs()
    for f in fournisseurs.values():
        f.id = f.nom  # substitut simple d'UUID pour ce test hors DB
    offres = _construire_offres(fournisseurs)
    assert len(offres) == 20
    ids_connus = {f.id for f in fournisseurs.values()}
    assert all(o.fournisseur_id in ids_connus for o in offres)
    assert all(o.categorie_slug == CATEGORIE_SLUG for o in offres)
    assert all("data_go" in o.caracteristiques for o in offres)


def test_quinze_regles_bien_formees():
    regles = _construire_regles()
    assert len(regles) == 15
    for regle in regles:
        assert regle.type in ("filtre", "scoring", "alerte")
        assert regle.categorie_slug == CATEGORIE_SLUG
        assert isinstance(regle.condition, dict) and regle.condition
        assert isinstance(regle.action, dict) and regle.action
        assert regle.action.get("kind") in ("exclude", "score_adjust", "warn")


def _regles_dicts():
    return [
        {"nom": r.nom, "type": r.type, "priorite": r.priorite, "condition": r.condition, "action": r.action, "actif": True}
        for r in _construire_regles()
    ]


def _offres_dicts():
    fournisseurs = _construire_fournisseurs()
    for i, f in enumerate(fournisseurs.values()):
        f.id = f"fournisseur-{i}"
    offres_orm = _construire_offres(fournisseurs)
    return [
        {
            "id": str(i),
            "nom": o.nom,
            "prix_mensuel": o.prix_mensuel,
            "engagement_mois": o.engagement_mois,
            "caracteristiques": o.caracteristiques,
        }
        for i, o in enumerate(offres_orm)
    ]


class TestTrameMobileSeTermine:
    def test_parcours_petit_rouleur_se_termine_en_nombre_de_questions_borne(self):
        offres = _offres_dicts()
        regles = _regles_dicts()
        reponses = {}
        for _ in range(30):  # garde-fou anti-boucle-infinie pour le test lui-même
            resultat = question_selector.prochaine_question(TRAME_MOBILE_V1, reponses, offres=offres, regles=regles)
            if resultat.question is None:
                break
            qid = resultat.question["id"]
            reponses[qid] = {"nb_lignes": 1, "conso_data_go": 3, "roaming_ue": "Jamais"}.get(qid, 1)
        else:
            raise AssertionError("La trame ne s'est jamais terminée en 30 questions.")

        assert trame_runtime.is_terminee(TRAME_MOBILE_V1, reponses) or resultat.question is None
        assert "conso_data_go" in reponses  # question à fort score_info bien posée

    def test_scoring_et_alertes_s_executent_sans_erreur_sur_les_offres_seedees(self):
        offres = _offres_dicts()
        regles = _regles_dicts()
        reponses = {"conso_data_go": 3, "roaming_ue": "Souvent", "sensibilite_prix": "Prix avant tout"}

        classement = scoring.score_offres(offres, reponses, regles)

        assert len(classement) > 0
        assert all(0 <= r["score"] <= 100 for r in classement)
        assert classement == sorted(classement, key=lambda r: r["score"], reverse=True)

    def test_anti_survente_penalise_bien_les_gros_forfaits_pour_petit_rouleur(self):
        offres = _offres_dicts()
        regles = _regles_dicts()
        reponses = {"conso_data_go": 2}

        classement = scoring.score_offres(offres, reponses, regles)
        par_data_go = {r["offre"]["caracteristiques"]["data_go"]: r["score"] for r in classement}

        petit_forfait = min(o["caracteristiques"]["data_go"] for o in offres if o["caracteristiques"]["data_go"] <= 40)
        gros_forfait = max(o["caracteristiques"]["data_go"] for o in offres)
        assert par_data_go[petit_forfait] > par_data_go[gros_forfait]
