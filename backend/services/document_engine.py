# ==============================================================================
#  DOCUMENT ENGINE — génération des PDF de démarche (mandat de représentation,
#  résiliation box, demande de portabilité mobile, changement de fournisseur
#  énergie, souscription) via fpdf2. Indépendant de `src/pdf_engine.py` — les
#  deux systèmes (`src/` et `backend/`) restent déployables séparément.
#
#  ⚠️ Les textes de courrier ci-dessous sont un boilerplate raisonnable, pas
#  encore relu par un avocat (même statut que le mandat existant dans
#  src/pdf_engine.py::generer_pdf_mandat) — voir SETUP_STATUS.md.
# ==============================================================================
from __future__ import annotations

import io
from datetime import datetime
from typing import Callable

from fpdf import FPDF

from backend.models.client import Client
from backend.models.dossier import Dossier
from backend.models.mandat_honoraires import MandatHonoraires

COULEUR_PRIMAIRE = (16, 42, 82)
COULEUR_ACCENT = (0, 150, 90)
COULEUR_GRIS = (110, 110, 110)
COULEUR_TEXTE = (35, 38, 45)
COULEUR_BORDURE = (222, 227, 235)
COULEUR_FOND_CARTE = (247, 249, 252)


def _txt(valeur) -> str:
    """Encode en latin-1 (fpdf2 sans police Unicode embarquée) en neutralisant
    les caractères non représentables plutôt que de planter la génération."""
    if valeur is None:
        return ""
    s = str(valeur)
    remplacements = {"’": "'", "–": "-", "—": "-", "•": "-", "œ": "oe", "€": "EUR"}
    for k, v in remplacements.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "ignore").decode("latin-1")


def _hex_vers_rgb(hex_couleur: str | None, defaut: tuple[int, int, int]) -> tuple[int, int, int]:
    if not hex_couleur:
        return defaut
    h = hex_couleur.lstrip("#")
    if len(h) != 6:
        return defaut
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return defaut


def _branding_defaut(branding: dict | None) -> tuple[str, tuple[int, int, int], tuple[int, int, int], bytes | None]:
    branding = branding or {}
    nom_societe = branding.get("nom_societe") or "IA CONSEIL"
    couleur_primaire = _hex_vers_rgb(branding.get("couleur_primaire_hex"), COULEUR_PRIMAIRE)
    couleur_accent = _hex_vers_rgb(branding.get("couleur_accent_hex"), COULEUR_ACCENT)
    return nom_societe, couleur_primaire, couleur_accent, branding.get("logo_bytes")


class PDFDemarche(FPDF):
    def __init__(self, titre: str):
        super().__init__()
        self._titre = titre

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*COULEUR_PRIMAIRE)
        self.cell(0, 12, _txt(self._titre), ln=True)
        self.set_draw_color(*COULEUR_BORDURE)
        self.line(10, 24, 200, 24)
        self.ln(6)
        self.set_text_color(*COULEUR_TEXTE)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*COULEUR_GRIS)
        self.cell(0, 10, _txt(f"Genere le {datetime.now().strftime('%d/%m/%Y')} - IA Conseil"), align="C")

    def paragraphe(self, texte: str, taille: int = 10.5, gras: bool = False, espace_apres: float = 4.0):
        self.set_font("Helvetica", "B" if gras else "", taille)
        self.set_text_color(*COULEUR_TEXTE)
        self.multi_cell(0, 6, _txt(texte))
        self.ln(espace_apres)

    def champ_signature(self, label_gauche: str = "Fait a ____________, le ____________",
                         label_droite: str = "Signature du client"):
        self.ln(10)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*COULEUR_GRIS)
        self.cell(95, 6, _txt(label_gauche))
        self.cell(95, 6, _txt(label_droite), ln=True)
        self.ln(20)
        self.set_draw_color(*COULEUR_BORDURE)
        self.line(115, self.get_y(), 195, self.get_y())


