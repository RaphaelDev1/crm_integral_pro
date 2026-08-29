# ==============================================================================
#  TESTS D'INTÉGRATION — trames + catalogues + règles des 4 catégories MVP
#  (mobile, box, energie_elec, energie_gaz). PLAN_IMPLEMENTATION_4_PHASES.md
#  §1.1 : garde-fou anti-régression sur le principe escargot (la trame se
#  termine en nombre borné de questions) et sur le moteur de scoring (au
#  moins 3 recommandations non vides par profil client type). Même idiome
#  hors-ligne (pas de Postgres) que test_seed_ia_conseil.py.
# ==============================================================================
from backend.rules_engine import question_selector, scoring
from backend.scripts import seed_ia_conseil_box as box
from backend.scripts import seed_ia_conseil_energie as energie
from backend.scripts.seed_ia_conseil import TRAME_MOBILE_V1
from backend.scripts.seed_ia_conseil import _construire_fournisseurs as _construire_fournisseurs_mobile
from backend.scripts.seed_ia_conseil import _construire_offres as _construire_offres_mobile
from backend.scripts.seed_ia_conseil import _construire_regles as _construire_regles_mobile

MAX_QUESTIONS = 40  # garde-fou anti-boucle-infinie pour le test lui-même
NB_RECOS_MIN = 3


def _fournisseurs_avec_id(construire_fournisseurs, *args):
    fournisseurs = construire_fournisseurs(*args)
    for i, f in enumerate(fournisseurs.values()):
        f.id = f"fournisseur-{i}"
    return fournisseurs


def _offres_dicts(offres_orm):
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


def _regles_dicts(regles_orm):
    return [
        {"nom": r.nom, "type": r.type, "priorite": r.priorite, "condition": r.condition, "action": r.action, "actif": True}
        for r in regles_orm
    ]


def _derouler_trame(trame, offres, regles, reponses_cibles: dict) -> dict:
    """Simule une session complète : répond à chaque question posée par le
    sélecteur "escargot" avec la valeur prévue dans `reponses_cibles` (ou 1
    par défaut), jusqu'à ce que la trame se termine. Renvoie les réponses
    finales."""
    reponses: dict = {}
    for _ in range(MAX_QUESTIONS):
        resultat = question_selector.prochaine_question(trame, reponses, offres=offres, regles=regles)
        if resultat.question is None:
            return reponses
        qid = resultat.question["id"]
        reponses[qid] = reponses_cibles.get(qid, 1)
    raise AssertionError(f"La trame ne s'est jamais terminée en {MAX_QUESTIONS} questions (réponses : {reponses}).")


# ==============================================================================
#  MOBILE
# ==============================================================================
class TestMobile:
    _fournisseurs = _fournisseurs_avec_id(_construire_fournisseurs_mobile)
    _offres = _offres_dicts(_construire_offres_mobile(_fournisseurs))
    _regles = _regles_dicts(_construire_regles_mobile())

    PROFILS = {
        "petit_rouleur_prix_avant_tout": {"nb_lignes": 1, "conso_data_go": 2, "roaming_ue": "Jamais", "sensibilite_prix": "Prix avant tout"},
        "famille_gros_rouleur_roaming": {"nb_lignes": 4, "conso_data_go": 80, "roaming_ue": "Souvent", "roaming_hors_ue": "Occasionnellement", "meme_operateur_famille": True},
        "qualite_avant_tout": {"nb_lignes": 1, "conso_data_go": 30, "qualite_reseau": "Mauvaise", "sensibilite_prix": "Qualité avant tout", "5g_importante": True},
    }

    def test_chaque_profil_termine_et_produit_au_moins_trois_recommandations(self):
        for nom_profil, cible in self.PROFILS.items():
            reponses = _derouler_trame(TRAME_MOBILE_V1, self._offres, self._regles, cible)
            classement = scoring.score_offres(self._offres, reponses, self._regles)
            assert len(classement) >= NB_RECOS_MIN, f"[{nom_profil}] seulement {len(classement)} recommandation(s)"


