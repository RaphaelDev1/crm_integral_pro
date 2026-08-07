# ==============================================================================
#  RESTITUTION PDF ENGINE — PDF de vente remis au client par le conseiller :
#  tableau comparatif multi-offres/multi-fournisseurs côte à côte + habillage
#  vendeur configurable (logo réel, couleurs, nom société — voir Parametre,
#  backend/routers/parametres.py). Style de cartes/pastilles réutilisé de
#  src/pdf_engine.py::PDFPro (fpdf2), mais layout entièrement redessiné en
#  tableau (au lieu des cartes empilées) — indépendant de src/pdf_engine.py et
#  de backend/services/document_engine.py (PDF légaux de démarche), sur le
#  même principe de découplage backend/src déjà en place.
# ==============================================================================
from __future__ import annotations

import io
from datetime import datetime

from fpdf import FPDF

from backend.models.client import Client
from backend.models.comparaison_offre import ComparaisonOffre
from backend.models.dossier import Dossier

COULEUR_PRIMAIRE_DEFAUT = (16, 42, 82)
COULEUR_ACCENT_DEFAUT = (0, 150, 90)
COULEUR_GRIS = (110, 110, 110)
COULEUR_TEXTE = (35, 38, 45)
COULEUR_BORDURE = (222, 227, 235)
COULEUR_FOND_CARTE = (247, 249, 252)
COULEUR_ACCENT_CLAIR = (224, 244, 235)


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


class PDFRestitution(FPDF):
    def __init__(self, nom_societe: str, couleur_primaire: tuple, couleur_accent: tuple, logo_bytes: bytes | None):
        super().__init__()
        self.nom_societe = nom_societe
        self.couleur_primaire = couleur_primaire
        self.couleur_accent = couleur_accent
        self.logo_bytes = logo_bytes

    # ---- en-tête / pied de page --------------------------------------------
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
        self.cell(0, 6, _txt("Etude comparative personnalisee"))

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
            f"{self.nom_societe} - Document genere le {datetime.now().strftime('%d/%m/%Y')}. "
            "Estimations indicatives, sans valeur contractuelle."), align="C")
        self.set_text_color(0, 0, 0)

    # ---- briques graphiques réutilisables (style src/pdf_engine.py::PDFPro) --
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


def _bloc_identite(pdf: PDFRestitution, client: Client, reference: str):
    y0 = pdf.get_y()
    h = 26
    pdf.rounded_card(10, y0, 190, h, r=3, fill=COULEUR_FOND_CARTE, border=COULEUR_BORDURE)
    nom_complet = f"{client.prenom or ''} {client.nom or ''}".strip() or "Client"
    pdf.set_xy(16, y0 + 4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*pdf.couleur_primaire)
    pdf.cell(0, 7, _txt(f"Audit facture - {nom_complet}"), ln=True)

    pdf.set_xy(16, y0 + 12)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.cell(0, 5.5, _txt(f"Reference client : {reference}"))

    contacts = [c for c in (client.telephone, client.email) if c]
    if contacts:
        pdf.set_xy(16, y0 + 18)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(0, 5.5, _txt("   -   ".join(contacts)))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)


def _bloc_conseiller(pdf: PDFRestitution, conseiller_nom: str | None, conseiller_telephone: str | None):
    if not conseiller_nom and not conseiller_telephone:
        return
    y0 = pdf.get_y()
    h = 14
    pdf.rounded_card(10, y0, 190, h, r=3, fill=COULEUR_ACCENT_CLAIR, border=COULEUR_BORDURE)
    pdf.set_xy(16, y0 + 3.5)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*pdf.couleur_primaire)
    contact = " - ".join(c for c in (conseiller_nom, conseiller_telephone) if c)
    pdf.cell(0, 5, _txt(f"Votre conseiller : {contact}"), ln=True)
    pdf.set_xy(16, y0 + 8.5)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.cell(0, 4.5, _txt("Une question ? Contactez-le directement, il gere votre dossier de A a Z."))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)


