# ==============================================================================
#  SOUSCRIPTION ASSISTÉE (Playwright) — pré-remplissage du formulaire opérateur
#
#  Ouvre un vrai navigateur (non headless, process détaché) sur le formulaire de
#  souscription en ligne de l'opérateur, pré-rempli avec les données du CRM.
#  Ce module ne soumet JAMAIS la commande/souscription elle-même : le conseiller
#  vérifie les champs et clique lui-même sur le bouton de validation final du site
#  de l'opérateur. Exception : chez Free (Box/Fibre), la page de commande n'est
#  atteignable qu'après un test d'éligibilité par adresse (cascade de listes
#  peuplées en AJAX) — cette étape préalable est automatisée (cf.
#  _remplir_eligibilite_free) car elle ne fait que vérifier une disponibilité,
#  sans engager le client.
# ==============================================================================
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

from db import enregistrer_action
from utils import construire_lien_affilie

# Opérateurs pris en charge pour le pré-remplissage automatique. On démarre avec
# Free et Bouygues (formulaires de souscription les plus simples) ; les autres
# fournisseurs restent en souscription manuelle tant qu'ils n'ont pas été ajoutés ici.
OPERATEURS_SUPPORTES = {"Free", "Bouygues"}

# Chez Free, le formulaire coordonnées (prénom/nom/email/adresse) n'apparaît qu'après
# une ou deux étapes que le conseiller valide lui-même (choix du Player TV...) après
# l'éligibilité + choix de box automatisés. On retente le remplissage périodiquement
# tant que la fenêtre reste ouverte, dans cette limite de temps.
SURVEILLANCE_DUREE_MAX_S    = 15 * 60
SURVEILLANCE_INTERVALLE_MS  = 3000

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
    payload = {"fournisseur": fournisseur, "url": url, "donnees": donnees, "nom_offre": nom_offre}

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
    forcément tous les champs, ex. pas de civilité en mobile prépayé). N'écrase jamais
    un champ déjà rempli (par un appel précédent ou par le conseiller lui-même) — sûr à
    rappeler plusieurs fois sur la même page (cf. boucle de surveillance dans _executer)."""
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
                    if (locator.input_value() or "").strip():
                        continue
                    locator.select_option(label=valeur)
                else:
                    if (locator.input_value() or "").strip():
                        continue
                    locator.fill(valeur)
                break
            except Exception:
                continue


def _normaliser_texte(s: str) -> str:
    """Normalise pour comparaison souple (accents, casse, espaces multiples) — ex.
    « Rue de Chantilly » et « RUE DE CHANTILLY » doivent matcher la même option."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip().upper()


def _mots_normalises(s: str) -> frozenset:
    """Ensemble des mots d'un texte, normalisés — le référentiel voirie de Free inverse
    l'ordre des noms de voie (ex. « CHANTILLY (RUE DE) » pour « Rue de Chantilly ») ; comparer
    des ensembles de mots plutôt que des chaînes littérales absorbe cette inversion."""
    s = re.sub(r"[(),]", " ", _normaliser_texte(s))
    return frozenset(w for w in s.split() if w)


def _selectionner_option_proche(page, select_id: str, texte_cible: str, id_suivant: str = None) -> bool:
    """Sélectionne, dans un <select> peuplé en AJAX (cascade adresse Free), l'option la
    plus proche de `texte_cible` (exacte, puis mêmes mots dans le désordre — cf.
    _mots_normalises —, puis correspondance partielle) puis attend que le <select> suivant
    de la cascade se peuple à son tour. Renvoie False si aucune correspondance ou si le
    suivant ne se peuple pas — l'adresse n'est alors pas au référentiel Free tel quel, au
    conseiller de continuer manuellement."""
    try:
        options = [o for o in page.locator(f"#{select_id} option").all_inner_texts() if o.strip()]
    except Exception:
        return False
    if not options:
        return False
    cible = _normaliser_texte(texte_cible)
    mots_cible = _mots_normalises(texte_cible)
    choix = (next((o for o in options if _normaliser_texte(o) == cible), None)
             or next((o for o in options if mots_cible and _mots_normalises(o) == mots_cible), None)
             or next((o for o in options if cible and cible in _normaliser_texte(o)), None)
             or next((o for o in options if cible and _normaliser_texte(o) in cible), None))
    if not choix:
        return False
    try:
        page.locator(f"#{select_id}").select_option(label=choix)
    except Exception:
        return False
    if id_suivant:
        try:
            page.wait_for_function(
                f"document.querySelectorAll('#{id_suivant} option').length > 1", timeout=8000)
        except Exception:
            return False
    return True


