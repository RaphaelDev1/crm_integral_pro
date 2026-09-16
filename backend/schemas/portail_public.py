# ==============================================================================
#  SCHEMAS PORTAIL PUBLIC — vue simplifiée du dossier, exposée au client via
#  son lien unique. On ne remonte que le strict nécessaire — pas de données
#  internes conseiller, pas de commissions, pas de refs autres clients.
# ==============================================================================
from pydantic import BaseModel


class DocumentRecuOut(BaseModel):
    """Un fichier déjà transmis pour un type de document donné — un même
    type_document (ex. "facture") peut en avoir plusieurs, voir
    backend/routers/portail_public.py::_uploader_document_prospect."""
    document_id: int
    nom_fichier: str | None = None
    date_upload: str | None = None


class DocumentDemandeOut(BaseModel):
    """Un document que le client doit uploader."""
    type_document: str          # "cni", "justificatif_domicile", "rib"
    label_affiche: str          # "Pièce d'identité", "Justificatif de domicile", etc.
    statut: str                 # "a_fournir", "en_attente", "valide", "rejete"
    motif_rejet: str | None = None
    date_upload: str | None = None
    # Tous les fichiers déjà transmis pour ce type (ex. plusieurs factures) —
    # `date_upload` ci-dessus reste le plus récent, pour compat affichage.
    fichiers_recus: list[DocumentRecuOut] = []


class OptionChampDemarcheOut(BaseModel):
    valeur: str
    label: str


class ChampDemarchePublicOut(BaseModel):
    """Un champ que le client doit renseigner pour une démarche (RIO, PDL/PCE, RIB...)."""
    cle: str
    label: str
    valeur: str | None = None
    requis: bool = True
    # "texte" (input libre, par défaut) ou "choix" (boutons parmi `options`) —
    # voir document_engine.CHAMPS_REQUIS_PAR_TEMPLATE.
    type: str = "texte"
    options: list[OptionChampDemarcheOut] | None = None
    # Texte d'aide affiché sous le champ (ex. comment obtenir son RIO).
    aide: str | None = None


class DemarcheAFournirOut(BaseModel):
    """Une démarche dont il manque des champs à compléter côté client."""
    demarche_id: int
    type_demarche: str
    statut: str
    champs: list[ChampDemarchePublicOut]


class ChampsDemarchePublicUpdate(BaseModel):
    valeurs: dict[str, str]


