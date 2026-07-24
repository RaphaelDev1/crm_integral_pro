# ==============================================================================
#  ANALYSE PDF (FACTURE + SPEEDTEST) + GÉNÉRATION PDF DE RESTITUTION
# ==============================================================================
import base64
import json
import re
from datetime import datetime

from PyPDF2 import PdfReader

try:
    from fpdf import FPDF
    FPDF_OK = True
except Exception:
    FPDF_OK = False

try:
    import anthropic
    ANTHROPIC_OK = True
except Exception:
    ANTHROPIC_OK = False


# ------------------------------------------------------------------------------
#  LECTURE / ANALYSE PDF ENTRANT
# ------------------------------------------------------------------------------
def lire_pdf(fichier) -> str:
    try:
        reader = PdfReader(fichier)
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return ""


def analyser_facture(texte: str) -> dict:
    res = {"operateur": "Autre / Aucun", "fournisseur": "Autre / Aucun", "prix": 0.0,
           "cp": "", "ville": "", "prenom": "", "nom": "", "tel": "", "email": "", "data_go": ""}
    if not texte:
        return res
    t_low = texte.lower()
    t_up  = texte.upper()
    lignes = [l.strip() for l in texte.split("\n") if l.strip()]

    if re.search(r"you\s*price", t_low):              res["operateur"] = "YouPrice (Réseau Orange)"
    elif re.search(r"orange|sosh", t_low):             res["operateur"] = "Orange"
    elif re.search(r"sfr|red\s+by|red\s*sfr", t_low): res["operateur"] = "SFR"
    elif re.search(r"bouygues|b&you|b\s*&\s*you", t_low): res["operateur"] = "Bouygues"
    elif re.search(r"free|proxymity", t_low):          res["operateur"] = "Free"

    if re.search(r"\bedf\b", t_low):                  res["fournisseur"] = "EDF"
    elif re.search(r"engie|gdf", t_low):               res["fournisseur"] = "Engie"
    elif re.search(r"total\s*energies|total\s*direct", t_low): res["fournisseur"] = "TotalEnergies"
    elif re.search(r"\beni\b", t_low):                 res["fournisseur"] = "Eni"
    elif re.search(r"vattenfall", t_low):              res["fournisseur"] = "Vattenfall"
    elif re.search(r"ekwateur|ekwatour", t_low):       res["fournisseur"] = "Ekwateur"

    def to_float(v): return float(v.replace(" ", "").replace(",", "."))
    mots_prix = ["abonnement","forfait","mensuel","prélèvement","prelevement",
                 "facturé","total","ttc","à payer","a payer","montant","somme"]
    for ligne in lignes:
        ll = ligne.lower()
        if any(m in ll for m in mots_prix):
            mts = re.findall(r"(\d+(?:[\s,.]\d{1,2})?)\s*(?:€|eur)", ll)
            if mts:
                res["prix"] = to_float(mts[-1])
                break
    if res["prix"] == 0.0:
        allp = re.findall(r"(\d+(?:[\s,.]\d{1,2})?)\s*(?:€|eur)", t_low)
        if allp:
            res["prix"] = to_float(allp[-1])

    blacklist = ["RUE","AVENUE","BOULEVARD","BD","CHEMIN","ROUTE","ZA","ZI","BP","CEDEX",
                 "SIRET","SIREN","RCS","APE","TSA","CS","SERVICE","CLIENT","SOCIETE","BOUTIQUE"]
    for m in re.finditer(r"\b(\d{5})\b", t_up):
        cp = m.group(1)
        for ligne in lignes:
            if cp in ligne:
                lu = ligne.upper()
                if any(w in lu for w in ["TSA","CS","RCS","SIRET","SERVICE CLIENT","SOCIETE","BOUTIQUE"]):
                    continue
                sub  = re.sub(r"\bCEDEX\b.*", "", lu.replace(cp, "")).strip()
                cand = re.sub(r"[^A-ZÀ-ÿ\s\-]", "", sub).strip()
                cand = re.sub(r"\s+", " ", cand)
                if len(cand) > 2 and not any(w in cand.split() for w in blacklist):
                    res["cp"] = cp; res["ville"] = cand; break
        if res["ville"]:
            break

    for ligne in lignes[:25]:
        if any(w in ligne.upper() for w in ["SOCIETE","SERVICE","TSA","CS","BOUTIQUE","RCS","APE"]):
            continue
        # NB : pas de \b entre le groupe civilité et \s+ — "M." se termine par un
        # caractère non-alphanumérique, donc "M." suivi d'un espace n'est jamais une
        # frontière de mot (\b) ; l'espace obligatoire (\s+) suffit à éviter les faux
        # positifs (ex. "MRS" ne matche pas "MR" faute d'espace après).
        mc = re.search(r"\b(M\.|MME|MR|MLLE|MONSIEUR|MADAME)\s+([A-ZÀ-ÿ\-]+)\s+([A-ZÀ-ÿ\-]+)", ligne.upper())
        if mc:
            res["prenom"] = mc.group(2).capitalize()
            res["nom"]    = mc.group(3).upper()
            break

    mt = re.search(r"\b(0[1-9])(?:[\s.-]?\d{2}){4}\b", texte)
    if mt: res["tel"] = mt.group(0)
    me = re.search(r"[a-zA-Z0-9-_\.]+@[a-zA-Z0-9-_\.]+\.[a-zA-Z]{2,5}", texte)
    if me: res["email"] = me.group(0)
    md = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:GO|GB)", t_up)
    if md: res["data_go"] = md.group(1).replace(",", ".")
    return res


