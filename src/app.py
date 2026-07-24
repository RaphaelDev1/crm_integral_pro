# ==============================================================================
#  IA CONSEIL — CRM INTÉGRAL PRO  (Télécom · Énergie · Abonnements)
#  Logiciel interne pour conseillers — accompagnement client de A à Z
#
#  ÉTAPE 1 — Fondations solides :
#    ✅ Mode WAL SQLite, comptes nominatifs, rôles, traçabilité, sécurité SQL
#
#  ÉTAPE 2 — Fiabiliser l'existant :
#    ✅ Bug critique : st.rerun() manquant fin étape 5 (page bloquée après création client)
#    ✅ Bug : generer_ref() pouvait produire des doublons en accès concurrent
#    ✅ Bug : abonnements — calcul économie ignorait le coût client réel
#    ✅ Validation email + téléphone avant enregistrement
#    ✅ safe_float() — conversions numériques protégées, plus de crash
#    ✅ Spinner sur les opérations lentes (comparaison, PDF)
#    ✅ Filtre par statut sur la page Prospects
#    ✅ Confirmation avant suppression prospect / client
#    ✅ Affichage propre quand la recherche client ne retourne rien
#    ✅ Notes auto enrichies à la création
#
#  ÉTAPE 3 — Améliorations fonctionnelles :
#    ✅ Tableau de bord — relances triées par vraie date (retard/jour/à venir)
#    ✅ Export Excel des listes Prospects et Clients
#    ✅ Historique des actions sur la fiche client (qui a fait quoi, quand)
#
#  ÉTAPE 4 — Découpage en modules (maintenabilité) :
#    ✅ constants.py       — options/listes métier
#    ✅ utils.py           — helpers génériques (validation, export Excel, refs)
#    ✅ db.py              — connexion SQLite, schéma, migrations, audit trail
#    ✅ auth.py            — hash de mots de passe, comptes utilisateurs
#    ✅ prospects_engine.py, clients_engine.py, contrats_engine.py, offres_engine.py
#    ✅ pdf_engine.py      — lecture facture/speedtest + génération PDF de restitution
#    ✅ email_engine.py    — envoi SMTP + gabarit HTML du bilan
#    → app.py ne contient plus que la session Streamlit, la navigation et les pages.
#
#  Lancement :
#     pip install streamlit pandas PyPDF2 fpdf2 openpyxl
#     streamlit run app.py
#
#  Identifiants par défaut (premier lancement) :
#     Login : admin   /   Mot de passe : Admin2026!
#     → À changer immédiatement dans Admin > Utilisateurs
# ==============================================================================

import base64
import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from constants import (
    DEBITS_OPTIONS, LISTE_OPERATEURS_TEL, LISTE_FOURNISSEURS_ENERGIE,
    LISTE_TECHNO, LISTE_TECHNO_MOBILE, SATISFACTION_RESEAU,
    UNIVERS, CATEGORIES_TELECOM, CATEGORIES_ENERGIE, CATEGORIES_ABO,
    SERVICE_PRINCIPAL, ROLES, STATUTS_FACTURE,
    SENTINEL_NON_RENSEIGNE, SATISFACTION_RESEAU_OBLIGATOIRE, LISTE_OPERATEURS_TEL_OBLIGATOIRE,
)

# Seuils indicatifs (€/mois) au-delà desquels on avertit d'une possible erreur de saisie
# dans le catalogue d'offres (ex. 777 € pour un forfait mobile) — non bloquant.
SEUIL_PRIX_SUSPECT = {"Télécom": 150.0, "Énergie": 500.0, "Abonnements": 100.0}
from utils import (
    safe_float, valider_email, valider_telephone, parser_date_relance, exporter_excel,
    generer_ref, construire_lien_affilie, economie_totale_groupee, cout_total_mensuel, OPENPYXL_OK,
)
from db import (
    initialiser_bdd, enregistrer_action, lire_historique, lire_parametre, ecrire_parametre,
    recherche_fts,
)
from auth import (
    hash_password, creer_utilisateur, creer_admin_par_defaut,
    authentifier_utilisateur, authentifier_avec_limite,
    lire_utilisateurs, maj_utilisateur, supprimer_utilisateur,
)
import jwt_auth
import secrets_config

if secrets_config.sentry_dsn():
    import sentry_sdk
    sentry_sdk.init(dsn=secrets_config.sentry_dsn(), traces_sample_rate=0.1)

# CRUD prospects/clients/contrats/offres + diagnostic : passe par l'API CRM interne
# (crm_api.py, Roadmap 4.3) avec repli automatique et transparent sur un accès direct
# à la base si l'API n'est pas démarrée — cf. api_client.py pour le détail du repli.
from api_client import (
    ajouter_prospect, lire_prospects, maj_prospect, supprimer_prospect,
    ajouter_client, lire_clients, maj_client, supprimer_client,
    ajouter_contrat, lire_contrats_client, maj_contrat, supprimer_contrat, lire_contrats_prospect,
    transferer_contrats_dossier_vers_client,
    ajouter_offre, lire_offres, maj_offre, supprimer_offre,
    creer_dossier, lire_dossiers_client, envoyer_lien_client, obtenir_briefing_client, analyser_facture_client,
    obtenir_dossier, obtenir_timeline_dossier, ajouter_note_dossier,
    obtenir_mandat_honoraires, creer_mandat_honoraires, marquer_signe_honoraires,
    lister_demarches, creer_demarche, generer_demarche, envoyer_demarche,
    renseigner_champs_demarche, demarche_document_url,
    ApiIndisponible,
    comparer_offres, construire_recommandations,
)
from prospects_engine import (
    widget_relance, recalculer_scores_prospects, indicateur_score, creer_token_documents,
    expliquer_score_prospect, cout_reference_categorie, CATEGORIE_PAR_SERVICE_PRINCIPAL,
)
from notifications import envoyer_demande_documents_prospect
from clients_engine import note_couverture_par_zone, meilleur_debit_par_zone, widget_relance_client
from contrats_engine import lire_contrats_echeance, ETAPES_CONTRAT, STATUT_CONTRAT_INITIAL
from offres_engine import inserer_offres_demo
from pdf_engine import (
    lire_pdf, analyser_facture, analyser_facture_vision, analyser_speedtest_pdf,
    generer_pdf_restitution, generer_pdf_teaser, generer_pdf_devis, generer_pdf_mandat,
    construire_apercu_pdf_prospect, FPDF_OK, ANTHROPIC_OK,
)
from sms_engine import envoyer_sms

# Analyse facture par LLM (backend/services/facture_analyzer.py, Claude Haiku,
# ~95%+ de précision) — remplace le repli regex ci-dessus (analyser_facture,
# ~60%) pour les champs opérateur/prix/data quand une clé API est disponible.
# `backend` est un package frère de `src/`, absent de sys.path par défaut
# quand `streamlit run app.py` est lancé depuis src/.
import sys as _sys
from pathlib import Path as _Path

_REPO_ROOT = _Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

try:
    from backend.services.facture_analyzer import (
        analyser_facture as analyser_facture_llm, FactureAnalyzerError,
    )
    FACTURE_LLM_OK = True
except Exception:
    FACTURE_LLM_OK = False
from email_engine import (
    envoyer_email, construire_corps_email, construire_corps_email_teaser,
    construire_corps_email_fin_engagement,
)
from souscription_engine import construire_donnees_client, lancer_souscription
from facturation_engine import (
    creer_facture, lire_factures, changer_statut, marquer_mandat_signe, lier_facture_a_client,
)
from veille_prix_engine import (
    ajouter_source, lire_sources, maj_source, supprimer_source, lancer_veille,
    lire_historique_prix, lire_alertes, valider_alerte, rejeter_alerte, PLAYWRIGHT_OK,
)
from catalogue_engine import (
    ajouter_source_catalogue, lire_sources_catalogue, maj_source_catalogue,
    supprimer_source_catalogue, ingerer_source, lire_offres_staging,
    valider_offre_staging, rejeter_offre_staging,
)
from audit_agent import lancer_audit, valider_audit_result

st.set_page_config(page_title="IA Conseil - CRM Intégral Pro", layout="wide")

