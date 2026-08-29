# ==============================================================================
#  RESTITUTION PDF ENGINE — PDF de vente remis au client par le conseiller :
#  bandeau de synthèse chiffrée + une carte détaillée par offre comparée
#  (avant/après barré, pastille de réduction, encart économie) + habillage
#  vendeur configurable (logo réel, couleurs, nom société — voir Parametre,
#  backend/routers/parametres.py). Style repris de src/pdf_engine.py::PDFPro
#  (fpdf2, cartes empilées plus détaillées qu'un tableau compact) — indépendant
#  de src/pdf_engine.py et de backend/services/document_engine.py (PDF légaux
#  de démarche), sur le même principe de découplage backend/src déjà en place.
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


def _bande_kpi(pdf: PDFRestitution, nb_offres: int, economie_mensuelle: float, economie_annuelle: float):
    """Bandeau de synthèse chiffrée en tête de l'étude (style
    src/pdf_engine.py::generer_pdf_restitution) — donne le total d'un coup
    d'oeil avant le détail offre par offre ci-dessous."""
    y0 = pdf.get_y()
    h = 20
    pdf.rounded_card(10, y0, 190, h, r=3, fill=(255, 255, 255), border=COULEUR_BORDURE)
    col_w = 190 / 3
    kpis = [
        (str(nb_offres), "offre(s) comparee(s)", pdf.couleur_primaire),
        (f"{economie_mensuelle:.2f} EUR", "economie estimee / mois", pdf.couleur_accent),
        (f"{economie_annuelle:.2f} EUR", "economie estimee / an", pdf.couleur_accent),
    ]
    for i, (valeur, label, couleur) in enumerate(kpis):
        x = 10 + i * col_w
        if i > 0:
            pdf.set_draw_color(*COULEUR_BORDURE)
            pdf.set_line_width(0.2)
            pdf.line(x, y0 + 4, x, y0 + h - 4)
        pdf.set_xy(x, y0 + 3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*couleur)
        pdf.cell(col_w, 7, _txt(valeur), align="C")
        pdf.set_xy(x, y0 + 11.5)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(col_w, 5, _txt(label), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)


def _carte_offre_comparee(pdf: PDFRestitution, offre: dict, cout_actuel_mensuel: float | None, recommandee: bool):
    """Une carte détaillée par offre comparée (au lieu d'une colonne compacte
    de tableau) — reprend le style avant/après barré + pastille d'économie de
    src/pdf_engine.py::_carte_offre, plus riche que la ligne de tableau."""
    h = 32
    y0 = pdf.get_y()
    if y0 > 297 - 24 - h:
        pdf.add_page()
        y0 = pdf.get_y()

    bordure = pdf.couleur_accent if recommandee else COULEUR_BORDURE
    fond = COULEUR_ACCENT_CLAIR if recommandee else COULEUR_FOND_CARTE
    pdf.rounded_card(10, y0, 190, h, r=3, fill=fond, border=bordure, line_width=0.6 if recommandee else 0.3)

    titre_y = y0 + 4
    if recommandee:
        pdf.pill(13, y0 + 3, "RECOMMANDEE", fill=pdf.couleur_accent, text_color=(255, 255, 255), h=5, font=("Helvetica", "B", 7))
        titre_y = y0 + 10

    pdf.set_xy(13, titre_y)
    pdf.set_font("Helvetica", "B", 11.5)
    pdf.set_text_color(*COULEUR_TEXTE)
    pdf.cell(120, 6, _txt(offre.get("nom") or "Offre"))

    pdf.set_xy(13, titre_y + 6.5)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.cell(120, 5, _txt(offre.get("fournisseur") or "-"))
    pdf.set_text_color(0, 0, 0)

    comparable = offre.get("comparable", True)
    prix_offre = offre.get("prix_mensuel")
    economie_mensuelle = offre.get("economie_mensuelle", 0) or 0

    if comparable and cout_actuel_mensuel and prix_offre is not None:
        yy = titre_y + 13.5
        avant_txt = f"{cout_actuel_mensuel:.2f} EUR/mois"
        pdf.set_xy(13, yy)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(13, 5, _txt("Avant :"))
        pdf.set_xy(27, yy)
        pdf.set_font("Helvetica", "", 9)
        largeur_avant = pdf.get_string_width(_txt(avant_txt))
        pdf.cell(largeur_avant, 5, _txt(avant_txt))
        pdf.set_draw_color(*COULEUR_GRIS)
        pdf.set_line_width(0.25)
        pdf.line(27, yy + 2.6, 27 + largeur_avant, yy + 2.6)

        pdf.set_xy(65, yy)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(13, 5, _txt("Apres :"))
        pdf.set_xy(78, yy - 0.7)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(*pdf.couleur_accent)
        pdf.cell(35, 6, _txt(f"{prix_offre:.2f} EUR/mois"))
        pdf.set_text_color(0, 0, 0)

        if cout_actuel_mensuel > 0 and prix_offre < cout_actuel_mensuel:
            baisse = round((cout_actuel_mensuel - prix_offre) / cout_actuel_mensuel * 100)
            pdf.pill(13, y0 + h - 6.5, f"-{baisse}% sur la facture", fill=(255, 255, 255) if recommandee else COULEUR_ACCENT_CLAIR,
                     text_color=pdf.couleur_accent, h=5, font=("Helvetica", "B", 7))
    else:
        pdf.set_xy(13, titre_y + 13.5)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(120, 5, _txt("Service complementaire, non directement comparable a l'abonnement actuel."))
        pdf.set_text_color(0, 0, 0)

    px, pw, py, ph = 140, 55, y0 + 4, h - 8
    pdf.rounded_card(px, py, pw, ph, r=2.5, fill=pdf.couleur_accent)
    pdf.set_xy(px, py + 3)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(pw, 4, _txt("Economie estimee"), align="C")
    pdf.set_xy(px, py + 8.5)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(pw, 7, _txt(f"{(economie_mensuelle * 12):.2f} EUR"), align="C")
    pdf.set_xy(px, py + 16)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(pw, 4, _txt("par an"), align="C")
    pdf.set_xy(px, py + 20)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.cell(pw, 4, _txt(f"soit {economie_mensuelle:.2f} EUR/mois"), align="C")
    pdf.set_text_color(0, 0, 0)

    pdf.set_y(y0 + h + 5)