# ------------------------------------------------------------------------------
#  ANALYSE PAR IA VISION (Claude) — photo, scan ou PDF image de facture
# ------------------------------------------------------------------------------
CHAMPS_FACTURE_VISION = [
    "operateur", "fournisseur", "prix", "cp", "ville",
    "prenom", "nom", "tel", "email", "data_go",
]

_MIME_PAR_EXTENSION = {
    "pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
}

PROMPT_FACTURE_VISION = (
    "Tu analyses une facture française (télécom ou énergie), fournie en photo, scan ou PDF. "
    "Réponds UNIQUEMENT avec un objet JSON valide (rien avant, rien après), avec exactement "
    "ces clés :\n"
    '{"operateur": "", "fournisseur": "", "prix": 0.0, "cp": "", "ville": "", '
    '"prenom": "", "nom": "", "tel": "", "email": "", "data_go": ""}\n\n'
    "Règles :\n"
    "- operateur : opérateur télécom (Orange, SFR, Bouygues, Free, YouPrice, Sosh, RED, B&You…) "
    "ou \"Autre / Aucun\" si la facture n'est pas une facture télécom\n"
    "- fournisseur : fournisseur d'énergie (EDF, Engie, TotalEnergies, Eni, Vattenfall, "
    "Ekwateur…) ou \"Autre / Aucun\" si la facture n'est pas une facture d'énergie\n"
    "- prix : montant total TTC facturé, nombre décimal avec un point (0.0 si introuvable)\n"
    "- cp / ville : code postal et ville du CLIENT (pas de l'opérateur/fournisseur)\n"
    "- prenom / nom : identité du client (pas le nom de la société émettrice)\n"
    "- tel / email : coordonnées du client si présentes sur le document\n"
    "- data_go : quantité de data mobile en Go si applicable, sinon chaîne vide\n"
    "Si une information est absente ou illisible, mets une chaîne vide (0.0 pour prix). "
    "Ne réponds rien d'autre que ce JSON."
)


def _resultat_vision_vide() -> dict:
    return {"operateur": "Autre / Aucun", "fournisseur": "Autre / Aucun", "prix": 0.0,
            "cp": "", "ville": "", "prenom": "", "nom": "", "tel": "", "email": "", "data_go": ""}


def analyser_facture_vision(contenu: bytes, nom_fichier: str, api_key: str,
                             model: str = "claude-sonnet-5"):
    """Extrait les données d'une facture (PDF, JPG ou PNG — photo, scan ou image) via
    l'API Claude Vision. Renvoie un dict au même format que `analyser_facture()`, ou
    None en cas d'échec (package/clé absents, format non supporté, erreur réseau,
    réponse non exploitable) — l'appelant doit alors retomber sur l'extraction PyPDF2."""
    if not ANTHROPIC_OK or not api_key or not contenu:
        return None
    ext  = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else ""
    mime = _MIME_PAR_EXTENSION.get(ext)
    if not mime:
        return None

    bloc_type = "document" if mime == "application/pdf" else "image"
    b64 = base64.b64encode(contenu).decode("ascii")
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": bloc_type, "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": PROMPT_FACTURE_VISION},
                ],
            }],
        )
        texte = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        texte = re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.MULTILINE).strip()
        brut = json.loads(texte)
    except Exception:
        return None

    res = _resultat_vision_vide()
    for champ in CHAMPS_FACTURE_VISION:
        val = brut.get(champ)
        if val not in (None, ""):
            res[champ] = val
    try:
        res["prix"] = float(str(res["prix"]).replace(",", ".").replace(" ", "")) if res["prix"] else 0.0
    except (TypeError, ValueError):
        res["prix"] = 0.0
    res["cp"]      = str(res["cp"])
    res["tel"]     = str(res["tel"])
    res["data_go"] = str(res["data_go"])
    return res


def analyser_speedtest_pdf(texte: str):
    down, up = 0.0, 0.0
    if not texte:
        return down, up
    t = texte.lower()
    md = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:mbit/s|mbps)?\s*(?:téléchargement|download|descendant|réception)", t)
    if not md:
        md = re.search(r"(?:téléchargement|download|descendant|réception)\s*[:\s-]*\s*(\d+(?:[\.,]\d+)?)", t)
    if md: down = float(md.group(1).replace(",", "."))
    mu = re.search(r"(\d+(?:[\.,]\d+)?)\s*(?:mbit/s|mbps)?\s*(?:transfert|upload|montant|envoi)", t)
    if not mu:
        mu = re.search(r"(?:transfert|upload|montant|envoi)\s*[:\s-]*\s*(\d+(?:[\.,]\d+)?)", t)
    if mu: up = float(mu.group(1).replace(",", "."))
    return down, up


