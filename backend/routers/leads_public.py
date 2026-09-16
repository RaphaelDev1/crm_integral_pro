"""LEADS PUBLIC — endpoints publics (sans JWT) exposés à la landing /economiser.

Contrairement à backend/routers/prospects.py (CRUD interne protégé par
`Depends(get_current_user)`), ce router N'A PAS de dépendance d'auth au niveau
global : un utilisateur anonyme sur la landing publique doit pouvoir POST.

À monter dans backend/main.py :
    from backend.routers import leads_public
    app.include_router(leads_public.router)   # dans la section « Routers publics »

Sécurité :
  - Rate limiting par IP (10 req/min, 100 req/j) via slowapi — mémoire en dev,
    Redis en prod multi-instances (voir backend/core/rate_limit.py).
  - Honeypot invisible (`hp_field`) — 200 OK muet mais rien n'est écrit.
  - Captcha invisible Cloudflare Turnstile (`turnstile_token`, désactivé tant
    que TURNSTILE_SECRET_KEY est vide).
  - Validation Pydantic stricte (téléphone FR, âge borné).
  - Consentement RGPD refusé si False.
  - Tracking complet : IP, User-Agent, UTM, date de consentement — audit CNIL.
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal, get_db
from backend.core.rate_limit import limiter
from backend.models.contrat import Contrat
from backend.models.prospect import Prospect
from backend.models.touchpoint import Touchpoint
from backend.schemas.lead_public import (
    AdresseSuggestionOut,
    DetectionFaiOut,
    EstimationOut,
    FibreOut,
    LeadEstimationRequest,
    LeadEstimationResponse,
    LigneEstimationOut,
    MethodologieOut,
)
from backend.services import audit_engine, captcha, eligibilite_fibre, estimation_publique, geo_ip, telephone_verification
from backend.services.estimation_publique import resoudre_tranche

# Notifications — import soft pour rester tolérant si le service n'a pas encore
# implémenté ces helpers dans l'environnement local du dev.
try:
    from backend.services import notification_engine
    _NOTIF_OK = True
except Exception:
    notification_engine = None  # type: ignore
    _NOTIF_OK = False

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public/leads", tags=["public-landing"])

LIMITE_MINUTE = "10/minute"
LIMITE_JOUR = "100/day"

# Catégorie de `DepensesActuelles.to_categories()` pour laquelle
# `operateur_mobile` s'applique comme fournisseur — distincte de la box, un
# prospect pouvant avoir un opérateur différent pour chaque service.
_CATEGORIE_MOBILE = "Mobile"
_CATEGORIES_BOX = {"Box / Fibre", "Pack Box + Mobile"}
# Idem pour `fournisseur_energie` (EDF, Engie…).
_CATEGORIES_ENERGIE = {"Électricité", "Gaz"}


def _fournisseur_pour_categorie(categorie: str, payload: LeadEstimationRequest) -> str | None:
    if categorie == _CATEGORIE_MOBILE:
        return payload.operateur_mobile or None
    if categorie in _CATEGORIES_BOX:
        return payload.operateur_box or None
    if categorie in _CATEGORIES_ENERGIE:
        return payload.fournisseur_energie or None
    return None


def _ip_reelle(request: Request) -> str:
    """Récupère l'IP réelle derrière un reverse proxy (Nginx, Cloudflare, Vercel).
    Fallback sur request.client.host si aucun header proxy."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


