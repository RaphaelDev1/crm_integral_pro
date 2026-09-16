"""Schemas Pydantic v2 pour la landing publique /economiser.

Exposés par backend/routers/leads_public.py — non protégés par JWT, donc :
  - validation stricte (téléphone FR, âge borné, longueur limitée)
  - consentement RGPD obligatoire (refus 422 si False)
  - honeypot invisible pour bloquer les bots naïfs
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.services.estimation_publique import LIBELLES_TRANCHES_AGE

TELEPHONE_FR_RE = re.compile(r"^(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}$")


class DepensesActuelles(BaseModel):
    """Chaque champ est facultatif — le prospect peut ne remplir qu'une partie
    (télécom seul, énergie seule, mix des trois univers…). Bornes larges pour
    éviter tout rejet accidentel, mais suffisamment serrées pour bloquer un
    payload aberrant."""
    mobile: Optional[float] = Field(None, ge=0, le=500)
    box_fibre: Optional[float] = Field(None, ge=0, le=500)
    pack_box_mobile: Optional[float] = Field(None, ge=0, le=500)
    electricite: Optional[float] = Field(None, ge=0, le=2000)
    gaz: Optional[float] = Field(None, ge=0, le=2000)
    assurance_auto: Optional[float] = Field(None, ge=0, le=500)
    assurance_habitation: Optional[float] = Field(None, ge=0, le=500)
    assurance_sante: Optional[float] = Field(None, ge=0, le=800)

    def to_categories(self) -> dict[str, float]:
        """Traduit les champs typés en noms de catégories attendus par le moteur
        d'estimation (aligné sur `contrats.categorie` côté BDD)."""
        return {
            "Mobile": self.mobile or 0,
            "Box / Fibre": self.box_fibre or 0,
            "Pack Box + Mobile": self.pack_box_mobile or 0,
            "Électricité": self.electricite or 0,
            "Gaz": self.gaz or 0,
            "Assurance auto": self.assurance_auto or 0,
            "Assurance habitation": self.assurance_habitation or 0,
            "Assurance santé": self.assurance_sante or 0,
        }


OBJECTIFS_PRINCIPAUX = {"economiser", "simplifier", "ameliorer_qualite", "regrouper"}
NB_LIGNES_MOBILES = {"1", "2+"}
QUALITES_RESEAU = {"Bonne partout", "Moyenne ou mauvaise à un endroit"}
CHAUFFAGES_PRINCIPAUX = {"Électrique", "Gaz", "Bois / fioul / PAC", "Chauffage collectif inclus"}
PUISSANCES_KVA = {"3", "6", "9", "12+"}
OPTIONS_TARIFAIRES = {"Base", "Heures Pleines-Creuses", "Tempo"}
USAGES_TV = {"Jamais, uniquement streaming", "Quelques chaînes", "Bouquet premium"}


class AdresseIn(BaseModel):
    """Adresse sélectionnée via l'autocomplétion (Base Adresse Nationale) —
    posée uniquement si un secteur box ou énergie est sélectionné (socle S1,
    utilisée pour la vraie éligibilité fibre au niveau commune et donnée de
    contexte au conseiller). Reste facultative : un visiteur qui ne trouve pas
    son adresse dans les suggestions ne doit jamais être bloqué."""
    label: Optional[str] = Field(None, max_length=256)
    code_postal: Optional[str] = Field(None, max_length=10)
    ville: Optional[str] = Field(None, max_length=128)
    code_insee: Optional[str] = Field(None, max_length=8)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class UTM(BaseModel):
    """Paramètres UTM récupérés depuis la query string de la landing —
    persistés côté prospect pour l'attribution des campagnes."""
    source: Optional[str] = Field(None, max_length=64)
    medium: Optional[str] = Field(None, max_length=64)
    campaign: Optional[str] = Field(None, max_length=128)
    content: Optional[str] = Field(None, max_length=128)
    term: Optional[str] = Field(None, max_length=128)


class TouchpointIn(BaseModel):
    """Un point de contact de l'historique first-party constitué côté client
    par frontend-portail/lib/attribution.ts (localStorage) avant la conversion
    du visiteur en lead — sert l'attribution multi-touch (P4.3)."""
    utm: UTM = Field(default_factory=UTM)
    referrer: Optional[str] = Field(None, max_length=512)
    landing_page: Optional[str] = Field(None, max_length=512)
    horodatage: Optional[str] = Field(None, max_length=32)