PROMPT_SPEEDTEST_VISION = (
    "Tu analyses une capture d'écran ou un export PDF d'un test de débit internet "
    "(nPerf, Speedtest.net, Ookla…). Réponds UNIQUEMENT avec un objet JSON valide "
    '(rien avant, rien après) : {"down": 0.0, "up": 0.0}\n'
    "- down : débit descendant (téléchargement/download) en Mbit/s\n"
    "- up : débit montant (envoi/upload) en Mbit/s\n"
    "Si une valeur est illisible ou absente, mets 0.0. Ne réponds rien d'autre que ce JSON."
)


def analyser_speedtest_vision(contenu: bytes, nom_fichier: str, api_key: str,
                               model: str = "claude-sonnet-5"):
    """Extrait les débits descendant/montant d'une capture d'écran ou d'un PDF de
    test de débit via l'API Claude Vision. Renvoie (down, up) ou None en cas
    d'échec (package/clé absents, format non supporté, erreur réseau, réponse
    non exploitable) — l'appelant doit alors retomber sur `analyser_speedtest_pdf`
    (texte) ou laisser les valeurs à 0."""
    if not ANTHROPIC_OK or not api_key or not contenu:
        return None
    ext  = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else ""
    mime = _MIME_PAR_EXTENSION.get(ext)
    if not mime:
        return None

    bloc_type = "document" if mime == "application/pdf" else "image"
    b64 = base64.b64encode(contenu).decode("ascii")
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": [
                    {"type": bloc_type, "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": PROMPT_SPEEDTEST_VISION},
                ],
            }],
        )
        texte = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        texte = re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.MULTILINE).strip()
        brut = json.loads(texte)
        down = float(str(brut.get("down", 0.0)).replace(",", ".") or 0.0)
        up   = float(str(brut.get("up", 0.0)).replace(",", ".") or 0.0)
        return down, up
    except Exception:
        return None


# ------------------------------------------------------------------------------
#  GÉNÉRATION PDF DE RESTITUTION
# ------------------------------------------------------------------------------
COULEUR_PRIMAIRE       = (16, 42, 82)
COULEUR_PRIMAIRE_FONCE = (10, 28, 58)
COULEUR_PRIMAIRE_CLAIR = (223, 231, 242)
COULEUR_ACCENT         = (0, 150, 90)
COULEUR_ACCENT_CLAIR   = (224, 244, 235)
COULEUR_ROUGE_DOUX     = (196, 92, 80)
COULEUR_GRIS           = (110, 110, 110)
COULEUR_GRIS_CLAIR     = (150, 155, 163)
COULEUR_FOND_CARTE     = (247, 249, 252)
COULEUR_BORDURE        = (222, 227, 235)
COULEUR_TEXTE          = (35, 38, 45)


def _pdf_txt(txt):
    if txt is None:
        return ""
    rep = {"€":"EUR","'":"'","–":"-","—":"-","•":"-","œ":"oe",
           "🎯":"","📱":"","🏠":"","📦":"","📲":"","⚡":"","🎬":"",
           "😀":"","😐":"","😡":"","💰":"","💶":""}
    s = str(txt)
    for k, v in rep.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "ignore").decode("latin-1")