# ------------------------------------------------------------------------------
#  ENDPOINT PRINCIPAL
# ------------------------------------------------------------------------------
@router.post("/capture", response_model=LeadEstimationResponse)
@limiter.limit(LIMITE_JOUR)
@limiter.limit(LIMITE_MINUTE)
async def capturer_lead(
    payload: LeadEstimationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Capture un lead depuis la landing publique.

    Étapes :
      1. rate limit IP (slowapi) + honeypot silencieux + captcha Turnstile
      2. estimation en temps réel (moteur estimation_publique) + éligibilité
         fibre niveau commune (si adresse sélectionnée)
      3. persistance dans `prospects` (origine="Landing <source>", statut="À relancer")
      4. tâches asynchrones (Slack + SMS immédiats, vérif téléphone Twilio,
         détection FAI par IP — email récap différé en J+1, voir tasks.py)
    """
    ip = _ip_reelle(request)
    user_agent = request.headers.get("user-agent", "")[:512]

    # Honeypot — les bots remplissent ce champ invisible, les humains ne le voient pas
    if payload.hp_field:
        logger.info("Lead honeypot silencieusement rejeté (IP=%s, hp=%r)", ip, payload.hp_field[:40])
        return LeadEstimationResponse(
            ok=True, ref="honeypot",
            estimation=EstimationOut(
                lignes=[], economie_annuelle_totale_basse=0,
                economie_annuelle_totale_haute=0, economie_annuelle_totale_typique=0,
                calculee_le=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            ),
            message="OK",
        )

    if not await captcha.verifier(payload.turnstile_token, ip):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Vérification anti-bot échouée, réessayez.")

    # Adresse (socle S1, docs/QUESTIONS_PAR_SECTEUR.md) — posée si un secteur
    # box ou énergie est sélectionné, reste facultative sinon. verifier(None)
    # est un no-op qui renvoie un résultat vide si le prospect ne l'a pas fournie.
    adresse_in = payload.adresse
    code_insee = adresse_in.code_insee if adresse_in else None
    resultat_fibre = await eligibilite_fibre.verifier(code_insee)

    # Estimation live
    estimation_dc = await estimation_publique.estimer(
        db, payload.depenses.to_categories(), age=payload.age, tranche=payload.tranche_age,
    )
    estimation_out = EstimationOut(
        lignes=[LigneEstimationOut(**l.__dict__) for l in estimation_dc.lignes],
        economie_annuelle_totale_basse=estimation_dc.economie_annuelle_totale_basse,
        economie_annuelle_totale_haute=estimation_dc.economie_annuelle_totale_haute,
        economie_annuelle_totale_typique=estimation_dc.economie_annuelle_totale_typique,
        methodologie_url=estimation_dc.methodologie_url,
        calculee_le=estimation_dc.calculee_le,
    )

    ref = f"L-{datetime.utcnow():%y%m%d}-{secrets.token_hex(2).upper()}"
    depenses = payload.depenses.to_categories()

    # Insertion via ORM (pas via reference_engine.generer_ref_prospect car nos leads
    # ont un préfixe "L-" distinct, pour repérer visuellement l'origine landing).
    prospect = Prospect(
        ref=ref,
        prenom=payload.prenom.strip(),
        nom="",   # non demandé sur la landing (friction minimum)
        telephone=payload.telephone,
        email=payload.email or None,
        operateur_actuel=payload.operateur_mobile or None,
        operateur_box=payload.operateur_box or None,
        # Réutilisation de techno (existant, pas dédié au mobile) pour l'offre
        # ADSL/Fibre déclarée sur la landing. `debit_declare` (distinct de
        # speed_down, réservé au vrai test mesuré) porte le débit déclaré ici.
        techno=payload.offre_box or None,
        debit_declare=payload.debit_box,
        fournisseur_energie=payload.fournisseur_energie or None,
        data_go=str(payload.conso_data_go) if payload.conso_data_go is not None else None,
        roaming_europe=payload.roaming_europe or None,
        roaming_hors_ue=payload.roaming_hors_ue or None,
        sensibilite_prix=payload.sensibilite_prix or None,
        bonus_malus_auto=payload.bonus_malus_auto or None,
        plage_horaire_rappel=payload.plage_horaire_rappel or None,
        objectif_principal=payload.objectif_principal or None,
        nb_lignes_mobiles=payload.nb_lignes_mobiles or None,
        qualite_reseau_mobile=payload.qualite_reseau_mobile or None,
        type_client="Particulier",
        univers_interesse=_detecter_univers(depenses),
        cout_mensuel_actuel=round(sum(v for v in depenses.values() if v), 2),
        economie_estimee_an=estimation_dc.economie_annuelle_totale_typique,
        statut="À relancer",
        origine=f"Landing {payload.utm.source or 'direct'}",
        notes=_construire_notes(payload, estimation_dc, ip, user_agent),
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        # ISO (YYYY-MM-DD) — format attendu partout ailleurs pour date_relance
        # (voir backend/routers/dashboard.py::_parse_date_relance), sans quoi
        # le lead disparaît silencieusement du tableau de bord des relances.
        date_relance=datetime.now().strftime("%Y-%m-%d"),
        cree_par="landing-publique",
        # Colonnes ajoutées par la migration 0028_leads_capture
        utm_source=payload.utm.source,
        utm_medium=payload.utm.medium,
        utm_campaign=payload.utm.campaign,
        utm_content=payload.utm.content,
        utm_term=payload.utm.term,
        age=payload.age,
        tranche_age=resoudre_tranche(payload.age, payload.tranche_age),
        consentement_rgpd=payload.consentement_rgpd,
        consentement_demarchage=payload.consentement_demarchage,
        date_consentement=datetime.now().strftime("%d/%m/%Y %H:%M"),
        ip_creation=ip,
        user_agent_creation=user_agent,
        depenses_declarees_json=json.dumps(payload.depenses.model_dump(), ensure_ascii=False),
        # Un lead landing est chaud par nature — score plancher pour remonter en tête
        # du tableau de bord conseiller avant le premier appel.
        score=200.0,
        # Colonnes ajoutées par la migration 0028_leads_enrichissements —
        # renseignées uniquement si le prospect a fourni son adresse (socle S1,
        # posée seulement si un secteur box ou énergie est sélectionné).
        code_postal=adresse_in.code_postal if adresse_in else None,
        ville=adresse_in.ville if adresse_in else None,
        adresse=adresse_in.label if adresse_in else None,
        latitude=adresse_in.latitude if adresse_in else None,
        longitude=adresse_in.longitude if adresse_in else None,
        code_insee=code_insee,
        fibre_disponible=resultat_fibre.disponible,
        fibre_taux_couverture=resultat_fibre.taux_couverture,
    )
    db.add(prospect)
    await db.flush()

    # Contrats structurés (P5) — un contrat "Actuel" (situation avant nous, pas
    # encore chez nous) par service déclaré non nul, pour que le conseiller
    # retrouve opérateur/fournisseur/consommation dans l'onglet Contrats du
    # prospect plutôt que noyés dans les notes texte. `categorie` reprend
    # exactement les clés de `depenses` (déjà celles attendues par
    # estimation_publique.FALLBACK_MARCHE).
    for categorie, cout in depenses.items():
        if not cout:
            continue
        est_box = categorie in _CATEGORIES_BOX
        est_electricite = categorie == "Électricité"
        est_energie = categorie in _CATEGORIES_ENERGIE
        db.add(Contrat(
            prospect_id=prospect.id,
            categorie=categorie,
            cout_mensuel=cout,
            statut_contrat="Actuel",
            chez_nous=False,
            fournisseur=_fournisseur_pour_categorie(categorie, payload),
            consommation=(
                f"{payload.conso_data_go:g} Go" if categorie == _CATEGORIE_MOBILE and payload.conso_data_go is not None
                else f"{payload.debit_box:g} Mbps" if est_box and payload.debit_box is not None
                else None
            ),
            # Offre ADSL/Fibre + débit déclarés — uniquement pertinents pour
            # les catégories box (voir Prospect.techno/debit_declare ci-dessus).
            nom_offre=payload.offre_box if est_box else None,
            debit_declare=payload.debit_box if est_box else None,
            # Trame box (B3, B3b) — voir docs/QUESTIONS_PAR_SECTEUR.md.
            usage_tv=payload.usage_tv if est_box else None,
            abonnements_payants=payload.abonnements_payants if est_box else None,
            # Trame énergie (E1) — le chauffage concerne le contrat Électricité
            # comme le contrat Gaz s'il existe ; (E5, E5a, E6) sont propres au
            # compteur électrique (kVA, option tarifaire), donc Électricité seule.
            chauffage_principal=payload.chauffage_principal if est_energie else None,
            puissance_kva=payload.puissance_kva if est_electricite else None,
            option_tarifaire=payload.option_tarifaire if est_electricite else None,
            gros_equipement_electrique=payload.gros_equipement_electrique if est_electricite else None,
        ))

    # Historique d'attribution (P4.3) — chaque point de contact constitué côté
    # client avant conversion (voir frontend-portail/lib/attribution.ts).
    for i, tp in enumerate(payload.touchpoints):
        db.add(Touchpoint(
            prospect_id=prospect.id,
            ordre=i,
            utm_source=tp.utm.source,
            utm_medium=tp.utm.medium,
            utm_campaign=tp.utm.campaign,
            utm_content=tp.utm.content,
            utm_term=tp.utm.term,
            referrer=tp.referrer,
            landing_page=tp.landing_page,
            horodatage_client=tp.horodatage,
            date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        ))

    await audit_engine.enregistrer_action(
        db, entite_type="prospect", entite_id=prospect.id,
        action="Lead capturé depuis la landing publique",
        details=(
            f"Source: {payload.utm.source or 'direct'} / {payload.utm.campaign or ''} — "
            f"Économie estimée: {estimation_dc.economie_annuelle_totale_typique:.0f} €/an"
        ),
        auteur="landing-publique",
    )
    await db.commit()
    await db.refresh(prospect)

    # Tâches asynchrones — l'HTTP répond immédiatement, le SMS part en fond
    background_tasks.add_task(
        _declencher_sequence_relance, prospect.id, payload, estimation_dc,
    )
    background_tasks.add_task(_enrichir_lead_arriere_plan, prospect.id, payload.telephone, ip)

    return LeadEstimationResponse(
        ok=True,
        ref=ref,
        estimation=estimation_out,
        message=(
            f"Merci {payload.prenom} ! Un conseiller vous rappelle sous 24h. "
            f"Vous allez recevoir un SMS de confirmation."
        ),
        fibre=FibreOut(disponible=resultat_fibre.disponible, taux_couverture=resultat_fibre.taux_couverture),
    )


@router.get("/adresse-autocomplete", response_model=list[AdresseSuggestionOut])
@limiter.limit(LIMITE_MINUTE)
async def adresse_autocomplete(request: Request, q: str):
    """Proxy vers l'API Adresse (Base Adresse Nationale, api-adresse.data.gouv.fr) —
    proxifié côté backend car le support CORS de l'API n'est pas garanti pour
    des appels directs depuis le navigateur. Sert l'autocomplétion d'adresse
    de l'étape 3 du formulaire (P2.1)."""
    q = q.strip()
    if len(q) < 3:
        return []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            reponse = await client.get(
                "https://api-adresse.data.gouv.fr/search/",
                params={"q": q, "limit": 5, "autocomplete": 1},
            )
            reponse.raise_for_status()
            data = reponse.json()
    except Exception as exc:
        logger.warning("API Adresse (BAN) indisponible : %s", exc)
        return []

    suggestions = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        coords = (feature.get("geometry") or {}).get("coordinates") or [None, None]
        suggestions.append(
            AdresseSuggestionOut(
                label=props.get("label", ""),
                code_postal=props.get("postcode"),
                ville=props.get("city"),
                code_insee=props.get("citycode"),
                longitude=coords[0],
                latitude=coords[1],
            )
        )
    return suggestions


@router.get("/detecter-fai", response_model=DetectionFaiOut)
@limiter.limit(LIMITE_MINUTE)
async def detecter_fai(request: Request):
    """Devine l'opérateur télécom actuel du visiteur à partir de son IP
    (ipapi.co) — sert à pré-remplir (de façon éditable) le champ "Opérateur
    actuel" à l'étape 2 du formulaire (P2.3)."""
    ip = _ip_reelle(request)
    resultat = await geo_ip.detecter(ip)
    return DetectionFaiOut(operateur_probable=resultat.operateur_probable)


@router.get("/desabonner/{ref}", response_model=dict)
async def desabonner_lead(ref: str, db: AsyncSession = Depends(get_db)):
    """Désabonnement en un clic depuis le pied des emails de nurturing (P4.2)
    — conforme RGPD (le retrait du consentement doit être aussi simple que son
    octroi). `ref` sert de jeton : c'est déjà l'identifiant public renvoyé au
    lead à la capture, aucune donnée sensible n'est exposée par cette action
    (idempotente : ré-appeler ce endpoint ne fait rien de plus)."""
    prospect = (await db.execute(select(Prospect).where(Prospect.ref == ref))).scalars().first()
    if prospect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lien de désabonnement invalide.")
    prospect.email_desabonne = True
    await db.commit()
    return {"ok": True, "message": "Vous ne recevrez plus d'emails de notre part."}


@router.get("/methodologie", response_model=MethodologieOut)
async def methodologie(db: AsyncSession = Depends(get_db)):
    """Sert de justification légale pour la mention "jusqu'à X€*" affichée en pub.
    Retourne aussi la liste des catégories calibrées sur BDD réelle vs fallback marché."""
    statut = await estimation_publique.statut_moteur(db)
    return MethodologieOut(
        principe=(
            "Nos estimations comparent le montant que vous déclarez au coût médian réel "
            "payé par nos clients dans la même catégorie (télécom, énergie, assurances). "
            "Lorsque notre échantillon interne est insuffisant (< 30 clients), nous utilisons "
            "les moyennes publiques de marché (Arcep, CRE, FFA)."
        ),
        fourchette=(
            "L'estimation est présentée sous forme de fourchette ±25 % autour d'une valeur "
            "typique, car les économies dépendent de votre situation exacte (options, "
            "consommation, éligibilité aux promotions). Seul un rendez-vous conseiller "
            "permet d'obtenir un chiffre définitif."
        ),
        **statut,
    )


# ------------------------------------------------------------------------------
#  HELPERS INTERNES
# ------------------------------------------------------------------------------
def _detecter_univers(depenses: dict) -> str:
    if depenses.get("Mobile") or depenses.get("Box / Fibre") or depenses.get("Pack Box + Mobile"):
        return "Télécom"
    if depenses.get("Électricité") or depenses.get("Gaz"):
        return "Énergie"
    if any(depenses.get(k) for k in ("Assurance auto", "Assurance habitation", "Assurance santé")):
        return "Assurances"
    return "Multi"


def _construire_notes(payload: LeadEstimationRequest, estimation, ip: str, ua: str) -> str:
    parts = [
        "== Lead landing publique ==",
        f"Tranche d'âge déclarée : {resoudre_tranche(payload.age, payload.tranche_age) or 'non renseignée'}",
        f"Consentement RGPD : {'✅' if payload.consentement_rgpd else '❌'}",
        f"Consentement démarchage tél : {'✅' if payload.consentement_demarchage else '❌'}",
        f"Créneau de rappel souhaité : {payload.plage_horaire_rappel or 'non renseigné'}",
        f"Opérateur mobile déclaré : {payload.operateur_mobile or 'non renseigné'}",
        f"Opérateur box déclaré : {payload.operateur_box or 'non renseigné'}",
        f"Offre box déclarée : {payload.offre_box or 'non renseignée'}",
        f"Débit box déclaré : {payload.debit_box if payload.debit_box is not None else 'non renseigné'} Mbps",
        f"Fournisseur d'énergie déclaré : {payload.fournisseur_energie or 'non renseigné'}",
        f"Consommation data mensuelle déclarée : {payload.conso_data_go if payload.conso_data_go is not None else 'non renseignée'} Go",
        f"Voyage en Europe : {payload.roaming_europe or 'non renseigné'}",
        f"Voyage hors UE : {payload.roaming_hors_ue or 'non renseigné'}",
        f"Priorité du client : {payload.sensibilite_prix or 'non renseignée'}",
        f"Objectif principal : {payload.objectif_principal or 'non renseigné'}",
        f"Nombre de lignes mobiles : {payload.nb_lignes_mobiles or 'non renseigné'}",
        f"Qualité réseau déclarée : {payload.qualite_reseau_mobile or 'non renseignée'}",
        f"Chauffage principal : {payload.chauffage_principal or 'non renseigné'}",
        f"Puissance souscrite : {payload.puissance_kva or 'non renseignée'} kVA"
        + (f" (gros équipement : {'oui' if payload.gros_equipement_electrique else 'non'})"
           if payload.puissance_kva else ""),
        f"Option tarifaire énergie : {payload.option_tarifaire or 'non renseignée'}",
        f"Usage TV : {payload.usage_tv or 'non renseigné'}"
        + (f" — abonnements : {payload.abonnements_payants}" if payload.abonnements_payants else ""),
        f"UTM : source={payload.utm.source} / medium={payload.utm.medium} / "
        f"campaign={payload.utm.campaign} / content={payload.utm.content}",
        f"IP : {ip}",
        f"User-Agent : {ua[:120]}",
        "",
        "-- Estimation calculée --",
        f"Total annuel typique : {estimation.economie_annuelle_totale_typique:.0f} €",
        f"Fourchette : {estimation.economie_annuelle_totale_basse:.0f} € à "
        f"{estimation.economie_annuelle_totale_haute:.0f} €",
    ]
    for l in estimation.lignes:
        parts.append(
            f"  • {l.categorie} : déclare {l.cout_actuel_mensuel} €/mois, "
            f"nous {l.notre_moyenne_mensuel} €/mois (source: {l.source}, n={l.echantillon})"
        )
    return "\n".join(parts)


def _declencher_sequence_relance(prospect_id: int, payload: LeadEstimationRequest, estimation) -> None:
    """Séquence asynchrone (exécutée hors du cycle request/response FastAPI) :
      - Notification Slack conseiller (fenêtre 5 min critique)
      - SMS immédiat (critique pour la conversion)
    L'email récap est volontairement différé à J+1 (point de contact
    stratégique distinct du SMS immédiat) via la tâche Celery Beat
    `relancer_email_j1_leads_landing` (backend/workers/tasks.py) — voir P3.2.
    Les erreurs sont loggées mais n'échouent jamais la requête initiale."""
    if not _NOTIF_OK:
        logger.warning("Séquence relance skippée (notification_engine indisponible) — prospect=%s", prospect_id)
        return

    prenom = payload.prenom
    eco = int(estimation.economie_annuelle_totale_typique)

    # 0) Notification Slack conseiller — fenêtre 5 min critique pour la conversion
    try:
        notification_engine.notifier_lead_slack(
            prospect_id=prospect_id,
            prenom=prenom,
            telephone=payload.telephone,
            economie_annuelle=estimation.economie_annuelle_totale_typique,
            utm_source=payload.utm.source,
            utm_campaign=payload.utm.campaign,
        )
    except Exception as e:
        logger.exception("Erreur notification Slack pour prospect %s : %s", prospect_id, e)

    # 1) SMS instantané
    try:
        notification_engine.envoyer_sms(
            payload.telephone,
            f"Bonjour {prenom}, IA Conseil confirme votre demande. "
            f"Économie estimée : jusqu'à {eco}€/an. "
            f"Un conseiller vous rappelle sous 24h. STOP au 36180.",
        )
    except Exception as e:
        logger.exception("Erreur SMS instant pour prospect %s : %s", prospect_id, e)


async def _enrichir_lead_arriere_plan(prospect_id: int, telephone: str, ip: str) -> None:
    """Enrichissements non bloquants exécutés après la réponse HTTP : validation
    téléphone (Twilio Lookup, P2.2) et FAI détecté par IP (P2.3, valeur brute
    conservée pour audit — distincte de `operateur_actuel` déclaré par
    l'utilisateur). Ouvre sa propre session DB (le cycle de vie de `db` côté
    requête est déjà terminé quand cette tâche s'exécute)."""
    try:
        resultat_tel = await telephone_verification.verifier(telephone)
        resultat_geo = await geo_ip.detecter(ip)
    except Exception as e:
        logger.exception("Erreur enrichissement arrière-plan pour prospect %s : %s", prospect_id, e)
        return

    if resultat_tel.verifie is None and resultat_geo.operateur_probable is None:
        return

    try:
        async with AsyncSessionLocal() as db:
            prospect = await db.get(Prospect, prospect_id)
            if prospect is None:
                return
            prospect.telephone_verifie = resultat_tel.verifie
            prospect.telephone_type_ligne = resultat_tel.type_ligne
            prospect.operateur_detecte_ip = resultat_geo.operateur_probable
            await db.commit()
    except Exception as e:
        logger.exception("Erreur mise à jour enrichissement pour prospect %s : %s", prospect_id, e)