class PDFMandat(FPDF):
    """Habillage « vendeur » des mandats (bandeau de marque, cartes arrondies,
    pastilles) — copie indépendante du style de restitution_pdf_engine.py::
    PDFRestitution (même principe de découplage backend/src déjà en place
    entre ce module et restitution_pdf_engine.py, voir l'en-tête de fichier),
    utilisée uniquement par les deux mandats (représentation, honoraires) :
    ce sont les seuls documents de démarche que le client lit vraiment avant
    de signer, les autres restent des lettres administratives sobres
    (PDFDemarche ci-dessus)."""

    def __init__(self, sous_titre: str, nom_societe: str, couleur_primaire: tuple, couleur_accent: tuple, logo_bytes: bytes | None):
        super().__init__()
        self.sous_titre = sous_titre
        self.nom_societe = nom_societe
        self.couleur_primaire = couleur_primaire
        self.couleur_accent = couleur_accent
        self.logo_bytes = logo_bytes

    def header(self):
        self.set_fill_color(*self.couleur_accent)
        self.rect(0, 0, 210, 2.5, "F")
        self.set_fill_color(*self.couleur_primaire)
        self.rect(0, 2.5, 210, 27.5, "F")

        if self.logo_bytes:
            self.image(io.BytesIO(self.logo_bytes), x=12, y=6, h=19)
            texte_x = 34
        else:
            self.set_fill_color(255, 255, 255)
            self.circle(20, 16.5, 7, "F")
            initiales = "".join(w[0] for w in self.nom_societe.split()[:2]).upper() or "IA"
            self.set_xy(13, 13)
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*self.couleur_primaire)
            self.cell(14, 7, _txt(initiales), align="C")
            texte_x = 31

        self.set_xy(texte_x, 8.5)
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, _txt(self.nom_societe), ln=True)
        self.set_xy(texte_x, 16.5)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(200, 213, 232)
        self.cell(0, 6, _txt(self.sous_titre))

        self.set_text_color(0, 0, 0)
        self.set_y(37)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(*COULEUR_BORDURE)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*COULEUR_GRIS)
        self.cell(0, 5, _txt(
            f"{self.nom_societe} - Document genere le {datetime.now().strftime('%d/%m/%Y')}."), align="C")
        self.set_text_color(0, 0, 0)

    def rounded_card(self, x, y, w, h, r=3, fill=None, border=None, line_width=0.3):
        if fill is not None:
            self.set_fill_color(*fill)
        if border is not None:
            self.set_draw_color(*border)
            self.set_line_width(line_width)
        style = "DF" if fill is not None and border is not None else ("F" if fill is not None else "D")
        self.rect(x, y, w, h, style, round_corners=True, corner_radius=r)

    def pill(self, x, y, text, fill, text_color, h=6.0, font=("Helvetica", "B", 7.5), w=None):
        self.set_font(*font)
        txt = _txt(text)
        if w is None:
            w = self.get_string_width(txt) + 8
        self.set_fill_color(*fill)
        self.rect(x, y, w, h, "F", round_corners=True, corner_radius=h / 2)
        self.set_text_color(*text_color)
        self.set_xy(x, y)
        self.cell(w, h, txt, align="C")
        self.set_text_color(0, 0, 0)
        return w

    def paragraphe(self, texte: str, taille: float = 10, espace_apres: float = 4.0):
        self.set_font("Helvetica", "", taille)
        self.set_text_color(*COULEUR_TEXTE)
        self.multi_cell(0, 5.5, _txt(texte))
        self.set_text_color(0, 0, 0)
        self.ln(espace_apres)


def _bloc_identite_mandat(pdf: PDFMandat, client: Client, reference: str, titre: str):
    y0 = pdf.get_y()
    h = 26
    pdf.rounded_card(10, y0, 190, h, r=3, fill=COULEUR_FOND_CARTE, border=COULEUR_BORDURE)
    nom_complet = f"{client.prenom or ''} {client.nom or ''}".strip() or "Client"
    pdf.set_xy(16, y0 + 4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*pdf.couleur_primaire)
    pdf.cell(0, 7, _txt(f"{titre} - {nom_complet}"), ln=True)

    pdf.set_xy(16, y0 + 12)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.cell(0, 5.5, _txt(f"Reference : {reference}"))

    contacts = [c for c in (client.telephone, client.email) if c]
    if contacts:
        pdf.set_xy(16, y0 + 18)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(0, 5.5, _txt("   -   ".join(contacts)))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)