class PDFPro(FPDF):
    def __init__(self, nom_societe="IA CONSEIL"):
        super().__init__()
        self.nom_societe = nom_societe

    # ---- en-tête / pied de page ----------------------------------------
    def header(self):
        self.set_fill_color(*COULEUR_ACCENT)
        self.rect(0, 0, 210, 2.5, "F")
        self.set_fill_color(*COULEUR_PRIMAIRE)
        self.rect(0, 2.5, 210, 27.5, "F")
        self.set_fill_color(*COULEUR_PRIMAIRE_FONCE)
        self.rect(0, 30, 210, 1, "F")

        self.set_fill_color(255, 255, 255)
        self.circle(20, 16.5, 7, "F")
        initiales = "".join(w[0] for w in self.nom_societe.split()[:2]).upper() or "IA"
        self.set_xy(13, 13)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*COULEUR_PRIMAIRE)
        self.cell(14, 7, _pdf_txt(initiales), align="C")

        self.set_xy(31, 8.5)
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, _pdf_txt(self.nom_societe), ln=True)
        self.set_xy(31, 16.5)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(200, 213, 232)
        self.cell(0, 6, _pdf_txt("Conseil en optimisation de contrats telecom & energie"))

        etiquette = "ETUDE PERSONNALISEE"
        self.set_font("Helvetica", "B", 7.5)
        w = self.get_string_width(_pdf_txt(etiquette)) + 8
        self.pill(200 - w, 11, etiquette, fill=(255, 255, 255),
                  text_color=COULEUR_PRIMAIRE, w=w)

        self.set_text_color(0, 0, 0)
        self.set_y(37)

    def footer(self):
        self.set_y(-20)
        self.set_draw_color(*COULEUR_BORDURE)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_y(-17)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*COULEUR_GRIS)
        self.multi_cell(0, 4, _pdf_txt(
            f"{self.nom_societe} - Document genere le {datetime.now().strftime('%d/%m/%Y')}. "
            "Estimations indicatives basees sur les informations communiquees et les offres "
            "disponibles a ce jour. Sans valeur contractuelle."), align="C")
        self.set_text_color(0, 0, 0)
        self.set_y(-9)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*COULEUR_GRIS)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    # ---- briques graphiques réutilisables --------------------------------
    def rounded_card(self, x, y, w, h, r=3, fill=None, border=None, line_width=0.3):
        if fill is not None:
            self.set_fill_color(*fill)
        if border is not None:
            self.set_draw_color(*border)
            self.set_line_width(line_width)
        if fill is not None and border is not None:
            style = "DF"
        elif fill is not None:
            style = "F"
        else:
            style = "D"
        self.rect(x, y, w, h, style, round_corners=True, corner_radius=r)

    def pill(self, x, y, text, fill, text_color, h=6.5, font=("Helvetica", "B", 7.5), w=None):
        self.set_font(*font)
        txt = _pdf_txt(text)
        if w is None:
            w = self.get_string_width(txt) + 8
        self.set_fill_color(*fill)
        self.rect(x, y, w, h, "F", round_corners=True, corner_radius=h / 2)
        self.set_text_color(*text_color)
        self.set_xy(x, y)
        self.cell(w, h, txt, align="C")
        self.set_text_color(0, 0, 0)
        return w

    def puce_check(self, x, y, texte, w, couleur=COULEUR_ACCENT, taille=9):
        d = 4.2
        self.set_fill_color(*couleur)
        self.circle(x + d / 2, y + d / 2, d / 2, "F")
        self.set_draw_color(255, 255, 255)
        self.set_line_width(0.6)
        self.polyline([(x + 1.1, y + 2.2), (x + 1.9, y + 3.1), (x + 3.3, y + 1.1)])
        self.set_xy(x + d + 2, y - 0.6)
        self.set_font("Helvetica", "", taille)
        self.set_text_color(*COULEUR_TEXTE)
        self.cell(w - d - 2, d + 1.2, _pdf_txt(texte))
        self.set_text_color(0, 0, 0)

    def texte_barre(self, x, y, texte, taille=10, couleur=COULEUR_ROUGE_DOUX):
        self.set_font("Helvetica", "", taille)
        self.set_text_color(*couleur)
        t = _pdf_txt(texte)
        w = self.get_string_width(t)
        self.set_xy(x, y)
        self.cell(w, 5, t)
        self.set_draw_color(*couleur)
        self.set_line_width(0.4)
        self.line(x, y + 2.6, x + w, y + 2.6)
        self.set_text_color(0, 0, 0)
        return w


def _bloc_identite(pdf, titre, personne):
    """En-tête « fiche client » commune aux PDF restitution / teaser : carte
    arrondie avec le nom du destinataire et ses coordonnées."""
    y0 = pdf.get_y()
    h = 24
    pdf.rounded_card(10, y0, 190, h, r=3, fill=COULEUR_FOND_CARTE, border=COULEUR_BORDURE)
    pdf.set_xy(16, y0 + 3.5)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*COULEUR_PRIMAIRE)
    pdf.cell(0, 7, _pdf_txt(titre), ln=True)

    lignes = []
    loc = []
    if personne.get("adresse"):
        loc.append(personne.get("adresse"))
    if personne.get("ville"):
        loc.append(f"{personne.get('ville')} ({personne.get('code_postal', '')})")
    if loc:
        lignes.append(", ".join(loc))
    contacts = []
    if personne.get("telephone"):
        contacts.append(f"Tel : {personne.get('telephone')}")
    if personne.get("email"):
        contacts.append(personne.get("email"))
    if contacts:
        lignes.append("   -   ".join(contacts))

    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*COULEUR_GRIS)
    yy = y0 + 12
    for ligne in lignes[:2]:
        pdf.set_xy(16, yy)
        pdf.cell(0, 5.5, _pdf_txt(ligne))
        yy += 5.5
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)


