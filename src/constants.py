# ==============================================================================
#  CONSTANTES / OPTIONS MÉTIER — listes déroulantes partagées par toute l'app
# ==============================================================================
DEBITS_OPTIONS       = ["100 Mbps", "400 Mbps", "1 Gbps", "2 Gbps", "5 Gbps", "8 Gbps"]
LISTE_OPERATEURS_TEL = ["Orange", "YouPrice (Réseau Orange)", "SFR", "Bouygues", "Free", "Autre / Aucun"]
LISTE_FOURNISSEURS_ENERGIE = ["EDF", "Engie", "TotalEnergies", "Eni", "Vattenfall", "Ekwateur", "OHM Énergie", "Autre / Aucun"]
LISTE_TECHNO         = ["FIBRE", "ADSL", "5G", "4G"]
LISTE_TECHNO_MOBILE  = ["5G", "4G"]
SATISFACTION_RESEAU  = ["😀 Très content", "😐 Ça va", "😡 Pas du tout"]
SATISFACTION_SCORE   = {"😀 Très content": 3, "😐 Ça va": 2, "😡 Pas du tout": 1}

# Sentinelle utilisée pour forcer une réponse explicite du conseiller sur les champs
# obligatoires du diagnostic (opérateur actuel, satisfaction réseau) plutôt que de
# laisser une valeur par défaut faussement "remplie" (ex. satisfaction pré-cochée
# "Très content" sans avoir réellement posé la question au client).
SENTINEL_NON_RENSEIGNE          = "— À sélectionner —"
SATISFACTION_RESEAU_OBLIGATOIRE = [SENTINEL_NON_RENSEIGNE] + SATISFACTION_RESEAU
LISTE_OPERATEURS_TEL_OBLIGATOIRE = [SENTINEL_NON_RENSEIGNE] + LISTE_OPERATEURS_TEL

UNIVERS              = ["Télécom", "Énergie", "Abonnements"]
CATEGORIES_TELECOM   = ["Mobile", "Box / Fibre", "Pack Box + Mobile", "Multi-lignes"]
CATEGORIES_ENERGIE   = ["Électricité", "Gaz", "Électricité Pro", "Gaz Pro"]
CATEGORIES_ABO       = ["Streaming Vidéo", "Musique", "Salle de sport", "SaaS / Logiciel", "Assurance", "Autre"]
SERVICE_PRINCIPAL    = ["Mobile uniquement", "Box / Fibre uniquement", "Pack Box + Mobile", "Multi-lignes"]

ROLES = ["Admin", "Conseiller", "Lecture"]

STATUTS_FACTURE = ["Devis envoyé", "Payé", "Démarches en cours", "Terminé"]
