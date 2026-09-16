# ==============================================================================
#  SOUSCRIPTION ASSISTÉE (Playwright) — pré-remplissage du formulaire opérateur
#
#  Portage de src/souscription_engine.py (app Streamlit conseiller, en cours
#  d'extinction — voir GUIDE_LANCEMENT.md) vers le backend FastAPI. Logique de
#  remplissage identique ; seule l'origine des données change (ORM Client/Offre
#  au lieu d'un dict pandas/sqlite3.Row) et la journalisation de l'action est
#  déplacée côté appelant (backend/routers/dossiers.py), qui dispose déjà d'une
#  session async — voir backend/services/audit_engine.py::enregistrer_action.
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
#
#  ⚠️ Ne fonctionne que si ce backend tourne sur la machine du conseiller (le
#  navigateur s'ouvre sur l'écran du process qui l'a lancé) — inutilisable
#  depuis un backend déployé à distance (Fly.io...), même limite que documentée
#  pour la version Streamlit dans DEPLOIEMENT.md.
# ==============================================================================
from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import tempfile
import time
import traceback
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.models.client import Client
from backend.models.contrat import Contrat

# Racine du repo (deux niveaux au-dessus de backend/services/) — nécessaire pour
# lancer le sous-process comme un module (`python -m backend.services...`), ce
# module faisant partie du package `backend` contrairement à l'original
# src/souscription_engine.py qui était un script autonome.
RACINE_REPO = Path(__file__).resolve().parents[2]

# Le process détaché (DETACHED_PROCESS, cf. lancer_souscription) n'a ni console
# ni stdout/stderr hérité : une exception non rattrapée y disparaît silencieusement
# (le conseiller voit juste « rien ne s'est passé »). On journalise donc dans un
# fichier dédié à la racine du repo (déjà couvert par le *.log du .gitignore).
JOURNAL = logging.getLogger("souscription_engine")


def _configurer_journal():
    if JOURNAL.handlers:
        return
    JOURNAL.setLevel(logging.INFO)
    handler = logging.FileHandler(RACINE_REPO / "souscription_assistee.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    JOURNAL.addHandler(handler)

# Opérateurs pris en charge pour le pré-remplissage automatique. On démarre avec
# Free et Bouygues (formulaires de souscription les plus simples) ; les autres
# fournisseurs restent en souscription manuelle tant qu'ils n'ont pas été ajoutés ici.
OPERATEURS_SUPPORTES = {"Free", "Bouygues"}

# Chez Free, le tunnel diffère selon la catégorie de l'offre (voir seed_catalogue.py) :
# Box/Fibre et Pack passent par la cascade d'éligibilité adresse (_remplir_eligibilite_free
# + _choisir_box_free) ; Mobile (forfait seul, sans vente de téléphone) atterrit directement
# sur mobile.free.fr/souscription/options (_remplir_options_mobile_free ci-dessous), qui n'a
# ni éligibilité adresse ni choix de box.
CATEGORIES_FREE_BOX = ("Box", "Fibre", "Pack")

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
    # Page "informations personnelles" du tunnel Free Mobile — champ de
    # confirmation d'email distinct du champ email lui-même.
    "email_confirmation": ['input[name*="confirm" i][name*="email" i]',
                            'input[id*="confirm" i][id*="email" i]',
                            'input[name*="emailconfirmation" i]'],
}

# Sélecteurs spécifiques à un opérateur, prioritaires sur les candidats génériques
# ci-dessus. À compléter au fur et à mesure de l'inspection des vrais formulaires
# de souscription Free / Bouygues (vide pour l'instant → repli sur les génériques).
# Bouygues n'a par ailleurs pas de vraie URL de souscription renseignée dans le
# catalogue de seed (voir backend/scripts/seed_catalogue.py) — tant que ça reste
# le cas, le pré-remplissage pour Bouygues échoue dès la navigation, comme pour
# tout fournisseur hors Free.
SELECTEURS_PAR_OPERATEUR = {
    "Free":     {},
    "Bouygues": {},
}


def construire_lien_affilie(url_base: str, code_affiliation: str = "", parametres: dict | None = None) -> str:
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