def _banniere_statut_signature(pdf: PDFMandat, signe: bool, date_signature: str | None):
    y0 = pdf.get_y()
    h = 14
    if signe:
        pdf.rounded_card(10, y0, 190, h, r=3, fill=pdf.couleur_accent)
        texte = f"Signe le {date_signature}" if date_signature else "Signe"
        couleur_texte = (255, 255, 255)
    else:
        pdf.rounded_card(10, y0, 190, h, r=3, fill=(255, 244, 230), border=(240, 200, 140))
        texte = "En attente de signature"
        couleur_texte = (150, 100, 20)
    pdf.set_xy(16, y0 + 4.5)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*couleur_texte)
    pdf.cell(0, 6, _txt(texte))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)


def _bloc_etapes_mandat(pdf: PDFMandat, titre: str, etapes: list[str]):
    hauteur_ligne = 6
    hauteur_totale = 10 + len(etapes) * hauteur_ligne
    y0 = pdf.get_y()
    if y0 > 297 - 24 - hauteur_totale:
        pdf.add_page()
        y0 = pdf.get_y()

    pdf.rounded_card(10, y0, 190, hauteur_totale, r=3, fill=COULEUR_FOND_CARTE, border=COULEUR_BORDURE)
    pdf.set_xy(16, y0 + 3.5)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*pdf.couleur_primaire)
    pdf.cell(0, 6, _txt(titre), ln=True)

    for i, etape in enumerate(etapes):
        y = y0 + 10 + i * hauteur_ligne
        pdf.pill(16, y, str(i + 1), fill=pdf.couleur_accent, text_color=(255, 255, 255), h=5, w=5)
        pdf.set_xy(23, y - 0.3)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*COULEUR_TEXTE)
        pdf.cell(0, 5.5, _txt(etape))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + hauteur_totale + 6)


def _champ_signature_mandat(pdf: PDFMandat):
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.cell(95, 6, _txt("Fait a ____________, le ____________"))
    pdf.cell(95, 6, _txt("Signature du client"), ln=True)
    pdf.ln(20)
    pdf.set_draw_color(*COULEUR_BORDURE)
    pdf.line(115, pdf.get_y(), 195, pdf.get_y())
    pdf.set_text_color(0, 0, 0)


# ------------------------------------------------------------------------------
#  Champs requis par type de démarche — utilisé par
#  demarches_engine.creer_demarche() pour initialiser `donnees_requises`, et
#  par demarches_engine.champs_manquants() pour bloquer la génération tant
#  qu'un champ requis n'est pas renseigné.
#
#  ⚠️ `pdl`/`pce` sont individuellement facultatifs (électricité seule, gaz
#  seul, ou les deux) — ce schéma plat ne peut pas exprimer "au moins un des
#  deux" ; à affiner si un besoin réel se présente.
# ------------------------------------------------------------------------------
# Socle commun aux 3 trames d'audit secteur ci-dessous (S1/S5/S6 de
# docs/QUESTIONS_PAR_SECTEUR.md) — factorise pour eviter de le repeter 3 fois
# a l'identique.
_SOCLE_COMMUN: dict[str, dict] = {
    "code_postal_ville": {"label": "Code postal et ville", "requis": True},
    "objectif_principal": {
        "label": "Quel est votre objectif principal ?", "requis": True, "type": "choix",
        "options": [
            {"valeur": "economiser", "label": "Economiser"},
            {"valeur": "simplifier", "label": "Simplifier"},
            {"valeur": "ameliorer_qualite", "label": "Ameliorer la qualite"},
            {"valeur": "regrouper", "label": "Regrouper mes contrats"},
        ],
    },
    "budget_mensuel_actuel": {
        "label": "Budget total actuel toutes depenses recurrentes (euros/mois)", "requis": False,
    },
}
_ENGAGEMENT_ACTUEL = {"label": "Etes-vous sous engagement ? Jusqu'a quand ?", "requis": False}