# ==============================================================================
#  POLISH VISUEL GLOBAL — cohérence des cartes/boutons/metrics sur tout l'app
#  (couleurs de base définies dans .streamlit/config.toml, [theme])
# ==============================================================================
st.markdown("""
<style>
/* Cartes (st.container(border=True)) : coins arrondis, ombre légère, respiration */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
/* Metrics : valeurs plus affirmées */
div[data-testid="stMetric"] {
    background: #F4F6F9;
    border-radius: 10px;
    padding: 0.6rem 0.9rem;
}
div[data-testid="stMetricValue"] {
    font-size: 1.4rem;
}
/* Boutons : coins arrondis cohérents, transition douce au survol */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    border-radius: 8px;
    transition: filter 0.15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
    filter: brightness(0.96);
}
/* Titres de section un peu plus espacés visuellement du contenu qui suit */
h4, h5 {
    margin-top: 0.4rem;
}
/* Onglets de navigation (sidebar radio) : espacement plus clair */
section[data-testid="stSidebar"] div[role="radiogroup"] label {
    padding: 0.15rem 0;
}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
#  INITIALISATION BDD + COMPTE ADMIN PAR DÉFAUT (premier lancement)
# ==============================================================================
initialiser_bdd()
_admin_mdp_genere = creer_admin_par_defaut()   # mot de passe en clair si compte créé, sinon None

# ==============================================================================
#  SESSION STATE & VALEURS PAR DÉFAUT
# ==============================================================================
DEFAUTS = {
    # Authentification (NOUVEAU Étape 1)
    "auth_logged_in":   False,
    "auth_user_id":     None,
    "auth_username":    "",
    "auth_nom_complet": "",
    "auth_role":        "Lecture",
    "auth_doit_changer_mdp": False,
    "api_token":        None,   # JWT pour l'API CRM interne (crm_api.py), cf. api_client.py
    # Navigation
    "menu": "📊 Tableau de bord",
    # Config
    "smtp_config": {"serveur": "", "port": 587, "user": "", "mdp": "", "expediteur": ""},
    "nom_societe": "IA CONSEIL",
    # Wizard diagnostic
    "w_etape": 1,
    "w_univers": ["Télécom"],
    "w_service_principal": "Mobile uniquement",
    "w_type_client": "Particulier",
    "w_prenom": "", "w_nom": "", "w_tel": "", "w_email": "", "w_cp": "", "w_ville": "", "w_adresse": "",
    "w_tel_operateur": "", "w_tel_cout": 0.0, "w_tel_data": "",
    "w_tel_techno": "FIBRE", "w_tel_offre": "", "w_tel_debit": DEBITS_OPTIONS[0],
    "w_sat_reseau": "", "w_veut_rester": False,
    "w_speed_down": 0.0, "w_speed_up": 0.0,
    "w_lignes_multi": [],
    "w_ener_fournisseur": "Autre / Aucun", "w_ener_cout_elec": 0.0, "w_ener_cout_gaz": 0.0,
    "w_abos": [],
    "facture_data": {},
}
for k, v in DEFAUTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Recharge la config SMTP/société — .env en priorité, repli sur la base (persistée
# par Admin > Email) — sans quoi elle serait perdue à chaque redémarrage et
# inutilisable par le script notifications.py. Cf. secrets_config.py.
if "smtp_config_loaded" not in st.session_state:
    st.session_state.smtp_config = secrets_config.smtp_config()
    st.session_state.nom_societe = lire_parametre("nom_societe", st.session_state.nom_societe)
    st.session_state.smtp_config_loaded = True


def peut_modifier() -> bool:
    return st.session_state.get("auth_role") in ("Conseiller", "Admin")


def est_admin() -> bool:
    return st.session_state.get("auth_role") == "Admin"


_RE_TEL_OPERATEURS = re.compile(
    r"you\s*price|orange|sosh|sfr|red\s*(?:by|sfr)?|bouygues|b\s*&\s*you|free|proxymity", re.I)
_RE_ENERGIE_FOURNISSEURS = re.compile(
    r"\bedf\b|engie|gdf|total\s*energies|total\s*direct|\beni\b|vattenfall|ekwateur|ekwatour", re.I)


def _enrichir_via_llm_facture(data: dict, contenu_pdf: bytes, api_key: str) -> dict:
    """Complète `data` (issu du repli regex `analyser_facture()`) avec les champs
    opérateur/prix/data extraits par le service LLM `backend/services/
    facture_analyzer.py` (Claude Haiku, ~95%+ de précision contre ~60% pour le
    regex). L'identité client (prénom/nom/tél/email/cp/ville) — non couverte
    par ce service — reste celle du regex. En cas d'échec (clé absente,
    fichier illisible, réponse LLM inexploitable), `data` est renvoyé
    inchangé : le repli regex reste la donnée affichée."""
    if not FACTURE_LLM_OK:
        return data
    import os
    import tempfile

    fd, chemin_tmp = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(contenu_pdf)
        brut = analyser_facture_llm(chemin_tmp, api_key=api_key)
    except FactureAnalyzerError:
        return data
    finally:
        os.unlink(chemin_tmp)

    operateur = brut["operateur"]
    if operateur:
        if _RE_TEL_OPERATEURS.search(operateur):
            data["operateur"] = operateur
        elif _RE_ENERGIE_FOURNISSEURS.search(operateur):
            data["fournisseur"] = operateur
    if brut["prix_ttc"] > 0:
        data["prix"] = brut["prix_ttc"]
    if brut["data_conso_go"] > 0:
        data["data_go"] = str(brut["data_conso_go"])
    return data


def _cout_reference_actuel(oi: dict, p) -> float | None:
    """Coût actuel de référence pour recalculer à la volée l'économie d'une offre
    « intéressait le client » — délègue à prospects_engine.cout_reference_categorie (Télécom :
    coût mensuel actuel du profil UNIQUEMENT si l'offre correspond au service principal
    déclaré, sinon un contrat existant du prospect dans la même catégorie, sinon aucune base
    de comparaison connue ; Énergie : coût élec/gaz du profil ; Abonnements : coût de
    l'abonnement correspondant). Sans ce recalcul, l'économie affichée resterait figée à sa
    valeur du moment de la sélection initiale même si le profil est mis à jour depuis (ex.
    après réception de la facture réelle, ou ajout d'un contrat par le conseiller)."""
    contrats_prospect = None
    if oi.get("univers") == "Télécom":
        contrats_prospect = lire_contrats_prospect(int(p["id"]))
        if not contrats_prospect.empty and "type_contrat" in contrats_prospect.columns:
            # Un dossier en cours (type_contrat='dossier_cmr') est la NOUVELLE offre en cours
            # de vente, pas un service déjà souscrit ailleurs — l'exclure de la base de
            # comparaison, sous peine de calculer une économie contre notre propre offre.
            contrats_prospect = contrats_prospect[contrats_prospect["type_contrat"] != "dossier_cmr"]
    return cout_reference_categorie(oi, p, contrats_prospect)


def bouton_pre_remplir(offre: dict, personne, entite_type: str, entite_id: int, key: str):
    """Bouton « Pré-remplir la souscription » unifié — toujours affiché dès qu'un lien de
    souscription existe (au lieu d'être masqué silencieusement pour les fournisseurs non
    supportés par l'automatisation Playwright, cf. OPERATEURS_SUPPORTES) : le message clair déjà
    renvoyé par `lancer_souscription` (non disponible pour ce fournisseur) s'affiche alors."""
    if not peut_modifier() or not offre.get("url_souscription"):
        return
    if st.button("🖊️ Pré-remplir la souscription", key=key):
        donnees = construire_donnees_client(personne)
        ok, msg = lancer_souscription(
            offre.get("fournisseur"), offre.get("url_souscription", ""), donnees,
            code_affiliation=offre.get("code_affiliation", ""),
            entite_type=entite_type, entite_id=entite_id,
            nom_offre=offre.get("nom") or offre.get("nom_offre", ""),
        )
        (st.success if ok else st.warning)(msg)


@st.dialog("🔍 Détails du prospect")
def _dialog_details_prospect(p):
    """Infos secondaires de la fiche prospect, déplacées ici pour ne garder en accès direct
    que l'essentiel (nom/prénom/tél/email/coût total/économie) — cf. bloc principal de la
    fiche prospect."""
    st.markdown(f"**{p['prenom']} {p['nom']}**")
    if "score" in p and p["score"] is not None:
        st.markdown(f"**Priorité de relance :** {indicateur_score(safe_float(p['score']))} "
                    f"(score {safe_float(p['score']):.0f})")
        with st.expander("ℹ️ Comment ce score est calculé ?"):
            for ligne in expliquer_score_prospect(p):
                st.markdown(f"- {ligne}")
    d1, d2 = st.columns(2)
    d1.write(f"**Opérateur :** {p['operateur_actuel']}")
    d1.write(f"**Offre actuelle :** {p['offre_actuelle']}")
    d1.write(f"**Coût actuel (télécom) :** {p['cout_mensuel_actuel']} €/mois")
    d1.write(f"**Débits :** ⬇️ {p['speed_down']} / ⬆️ {p['speed_up']} Mbps")
    d2.write(f"**Satisfaction réseau :** {p['satisfaction_reseau']}")
    d2.write(f"**Veut rester :** {p['veut_rester']}")
    d2.write(f"**Adresse :** {p.get('adresse') or '—'}")
    d2.write(f"**Ville :** {p.get('ville','')} ({p.get('code_postal','')})")
    st.write(f"**Statut :** {p.get('statut') or '—'}  ·  "
             f"**Prochaine relance :** {p.get('date_relance') or '—'}"
             + (f"  ·  **Fin d'engagement :** {p.get('date_fin_engagement')}"
                if p.get('date_fin_engagement') else ""))
    if p.get("cree_par"):
        st.caption(f"Créé par : **{p['cree_par']}** le {p.get('date_creation')}")
    if p.get("lignes_multi") and p["lignes_multi"] not in ("[]", None):
        with st.expander("Lignes supplémentaires"):
            try:    st.json(json.loads(p["lignes_multi"]))
            except Exception: st.write(p["lignes_multi"])


CHAMPS_PROSPECT_VERS_CLIENT = (
    "ref","prenom","nom","telephone","email","code_postal","ville","adresse","type_client",
    "operateur_actuel","techno","data_go","offre_actuelle","cout_mensuel_actuel",
    "satisfaction_reseau","veut_rester","speed_down","speed_up",
    "fournisseur_energie","cout_elec","cout_gaz","economie_estimee_an","notes",
)


def creer_dossier_prospect_ui(p_row, key_prefix: str, moi: str) -> bool:
    """Affiche la sélection des offres « intéresse le client » à reprendre comme dossier
    (contrats rattachés au prospect, type_contrat='dossier_cmr', suivis via ETAPES_CONTRAT) —
    le prospect devient client automatiquement une fois le dossier signé (statut "Actif"), cf.
    finaliser_conversion_client. Renvoie True quand le dossier est créé (à l'appelant de faire
    le st.rerun())."""
    pid = int(p_row["id"])
    try:
        offres_int = json.loads(p_row.get("offres_interet") or "[]")
    except Exception:
        offres_int = []

    st.markdown("**Sélectionnez les offres réellement retenues pour ce dossier :**")
    contrats_a_creer = []
    if not offres_int:
        st.caption("Aucune offre cochée « Intéresse le client » sur ce prospect — cochez-en "
                    "dans « Modifier les offres qui intéressent le client » avant de créer un dossier.")
    for i, o in enumerate(offres_int):
        with st.container(border=True):
            ch = st.checkbox(
                f"{o.get('univers','')} – {o.get('categorie','')} : {o.get('nom','')} ({o.get('fournisseur','')})",
                value=True, key=f"{key_prefix}_ch_{pid}_{i}")
            cc1, cc2 = st.columns(2)
            prix = cc1.number_input(
                "Coût mensuel (€)", min_value=0.0,
                value=float(o.get("prix_mensuel", 0) or 0), step=1.0,
                key=f"{key_prefix}_prix_{pid}_{i}")
            cout_ref = _cout_reference_actuel(o, p_row)
            eco_prefill = (round((cout_ref - safe_float(o.get("prix_mensuel"))), 2)
                           if cout_ref is not None else 0.0)
            eco = cc2.number_input(
                "Économie mensuelle (€)", min_value=0.0,
                value=max(0.0, eco_prefill), step=1.0,
                key=f"{key_prefix}_eco_{pid}_{i}",
                help=None if cout_ref is not None else
                     "Coût actuel inconnu pour ce service — économie non calculable, "
                     "saisissez-la manuellement si vous la connaissez.")
            if ch:
                contrats_a_creer.append({
                    "univers": o.get("univers"), "categorie": o.get("categorie"),
                    "fournisseur": o.get("fournisseur"), "nom_offre": o.get("nom"),
                    "cout_mensuel": prix, "economie_mensuelle": eco,
                    "cree_par": moi,
                })

    if offres_int and not contrats_a_creer:
        st.caption("Cochez au moins une offre pour créer un dossier.")
    if contrats_a_creer and st.button(
            "🚀 Créer le dossier", key=f"{key_prefix}_confirm_{pid}", type="primary"):
        for ct in contrats_a_creer:
            ajouter_contrat({**ct, "prospect_id": pid, "type_contrat": "dossier_cmr",
                              "statut_contrat": STATUT_CONTRAT_INITIAL,
                              "notes": "Dossier créé depuis les offres retenues"})
        enregistrer_action("prospect", pid, "Dossier créé",
                            f"{len(contrats_a_creer)} offre(s) retenue(s)", auteur=moi)
        return True
    return False


def finaliser_conversion_client(pid: int, moi: str):
    """Finalise un prospect en client une fois son dossier signé (un de ses contrats
    'dossier_cmr' passe au statut "Actif") : copie ses infos vers un nouveau client, migre les
    contrats de dossier vers ce client et nettoie les contrats de référence devenus inutiles
    (cf. transferer_contrats_dossier_vers_client), puis supprime la fiche prospect. Renvoie le
    nouvel id client, ou None si le prospect est introuvable."""
    dfp   = lire_prospects()
    match = dfp[dfp["id"] == pid]
    if match.empty:
        return None
    p_row = match.iloc[0]
    d = {k: p_row.get(k, "") for k in CHAMPS_PROSPECT_VERS_CLIENT}
    d["cree_par"] = moi
    cid_nv = ajouter_client(d)
    transferer_contrats_dossier_vers_client(pid, cid_nv)
    enregistrer_action("client", cid_nv, "Conversion automatique prospect→client",
                        f"Dossier signé — depuis prospect #{pid} "
                        f"({p_row.get('prenom','')} {p_row.get('nom','')})")
    lier_facture_a_client(pid, cid_nv)
    supprimer_prospect(pid)
    return cid_nv


def _widget_etape_dossier(ctid: int, statut_actuel: str, key_prefix: str, on_transition=None):
    """Affiche la progression ETAPES_CONTRAT d'un contrat (bouton étape suivante + correction
    manuelle/résiliation). `on_transition(nouveau_statut)`, si fourni, est appelé juste après
    chaque changement de statut et doit renvoyer True s'il a déjà géré message + st.rerun()
    lui-même (cas de la conversion automatique prospect→client à l'étape "Actif") — sinon ce
    helper affiche un message générique et fait le st.rerun()."""
    statut_actuel = statut_actuel or STATUT_CONTRAT_INITIAL
    if statut_actuel in ETAPES_CONTRAT:
        idx_etape = ETAPES_CONTRAT.index(statut_actuel)
        st.caption(f"Étape actuelle : **{statut_actuel}**")
        if idx_etape < len(ETAPES_CONTRAT) - 1:
            prochaine_etape = ETAPES_CONTRAT[idx_etape + 1]
            if st.button(f"➡️ {prochaine_etape}", key=f"{key_prefix}_next_{ctid}"):
                maj_contrat(int(ctid), "statut_contrat", prochaine_etape)
                gere = on_transition(prochaine_etape) if on_transition else False
                if not gere:
                    st.success(f"Étape mise à jour : {prochaine_etape}."); st.rerun()
        else:
            st.success("✅ Contrat actif.")
    else:
        st.caption(f"Statut actuel : **{statut_actuel}**")
    with st.expander(f"Corriger l'étape manuellement / résilier (#{ctid})"):
        options_statut = ETAPES_CONTRAT + ["Résilié"]
        nv_statut = st.selectbox(
            "Statut du contrat", options_statut,
            index=options_statut.index(statut_actuel) if statut_actuel in options_statut else 0,
            key=f"{key_prefix}_statut_{ctid}")
        if st.button("Appliquer ce statut", key=f"{key_prefix}_force_{ctid}"):
            maj_contrat(int(ctid), "statut_contrat", nv_statut)
            gere = on_transition(nv_statut) if (on_transition and nv_statut == "Actif") else False
            if not gere:
                st.success("Statut mis à jour."); st.rerun()


def _on_transition_dossier_prospect(nouveau_statut: str, pid: int, prenom_nom: str, moi: str) -> bool:
    """on_transition à passer à _widget_etape_dossier pour un dossier côté prospect : dès que le
    statut atteint "Actif", finalise la conversion en client et redirige vers sa fiche."""
    if nouveau_statut != "Actif":
        return False
    cid_nv = finaliser_conversion_client(pid, moi)
    if cid_nv is None:
        return False
    st.success(f"🎉 Dossier signé — {prenom_nom} est maintenant client (#{cid_nv}) !")
    st.balloons()
    st.session_state["_focus_client_id"] = cid_nv
    st.session_state.menu = "👥 Clients & contrats"
    st.rerun()
    return True


def _recos_post_paiement(facture: dict):
    """Reconstruit les recommandations à restituer une fois le devis payé : depuis les
    offres « intéresse le client » du prospect s'il existe encore, sinon depuis les
    contrats du client (cas où le prospect a déjà été converti). Renvoie
    (personne_dict, recommandations) ou (None, []) si rien à restituer."""
    if facture.get("prospect_id"):
        dfp   = lire_prospects()
        match = dfp[dfp["id"] == facture["prospect_id"]]
        if not match.empty:
            p = match.iloc[0]
            try:
                offres_int = json.loads(p.get("offres_interet") or "[]")
            except Exception:
                offres_int = []
            if offres_int:
                recos = []
                for o in offres_int:
                    cout_ref = _cout_reference_actuel(o, p)
                    if cout_ref is not None:
                        cout_actuel = cout_ref
                        offre = {**o, "economie_annuelle":
                                 round((cout_ref - safe_float(o.get("prix_mensuel"))) * 12, 2)}
                    else:
                        # Pas de base de comparaison connue pour ce service (ex. Box proposée
                        # à un prospect Mobile uniquement, sans contrat Box connu) — mieux vaut
                        # ne rien afficher que restituer une économie calculée contre un coût
                        # sans rapport avec ce service, cf. cout_reference_categorie.
                        cout_actuel = 0
                        offre = {**o, "economie_annuelle": 0}
                    recos.append({"univers": o.get("univers"), "categorie": o.get("categorie"),
                                   "cout_actuel": cout_actuel, "offre": offre})
                return p.to_dict(), recos
    if facture.get("client_id"):
        dfc   = lire_clients()
        match = dfc[dfc["id"] == facture["client_id"]]
        if not match.empty:
            cl       = match.iloc[0]
            contrats = lire_contrats_client(int(facture["client_id"]))
            recos = [{"univers": ct["univers"], "categorie": ct["categorie"],
                      "cout_actuel": cl.get("cout_mensuel_actuel", 0),
                      "offre": {"nom": ct["nom_offre"], "fournisseur": ct["fournisseur"],
                                "caracteristiques": "", "prix_mensuel": ct["cout_mensuel"],
                                "economie_annuelle": round((ct["economie_mensuelle"] or 0) * 12, 2)}}
                     for _, ct in contrats.iterrows()]
            return cl.to_dict(), recos
    return None, []


# ==============================================================================
#  BARRE LATÉRALE — LOGIN NOMINATIF
# ==============================================================================
with st.sidebar:
    st.title("📡 IA Conseil")
    st.caption("CRM Intégral Pro — usage interne")

    if not st.session_state.auth_logged_in:
        # ---- Formulaire de connexion ----
        st.markdown("### 🔐 Connexion")
        login_u = st.text_input("Identifiant", key="sidebar_username")
        login_p = st.text_input("Mot de passe", type="password", key="sidebar_password")
        if st.button("Se connecter", type="primary", use_container_width=True):
            ip = str(st.context.ip_address or "")
            user, err = authentifier_avec_limite(login_u, login_p, ip)
            if user:
                st.session_state.auth_logged_in   = True
                st.session_state.auth_user_id     = user["id"]
                st.session_state.auth_username    = user["username"]
                st.session_state.auth_nom_complet = user["nom_complet"]
                st.session_state.auth_role        = user["role"]
                st.session_state.auth_doit_changer_mdp = bool(user.get("doit_changer_mdp"))
                # Jeton JWT émis localement (sans appel réseau) pour authentifier les
                # appels api_client.py vers l'API CRM interne au nom de cet utilisateur.
                st.session_state.api_token        = jwt_auth.creer_token(user)
                st.rerun()
            else:
                st.error(err)
    else:
        # ---- Utilisateur connecté ----
        st.markdown(f"**👤 {st.session_state.auth_nom_complet}**")
        st.caption(f"Rôle : {st.session_state.auth_role}")
        if st.button("🚪 Se déconnecter", use_container_width=True):
            for k in ["auth_logged_in","auth_user_id","auth_username","auth_nom_complet","auth_role",
                      "auth_doit_changer_mdp","api_token"]:
                st.session_state[k] = DEFAUTS[k]
            st.session_state.menu = "📊 Tableau de bord"
            st.rerun()

        st.divider()
        options_menu = ["📊 Tableau de bord", "🧭 Nouveau diagnostic",
                        "📇 Prospects", "👥 Clients & contrats", "🧾 Facturation", "🛠️ Admin"]
        st.session_state.menu = st.radio(
            "Navigation", options_menu,
            index=options_menu.index(st.session_state.menu)
                  if st.session_state.menu in options_menu else 0
        )
        st.divider()
        df_p = lire_prospects(); df_c = lire_clients()
        moi  = st.session_state.auth_nom_complet
        mes_p = df_p[df_p["cree_par"] == moi] if not df_p.empty and "cree_par" in df_p.columns else df_p
        st.metric("Mes prospects", len(mes_p))
        a_relancer = len(mes_p[mes_p["statut"] == "À relancer"]) if not mes_p.empty and "statut" in mes_p.columns else 0
        st.metric("À relancer", a_relancer, delta="⚠️" if a_relancer > 0 else "✅ 0")
        mes_c = df_c[df_c["cree_par"] == moi] if not df_c.empty and "cree_par" in df_c.columns else df_c
        st.metric("Mes clients", len(mes_c))


# ==============================================================================
#  GARDE : tout le reste nécessite d'être connecté
# ==============================================================================
if not st.session_state.auth_logged_in:
    st.title("🔐 Connexion requise")
    st.info("Veuillez vous identifier via le panneau à gauche.")
    if _admin_mdp_genere:
        st.warning(
            "**Premier lancement détecté.** Un compte administrateur a été créé automatiquement :\n\n"
            "- Identifiant : `admin`\n"
            f"- Mot de passe (généré, à noter maintenant) : `{_admin_mdp_genere}`\n\n"
            "⚠️ Ce mot de passe ne sera plus jamais réaffiché. Le changement sera exigé "
            "dès la première connexion."
        )
    st.stop()

# ── Changement de mot de passe obligatoire (premier login admin, ou forcé par un
#    administrateur) — bloque tout accès au reste de l'application tant que ce
#    n'est pas fait. ──────────────────────────────────────────────────────────
if st.session_state.auth_doit_changer_mdp:
    st.title("🔒 Changement de mot de passe requis")
    st.warning("Vous devez définir un nouveau mot de passe avant de continuer.")
    npwd1 = st.text_input("Nouveau mot de passe", type="password", key="force_pwd_1")
    npwd2 = st.text_input("Confirmer le nouveau mot de passe", type="password", key="force_pwd_2")
    if st.button("Valider", type="primary"):
        if len(npwd1) < 8:
            st.error("Le mot de passe doit faire au moins 8 caractères.")
        elif npwd1 != npwd2:
            st.error("Les deux mots de passe ne correspondent pas.")
        else:
            maj_utilisateur(st.session_state.auth_user_id, "password_hash", hash_password(npwd1))
            maj_utilisateur(st.session_state.auth_user_id, "doit_changer_mdp", 0)
            st.session_state.auth_doit_changer_mdp = False
            st.success("Mot de passe mis à jour.")
            st.rerun()
    st.stop()

menu = st.session_state.menu


def _table_cliquable_vers_fiche(df_avec_id, cols_affiches, key, menu_cible, session_key_focus, id_col="id"):
    """Affiche un tableau où cliquer sur une ligne ouvre la fiche détaillée
    correspondante (bascule vers `menu_cible`, en mémorisant l'id de la ligne
    cliquée — colonne `id_col` — dans `session_key_focus` pour que la fiche
    présélectionne l'enregistrement)."""
    if df_avec_id.empty:
        st.caption("Aucune")
        return
    cols_visibles = [c for c in cols_affiches if c != id_col]
    evt = st.dataframe(df_avec_id[cols_visibles], hide_index=True, use_container_width=True,
                        on_select="rerun", selection_mode="single-row", key=key)
    lignes = evt.selection.rows if evt and evt.selection else []
    if lignes:
        st.session_state[session_key_focus] = int(df_avec_id.iloc[lignes[0]][id_col])
        st.session_state.menu = menu_cible
        st.rerun()


def _champs_obligatoires_identite() -> dict:
    """Champs obligatoires de l'étape 2 (coordonnées client) — {libellé: valeur}."""
    return {
        "Prénom":    st.session_state.w_prenom.strip(),
        "Nom":       st.session_state.w_nom.strip(),
        "Téléphone": st.session_state.w_tel.strip(),
        "Email":     st.session_state.w_email.strip(),
    }


def _champs_obligatoires_telecom() -> dict:
    """Champs obligatoires de l'étape 3 pour le bloc Télécom — {libellé: valeur}
    — vide si l'univers Télécom n'a pas été coché à l'étape 1 (rien à exiger)."""
    if "Télécom" not in st.session_state.w_univers:
        return {}
    champs = {
        "Opérateur actuel":             st.session_state.w_tel_operateur,
        "Coût mensuel actuel":          st.session_state.w_tel_cout if safe_float(st.session_state.w_tel_cout) > 0 else "",
        "Satisfaction réseau (réelle)": st.session_state.w_sat_reseau,
    }
    if st.session_state.w_service_principal != "Box / Fibre uniquement":
        champs["Data mobile minimum (Go)"] = str(st.session_state.w_tel_data).strip()
    return champs


@st.dialog("➕ Ajouter une ligne supplémentaire")
def _dialog_ajouter_ligne_multi():
    """Popup d'ajout d'une ligne multi-lignes (ex. ligne du conjoint) — sorti du
    corps de l'étape 3 du diagnostic pour ne pas encombrer/embrouiller l'écran
    principal avec un mini-formulaire complet en permanence affiché."""
    ml_label  = st.text_input("Libellé (ex: Ligne épouse)", key="ml_label")
    ml_op     = st.selectbox("Opérateur", LISTE_OPERATEURS_TEL, key="ml_op")
    ml_techno = st.selectbox("Techno", LISTE_TECHNO, key="ml_techno")
    ml_data   = st.text_input("Data nécessaire (Go)", key="ml_data")
    ml_sat    = st.selectbox("Satisfaction", SATISFACTION_RESEAU, key="ml_sat")
    ml_cout   = st.number_input("€/mois", min_value=0.0, step=1.0, key="ml_cout")
    if st.button("➕ Ajouter la ligne", type="primary"):
        if not ml_label:
            st.warning("Le libellé est obligatoire.")
        else:
            st.session_state.w_lignes_multi.append({
                "label": ml_label, "operateur": ml_op, "techno": ml_techno,
                "data": ml_data, "satisfaction": ml_sat, "cout": ml_cout})
            st.rerun()


def _afficher_progression_obligatoire(champs: dict) -> bool:
    """Affiche une barre de progression (%) des champs obligatoires renseignés
    + la liste de ceux qui manquent. Renvoie True si tout est rempli (rien à
    bloquer si `champs` est vide, ex. Télécom non sélectionné)."""
    if not champs:
        return True
    remplis = sum(1 for v in champs.values() if v)
    total   = len(champs)
    pct     = remplis / total
    st.progress(pct, text=f"Informations obligatoires renseignées : {int(pct*100)}% ({remplis}/{total})")
    manquants = [k for k, v in champs.items() if not v]
    if manquants:
        st.warning("⚠️ Obligatoire avant de continuer : " + ", ".join(manquants))
    return not manquants


# ==============================================================================
#  NOUVEAU DIAGNOSTIC
# ==============================================================================
if menu == "🧭 Nouveau diagnostic":
    st.title("🧭 Diagnostic client guidé")
    barre = st.progress(0)

    # ---------- ÉTAPE 1 ----------
    if st.session_state.w_etape == 1:
        barre.progress(0.15)
        st.subheader("Étape 1 — Besoins + import de documents")

        with st.expander("🔄 Reprendre un client existant (pré-remplit la fiche)"):
            df_clients_dispo = lire_clients()
            if df_clients_dispo.empty:
                st.caption("Aucun client enregistré pour l'instant.")
            else:
                ids_clients_dispo = df_clients_dispo["id"].tolist()
                choix_client_dispo = st.selectbox(
                    "Client à reprendre", ids_clients_dispo,
                    format_func=lambda i: (
                        f"{df_clients_dispo[df_clients_dispo['id']==i]['ref'].values[0] or f'#{i}'} — "
                        f"{df_clients_dispo[df_clients_dispo['id']==i]['prenom'].values[0]} "
                        f"{df_clients_dispo[df_clients_dispo['id']==i]['nom'].values[0]} — "
                        f"{df_clients_dispo[df_clients_dispo['id']==i]['telephone'].values[0]}"),
                    key="w_reprise_client_choix")
                if st.button("📥 Charger les informations de ce client"):
                    cl_dispo = df_clients_dispo[df_clients_dispo["id"] == choix_client_dispo].iloc[0]
                    univers_dispo = ["Télécom"]
                    if safe_float(cl_dispo.get("cout_elec")) > 0 or safe_float(cl_dispo.get("cout_gaz")) > 0:
                        univers_dispo.append("Énergie")
                    st.session_state.w_univers          = univers_dispo
                    st.session_state.w_service_principal = (
                        "Box / Fibre uniquement" if cl_dispo.get("techno") in ("FIBRE", "ADSL")
                        else "Mobile uniquement")
                    st.session_state.w_type_client  = cl_dispo.get("type_client") or "Particulier"
                    st.session_state.w_prenom       = cl_dispo.get("prenom") or ""
                    st.session_state.w_nom          = cl_dispo.get("nom") or ""
                    st.session_state.w_tel          = cl_dispo.get("telephone") or ""
                    st.session_state.w_email        = cl_dispo.get("email") or ""
                    st.session_state.w_cp           = cl_dispo.get("code_postal") or ""
                    st.session_state.w_ville        = cl_dispo.get("ville") or ""
                    st.session_state.w_adresse      = cl_dispo.get("adresse") or ""
                    st.session_state.w_tel_operateur = cl_dispo.get("operateur_actuel") or ""
                    st.session_state.w_tel_techno   = cl_dispo.get("techno") or "FIBRE"
                    st.session_state.w_tel_data     = str(cl_dispo.get("data_go") or "")
                    st.session_state.w_tel_offre    = cl_dispo.get("offre_actuelle") or ""
                    st.session_state.w_tel_cout     = safe_float(cl_dispo.get("cout_mensuel_actuel"))
                    st.session_state.w_sat_reseau   = cl_dispo.get("satisfaction_reseau") or ""
                    st.session_state.w_veut_rester  = cl_dispo.get("veut_rester") == "Oui"
                    st.session_state.w_speed_down   = safe_float(cl_dispo.get("speed_down"))
                    st.session_state.w_speed_up     = safe_float(cl_dispo.get("speed_up"))
                    st.session_state.w_ener_fournisseur = cl_dispo.get("fournisseur_energie") or "Autre / Aucun"
                    st.session_state.w_ener_cout_elec   = safe_float(cl_dispo.get("cout_elec"))
                    st.session_state.w_ener_cout_gaz    = safe_float(cl_dispo.get("cout_gaz"))
                    st.success(f"Fiche de {st.session_state.w_prenom} {st.session_state.w_nom} chargée.")
                    st.rerun()

        st.session_state.w_univers = st.multiselect(
            "Univers à analyser :", UNIVERS, default=st.session_state.w_univers)

        if "Télécom" in st.session_state.w_univers:
            st.session_state.w_service_principal = st.radio(
                "Service principal recherché :", SERVICE_PRINCIPAL,
                index=SERVICE_PRINCIPAL.index(st.session_state.w_service_principal),
                horizontal=True)

        st.markdown("##### 📄 Facture — PDF, photo ou scan (optionnel — pré-remplit la fiche)")
        pdf_f = st.file_uploader("Facture Télécom ou Énergie", type=["pdf", "jpg", "jpeg", "png"],
                                  key="pdf_facture")
        if pdf_f is not None:
            api_key   = secrets_config.anthropic_api_key()
            ext       = pdf_f.name.rsplit(".", 1)[-1].lower() if "." in pdf_f.name else ""
            est_image = ext in ("jpg", "jpeg", "png")
            with st.spinner("Analyse de la facture en cours…"):
                data = analyser_facture_vision(pdf_f.getvalue(), pdf_f.name, api_key) if api_key else None
                via_vision = data is not None
                via_llm = False
                if data is None and not est_image:
                    data = analyser_facture(lire_pdf(pdf_f))
                    if api_key:
                        avant = dict(data)
                        data = _enrichir_via_llm_facture(data, pdf_f.getvalue(), api_key)
                        via_llm = data != avant

            if data is None:
                st.error("Analyse impossible pour une image — configurez la clé API Claude "
                          "dans **Admin > 🔍 OCR Vision** pour lire les photos/scans de facture.")
            else:
                st.session_state.facture_data = data
                for src, dst in [("prenom","w_prenom"),("nom","w_nom"),("tel","w_tel"),
                                 ("email","w_email"),("cp","w_cp"),("ville","w_ville")]:
                    if data[src]: st.session_state[dst] = data[src]
                if data["operateur"] != "Autre / Aucun": st.session_state.w_tel_operateur = data["operateur"]
                if data["fournisseur"] != "Autre / Aucun": st.session_state.w_ener_fournisseur = data["fournisseur"]
                if data["prix"] > 0: st.session_state.w_tel_cout = data["prix"]
                if data["data_go"]: st.session_state.w_tel_data = data["data_go"]
                if via_vision:
                    st.success("📸 Facture analysée par IA Vision — champs pré-remplis.")
                elif via_llm:
                    st.success("Facture analysée par IA (extraction structurée) — champs pré-remplis.")
                else:
                    st.success("Facture analysée — champs pré-remplis.")

        st.markdown("##### 📶 Speedtest PDF (optionnel)")
        pdf_s = st.file_uploader("PDF de test de débit (nPerf, Speedtest…)", type=["pdf"], key="pdf_speed")
        if pdf_s is not None:
            d, u = analyser_speedtest_pdf(lire_pdf(pdf_s))
            if d: st.session_state.w_speed_down = d
            if u: st.session_state.w_speed_up   = u
            st.success(f"Débits détectés — ⬇️ {d} Mbps / ⬆️ {u} Mbps")

        if st.button("Commencer ➡️", type="primary"):
            if not st.session_state.w_univers:
                st.warning("Cochez au moins un univers.")
            else:
                st.session_state.w_etape = 2; st.rerun()

    # ---------- ÉTAPE 2 : identité ----------
    elif st.session_state.w_etape == 2:
        barre.progress(0.30)
        st.subheader("Étape 2 — Coordonnées du client")
        st.session_state.w_type_client = st.radio(
            "Type :", ["Particulier", "Professionnel"], horizontal=True,
            index=0 if st.session_state.w_type_client == "Particulier" else 1)
        c1, c2 = st.columns(2)
        st.session_state.w_prenom = c1.text_input("Prénom", st.session_state.w_prenom)
        st.session_state.w_nom    = c2.text_input("Nom",    st.session_state.w_nom)
        st.session_state.w_tel    = c1.text_input("Téléphone", st.session_state.w_tel)
        st.session_state.w_email  = c2.text_input("Email",     st.session_state.w_email)
        st.session_state.w_cp     = c1.text_input("Code postal", st.session_state.w_cp)
        st.session_state.w_ville  = c2.text_input("Ville",       st.session_state.w_ville)
        st.session_state.w_adresse = st.text_input(
            "Adresse (n°, rue, complément — bis, ter…)", st.session_state.w_adresse)
        # Validation en temps réel (non bloquante, juste indicative)
        if st.session_state.w_email and not valider_email(st.session_state.w_email):
            st.warning("⚠️ Format email invalide — vérifiez avant de continuer.")
        if st.session_state.w_tel and not valider_telephone(st.session_state.w_tel):
            st.warning("⚠️ Numéro de téléphone inhabituel — vérifiez.")

        complet_identite = _afficher_progression_obligatoire(_champs_obligatoires_identite())

        a, b = st.columns(2)
        if a.button("⬅️ Retour"):    st.session_state.w_etape = 1; st.rerun()
        if b.button("Suivant ➡️", type="primary"):
            if not complet_identite:
                st.error("Merci de renseigner toutes les informations client obligatoires avant de continuer.")
            else:
                st.session_state.w_etape = 3; st.rerun()

    # ---------- ÉTAPE 3 : situation actuelle ----------
    elif st.session_state.w_etape == 3:
        barre.progress(0.55)
        st.subheader("Étape 3 — Situation actuelle du client")

        if "Télécom" in st.session_state.w_univers:
            with st.container(border=True):
                st.markdown("#### 📱 Télécom")
                box_seule    = st.session_state.w_service_principal == "Box / Fibre uniquement"
                mobile_seul  = st.session_state.w_service_principal == "Mobile uniquement"
                c1, c2 = st.columns(2)
                operateur_choisi = c1.selectbox(
                    "Opérateur actuel *", LISTE_OPERATEURS_TEL_OBLIGATOIRE,
                    index=LISTE_OPERATEURS_TEL_OBLIGATOIRE.index(st.session_state.w_tel_operateur)
                          if st.session_state.w_tel_operateur in LISTE_OPERATEURS_TEL_OBLIGATOIRE else 0)
                st.session_state.w_tel_operateur = "" if operateur_choisi == SENTINEL_NON_RENSEIGNE else operateur_choisi
                techno_options = LISTE_TECHNO_MOBILE if mobile_seul else LISTE_TECHNO
                st.session_state.w_tel_techno = c2.selectbox(
                    "Technologie", techno_options,
                    index=techno_options.index(st.session_state.w_tel_techno)
                          if st.session_state.w_tel_techno in techno_options else 0)
                st.session_state.w_tel_offre = c1.text_input("Offre / forfait actuel", st.session_state.w_tel_offre)
                st.session_state.w_tel_cout  = c2.number_input(
                    "Coût mensuel actuel (€) *", min_value=0.0,
                    value=float(st.session_state.w_tel_cout), step=1.0)

                if box_seule or st.session_state.w_tel_techno in ("FIBRE","ADSL"):
                    st.session_state.w_tel_debit = c1.selectbox(
                        "Bande passante souhaitée", DEBITS_OPTIONS,
                        index=DEBITS_OPTIONS.index(st.session_state.w_tel_debit)
                              if st.session_state.w_tel_debit in DEBITS_OPTIONS else 0)
                else:
                    st.session_state.w_tel_data = c1.text_input(
                        "Data mobile minimum (Go) *", str(st.session_state.w_tel_data),
                        help="La conso data MINIMALE du client, relevée sur sa facture actuelle — "
                             "pour ne jamais lui proposer une offre en dessous et le laisser à court de données.")

                cc1, cc2 = st.columns(2)
                satisfaction_choisie = cc1.selectbox(
                    "Satisfaction réseau (réponse réelle du client) *", SATISFACTION_RESEAU_OBLIGATOIRE,
                    index=SATISFACTION_RESEAU_OBLIGATOIRE.index(st.session_state.w_sat_reseau)
                          if st.session_state.w_sat_reseau in SATISFACTION_RESEAU_OBLIGATOIRE else 0)
                st.session_state.w_sat_reseau = "" if satisfaction_choisie == SENTINEL_NON_RENSEIGNE else satisfaction_choisie
                st.session_state.w_veut_rester = cc2.checkbox(
                    "⚠️ Veut rester chez son opérateur actuel",
                    value=st.session_state.w_veut_rester)

                if st.session_state.w_sat_reseau not in ("", SATISFACTION_RESEAU[0]) and st.session_state.w_ville:
                    couverture = note_couverture_par_zone(st.session_state.w_ville)
                    if not couverture.empty:
                        meilleur = couverture.iloc[0]
                        if meilleur["operateur"] != st.session_state.w_tel_operateur and meilleur["nb_avis"] >= 2:
                            st.info(
                                f"📍 À {st.session_state.w_ville}, **{meilleur['operateur']}** obtient la "
                                f"meilleure satisfaction réseau chez nos clients/prospects "
                                f"({meilleur['note_moyenne']:.1f}/3 sur {int(meilleur['nb_avis'])} avis) — "
                                f"à proposer si le client envisage de changer d'opérateur.")

                    debits_zone = meilleur_debit_par_zone(st.session_state.w_ville)
                    if not debits_zone.empty:
                        meilleur_d = debits_zone.iloc[0]
                        if meilleur_d["operateur"] != st.session_state.w_tel_operateur and meilleur_d["nb_mesures"] >= 2:
                            st.info(
                                f"📶 À {st.session_state.w_ville}, **{meilleur_d['operateur']}** obtient le "
                                f"meilleur débit mesuré chez nos clients/prospects "
                                f"(⬇️ {meilleur_d['debit_down_moyen']} Mbps / ⬆️ {meilleur_d['debit_up_moyen']} Mbps "
                                f"sur {int(meilleur_d['nb_mesures'])} mesures) — "
                                f"à proposer si le client envisage de changer d'opérateur.")

                # Débits : key= (sans value=) pour éviter le bug Streamlit qui oblige
                # à cliquer deux fois sur +/- quand value= et la ré-affectation à la
                # même clé de session_state coexistent.
                d1, d2 = st.columns(2)
                d1.number_input("Débit descendant (Mbps)", min_value=0.0, step=1.0, key="w_speed_down")
                d2.number_input("Débit montant (Mbps)", min_value=0.0, step=1.0, key="w_speed_up")
                if st.session_state.w_speed_down or st.session_state.w_speed_up:
                    st.caption(f"📶 Mesurés : ⬇️ {st.session_state.w_speed_down} Mbps  /  ⬆️ {st.session_state.w_speed_up} Mbps")

                st.markdown("**Lignes supplémentaires (multi-lignes) :**")
                if st.button("➕ Ajouter une ligne supplémentaire", key="btn_open_ligne_multi"):
                    _dialog_ajouter_ligne_multi()
                if st.session_state.w_lignes_multi:
                    total_multi = sum(l["cout"] for l in st.session_state.w_lignes_multi)
                    for i, l in enumerate(st.session_state.w_lignes_multi):
                        cx, cy = st.columns([5, 1])
                        cx.write(f"• **{l['label']}** — {l['operateur']} / {l['techno']} / {l['data']} Go / {l['satisfaction']} — {l['cout']} €/mois")
                        if cy.button("🗑️", key=f"del_ml_{i}"):
                            st.session_state.w_lignes_multi.pop(i); st.rerun()
                    st.info(f"Total multi-lignes : **{round(total_multi,2)} €/mois** ({round(total_multi*12,2)} €/an)")

        if "Énergie" in st.session_state.w_univers:
            with st.container(border=True):
                st.markdown("#### ⚡ Énergie")
                e1, e2, e3 = st.columns(3)
                st.session_state.w_ener_fournisseur = e1.selectbox(
                    "Fournisseur actuel", LISTE_FOURNISSEURS_ENERGIE,
                    index=LISTE_FOURNISSEURS_ENERGIE.index(st.session_state.w_ener_fournisseur)
                          if st.session_state.w_ener_fournisseur in LISTE_FOURNISSEURS_ENERGIE
                          else len(LISTE_FOURNISSEURS_ENERGIE)-1)
                st.session_state.w_ener_cout_elec = e2.number_input(
                    "Élec — €/mois", min_value=0.0, value=float(st.session_state.w_ener_cout_elec), step=1.0)
                st.session_state.w_ener_cout_gaz = e3.number_input(
                    "Gaz — €/mois", min_value=0.0, value=float(st.session_state.w_ener_cout_gaz), step=1.0)

        if "Abonnements" in st.session_state.w_univers:
            with st.container(border=True):
                st.markdown("#### 🎬 Abonnements")
                a1, a2, a3 = st.columns([2, 1, 1])
                abo_nom  = a1.text_input("Nom de l'abonnement", key="abo_nom")
                abo_cout = a2.number_input("€/mois", min_value=0.0, step=1.0, key="abo_cout")
                if a3.button("➕ Ajouter l'abo"):
                    if abo_nom:
                        st.session_state.w_abos.append({"nom": abo_nom, "cout": abo_cout}); st.rerun()
                if st.session_state.w_abos:
                    total_abo = sum(a["cout"] for a in st.session_state.w_abos)
                    for i, a in enumerate(st.session_state.w_abos):
                        cx, cy = st.columns([5, 1])
                        cx.write(f"• {a['nom']} — {a['cout']} €/mois")
                        if cy.button("🗑️", key=f"del_abo_{i}"):
                            st.session_state.w_abos.pop(i); st.rerun()
                    st.info(f"Total abonnements : **{round(total_abo,2)} €/mois** ({round(total_abo*12,2)} €/an)")

        complet_telecom = _afficher_progression_obligatoire(_champs_obligatoires_telecom())

        a, b = st.columns(2)
        if a.button("⬅️ Retour"): st.session_state.w_etape = 2; st.rerun()
        if b.button("🔍 Lancer la comparaison ➡️", type="primary"):
            if not complet_telecom:
                st.error("Merci de renseigner toutes les informations obligatoires avant de lancer la comparaison.")
            else:
                with st.spinner("Analyse en cours…"):
                    st.session_state.w_etape = 4
                st.rerun()

    # ---------- ÉTAPE 4 : RECOMMANDATIONS ----------
    elif st.session_state.w_etape == 4:
        barre.progress(1.0)
        nom_complet = f"{st.session_state.w_prenom} {st.session_state.w_nom}".strip() or "Client"
        st.subheader(f"🎯 Recommandations pour {nom_complet}")

        if st.session_state.w_veut_rester:
            st.warning(f"⚠️ Le client souhaite rester chez **{st.session_state.w_tel_operateur}** — adaptez votre argumentaire.")

        with st.expander("🤖 Audit automatique (agent IA — aide à la décision, sourcé)", expanded=False):
            st.caption(
                "Appelle un agent Claude qui orchestre les mêmes fonctions de comparaison que "
                "ci-dessous (comparer_offres, cout_reference_categorie, couverture_reseau) : "
                "aucun montant n'est calculé par le LLM, chaque chiffre vient d'un outil Python. "
                "Purement informatif — ne coche rien automatiquement, à vous de valider/ajuster "
                "avant restitution."
            )
            if st.button("🤖 Lancer l'audit automatique", key="btn_lancer_audit_auto"):
                situation_audit = {
                    "univers_interesse": st.session_state.w_univers,
                    "service_principal": st.session_state.w_service_principal,
                    "operateur_actuel": st.session_state.w_tel_operateur,
                    "cout_mensuel_actuel": float(st.session_state.w_tel_cout) +
                                           sum(l["cout"] for l in st.session_state.w_lignes_multi),
                    "satisfaction_reseau": st.session_state.w_sat_reseau,
                    "data_go": st.session_state.w_tel_data,
                    "veut_rester": st.session_state.w_veut_rester,
                    "ville": st.session_state.w_ville,
                    "cout_elec": st.session_state.w_ener_cout_elec,
                    "cout_gaz": st.session_state.w_ener_cout_gaz,
                    "fournisseur_energie": st.session_state.w_ener_fournisseur,
                    "abonnements": st.session_state.w_abos,
                }
                with st.spinner("Audit en cours…"):
                    st.session_state["dernier_audit_auto"] = lancer_audit(situation_audit)

            audit_res = st.session_state.get("dernier_audit_auto")
            if audit_res and valider_audit_result(audit_res):
                if audit_res["situation_detectee"]:
                    st.info(audit_res["situation_detectee"])
                if not audit_res["offres_recommandees"]:
                    st.warning("Aucune recommandation sourcée n'a pu être produite.")
                for r in audit_res["offres_recommandees"]:
                    o = r["offre"]
                    with st.container(border=True):
                        st.markdown(f"**{o['nom']}** — {o['fournisseur']} · {o.get('caracteristiques','')}")
                        st.caption(f"💶 {o['prix_mensuel']} €/mois — économie estimée **{r['economie_an']} €/an**")
                        st.caption(f"🧠 {r['pourquoi']}")
                        st.caption(f"📎 Source : {r['source']}")
                if audit_res["offres_recommandees"]:
                    st.success(f"💰 Économie totale sourcée : **{audit_res['economie_totale_an']} €/an**")
                for pa in audit_res["points_attention"]:
                    st.warning(f"⚠️ {pa}")
                st.caption(f"Niveau de confiance de l'agent : {round(audit_res['niveau_confiance']*100)}%")
                with st.expander("🔍 Traçabilité (appels d'outils)"):
                    st.json(audit_res["tracabilite"])
            elif audit_res:
                st.error("Résultat d'audit invalide — relancez ou vérifiez la configuration de la clé API.")

        recommandations = []
        offres_interet_list = []
        # Économie affichée/enregistrée : toujours basée sur la MEILLEURE offre de chaque
        # catégorie comparée, indépendamment des cases « Intéresse le client » cochées par le
        # conseiller (celles-ci ne servent qu'à tracer ce qui a été présenté/retenu).
        meilleures_offres_auto = []

        def _bouton_souscrire(o, contexte):
            """Bouton « Souscrire » : ouvre le lien affilié de l'offre (avec code d'affiliation
            + paramètres du client) et logue chaque clic dans l'historique (audit trail)."""
            if not o.get("url_souscription"):
                return
            key_reveal = f"souscrire_reveal_{contexte}_{o['id']}"
            if st.button("🔗 Souscrire", key=f"souscrire_btn_{contexte}_{o['id']}"):
                st.session_state[key_reveal] = True
                enregistrer_action(
                    "offre", o["id"], "Clic lien affilié",
                    f"{o['nom']} ({o['fournisseur']}) — client : {nom_complet}"
                )
            if st.session_state.get(key_reveal):
                lien = construire_lien_affilie(
                    o["url_souscription"], o.get("code_affiliation", ""),
                    {"client": nom_complet, "cp": st.session_state.w_cp, "ville": st.session_state.w_ville},
                )
                st.link_button("➡️ Ouvrir le lien de souscription", lien)

        # ----- TÉLÉCOM -----
        if "Télécom" in st.session_state.w_univers:
            cout_tel = float(st.session_state.w_tel_cout) + sum(l["cout"] for l in st.session_state.w_lignes_multi)
            st.caption(f"Coût télécom actuel pris en compte : **{round(cout_tel,2)} €/mois** "
                       f"soit **{round(cout_tel*12,2)} €/an**")

            fournisseur_exclu = None
            if (st.session_state.w_sat_reseau != SATISFACTION_RESEAU[0]
                    and st.session_state.w_tel_operateur not in ("Autre / Aucun", "")):
                fournisseur_exclu = st.session_state.w_tel_operateur
                st.caption(f"ℹ️ Client pas pleinement satisfait de **{fournisseur_exclu}** — "
                           f"nous proposons en priorité des offres d'autres opérateurs.")
            reco = construire_recommandations(st.session_state.w_service_principal, cout_tel,
                                               fournisseur_exclu=fournisseur_exclu,
                                               data_go_min=safe_float(st.session_state.w_tel_data))

            # ids déjà couverts par une "carte" (PDF/email) pour éviter les doublons
            ids_pdf = set()

            def _ajouter_offre_interet(o, categorie):
                """Enregistre une offre cochée « Intéresse le client » (box, pack ou offre
                principale) pour la fiche prospect ET pour la restitution PDF/email."""
                offres_interet_list.append({"univers": "Télécom", "categorie": categorie, **o})
                if o["id"] not in ids_pdf:
                    recommandations.append({
                        "univers": "Télécom", "categorie": categorie,
                        "cout_actuel": round(cout_tel, 2), "offre": o})
                    ids_pdf.add(o["id"])

            titre_p, offres_p = reco["principal"]
            st.markdown(f"### {titre_p}")
            if not offres_p:
                st.info("Aucune offre dans cette catégorie au catalogue. Ajoutez-en dans 🛠️ Admin.")
            categorie_p = titre_p.strip("📱🏠📦📲 ")
            if offres_p:
                meilleures_offres_auto.append({"univers": "Télécom", "categorie": categorie_p,
                                                "economie_annuelle": offres_p[0]["economie_annuelle"]})
            for o in offres_p:
                with st.container(border=True):
                    a, b, c = st.columns([3, 2, 1])
                    a.markdown(f"##### {o['nom']}")
                    a.caption(f"{o['fournisseur']} · {o['caracteristiques']}")
                    b.write(f"💶 **{o['prix_mensuel']} €/mois**")
                    b.caption(f"Coût 1ère année : {o['cout_1_an']} €")
                    c.metric("Économie/an", f"{o['economie_annuelle']} €")
                    interesse = st.checkbox("⭐ Intéresse le client", key=f"interet_offre_{o['id']}")
                    if interesse:
                        _ajouter_offre_interet(o, categorie_p)
                    _bouton_souscrire(o, "tel_principal")

            if reco["cross_sell"]:
                st.markdown("---")
                st.markdown("#### 💡 Pour aller plus loin (à proposer au client)")
            for titre_cs, offres_cs in reco["cross_sell"]:
                if offres_cs:
                    categorie_cs = titre_cs.strip("📱🏠📦📲⚡🎬 ")
                    with st.expander(f"{titre_cs}  —  à partir de {offres_cs[0]['prix_mensuel']} €/mois"):
                        for o in offres_cs:
                            cca, ccb, ccc = st.columns([4, 1, 1.6])
                            cca.write(f"**{o['nom']}** — {o['fournisseur']}  ·  {o['caracteristiques']}")
                            ccb.write(f"**{o['prix_mensuel']} €/mois**")
                            interesse_cs = ccc.checkbox("⭐ Intéresse", key=f"interet_offre_{o['id']}")
                            if interesse_cs:
                                _ajouter_offre_interet(o, categorie_cs)
                            _bouton_souscrire(o, f"tel_cs_{categorie_cs}")

        # ----- ÉNERGIE -----
        if "Énergie" in st.session_state.w_univers:
            st.markdown("### ⚡ Énergie")
            for cat, cout in [("Électricité", st.session_state.w_ener_cout_elec),
                              ("Gaz",          st.session_state.w_ener_cout_gaz)]:
                if cout > 0:
                    offres = comparer_offres("Énergie", cat, float(cout)) or \
                             comparer_offres("Énergie", cat + " Pro", float(cout))
                    if offres:
                        st.markdown(f"**{cat}** — actuel : {cout} €/mois soit {round(cout*12,2)} €/an")
                        meilleures_offres_auto.append({"univers": "Énergie", "categorie": cat,
                                                        "economie_annuelle": offres[0]["economie_annuelle"]})
                        for o in offres[:3]:
                            with st.container(border=True):
                                a, b, c = st.columns([3, 2, 1])
                                a.markdown(f"##### {o['nom']}")
                                a.caption(f"{o['fournisseur']} · {o['caracteristiques']}")
                                b.write(f"💶 {o['prix_mensuel']} €/mois")
                                c.metric("Économie/an", f"{o['economie_annuelle']} €")
                                interesse = st.checkbox("⭐ Intéresse le client",
                                                         key=f"interet_offre_ener_{cat}_{o['id']}")
                                if interesse:
                                    offres_interet_list.append({"univers": "Énergie", "categorie": cat, **o})
                                    recommandations.append({
                                        "univers": "Énergie", "categorie": cat,
                                        "cout_actuel": float(cout), "offre": o})
                                _bouton_souscrire(o, f"ener_{cat}")
                    else:
                        st.info(f"Aucune offre {cat} au catalogue.")

        # ----- ABONNEMENTS -----
        if "Abonnements" in st.session_state.w_univers and st.session_state.w_abos:
            st.markdown("### 🎬 Abonnements")
            for abo_idx, a in enumerate(st.session_state.w_abos):
                cout_abo = safe_float(a["cout"])
                offres   = comparer_offres("Abonnements", None, cout_abo)
                # Ne proposer que des alternatives moins chères ET du même type (approximation par catégorie)
                alt = [o for o in offres if safe_float(o["prix_mensuel"]) < cout_abo]
                st.markdown(f"**{a['nom']}** — actuel : {cout_abo} €/mois soit {round(cout_abo*12,2)} €/an")
                if alt:
                    o = alt[0]
                    eco_reelle_an = round((cout_abo - safe_float(o["prix_mensuel"])) * 12, 2)
                    # On corrige economie_annuelle avec le vrai coût client
                    o = {**o, "economie_annuelle": eco_reelle_an}
                    meilleures_offres_auto.append({"univers": "Abonnements", "categorie": a["nom"],
                                                    "economie_annuelle": eco_reelle_an})
                    with st.container(border=True):
                        x, y, z = st.columns([3, 2, 1])
                        x.markdown(f"##### {o['nom']}")
                        x.caption(f"{o['fournisseur']} · {o['caracteristiques']}")
                        y.write(f"💶 {o['prix_mensuel']} €/mois")
                        z.metric("Économie/an", f"{eco_reelle_an} €")
                        interesse = st.checkbox("⭐ Intéresse le client",
                                                 key=f"interet_offre_abo_{abo_idx}_{o['id']}")
                        if interesse:
                            offres_interet_list.append({"univers": "Abonnements", "categorie": a["nom"], **o})
                            recommandations.append({
                                "univers": "Abonnements", "categorie": a["nom"],
                                "cout_actuel": cout_abo, "offre": o})
                        _bouton_souscrire(o, f"abo_{abo_idx}")
                else:
                    st.caption("Pas d'alternative moins chère au catalogue.")

        # ----- SYNTHÈSE -----
        total_eco = economie_totale_groupee(meilleures_offres_auto)
        st.divider()
        if total_eco > 0:
            st.success(f"### 💰 Économie totale estimée : {round(total_eco,2)} € / an")
        else:
            st.info("Aucune économie chiffrée — vérifiez votre catalogue.")

        # ----- DICT CLIENT -----
        infos_client = {
            "ref":                  generer_ref(),
            "prenom":               st.session_state.w_prenom,
            "nom":                  st.session_state.w_nom,
            "telephone":            st.session_state.w_tel,
            "email":                st.session_state.w_email,
            "code_postal":          st.session_state.w_cp,
            "ville":                st.session_state.w_ville,
            "adresse":              st.session_state.w_adresse,
            "type_client":          st.session_state.w_type_client,
            "univers_interesse":    ", ".join(st.session_state.w_univers),
            "service_principal":    st.session_state.w_service_principal,
            "operateur_actuel":     st.session_state.w_tel_operateur,
            "techno":               st.session_state.w_tel_techno,
            "data_go":              st.session_state.w_tel_data,
            "offre_actuelle":       st.session_state.w_tel_offre,
            "cout_mensuel_actuel":  safe_float(st.session_state.w_tel_cout),
            "satisfaction_reseau":  st.session_state.w_sat_reseau,
            "veut_rester":          "Oui" if st.session_state.w_veut_rester else "Non",
            "speed_down":           safe_float(st.session_state.w_speed_down),
            "speed_up":             safe_float(st.session_state.w_speed_up),
            "cout_elec":            safe_float(st.session_state.w_ener_cout_elec),
            "cout_gaz":             safe_float(st.session_state.w_ener_cout_gaz),
            "fournisseur_energie":  st.session_state.w_ener_fournisseur,
            "abonnements":          json.dumps(st.session_state.w_abos, ensure_ascii=False),
            "lignes_multi":         json.dumps(st.session_state.w_lignes_multi, ensure_ascii=False),
            "economie_estimee_an":  round(total_eco, 2),
            "notes":                (f"Satisfaction réseau : {st.session_state.w_sat_reseau}. "
                                     f"Veut rester : {'Oui' if st.session_state.w_veut_rester else 'Non'}."),
            "cree_par":             st.session_state.auth_nom_complet,  # ← TRAÇABILITÉ
            "offres_interet":       json.dumps(offres_interet_list, ensure_ascii=False),
        }

        # ----- RESTITUTION (teaser — le détail des offres n'est communiqué qu'après
        #       règlement des honoraires, voir menu 🧾 Facturation) -----
        st.divider()
        st.markdown("#### 📤 Restitution & suivi")
        st.caption("📌 Le PDF et l'email ci-dessous sont la version « aperçu » (économie totale, "
                   "sans détail des offres). Le détail complet se débloque via un devis d'honoraires "
                   "dans le menu 🧾 Facturation.")
        # Catégories proposées par univers (ex. "Télécom" → "Mobile", "Pack Box + Mobile"),
        # affichées dans le PDF juste après chaque univers — sans le détail commercial complet
        # (fournisseur/prix), qui reste réservé à la version débloquée après honoraires.
        details_univers = {}
        for m in meilleures_offres_auto:
            categories = details_univers.setdefault(m["univers"], [])
            if m["categorie"] not in categories:
                categories.append(m["categorie"])

        pdf_bytes = None
        if total_eco > 0:
            with st.spinner("Génération du PDF…"):
                pdf_bytes = generer_pdf_teaser(
                    infos_client, st.session_state.w_univers, total_eco, st.session_state.nom_societe,
                    details_univers=details_univers)

        col1, col2, col3 = st.columns(3)
        if pdf_bytes:
            col1.download_button("📄 Télécharger le PDF (aperçu)", data=pdf_bytes,
                                 file_name=f"apercu_{nom_complet.replace(' ','_')}.pdf",
                                 mime="application/pdf")
        elif not FPDF_OK:
            col1.caption("PDF indispo (pip install fpdf2)")

        if col2.button("📧 Envoyer au client"):
            if not st.session_state.w_email:
                st.warning("Pas d'email client.")
            elif total_eco <= 0:
                st.warning("Aucune économie chiffrée à communiquer.")
            else:
                corps = construire_corps_email_teaser(infos_client, st.session_state.w_univers, total_eco)
                ok, msg = envoyer_email(
                    st.session_state.w_email,
                    "Votre étude d'économies personnalisée",
                    corps, pdf_bytes,
                    f"apercu_{nom_complet.replace(' ','_')}.pdf")
                (st.success if ok else st.error)(msg)

        if col3.button("📇 Enregistrer prospect"):
            if not peut_modifier():
                st.error("🔒 Action réservée aux conseillers et admins.")
            else:
                # Enrichissement auto des notes
                infos_client["notes"] = (
                    f"Satisfaction réseau : {st.session_state.w_sat_reseau}. "
                    f"Veut rester : {'Oui' if st.session_state.w_veut_rester else 'Non'}. "
                    f"Économie estimée : {round(total_eco,2)} €/an. "
                    f"Univers : {infos_client['univers_interesse']}."
                )
                ajouter_prospect(infos_client)
                st.success(f"✅ Prospect enregistré — économie estimée {round(total_eco,2)} €/an. "
                           "Retrouvez-le dans « Prospects » pour y créer un dossier une fois "
                           "les offres retenues.")

        st.divider()
        br1, br2 = st.columns(2)
        if br1.button("⬅️ Corriger une information (retour à l'étape 3)"):
            st.session_state.w_etape = 3; st.rerun()
        if br2.button("🔄 Nouveau diagnostic (réinitialiser)"):
            for k in list(DEFAUTS.keys()):
                if k.startswith("w_") or k == "facture_data":
                    st.session_state[k] = DEFAUTS[k]
            st.session_state.w_etape = 1; st.rerun()


# ==============================================================================
#  TABLEAU DE BORD
# ==============================================================================
elif menu == "📊 Tableau de bord":
    moi  = st.session_state.auth_nom_complet
    role = st.session_state.auth_role
    st.title(f"📊 Tableau de bord — {moi}")

    recalculer_scores_prospects()
    df_p_all = lire_prospects()
    df_c_all = lire_clients()

    # Filtrer par conseiller (admin voit tout si souhaité)
    if role == "Admin":
        vue_admin = st.toggle("Vue globale (tous les conseillers)", value=False, key="tdb_global")
    else:
        vue_admin = False

    if vue_admin:
        df_p = df_p_all
        df_c = df_c_all
        st.caption("Mode global — vous voyez les données de toute l'équipe.")
    else:
        df_p = df_p_all[df_p_all["cree_par"] == moi] if not df_p_all.empty and "cree_par" in df_p_all.columns else df_p_all
        df_c = df_c_all[df_c_all["cree_par"] == moi] if not df_c_all.empty and "cree_par" in df_c_all.columns else df_c_all

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    total_prospects  = len(df_p)
    a_relancer       = len(df_p[df_p["statut"] == "À relancer"]) if not df_p.empty and "statut" in df_p.columns else 0
    total_clients    = len(df_c)
    eco_totale       = round(df_c["economie_estimee_an"].sum(), 2) if not df_c.empty and "economie_estimee_an" in df_c.columns else 0.0

    k1.metric("📋 Prospects total",    total_prospects)
    k2.metric("⏰ À relancer",          a_relancer,    delta="urgent" if a_relancer > 3 else None,
              delta_color="inverse" if a_relancer > 3 else "normal")
    k3.metric("✅ Clients signés",      total_clients)
    k4.metric("💰 Économies générées",  f"{eco_totale} €/an")

    st.divider()

    # ── Relances à faire aujourd'hui / en retard ───────────────────────────────
    st.markdown("### ⏰ Relances à traiter")
    if df_p.empty or "statut" not in df_p.columns:
        st.info("Aucun prospect enregistré.")
    else:
        relances = df_p[df_p["statut"].isin(["À relancer", "Relancé"])].copy()
        if relances.empty:
            st.success("✅ Aucune relance en attente — bon travail !")
        else:
            if "score" in relances.columns:
                relances["priorité"] = relances["score"].apply(indicateur_score)
            cols_rel = ["priorité","economie_estimee_an","nom","prenom","telephone","email"]
            cols_rel = [c for c in cols_rel if c in relances.columns]

            today_date = datetime.now().date()
            relances["_date_parsed"] = relances["date_relance"].apply(parser_date_relance)

            def _trier_par_priorite(g):
                """Au sein d'un même groupe (retard / aujourd'hui / à venir — donc déjà
                organisé par échéance d'appel hebdomadaire), trie par économie estimée
                décroissante : on appelle en priorité les prospects avec la plus grosse
                économie, notre rémunération étant un % de cette économie."""
                return g.sort_values("economie_estimee_an", ascending=False) if "economie_estimee_an" in g.columns \
                    else g.sort_values("_date_parsed")

            en_retard  = _trier_par_priorite(relances[relances["_date_parsed"].notna() & (relances["_date_parsed"] < today_date)])
            aujourdhui = _trier_par_priorite(relances[relances["_date_parsed"] == today_date])
            a_venir    = _trier_par_priorite(relances[relances["_date_parsed"].notna() & (relances["_date_parsed"] > today_date)])
            sans_date  = _trier_par_priorite(relances[relances["_date_parsed"].isna()])

            st.caption("💡 Cliquez sur une ligne pour ouvrir la fiche prospect correspondante.")
            for cle_grp, titre, groupe in [
                ("retard", f"🔴 En retard ({len(en_retard)})", en_retard),
                ("jour", f"🟠 Aujourd'hui ({len(aujourdhui)})", aujourdhui),
                ("venir", f"🟢 À venir ({len(a_venir)})", a_venir),
                ("sans_date", f"⚪ Sans date ({len(sans_date)})", sans_date),
            ]:
                st.markdown(f"#### {titre}")
                _table_cliquable_vers_fiche(
                    groupe, ["id"] + cols_rel, key=f"tdb_relance_prospects_{cle_grp}",
                    menu_cible="📇 Prospects", session_key_focus="_focus_prospect_id")

            # Actions rapides
            st.markdown("**Action rapide sur un prospect :**")
            ids_rel = relances["id"].tolist()
            sel = st.selectbox("Prospect", ids_rel,
                format_func=lambda i: f"{relances[relances['id']==i]['prenom'].values[0]} {relances[relances['id']==i]['nom'].values[0]} — {relances[relances['id']==i]['telephone'].values[0]}",
                key="tdb_sel_prospect")
            if widget_relance(sel, "tdb_relance"):
                st.success("Relance programmée."); st.rerun()
            cb, cc = st.columns(2)
            if cb.button("📇 Voir la fiche", key="tdb_voir_fiche"):
                st.session_state["_focus_prospect_id"] = int(sel)
                st.session_state.menu = "📇 Prospects"
                st.rerun()
            if cc.button("🗑️ Supprimer", key="tdb_del"):
                supprimer_prospect(int(sel)); st.warning("Supprimé."); st.rerun()

    st.divider()

    # ── Relances clients à faire aujourd'hui / en retard ───────────────────────
    st.markdown("### ⏰ Relances clients à traiter")
    if df_c.empty or "statut_relance" not in df_c.columns:
        st.info("Aucun client enregistré.")
    else:
        relances_c = df_c[df_c["statut_relance"].isin(["À relancer", "Relancé"])].copy()
        if relances_c.empty:
            st.success("✅ Aucune relance client en attente.")
        else:
            cols_rel_c = ["prenom","nom","telephone","email","operateur_actuel",
                          "cout_mensuel_actuel","economie_estimee_an","statut_relance","date_relance","cree_par"]
            cols_rel_c = [c for c in cols_rel_c if c in relances_c.columns]

            today_date_c = datetime.now().date()
            relances_c["_date_parsed"] = relances_c["date_relance"].apply(parser_date_relance)

            # Complète par la date de fin d'engagement du contrat le plus proche quand la
            # relance n'a pas de date propre — sinon une échéance imminente (ex. dans 2 jours)
            # se retrouve masquée dans « Sans date » au lieu d'apparaître en urgence.
            manquants_c = relances_c["_date_parsed"].isna()
            if manquants_c.any():
                df_ech_tous = lire_contrats_echeance(3650)
                if not df_ech_tous.empty:
                    echeance_par_client = df_ech_tous.groupby("client_id")["_date_fin"].min()
                    dates_completees = relances_c.loc[manquants_c, "id"].map(echeance_par_client)
                    relances_c.loc[manquants_c, "_date_parsed"] = dates_completees
                    trouve_c = manquants_c & relances_c["_date_parsed"].notna()
                    relances_c.loc[trouve_c, "date_relance"] = relances_c.loc[trouve_c, "_date_parsed"].apply(
                        lambda d: f"{d.strftime('%d/%m/%Y')} (fin de contrat)")

            en_retard_c  = relances_c[relances_c["_date_parsed"].notna() & (relances_c["_date_parsed"] < today_date_c)] \
                              .sort_values("_date_parsed")
            aujourdhui_c = relances_c[relances_c["_date_parsed"] == today_date_c]
            a_venir_c    = relances_c[relances_c["_date_parsed"].notna() & (relances_c["_date_parsed"] > today_date_c)] \
                              .sort_values("_date_parsed")
            sans_date_c  = relances_c[relances_c["_date_parsed"].isna()]

            for titre, groupe in [
                (f"🔴 En retard ({len(en_retard_c)})", en_retard_c),
                (f"🟠 Aujourd'hui ({len(aujourdhui_c)})", aujourdhui_c),
                (f"🟢 À venir ({len(a_venir_c)})", a_venir_c),
                (f"⚪ Sans date ({len(sans_date_c)})", sans_date_c),
            ]:
                st.markdown(f"#### {titre}")
                if groupe.empty:
                    st.caption("Aucune")
                else:
                    st.dataframe(groupe[cols_rel_c], hide_index=True, use_container_width=True)

            st.markdown("**Action rapide sur un client :**")
            ids_rel_c = relances_c["id"].tolist()
            sel_c = st.selectbox("Client", ids_rel_c,
                format_func=lambda i: f"{relances_c[relances_c['id']==i]['prenom'].values[0]} {relances_c[relances_c['id']==i]['nom'].values[0]} — {relances_c[relances_c['id']==i]['telephone'].values[0]}",
                key="tdb_sel_client")
            if widget_relance_client(sel_c, "tdb_relance_client"):
                st.success("Relance client programmée."); st.rerun()

    st.divider()

    # ── Contrats arrivant à échéance (dernier mois d'engagement : à venir ≤14j, urgent ≤7j) ──
    st.markdown("### 📅 Fin d'engagement — 14 prochains jours")
    df_echeance = lire_contrats_echeance(14)
    if not vue_admin and not df_echeance.empty and "client_conseiller" in df_echeance.columns:
        df_echeance = df_echeance[df_echeance["client_conseiller"] == moi]
    if df_echeance.empty:
        st.success("✅ Aucun contrat n'arrive en fin d'engagement dans les 14 prochains jours.")
    else:
        df_echeance = df_echeance.assign(
            priorité=df_echeance["jours_restants"].apply(lambda j: "🔴 Urgent" if j <= 7 else "🟢 À venir"))
        cols_ech = ["priorité", "client_prenom", "client_nom", "client_telephone", "client_email",
                    "fournisseur", "nom_offre", "date_fin_engagement", "jours_restants"]
        cols_ech = [c for c in cols_ech if c in df_echeance.columns]
        st.caption("💡 Cliquez sur une ligne pour ouvrir la fiche client et préparer son nouveau forfait.")
        _table_cliquable_vers_fiche(
            df_echeance, ["client_id"] + cols_ech, key="tdb_echeance_clients",
            menu_cible="👥 Clients & contrats", session_key_focus="_focus_client_id", id_col="client_id")

        st.markdown("**Envoyer l'alerte de fin d'engagement à un client :**")
        ids_ech = df_echeance["id"].tolist()
        sel_ech = st.selectbox("Contrat", ids_ech,
            format_func=lambda i: f"{df_echeance[df_echeance['id']==i]['client_prenom'].values[0]} "
                                   f"{df_echeance[df_echeance['id']==i]['client_nom'].values[0]} — "
                                   f"fin le {df_echeance[df_echeance['id']==i]['date_fin_engagement'].values[0]}",
            key="tdb_sel_echeance")
        if st.button("📧 Envoyer l'alerte au client", key="tdb_envoi_echeance"):
            row_ech = df_echeance[df_echeance["id"] == sel_ech].iloc[0]
            alternatives = comparer_offres(row_ech["univers"], row_ech["categorie"],
                                            float(row_ech["cout_mensuel"] or 0),
                                            fournisseur_exclu=row_ech["fournisseur"])
            meilleure = alternatives[0] if alternatives and alternatives[0]["economie_annuelle"] > 0 else None
            corps = construire_corps_email_fin_engagement(
                row_ech["client_prenom"], row_ech["date_fin_engagement"], meilleure)
            ok, msg = envoyer_email(row_ech["client_email"],
                                     "Votre engagement arrive à échéance", corps)
            (st.success if ok else st.error)(msg)

    st.divider()

    # ── Mes derniers clients ───────────────────────────────────────────────────
    st.markdown("### 👥 Derniers clients enregistrés")
    if df_c.empty:
        st.info("Aucun client enregistré.")
    else:
        cols_c = ["prenom","nom","telephone","operateur_actuel","offre_actuelle",
                  "cout_mensuel_actuel","economie_estimee_an","date_creation","cree_par"]
        cols_c = [c for c in cols_c if c in df_c.columns]
        st.dataframe(df_c[cols_c].head(10), hide_index=True, use_container_width=True)

    # ── Vue admin : répartition par conseiller + agenda d'appels ────────────────
    if role == "Admin" and not df_p_all.empty and "cree_par" in df_p_all.columns:
        st.divider()
        st.markdown("### 🏆 Performance par conseiller (Admin)")
        conseillers = df_p_all["cree_par"].dropna().unique().tolist()
        rows = []
        for cons in conseillers:
            p_cons = df_p_all[df_p_all["cree_par"] == cons]
            c_cons = df_c_all[df_c_all["cree_par"] == cons] if not df_c_all.empty and "cree_par" in df_c_all.columns else pd.DataFrame()
            eco = round(c_cons["economie_estimee_an"].sum(), 2) if not c_cons.empty and "economie_estimee_an" in c_cons.columns else 0.0
            a_relancer_cons = p_cons[p_cons["statut"] == "À relancer"] if "statut" in p_cons.columns else p_cons.iloc[0:0]
            nb_chaud = len(a_relancer_cons[a_relancer_cons["score"] >= 150]) if "score" in a_relancer_cons.columns else 0
            rows.append({
                "Conseiller":         cons,
                "Prospects":          len(p_cons),
                "À relancer":         len(a_relancer_cons),
                "🔴 Chaud":           nb_chaud,
                "Clients":            len(c_cons),
                "Économie générée €": eco,
            })
        if rows:
            st.dataframe(pd.DataFrame(rows).sort_values("Clients", ascending=False),
                         hide_index=True, use_container_width=True)

        st.markdown("#### 🗓️ Agenda d'appels — vue par conseiller")
        options_cons = ["Tous les conseillers"] + conseillers
        cons_choisi = st.selectbox("Conseiller", options_cons, key="agenda_cons_choisi")
        vue_globale = cons_choisi == "Tous les conseillers"
        base_agenda = df_p_all if vue_globale else df_p_all[df_p_all["cree_par"] == cons_choisi]
        agenda_cons = base_agenda[base_agenda["statut"].isin(["À relancer", "Relancé"])].copy() \
            if "statut" in base_agenda.columns else base_agenda.iloc[0:0]
        if agenda_cons.empty:
            st.success(f"✅ Aucune relance en attente pour {cons_choisi}.")
        else:
            if "score" in agenda_cons.columns:
                agenda_cons["priorité"] = agenda_cons["score"].apply(indicateur_score)
            if "economie_estimee_an" in agenda_cons.columns:
                # Tri par économie décroissante : on appelle en priorité les prospects
                # avec la plus grosse économie (rémunération en % de l'économie réalisée).
                if vue_globale and "cree_par" in agenda_cons.columns:
                    agenda_cons = agenda_cons.sort_values(["cree_par", "economie_estimee_an"], ascending=[True, False])
                else:
                    agenda_cons = agenda_cons.sort_values("economie_estimee_an", ascending=False)
            cols_agenda = [c for c in (["cree_par"] if vue_globale else [])
                           + ["priorité", "economie_estimee_an", "prenom", "nom", "telephone", "date_relance", "statut"]
                           if c in agenda_cons.columns]
            st.caption(f"Liste d'appels de {cons_choisi}, triée par économie décroissante — {len(agenda_cons)} prospect(s).")

            c_toggle, c_export = st.columns([2, 1])
            vue_imprimable = c_toggle.toggle("🖨️ Vue imprimable (point d'équipe)", key="agenda_vue_imprimable")
            excel_bytes_agenda = exporter_excel(agenda_cons[cols_agenda], nom_feuille="Agenda")
            if excel_bytes_agenda:
                c_export.download_button(
                    "📥 Export Excel", data=excel_bytes_agenda,
                    file_name=f"agenda_appels_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="export_excel_agenda")
            elif not OPENPYXL_OK:
                c_export.caption("Export indispo (pip install openpyxl)")

            if vue_imprimable:
                st.markdown(
                    "<style>@media print{[data-testid='stSidebar'],header,"
                    "[data-testid='stToolbar']{display:none !important;}}</style>",
                    unsafe_allow_html=True,
                )
                st.caption("Prêt pour l'impression — utilisez Ctrl+P (ou Cmd+P).")
                st.table(agenda_cons[cols_agenda])
            else:
                st.dataframe(agenda_cons[cols_agenda], hide_index=True, use_container_width=True)


# ==============================================================================
#  PROSPECTS
# ==============================================================================
elif menu == "📇 Prospects":
    st.title("📇 Prospects à relancer")
    recalculer_scores_prospects()
    df = lire_prospects()
    if df.empty:
        st.info("Aucun prospect. Lancez un diagnostic puis « Enregistrer prospect ».")
    else:
        recherche_p = st.text_input("🔎 Rechercher (nom, ville, email, réf., opérateur…)",
                                     key="recherche_prospects")

        # Filtre par statut
        statuts_dispo = ["Tous"] + sorted(df["statut"].dropna().unique().tolist()) if "statut" in df.columns else ["Tous"]
        col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
        filtre_statut = col_f1.selectbox("Filtrer par statut", statuts_dispo, key="filtre_statut_prospects")
        tri_score_actif = col_f2.toggle("💰 Trier par économie", value=True, key="tri_score_prospects")
        col_f3.metric("Total prospects", len(df),
                      delta=f"{len(df[df['statut']=='À relancer'])} à relancer" if 'statut' in df.columns else "")

        dff = df if filtre_statut == "Tous" else df[df["statut"] == filtre_statut]
        if recherche_p:
            ids = recherche_fts("prospects", recherche_p)
            if ids is not None:
                ordre = {i: n for n, i in enumerate(ids)}
                dff = dff[dff["id"].isin(ids)]
                dff = dff.assign(_rang=dff["id"].map(ordre)).sort_values("_rang").drop(columns="_rang")
            else:
                r   = recherche_p.lower()
                dff = dff[dff.apply(lambda row: r in str(row.to_dict()).lower(), axis=1)]

        if "score" in dff.columns:
            dff = dff.assign(priorité=dff["score"].apply(indicateur_score))
        if tri_score_actif and "economie_estimee_an" in dff.columns:
            dff = dff.sort_values("economie_estimee_an", ascending=False)

        cols = ["priorité","score","ref","origine","prenom","nom","telephone","email","ville","univers_interesse",
                "service_principal","operateur_actuel","cout_mensuel_actuel",
                "satisfaction_reseau","veut_rester","economie_estimee_an","statut",
                "cree_par","date_creation","date_relance"]
        cols = [c for c in cols if c in dff.columns]
        st.dataframe(dff[cols], hide_index=True, use_container_width=True)

        excel_bytes = exporter_excel(dff[cols], nom_feuille="Prospects")
        if excel_bytes:
            st.download_button("📥 Exporter en Excel (.xlsx)", data=excel_bytes,
                                file_name=f"prospects_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="export_excel_prospects")
        elif not OPENPYXL_OK:
            st.caption("Export Excel indisponible (pip install openpyxl)")

        st.divider()
        st.markdown("#### Fiche prospect détaillée")
        if dff.empty:
            st.info("Aucun prospect avec ce statut.")
            st.stop()
        ids_dispo_prospect = dff["id"].tolist()
        focus_prospect = st.session_state.pop("_focus_prospect_id", None)
        if focus_prospect is not None and focus_prospect in ids_dispo_prospect:
            st.session_state["fiche_prospect_choix"] = focus_prospect
        choix = st.selectbox("Prospect", ids_dispo_prospect,
            format_func=lambda i: (
                f"{df[df['id']==i]['prenom'].values[0]} "
                f"{df[df['id']==i]['nom'].values[0]} (#{i})"),
            key="fiche_prospect_choix")
        p = df[df["id"] == choix].iloc[0]
        st.markdown(f"##### 🔖 Référence : {p.get('ref') or '—'}")
        st.caption(f"{p['prenom']} {p['nom']}")
        if p.get("origine") == "Chatbot":
            st.info("🤖 Ce prospect a été créé automatiquement par le chatbot du site web.")

        cout_total = cout_total_mensuel(p.to_dict())
        eco_an     = safe_float(p.get("economie_estimee_an"))
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💶 Coût total /mois", f"{cout_total} €")
        m2.metric("💶 Coût total /an", f"{round(cout_total * 12, 2)} €")
        m3.metric("💰 Économie /mois", f"{round(eco_an / 12, 2)} €")
        m4.metric("💰 Économie /an", f"{eco_an} €")
        ic1, ic2 = st.columns(2)
        ic1.write(f"**Tél :** {p['telephone']}")
        ic2.write(f"**Email :** {p['email']}")

        if st.button("🔍 Voir plus de détails", key=f"voir_plus_prospect_{choix}"):
            _dialog_details_prospect(p)

        pdf_apercu = construire_apercu_pdf_prospect(p.to_dict(), st.session_state.nom_societe)
        if pdf_apercu:
            with st.container(border=True):
                st.markdown("##### 📄 Aperçu à partager")
                b64_apercu = base64.b64encode(pdf_apercu).decode()
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{b64_apercu}" '
                    f'width="100%" height="500"></iframe>',
                    unsafe_allow_html=True)
                cd1, cd2, cd3 = st.columns(3)
                cd1.download_button("📥 Télécharger", data=pdf_apercu,
                                     file_name=f"apercu_{p['prenom']}_{p['nom']}.pdf",
                                     mime="application/pdf", key=f"dl_apercu_{choix}")
                if peut_modifier():
                    if cd2.button("📧 Envoyer par email", key=f"btn_apercu_mail_{choix}"):
                        if not p.get("email"):
                            st.warning("Pas d'email sur cette fiche.")
                        else:
                            try:
                                offres_int_pdf = json.loads(p.get("offres_interet") or "[]")
                            except Exception:
                                offres_int_pdf = []
                            univers_pdf = [u for u in dict.fromkeys(
                                o.get("univers") for o in offres_int_pdf) if u]
                            corps = construire_corps_email_teaser(p.to_dict(), univers_pdf, eco_an)
                            ok, msg = envoyer_email(
                                p["email"], "Votre étude d'économies personnalisée",
                                corps, pdf_apercu, f"apercu_{p['prenom']}_{p['nom']}.pdf")
                            (st.success if ok else st.error)(msg)
                    if cd3.button("📱 Envoyer par SMS", key=f"btn_apercu_sms_{choix}"):
                        if not p.get("telephone"):
                            st.warning("Pas de téléphone sur cette fiche.")
                        else:
                            tok = creer_token_documents(int(choix))
                            url_pdf = (f"{secrets_config.portail_prospect_base_url()}"
                                       f"/portail/{tok['token']}/apercu.pdf")
                            message = (f"Bonjour {p['prenom']}, voici votre étude d'économies "
                                       f"personnalisée : {url_pdf}")
                            ok_sms = envoyer_sms(p["telephone"], message)
                            (st.success if ok_sms else st.error)(
                                "SMS envoyé." if ok_sms else
                                "Échec de l'envoi du SMS (vérifiez la configuration).")

        if p.get("offres_interet") and p.get("offres_interet") not in ("[]", None):
            st.markdown("##### ⭐ Offres qui intéressaient le client")
            try:
                offres_int = json.loads(p["offres_interet"])
            except Exception:
                offres_int = None
            if offres_int:
                for idx_oi, oi in enumerate(offres_int):
                    with st.container(border=True):
                        a, b, c = st.columns([3, 2, 1])
                        a.markdown(f"**{oi.get('nom','—')}**")
                        sous_titre = " · ".join(x for x in (oi.get("univers"), oi.get("categorie"), oi.get("fournisseur")) if x)
                        a.caption(sous_titre)
                        if oi.get("caracteristiques"):
                            a.caption(oi["caracteristiques"])
                        b.write(f"💶 **{oi.get('prix_mensuel','—')} €/mois**")
                        if oi.get("engagement"):
                            b.caption(f"Engagement {oi['engagement']} mois")
                        cout_ref = _cout_reference_actuel(oi, p)
                        if cout_ref is not None:
                            eco_affichee = round((cout_ref - safe_float(oi.get("prix_mensuel"))) * 12, 2)
                            c.metric("Économie/an", f"{eco_affichee} €")
                        elif oi.get("univers") == "Télécom":
                            c.caption("ℹ️ Coût actuel inconnu pour ce service — pas de "
                                      "comparaison possible. Ajoutez le contrat existant du "
                                      "prospect ci-dessous pour calculer l'économie.")
                        with b:
                            bouton_pre_remplir(oi, p, "prospect", int(choix),
                                                key=f"presous_prosp_{choix}_{idx_oi}")
            else:
                st.caption(p["offres_interet"])

        if peut_modifier():
            with st.container(border=True):
                st.markdown("##### 📩 Demander facture + test de débit")
                st.caption("Envoie un lien personnel par SMS et email pour que le prospect "
                           "transmette lui-même sa facture et un test de débit — les champs "
                           "opérateur/coût/débit de sa fiche se mettent à jour automatiquement, "
                           "sans que vous ayez à les ressaisir.")
                if st.button("📩 Envoyer la demande (SMS + email)", key=f"btn_demande_docs_{choix}"):
                    tok = creer_token_documents(int(choix))
                    url = f"{secrets_config.portail_prospect_base_url()}/portail/{tok['token']}"
                    resultat = envoyer_demande_documents_prospect(p.to_dict(), url)
                    enregistrer_action(
                        "prospect", int(choix), "Demande facture + débit envoyée",
                        f"Lien valable jusqu'au {tok['date_expiration']} — "
                        f"SMS {'envoyé' if resultat['sms_envoye'] else 'non envoyé'}, "
                        f"email {'envoyé' if resultat['email_envoye'] else 'non envoyé'}")
                    if resultat["sms_envoye"] or resultat["email_envoye"]:
                        c_sms, c_mail = st.columns(2)
                        c_sms.metric("SMS", "✅ Envoyé" if resultat["sms_envoye"] else "❌ Non envoyé")
                        c_mail.metric("Email", "✅ Envoyé" if resultat["email_envoye"] else "❌ Non envoyé")
                    else:
                        st.warning("Aucun canal automatique n'a fonctionné (SMS non configuré et/ou "
                                   "email manquant sur la fiche) — transmettez ce lien manuellement :")
                    st.markdown(f"🔗 [Ouvrir le portail prospect]({url})")
                    st.caption(f"Lien : {url} — nécessite que le service `chatbot_api.py` "
                               f"(port {url.split(':')[-1].split('/')[0]}) soit démarré.")

            with st.expander("✏️ Modifier ce prospect"):
                champs = {"telephone":"Téléphone","email":"Email","adresse":"Adresse",
                          "ville":"Ville","code_postal":"Code postal","operateur_actuel":"Opérateur",
                          "offre_actuelle":"Offre actuelle","cout_mensuel_actuel":"Coût (€)",
                          "notes":"Notes","statut":"Statut"}
                with st.form(key=f"form_edit_prospect_{choix}"):
                    valeurs = {champ: st.text_input(label, str(p[champ]), key=f"edit_p_{champ}_{choix}")
                               for champ, label in champs.items()}
                    if st.form_submit_button("💾 Enregistrer"):
                        for champ, val in valeurs.items():
                            v = safe_float(val) if champ == "cout_mensuel_actuel" else val
                            maj_prospect(int(choix), champ, v)
                        st.success("Prospect mis à jour."); st.rerun()

            with st.expander("⭐ Modifier les offres qui intéressent le client"):
                st.caption("Cochez les offres que le client souhaite finalement retenir "
                           "— l'économie totale de la fiche est recalculée automatiquement.")
                try:
                    offres_int_actuelles = json.loads(p.get("offres_interet") or "[]")
                except Exception:
                    offres_int_actuelles = []
                ids_actuels = {o.get("id") for o in offres_int_actuelles}

                nouvelles_offres = []
                univers_p = [u.strip() for u in (p.get("univers_interesse") or "").split(",") if u.strip()]

                if "Télécom" in univers_p:
                    cat_key = CATEGORIE_PAR_SERVICE_PRINCIPAL.get(p.get("service_principal"), "Mobile")
                    offres_tel = comparer_offres("Télécom", cat_key, safe_float(p.get("cout_mensuel_actuel")),
                                                  data_go_min=safe_float(p.get("data_go")))
                    if offres_tel:
                        st.markdown(f"##### 📱 Télécom — {cat_key}")
                        for o in offres_tel[:5]:
                            val = st.checkbox(
                                f"{o['nom']} — {o['fournisseur']} · {o['prix_mensuel']} €/mois · "
                                f"éco {o['economie_annuelle']} €/an",
                                value=o["id"] in ids_actuels, key=f"prosp_int_tel_{choix}_{o['id']}")
                            if val:
                                nouvelles_offres.append({"univers": "Télécom", "categorie": cat_key, **o})
                                bouton_pre_remplir(o, p, "prospect", int(choix),
                                                    key=f"presous_mod_tel_{choix}_{o['id']}")

                if "Énergie" in univers_p:
                    for cat, cout_champ in [("Électricité", "cout_elec"), ("Gaz", "cout_gaz")]:
                        cout = safe_float(p.get(cout_champ))
                        if cout > 0:
                            offres_e = comparer_offres("Énergie", cat, cout) or \
                                       comparer_offres("Énergie", cat + " Pro", cout)
                            if offres_e:
                                st.markdown(f"##### ⚡ {cat}")
                                for o in offres_e[:3]:
                                    val = st.checkbox(
                                        f"{o['nom']} — {o['fournisseur']} · {o['prix_mensuel']} €/mois · "
                                        f"éco {o['economie_annuelle']} €/an",
                                        value=o["id"] in ids_actuels,
                                        key=f"prosp_int_ener_{choix}_{cat}_{o['id']}")
                                    if val:
                                        nouvelles_offres.append({"univers": "Énergie", "categorie": cat, **o})
                                        bouton_pre_remplir(o, p, "prospect", int(choix),
                                                            key=f"presous_mod_ener_{choix}_{cat}_{o['id']}")

                if "Abonnements" in univers_p and p.get("abonnements") and p["abonnements"] not in ("[]", None):
                    try:
                        abos_p = json.loads(p["abonnements"])
                    except Exception:
                        abos_p = []
                    if abos_p:
                        st.markdown("##### 🎬 Abonnements")
                        for abo_idx, a in enumerate(abos_p):
                            cout_abo = safe_float(a.get("cout"))
                            offres_abo = comparer_offres("Abonnements", None, cout_abo)
                            alt = [o for o in offres_abo if safe_float(o["prix_mensuel"]) < cout_abo]
                            if alt:
                                eco_reelle = round((cout_abo - safe_float(alt[0]["prix_mensuel"])) * 12, 2)
                                o = {**alt[0], "economie_annuelle": eco_reelle}
                                val = st.checkbox(
                                    f"{a.get('nom','')} → {o['nom']} — {o['fournisseur']} · "
                                    f"{o['prix_mensuel']} €/mois · éco {eco_reelle} €/an",
                                    value=o["id"] in ids_actuels,
                                    key=f"prosp_int_abo_{choix}_{abo_idx}_{o['id']}")
                                if val:
                                    nouvelles_offres.append({"univers": "Abonnements", "categorie": a.get("nom"), **o})
                                    bouton_pre_remplir(o, p, "prospect", int(choix),
                                                        key=f"presous_mod_abo_{choix}_{abo_idx}_{o['id']}")

                if not univers_p:
                    st.caption("Aucun univers renseigné sur ce prospect.")

                if st.button("💾 Mettre à jour les offres retenues", key=f"btn_maj_offres_{choix}"):
                    total_eco_nv = economie_totale_groupee(nouvelles_offres)
                    maj_prospect(int(choix), "offres_interet", json.dumps(nouvelles_offres, ensure_ascii=False))
                    maj_prospect(int(choix), "economie_estimee_an", total_eco_nv)
                    st.success(f"Offres mises à jour — économie recalculée : {total_eco_nv} €/an."); st.rerun()

            st.markdown("##### 📑 Autres contrats du prospect")
            st.caption("Services déjà souscrits ailleurs par le prospect (appris au fil des "
                       "échanges) — sert de base de comparaison pour les offres cross-sell "
                       "(ex. Box) qui ne correspondent pas au service principal renseigné.")
            tous_contrats_p = lire_contrats_prospect(int(choix))
            if not tous_contrats_p.empty and "type_contrat" in tous_contrats_p.columns:
                contrats_p = tous_contrats_p[tous_contrats_p["type_contrat"] != "dossier_cmr"]
            else:
                contrats_p = tous_contrats_p
            if contrats_p.empty:
                st.caption("Aucun autre contrat renseigné.")
            else:
                cols_ctp = ["id", "univers", "categorie", "fournisseur", "nom_offre",
                            "cout_mensuel", "date_fin_engagement"]
                cols_ctp = [c for c in cols_ctp if c in contrats_p.columns]
                st.dataframe(contrats_p[cols_ctp], hide_index=True, use_container_width=True)
                if peut_modifier():
                    with st.expander("✏️ Modifier / supprimer un contrat du prospect"):
                        ctpid = st.selectbox("Contrat", contrats_p["id"].tolist(),
                            format_func=lambda i: f"#{i} · {contrats_p[contrats_p['id']==i]['nom_offre'].values[0]}",
                            key=f"ctp_sel_{choix}")
                        ctp = contrats_p[contrats_p["id"] == ctpid].iloc[0]
                        nv_cout_p = st.number_input("Coût mensuel (€)", min_value=0.0,
                            value=float(ctp["cout_mensuel"] or 0), step=1.0, key=f"ctp_cout_{choix}")
                        nv_fin_eng_p = st.date_input(
                            "Date de fin d'engagement", value=parser_date_relance(ctp.get("date_fin_engagement")),
                            format="DD/MM/YYYY", key=f"ctp_fin_eng_{choix}")
                        cxp, cyp = st.columns(2)
                        if cxp.button("💾 Enregistrer les modifs", key=f"ctp_save_{choix}"):
                            maj_contrat(int(ctpid), "cout_mensuel", nv_cout_p)
                            maj_contrat(int(ctpid), "date_fin_engagement",
                                        nv_fin_eng_p.strftime("%d/%m/%Y") if nv_fin_eng_p else "")
                            st.success("Contrat mis à jour."); st.rerun()
                        if cyp.button("🗑️ Supprimer ce contrat", key=f"ctp_del_{choix}"):
                            supprimer_contrat(int(ctpid)); st.warning("Contrat supprimé."); st.rerun()

            if peut_modifier():
                with st.expander("➕ Ajouter un contrat au prospect"):
                    up   = st.selectbox("Univers", UNIVERS, key="add_ctp_u")
                    cat_map_p = {"Télécom": CATEGORIES_TELECOM, "Énergie": CATEGORIES_ENERGIE,
                                 "Abonnements": CATEGORIES_ABO}
                    catp = st.selectbox("Catégorie", cat_map_p[up], key="add_ctp_c")
                    fp   = st.text_input("Fournisseur", key="add_ctp_f")
                    nop  = st.text_input("Nom de l'offre", key="add_ctp_no")
                    cmp_ = st.number_input("Coût mensuel (€)", min_value=0.0, step=1.0, key="add_ctp_cm")
                    fin_eng_p = st.date_input("Date de fin d'engagement", value=None,
                                               format="DD/MM/YYYY", key="add_ctp_fin_eng")
                    if st.button("Ajouter le contrat", key="add_ctp_btn"):
                        ajouter_contrat({
                            "prospect_id": int(choix), "univers": up, "categorie": catp,
                            "fournisseur": fp, "nom_offre": nop, "cout_mensuel": cmp_,
                            "type_contrat": "reference_externe",
                            "date_fin_engagement": fin_eng_p.strftime("%d/%m/%Y") if fin_eng_p else "",
                            "notes": "Contrat existant du prospect (appris par le conseiller)",
                            "cree_par": st.session_state.auth_nom_complet,
                        })
                        st.success("Contrat ajouté."); st.rerun()

            st.markdown("##### 📂 Dossier en cours")
            st.caption("Tant que ce dossier n'est pas signé (statut « Actif »), le prospect "
                       "reste ici — il devient client automatiquement dès la signature.")
            dossiers_p = tous_contrats_p[tous_contrats_p["type_contrat"] == "dossier_cmr"] \
                if not tous_contrats_p.empty and "type_contrat" in tous_contrats_p.columns \
                else tous_contrats_p.iloc[0:0]
            if dossiers_p.empty:
                creer_dossier_prospect_ui(p, "fiche_dossier", st.session_state.auth_nom_complet)
            else:
                prenom_nom_p = f"{p.get('prenom','')} {p.get('nom','')}"
                for _, ctd in dossiers_p.iterrows():
                    with st.container(border=True):
                        st.write(f"**{ctd['univers']} – {ctd['categorie']} : "
                                 f"{ctd['nom_offre']} ({ctd['fournisseur']})** · "
                                 f"{ctd['cout_mensuel']} €/mois")
                        _widget_etape_dossier(
                            int(ctd["id"]), ctd.get("statut_contrat"), f"fiche_dossier_{choix}",
                            on_transition=lambda s, _pid=int(choix), _nom=prenom_nom_p:
                                _on_transition_dossier_prospect(s, _pid, _nom, st.session_state.auth_nom_complet))

            st.divider()
            st.markdown("##### 📄 Où en est ce dossier")
            st.caption("Dossier de suivi, stepper, mandats (représentation + honoraires) et historique "
                       "horodaté — un seul endroit, plus besoin de croiser plusieurs écrans.")
            backend_id_prospect = p.get("backend_client_id")
            try:
                dossiers_p_backend = lire_dossiers_client(int(backend_id_prospect) if backend_id_prospect else -1)
            except ApiIndisponible:
                dossiers_p_backend = None
            if dossiers_p_backend is None:
                st.warning("⚠️ Backend indisponible (lancez `uvicorn backend.main:app --reload`) — "
                           "dossier de souscription, mandats et lien client inaccessibles.")
            else:
                if peut_modifier():
                    with st.expander("➕ Créer un dossier"):
                        # Slugs reconnus par backend/services/dossier_engine.py::documents_requis_pour_univers
                        # (déclenche les documents à demander au client) — distinct de la constante UNIVERS
                        # (libellés FR utilisés pour les contrats/offres du CRM Streamlit).
                        univers_dossier_p = {
                            "telecom_mobile": "Télécom — Mobile",
                            "telecom_box": "Télécom — Box / Fibre",
                            "energie": "Énergie — Particulier",
                            "energie_pro": "Énergie — Pro",
                            "assurance_habitation": "Assurance habitation",
                            "alarme": "Alarme / Sécurité",
                            "tpe": "TPE / Terminal de paiement",
                        }
                        u_dos_p = st.selectbox("Univers", list(univers_dossier_p.keys()),
                                                format_func=lambda k: univers_dossier_p[k],
                                                key="dos_univers_prospect")
                        f_dos_p = st.text_input("Fournisseur cible (optionnel)", key="dos_fournisseur_prospect")
                        eco_dos_p = st.number_input("Économie annuelle estimée (€)", min_value=0.0,
                                                     value=safe_float(p.get("economie_estimee_an")),
                                                     step=10.0, key="dos_eco_prospect")
                        if st.button("🚀 Créer le dossier", type="primary", key="btn_creer_dossier_prospect"):
                            try:
                                dossier_nv_p = creer_dossier(p.to_dict(), u_dos_p, f_dos_p, eco_dos_p,
                                                              entite="prospect")
                                enregistrer_action(
                                    "prospect", int(choix), "Dossier créé",
                                    f"Dossier #{dossier_nv_p['id']} ({u_dos_p})")
                                st.session_state["_dossier_a_envoyer_prospect"] = {
                                    "prospect_id": int(choix), "dossier_id": dossier_nv_p["id"],
                                }
                                st.session_state.pop("_dernier_lien_dossier_prospect", None)
                                st.rerun()
                            except ApiIndisponible as exc:
                                st.error(f"Backend indisponible : {exc}")

                a_envoyer_p = st.session_state.get("_dossier_a_envoyer_prospect")
                if a_envoyer_p and a_envoyer_p["prospect_id"] == int(choix):
                    with st.container(border=True):
                        st.success(f"✅ Dossier #{a_envoyer_p['dossier_id']} créé.")
                        st.caption("Comment le prospect préfère-t-il recevoir son lien personnel ?")
                        c_sms_p, c_mail_p = st.columns(2)
                        if c_sms_p.button("📱 Envoyer par SMS", key="btn_envoyer_sms_prospect"):
                            try:
                                envoi_p = envoyer_lien_client(a_envoyer_p["dossier_id"], "sms")
                                enregistrer_action(
                                    "prospect", int(choix), "Lien dossier envoyé par SMS",
                                    f"Dossier #{a_envoyer_p['dossier_id']} — "
                                    f"SMS {'envoyé' if envoi_p['sms_envoye'] else 'NON envoyé'}")
                                st.session_state["_dernier_lien_dossier_prospect"] = {
                                    "prospect_id": int(choix), "dossier_id": a_envoyer_p["dossier_id"],
                                    "url": envoi_p["url"], "canal": "sms", "envoye": envoi_p["sms_envoye"],
                                }
                                del st.session_state["_dossier_a_envoyer_prospect"]
                                st.rerun()
                            except ApiIndisponible as exc:
                                st.error(f"Backend indisponible : {exc}")
                        if c_mail_p.button("✉️ Envoyer par email", key="btn_envoyer_email_prospect"):
                            try:
                                envoi_p = envoyer_lien_client(a_envoyer_p["dossier_id"], "email")
                                enregistrer_action(
                                    "prospect", int(choix), "Lien dossier envoyé par email",
                                    f"Dossier #{a_envoyer_p['dossier_id']} — "
                                    f"email {'envoyé' if envoi_p['email_envoye'] else 'NON envoyé'}")
                                st.session_state["_dernier_lien_dossier_prospect"] = {
                                    "prospect_id": int(choix), "dossier_id": a_envoyer_p["dossier_id"],
                                    "url": envoi_p["url"], "canal": "email", "envoye": envoi_p["email_envoye"],
                                }
                                del st.session_state["_dossier_a_envoyer_prospect"]
                                st.rerun()
                            except ApiIndisponible as exc:
                                st.error(f"Backend indisponible : {exc}")
                        if st.button("✖️ Envoyer plus tard", key="btn_reporter_envoi_prospect"):
                            del st.session_state["_dossier_a_envoyer_prospect"]
                            st.rerun()

                dernier_lien_p = st.session_state.get("_dernier_lien_dossier_prospect")
                if dernier_lien_p and dernier_lien_p["prospect_id"] == int(choix):
                    with st.container(border=True):
                        libelle_canal_p = "SMS" if dernier_lien_p["canal"] == "sms" else "Email"
                        if dernier_lien_p["envoye"]:
                            st.success(f"✅ Lien envoyé par {libelle_canal_p} pour le dossier "
                                       f"#{dernier_lien_p['dossier_id']}.")
                        else:
                            st.warning(f"⚠️ {libelle_canal_p} non envoyé (dossier #{dernier_lien_p['dossier_id']}) — "
                                       "identifiants du fournisseur (Twilio/OVH/Resend) absents de "
                                       "`backend/.env`, ou coordonnées manquantes sur la fiche prospect.")
                            st.caption("📌 Mode test — ouvrez le lien ci-dessous vous-même pour vérifier que "
                                       "tout le parcours client fonctionne (portail, upload documents…), à la "
                                       "place du prospect en attendant les comptes réels.")
                        st.link_button("🔗 Ouvrir le lien du portail client", dernier_lien_p["url"])
                        if st.button("✖️ Masquer", key="btn_fermer_lien_dossier_prospect"):
                            del st.session_state["_dernier_lien_dossier_prospect"]
                            st.rerun()

                if not dossiers_p_backend:
                    st.caption("Aucun dossier créé pour ce prospect.")
                else:
                    options_dos_p = {f"#{d['id']} — {d['univers']} ({d['statut']})": d["id"]
                                      for d in dossiers_p_backend}
                    libelle_dos_p = st.selectbox("Dossier à inspecter", list(options_dos_p.keys()),
                                                  key="dos_inspect_choix_prospect")
                    dossier_id_sel_p = options_dos_p[libelle_dos_p]

                    try:
                        timeline_p = obtenir_timeline_dossier(dossier_id_sel_p)
                        dossier_detail_p = obtenir_dossier(dossier_id_sel_p)
                    except ApiIndisponible as exc:
                        st.error(f"Backend indisponible : {exc}")
                        timeline_p, dossier_detail_p = [], None

                    if timeline_p:
                        icones_etape_p = {"termine": "✅", "en_cours": "🕓", "a_venir": "⚪"}
                        cols_step_p = st.columns(len(timeline_p))
                        for col, etape in zip(cols_step_p, timeline_p):
                            with col:
                                st.markdown(icones_etape_p.get(etape["statut"], "⚪"))
                                st.caption(etape["label"])
                                if etape.get("date"):
                                    st.caption(etape["date"])

                    try:
                        briefing_mandats_p = obtenir_briefing_client(int(backend_id_prospect)) \
                            if backend_id_prospect else None
                    except ApiIndisponible:
                        briefing_mandats_p = None

                    mc1_p, mc2_p = st.columns(2)
                    with mc1_p:
                        st.markdown("**Mandat de représentation (Yousign)**")
                        mandat_repr_p = (briefing_mandats_p or {}).get("mandat_representation")
                        if mandat_repr_p:
                            st.write(f"Statut : **{mandat_repr_p['statut']}**")
                            if mandat_repr_p.get("date_signature"):
                                st.caption(f"Signé le {mandat_repr_p['date_signature']}")
                        else:
                            st.caption("Aucun mandat de représentation envoyé.")

                    with mc2_p:
                        st.markdown("**Mandat d'honoraires**")
                        try:
                            mandat_hon_p = obtenir_mandat_honoraires(dossier_id_sel_p)
                        except ApiIndisponible:
                            mandat_hon_p = None
                        if mandat_hon_p:
                            st.write(f"Statut : **{mandat_hon_p['statut']}** — "
                                     f"{mandat_hon_p['montant']} € ({mandat_hon_p['taux']} %)")
                            if mandat_hon_p["statut"] != "signe" and peut_modifier():
                                signataire_p = st.text_input("Signataire",
                                                              key=f"signataire_hon_prospect_{dossier_id_sel_p}")
                                if st.button("✍️ Marquer les honoraires signés",
                                             key=f"btn_signer_hon_prospect_{dossier_id_sel_p}") and signataire_p:
                                    try:
                                        marquer_signe_honoraires(dossier_id_sel_p, signataire_p)
                                        st.success("Mandat d'honoraires marqué signé.")
                                        st.rerun()
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")
                        else:
                            st.caption("Aucun mandat d'honoraires pour ce dossier.")
                            if peut_modifier():
                                montant_hon_p = st.number_input("Montant honoraires (€)", min_value=0.0,
                                                                 step=10.0,
                                                                 key=f"montant_hon_prospect_{dossier_id_sel_p}")
                                taux_hon_p = st.number_input("Taux (%)", min_value=0.0, step=1.0,
                                                              key=f"taux_hon_prospect_{dossier_id_sel_p}")
                                if st.button("➕ Créer le mandat d'honoraires",
                                             key=f"btn_creer_hon_prospect_{dossier_id_sel_p}"):
                                    try:
                                        creer_mandat_honoraires(dossier_id_sel_p, montant_hon_p, taux_hon_p)
                                        st.success("Mandat d'honoraires créé.")
                                        st.rerun()
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")

                    st.markdown("**📮 Démarches**")
                    try:
                        demarches_info_p = lister_demarches(dossier_id_sel_p)
                    except ApiIndisponible as exc:
                        st.error(f"Backend indisponible : {exc}")
                        demarches_info_p = {"existantes": [], "requises_non_creees": []}

                    if peut_modifier():
                        for requise_p in demarches_info_p["requises_non_creees"]:
                            if st.button(f"➕ Créer « {requise_p['label']} »",
                                         key=f"btn_creer_dem_prospect_{dossier_id_sel_p}_{requise_p['type_demarche']}"):
                                try:
                                    creer_demarche(dossier_id_sel_p, requise_p["type_demarche"])
                                    st.success("Démarche créée.")
                                    st.rerun()
                                except ApiIndisponible as exc:
                                    st.error(f"Backend indisponible : {exc}")

                    for dem_p in demarches_info_p["existantes"]:
                        with st.expander(f"{dem_p['type_demarche']} — statut : {dem_p['statut']}"):
                            champs_vides_p = {c: v for c, v in (dem_p.get("donnees_requises") or {}).items()
                                              if v.get("requis") and not v.get("valeur")}
                            if champs_vides_p and peut_modifier():
                                saisies_p = {c: st.text_input(v["label"], key=f"champ_dem_prospect_{dem_p['id']}_{c}")
                                             for c, v in champs_vides_p.items()}
                                if st.button("💾 Enregistrer les champs",
                                             key=f"btn_champs_dem_prospect_{dem_p['id']}") and all(saisies_p.values()):
                                    try:
                                        renseigner_champs_demarche(dem_p["id"], saisies_p)
                                        st.success("Champs enregistrés.")
                                        st.rerun()
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")
                            elif dem_p["statut"] == "a_generer" and peut_modifier():
                                if st.button("📄 Générer le document", key=f"btn_gen_dem_prospect_{dem_p['id']}"):
                                    try:
                                        generer_demarche(dem_p["id"])
                                        st.info("Génération lancée.")
                                        st.rerun()
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")
                            elif dem_p["statut"] == "generee":
                                if peut_modifier():
                                    try:
                                        st.link_button("📥 Voir le document", demarche_document_url(dem_p["id"]))
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")
                                    if st.button("📮 Envoyer en LRE", key=f"btn_envoyer_dem_prospect_{dem_p['id']}"):
                                        try:
                                            envoyer_demarche(dem_p["id"])
                                            st.info("Envoi lancé.")
                                            st.rerun()
                                        except ApiIndisponible as exc:
                                            st.error(f"Backend indisponible : {exc}")
                            elif dem_p["statut"] in ("envoyee", "accusee"):
                                libelle_p = "accusée" if dem_p["statut"] == "accusee" else "envoyée"
                                st.write(f"{libelle_p.capitalize()} le {dem_p.get('date_envoi', '—')}")
                            elif dem_p["statut"] == "echouee":
                                st.error(f"Échec : {dem_p.get('notes') or 'motif inconnu'}")

                    st.markdown("**Historique du dossier**")
                    notes_dos_p = (dossier_detail_p or {}).get("notes_workflow") or []
                    if not notes_dos_p:
                        st.caption("Aucun évènement enregistré.")
                    else:
                        icones_evt_p = {"transition": "➡️", "note": "📝", "relance_auto": "🔔"}
                        for entree in reversed(notes_dos_p):
                            type_e = entree.get("type", "transition")
                            if type_e == "transition":
                                detail = f"{entree.get('de', '?')} → {entree.get('vers', '?')}"
                                if entree.get("commentaire"):
                                    detail += f" — {entree['commentaire']}"
                            else:
                                detail = entree.get("texte", "")
                            st.caption(f"{icones_evt_p.get(type_e, '•')} {entree.get('date', '')} — "
                                       f"**{entree.get('par', '—')}** — {detail}")

                    if peut_modifier():
                        note_txt_p = st.text_input("Ajouter une note (compte-rendu, remarque…)",
                                                    key=f"note_dos_prospect_{dossier_id_sel_p}")
                        if st.button("Ajouter la note", key=f"btn_note_dos_prospect_{dossier_id_sel_p}") \
                                and note_txt_p:
                            try:
                                ajouter_note_dossier(dossier_id_sel_p, note_txt_p)
                                st.success("Note ajoutée.")
                                st.rerun()
                            except ApiIndisponible as exc:
                                st.error(f"Backend indisponible : {exc}")

            if widget_relance(choix, f"fiche_relance_{choix}"):
                st.success("Relance programmée."); st.rerun()
            with st.expander("🗑️ Supprimer ce prospect"):
                st.warning(f"Cette action est irréversible. Le prospect **{p.get('prenom','')} {p.get('nom','')}** sera définitivement supprimé.")
                if st.button("✅ Confirmer la suppression", key="confirm_del_prospect"):
                    supprimer_prospect(int(choix)); st.warning("Prospect supprimé."); st.rerun()
        else:
            st.caption("🔒 Rôle Lecture — connexion Conseiller ou Admin requise pour modifier.")


# ==============================================================================
#  CLIENTS & CONTRATS
# ==============================================================================
elif menu == "👥 Clients & contrats":
    st.title("👥 Clients & contrats")
    df = lire_clients()
    if df.empty:
        st.info("Aucun client signé.")
    else:
        recherche = st.text_input("🔎 Rechercher (nom, ville, email, réf., opérateur…)",
                                   key="recherche_clients")
        dff = df.copy()
        if recherche:
            ids = recherche_fts("clients", recherche)
            if ids is not None:
                ordre = {i: n for n, i in enumerate(ids)}
                dff = df[df["id"].isin(ids)]
                dff = dff.assign(_rang=dff["id"].map(ordre)).sort_values("_rang").drop(columns="_rang")
            else:
                r   = recherche.lower()
                dff = df[df.apply(lambda row: r in str(row.to_dict()).lower(), axis=1)]

        col_m1, col_m2 = st.columns([3, 1])
        col_m2.metric("Clients trouvés", len(dff))

        cols_aff = ["ref","prenom","nom","telephone","email","ville","operateur_actuel",
                    "offre_actuelle","cout_mensuel_actuel","economie_estimee_an",
                    "cree_par","date_creation"]
        cols_aff = [c for c in cols_aff if c in dff.columns]
        st.dataframe(dff[cols_aff], hide_index=True, use_container_width=True)

        excel_bytes_c = exporter_excel(dff[cols_aff], nom_feuille="Clients")
        if excel_bytes_c:
            st.download_button("📥 Exporter en Excel (.xlsx)", data=excel_bytes_c,
                                file_name=f"clients_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="export_excel_clients")
        elif not OPENPYXL_OK:
            st.caption("Export Excel indisponible (pip install openpyxl)")

        if dff.empty:
            st.info("Aucun client ne correspond à votre recherche.")
        st.divider()
        st.markdown("#### 📂 Fiche client")
        if not dff.empty:
            ids_dispo_client = dff["id"].tolist()
            focus_client = st.session_state.pop("_focus_client_id", None)
            if focus_client is not None and focus_client in ids_dispo_client:
                st.session_state["fiche_client_choix"] = focus_client
            choix = st.selectbox("Client", ids_dispo_client,
                format_func=lambda i: (
                    f"{df[df['id']==i]['prenom'].values[0]} "
                    f"{df[df['id']==i]['nom'].values[0]} (#{i})"),
                key="fiche_client_choix")
            cl = df[df["id"] == choix].iloc[0]

            # Accès sécurisé : .get() évite KeyError sur anciennes BDD
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Réf :** {cl.get('ref', '')}")
            c1.write(f"**Tél :** {cl.get('telephone', '')}")
            c1.write(f"**Email :** {cl.get('email', '')}")
            c2.write(f"**Ville :** {cl.get('ville', '')} ({cl.get('code_postal', '')})")
            c2.write(f"**Opérateur :** {cl.get('operateur_actuel', '—')}")
            c2.write(f"**Offre actuelle :** {cl.get('offre_actuelle', '—')}")
            c3.write(f"**Satisfaction réseau :** {cl.get('satisfaction_reseau', '—')}")
            c3.write(f"**Veut rester :** {cl.get('veut_rester', '—')}")
            c3.write(f"**Débits :** ⬇️ {cl.get('speed_down', 0)} / ⬆️ {cl.get('speed_up', 0)} Mbps")
            c1.write(f"**Adresse :** {cl.get('adresse') or '—'}")
            if cl.get("cree_par"):
                st.caption(f"Créé par : **{cl.get('cree_par')}** le {cl.get('date_creation', '')}")

            st.markdown("##### ⏰ Relance")
            st.write(f"**Statut :** {cl.get('statut_relance') or 'Aucune'}  ·  "
                     f"**Prochaine relance :** {cl.get('date_relance') or '—'}")
            if peut_modifier():
                with st.expander("📅 Programmer / reprogrammer une relance"):
                    if widget_relance_client(int(choix), f"fiche_relance_client_{choix}"):
                        st.success("Relance programmée."); st.rerun()

            if peut_modifier():
                with st.expander("✏️ Modifier les informations du client"):
                    champs = {"telephone":"Téléphone","email":"Email","adresse":"Adresse","ville":"Ville",
                              "operateur_actuel":"Opérateur","offre_actuelle":"Offre actuelle",
                              "cout_mensuel_actuel":"Coût actuel (€)","satisfaction_reseau":"Satisfaction réseau",
                              "veut_rester":"Veut rester","notes":"Notes"}
                    with st.form(key=f"form_edit_client_{choix}"):
                        # .get() avec fallback vide pour les colonnes ajoutées par migration
                        valeurs_c = {champ: st.text_input(label, str(cl.get(champ, "")), key=f"edit_c_{champ}")
                                     for champ, label in champs.items()}
                        if st.form_submit_button("💾 Enregistrer"):
                            for champ, val in valeurs_c.items():
                                v = float(val) if champ == "cout_mensuel_actuel" else val
                                maj_client(int(choix), champ, v)
                            st.success("Client mis à jour."); st.rerun()

            st.markdown("##### 📑 Contrats du client")
            contrats = lire_contrats_client(int(choix))
            if contrats.empty:
                st.info("Aucun contrat rattaché.")
            else:
                cols_ct = ["id","univers","categorie","fournisseur","nom_offre",
                           "cout_mensuel","economie_mensuelle","statut_contrat",
                           "cree_par","date_souscription","date_fin_engagement"]
                cols_ct = [c for c in cols_ct if c in contrats.columns]
                st.dataframe(contrats[cols_ct], hide_index=True, use_container_width=True)
                a, b = st.columns(2)
                a.metric("Total mensuel",    f"{round(contrats['cout_mensuel'].sum(),2)} €")
                b.metric("Économie mensuelle",f"{round(contrats['economie_mensuelle'].sum(),2)} €")

                if peut_modifier():
                    with st.expander("✏️ Modifier / supprimer un contrat"):
                        ctid = st.selectbox("Contrat", contrats["id"].tolist(),
                            format_func=lambda i: f"#{i} · {contrats[contrats['id']==i]['nom_offre'].values[0]}")
                        ct = contrats[contrats["id"] == ctid].iloc[0]
                        off_match = lire_offres()
                        off_match = off_match[(off_match["fournisseur"] == ct["fournisseur"]) &
                                               (off_match["nom_offre"] == ct["nom_offre"])]
                        if not off_match.empty and off_match.iloc[0].get("url_souscription"):
                            row_off = off_match.iloc[0]
                            bouton_pre_remplir(
                                {"fournisseur": ct["fournisseur"], "nom_offre": ct["nom_offre"],
                                 "url_souscription": row_off["url_souscription"],
                                 "code_affiliation": row_off.get("code_affiliation", "")},
                                cl, "client", int(choix), key=f"presous_ctr_{ctid}")
                        nv_offre  = st.text_input("Nom de l'offre", ct["nom_offre"], key="ct_nom")
                        nv_cout   = st.number_input("Coût mensuel (€)", min_value=0.0,
                                                    value=float(ct["cout_mensuel"]), step=1.0, key="ct_cout")
                        nv_fin_eng = st.date_input(
                            "Date de fin d'engagement", value=parser_date_relance(ct.get("date_fin_engagement")),
                            format="DD/MM/YYYY", key="ct_fin_eng")
                        cx, cy = st.columns(2)
                        if cx.button("💾 Enregistrer les modifs"):
                            maj_contrat(int(ctid), "nom_offre",      nv_offre)
                            maj_contrat(int(ctid), "cout_mensuel",   nv_cout)
                            maj_contrat(int(ctid), "date_fin_engagement",
                                        nv_fin_eng.strftime("%d/%m/%Y") if nv_fin_eng else "")
                            st.success("Contrat mis à jour."); st.rerun()
                        if cy.button("🗑️ Supprimer ce contrat"):
                            supprimer_contrat(int(ctid)); st.warning("Contrat supprimé."); st.rerun()

                        st.markdown("###### 🔄 Étape du dossier")
                        _widget_etape_dossier(int(ctid), ct.get("statut_contrat"), f"ct_{choix}")

            if peut_modifier():
                with st.expander("➕ Ajouter un contrat à ce client"):
                    u   = st.selectbox("Univers", UNIVERS, key="add_ctr_u")
                    cat_map = {"Télécom": CATEGORIES_TELECOM, "Énergie": CATEGORIES_ENERGIE,
                               "Abonnements": CATEGORIES_ABO}
                    cat = st.selectbox("Catégorie", cat_map[u], key="add_ctr_c")
                    f   = st.text_input("Fournisseur",   key="add_ctr_f")
                    no  = st.text_input("Nom de l'offre",key="add_ctr_no")
                    cm  = st.number_input("Coût mensuel (€)", min_value=0.0, step=1.0, key="add_ctr_cm")
                    em  = st.number_input("Économie mensuelle (€)", min_value=0.0, step=1.0, key="add_ctr_em")
                    ref_c = st.text_input("Référence contrat", key="add_ctr_ref")
                    fin_eng = st.date_input("Date de fin d'engagement", value=None,
                                             format="DD/MM/YYYY", key="add_ctr_fin_eng")
                    if st.button("Ajouter le contrat"):
                        ajouter_contrat({
                            "client_id": int(choix), "univers": u, "categorie": cat,
                            "fournisseur": f, "nom_offre": no, "cout_mensuel": cm,
                            "economie_mensuelle": em, "reference_contrat": ref_c,
                            "statut_contrat": STATUT_CONTRAT_INITIAL,
                            "date_fin_engagement": fin_eng.strftime("%d/%m/%Y") if fin_eng else "",
                            "notes": "Ajout manuel",
                            "cree_par": st.session_state.auth_nom_complet,
                        })
                        st.success("Contrat ajouté."); st.rerun()

                with st.expander("🗑️ Supprimer ce client"):
                    st.error(f"⚠️ Supprime **{cl.get('prenom','')} {cl.get('nom','')}** ET tous ses contrats. Irréversible.")
                    if st.button("✅ Confirmer la suppression du client", key="confirm_del_client"):
                        supprimer_client(int(choix)); st.warning("Client et contrats supprimés."); st.rerun()
            else:
                st.caption("🔒 Rôle Lecture — connexion Conseiller ou Admin requise pour modifier.")

            st.divider()
            st.markdown("##### 📄 Où en est ce dossier")
            st.caption("Dossier de suivi, stepper, mandats (représentation + honoraires) et historique "
                       "horodaté — un seul endroit, plus besoin de croiser plusieurs écrans.")
            try:
                dossiers_cl = lire_dossiers_client(int(choix))
            except ApiIndisponible:
                dossiers_cl = None
            if dossiers_cl is None:
                st.warning("⚠️ Backend indisponible (lancez `uvicorn backend.main:app --reload`) — "
                           "dossier de souscription, mandats et lien client inaccessibles.")
            else:
                if peut_modifier():
                    with st.expander("➕ Créer un dossier"):
                        # Slugs reconnus par backend/services/dossier_engine.py::documents_requis_pour_univers
                        # (déclenche les documents à demander au client) — distinct de la constante UNIVERS
                        # (libellés FR utilisés pour les contrats/offres du CRM Streamlit).
                        univers_dossier = {
                            "telecom_mobile": "Télécom — Mobile",
                            "telecom_box": "Télécom — Box / Fibre",
                            "energie": "Énergie — Particulier",
                            "energie_pro": "Énergie — Pro",
                            "assurance_habitation": "Assurance habitation",
                            "alarme": "Alarme / Sécurité",
                            "tpe": "TPE / Terminal de paiement",
                        }
                        u_dos = st.selectbox("Univers", list(univers_dossier.keys()),
                                              format_func=lambda k: univers_dossier[k], key="dos_univers")
                        f_dos = st.text_input("Fournisseur cible (optionnel)", key="dos_fournisseur")
                        eco_dos = st.number_input("Économie annuelle estimée (€)", min_value=0.0,
                                                   value=safe_float(cl.get("economie_estimee_an")),
                                                   step=10.0, key="dos_eco")
                        if st.button("🚀 Créer le dossier", type="primary", key="btn_creer_dossier"):
                            try:
                                dossier_nv = creer_dossier(cl.to_dict(), u_dos, f_dos, eco_dos)
                                enregistrer_action(
                                    "client", int(choix), "Dossier créé",
                                    f"Dossier #{dossier_nv['id']} ({u_dos})")
                                # Mémorisé en session (et non affiché seulement avant le st.rerun()
                                # ci-dessous, sans quoi le message disparaîtrait avant que tu aies pu
                                # choisir le canal d'envoi) — affiché juste après l'expander, persistant
                                # tant qu'un nouveau dossier n'est pas créé.
                                st.session_state["_dossier_a_envoyer"] = {
                                    "client_id": int(choix), "dossier_id": dossier_nv["id"],
                                }
                                st.session_state.pop("_dernier_lien_dossier", None)
                                st.rerun()
                            except ApiIndisponible as exc:
                                st.error(f"Backend indisponible : {exc}")

                a_envoyer = st.session_state.get("_dossier_a_envoyer")
                if a_envoyer and a_envoyer["client_id"] == int(choix):
                    with st.container(border=True):
                        st.success(f"✅ Dossier #{a_envoyer['dossier_id']} créé.")
                        st.caption("Comment le client préfère-t-il recevoir son lien personnel ?")
                        c_sms, c_mail = st.columns(2)
                        if c_sms.button("📱 Envoyer par SMS", key="btn_envoyer_sms"):
                            try:
                                envoi = envoyer_lien_client(a_envoyer["dossier_id"], "sms")
                                enregistrer_action(
                                    "client", int(choix), "Lien dossier envoyé par SMS",
                                    f"Dossier #{a_envoyer['dossier_id']} — "
                                    f"SMS {'envoyé' if envoi['sms_envoye'] else 'NON envoyé'}")
                                st.session_state["_dernier_lien_dossier"] = {
                                    "client_id": int(choix), "dossier_id": a_envoyer["dossier_id"],
                                    "url": envoi["url"], "canal": "sms", "envoye": envoi["sms_envoye"],
                                }
                                del st.session_state["_dossier_a_envoyer"]
                                st.rerun()
                            except ApiIndisponible as exc:
                                st.error(f"Backend indisponible : {exc}")
                        if c_mail.button("✉️ Envoyer par email", key="btn_envoyer_email"):
                            try:
                                envoi = envoyer_lien_client(a_envoyer["dossier_id"], "email")
                                enregistrer_action(
                                    "client", int(choix), "Lien dossier envoyé par email",
                                    f"Dossier #{a_envoyer['dossier_id']} — "
                                    f"email {'envoyé' if envoi['email_envoye'] else 'NON envoyé'}")
                                st.session_state["_dernier_lien_dossier"] = {
                                    "client_id": int(choix), "dossier_id": a_envoyer["dossier_id"],
                                    "url": envoi["url"], "canal": "email", "envoye": envoi["email_envoye"],
                                }
                                del st.session_state["_dossier_a_envoyer"]
                                st.rerun()
                            except ApiIndisponible as exc:
                                st.error(f"Backend indisponible : {exc}")
                        if st.button("✖️ Envoyer plus tard", key="btn_reporter_envoi"):
                            del st.session_state["_dossier_a_envoyer"]
                            st.rerun()

                dernier_lien = st.session_state.get("_dernier_lien_dossier")
                if dernier_lien and dernier_lien["client_id"] == int(choix):
                    with st.container(border=True):
                        libelle_canal = "SMS" if dernier_lien["canal"] == "sms" else "Email"
                        if dernier_lien["envoye"]:
                            st.success(f"✅ Lien envoyé par {libelle_canal} pour le dossier #{dernier_lien['dossier_id']}.")
                        else:
                            st.warning(f"⚠️ {libelle_canal} non envoyé (dossier #{dernier_lien['dossier_id']}) — "
                                       "identifiants du fournisseur (Twilio/OVH/Resend) absents de "
                                       "`backend/.env`, ou coordonnées manquantes sur la fiche client.")
                            st.caption("📌 Mode test — ouvrez le lien ci-dessous vous-même pour vérifier que "
                                       "tout le parcours client fonctionne (portail, upload documents…), à la "
                                       "place du client en attendant les comptes réels.")
                        st.link_button("🔗 Ouvrir le lien du portail client", dernier_lien["url"])
                        if st.button("✖️ Masquer", key="btn_fermer_lien_dossier"):
                            del st.session_state["_dernier_lien_dossier"]
                            st.rerun()

                if not dossiers_cl:
                    st.caption("Aucun dossier créé pour ce client.")
                else:
                    options_dos = {f"#{d['id']} — {d['univers']} ({d['statut']})": d["id"] for d in dossiers_cl}
                    libelle_dos = st.selectbox("Dossier à inspecter", list(options_dos.keys()),
                                                key="dos_inspect_choix")
                    dossier_id_sel = options_dos[libelle_dos]

                    try:
                        timeline = obtenir_timeline_dossier(dossier_id_sel)
                        dossier_detail = obtenir_dossier(dossier_id_sel)
                    except ApiIndisponible as exc:
                        st.error(f"Backend indisponible : {exc}")
                        timeline, dossier_detail = [], None

                    if timeline:
                        icones_etape = {"termine": "✅", "en_cours": "🕓", "a_venir": "⚪"}
                        cols_step = st.columns(len(timeline))
                        for col, etape in zip(cols_step, timeline):
                            with col:
                                st.markdown(icones_etape.get(etape["statut"], "⚪"))
                                st.caption(etape["label"])
                                if etape.get("date"):
                                    st.caption(etape["date"])

                    try:
                        briefing_mandats = obtenir_briefing_client(int(choix))
                    except ApiIndisponible:
                        briefing_mandats = None

                    mc1, mc2 = st.columns(2)
                    with mc1:
                        st.markdown("**Mandat de représentation (Yousign)**")
                        mandat_repr = (briefing_mandats or {}).get("mandat_representation")
                        if mandat_repr:
                            st.write(f"Statut : **{mandat_repr['statut']}**")
                            if mandat_repr.get("date_signature"):
                                st.caption(f"Signé le {mandat_repr['date_signature']}")
                        else:
                            st.caption("Aucun mandat de représentation envoyé.")

                    with mc2:
                        st.markdown("**Mandat d'honoraires**")
                        try:
                            mandat_hon = obtenir_mandat_honoraires(dossier_id_sel)
                        except ApiIndisponible:
                            mandat_hon = None
                        if mandat_hon:
                            st.write(f"Statut : **{mandat_hon['statut']}** — "
                                     f"{mandat_hon['montant']} € ({mandat_hon['taux']} %)")
                            if mandat_hon["statut"] != "signe" and peut_modifier():
                                signataire = st.text_input("Signataire", key=f"signataire_hon_{dossier_id_sel}")
                                if st.button("✍️ Marquer les honoraires signés",
                                             key=f"btn_signer_hon_{dossier_id_sel}") and signataire:
                                    try:
                                        marquer_signe_honoraires(dossier_id_sel, signataire)
                                        st.success("Mandat d'honoraires marqué signé.")
                                        st.rerun()
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")
                        else:
                            st.caption("Aucun mandat d'honoraires pour ce dossier.")
                            if peut_modifier():
                                montant_hon = st.number_input("Montant honoraires (€)", min_value=0.0,
                                                               step=10.0, key=f"montant_hon_{dossier_id_sel}")
                                taux_hon = st.number_input("Taux (%)", min_value=0.0, step=1.0,
                                                            key=f"taux_hon_{dossier_id_sel}")
                                if st.button("➕ Créer le mandat d'honoraires",
                                             key=f"btn_creer_hon_{dossier_id_sel}"):
                                    try:
                                        creer_mandat_honoraires(dossier_id_sel, montant_hon, taux_hon)
                                        st.success("Mandat d'honoraires créé.")
                                        st.rerun()
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")

                    st.markdown("**📮 Démarches**")
                    try:
                        demarches_info = lister_demarches(dossier_id_sel)
                    except ApiIndisponible as exc:
                        st.error(f"Backend indisponible : {exc}")
                        demarches_info = {"existantes": [], "requises_non_creees": []}

                    if peut_modifier():
                        for requise in demarches_info["requises_non_creees"]:
                            if st.button(f"➕ Créer « {requise['label']} »",
                                         key=f"btn_creer_dem_{dossier_id_sel}_{requise['type_demarche']}"):
                                try:
                                    creer_demarche(dossier_id_sel, requise["type_demarche"])
                                    st.success("Démarche créée.")
                                    st.rerun()
                                except ApiIndisponible as exc:
                                    st.error(f"Backend indisponible : {exc}")

                    for dem in demarches_info["existantes"]:
                        with st.expander(f"{dem['type_demarche']} — statut : {dem['statut']}"):
                            champs_vides = {c: v for c, v in (dem.get("donnees_requises") or {}).items()
                                            if v.get("requis") and not v.get("valeur")}
                            if champs_vides and peut_modifier():
                                saisies = {c: st.text_input(v["label"], key=f"champ_dem_{dem['id']}_{c}")
                                           for c, v in champs_vides.items()}
                                if st.button("💾 Enregistrer les champs",
                                             key=f"btn_champs_dem_{dem['id']}") and all(saisies.values()):
                                    try:
                                        renseigner_champs_demarche(dem["id"], saisies)
                                        st.success("Champs enregistrés.")
                                        st.rerun()
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")
                            elif dem["statut"] == "a_generer" and peut_modifier():
                                if st.button("📄 Générer le document", key=f"btn_gen_dem_{dem['id']}"):
                                    try:
                                        generer_demarche(dem["id"])
                                        st.info("Génération lancée.")
                                        st.rerun()
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")
                            elif dem["statut"] == "generee":
                                if peut_modifier():
                                    try:
                                        st.link_button("📥 Voir le document", demarche_document_url(dem["id"]))
                                    except ApiIndisponible as exc:
                                        st.error(f"Backend indisponible : {exc}")
                                    if st.button("📮 Envoyer en LRE", key=f"btn_envoyer_dem_{dem['id']}"):
                                        try:
                                            envoyer_demarche(dem["id"])
                                            st.info("Envoi lancé.")
                                            st.rerun()
                                        except ApiIndisponible as exc:
                                            st.error(f"Backend indisponible : {exc}")
                            elif dem["statut"] in ("envoyee", "accusee"):
                                libelle = "accusée" if dem["statut"] == "accusee" else "envoyée"
                                st.write(f"{libelle.capitalize()} le {dem.get('date_envoi', '—')}")
                            elif dem["statut"] == "echouee":
                                st.error(f"Échec : {dem.get('notes') or 'motif inconnu'}")

                    st.markdown("**Historique du dossier**")
                    notes_dos = (dossier_detail or {}).get("notes_workflow") or []
                    if not notes_dos:
                        st.caption("Aucun évènement enregistré.")
                    else:
                        icones_evt = {"transition": "➡️", "note": "📝", "relance_auto": "🔔"}
                        for entree in reversed(notes_dos):
                            type_e = entree.get("type", "transition")
                            if type_e == "transition":
                                detail = f"{entree.get('de', '?')} → {entree.get('vers', '?')}"
                                if entree.get("commentaire"):
                                    detail += f" — {entree['commentaire']}"
                            else:
                                detail = entree.get("texte", "")
                            st.caption(f"{icones_evt.get(type_e, '•')} {entree.get('date', '')} — "
                                       f"**{entree.get('par', '—')}** — {detail}")

                    if peut_modifier():
                        note_txt = st.text_input("Ajouter une note (compte-rendu, remarque…)",
                                                  key=f"note_dos_{dossier_id_sel}")
                        if st.button("Ajouter la note", key=f"btn_note_dos_{dossier_id_sel}") and note_txt:
                            try:
                                ajouter_note_dossier(dossier_id_sel, note_txt)
                                st.success("Note ajoutée.")
                                st.rerun()
                            except ApiIndisponible as exc:
                                st.error(f"Backend indisponible : {exc}")

            st.divider()
            st.markdown("##### 📋 Briefing avant appel")
            st.caption("Dernière facture analysée, en un coup d'œil — à consulter juste avant "
                       "de décrocher le téléphone.")
            if peut_modifier():
                with st.expander("🧾 Analyser une facture (avant l'appel)"):
                    fact_up = st.file_uploader("Facture PDF récente du client (télécom/énergie)",
                                                type=["pdf"], key="fact_briefing_upload")
                    if fact_up and st.button("🔎 Analyser et enregistrer",
                                              key="btn_analyser_facture_briefing"):
                        try:
                            resultat_f = analyser_facture_client(fact_up.getvalue(), fact_up.name, int(choix))
                            enregistrer_action(
                                "client", int(choix), "Facture analysée",
                                f"{resultat_f.get('operateur','—')} — {resultat_f.get('prix_ttc',0)} €/mois TTC")
                            st.success("Facture analysée et enregistrée.")
                            st.session_state["briefing_client_id"] = int(choix)
                            st.rerun()
                        except ApiIndisponible as exc:
                            st.error(f"Backend indisponible : {exc}")

            if st.button("🔄 Charger / actualiser le briefing", key="btn_charger_briefing"):
                st.session_state["briefing_client_id"] = int(choix)

            if st.session_state.get("briefing_client_id") == int(choix):
                try:
                    briefing = obtenir_briefing_client(int(choix))
                except ApiIndisponible as exc:
                    st.error(f"Backend indisponible : {exc}")
                    briefing = None
                if briefing:
                    fact = briefing.get("derniere_facture")
                    if fact:
                        st.markdown("**Dernière facture analysée :**")
                        cf1, cf2, cf3 = st.columns(3)
                        cf1.write(f"Opérateur : **{fact.get('operateur') or '—'}**")
                        cf1.write(f"Prix TTC : **{fact.get('prix_ttc', 0)} €**")
                        cf2.write(f"Data : **{fact.get('data_conso_go', 0)} Go**")
                        cf2.write(f"Engagement : **{fact.get('engagement_mois', 0)} mois**")
                        cf3.write(f"Fin d'engagement : **{fact.get('date_fin_engagement') or '—'}**")
                        cf3.write(f"IBAN prélèvement : **{fact.get('iban_prelevement') or '—'}**")
                        if fact.get("options"):
                            st.caption("Options : " + ", ".join(fact["options"]))
                        st.caption(f"Analysée le {fact.get('date_analyse','—')} par {fact.get('analyse_par','—')}")
                    else:
                        st.caption("Aucune facture analysée pour ce client pour l'instant.")

            st.divider()
            st.markdown("##### 🕒 Historique des actions")
            hist = lire_historique("client", int(choix))
            if hist.empty:
                st.caption("Aucune action enregistrée pour cette fiche.")
            else:
                cols_h = ["date_action", "auteur", "action", "details"]
                st.dataframe(hist[cols_h], hide_index=True, use_container_width=True)


# ==============================================================================
#  FACTURATION — devis d'honoraires, mandat, suivi de paiement
# ==============================================================================
elif menu == "🧾 Facturation":
    st.title("🧾 Facturation")
    df_f = lire_factures()

    statuts_dispo_f = ["Tous"] + STATUTS_FACTURE
    col_f1, col_f2  = st.columns([2, 3])
    filtre_statut_f = col_f1.selectbox("Filtrer par statut", statuts_dispo_f, key="filtre_statut_factures")
    col_f2.metric("Total devis/factures", len(df_f))

    dff_f = df_f if filtre_statut_f == "Tous" else df_f[df_f["statut"] == filtre_statut_f]
    if df_f.empty:
        st.info("Aucun devis créé pour l'instant.")
    elif dff_f.empty:
        st.info("Aucun devis avec ce statut.")
    else:
        cols_f = ["reference", "prenom", "nom", "telephone", "montant_honoraires", "statut",
                  "date_creation", "date_paiement", "mandat_signe", "cree_par"]
        cols_f = [c for c in cols_f if c in dff_f.columns]
        st.dataframe(dff_f[cols_f], hide_index=True, use_container_width=True)

    st.divider()

    if peut_modifier():
        with st.expander("➕ Créer un devis d'honoraires"):
            df_p_choix = lire_prospects()
            if df_p_choix.empty:
                st.info("Aucun prospect enregistré. Enregistrez d'abord un prospect depuis le diagnostic.")
            else:
                pid_sel = st.selectbox("Prospect", df_p_choix["id"].tolist(),
                    format_func=lambda i: (
                        f"{df_p_choix[df_p_choix['id']==i]['prenom'].values[0]} "
                        f"{df_p_choix[df_p_choix['id']==i]['nom'].values[0]} (#{i})"),
                    key="fact_sel_prospect")
                p_sel        = df_p_choix[df_p_choix["id"] == pid_sel].iloc[0]
                eco_defaut   = max(0.0, safe_float(p_sel.get("economie_estimee_an")))
                taux_defaut  = safe_float(lire_parametre("taux_honoraires_defaut", "20"), 20.0)

                cfa, cfb = st.columns(2)
                eco_saisie = cfa.number_input("Économie annuelle (€)", min_value=0.0,
                                              value=eco_defaut, step=10.0, key="fact_eco")
                taux_saisi = cfb.number_input("Taux d'honoraires (%)", min_value=0.0, max_value=100.0,
                                              value=taux_defaut, step=1.0, key="fact_taux")
                montant = round(eco_saisie * taux_saisi / 100, 2)
                st.info(f"💶 Montant des honoraires : **{montant} €**")

                if st.button("🧾 Créer le devis", type="primary"):
                    fid = creer_facture({
                        "reference":  generer_ref("FAC"),
                        "prospect_id": int(pid_sel),
                        "prenom": p_sel.get("prenom"), "nom": p_sel.get("nom"),
                        "email": p_sel.get("email"),   "telephone": p_sel.get("telephone"),
                        "ville": p_sel.get("ville"),
                        "economie_annuelle": eco_saisie, "taux_honoraires": taux_saisi,
                        "montant_honoraires": montant,   "statut": "Devis envoyé",
                        "cree_par": st.session_state.auth_nom_complet,
                    })
                    st.success(f"Devis créé — dossier #{fid}."); st.rerun()

    st.divider()
    st.markdown("#### 📂 Fiche devis/facture")
    if df_f.empty:
        st.info("Aucun devis à afficher.")
    else:
        fid_choix = st.selectbox("Devis", df_f["id"].tolist(),
            format_func=lambda i: (
                f"{df_f[df_f['id']==i]['reference'].values[0]} — "
                f"{df_f[df_f['id']==i]['prenom'].values[0]} {df_f[df_f['id']==i]['nom'].values[0]}"),
            key="fact_sel_fiche")
        f = df_f[df_f["id"] == fid_choix].iloc[0].to_dict()

        c1, c2, c3 = st.columns(3)
        c1.write(f"**Client :** {f.get('prenom','')} {f.get('nom','')}")
        c1.write(f"**Tél :** {f.get('telephone','')}")
        c2.write(f"**Économie annuelle :** {f.get('economie_annuelle',0)} €/an")
        c2.write(f"**Taux :** {f.get('taux_honoraires',0)} %")
        c3.metric("Montant honoraires", f"{f.get('montant_honoraires',0)} €")
        c3.write(f"**Statut :** {f.get('statut','')}")

        pdf_devis  = generer_pdf_devis(f, st.session_state.nom_societe)
        pdf_mandat = generer_pdf_mandat(f, st.session_state.nom_societe)
        dcol1, dcol2 = st.columns(2)
        if pdf_devis:
            dcol1.download_button("📄 Télécharger le devis", data=pdf_devis,
                file_name=f"devis_{f.get('reference','')}.pdf", mime="application/pdf",
                key=f"dl_devis_{fid_choix}")
        if pdf_mandat:
            dcol2.download_button("📄 Télécharger le mandat", data=pdf_mandat,
                file_name=f"mandat_{f.get('reference','')}.pdf", mime="application/pdf",
                key=f"dl_mandat_{fid_choix}")

        if peut_modifier():
            st.markdown("##### 🔄 Statut du dossier")
            statut_actuel = f.get("statut") or "Devis envoyé"
            idx_statut    = STATUTS_FACTURE.index(statut_actuel) if statut_actuel in STATUTS_FACTURE else 0
            if idx_statut < len(STATUTS_FACTURE) - 1:
                prochain = STATUTS_FACTURE[idx_statut + 1]
                labels   = {"Payé": "✅ Marquer payé", "Démarches en cours": "🔧 Démarches en cours",
                            "Terminé": "🏁 Marquer terminé"}
                if st.button(labels.get(prochain, f"➡️ {prochain}"), key=f"statut_next_{fid_choix}"):
                    changer_statut(int(fid_choix), prochain)
                    st.success(f"Statut mis à jour : {prochain}."); st.rerun()
            else:
                st.success("✅ Dossier terminé.")

            st.markdown("##### ✍️ Mandat")
            if f.get("mandat_signe"):
                st.success(f"Signé par **{f.get('mandat_signataire','')}** "
                           f"le **{f.get('mandat_date_signature','')}**.")
            else:
                with st.form(key=f"form_mandat_{fid_choix}"):
                    nom_sign  = st.text_input("Nom du signataire",
                        value=f"{f.get('prenom','')} {f.get('nom','')}".strip())
                    date_sign = st.date_input("Date de signature", value=datetime.now().date())
                    if st.form_submit_button("✅ Marquer le mandat comme signé"):
                        marquer_mandat_signe(int(fid_choix), nom_sign, date_sign.strftime("%d/%m/%Y"))
                        st.success("Mandat marqué comme signé."); st.rerun()

        if f.get("statut") in ("Payé", "Démarches en cours", "Terminé"):
            st.markdown("##### 📄 Restitution complète (post-paiement)")
            personne, recos_post = _recos_post_paiement(f)
            if not recos_post:
                st.caption("Aucune offre enregistrée pour ce dossier (prospect sans offre cochée, "
                           "ou client sans contrat) — rien à restituer automatiquement.")
            else:
                pdf_complet = generer_pdf_restitution(personne, recos_post, st.session_state.nom_societe)
                if pdf_complet:
                    st.download_button("📄 Télécharger le PDF complet", data=pdf_complet,
                        file_name=f"bilan_complet_{f.get('reference','')}.pdf", mime="application/pdf",
                        key=f"dl_complet_{fid_choix}")


# ==============================================================================
#  ADMIN
# ==============================================================================
elif menu == "🛠️ Admin":
    st.title("🛠️ Administration")
    if not est_admin():
        st.warning("Accès réservé à l'administrateur.")
        st.stop()

    st.success(f"Mode administrateur — connecté en tant que **{st.session_state.auth_nom_complet}**.")

    tab_users, tab_cat, tab_add, tab_demo, tab_mail, tab_fact, tab_ocr, tab_veille = st.tabs(
        ["👤 Utilisateurs", "📚 Catalogue", "➕ Ajouter une offre", "⚡ Pré-remplir (démo)",
         "📧 Email", "💶 Facturation", "🔍 OCR Vision", "📈 Veille prix"])

    # ---- UTILISATEURS (NOUVEAU Étape 1) ----
    with tab_users:
        st.markdown("### Gestion des utilisateurs")
        df_u = lire_utilisateurs()
        if not df_u.empty:
            st.dataframe(df_u, hide_index=True, use_container_width=True)

        st.divider()
        st.markdown("#### ➕ Créer un compte")
        cu1, cu2 = st.columns(2)
        new_login   = cu1.text_input("Identifiant (login)",          key="create_login")
        new_nom     = cu2.text_input("Nom complet",                   key="create_nom")
        new_pwd     = cu1.text_input("Mot de passe",   type="password", key="create_pwd")
        new_pwd2    = cu2.text_input("Confirmer le mot de passe", type="password", key="create_pwd2")
        new_role    = st.selectbox("Rôle", ROLES, index=1, key="create_role")
        if st.button("Créer le compte", type="primary", key="btn_create_user"):
            if not new_login or not new_nom or not new_pwd:
                st.warning("Tous les champs sont obligatoires.")
            elif new_pwd != new_pwd2:
                st.error("Les mots de passe ne correspondent pas.")
            elif len(new_pwd) < 8:
                st.error("Le mot de passe doit contenir au moins 8 caractères.")
            else:
                ok, msg = creer_utilisateur(new_login, new_nom, new_pwd, new_role)
                (st.success if ok else st.error)(msg)
                if ok: st.rerun()

        if not df_u.empty:
            st.divider()
            st.markdown("#### ✏️ Modifier un compte")
            uid_sel = st.selectbox("Utilisateur", df_u["id"].tolist(),
                format_func=lambda i: f"{df_u[df_u['id']==i]['nom_complet'].values[0]} (@{df_u[df_u['id']==i]['username'].values[0]})",
                key="sel_edit_user")
            user_sel = df_u[df_u["id"] == uid_sel].iloc[0]

            col_a, col_b = st.columns(2)
            nv_nom  = col_a.text_input("Nom complet (modifier)",    user_sel["nom_complet"], key="edit_u_nom")
            nv_role = col_b.selectbox("Rôle",                       ROLES,
                index=ROLES.index(user_sel["role"]) if user_sel["role"] in ROLES else 1, key="edit_u_role")
            nv_actif = st.checkbox("Compte actif", value=bool(user_sel["actif"]), key="edit_u_actif")

            col_c, col_d = st.columns(2)
            nv_pwd  = col_c.text_input("Nouveau mot de passe (vide = inchangé)", type="password", key="edit_u_pwd")
            nv_pwd2 = col_d.text_input("Confirmer le nouveau mot de passe",      type="password", key="edit_u_pwd2")

            if st.button("💾 Enregistrer les modifications", key="btn_save_user"):
                if uid_sel == st.session_state.auth_user_id and nv_role != "Admin":
                    st.error("Vous ne pouvez pas vous retirer le rôle Admin.")
                else:
                    maj_utilisateur(int(uid_sel), "nom_complet", nv_nom)
                    maj_utilisateur(int(uid_sel), "role",        nv_role)
                    maj_utilisateur(int(uid_sel), "actif",       1 if nv_actif else 0)
                    if nv_pwd:
                        if nv_pwd != nv_pwd2:
                            st.error("Les mots de passe ne correspondent pas.")
                        elif len(nv_pwd) < 8:
                            st.error("Minimum 8 caractères.")
                        else:
                            maj_utilisateur(int(uid_sel), "password_hash", hash_password(nv_pwd))
                            st.success("Mot de passe mis à jour.")
                    st.success("Compte mis à jour."); st.rerun()

            if st.button("🗑️ Supprimer ce compte", key="btn_del_user"):
                if uid_sel == st.session_state.auth_user_id:
                    st.error("Vous ne pouvez pas supprimer votre propre compte.")
                else:
                    supprimer_utilisateur(int(uid_sel)); st.warning("Compte supprimé."); st.rerun()

    # ---- CATALOGUE ----
    with tab_cat:
        sous_catalogue, sous_cat_sources, sous_cat_detectees = st.tabs(
            ["📋 Catalogue actif", "🔎 Sources à ingérer", "🆕 Offres détectées"])

        # -- Catalogue actif (offres en production) --
        with sous_catalogue:
            filtre_u = st.selectbox("Filtrer par univers", ["Tous"] + UNIVERS)
            df_o = lire_offres(univers=None if filtre_u == "Tous" else filtre_u, actif_seulement=False)
            if df_o.empty:
                st.info("Catalogue vide.")
            else:
                cols_cat = [c for c in ["id","univers","categorie","fournisseur","nom_offre","prix_mensuel",
                                         "frais_activation","engagement_mois","data_go",
                                         "commission_affiliation","url_souscription","code_affiliation",
                                         "actif"] if c in df_o.columns]
                st.dataframe(df_o[cols_cat], hide_index=True, use_container_width=True)
                oid = st.selectbox("Offre à modifier", df_o["id"].tolist(),
                    format_func=lambda i: f"#{i} · {df_o[df_o['id']==i]['nom_offre'].values[0]}")
                c1, c2, c3 = st.columns(3)
                nv_prix = c1.number_input("Nouveau prix (€)", min_value=0.0,
                    value=float(df_o[df_o["id"]==oid]["prix_mensuel"].values[0]), step=1.0)
                if nv_prix > SEUIL_PRIX_SUSPECT.get(df_o[df_o["id"]==oid]["univers"].values[0], 99999):
                    c1.warning("⚠️ Prix inhabituellement élevé pour cet univers — vérifiez qu'il n'y a "
                               "pas une erreur de saisie avant d'enregistrer.")
                if c1.button("💾 MàJ prix"):
                    maj_offre(oid, "prix_mensuel", nv_prix); st.success("OK."); st.rerun()
                if c2.button("🔁 Activer/Désactiver"):
                    etat = int(df_o[df_o["id"]==oid]["actif"].values[0])
                    maj_offre(oid, "actif", 0 if etat else 1); st.rerun()
                if c3.button("🗑️ Supprimer"):
                    supprimer_offre(oid); st.warning("Supprimé."); st.rerun()

                st.markdown("##### 🔗 Lien de souscription (affiliation)")
                ligne_sel = df_o[df_o["id"] == oid].iloc[0]
                cu1, cu2 = st.columns(2)
                nv_url  = cu1.text_input("URL de souscription", ligne_sel.get("url_souscription") or "",
                                          key="edit_off_url")
                nv_code = cu2.text_input("Code d'affiliation", ligne_sel.get("code_affiliation") or "",
                                          key="edit_off_code")
                if st.button("💾 MàJ lien affilié", key="btn_maj_lien_affilie"):
                    maj_offre(oid, "url_souscription", nv_url)
                    maj_offre(oid, "code_affiliation", nv_code)
                    st.success("Lien affilié mis à jour."); st.rerun()

        # -- Sources à ingérer (catalogue auto-alimenté) --
        with sous_cat_sources:
            st.caption(
                "Pages tarifs/flux à ingérer automatiquement : le pipeline récupère la page, "
                "en extrait les offres via un LLM (Claude) et les dépose dans « Offres détectées » "
                "— jamais directement dans le catalogue. Distinct de « 📈 Veille prix », qui ne "
                "fait que suivre le prix d'une offre déjà connue."
            )
            cs1, cs2 = st.columns(2)
            cat_u = cs1.selectbox("Univers", UNIVERS, key="cat_src_u")
            cat_cat_map = {"Télécom": CATEGORIES_TELECOM, "Énergie": CATEGORIES_ENERGIE,
                           "Abonnements": CATEGORIES_ABO}
            cat_cat = cs2.selectbox("Catégorie", cat_cat_map[cat_u], key="cat_src_cat")
            cat_fourn = cs1.text_input("Fournisseur (optionnel)", key="cat_src_fourn")
            cat_type  = cs2.selectbox("Type de source", ["page_officielle", "flux_partenaire", "open_data"],
                                      key="cat_src_type")
            cat_methode = cs1.selectbox("Méthode de récupération", ["requests", "playwright"],
                                        key="cat_src_methode",
                                        help="`playwright` si la page nécessite du JavaScript pour afficher les prix.")
            cat_url = st.text_input("URL de la page à ingérer", key="cat_src_url")
            if st.button("➕ Ajouter la source", type="primary", key="btn_add_source_catalogue"):
                if cat_url:
                    ajouter_source_catalogue({
                        "univers": cat_u, "categorie": cat_cat, "fournisseur": cat_fourn,
                        "url": cat_url, "type_source": cat_type, "methode": cat_methode,
                    })
                    st.success("Source ajoutée."); st.rerun()
                else:
                    st.warning("L'URL est obligatoire.")

            st.divider()
            st.markdown("#### Sources actives")
            df_cat_src = lire_sources_catalogue()
            if df_cat_src.empty:
                st.info("Aucune source configurée pour le moment.")
            else:
                cols_src = [c for c in ["id", "univers", "categorie", "fournisseur", "url", "type_source",
                                         "methode", "robots_ok", "date_derniere_ingestion", "actif"]
                            if c in df_cat_src.columns]
                st.dataframe(df_cat_src[cols_src], hide_index=True, use_container_width=True)

                cat_sid = st.selectbox("Source à gérer", df_cat_src["id"].tolist(),
                    format_func=lambda i: f"#{i} · {df_cat_src[df_cat_src['id']==i]['fournisseur'].values[0] or '—'} — "
                                          f"{df_cat_src[df_cat_src['id']==i]['url'].values[0]}",
                    key="cat_sel_source")
                if not bool(df_cat_src[df_cat_src["id"] == cat_sid]["robots_ok"].values[0]):
                    st.warning("⚠️ robots.txt interdit l'accès à cette URL pour notre agent — "
                               "l'ingestion sera ignorée tant que c'est le cas.")
                ccs1, ccs2, ccs3 = st.columns(3)
                if ccs1.button("🔎 Ingérer maintenant", type="primary", key="btn_ingerer_source"):
                    with st.spinner("Récupération et extraction en cours…"):
                        resume = ingerer_source(int(cat_sid), api_key=secrets_config.anthropic_api_key())
                    st.success(f"Détectées : {resume['detectees']} · Changements : {resume['changements']} · "
                               f"À vérifier : {resume['a_verifier']} · Doublons ignorés : {resume['doublons']}")
                    st.rerun()
                if ccs2.button("🔁 Activer/Désactiver", key="btn_toggle_source_catalogue"):
                    etat = int(df_cat_src[df_cat_src["id"] == cat_sid]["actif"].values[0])
                    maj_source_catalogue(int(cat_sid), "actif", 0 if etat else 1); st.rerun()
                if ccs3.button("🗑️ Supprimer la source", key="btn_del_source_catalogue"):
                    supprimer_source_catalogue(int(cat_sid)); st.warning("Source supprimée."); st.rerun()

        # -- Offres détectées (validation avant impact catalogue) --
        with sous_cat_detectees:
            st.caption(
                "Offres découvertes par le pipeline d'ingestion, en attente de validation. "
                "« Valider » ajoute la nouvelle offre au catalogue (ou met à jour le prix si "
                "l'offre existe déjà), « Rejeter » l'écarte sans impact."
            )
            df_stg = lire_offres_staging(statut="en_attente")
            df_stg_verif = lire_offres_staging(statut="a_verifier")
            df_stg_tout = pd.concat([df_stg, df_stg_verif]) if not df_stg_verif.empty else df_stg
            if df_stg_tout.empty:
                st.info("Aucune offre détectée en attente de validation.")
            else:
                for o in df_stg_tout.itertuples():
                    with st.container(border=True):
                        if o.offre_existante_id:
                            st.markdown(f"**{o.fournisseur} — {o.nom_offre}** ({o.univers} / {o.categorie}) "
                                        f"— 🔄 changement de prix détecté")
                        else:
                            st.markdown(f"**{o.fournisseur} — {o.nom_offre}** ({o.univers} / {o.categorie}) "
                                        f"— 🆕 nouvelle offre")
                        prix_aff = f"{o.prix_mensuel:.2f} €" if o.prix_mensuel is not None else "❓ non trouvé"
                        st.markdown(f"Prix mensuel : **{prix_aff}** — engagement {o.engagement_mois or 0} mois "
                                    f"— détecté le {o.date_detection}")
                        if o.statut == "a_verifier":
                            st.warning("⚠️ Prix non trouvé par l'extraction — à vérifier manuellement "
                                       "avant validation (source ci-dessous).")
                        if o.champs_incertains and o.champs_incertains not in ("[]", "null", None):
                            st.caption(f"Champs incertains signalés par le LLM : {o.champs_incertains}")
                        if o.source_url:
                            st.caption(f"Source : {o.source_url}")
                        co1, co2 = st.columns(2)
                        if co1.button("✅ Valider", key=f"btn_valid_stg_{o.id}"):
                            ok, msg = valider_offre_staging(int(o.id), st.session_state.auth_nom_complet)
                            (st.success if ok else st.error)(msg); st.rerun()
                        if co2.button("❌ Rejeter", key=f"btn_reject_stg_{o.id}"):
                            rejeter_offre_staging(int(o.id)); st.warning("Offre rejetée."); st.rerun()

    # ---- AJOUTER OFFRE ----
    with tab_add:
        st.caption("💡 Pour énergie/abonnements : relevez l'offre sur un comparateur, saisissez-la ici.")
        u = st.selectbox("Univers", UNIVERS, key="off_u")
        cat_map = {"Télécom": CATEGORIES_TELECOM, "Énergie": CATEGORIES_ENERGIE,
                   "Abonnements": CATEGORIES_ABO}
        liens = {"Énergie":      "https://comparateur-offres.energie-info.fr",
                 "Télécom":      "https://www.google.com/search?q=comparatif+forfait+mobile+box",
                 "Abonnements":  "https://www.google.com/search?q=prix+abonnement+streaming"}
        st.markdown(f"🔗 [Ouvrir un comparateur {u}]({liens[u]})")
        cat    = st.selectbox("Catégorie", cat_map[u], key="off_c")
        c1, c2 = st.columns(2)
        fourn  = c1.text_input("Fournisseur / Opérateur", key="add_off_fourn")
        nom    = c2.text_input("Nom de l'offre",           key="add_off_nom")
        prix   = c1.number_input("Prix mensuel (€)", min_value=0.0, step=1.0)
        if prix > SEUIL_PRIX_SUSPECT.get(u, 99999):
            c1.warning("⚠️ Prix inhabituellement élevé pour cet univers — vérifiez qu'il n'y a "
                       "pas une erreur de saisie avant d'ajouter au catalogue.")
        frais  = c2.number_input("Frais d'activation (€)", min_value=0.0, step=1.0)
        engage = c1.number_input("Engagement (mois)", min_value=0, step=1)
        commiss= c2.number_input("Commission affiliation (€)", min_value=0.0, step=1.0)
        data_go_off = c1.number_input("Data (Go) — 0 si non applicable (Box/Fibre, Énergie, Abo)",
                                      min_value=0.0, step=10.0, key="add_off_data")
        carac  = st.text_area("Caractéristiques (data, débit, options…)")
        url_souscr = c1.text_input("URL de souscription (lien affilié)", key="add_off_url")
        code_aff   = c2.text_input("Code d'affiliation", key="add_off_code")
        if st.button("➕ Ajouter au catalogue", type="primary"):
            if nom and fourn:
                ajouter_offre({"univers": u, "categorie": cat, "fournisseur": fourn,
                               "nom_offre": nom, "prix_mensuel": prix,
                               "frais_activation": frais, "engagement_mois": engage,
                               "caracteristiques": carac, "commission_affiliation": commiss,
                               "data_go": data_go_off,
                               "url_souscription": url_souscr, "code_affiliation": code_aff})
                st.success(f"« {nom} » ajoutée.")
            else:
                st.warning("Fournisseur et nom obligatoires.")

    # ---- DÉMO ----
    with tab_demo:
        st.markdown("### Pré-remplir le catalogue avec des offres de démonstration")
        st.caption("Ajoute un jeu d'offres types pour tester immédiatement. Vous pourrez tout modifier.")
        if st.button("⚡ Charger les offres de démo", type="primary"):
            inserer_offres_demo()
            st.success("Catalogue de démonstration chargé !"); st.rerun()

    # ---- EMAIL ----
    with tab_mail:
        st.session_state.nom_societe = st.text_input(
            "Nom de votre société (en-tête PDF/email)", st.session_state.nom_societe,
            key="smtp_nom_societe")
        st.markdown("### Configuration SMTP")
        smtp_via_env = any(secrets_config.source_env(v) for v in
                            ("SMTP_SERVEUR", "SMTP_USER", "SMTP_MDP"))
        cfg = st.session_state.smtp_config
        if smtp_via_env:
            st.info("🔒 Configuration SMTP gérée via `.env` — modifiez le fichier `.env` "
                     "et redémarrez l'application pour changer ces valeurs.")
            st.text_input("Serveur SMTP", cfg.get("serveur", ""), disabled=True)
            st.text_input("Identifiant SMTP", cfg.get("user", ""), disabled=True)
            st.text_input("Expéditeur affiché", cfg.get("expediteur", ""), disabled=True)
        else:
            st.caption("Gmail : smtp.gmail.com, port 587, mot de passe d'application. "
                       "💡 Pour ne plus stocker ce mot de passe en base, définissez "
                       "SMTP_SERVEUR/SMTP_USER/SMTP_MDP dans `.env` (voir `.env.example`).")
            cfg["serveur"]    = st.text_input("Serveur SMTP",          cfg.get("serveur", ""),             key="smtp_serveur")
            cfg["port"]       = st.number_input("Port", min_value=1,   value=int(cfg.get("port", 587)),    key="smtp_port")
            cfg["user"]       = st.text_input("Identifiant SMTP",      cfg.get("user", ""),                key="smtp_user")
            cfg["mdp"]        = st.text_input("Mot de passe SMTP",     type="password",
                                              value=cfg.get("mdp", ""),                                    key="smtp_mdp")
            cfg["expediteur"] = st.text_input("Expéditeur affiché",    cfg.get("expediteur", cfg.get("user", "")), key="smtp_expediteur")
            st.session_state.smtp_config = cfg

        st.markdown("### 🔔 Notifications de relances (`notifications.py`)")
        st.caption("Réglages utilisés par le script planifié `notifications.py` (cron / tâche "
                   "planifiée quotidienne) — celui-ci tourne hors de l'application. "
                   "💡 Peut aussi être défini via `.env` (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).")
        notif_email = st.text_input("Email du conseiller à notifier",
                                     lire_parametre("notif_email_destinataire", cfg.get("user", "")),
                                     key="notif_email_dest")
        tg_via_env = secrets_config.source_env("TELEGRAM_BOT_TOKEN")
        c_tg1, c_tg2 = st.columns(2)
        if tg_via_env:
            c_tg1.text_input("Jeton bot Telegram", "🔒 géré via .env", disabled=True)
            tg_token = secrets_config.telegram_bot_token()
        else:
            tg_token = c_tg1.text_input("Jeton bot Telegram (optionnel)",
                                         lire_parametre("telegram_bot_token", ""), key="notif_tg_token")
        tg_chat  = c_tg2.text_input("Chat ID Telegram (optionnel)",
                                     lire_parametre("telegram_chat_id", ""), key="notif_tg_chat")

        if st.button("💾 Enregistrer", key="btn_smtp_save"):
            if not smtp_via_env:
                ecrire_parametre("smtp_serveur",    cfg["serveur"])
                ecrire_parametre("smtp_port",       cfg["port"])
                ecrire_parametre("smtp_user",       cfg["user"])
                ecrire_parametre("smtp_mdp",        cfg["mdp"])
                ecrire_parametre("smtp_expediteur", cfg["expediteur"])
            ecrire_parametre("nom_societe",     st.session_state.nom_societe)
            ecrire_parametre("notif_email_destinataire", notif_email)
            if not tg_via_env:
                ecrire_parametre("telegram_bot_token", tg_token)
            ecrire_parametre("telegram_chat_id", tg_chat)
            st.success("Configuration enregistrée en base — réutilisable par notifications.py.")

    # ---- FACTURATION ----
    with tab_fact:
        st.markdown("### Taux d'honoraires par défaut")
        st.caption("Appliqué par défaut à la création d'un devis (modifiable au cas par cas) "
                   "— pourcentage de l'économie annuelle trouvée.")
        taux_actuel = safe_float(lire_parametre("taux_honoraires_defaut", "20"), 20.0)
        nv_taux = st.number_input("Taux d'honoraires par défaut (%)", min_value=0.0, max_value=100.0,
                                  value=taux_actuel, step=1.0, key="admin_taux_honoraires")
        if st.button("💾 Enregistrer le taux", key="btn_taux_save"):
            ecrire_parametre("taux_honoraires_defaut", nv_taux)
            st.success("Taux par défaut mis à jour."); st.rerun()

    # ---- OCR VISION (NOUVEAU) ----
    with tab_ocr:
        st.markdown("### Analyse de factures par IA Vision (Claude)")
        st.caption(
            "Remplace/complète l'extraction PyPDF2 (texte embarqué uniquement) par l'API "
            "Claude Vision, capable de lire une **photo**, un **scan** ou un **PDF image** de "
            "facture. Sans clé configurée, l'analyse retombe automatiquement sur l'extraction "
            "PyPDF2 classique (PDF texte uniquement — les photos/scans nécessitent la clé API)."
        )
        if not ANTHROPIC_OK:
            st.warning("Le package `anthropic` n'est pas installé — `pip install anthropic` "
                       "puis relancez l'application.")
        if secrets_config.source_env("ANTHROPIC_API_KEY"):
            st.info("🔒 Clé API gérée via `.env` (ANTHROPIC_API_KEY) — modifiez le fichier "
                     "`.env` et redémarrez l'application pour la changer.")
        else:
            st.caption("💡 Pour ne plus stocker cette clé en base, définissez ANTHROPIC_API_KEY "
                       "dans `.env` (voir `.env.example`).")
            cle_actuelle = lire_parametre("anthropic_api_key", "")
            nv_cle = st.text_input("Clé API Anthropic (Claude)", value=cle_actuelle,
                                    type="password", key="admin_anthropic_key",
                                    help="Obtenue sur console.anthropic.com — jamais affichée en clair.")
            if st.button("💾 Enregistrer la clé", key="btn_anthropic_save"):
                ecrire_parametre("anthropic_api_key", nv_cle)
                st.success("Clé API enregistrée.")

    # ---- VEILLE PRIX (NOUVEAU) ----
    with tab_veille:
        st.markdown("### 📈 Veille automatique des prix opérateurs")
        st.caption(
            "Surveille des pages tarifs (Playwright) et détecte les changements de prix. "
            "Aucune mise à jour du catalogue n'est automatique : chaque changement crée "
            "une alerte que vous validez ou rejetez ci-dessous."
        )
        if not PLAYWRIGHT_OK:
            st.warning("Le package `playwright` n'est pas installé (ou ses navigateurs ne le "
                       "sont pas) — `pip install playwright && playwright install chromium`.")

        sous_sources, sous_alertes, sous_historique = st.tabs(
            ["🔗 Sources surveillées", "🔔 Alertes en attente", "📊 Historique des prix"])

        # -- Sources --
        with sous_sources:
            df_off_veille = lire_offres(actif_seulement=False)
            st.markdown("#### ➕ Ajouter une source à surveiller")
            cv1, cv2 = st.columns(2)
            v_u   = cv1.selectbox("Univers", UNIVERS, key="veille_u")
            v_cat_map = {"Télécom": CATEGORIES_TELECOM, "Énergie": CATEGORIES_ENERGIE,
                         "Abonnements": CATEGORIES_ABO}
            v_cat = cv2.selectbox("Catégorie", v_cat_map[v_u], key="veille_cat")
            v_fourn = cv1.text_input("Fournisseur / Opérateur", key="veille_fourn")
            v_nom   = cv2.text_input("Nom de l'offre suivie", key="veille_nom")
            v_url   = st.text_input("URL de la page tarif à surveiller", key="veille_url")
            v_sel   = st.text_input(
                "Sélecteur CSS du prix (ex. `.price`, `span#tarif`)", key="veille_selecteur",
                help="Inspectez la page (clic droit > Inspecter) pour trouver l'élément qui "
                     "affiche le prix.")
            offres_dispo = ["Aucune (veille seule, sans mise à jour catalogue)"] + [
                f"#{r.id} · {r.fournisseur} — {r.nom_offre}" for r in df_off_veille.itertuples()]
            v_offre_choix = st.selectbox(
                "Offre du catalogue à mettre à jour automatiquement (après validation)",
                offres_dispo, key="veille_offre_liee")
            if st.button("➕ Ajouter la source", type="primary", key="btn_add_source_veille"):
                if v_url and v_sel and v_fourn:
                    offre_id_liee = None
                    if v_offre_choix != offres_dispo[0]:
                        offre_id_liee = int(v_offre_choix.split("·")[0].strip().lstrip("#"))
                    ajouter_source({
                        "univers": v_u, "categorie": v_cat, "fournisseur": v_fourn,
                        "nom_offre": v_nom, "offre_id": offre_id_liee,
                        "url": v_url, "selecteur_prix": v_sel,
                    })
                    st.success("Source ajoutée."); st.rerun()
                else:
                    st.warning("Fournisseur, URL et sélecteur CSS sont obligatoires.")

            st.divider()
            st.markdown("#### Sources actives")
            df_src = lire_sources()
            if df_src.empty:
                st.info("Aucune source configurée pour le moment.")
            else:
                cols_src = [c for c in ["id", "univers", "categorie", "fournisseur", "nom_offre",
                                         "offre_id", "url", "dernier_prix", "date_derniere_verif",
                                         "actif"] if c in df_src.columns]
                st.dataframe(df_src[cols_src], hide_index=True, use_container_width=True)

                if st.button("🔎 Lancer la veille maintenant", type="primary", key="btn_lancer_veille"):
                    with st.spinner("Vérification des sources en cours…"):
                        nouvelles = lancer_veille()
                    if nouvelles:
                        st.warning(f"{len(nouvelles)} changement(s) de prix détecté(s) — "
                                   f"voir l'onglet « Alertes en attente ».")
                    else:
                        st.success("Vérification terminée — aucun changement détecté.")
                    st.rerun()

                sid_sel = st.selectbox("Source à gérer", df_src["id"].tolist(),
                    format_func=lambda i: f"#{i} · {df_src[df_src['id']==i]['fournisseur'].values[0]} — "
                                          f"{df_src[df_src['id']==i]['nom_offre'].values[0]}",
                    key="veille_sel_source")
                cs1, cs2 = st.columns(2)
                if cs1.button("🔁 Activer/Désactiver", key="btn_toggle_source"):
                    etat = int(df_src[df_src["id"] == sid_sel]["actif"].values[0])
                    maj_source(int(sid_sel), "actif", 0 if etat else 1); st.rerun()
                if cs2.button("🗑️ Supprimer la source", key="btn_del_source"):
                    supprimer_source(int(sid_sel)); st.warning("Source supprimée."); st.rerun()

        # -- Alertes --
        with sous_alertes:
            df_al = lire_alertes(statut="en_attente")
            if df_al.empty:
                st.info("Aucune alerte en attente.")
            else:
                for a in df_al.itertuples():
                    sens = "🔺" if a.nouveau_prix > a.ancien_prix else "🔻"
                    with st.container(border=True):
                        st.markdown(f"**{a.fournisseur} — {a.nom_offre}** ({a.univers} / {a.categorie})")
                        st.markdown(f"{sens} {a.ancien_prix:.2f} € → **{a.nouveau_prix:.2f} €** "
                                    f"— détecté le {a.date_detection}")
                        ca1, ca2 = st.columns(2)
                        if ca1.button("✅ Valider (répercuter au catalogue)", key=f"btn_valid_{a.id}"):
                            ok, msg = valider_alerte(int(a.id), st.session_state.auth_nom_complet)
                            (st.success if ok else st.error)(msg); st.rerun()
                        if ca2.button("❌ Rejeter", key=f"btn_reject_{a.id}"):
                            rejeter_alerte(int(a.id)); st.warning("Alerte rejetée."); st.rerun()

        # -- Historique --
        with sous_historique:
            df_src_hist = lire_sources()
            if df_src_hist.empty:
                st.info("Aucune source configurée.")
            else:
                sid_hist = st.selectbox("Source", df_src_hist["id"].tolist(),
                    format_func=lambda i: f"#{i} · {df_src_hist[df_src_hist['id']==i]['fournisseur'].values[0]} — "
                                          f"{df_src_hist[df_src_hist['id']==i]['nom_offre'].values[0]}",
                    key="veille_sel_historique")
                df_h = lire_historique_prix(int(sid_hist))
                if df_h.empty:
                    st.info("Aucun relevé pour cette source pour le moment — lancez la veille.")
                else:
                    st.line_chart(df_h.set_index("date_releve")["prix"])
                    st.dataframe(df_h[["date_releve", "prix"]], hide_index=True, use_container_width=True)