def construire_donnees_client(client: Client, contrat_mobile: Contrat | None = None) -> dict:
    """Convertit un Client (ORM) en champs normalisés pour le formulaire de souscription.

    `contrat_mobile` (la ligne « Forfait mobile » de référence, voir
    backend/services/demarches_engine.py::_synchroniser_contrat_portabilite) n'est
    utile que pour un forfait Free Mobile — `conserver_numero`/`type_sim` pilotent
    les choix du tunnel d'options (_remplir_options_mobile_free), pas un champ de
    formulaire générique : ils sont ignorés par `_remplir_page` pour tout autre
    fournisseur (absents de SELECTEURS_CANDIDATS)."""
    donnees = {
        "civilite":    "",
        "prenom":      client.prenom or "",
        "nom":         client.nom or "",
        "email":       client.email or "",
        "email_confirmation": client.email or "",
        "telephone":   client.telephone or "",
        "adresse":     client.adresse or "",
        "code_postal": client.code_postal or "",
        "ville":       client.ville or "",
        # Page "informations personnelles" du tunnel Free Mobile — non
        # automatisés dans SELECTEURS_CANDIDATS (libellés du site jamais
        # vérifiés), transmis quand même pour figurer dans l'aide-mémoire
        # affiché au conseiller (souscription-reference/page.tsx).
        "date_naissance": client.date_naissance or "",
        "departement_naissance": client.departement_naissance or "",
        "ville_naissance": client.ville_naissance or "",
    }
    if contrat_mobile is not None:
        donnees["conserver_numero"] = contrat_mobile.conserver_numero or ""
        donnees["type_sim"] = contrat_mobile.type_sim or ""
    return donnees


def lancer_souscription(fournisseur: str, url_souscription: str, donnees: dict,
                         code_affiliation: str = "", nom_offre: str = "", categorie: str = "",
                         position: tuple[int, int] | None = None, taille: tuple[int, int] | None = None):
    """Lance un navigateur Playwright visible (process détaché du backend) sur le
    formulaire de souscription de `fournisseur`, pré-rempli avec `donnees`.
    Ne soumet jamais le formulaire. Renvoie (ok: bool, message: str).

    `position`/`taille` (en pixels écran, coin haut-gauche + largeur/hauteur)
    permettent au conseiller de positionner cette fenêtre à côté de la fenêtre
    de référence ouverte par le frontend (voir dossiers.py::pre_remplir_souscription
    et frontend-conseiller/app/(conseiller)/dossiers/[id]/page.tsx::handlePreRemplir)
    pour un affichage 50/50 — sans valeur, Chromium choisit sa position par défaut."""
    if fournisseur not in OPERATEURS_SUPPORTES:
        return False, (f"Pré-remplissage automatique non disponible pour « {fournisseur} » — "
                        f"ouvrez le lien et souscrivez manuellement sur le site de l'opérateur.")
    if not url_souscription:
        return False, "Aucune URL de souscription renseignée pour cette offre."
    # Domaine ".invalid" (RFC 2606) = URL placeholder du catalogue de seed
    # (voir backend/scripts/seed_catalogue.py::URL_SOUSCRIPTION_DEFAUT), posée
    # tant qu'aucune vraie URL n'a été renseignée pour cette offre. Sans ce
    # garde-fou, le navigateur s'ouvrait quand même dessus et échouait
    # silencieusement à la navigation (domaine qui ne résout jamais) : le
    # conseiller ne voyait qu'une fenêtre vide sans comprendre pourquoi.
    if (urlsplit(url_souscription).hostname or "").endswith(".invalid"):
        return False, (f"Aucune URL de souscription réelle n'est configurée pour cette offre "
                        f"({fournisseur}) dans le catalogue — ouvrez le lien et souscrivez "
                        f"manuellement, ou complétez l'URL de souscription sur la fiche de l'offre.")

    url = construire_lien_affilie(url_souscription, code_affiliation)
    payload = {
        "fournisseur": fournisseur, "url": url, "donnees": donnees, "nom_offre": nom_offre,
        "categorie": categorie,
        "window_position": list(position) if position else None,
        "window_size": list(taille) if taille else None,
    }

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(payload, tmp, ensure_ascii=False)
    tmp.close()

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(
            [sys.executable, "-m", "backend.services.souscription_engine", "--run", tmp.name],
            cwd=str(RACINE_REPO), creationflags=creationflags, close_fds=True,
            # DETACHED_PROCESS laisse stdin/stdout/stderr sans handle valide hérité :
            # Playwright plante dès sync_playwright() en tentant de lancer son driver
            # Node dessus (l'utilisateur ne voit alors qu'une fenêtre console qui
            # s'ouvre et se ferme aussitôt, sans navigateur). DEVNULL fournit des
            # handles valides et neutres à la place.
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        return False, f"Impossible de lancer le navigateur : {exc}"

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


def _selectionner_option_proche(page, select_id: str, texte_cible: str, id_suivant: str | None = None) -> bool:
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


def _choisir_option_texte(page, textes: list[str]) -> bool:
    """Clique le premier élément visible dont le texte correspond à l'un de `textes`
    (dans l'ordre) — pour des choix affichés en boutons/cases stylées plutôt qu'en
    <select> classique, comme le tunnel d'options Free Mobile. Best-effort : une
    correspondance absente est ignorée silencieusement, le conseiller fait le choix
    lui-même sur la page restée ouverte."""
    for texte in textes:
        try:
            loc = page.get_by_text(texte, exact=False).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=2000)
                page.wait_for_timeout(300)
                return True
        except Exception:
            continue
    return False


