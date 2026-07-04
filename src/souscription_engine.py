# ==============================================================================
#  SOUSCRIPTION ASSISTÉE (Playwright) — pré-remplissage du formulaire opérateur
#
#  Ouvre un vrai navigateur (non headless, process détaché) sur le formulaire de
#  souscription en ligne de l'opérateur, pré-rempli avec les données du CRM.
#  Ce module ne soumet JAMAIS le formulaire : le conseiller vérifie les champs
#  et clique lui-même sur le bouton de validation du site de l'opérateur.
# ==============================================================================
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from db import enregistrer_action
from utils import construire_lien_affilie

# Opérateurs pris en charge pour le pré-remplissage automatique. On démarre avec
# Free et Bouygues (formulaires de souscription les plus simples) ; les autres
# fournisseurs restent en souscription manuelle tant qu'ils n'ont pas été ajoutés ici.
OPERATEURS_SUPPORTES = {"Free", "Bouygues"}

# Sélecteurs CSS candidats par champ logique, essayés dans l'ordre. La structure
# exacte (id/name/attributs) d'un formulaire opérateur varie et change au fil des
# refontes du site — plusieurs candidats génériques couvrent la majorité des cas
# sans dépendre d'une inspection préalable de chaque site.
SELECTEURS_CANDIDATS = {
    "civilite":    ['select[name*="civilite" i]', 'select[id*="civility" i]'],
    "prenom":      ['input[name*="prenom" i]', 'input[id*="firstname" i]',
                     'input[autocomplete="given-name"]'],
    "nom":         ['input[name*="nom" i]:not([name*="prenom" i])', 'input[id*="lastname" i]',
                     'input[autocomplete="family-name"]'],
    "email":       ['input[type="email"]', 'input[name*="email" i]', 'input[autocomplete="email"]'],
    "telephone":   ['input[type="tel"]', 'input[name*="telephone" i]', 'input[name*="phone" i]',
                     'input[autocomplete="tel"]'],
    "adresse":     ['input[name*="adresse" i]', 'input[id*="address" i]',
                     'input[autocomplete="address-line1"]'],
    "code_postal": ['input[name*="codepostal" i]', 'input[name*="postal" i]',
                     'input[autocomplete="postal-code"]'],
    "ville":       ['input[name*="ville" i]', 'input[name*="city" i]',
                     'input[autocomplete="address-level2"]'],
}

# Sélecteurs spécifiques à un opérateur, prioritaires sur les candidats génériques
# ci-dessus. À compléter au fur et à mesure de l'inspection des vrais formulaires
# de souscription Free / Bouygues (vide pour l'instant → repli sur les génériques).
SELECTEURS_PAR_OPERATEUR = {
    "Free":     {},
    "Bouygues": {},
}


def construire_donnees_client(record: dict) -> dict:
    """Convertit un enregistrement prospect/client (dict-like : pandas Series ou
    sqlite3.Row) en champs normalisés pour le formulaire de souscription."""
    return {
        "civilite":    "",
        "prenom":      record.get("prenom", "") or "",
        "nom":         record.get("nom", "") or "",
        "email":       record.get("email", "") or "",
        "telephone":   record.get("telephone", "") or "",
        "adresse":     record.get("adresse", "") or "",
        "code_postal": record.get("code_postal", "") or "",
        "ville":       record.get("ville", "") or "",
    }


def lancer_souscription(fournisseur: str, url_souscription: str, donnees: dict,
                         code_affiliation: str = "", auteur: str = "",
                         entite_type: str = "", entite_id: int = None,
                         nom_offre: str = ""):
    """Lance un navigateur Playwright visible (process détaché de Streamlit) sur le
    formulaire de souscription de `fournisseur`, pré-rempli avec `donnees`.
    Ne soumet jamais le formulaire. Renvoie (ok: bool, message: str)."""
    if fournisseur not in OPERATEURS_SUPPORTES:
        return False, (f"Pré-remplissage automatique non disponible pour « {fournisseur} » — "
                        f"ouvrez le lien et souscrivez manuellement sur le site de l'opérateur.")
    if not url_souscription:
        return False, "Aucune URL de souscription renseignée pour cette offre."

    url = construire_lien_affilie(url_souscription, code_affiliation)
    payload = {"fournisseur": fournisseur, "url": url, "donnees": donnees}

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(payload, tmp, ensure_ascii=False)
    tmp.close()

    script = str(Path(__file__).resolve())
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen([sys.executable, script, "--run", tmp.name],
                          creationflags=creationflags, close_fds=True)
    except Exception as exc:
        return False, f"Impossible de lancer le navigateur : {exc}"

    if entite_type and entite_id:
        enregistrer_action(entite_type, int(entite_id), "Pré-remplissage souscription",
                            f"{fournisseur} — {nom_offre or ''} "
                            "(formulaire ouvert, validation manuelle par le conseiller)")
    return True, ("Navigateur ouvert avec le formulaire pré-rempli — vérifiez les informations "
                  "puis validez vous-même la souscription sur le site de l'opérateur.")


def _remplir_page(page, fournisseur: str, donnees: dict):
    """Essaie, pour chaque champ logique, chaque sélecteur candidat dans l'ordre ;
    ignore silencieusement un champ absent du formulaire (chaque opérateur n'a pas
    forcément tous les champs, ex. pas de civilité en mobile prépayé)."""
    specifiques = SELECTEURS_PAR_OPERATEUR.get(fournisseur, {})
    for champ, valeur in donnees.items():
        if not valeur:
            continue
        for selecteur in specifiques.get(champ, []) + SELECTEURS_CANDIDATS.get(champ, []):
            try:
                locator = page.locator(selecteur).first
                if locator.count() == 0:
                    continue
                if locator.evaluate("el => el.tagName.toLowerCase()") == "select":
                    locator.select_option(label=valeur)
                else:
                    locator.fill(valeur)
                break
            except Exception:
                continue


def _executer(chemin_json: str):
    """Point d'entrée exécuté dans le process détaché : ouvre un navigateur visible,
    pré-remplit le formulaire, puis attend que le conseiller ferme la fenêtre
    lui-même — aucune fermeture ni soumission automatique."""
    with open(chemin_json, "r", encoding="utf-8") as f:
        payload = json.load(f)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(payload["url"], wait_until="domcontentloaded")
        _remplir_page(page, payload["fournisseur"], payload["donnees"])
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--run":
        _executer(sys.argv[2])