def _accepter_cookies(page):
    """Ferme la bannière de consentement cookies (CMP) si elle est affichée, avant tout
    remplissage — sans quoi elle recouvre le formulaire et intercepte clics/saisies.
    Best-effort : essaie les CMP les plus courants côté opérateurs télécom (Didomi,
    OneTrust) puis un repli générique par texte de bouton ; ignore silencieusement
    l'absence de bannière (site déjà consenti, cookie de session existant...)."""
    selecteurs = [
        "#didomi-notice-agree-button",
        "#onetrust-accept-btn-handler",
        "button[id*='accept' i]",
    ]
    for sel in selecteurs:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=2000)
                page.wait_for_timeout(300)
                return
        except Exception:
            continue
    for texte in ["Tout accepter", "J'accepte", "Accepter et fermer", "Accepter", "Accept all"]:
        try:
            loc = page.get_by_role("button", name=texte, exact=False).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=2000)
                page.wait_for_timeout(300)
                return
        except Exception:
            continue


def _remplir_eligibilite_free(page, donnees: dict) -> bool:
    """Remplit le test d'éligibilité Free (code postal → ville → voie → numéro, cascade
    peuplée en AJAX) avec l'adresse du client, jusqu'à la page de commande qui suit une
    fois le numéro sélectionné (le site soumet alors lui-même la cascade). Best-effort :
    si l'adresse ne correspond à rien dans le référentiel Free (format différent, adresse
    trop récente...), s'arrête sans erreur — le conseiller termine la cascade lui-même
    dans la fenêtre restée ouverte. Renvoie True si le numéro a bien été sélectionné."""
    code_postal = (donnees.get("code_postal") or "").strip()
    adresse     = (donnees.get("adresse") or "").strip()
    ville       = (donnees.get("ville") or "").strip()
    if not code_postal:
        return False
    try:
        page.locator("#code_postal").fill(code_postal)
    except Exception:
        return False

    # Cette première page (accueil du test d'éligibilité) ne contient que le code postal ;
    # il faut valider « Continuer » pour arriver sur la page ville/voie/numéro qui suit
    # (00_insert_addr.pl, cascade classique en AJAX gérée ci-dessous).
    try:
        with page.expect_navigation(timeout=10000):
            page.get_by_role("button", name="Continuer").click()
    except Exception:
        return False
    try:
        page.wait_for_selector("#ville_select", timeout=8000)
    except Exception:
        return False

    if ville and not _selectionner_option_proche(page, "ville_select", ville, "nom_voie"):
        return False

    # Le champ CRM « adresse » est en texte libre (ex. "12 rue de Chantilly") — on en
    # extrait le numéro (avec suffixe éventuel bis/ter/A/B) et le nom de voie séparément,
    # tels qu'attendus par les deux listes déroulantes successives du site.
    m = re.match(r"^\s*(\d+\s?[a-zA-Z]?)\s+(.+)$", adresse)
    numero_cible, voie_cible = (m.group(1), m.group(2)) if m else ("", adresse)
    if not voie_cible or not _selectionner_option_proche(page, "nom_voie", voie_cible, "numero"):
        return False
    if not numero_cible:
        return False

    try:
        options_num = [o for o in page.locator("#numero option").all_inner_texts() if o.strip()]
    except Exception:
        return False
    cible_num = _normaliser_texte(numero_cible)
    choix_num = next((o for o in options_num if _normaliser_texte(o).split(" ")[0] == cible_num), None)
    if not choix_num:
        return False
    try:
        with page.expect_navigation(timeout=15000):
            page.locator("#numero").select_option(label=choix_num)   # déclenche this.form.submit()
    except Exception:
        pass   # Pas de rechargement détecté (page en SPA) — on continue quand même

    # Suit d'une case « référence de prise fibre » optionnelle avant de pouvoir continuer —
    # on coche « je ne la connais pas », le conseiller la renseignera lui-même si besoin.
    try:
        if page.locator("#pto_hotline").count():
            page.locator("#pto_hotline").check()
            with page.expect_navigation(timeout=10000):
                page.get_by_role("button", name="Continuer").click()
    except Exception:
        pass
    return True