CHAMPS_REQUIS_PAR_TEMPLATE: dict[str, dict[str, dict]] = {
    "mandat": {},
    "resiliation": {
        "numero_contrat": {"label": "Numero de contrat / client chez le fournisseur actuel", "requis": True},
        "date_effet_souhaitee": {"label": "Date d'effet souhaitee", "requis": False},
    },
    "portabilite": {
        "conserver_numero": {
            "label": "Souhaitez-vous conserver votre numero de telephone actuel ?",
            "requis": True,
            "type": "choix",
            "options": [
                {"valeur": "oui", "label": "Oui, je garde mon numero"},
                {"valeur": "non", "label": "Non, nouveau numero"},
            ],
        },
        # Requis uniquement si le prospect a choisi de conserver son numero
        # (voir demarches_engine.champs_manquants, qui evalue `requis_si`) —
        # sans portabilite demandee, ni le RIO ni la ligne a porter n'ont de sens.
        "rio": {
            "label": "RIO (releve d'identite operateur)",
            "requis": True,
            "requis_si": {"champ": "conserver_numero", "egal": "oui"},
            "aide": "Pour obtenir votre RIO, appelez gratuitement le 3179 depuis le telephone dont vous "
                    "souhaitez porter le numero.",
        },
        "numero_ligne": {
            "label": "Numero de ligne a porter",
            "requis": True,
            "requis_si": {"champ": "conserver_numero", "egal": "oui"},
        },
        "type_sim": {
            "label": "Souhaitez-vous une eSIM ou une carte SIM ?",
            "requis": True,
            "type": "choix",
            "options": [
                {"valeur": "esim", "label": "eSIM"},
                {"valeur": "carte_sim", "label": "Carte SIM"},
            ],
        },
    },
    "souscription": {
        "adresse_installation": {"label": "Adresse d'installation", "requis": True},
    },
    "changement_fournisseur": {
        "pdl": {"label": "PDL (point de livraison electricite)", "requis": False},
        "pce": {"label": "PCE (point de comptage/estimation gaz)", "requis": False},
        "rib": {"label": "IBAN pour prelevement", "requis": True},
    },
    # ------------------------------------------------------------------------
    #  Trame adaptative par secteur (voir docs/QUESTIONS_PAR_SECTEUR.md),
    #  posee au client avant l'upload de documents — une demarche par univers
    #  (voir demarches_engine.MAPPING_UNIVERS_DEMARCHES et .audit_secteur_complet,
    #  qui bloque l'upload tant qu'elle n'est pas completee). Le socle S1/S5/S6
    #  de la doc est duplique dans chaque secteur faute de stockage partage au
    #  niveau client aujourd'hui. Les questions a seuil numerique (conso data,
    #  kVA...) sont modelisees en choix pre-decoupes en tranches pour rester
    #  exprimables avec le seul comparateur `egal` de `requis_si` (pas de
    #  comparateur numerique dans demarches_engine.champs_manquants).
    # ------------------------------------------------------------------------
    "audit_mobile": {
        **_SOCLE_COMMUN,
        "nb_lignes_mobiles": {
            "label": "Combien de lignes mobiles a optimiser ?", "requis": True, "type": "choix",
            "options": [{"valeur": "1", "label": "1 seule"}, {"valeur": "2+", "label": "2 ou plus"}],
        },
        "operateur_prix_actuel": {
            "label": "Operateur actuel et prix mensuel de la ligne", "requis": True,
        },
        "conso_data": {
            "label": "Consommation data moyenne des 3 derniers mois",
            "requis": True, "type": "choix",
            "aide": "A lire sur votre facture ou l'appli de votre operateur, ligne consommation data.",
            "options": [
                {"valeur": "<5", "label": "Moins de 5 Go"},
                {"valeur": "5-30", "label": "Entre 5 et 30 Go"},
                {"valeur": "30-100", "label": "Entre 30 et 100 Go"},
                {"valeur": ">100", "label": "Plus de 100 Go"},
            ],
        },
        "partage_connexion": {
            "label": "Partagez-vous votre connexion mobile pour votre domicile ?",
            "requis": True, "type": "choix",
            "requis_si": {"champ": "conso_data", "egal": ">100"},
            "options": [{"valeur": "oui", "label": "Oui"}, {"valeur": "non", "label": "Non"}],
        },
        "roaming": {
            "label": "Voyagez-vous a l'etranger avec ce telephone ?",
            "requis": True, "type": "choix",
            "options": [
                {"valeur": "jamais", "label": "Jamais"},
                {"valeur": "ue", "label": "En Europe, occasionnellement ou souvent"},
                {"valeur": "hors_ue", "label": "Hors Europe, occasionnellement ou souvent"},
            ],
        },
        "qualite_reseau": {
            "label": "Qualite du reseau a votre domicile et au travail ?",
            "requis": True, "type": "choix",
            "options": [
                {"valeur": "bonne", "label": "Bonne partout"},
                {"valeur": "moyenne", "label": "Moyenne ou mauvaise a un endroit"},
            ],
        },
        "engagement_actuel": _ENGAGEMENT_ACTUEL,
    },
    "audit_box": {
        **_SOCLE_COMMUN,
        "type_logement": {"label": "Type de logement (appartement/maison) et surface en m2", "requis": False},
        "fibre_disponible": {
            "label": "La fibre est-elle disponible a votre adresse ?",
            "requis": True, "type": "choix",
            "options": [
                {"valeur": "oui", "label": "Oui"},
                {"valeur": "non", "label": "Non, uniquement ADSL/VDSL"},
                {"valeur": "zone_4g5g", "label": "Zone 4G/5G couverte mais ADSL tres faible"},
            ],
        },
        "operateur_prix_actuel": {"label": "Operateur actuel et prix mensuel", "requis": True},
        "usage_tv": {
            "label": "Regardez-vous la TV via la box (chaines TNT et payantes) ?",
            "requis": True, "type": "choix",
            "options": [
                {"valeur": "jamais", "label": "Jamais, uniquement streaming"},
                {"valeur": "quelques_chaines", "label": "Oui, quelques chaines"},
                {"valeur": "bouquet_premium", "label": "Oui, bouquet premium (Canal+, beIN...)"},
            ],
        },
        "chaines_payantes": {
            "label": "Quels abonnements payants en plus du bouquet ?",
            "requis": True,
            "requis_si": {"champ": "usage_tv", "egal": "bouquet_premium"},
        },
        "utilisateurs_simultanes": {
            "label": "Combien de personnes en streaming simultane ? Video 4K ?",
            "requis": True, "type": "choix",
            "options": [
                {"valeur": "1-2", "label": "1 a 2 personnes, HD"},
                {"valeur": "3+", "label": "3 personnes ou plus, ou 4K"},
                {"valeur": "gaming", "label": "Console / gaming en ligne"},
            ],
        },
        "teletravail": {
            "label": "Teletravaillez-vous regulierement (visios frequentes) ?",
            "requis": True, "type": "choix",
            "options": [{"valeur": "oui", "label": "Oui"}, {"valeur": "non", "label": "Non"}],
        },
        "engagement_actuel": _ENGAGEMENT_ACTUEL,
    },
    "audit_energie": {
        **_SOCLE_COMMUN,
        "type_logement": {"label": "Type de logement (appartement/maison) et surface en m2", "requis": False},
        "statut_occupation": {
            "label": "Etes-vous proprietaire ou locataire ?", "requis": False, "type": "choix",
            "options": [
                {"valeur": "proprietaire", "label": "Proprietaire"},
                {"valeur": "locataire", "label": "Locataire"},
            ],
        },
        "chauffage_principal": {
            "label": "Chauffage principal du logement ?", "requis": True, "type": "choix",
            "options": [
                {"valeur": "electrique", "label": "Electrique (convecteurs, radiants, PAC)"},
                {"valeur": "gaz", "label": "Gaz"},
                {"valeur": "bois_fioul_pac", "label": "Bois / fioul / pompe a chaleur air-eau"},
                {"valeur": "collectif", "label": "Chauffage collectif inclus dans les charges"},
            ],
        },
        "conso_annuelle_kwh": {
            "label": "Consommation annuelle (kWh) - electricite et gaz separes",
            "requis": True,
            "aide": "A lire sur votre facture ; a defaut, votre conseiller l'estimera.",
        },
        "puissance_kva": {
            "label": "Puissance souscrite (kVA) - en haut de votre facture", "requis": True, "type": "choix",
            "options": [
                {"valeur": "3", "label": "3 kVA"}, {"valeur": "6", "label": "6 kVA"},
                {"valeur": "9", "label": "9 kVA"}, {"valeur": "12+", "label": "12 kVA ou plus"},
            ],
        },
        # Doc source : declenche aussi pour 12+ kVA — un seul seuil exprimable
        # avec `requis_si` (egal uniquement), on retient le plus frequent (9).
        "gros_equipement_electrique": {
            "label": "Avez-vous une clim, une piscine, un vehicule electrique ou des plaques induction puissantes ?",
            "requis": True, "type": "choix",
            "requis_si": {"champ": "puissance_kva", "egal": "9"},
            "options": [{"valeur": "oui", "label": "Oui"}, {"valeur": "non", "label": "Non"}],
        },
        "option_tarifaire": {
            "label": "Option tarifaire actuelle ?", "requis": True, "type": "choix",
            "options": [
                {"valeur": "base", "label": "Base"},
                {"valeur": "hphc", "label": "Heures Pleines-Creuses"},
                {"valeur": "tempo", "label": "Tempo"},
            ],
        },
        "equipements_pilotables_nuit": {
            "label": "Avez-vous de gros equipements pilotables la nuit (chauffe-eau, VE, chauffage programmable) ?",
            "requis": True, "type": "choix",
            "options": [{"valeur": "oui", "label": "Oui"}, {"valeur": "non", "label": "Non"}],
        },
        "fournisseur_prix_actuel": {
            "label": "Fournisseur actuel, prix du kWh et de l'abonnement", "requis": True,
        },
        "engagement_actuel": {
            "label": "Prix fixe ou indexe ? Duree d'engagement restante ?", "requis": False,
        },
    },
}