# ==============================================================================
#  BOX
# ==============================================================================
class TestBox:
    _fournisseurs = _fournisseurs_avec_id(box._construire_fournisseurs)
    _offres = _offres_dicts(box._construire_offres(_fournisseurs))
    _regles = _regles_dicts(box._construire_regles())

    PROFILS = {
        "non_eligible_fibre_prix_avant_tout": {"type_logement": "Maison", "eligibilite_fibre": "Non", "nb_utilisateurs_simultanes": 2, "sensibilite_prix": "Prix avant tout"},
        "eligible_fibre_teletravail": {"type_logement": "Appartement", "eligibilite_fibre": "Oui", "nb_utilisateurs_simultanes": 2, "teletravail": True},
        "famille_nombreuse_streaming": {"type_logement": "Maison", "eligibilite_fibre": "Oui", "nb_utilisateurs_simultanes": 5, "usage_streaming_4k_gaming": True, "tv_incluse_souhaitee": True},
    }

    def test_chaque_profil_termine_et_produit_au_moins_trois_recommandations(self):
        for nom_profil, cible in self.PROFILS.items():
            reponses = _derouler_trame(box.TRAME_BOX_V1, self._offres, self._regles, cible)
            classement = scoring.score_offres(self._offres, reponses, self._regles)
            assert len(classement) >= NB_RECOS_MIN, f"[{nom_profil}] seulement {len(classement)} recommandation(s)"

    def test_offre_fibre_exclue_si_non_eligible(self):
        reponses = {"eligibilite_fibre": "Non"}
        classement = scoring.score_offres(self._offres, reponses, self._regles)
        assert all(r["offre"]["caracteristiques"]["technologie"] != "fibre" for r in classement)
        assert len(classement) >= NB_RECOS_MIN


# ==============================================================================
#  ÉNERGIE — ÉLECTRICITÉ
# ==============================================================================
class TestEnergieElec:
    _fournisseurs = _fournisseurs_avec_id(energie._construire_fournisseurs, energie._FOURNISSEURS_ELEC, energie.CATEGORIE_SLUG_ELEC)
    _offres = _offres_dicts(energie._construire_offres_elec(_fournisseurs))
    _regles = _regles_dicts(energie._construire_regles_elec())

    PROFILS = {
        "petit_conso_appartement": {"type_logement": "Appartement", "surface_m2": 40, "nb_occupants": 1, "consommation_elec_kwh_an": 1500, "puissance_compteur_kva": "6"},
        "gros_conso_verte": {"type_logement": "Maison", "surface_m2": 140, "nb_occupants": 4, "consommation_elec_kwh_an": 9500, "chauffage_electrique": True, "heures_creuses_interessant": True, "energie_verte_importante": True},
        "prix_avant_tout": {"type_logement": "Appartement", "surface_m2": 60, "nb_occupants": 2, "consommation_elec_kwh_an": 4000, "sensibilite_prix_energie": "Prix avant tout"},
    }

    def test_chaque_profil_termine_et_produit_au_moins_trois_recommandations(self):
        for nom_profil, cible in self.PROFILS.items():
            reponses = _derouler_trame(energie.TRAME_ENERGIE_ELEC_V1, self._offres, self._regles, cible)
            classement = scoring.score_offres(self._offres, reponses, self._regles)
            assert len(classement) >= NB_RECOS_MIN, f"[{nom_profil}] seulement {len(classement)} recommandation(s)"


# ==============================================================================
#  ÉNERGIE — GAZ
# ==============================================================================
class TestEnergieGaz:
    _fournisseurs = _fournisseurs_avec_id(energie._construire_fournisseurs, energie._FOURNISSEURS_GAZ, energie.CATEGORIE_SLUG_GAZ)
    _offres = _offres_dicts(energie._construire_offres_gaz(_fournisseurs))
    _regles = _regles_dicts(energie._construire_regles_gaz())

    PROFILS = {
        "cuisson_uniquement": {"type_logement": "Appartement", "surface_m2": 35, "nb_occupants": 1, "consommation_gaz_kwh_an": 1000, "usage_gaz": "Cuisson uniquement"},
        "chauffage_gros_conso": {"type_logement": "Maison", "surface_m2": 130, "nb_occupants": 4, "consommation_gaz_kwh_an": 17000, "usage_gaz": "Chauffage + eau chaude + cuisson"},
        "verte_prioritaire": {"type_logement": "Maison", "surface_m2": 90, "nb_occupants": 3, "consommation_gaz_kwh_an": 8000, "energie_verte_importante_gaz": True, "sensibilite_prix_energie_gaz": "Origine renouvelable"},
    }

    def test_chaque_profil_termine_et_produit_au_moins_trois_recommandations(self):
        for nom_profil, cible in self.PROFILS.items():
            reponses = _derouler_trame(energie.TRAME_ENERGIE_GAZ_V1, self._offres, self._regles, cible)
            classement = scoring.score_offres(self._offres, reponses, self._regles)
            assert len(classement) >= NB_RECOS_MIN, f"[{nom_profil}] seulement {len(classement)} recommandation(s)"