def _bloc_etapes_souscription(pdf: PDFRestitution):
    etapes = [
        "Vous validez l'offre retenue avec votre conseiller.",
        "Nous preparons votre dossier et le mandat de resiliation/souscription.",
        "Vous signez electroniquement en quelques minutes, ou sur place.",
        "Nous gerons la resiliation de l'ancien contrat et l'activation du nouveau, sans que vous ayez a rappeler qui que ce soit.",
        "Vous etes tenu informe a chaque etape jusqu'a l'activation effective.",
    ]
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
    pdf.cell(0, 6, _txt("Une souscription rapide et 100% geree pour vous"), ln=True)

    for i, etape in enumerate(etapes):
        y = y0 + 10 + i * hauteur_ligne
        pdf.pill(16, y, str(i + 1), fill=pdf.couleur_accent, text_color=(255, 255, 255), h=5, w=5)
        pdf.set_xy(23, y - 0.3)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*COULEUR_TEXTE)
        pdf.cell(0, 5.5, _txt(etape))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + hauteur_totale + 6)


def _banniere_economie(pdf: PDFRestitution, montant_annuel: float, hauteur: float = 22):
    y = pdf.get_y()
    pdf.rounded_card(10, y, 190, hauteur, r=3, fill=pdf.couleur_accent)
    pdf.set_fill_color(255, 255, 255)
    pdf.circle(24, y + hauteur / 2, 6, "F")
    pdf.set_xy(18, y + hauteur / 2 - 4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*pdf.couleur_accent)
    pdf.cell(12, 8, "EUR", align="C")
    pdf.set_xy(36, y + 3)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(160, 8, _txt(f"ECONOMIE ESTIMEE : {round(montant_annuel, 2)} EUR / AN"))
    pdf.set_xy(36, y + hauteur - 8)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(160, 5, _txt(f"soit {round(montant_annuel / 12, 2)} EUR / mois"))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y + hauteur + 6)