def _verifier_offre_panier_free(page, nom_offre: str) -> None:
    """Sur la page panier free.fr (« Votre panier »), atteinte après la sélection
    de l'offre mobile, vérifie que l'offre affichée par défaut correspond bien à
    `nom_offre` choisi dans le dossier CRM — le panier peut afficher une offre par
    défaut différente (ex. « Série Free ») nécessitant de cliquer « Modifier » puis
    de sélectionner la bonne offre dans la liste proposée.

    Best-effort par texte visible, jamais vérifié contre le vrai DOM du panier
    free.fr — à ajuster si les libellés réels diffèrent. Un échec de correspondance
    ne bloque jamais la suite du tunnel : le conseiller vérifie lui-même l'offre
    affichée dans le panier avant de continuer (cf. philosophie du module, voir
    docstring de _choisir_option_texte)."""
    if not nom_offre:
        return
    try:
        deja_correcte = page.get_by_text(nom_offre, exact=False).first
        if deja_correcte.count() and deja_correcte.is_visible():
            return
    except Exception:
        return

    if not _choisir_option_texte(page, ["Modifier"]):
        return
    _choisir_option_texte(page, [nom_offre])


def _remplir_options_mobile_free(page, donnees: dict) -> None:
    """Tunnel d'options d'un forfait Free Mobile seul (mobile.free.fr/souscription/options,
    avant la page « informations personnelles ») : jamais de cascade d'éligibilité adresse
    ni de choix de box ici (voir CATEGORIES_FREE_BOX), contrairement à Free Box/Fibre.

    Best-effort par texte visible : ce tunnel n'expose pas d'ids stables comme la
    cascade d'éligibilité Free Box (_selectionner_option_proche) — un choix non
    trouvé est simplement laissé au conseiller."""
    # Consigne métier : ne jamais rattacher automatiquement à un compte Freebox
    # existant, même si "Oui, je suis abonné" est présélectionné sur la page.
    _choisir_option_texte(page, ["Non, je ne suis pas abonné", "Non je ne suis pas abonné"])

    if donnees.get("conserver_numero") == "non":
        _choisir_option_texte(page, ["Je choisis un nouveau numéro", "je choisis un nouveau numéro"])
    # Si "oui" (ou non renseigné) : "Je conserve mon numéro actuel" reste le choix
    # présélectionné par défaut sur la page — rien à faire.

    if donnees.get("type_sim") == "esim":
        _choisir_option_texte(page, ["eSIM"])
    elif donnees.get("type_sim") == "carte_sim":
        _choisir_option_texte(page, ["Carte SIM"])

    # Consigne métier : toujours choisir « sans solution » McAfee (jamais la
    # sécurité payante proposée par défaut).
    _choisir_option_texte(page, ["Sans solution", "Sans solution de sécurité", "Non merci"])


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
    lui-même — aucune fermeture ni soumission de commande automatique.

    Ce process n'a pas de console (cf. DETACHED_PROCESS dans lancer_souscription) :
    toute exception non rattrapée ici est invisible pour le conseiller, qui ne voit
    que « rien ne s'est passé ». Chaque étape est donc isolée dans son propre
    try/except et journalisée (cf. JOURNAL) — un échec de remplissage ne doit
    jamais fermer prématurément le navigateur ni empêcher les étapes suivantes."""
    _configurer_journal()
    with open(chemin_json, "r", encoding="utf-8") as f:
        payload = json.load(f)
    fournisseur = payload["fournisseur"]
    JOURNAL.info("Lancement — fournisseur=%s url=%s", fournisseur, payload["url"])

    from playwright.sync_api import sync_playwright

    # --window-position/--window-size sont des arguments Chromium natifs, pas des
    # options Playwright (le `viewport` de la page ne contrôle que le contenu,
    # pas la fenêtre OS) — c'est la méthode standard pour positionner la fenêtre.
    args = []
    if payload.get("window_position"):
        x, y = payload["window_position"]
        args.append(f"--window-position={x},{y}")
    if payload.get("window_size"):
        w, h = payload["window_size"]
        args.append(f"--window-size={w},{h}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=args)
        page = browser.new_page(no_viewport=True) if args else browser.new_page()

        # Cette fenêtre Chromium est un process OS distinct de celui du navigateur
        # du conseiller (qui vient lui-même de prendre le focus en ouvrant la
        # fenêtre de référence, cf. handlePreRemplir côté frontend) : sans appel
        # explicite, elle s'ouvre en arrière-plan et passe inaperçue — le
        # conseiller la croit alors jamais ouverte alors qu'elle tourne bien
        # (constaté dans souscription_assistee.log : navigation Free réussie,
        # fenêtre restée ouverte des heures sans qu'on ne l'ait vue).
        try:
            page.bring_to_front()
        except Exception:
            pass

        try:
            page.goto(payload["url"], wait_until="domcontentloaded", timeout=30000)
        except Exception:
            # Ex. URL de catalogue invalide/injoignable : on journalise mais on laisse
            # le navigateur ouvert sur la page d'erreur — le conseiller voit quel URL
            # a été tenté au lieu de voir une fenêtre qui se ferme sans explication.
            JOURNAL.error("Échec de navigation vers %s :\n%s", payload["url"], traceback.format_exc())
        else:
            try:
                _accepter_cookies(page)
            except Exception:
                JOURNAL.warning("Échec fermeture bannière cookies :\n%s", traceback.format_exc())

            categorie = payload.get("categorie", "")
            categorie_box = fournisseur == "Free" and any(mot in categorie for mot in CATEGORIES_FREE_BOX)
            categorie_mobile = fournisseur == "Free" and not categorie_box and "Mobile" in categorie
            try:
                if categorie_box:
                    if _remplir_eligibilite_free(page, payload["donnees"]):
                        _choisir_box_free(page, payload.get("nom_offre", ""))
                elif categorie_mobile:
                    _verifier_offre_panier_free(page, payload.get("nom_offre", ""))
                    _remplir_options_mobile_free(page, payload["donnees"])
                _remplir_page(page, fournisseur, payload["donnees"])
            except Exception:
                JOURNAL.error("Échec de remplissage :\n%s", traceback.format_exc())

            # Chez Free, le formulaire coordonnées n'apparaît souvent qu'après une étape
            # supplémentaire validée par le conseiller (choix du Player TV...) — on retente
            # le remplissage périodiquement en arrière-plan tant que la fenêtre reste ouverte.
            # _remplir_page n'écrase jamais un champ déjà rempli, donc sans risque de « combattre »
            # une saisie manuelle en cours.
            if fournisseur == "Free":
                debut = time.monotonic()
                while time.monotonic() - debut < SURVEILLANCE_DUREE_MAX_S:
                    try:
                        page.wait_for_timeout(SURVEILLANCE_INTERVALLE_MS)
                        if page.is_closed():
                            break
                        _remplir_page(page, fournisseur, payload["donnees"])
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
        JOURNAL.info("Fenêtre fermée — fin.")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--run":
        try:
            _executer(sys.argv[2])
        except Exception:
            _configurer_journal()
            JOURNAL.error("Échec fatal de _executer :\n%s", traceback.format_exc())
            raise