def _identite_client(client: Client) -> str:
    nom_complet = f"{client.prenom or ''} {client.nom or ''}".strip() or "Client"
    lignes = [nom_complet]
    if client.adresse:
        lignes.append(client.adresse)
    loc = " ".join(p for p in [client.code_postal, client.ville] if p)
    if loc:
        lignes.append(loc)
    if client.email:
        lignes.append(f"Email : {client.email}")
    if client.telephone:
        lignes.append(f"Tel : {client.telephone}")
    return "\n".join(lignes)


def generer_pdf_mandat_representation(dossier: Dossier, client: Client, branding: dict | None = None) -> bytes:
    """Génère le mandat de représentation avec l'habillage « vendeur » (voir
    PDFMandat) — décrit ce que le mandat couvre et ce qui se passe une fois
    signé, sur le même principe que la restitution remise après le
    diagnostic (voir restitution_pdf_engine.generer_pdf_restitution_dossier)."""
    nom_societe, couleur_primaire, couleur_accent, logo_bytes = _branding_defaut(branding)
    pdf = PDFMandat("Mandat de representation", nom_societe, couleur_primaire, couleur_accent, logo_bytes)
    pdf.set_auto_page_break(auto=True, margin=24)
    pdf.add_page()

    reference = client.ref or f"MND-{dossier.id:06d}"
    _bloc_identite_mandat(pdf, client, reference, "Mandat de representation")
    _banniere_statut_signature(pdf, signe=False, date_signature=None)

    pdf.paragraphe(
        f"Je soussigne(e) {(client.prenom or '')} {(client.nom or '')}, donne mandat a {nom_societe} pour me "
        f"representer aupres des operateurs et fournisseurs concernes ({dossier.univers}) afin d'effectuer, "
        "en mon nom et pour mon compte, les demarches necessaires a la resiliation de mes contrats en cours "
        "et/ou a la souscription des nouvelles offres retenues"
        + (f" aupres de {dossier.fournisseur_cible}" if dossier.fournisseur_cible else "")
        + ".",
    )
    pdf.paragraphe(
        "Ce mandat couvre notamment : la demande de resiliation, la demande de portabilite (le cas echeant), "
        "et toute demarche administrative strictement necessaire a l'execution de ce changement d'offre. "
        "Il est valable jusqu'a l'aboutissement de la ou des demarches concernees, ou revocation ecrite de ma part.",
    )

    _bloc_etapes_mandat(pdf, "Ce que ce mandat nous permet de faire pour vous", [
        "Nous demandons la resiliation de votre ou vos contrats actuels.",
        "Nous portons votre numero si besoin, sans coupure de service.",
        "Nous soumettons votre dossier au(x) nouveau(x) fournisseur(s) retenu(s).",
        "Vous etes tenu informe a chaque etape jusqu'a l'activation effective.",
    ])

    _champ_signature_mandat(pdf)
    return bytes(pdf.output())