class SituationActuellePublicIn(BaseModel):
    """Ce que le prospect renseigne lui-même sur sa situation réseau actuelle,
    depuis son lien personnel — mêmes champs que le bloc "Situation actuelle"
    de components/clients/ContratForm.tsx côté conseiller, appliqués au
    contrat concurrent (Contrat.chez_nous=False) du prospect."""
    operateur_actuel: str | None = None
    satisfaction_reseau: str | None = None
    veut_rester: str | None = None
    defaut_technique: str | None = None
    # Montant mensuel exact — alternative à l'envoi d'une facture quand le
    # prospect ne veut pas la chercher (voir la ligne "montant exact" par
    # univers sur documents/page.tsx côté frontend-portail). Écrit directement
    # sur Contrat.cout_mensuel.
    cout_mensuel: float | None = None
    # Précise à quelle ligne (mobile OU box) ces réponses se rapportent — voir
    # GET /{token}/contrats-telecom, la même liste que celle proposée avant un
    # test de débit. Optionnel : sans sélection explicite, on retombe sur
    # l'ancien comportement (voir _contrat_situation_actuelle_prospect).
    contrat_id: int | None = None
    # Catégorie de la ligne concurrente à cibler/créer quand `contrat_id` n'est
    # pas connu (ex. "Énergie électricité", "Abonnement") — voir
    # _contrat_situation_actuelle_prospect. Ignoré si `contrat_id` est fourni.
    categorie: str | None = None

    # ==========================================================================
    #  TRAME MOBILE (docs/QUESTIONS_PAR_SECTEUR.md) — voir backend/routers/
    #  portail_public.py::renseigner_situation_actuelle pour le routage
    #  Prospect (socle, posé une fois) vs Contrat (par ligne).
    # ==========================================================================
    # Socle (S5/M1/M5) — Prospect.objectif_principal/nb_lignes_mobiles/
    # qualite_reseau_mobile, indépendants de la ligne.
    objectif_principal: str | None = None
    nb_lignes_mobiles: str | None = None
    qualite_reseau_mobile: str | None = None
    # Identité (requise par la page "informations personnelles" du tunnel de
    # souscription Free Mobile, voir souscription_engine.py) — socle, posée
    # une seule fois, jamais par ligne.
    date_naissance: str | None = None
    departement_naissance: str | None = None
    ville_naissance: str | None = None
    # Par ligne (M3/M8) — écrits sur le Contrat ciblé.
    consommation: str | None = None
    date_fin_engagement: str | None = None
    # Portabilité (M-portabilité) — écrits sur le Contrat ciblé, uniquement
    # pertinents pour une ligne mobile.
    conserver_numero: str | None = None
    rio: str | None = None
    numero_ligne: str | None = None
    type_sim: str | None = None
    # Questions par secteur Box/Énergie (docs/QUESTIONS_PAR_SECTEUR.md), par
    # ligne — écrites sur le Contrat ciblé (mêmes champs que Contrat, voir
    # backend/models/contrat.py:74-87, ajoutés par la migration 0047).
    chauffage_principal: str | None = None
    puissance_kva: str | None = None
    option_tarifaire: str | None = None
    gros_equipement_electrique: bool | None = None
    usage_tv: str | None = None
    abonnements_payants: str | None = None
    # Trame Box B4/B5/B6/B7 (docs/QUESTIONS_PAR_SECTEUR.md), par ligne — posées
    # uniquement depuis le lien personnel (jamais /economiser).
    nb_utilisateurs_streaming: str | None = None
    usage_4k: bool | None = None
    teletravail: str | None = None
    interet_box_4g5g: str | None = None
    telephone_fixe_utilise: str | None = None
    appels_fixe_mensuels: str | None = None


class ContratTelecomPublicOut(BaseModel):
    """Un forfait mobile/box concurrent du client ou prospect, proposé comme
    choix avant de lancer un test de débit (voir GET /{token}/contrats-telecom).

    Les champs de situation (satisfaction/veut_rester/defaut_technique...) sont
    inclus pour permettre au prospect de pré-remplir le formulaire de
    /situation quand il revient modifier ses réponses (voir
    situation/page.tsx côté frontend-portail)."""
    id: int
    categorie: str | None = None
    fournisseur: str | None = None
    nom_offre: str | None = None
    satisfaction_reseau: str | None = None
    veut_rester: str | None = None
    defaut_technique: str | None = None
    situation_renseignee: bool = False
    consommation: str | None = None
    date_fin_engagement: str | None = None
    conserver_numero: str | None = None
    rio: str | None = None
    numero_ligne: str | None = None
    type_sim: str | None = None
    chauffage_principal: str | None = None
    puissance_kva: str | None = None
    option_tarifaire: str | None = None
    gros_equipement_electrique: bool | None = None
    usage_tv: str | None = None
    abonnements_payants: str | None = None
    nb_utilisateurs_streaming: str | None = None
    usage_4k: bool | None = None
    teletravail: str | None = None
    interet_box_4g5g: str | None = None
    telephone_fixe_utilise: str | None = None
    appels_fixe_mensuels: str | None = None
    # Débit mesuré (speedtest, prioritaire) et débit auto-déclaré (fallback) —
    # exposés pour que /situation puisse contextualiser B1-bis/B6 (box 4G/5G)
    # sans requête supplémentaire. `nom_offre` porte "ADSL"/"Fibre" pour une
    # ligne box (voir leads_public.py::capturer_lead, `nom_offre=offre_box`).
    speed_down: float | None = None
    debit_declare: float | None = None