def _banniere_totale(pdf, montant, sous_titre, hauteur=22):
    y = pdf.get_y()
    if y > 260 - hauteur:
        pdf.add_page()
        y = pdf.get_y()
    pdf.rounded_card(10, y, 190, hauteur, r=3, fill=COULEUR_ACCENT)
    pdf.set_fill_color(255, 255, 255)
    pdf.circle(24, y + hauteur / 2, 6, "F")
    pdf.set_xy(18, y + hauteur / 2 - 4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*COULEUR_ACCENT)
    pdf.cell(12, 8, "EUR", align="C")
    pdf.set_xy(36, y + 3)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(160, 8, _pdf_txt(f"ECONOMIE TOTALE ESTIMEE : {round(montant, 2)} EUR / AN"))
    pdf.set_xy(36, y + hauteur - 8)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(160, 5, _pdf_txt(sous_titre))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y + hauteur + 6)


def _bande_confiance(pdf, items):
    y0 = pdf.get_y()
    h = 22
    if y0 > 262 - h:
        pdf.add_page()
        y0 = pdf.get_y()
    pdf.rounded_card(10, y0, 190, h, r=3, fill=(255, 255, 255), border=COULEUR_BORDURE)
    col_w = 190 / len(items)
    for i, (titre, sous) in enumerate(items):
        x = 10 + i * col_w
        if i > 0:
            pdf.set_draw_color(*COULEUR_BORDURE)
            pdf.set_line_width(0.2)
            pdf.line(x, y0 + 4, x, y0 + h - 4)
        d = 5
        pdf.set_fill_color(*COULEUR_ACCENT)
        pdf.circle(x + col_w / 2, y0 + 6, d / 2, "F")
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.6)
        cx, cy = x + col_w / 2 - d / 2, y0 + 6 - d / 2
        pdf.polyline([(cx + 1.3, cy + 2.6), (cx + 2.2, cy + 3.6), (cx + 3.9, cy + 1.3)])
        pdf.set_xy(x + 2, y0 + 10)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*COULEUR_PRIMAIRE)
        pdf.cell(col_w - 4, 5, _pdf_txt(titre), align="C")
        pdf.set_xy(x + 2, y0 + 15)
        pdf.set_font("Helvetica", "", 7.3)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(col_w - 4, 5, _pdf_txt(sous), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)


def _carte_offre(pdf, titre_section, offre, cout_actuel):
    h = 40
    y0 = pdf.get_y()
    if y0 > 297 - 24 - h:
        pdf.add_page(); y0 = pdf.get_y()
    pdf.rounded_card(10, y0, 190, h, r=3, fill=COULEUR_FOND_CARTE, border=COULEUR_BORDURE)

    pdf.pill(13, y0 + 3, titre_section.upper(), fill=COULEUR_PRIMAIRE_CLAIR,
             text_color=COULEUR_PRIMAIRE, h=5.5, font=("Helvetica", "B", 7))

    pdf.set_xy(13, y0 + 10.5)
    pdf.set_font("Helvetica", "B", 12.5)
    pdf.set_text_color(*COULEUR_TEXTE)
    pdf.cell(132, 6, _pdf_txt(offre.get("nom", "")))

    pdf.set_xy(13, y0 + 17)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*COULEUR_GRIS)
    carac = offre.get("caracteristiques", "") or ""
    detail = offre.get("fournisseur", "")
    if carac:
        detail += f"  -  {carac[:60]}"
    pdf.cell(132, 5, _pdf_txt(detail))

    cout_actuel = cout_actuel or 0
    prix_offre  = offre.get("prix_mensuel", 0) or 0
    yy = y0 + 26
    pdf.set_xy(13, yy)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.cell(16, 5, _pdf_txt("Avant :"))
    pdf.texte_barre(29, yy, f"{cout_actuel} EUR/mois", taille=9.5)
    pdf.set_xy(70, yy)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.cell(16, 5, _pdf_txt("Apres :"))
    pdf.set_xy(85, yy - 0.7)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*COULEUR_ACCENT)
    pdf.cell(35, 6, _pdf_txt(f"{prix_offre} EUR/mois"))
    if cout_actuel > 0 and prix_offre < cout_actuel:
        baisse = round((cout_actuel - prix_offre) / cout_actuel * 100)
        pdf.pill(13, y0 + 32.5, f"-{baisse}% sur la facture", fill=COULEUR_ACCENT_CLAIR,
                 text_color=COULEUR_ACCENT, h=5, font=("Helvetica", "B", 7.5))
    pdf.set_text_color(0, 0, 0)

    eco_an = offre.get("economie_annuelle", 0) or 0
    px, pw, py, ph = 148, 45, y0 + 4, h - 8
    pdf.rounded_card(px, py, pw, ph, r=2.5, fill=COULEUR_ACCENT)
    pdf.set_xy(px, py + 4)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(pw, 4, _pdf_txt("Economie estimee"), align="C")
    pdf.set_xy(px, py + 10)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(pw, 8, _pdf_txt(f"{round(eco_an, 2)} EUR"), align="C")
    pdf.set_xy(px, py + 19)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.cell(pw, 4, _pdf_txt("par an"), align="C")
    pdf.set_xy(px, py + 24)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(pw, 4, _pdf_txt(f"soit {round(eco_an / 12, 2)} EUR/mois"), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + h + 6)