def generer_pdf_resiliation_box(dossier: Dossier, client: Client, donnees: dict) -> bytes:
    pdf = PDFDemarche("Demande de resiliation")
    pdf.add_page()
    pdf.paragraphe(_identite_client(client), taille=10)
    pdf.paragraphe(
        "Objet : demande de resiliation de mon contrat Box internet, dans le cadre du mandat de representation "
        "confie a IA Conseil.",
        gras=True,
    )
    numero_contrat = donnees.get("numero_contrat") or "(a completer)"
    pdf.paragraphe(f"Numero de contrat / reference client : {numero_contrat}")
    date_effet = donnees.get("date_effet_souhaitee")
    if date_effet:
        pdf.paragraphe(f"Date d'effet souhaitee : {date_effet}")
    pdf.paragraphe(
        "Je vous demande de bien vouloir prendre en compte la resiliation de ce contrat, et vous remercie de "
        "m'indiquer les modalites de restitution du materiel eventuellement du et le solde de tout compte.",
    )
    pdf.champ_signature()
    return bytes(pdf.output())


def generer_pdf_demande_portabilite_mobile(dossier: Dossier, client: Client, donnees: dict) -> bytes:
    pdf = PDFDemarche("Demande de portabilite mobile")
    pdf.add_page()
    pdf.paragraphe(_identite_client(client), taille=10)
    conserve_numero = donnees.get("conserver_numero") == "oui"
    if conserve_numero:
        pdf.paragraphe(
            "Objet : demande de conservation de mon numero de mobile (portabilite), dans le cadre du mandat de "
            "representation confie a IA Conseil.",
            gras=True,
        )
        pdf.paragraphe(f"Numero de ligne a porter : {donnees.get('numero_ligne') or '(a completer)'}")
        pdf.paragraphe(f"RIO : {donnees.get('rio') or '(a completer)'}")
        pdf.paragraphe(
            "Je souhaite conserver mon numero de telephone actuel lors du changement d'operateur. Le nouvel "
            "operateur se charge de la resiliation de la ligne d'origine dans le cadre de cette portabilite.",
        )
    else:
        pdf.paragraphe(
            "Objet : souscription d'une nouvelle ligne mobile avec un nouveau numero, dans le cadre du mandat "
            "de representation confie a IA Conseil.",
            gras=True,
        )
    type_sim = donnees.get("type_sim")
    if type_sim:
        pdf.paragraphe(f"Type de carte SIM souhaite : {'eSIM' if type_sim == 'esim' else 'Carte SIM'}")
    pdf.champ_signature()
    return bytes(pdf.output())


