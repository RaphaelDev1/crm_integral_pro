# ==============================================================================
#  PROSPECT — miroir de la table `prospects` (src/db.py, création + colonnes
#  ajoutées par _migrer_bdd()). Les dates restent des chaînes "%d/%m/%Y %H:%M"
#  pour rester compatibles avec le formatage utilisé côté Streamlit (src/app.py).
# ==============================================================================
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.contrat import Contrat


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Client "miroir" (cf. backend/services/prospect_conversion.py) : renseigné dès qu'un
    # dossier ou un token de documents pré-conversion a besoin d'un Client réel, réutilisé
    # (pas recréé) comme client définitif à la conversion.
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    # ClientConseil IA Conseil rattaché (cf. backend/services/ia_conseil_bridge.py) —
    # créé à la demande à l'entrée de l'étape "Trame" du diagnostic fusionné,
    # jamais recréé ensuite. Migration : 0037_ia_conseil_bridge.
    ia_conseil_client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("client.id"), nullable=True)
    converti_at: Mapped[str | None] = mapped_column(String, nullable=True)
    ref: Mapped[str | None] = mapped_column(String, nullable=True)
    prenom: Mapped[str | None] = mapped_column(String, nullable=True)
    nom: Mapped[str | None] = mapped_column(String, nullable=True)
    telephone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    code_postal: Mapped[str | None] = mapped_column(String, nullable=True)
    ville: Mapped[str | None] = mapped_column(String, nullable=True)
    adresse: Mapped[str | None] = mapped_column(String, nullable=True)
    type_client: Mapped[str | None] = mapped_column(String, nullable=True)
    # Renseignés uniquement pour type_client == "Professionnel" (voir
    # EtapeIdentite.tsx côté diagnostic) — raison_sociale : nom de l'entreprise,
    # effectif : tranche libre ("1", "2-5", "6-9", "10-19", "20+").
    raison_sociale: Mapped[str | None] = mapped_column(String, nullable=True)
    effectif: Mapped[str | None] = mapped_column(String, nullable=True)
    univers_interesse: Mapped[str | None] = mapped_column(String, nullable=True)
    service_principal: Mapped[str | None] = mapped_column(String, nullable=True)
    operateur_actuel: Mapped[str | None] = mapped_column(String, nullable=True)
    # Opérateur box, distinct de `operateur_actuel` (mobile) — un prospect peut
    # avoir deux opérateurs différents. `techno`/`speed_down` juste en dessous
    # sont réutilisés pour l'offre ADSL/Fibre et le débit box déclarés sur la
    # landing /economiser. Migration 0044.
    operateur_box: Mapped[str | None] = mapped_column(String, nullable=True)
    techno: Mapped[str | None] = mapped_column(String, nullable=True)
    data_go: Mapped[str | None] = mapped_column(String, nullable=True)
    # Mêmes questions/valeurs que la trame mobile (roaming_ue / sensibilite_prix,
    # voir backend/scripts/seed_ia_conseil.py) — désormais posées aussi sur la
    # landing publique /economiser. Migration : 0038_landing_roaming_priorite.
    roaming_europe: Mapped[str | None] = mapped_column(String, nullable=True)
    # Voyage hors UE ("roaming_hors_ue" dans la trame) — posé sur la landing
    # /economiser en complément de roaming_europe ci-dessus. Migration : 0045.
    roaming_hors_ue: Mapped[str | None] = mapped_column(String, nullable=True)
    sensibilite_prix: Mapped[str | None] = mapped_column(String, nullable=True)
    cout_mensuel_actuel: Mapped[float | None] = mapped_column(Float, default=0)
    offre_actuelle: Mapped[str | None] = mapped_column(String, nullable=True)
    satisfaction_reseau: Mapped[str | None] = mapped_column(String, nullable=True)
    veut_rester: Mapped[str | None] = mapped_column(String, nullable=True)
    # Signalement d'un défaut technique potentiel constaté sur le réseau actuel
    # du prospect ("Faible" | "Moyen" | "Critique"), voir NIVEAUX_DEFAUT_TECHNIQUE
    # côté frontend (lib/diagnosticConstants.ts).
    defaut_technique: Mapped[str | None] = mapped_column(String, nullable=True)
    speed_down: Mapped[float | None] = mapped_column(Float)
    speed_up: Mapped[float | None] = mapped_column(Float)
    # Débit auto-déclaré sur la landing publique (champ libre, jamais mesuré) —
    # distinct de speed_down/speed_up, réservés au test de débit réellement
    # effectué (voir portail_public.py::speedtest_fait). Migration 0046.
    debit_declare: Mapped[float | None] = mapped_column(Float, nullable=True)
    cout_elec: Mapped[float | None] = mapped_column(Float, default=0)
    cout_gaz: Mapped[float | None] = mapped_column(Float, default=0)
    fournisseur_energie: Mapped[str | None] = mapped_column(String, nullable=True)
    abonnements: Mapped[str | None] = mapped_column(String, nullable=True)
    lignes_multi: Mapped[str | None] = mapped_column(String, nullable=True)
    economie_estimee_an: Mapped[float | None] = mapped_column(Float, default=0)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    statut: Mapped[str | None] = mapped_column(String, default="À relancer")
    date_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    date_relance: Mapped[str | None] = mapped_column(String, nullable=True)
    cree_par: Mapped[str | None] = mapped_column(String, nullable=True)
    offres_interet: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, default=0)
    origine: Mapped[str | None] = mapped_column(String, default="Manuel")
    # ==========================================================================
    #  LANDING CAPTURE — colonnes de tracking pour leads capturés depuis la
    #  landing publique /economiser (campagnes TikTok/IG/Facebook). Alimentées
    #  uniquement par backend/routers/leads_public.py ; restent None pour les
    #  prospects créés manuellement. Migration : 0027_leads_capture.
    # ==========================================================================
    utm_source: Mapped[str | None] = mapped_column(String, nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String, nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String, nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String, nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tranche_age: Mapped[str | None] = mapped_column(String, nullable=True)
    consentement_rgpd: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consentement_demarchage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    date_consentement: Mapped[str | None] = mapped_column(String, nullable=True)
    ip_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent_creation: Mapped[str | None] = mapped_column(String, nullable=True)
    depenses_declarees_json: Mapped[str | None] = mapped_column(String, nullable=True)
    # ==========================================================================
    #  ENRICHISSEMENTS LANDING V3 — adresse/fibre (P2.1), validation téléphone
    #  Twilio Lookup (P2.2), FAI détecté par IP (P2.3), idempotence email J+1
    #  (P3.2). Migration : 0028_leads_enrichissements.
    # ==========================================================================
    code_insee: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Couverture FttH au niveau commune (pas d'API gratuite fiable au niveau
    # adresse exacte) — None = non vérifié/service indisponible.
    fibre_disponible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fibre_taux_couverture: Mapped[float | None] = mapped_column(Float, nullable=True)
    # None = non vérifié (Twilio Lookup non configuré ou appel en attente/échoué),
    # True/False = résultat Twilio Lookup — ne jamais masquer un lead sur un
    # None, uniquement sur un False explicite.
    telephone_verifie: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    telephone_type_ligne: Mapped[str | None] = mapped_column(String, nullable=True)
    operateur_detecte_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    email_j1_envoye: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # ==========================================================================
    #  SÉQUENCE DE NURTURING (P4.2) — emails éducatifs J+2 à J+5 pour les leads
    #  non convertis, dans la continuité de l'email récap J+1 ci-dessus.
    #  Idempotence par jour, même principe que email_j1_envoye.
    #  `email_desabonne` : désabonnement marketing (lien en pied d'email),
    #  distinct de `consentement_demarchage` (démarchage téléphonique).
    #  Migration : 0029_utm_dashboard_attribution.
    # ==========================================================================
    email_j2_envoye: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_j3_envoye: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_j4_envoye: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_j5_envoye: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_desabonne: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # ==========================================================================
    #  Coefficient bonus/malus assurance auto (étape 2 /economiser), créneau de
    #  rappel souhaité (étape 3) et motif de refus saisi par le conseiller.
    #  Migration : 0030_bonus_malus_plage_horaire_refus.
    # ==========================================================================
    bonus_malus_auto: Mapped[str | None] = mapped_column(String, nullable=True)
    plage_horaire_rappel: Mapped[str | None] = mapped_column(String, nullable=True)
    motif_refus: Mapped[str | None] = mapped_column(String, nullable=True)
    # Idempotence de la relance automatique demandant la facture au prospect
    # (voir backend/workers/tasks.py::demander_facture_prospects).
    # Migration : 0031_facture_prospect_auto.
    demande_facture_envoyee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # ==========================================================================
    #  SOCLE COMMUN + MOBILE — trame de questions par secteur de la landing
    #  /economiser (docs/QUESTIONS_PAR_SECTEUR.md), limitée aux questions qui
    #  décrivent la personne plutôt qu'un contrat précis (cf. Contrat pour les
    #  questions énergie/box). Migration : 0047_questions_par_secteur.
    # ==========================================================================
    # Objectif principal déclaré (S5) : "economiser" | "simplifier" |
    # "ameliorer_qualite" | "regrouper" — pondère le scoring conseiller.
    objectif_principal: Mapped[str | None] = mapped_column(String, nullable=True)
    # "1" ou "2+" (M1) — si "2+", le conseiller demande lui-même le détail des
    # lignes au téléphone plutôt que d'alourdir la landing.
    nb_lignes_mobiles: Mapped[str | None] = mapped_column(String, nullable=True)
    # "Bonne partout" | "Moyenne ou mauvaise à un endroit" (M5) — change la
    # priorité de la recommandation (couverture avant prix) selon la trame.
    qualite_reseau_mobile: Mapped[str | None] = mapped_column(String, nullable=True)
    # Date/lieu de naissance — requis par la page "informations personnelles"
    # du tunnel de souscription Free Mobile (voir souscription_engine.py).
    # date_naissance au format "JJ/MM/AAAA", comme les autres dates du projet.
    # Migration : 0053_date_lieu_naissance.
    date_naissance: Mapped[str | None] = mapped_column(String, nullable=True)
    departement_naissance: Mapped[str | None] = mapped_column(String, nullable=True)
    ville_naissance: Mapped[str | None] = mapped_column(String, nullable=True)

    contrats: Mapped[list["Contrat"]] = relationship(back_populates="prospect")