def generer_pdf_restitution(client, recommandations, nom_societe="IA CONSEIL"):
    if not FPDF_OK:
        return None
    pdf = PDFPro(nom_societe)
    pdf.set_auto_page_break(auto=True, margin=24)
    pdf.add_page()

    nom_complet = f"{client.get('prenom','')} {client.get('nom','')}".strip() or "Client"
    _bloc_identite(pdf, f"Etude preparee pour {nom_complet}", client)

    total_eco_an = sum((r.get("offre", {}).get("economie_annuelle", 0) or 0) for r in recommandations)
    y1 = pdf.get_y()
    pdf.rounded_card(10, y1, 190, 20, r=3, fill=(255, 255, 255), border=COULEUR_BORDURE)
    col_w = 190 / 3
    kpis = [(str(len(recommandations)), "offre(s) optimisee(s)", COULEUR_PRIMAIRE),
            (f"{round(total_eco_an, 2)} EUR", "economie totale / an", COULEUR_ACCENT),
            (f"{round(total_eco_an / 12, 2)} EUR", "soit par mois", COULEUR_ACCENT)]
    for i, (val, label, couleur) in enumerate(kpis):
        x = 10 + i * col_w
        if i > 0:
            pdf.set_draw_color(*COULEUR_BORDURE)
            pdf.set_line_width(0.2)
            pdf.line(x, y1 + 4, x, y1 + 16)
        pdf.set_xy(x, y1 + 3)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*couleur)
        pdf.cell(col_w, 7, _pdf_txt(val), align="C")
        pdf.set_xy(x, y1 + 11.5)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(col_w, 5, _pdf_txt(label), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y1 + 26)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COULEUR_TEXTE)
    pdf.multi_cell(0, 5, _pdf_txt(
        "Voici la synthese des offres que nous avons selectionnees pour votre situation, "
        "avec les economies estimees sur 12 mois. Notre equipe s'occupe de toutes les demarches."))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    for r in recommandations:
        offre = r.get("offre", {})
        _carte_offre(pdf, f"{r.get('univers','')} - {r.get('categorie','')}", offre, r.get("cout_actuel", 0))

    _banniere_totale(pdf, total_eco_an, "Sur 12 mois, tous univers confondus")
    _bande_confiance(pdf, [
        ("Sans engagement", "pour vous"),
        ("Demarches prises en charge", "de A a Z"),
        ("Donnees confidentielles", "traitees en toute securite"),
    ])
    return bytes(pdf.output())