def generer_pdf_changement_fournisseur_energie(dossier: Dossier, client: Client, donnees: dict) -> bytes:
    pdf = PDFDemarche("Demande de changement de fournisseur")
    pdf.add_page()
    pdf.paragraphe(_identite_client(client), taille=10)
    pdf.paragraphe(
        "Objet : demande de changement de fournisseur d'energie, dans le cadre du mandat de representation "
        "confie a IA Conseil. Le nouveau fournisseur se charge de la resiliation de mon contrat en cours.",
        gras=True,
    )
    if donnees.get("pdl"):
        pdf.paragraphe(f"PDL (electricite) : {donnees['pdl']}")
    if donnees.get("pce"):
        pdf.paragraphe(f"PCE (gaz) : {donnees['pce']}")
    pdf.paragraphe(f"IBAN pour prelevement : {donnees.get('rib') or '(a completer)'}")
    pdf.champ_signature()
    return bytes(pdf.output())


def generer_pdf_souscription(dossier: Dossier, client: Client, donnees: dict) -> bytes:
    pdf = PDFDemarche("Demande de souscription")
    pdf.add_page()
    pdf.paragraphe(_identite_client(client), taille=10)
    pdf.paragraphe(
        f"Objet : demande de souscription a une nouvelle offre ({dossier.univers}"
        + (f", {dossier.fournisseur_cible}" if dossier.fournisseur_cible else "")
        + "), dans le cadre du mandat de representation confie a IA Conseil.",
        gras=True,
    )
    if donnees.get("adresse_installation"):
        pdf.paragraphe(f"Adresse d'installation : {donnees['adresse_installation']}")
    pdf.champ_signature()
    return bytes(pdf.output())


