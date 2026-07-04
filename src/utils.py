# ==============================================================================
#  UTILITAIRES GLOBAUX — helpers génériques sans dépendance métier
# ==============================================================================
import itertools
import re
import secrets
import threading
from io import BytesIO
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import pandas as pd

try:
    import openpyxl  # noqa: F401 — moteur requis par pandas.to_excel(engine="openpyxl")
    OPENPYXL_OK = True
except Exception:
    OPENPYXL_OK = False


def safe_float(val, default: float = 0.0) -> float:
    """Conversion float robuste — jamais de crash sur valeur vide ou invalide."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def valider_email(email: str) -> bool:
    """Vérifie qu'un email a une forme valide (non bloquant, juste un avertissement)."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$", email.strip())) if email.strip() else True


def valider_telephone(tel: str) -> bool:
    """Vérifie qu'un numéro FR a 10 chiffres (autorise espaces/tirets)."""
    digits = re.sub(r"[\s.\-]", "", tel.strip())
    return bool(re.match(r"^(0|\+33)[1-9]\d{8}$", digits)) if digits else True


def parser_date_relance(date_str):
    """Parse une date 'dd/mm/YYYY' -> objet date, ou None si vide/invalide."""
    try:
        return datetime.strptime(str(date_str).strip(), "%d/%m/%Y").date()
    except (ValueError, TypeError, AttributeError):
        return None


def exporter_excel(df: pd.DataFrame, nom_feuille: str = "Export"):
    """Sérialise un DataFrame en bytes .xlsx (moteur openpyxl). None si moteur absent ou df vide."""
    if not OPENPYXL_OK or df is None or df.empty:
        return None
    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name=nom_feuille, engine="openpyxl")
    buffer.seek(0)
    return buffer.getvalue()


def construire_lien_affilie(url_base: str, code_affiliation: str = "", parametres: dict = None) -> str:
    """Ajoute le code d'affiliation et les paramètres du client à l'URL de souscription
    d'une offre, sans écraser une éventuelle query string déjà présente sur l'URL."""
    if not url_base:
        return ""
    parts = urlsplit(url_base)
    query = dict(parse_qsl(parts.query))
    if code_affiliation:
        query["aff"] = code_affiliation
    for cle, val in (parametres or {}).items():
        if val:
            query[cle] = val
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


_ref_lock    = threading.Lock()
_ref_counter = itertools.count()   # partagé par tous les threads du process


def generer_ref(prefix: str = "REF") -> str:
    """Référence unique basée sur timestamp + compteur atomique + 3 chiffres
    aléatoires. Le compteur (incrémenté sous verrou, partagé par tous les threads
    du process — c'est le cas de tous les conseillers connectés à un même serveur
    Streamlit) garantit l'absence de collision même en rafale/accès concurrent ;
    le suffixe aléatoire évite les doublons prévisibles entre deux process/redémarrages
    au même instant."""
    now = datetime.now()
    with _ref_lock:
        compteur = next(_ref_counter) % 1000
    suffix = secrets.randbelow(900) + 100   # 100–999
    return f"{prefix}-{now.year}-{now.strftime('%m%d')}-{compteur:03d}{suffix}"