# ------------------------------------------------------------------------------
#  PDF TEASER — aperçu gratuit avant paiement des honoraires (sans détail d'offres)
# ------------------------------------------------------------------------------
def generer_pdf_teaser(client, univers_analyses, economie_totale, nom_societe="IA CONSEIL", details_univers=None):
    if not FPDF_OK:
        return None
    pdf = PDFPro(nom_societe)
    pdf.set_auto_page_break(auto=True, margin=24)
    pdf.add_page()

    nom_complet = f"{client.get('prenom','')} {client.get('nom','')}".strip() or "Client"
    _bloc_identite(pdf, f"Etude preparee pour {nom_complet}", client)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COULEUR_TEXTE)
    pdf.multi_cell(0, 5, _pdf_txt(
        "Notre analyse de votre situation actuelle a permis d'identifier des pistes "
        "d'economies sur les postes suivants :"))
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    details_univers = details_univers or {}
    for u in univers_analyses:
        categories = details_univers.get(u) or []
        hauteur = 9 if not categories else 9 + 5
        y = pdf.get_y()
        pdf.rounded_card(10, y, 190, hauteur, r=2, fill=COULEUR_FOND_CARTE, border=COULEUR_BORDURE)
        pdf.puce_check(15, y + 2.2, u, 170)
        if categories:
            pdf.set_xy(20, y + 8.5)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(*COULEUR_GRIS)
            pdf.cell(0, 4.5, _pdf_txt("Ce que nous vous proposons : " + ", ".join(categories)))
            pdf.set_text_color(0, 0, 0)
        pdf.set_y(y + hauteur + 2)
    pdf.ln(3)

    _banniere_totale(pdf, economie_totale, "Estimation realisee sur la base des documents transmis", hauteur=24)

    y2 = pdf.get_y()
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*COULEUR_PRIMAIRE)
    pdf.cell(0, 7, _pdf_txt("Comment recuperer ces economies ?"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

    etapes = [
        ("1", "Vous validez le devis d'honoraires", "joint a cette etude, calcule au pourcentage de l'economie realisee."),
        ("2", "Vous recevez le detail complet", "des offres et fournisseurs recommandes pour votre situation."),
        ("3", "Nous prenons en charge les demarches", "resiliation et souscription, sans autre intervention de votre part."),
    ]
    for num, titre, sous in etapes:
        y = pdf.get_y()
        pdf.set_fill_color(*COULEUR_PRIMAIRE)
        pdf.circle(16, y + 4, 4, "F")
        pdf.set_xy(12, y + 1)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(8, 6, num, align="C")
        pdf.set_xy(24, y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*COULEUR_TEXTE)
        pdf.cell(176, 5, _pdf_txt(titre), ln=True)
        pdf.set_x(24)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.multi_cell(176, 4.5, _pdf_txt(sous))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    y3 = pdf.get_y()
    pdf.rounded_card(10, y3, 190, 14, r=3, fill=COULEUR_PRIMAIRE_CLAIR)
    pdf.set_xy(15, y3 + 3.5)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*COULEUR_PRIMAIRE)
    pdf.multi_cell(180, 4.7, _pdf_txt(
        "Le detail nominatif des offres vous sera communique apres reglement de nos "
        "honoraires de conseil (devis joint separement)."))
    pdf.set_text_color(0, 0, 0)
    return bytes(pdf.output())


def construire_apercu_pdf_prospect(prospect: dict, nom_societe: str = "IA CONSEIL"):
    """Reconstruit le PDF teaser d'un prospect à partir de ses offres « intéresse le client »
    (prospect['offres_interet'], JSON) — même logique que le wizard de diagnostic (étape 4),
    généralisée pour être réutilisable depuis la fiche prospect (app.py) et le portail public
    (chatbot_api.py, lien SMS). Renvoie None si aucune offre retenue ou économie nulle."""
    from utils import economie_totale_groupee

    try:
        offres_interet = json.loads(prospect.get("offres_interet") or "[]")
    except Exception:
        offres_interet = []
    if not offres_interet:
        return None
    total_eco = economie_totale_groupee(offres_interet)
    if total_eco <= 0:
        return None
    univers_analyses = []
    details_univers = {}
    for o in offres_interet:
        u = o.get("univers")
        if u and u not in univers_analyses:
            univers_analyses.append(u)
        if u:
            categories = details_univers.setdefault(u, [])
            if o.get("categorie") and o["categorie"] not in categories:
                categories.append(o["categorie"])
    return generer_pdf_teaser(prospect, univers_analyses, total_eco, nom_societe,
                               details_univers=details_univers)


# ------------------------------------------------------------------------------
#  PDF DEVIS — honoraires de conseil (% x economie annuelle)
# ------------------------------------------------------------------------------
def generer_pdf_devis(facture, nom_societe="IA CONSEIL"):
    if not FPDF_OK:
        return None
    pdf = PDFPro(nom_societe)
    pdf.set_auto_page_break(auto=True, margin=24)
    pdf.add_page()
    nom_complet = f"{facture.get('prenom','')} {facture.get('nom','')}".strip()

    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*COULEUR_PRIMAIRE)
    pdf.cell(140, 9, _pdf_txt("Devis d'honoraires"), ln=False)
    ref = facture.get("reference", "")
    if ref:
        pdf.set_font("Helvetica", "B", 8.5)
        w = pdf.get_string_width(_pdf_txt(ref)) + 8
        pdf.pill(200 - w, pdf.get_y() + 0.5, ref, fill=COULEUR_PRIMAIRE_CLAIR, text_color=COULEUR_PRIMAIRE, w=w)
    pdf.ln(9)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.cell(0, 6, _pdf_txt(f"Date : {facture.get('date_creation','')}"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    y0 = pdf.get_y()
    pdf.rounded_card(10, y0, 190, 24, r=3, fill=COULEUR_FOND_CARTE, border=COULEUR_BORDURE)
    pdf.set_xy(15, y0 + 3)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*COULEUR_PRIMAIRE)
    pdf.cell(0, 5, _pdf_txt("CLIENT"), ln=True)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*COULEUR_TEXTE)
    coords = [nom_complet]
    if facture.get("adresse"): coords.append(facture.get("adresse"))
    if facture.get("ville"):   coords.append(facture.get("ville"))
    pdf.set_xy(15, y0 + 9)
    pdf.cell(0, 5, _pdf_txt("  -  ".join(x for x in coords if x)), ln=True)
    contacts = []
    if facture.get("telephone"): contacts.append(f"Tel : {facture.get('telephone')}")
    if facture.get("email"):     contacts.append(facture.get("email"))
    pdf.set_x(15)
    pdf.cell(0, 5, _pdf_txt("  -  ".join(contacts)), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + 30)

    y1 = pdf.get_y()
    pdf.rounded_card(10, y1, 190, 40, r=3, fill=(255, 255, 255), border=COULEUR_BORDURE)
    pdf.set_xy(15, y1 + 5)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COULEUR_TEXTE)
    pdf.cell(120, 6, _pdf_txt("Economie annuelle estimee"), ln=False)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(65, 6, _pdf_txt(f"{round(facture.get('economie_annuelle',0),2)} EUR / an"), align="R", ln=True)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(120, 6, _pdf_txt("Taux d'honoraires applique"), ln=False)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(65, 6, _pdf_txt(f"{facture.get('taux_honoraires',0)} %"), align="R", ln=True)
    pdf.set_draw_color(*COULEUR_BORDURE)
    pdf.set_line_width(0.3)
    pdf.line(15, y1 + 20, 195, y1 + 20)

    y2 = y1 + 24
    pdf.rounded_card(13, y2, 184, 12, r=2.5, fill=COULEUR_PRIMAIRE)
    pdf.set_xy(15, y2 + 3)
    pdf.set_font("Helvetica", "B", 11.5)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 6, _pdf_txt("Montant des honoraires"), ln=False)
    pdf.cell(60, 6, _pdf_txt(f"{round(facture.get('montant_honoraires',0),2)} EUR"), align="R")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y1 + 46)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.multi_cell(0, 5, _pdf_txt(
        "Ces honoraires remunerent notre prestation de conseil (analyse de votre situation, "
        "comparaison du marche, recommandation personnalisee) et couvrent la prise en charge "
        "des demarches de changement une fois le mandat signe. Montant exigible au reglement "
        "du present devis."))
    pdf.set_text_color(0, 0, 0)
    return bytes(pdf.output())