def _bande_confiance(pdf: PDFRestitution, items: list[tuple[str, str]]):
    """Bandeau de réassurance en pied d'étude (style
    src/pdf_engine.py::_bande_confiance)."""
    y0 = pdf.get_y()
    h = 16
    if y0 > 297 - 24 - h:
        pdf.add_page()
        y0 = pdf.get_y()
    pdf.rounded_card(10, y0, 190, h, r=3, fill=COULEUR_FOND_CARTE, border=COULEUR_BORDURE)
    col_w = 190 / len(items)
    for i, (titre, sous_titre) in enumerate(items):
        x = 10 + i * col_w
        pdf.set_xy(x, y0 + 3.5)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*pdf.couleur_primaire)
        pdf.cell(col_w, 5, _txt(titre), align="C")
        pdf.set_xy(x, y0 + 9)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(col_w, 4.5, _txt(sous_titre), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)


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
    montant_annuel = comparaison.economie_annuelle_estimee or dossier.economie_annuelle_estimee or 0.0
    if offres:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*COULEUR_TEXTE)
        pdf.multi_cell(0, 5, _txt(
            "Voici le detail des offres que nous avons comparees pour votre situation "
            f"({comparaison.univers or ''} - {comparaison.categorie or ''}), avec l'offre recommandee mise en avant."))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

        _bande_kpi(pdf, len(offres), comparaison.economie_mensuelle_estimee or (montant_annuel / 12), montant_annuel)

        for offre in offres:
            recommandee = comparaison.offre_recommandee_id is not None and offre.get("offre_id") == comparaison.offre_recommandee_id
            _carte_offre_comparee(pdf, offre, comparaison.cout_actuel_mensuel, recommandee)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.multi_cell(0, 5, _txt("Aucune offre comparee n'est disponible pour ce dossier."))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    _bloc_etapes_souscription(pdf)
    _bande_confiance(pdf, [
        ("Sans engagement", "pour vous"),
        ("Demarches prises en charge", "de A a Z"),
        ("Donnees confidentielles", "traitees en toute securite"),
    ])

    _banniere_economie(pdf, montant_annuel)

    return bytes(pdf.output())
