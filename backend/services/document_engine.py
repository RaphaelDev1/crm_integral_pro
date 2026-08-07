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
CHAMPS_REQUIS_PAR_TEMPLATE: dict[str, dict[str, dict]] = {
    "mandat": {},
    "resiliation": {
        "numero_contrat": {"label": "Numero de contrat / client chez le fournisseur actuel", "requis": True},
        "date_effet_souhaitee": {"label": "Date d'effet souhaitee", "requis": False},
    },
    "portabilite": {
        "rio": {"label": "RIO (releve d'identite operateur, obtenu au 3179)", "requis": True},
        "numero_ligne": {"label": "Numero de ligne a porter", "requis": True},
    },
    "souscription": {
        "adresse_installation": {"label": "Adresse d'installation", "requis": True},
    },
    "changement_fournisseur": {
        "pdl": {"label": "PDL (point de livraison electricite)", "requis": False},
        "pce": {"label": "PCE (point de comptage/estimation gaz)", "requis": False},
        "rib": {"label": "IBAN pour prelevement", "requis": True},
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


def generer_pdf_mandat_representation(dossier: Dossier, client: Client) -> bytes:
    pdf = PDFDemarche("Mandat de representation")
    pdf.add_page()
    pdf.paragraphe(_identite_client(client), taille=10)
    pdf.paragraphe(
        f"Je soussigne(e) {(client.prenom or '')} {(client.nom or '')}, donne mandat a IA Conseil pour me "
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
    pdf.champ_signature()
    return bytes(pdf.output())


def generer_pdf_resiliation_box(dossier: Dossier, client: Client, donnees: dict) -> bytes:
    pdf = PDFDemarche("Demande de resiliation")
    pdf.add_page()
    pdf.paragraphe(_identite_client(client), taille=10)
    pdf.paragraphe(
        "Objet : demande de resiliation de mon contrat Box / Fibre, dans le cadre du mandat de representation "
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


def generer_pdf_mandat_honoraires(dossier: Dossier, client: Client, mandat: MandatHonoraires) -> bytes:
    pdf = PDFDemarche("Mandat d'honoraires")
    pdf.add_page()
    pdf.paragraphe(_identite_client(client), taille=10)
    pdf.paragraphe(
        f"Je soussigne(e) {(client.prenom or '')} {(client.nom or '')}, confie a IA Conseil un mandat "
        f"d'honoraires pour les prestations de conseil et de mise en concurrence realisees dans le cadre "
        f"du dossier {dossier.univers}"
        + (f" aupres de {dossier.fournisseur_cible}" if dossier.fournisseur_cible else "")
        + ".",
    )
    pdf.paragraphe(
        f"Montant des honoraires : {mandat.montant:.2f} EUR - Taux applicable : {mandat.taux:.2f} %.",
        gras=True,
    )
    pdf.paragraphe(
        "Ce mandat d'honoraires est distinct du mandat de representation aupres des operateurs et "
        "fournisseurs, et couvre uniquement la remuneration du cabinet pour les prestations rendues.",
    )
    pdf.champ_signature()
    return bytes(pdf.output())


GENERATEURS_PAR_TYPE: dict[str, Callable[[Dossier, Client, dict], bytes]] = {
    "mandat": lambda dossier, client, _donnees: generer_pdf_mandat_representation(dossier, client),
    "resiliation": generer_pdf_resiliation_box,
    "portabilite": generer_pdf_demande_portabilite_mobile,
    "souscription": generer_pdf_souscription,
    "changement_fournisseur": generer_pdf_changement_fournisseur_energie,
}