def _tableau_comparatif(pdf: PDFRestitution, offres: list[dict], offre_recommandee_id: int | None):
    """Tableau comparatif côte à côte — une colonne par offre comparée (au
    lieu des cartes empilées de src/pdf_engine.py::_carte_offre), avec la
    colonne recommandée mise en évidence visuellement."""
    marge_x = 10
    largeur_totale = 190
    nb_offres = len(offres)
    largeur_col = largeur_totale / nb_offres
    def _economie(o: dict, annuelle: bool) -> str:
        if not o.get("comparable", True):
            return "-"
        montant = (o.get("economie_mensuelle", 0) or 0) * (12 if annuelle else 1)
        return f"{montant:.2f} EUR"

    lignes = [
        ("Fournisseur", lambda o: o.get("fournisseur") or "-"),
        ("Offre", lambda o: (o.get("nom") or "-")[:22]),
        ("Economie / mois", lambda o: _economie(o, annuelle=False)),
        ("Economie / an", lambda o: _economie(o, annuelle=True)),
    ]
    hauteur_ligne = 8
    hauteur_entete = 10
    hauteur_totale = hauteur_entete + len(lignes) * hauteur_ligne

    y0 = pdf.get_y()
    if y0 > 297 - 24 - hauteur_totale:
        pdf.add_page()
        y0 = pdf.get_y()

    # En-tête (nom de l'offre recommandée mis en avant)
    for i, offre in enumerate(offres):
        x = marge_x + i * largeur_col
        recommandee = offre_recommandee_id is not None and offre.get("offre_id") == offre_recommandee_id
        pdf.rounded_card(x + 1, y0, largeur_col - 2, hauteur_entete,
                          r=2, fill=pdf.couleur_accent if recommandee else pdf.couleur_primaire)
        pdf.set_xy(x + 1, y0 + 1.5)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(largeur_col - 2, 4, _txt(f"Offre {i + 1}"), align="C")
        if recommandee:
            pdf.set_xy(x + 1, y0 + 5.5)
            pdf.set_font("Helvetica", "", 6.5)
            pdf.cell(largeur_col - 2, 3.5, _txt("RECOMMANDEE"), align="C")
        pdf.set_text_color(0, 0, 0)

    # Corps du tableau, ligne par ligne
    for j, (label, extracteur) in enumerate(lignes):
        y = y0 + hauteur_entete + j * hauteur_ligne
        for i, offre in enumerate(offres):
            x = marge_x + i * largeur_col
            recommandee = offre_recommandee_id is not None and offre.get("offre_id") == offre_recommandee_id
            fill = COULEUR_ACCENT_CLAIR if recommandee else (COULEUR_FOND_CARTE if j % 2 == 0 else (255, 255, 255))
            pdf.set_fill_color(*fill)
            pdf.set_draw_color(*COULEUR_BORDURE)
            pdf.set_line_width(0.2)
            pdf.rect(x + 1, y, largeur_col - 2, hauteur_ligne, "DF")
            pdf.set_xy(x + 1, y + 1.3)
            pdf.set_font("Helvetica", "B" if label.startswith("Economie") else "", 8)
            pdf.set_text_color(*(pdf.couleur_accent if label.startswith("Economie") else COULEUR_TEXTE))
            pdf.cell(largeur_col - 2, 5.4, _txt(extracteur(offre)), align="C")
            pdf.set_text_color(0, 0, 0)

    pdf.set_y(y0 + hauteur_totale + 4)

    # Légende textuelle des lignes (le tableau ci-dessus n'a pas de colonne
    # d'étiquettes pour rester compact sur mobile/impression — les libellés
    # sont donnés ici une seule fois).
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.multi_cell(0, 4, _txt(
        "Lignes du tableau, de haut en bas : Fournisseur, Offre, Economie mensuelle, Economie annuelle. "
        "Les offres complementaires ('-') portent sur un autre type de service et ne sont pas comparables "
        "financierement a votre abonnement actuel."))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def generer_pdf_restitution_dossier(
    dossier: Dossier,
    client: Client,
    comparaison: ComparaisonOffre,
    branding: dict,
) -> bytes:
    """Génère le PDF de restitution remis au client : tableau comparatif des
    offres de `comparaison.offres_comparees` (instantané figé au moment du
    calcul, voir backend/models/comparaison_offre.py), habillé aux couleurs et
    au logo du cabinet (branding lu depuis Parametre par l'appelant, voir
    backend/routers/dossiers.py::generer_pdf_restitution_dossier)."""
    nom_societe = branding.get("nom_societe") or "IA CONSEIL"
    couleur_primaire = _hex_vers_rgb(branding.get("couleur_primaire_hex"), COULEUR_PRIMAIRE_DEFAUT)
    couleur_accent = _hex_vers_rgb(branding.get("couleur_accent_hex"), COULEUR_ACCENT_DEFAUT)
    logo_bytes = branding.get("logo_bytes")

    pdf = PDFRestitution(nom_societe, couleur_primaire, couleur_accent, logo_bytes)
    pdf.set_auto_page_break(auto=True, margin=24)
    pdf.add_page()

    reference = client.ref or f"DOS-{dossier.id:06d}"
    _bloc_identite(pdf, client, reference)
    _bloc_conseiller(pdf, branding.get("conseiller_nom"), branding.get("conseiller_telephone"))

    offres = comparaison.offres_comparees or []
    if offres:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COULEUR_TEXTE)
        pdf.multi_cell(0, 5, _txt(
            "Voici, cote a cote, les offres que nous avons comparees pour votre situation "
            f"({comparaison.univers or ''} - {comparaison.categorie or ''}), avec l'offre recommandee mise en avant."))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)
        _tableau_comparatif(pdf, offres, comparaison.offre_recommandee_id)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.multi_cell(0, 5, _txt("Aucune offre comparee n'est disponible pour ce dossier."))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    _bloc_etapes_souscription(pdf)

    montant_annuel = comparaison.economie_annuelle_estimee or dossier.economie_annuelle_estimee or 0.0
    _banniere_economie(pdf, montant_annuel)

    return bytes(pdf.output())