class TokenPublicContexte(BaseModel):
    """Vue publique du contexte du token — ce que le client voit en arrivant."""
    prenom_client: str
    nom_client: str
    dossier_id: int | None
    univers: str | None
    fournisseur_cible: str | None
    economie_annuelle_estimee: float
    statut_dossier: str | None
    conseiller_nom: str | None
    conseiller_telephone: str | None = None

    # Ce qu'il doit faire
    documents_a_fournir: list[DocumentDemandeOut]
    mandat_statut: str | None      # "a_signer", "signe", None
    peut_uploader_docs: bool
    peut_signer_mandat: bool
    demarches_a_completer: list[DemarcheAFournirOut] = []
    # Vrai une fois la trame adaptative par secteur (audit_*/portabilite, voir
    # demarches_engine.audit_secteur_complet) entièrement répondue — ou s'il
    # n'y en a aucune pour ce dossier. Tant que c'est faux, l'upload de
    # documents est refusé (voir POST /{token}/documents) : le frontend doit
    # orienter le client vers /dossier/[token]/questionnaire en premier.
    audit_complet: bool = True
    peut_renseigner_demarches: bool = True
    peut_transmettre_speedtest: bool = True
    speedtest_fait: bool = False
    peut_renseigner_situation: bool = False
    situation_renseignee: bool = False
    peut_voir_suivi: bool = False
    # Socle de la trame mobile (docs/QUESTIONS_PAR_SECTEUR.md), posé une seule
    # fois sur le Prospect (pas par ligne) — None pour un token client (pas
    # encore porté sur Client). Permet au formulaire /situation de pré-remplir
    # ces champs quand le prospect revient modifier ses réponses.
    objectif_principal: str | None = None
    nb_lignes_mobiles: str | None = None
    qualite_reseau_mobile: str | None = None
    date_naissance: str | None = None
    departement_naissance: str | None = None
    ville_naissance: str | None = None
    # Uniquement significatif pour un token prospect (voir TokenPublic.
    # remplissage_autonome) — True = le formulaire /situation masque les
    # questions confort B4-B7 (redemandées plus tard), False = le conseiller
    # répond avec le prospect au téléphone (formulaire complet).
    remplissage_autonome: bool = True
    # "a_signer" / "signe" / None — même principe que mandat_statut, mais pour
    # le mandat d'honoraires (backend/models/mandat_honoraires.py). Exposé dès
    # qu'un MandatHonoraires existe pour le dossier (pas seulement à l'étape
    # mandat_a_signer, contrairement à mandat_statut, puisque l'honoraire suit
    # la représentation).
    mandat_honoraires_statut: str | None = None
    # Vrai dès que le dossier a atteint (ou dépassé) l'étape "soumis_fournisseur"
    # de la timeline (voir dossier_engine.ETAPES_TIMELINE / construire_timeline).
    dossier_soumis_fournisseur: bool = False


class UploadResultOut(BaseModel):
    document_id: int
    type_detecte: str | None
    statut_kyc: str
    motif_rejet: str | None = None
    message: str


class SpeedtestResultatOut(BaseModel):
    """Résultat de la soumission — mesure numérique (LibreSpeed) ou capture
    fichier (fallback), jamais les deux à la fois."""
    speed_down: float | None = None
    speed_up: float | None = None
    document_id: int | None = None
    message: str


class SuiviEtape(BaseModel):
    """Une étape de timeline pour l'affichage client."""
    cle: str                    # "docs_demandes", "mandat_signe", ...
    label: str                  # "Vos documents nous parviennent"
    statut: str                 # "termine", "en_cours", "a_venir"
    date: str | None = None
    icone: str = "circle"


class SuiviDossierOut(BaseModel):
    dossier_id: int
    statut_actuel: str
    etapes: list[SuiviEtape]
    prochaine_action: str | None = None
    delai_estime: str | None = None