def _extraire_titre_carte(texte: str) -> str:
    """Isole le titre d'une carte d'offre Free (ex. « Freebox Ultra ») dans le texte complet
    de la carte, qui contient aussi bandeau promo (« Exclu Web »...) et argumentaire commercial
    listés avant/après selon les offres."""
    for segment in texte.splitlines():
        segment = segment.strip()
        if segment.lower().startswith("freebox"):
            return segment
    return texte.strip().splitlines()[0] if texte.strip() else ""


def _choisir_box_free(page, nom_offre: str) -> bool:
    """Sur la page de choix de box qui suit l'éligibilité (01_choose_box.pl), clique CHOISIR
    sur la carte dont le titre correspond le mieux à `nom_offre` (catalogue CRM) — ex.
    « Freebox Ultra » du catalogue vers la carte « Freebox Ultra » du site. N'engage rien à ce
    stade (pas de paiement, juste une sélection modifiable dans la suite du tunnel). Si aucune
    carte ne correspond (offre non proposée à cette adresse, gamme différente...), s'arrête
    sans erreur — le conseiller choisit lui-même sur la page restée ouverte."""
    cible = _mots_normalises(nom_offre)
    if not cible:
        return False
    try:
        boutons = page.get_by_text("CHOISIR", exact=True)
        n = boutons.count()
    except Exception:
        return False

    candidats = []
    for i in range(n):
        el = boutons.nth(i)
        try:
            if not el.is_visible():
                continue
            texte = el.locator("xpath=ancestor::div[contains(@class,'box_model')][1]").inner_text()
        except Exception:
            continue
        candidats.append((i, _mots_normalises(_extraire_titre_carte(texte))))

    exacts = [i for i, mots in candidats if mots == cible]
    # Repli : la carte du site n'est qu'un sous/sur-ensemble des mots du catalogue (ex.
    # catalogue « Freebox Pop Fibre » vs carte « Freebox Pop ») — on prend la première.
    proches = exacts or [i for i, mots in candidats if mots and (mots <= cible or cible <= mots)]
    if not proches:
        return False
    try:
        with page.expect_navigation(timeout=15000):
            boutons.nth(proches[0]).click()
    except Exception:
        pass
    return True


def _executer(chemin_json: str):
    """Point d'entrée exécuté dans le process détaché : ouvre un navigateur visible,
    pré-remplit le formulaire, puis attend que le conseiller ferme la fenêtre
    lui-même — aucune fermeture ni soumission de commande automatique."""
    with open(chemin_json, "r", encoding="utf-8") as f:
        payload = json.load(f)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(payload["url"], wait_until="domcontentloaded")
        _accepter_cookies(page)
        if payload["fournisseur"] == "Free":
            if _remplir_eligibilite_free(page, payload["donnees"]):
                _choisir_box_free(page, payload.get("nom_offre", ""))
        _remplir_page(page, payload["fournisseur"], payload["donnees"])

        # Chez Free, le formulaire coordonnées n'apparaît souvent qu'après une étape
        # supplémentaire validée par le conseiller (choix du Player TV...) — on retente
        # le remplissage périodiquement en arrière-plan tant que la fenêtre reste ouverte.
        # _remplir_page n'écrase jamais un champ déjà rempli, donc sans risque de « combattre »
        # une saisie manuelle en cours.
        if payload["fournisseur"] == "Free":
            debut = time.monotonic()
            while time.monotonic() - debut < SURVEILLANCE_DUREE_MAX_S:
                try:
                    page.wait_for_timeout(SURVEILLANCE_INTERVALLE_MS)
                    if page.is_closed():
                        break
                    _remplir_page(page, payload["fournisseur"], payload["donnees"])
                except Exception:
                    break

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