def generer_pdf_mandat_honoraires(
    dossier: Dossier, client: Client, mandat: MandatHonoraires, branding: dict | None = None
) -> bytes:
    """Génère le mandat d'honoraires avec l'habillage « vendeur » (voir
    PDFMandat), y compris son statut de signature réel (`mandat.statut`) —
    ce PDF est régénéré à la volée à chaque consultation (GET .../pdf), avant
    et après signature, contrairement au mandat de représentation dont le
    PDF est figé au moment de sa génération (voir generer_pdf_mandat_representation)."""
    nom_societe, couleur_primaire, couleur_accent, logo_bytes = _branding_defaut(branding)
    pdf = PDFMandat("Mandat d'honoraires", nom_societe, couleur_primaire, couleur_accent, logo_bytes)
    pdf.set_auto_page_break(auto=True, margin=24)
    pdf.add_page()

    reference = client.ref or f"HON-{dossier.id:06d}"
    signe = mandat.statut == "signe"
    _bloc_identite_mandat(pdf, client, reference, "Mandat d'honoraires")
    _banniere_statut_signature(pdf, signe=signe, date_signature=mandat.date_signature)

    y0 = pdf.get_y()
    h = 22
    pdf.rounded_card(10, y0, 190, h, r=3, fill=couleur_accent)
    pdf.set_xy(16, y0 + 4)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, _txt(f"Honoraires : {mandat.montant:.2f} EUR"), ln=True)
    pdf.set_xy(16, y0 + 13)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, _txt(f"Taux applicable : {mandat.taux:.2f} %"))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)

    pdf.paragraphe(
        f"Je soussigne(e) {(client.prenom or '')} {(client.nom or '')}, confie a {nom_societe} un mandat "
        f"d'honoraires pour les prestations de conseil et de mise en concurrence realisees dans le cadre "
        f"du dossier {dossier.univers}"
        + (f" aupres de {dossier.fournisseur_cible}" if dossier.fournisseur_cible else "")
        + ".",
    )
    pdf.paragraphe(
        "Ce mandat d'honoraires est distinct du mandat de representation aupres des operateurs et "
        "fournisseurs, et couvre uniquement la remuneration du cabinet pour les prestations rendues.",
    )

    _bloc_etapes_mandat(pdf, "Comment se deroule le paiement de ces honoraires", [
        "Vous signez ce mandat une fois l'offre validee avec votre conseiller.",
        "Nous finalisons la souscription et la resiliation de l'ancien contrat.",
        "Les honoraires sont dus une fois votre nouvelle offre activee.",
        "Vous recevez une facture detaillee correspondant a ce montant.",
    ])

    if not signe:
        _champ_signature_mandat(pdf)
    return bytes(pdf.output())


GENERATEURS_PAR_TYPE: dict[str, Callable[[Dossier, Client, dict], bytes]] = {
    "mandat": lambda dossier, client, _donnees: generer_pdf_mandat_representation(dossier, client),
    "resiliation": generer_pdf_resiliation_box,
    "portabilite": generer_pdf_demande_portabilite_mobile,
    "souscription": generer_pdf_souscription,
    "changement_fournisseur": generer_pdf_changement_fournisseur_energie,
}