class LeadEstimationRequest(BaseModel):
    prenom: str = Field(..., min_length=1, max_length=64)
    telephone: str = Field(..., min_length=10, max_length=20)
    email: Optional[str] = Field(None, max_length=254)
    # Un même prospect peut avoir un opérateur mobile différent de son
    # opérateur box — deux champs distincts, chacun alimenté par un menu
    # déroulant (liste connue + "Autre") côté formulaire.
    operateur_mobile: Optional[str] = Field(None, max_length=64)
    operateur_box: Optional[str] = Field(None, max_length=64)
    # "ADSL" ou "Fibre" — reprend Prospect.techno / Contrat.categorie, laissé
    # en texte libre pour rester tolérant si de nouvelles valeurs apparaissent.
    offre_box: Optional[str] = Field(None, max_length=32)
    debit_box: Optional[float] = Field(None, ge=0, le=10000)
    # Mêmes questions/valeurs que la trame mobile conseiller (conso_data_go /
    # roaming_ue / sensibilite_prix, voir backend/scripts/seed_ia_conseil.py) —
    # posées ici pour que le conseiller n'ait plus à les redemander au
    # téléphone (Prospect.data_go / roaming_europe / sensibilite_prix,
    # migration 0038_landing_roaming_priorite).
    conso_data_go: Optional[float] = Field(None, ge=0, le=1000)
    roaming_europe: Optional[str] = Field(None, max_length=32)
    # Voyage hors UE — complément de roaming_europe, mêmes valeurs (Jamais /
    # Occasionnellement / Souvent). Migration 0045_roaming_hors_ue.
    roaming_hors_ue: Optional[str] = Field(None, max_length=32)
    sensibilite_prix: Optional[str] = Field(None, max_length=32)
    # `age` reste accepté pour compat mais le formulaire n'envoie plus qu'une
    # tranche choisie dans un menu déroulant (voir estimation_publique.TRANCHES_AGE).
    age: Optional[int] = Field(None, ge=18, le=120)
    tranche_age: Optional[str] = Field(None, max_length=8)
    # Fournisseur d'énergie actuel — capturé au même titre que operateur_actuel
    # pour le télécom, pour pouvoir créer un Contrat "Actuel" exploitable.
    fournisseur_energie: Optional[str] = Field(None, max_length=64)
    depenses: DepensesActuelles
    # Adresse (socle S1) — posée si box ou énergie sélectionné, cf. AdresseIn.
    adresse: Optional[AdresseIn] = None
    # Socle commun S5 — pondère le scoring conseiller, posé quel que soit le
    # secteur choisi (question unique, à faible friction).
    objectif_principal: Optional[str] = Field(None, max_length=32)
    # Trame mobile (M1, M5) — voir docs/QUESTIONS_PAR_SECTEUR.md.
    nb_lignes_mobiles: Optional[str] = Field(None, max_length=8)
    qualite_reseau_mobile: Optional[str] = Field(None, max_length=64)
    # Trame énergie (E1, E5, E5a, E6) — posées uniquement si le secteur
    # énergie est sélectionné côté formulaire.
    chauffage_principal: Optional[str] = Field(None, max_length=32)
    puissance_kva: Optional[str] = Field(None, max_length=8)
    gros_equipement_electrique: Optional[bool] = None
    option_tarifaire: Optional[str] = Field(None, max_length=32)
    # Trame box (B3, B3b) — posées uniquement si une dépense box/fibre > 0.
    usage_tv: Optional[str] = Field(None, max_length=32)
    abonnements_payants: Optional[str] = Field(None, max_length=256)
    # Coefficient bonus/malus assurance auto (0.50 à 3.50 en France) — texte
    # libre pour rester tolérant à la saisie ("0.85", "1", "1,20"…).
    bonus_malus_auto: Optional[str] = Field(None, max_length=16)
    # Créneau souhaité pour être rappelé (étape 3 du formulaire).
    plage_horaire_rappel: Optional[str] = Field(None, max_length=64)
    consentement_rgpd: bool
    consentement_demarchage: bool = False
    utm: UTM = Field(default_factory=UTM)
    # Historique des points de contact avant conversion (attribution multi-touch,
    # P4.3) — plafonné pour éviter tout payload abusif, le premier et le dernier
    # élément suffisent à l'analyse (voir backend/routers/dashboard_utm.py).
    touchpoints: list[TouchpointIn] = Field(default_factory=list, max_length=20)
    # Token Cloudflare Turnstile — vérifié uniquement si TURNSTILE_SECRET_KEY
    # est configuré côté backend (sinon la vérification est un no-op).
    turnstile_token: Optional[str] = Field(None, max_length=2048)
    # Honeypot invisible — les bots remplissent, les humains ne voient rien.
    hp_field: Optional[str] = Field(None, max_length=256)

    @field_validator("telephone")
    @classmethod
    def valider_telephone(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not TELEPHONE_FR_RE.match(v):
            raise ValueError("Numéro de téléphone français invalide.")
        return v

    @field_validator("email")
    @classmethod
    def valider_email(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip().lower()
        # Validation regex simple — pas besoin de la dépendance `email-validator`
        # pour un champ optionnel (le SMS reste le canal principal).
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Email invalide.")
        return v

    @field_validator("consentement_rgpd")
    @classmethod
    def rgpd_obligatoire(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Le consentement RGPD est obligatoire.")
        return v

    @field_validator("tranche_age")
    @classmethod
    def valider_tranche_age(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in LIBELLES_TRANCHES_AGE:
            raise ValueError("Tranche d'âge invalide.")
        return v

    @field_validator("objectif_principal")
    @classmethod
    def valider_objectif_principal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in OBJECTIFS_PRINCIPAUX:
            raise ValueError("Objectif principal invalide.")
        return v

    @field_validator("nb_lignes_mobiles")
    @classmethod
    def valider_nb_lignes_mobiles(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in NB_LIGNES_MOBILES:
            raise ValueError("Nombre de lignes mobiles invalide.")
        return v

    @field_validator("qualite_reseau_mobile")
    @classmethod
    def valider_qualite_reseau_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in QUALITES_RESEAU:
            raise ValueError("Qualité réseau invalide.")
        return v

    @field_validator("chauffage_principal")
    @classmethod
    def valider_chauffage_principal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CHAUFFAGES_PRINCIPAUX:
            raise ValueError("Chauffage principal invalide.")
        return v

    @field_validator("puissance_kva")
    @classmethod
    def valider_puissance_kva(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PUISSANCES_KVA:
            raise ValueError("Puissance souscrite invalide.")
        return v

    @field_validator("option_tarifaire")
    @classmethod
    def valider_option_tarifaire(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in OPTIONS_TARIFAIRES:
            raise ValueError("Option tarifaire invalide.")
        return v

    @field_validator("usage_tv")
    @classmethod
    def valider_usage_tv(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in USAGES_TV:
            raise ValueError("Usage TV invalide.")
        return v


class LigneEstimationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    categorie: str
    cout_actuel_mensuel: float
    notre_moyenne_mensuel: float
    economie_mensuelle_basse: float
    economie_mensuelle_haute: float
    economie_annuelle_typique: float
    source: str          # "base_client" ou "marche_public"
    echantillon: int     # taille de l'échantillon (0 si fallback marché)
    tranche_age_utilisee: Optional[str] = None


class EstimationOut(BaseModel):
    lignes: list[LigneEstimationOut]
    economie_annuelle_totale_basse: float
    economie_annuelle_totale_haute: float
    economie_annuelle_totale_typique: float
    methodologie_url: str = "/economiser/methodologie"
    calculee_le: str


class FibreOut(BaseModel):
    """Résultat d'éligibilité fibre — au niveau commune (voir
    backend/services/eligibilite_fibre.py), jamais au niveau adresse exacte.
    `disponible`/`taux_couverture` restent None si le code INSEE est absent,
    si le service tiers est désactivé, ou en cas d'échec/timeout."""
    disponible: Optional[bool] = None
    taux_couverture: Optional[float] = None


class LeadEstimationResponse(BaseModel):
    ok: bool
    ref: str
    estimation: EstimationOut
    message: str
    fibre: FibreOut = Field(default_factory=FibreOut)


class MethodologieOut(BaseModel):
    principe: str
    fourchette: str
    categories_calibrees_base_reelle: list[str]
    categories_en_fallback_marche: list[str]
    derniere_maj: Optional[str] = None


class AdresseSuggestionOut(BaseModel):
    label: str
    code_postal: Optional[str] = None
    ville: Optional[str] = None
    code_insee: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class DetectionFaiOut(BaseModel):
    operateur_probable: Optional[str] = None