# ------------------------------------------------------------------------------
#  PDF MANDAT — autorisation de représentation pour les démarches
# ------------------------------------------------------------------------------
def generer_pdf_mandat(facture, nom_societe="IA CONSEIL"):
    if not FPDF_OK:
        return None
    pdf = PDFPro(nom_societe)
    pdf.set_auto_page_break(auto=True, margin=24)
    pdf.add_page()
    nom_complet = f"{facture.get('prenom','')} {facture.get('nom','')}".strip()

    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*COULEUR_PRIMAIRE)
    pdf.cell(140, 9, _pdf_txt("Mandat de representation"), ln=False)
    ref = facture.get("reference", "")
    if ref:
        pdf.set_font("Helvetica", "B", 8.5)
        w = pdf.get_string_width(_pdf_txt(ref)) + 8
        pdf.pill(200 - w, pdf.get_y() + 0.5, ref, fill=COULEUR_PRIMAIRE_CLAIR, text_color=COULEUR_PRIMAIRE, w=w)
    pdf.ln(9)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*COULEUR_GRIS)
    pdf.cell(0, 6, _pdf_txt("Autorisation de gestion des demarches de resiliation et de souscription"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    y0 = pdf.get_y()
    adresse_complete = ", ".join(x for x in (facture.get("adresse"), facture.get("ville")) if x)
    texte = _pdf_txt(
        f"Je soussigne(e) {nom_complet}"
        + (f", demeurant a {adresse_complete}" if adresse_complete else "")
        + f", mandate {nom_societe} pour effectuer en mon nom et pour mon compte les demarches "
        "necessaires au changement des contrats identifies lors de notre etude (resiliation des "
        "contrats en cours, souscription des nouvelles offres recommandees), et ce sans autre "
        "intervention de ma part.")
    hauteur_texte = pdf.multi_cell(170, 5.5, texte, dry_run=True, output="HEIGHT")
    pdf.rounded_card(10, y0, 190, hauteur_texte + 10, r=3, fill=COULEUR_FOND_CARTE, border=COULEUR_BORDURE)
    pdf.set_xy(15, y0 + 5)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*COULEUR_TEXTE)
    pdf.multi_cell(170, 5.5, texte)
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + hauteur_texte + 16)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _pdf_txt(f"Fait a {facture.get('ville','________________')}, "
                            f"le {facture.get('date_creation','__/__/____').split(' ')[0]}"), ln=True)
    pdf.ln(8)

    if facture.get("mandat_signe"):
        y1 = pdf.get_y()
        pdf.rounded_card(10, y1, 190, 22, r=3, fill=COULEUR_ACCENT_CLAIR, border=COULEUR_BORDURE)
        d = 8
        pdf.set_fill_color(*COULEUR_ACCENT)
        pdf.circle(20, y1 + 11, d / 2, "F")
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.7)
        pdf.polyline([(20 - d / 2 + 2, y1 + 11), (20 - d / 2 + 3.4, y1 + 12.6), (20 - d / 2 + 6, y1 + 8.6)])
        pdf.set_xy(28, y1 + 5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*COULEUR_ACCENT)
        pdf.cell(0, 6, _pdf_txt(
            f"Signe par {facture.get('mandat_signataire','')} "
            f"le {facture.get('mandat_date_signature','')}"), ln=True)
        pdf.set_x(28)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(0, 6, _pdf_txt("Mention \"Lu et approuve, bon pour mandat\""), ln=True)
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*COULEUR_GRIS)
        pdf.cell(0, 6, _pdf_txt("Mention \"Lu et approuve, bon pour mandat\" + signature :"), ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(18)
        pdf.set_draw_color(*COULEUR_GRIS_CLAIR)
        pdf.set_line_width(0.3)
        pdf.line(15, pdf.get_y(), 90, pdf.get_y())
    return bytes(pdf.output())
