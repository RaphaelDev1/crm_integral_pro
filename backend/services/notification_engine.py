# ==============================================================================
#  NOTIFICATION ENGINE — envoi réel du lien client par email (Resend) et SMS
#  (OVH ou Twilio selon `settings.sms_provider`).
#
#  Repli gracieux (même logique que src/notifications.py) : si les identifiants
#  du fournisseur ne sont pas configurés dans backend/.env, la fonction se
#  contente de journaliser l'absence de config et renvoie False — jamais
#  d'exception propagée à l'appelant (le conseiller doit toujours voir le lien
#  généré, même si l'envoi automatique échoue).
# ==============================================================================
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, datetime
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.client import Client
from backend.models.contrat import Contrat
from backend.models.parametre import Parametre
from backend.models.prospect import Prospect

if TYPE_CHECKING:
    from backend.models.dossier import Dossier

logger = logging.getLogger(__name__)

# ≈ 2 mois — seuil (en jours avant la fin d'engagement) déclenchant l'alerte
# client dans `alerter_fin_engagement`, cf. suivi post-souscription.
JOURS_AVANT_ALERTE_ENGAGEMENT = 60

_OVH_BASE_URLS = {
    "ovh-eu": "https://eu.api.ovh.com/1.0",
    "ovh-ca": "https://ca.api.ovh.com/1.0",
    "ovh-us": "https://api.us.ovhcloud.com/1.0",
}


def envoyer_email(
    destinataire: str, sujet: str, corps_html: str, attachments: list[dict] | None = None
) -> bool:
    """Envoie un email transactionnel via Resend. False (sans exception) si
    RESEND_API_KEY absente ou si l'envoi échoue. `attachments` (optionnel) :
    liste Resend `[{"filename": ..., "content": <base64 str>}]`."""
    if not destinataire:
        return False
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY absente — email non envoyé à %s.", destinataire)
        return False
    try:
        import resend

        resend.api_key = settings.resend_api_key
        payload = {
            "from": f"{settings.email_from_name} <{settings.email_from}>",
            "to": [destinataire],
            "subject": sujet,
            "html": corps_html,
        }
        if attachments:
            payload["attachments"] = attachments
        resend.Emails.send(payload)
        return True
    except Exception:
        logger.exception("Échec de l'envoi email (Resend) à %s.", destinataire)
        return False


def _envoyer_sms_ovh(destinataire: str, message: str) -> bool:
    if not (settings.ovh_application_key and settings.ovh_application_secret
            and settings.ovh_consumer_key and settings.ovh_sms_service_name):
        logger.warning("Identifiants OVH SMS incomplets — SMS non envoyé à %s.", destinataire)
        return False

    base_url = _OVH_BASE_URLS.get(settings.ovh_sms_endpoint, _OVH_BASE_URLS["ovh-eu"])
    chemin = f"/sms/{settings.ovh_sms_service_name}/jobs"
    url = base_url + chemin
    corps = json.dumps(
        {"message": message, "receivers": [destinataire], "senderForResponse": True},
        separators=(",", ":"),
    )
    timestamp = str(int(time.time()))
    # Schéma de signature OVH API (v6/v7) : "$1$" + sha1("AS+CK+METHODE+URL+CORPS+TIMESTAMP")
    a_signer = "+".join([
        settings.ovh_application_secret, settings.ovh_consumer_key, "POST", url, corps, timestamp,
    ])
    signature = "$1$" + hashlib.sha1(a_signer.encode("utf-8")).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Ovh-Application": settings.ovh_application_key,
        "X-Ovh-Consumer": settings.ovh_consumer_key,
        "X-Ovh-Timestamp": timestamp,
        "X-Ovh-Signature": signature,
    }
    try:
        reponse = httpx.post(url, content=corps, headers=headers, timeout=10)
        reponse.raise_for_status()
        return True
    except Exception:
        logger.exception("Échec de l'envoi SMS (OVH) à %s.", destinataire)
        return False


def _envoyer_sms_twilio(destinataire: str, message: str) -> bool:
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
        logger.warning("Identifiants Twilio incomplets — SMS non envoyé à %s.", destinataire)
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    try:
        reponse = httpx.post(
            url,
            data={"From": settings.twilio_from_number, "To": destinataire, "Body": message},
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=10,
        )
        reponse.raise_for_status()
        return True
    except Exception:
        logger.exception("Échec de l'envoi SMS (Twilio) à %s.", destinataire)
        return False


def envoyer_sms(destinataire: str, message: str) -> bool:
    """Envoie un SMS via le fournisseur configuré (`settings.sms_provider`,
    "ovh" par défaut ou "twilio"). False (sans exception) si non configuré ou
    en cas d'échec."""
    if not destinataire:
        return False
    if settings.sms_provider == "twilio":
        return _envoyer_sms_twilio(destinataire, message)
    return _envoyer_sms_ovh(destinataire, message)


def notifier_lead_slack(
    *,
    prospect_id: int,
    prenom: str,
    telephone: str,
    economie_annuelle: float,
    utm_source: str | None,
    utm_campaign: str | None,
) -> bool:
    """Ping Slack (ou Discord, même format webhook `{"text": ...}`) à la
    capture d'un lead depuis la landing publique — la fenêtre de rappel des
    5 premières minutes est le facteur n°1 de conversion. False (sans
    exception) si `SLACK_WEBHOOK_URL` absente ou si l'envoi échoue."""
    if not settings.slack_webhook_url:
        logger.info("SLACK_WEBHOOK_URL absente — notification lead non envoyée (prospect=%s).", prospect_id)
        return False
    lien_fiche = f"{settings.frontend_conseiller_base_url}/prospects/{prospect_id}"
    texte = (
        f"🔥 *Nouveau lead landing* — {prenom}\n"
        f"📞 <tel:{telephone}|{telephone}>  ·  💰 ~{economie_annuelle:.0f} €/an estimés\n"
        f"📍 Source : {utm_source or 'direct'}"
        + (f" / {utm_campaign}" if utm_campaign else "")
        + f"\n<{lien_fiche}|Voir la fiche prospect>"
    )
    try:
        reponse = httpx.post(settings.slack_webhook_url, json={"text": texte}, timeout=10)
        reponse.raise_for_status()
        return True
    except Exception:
        logger.exception("Échec de la notification Slack pour le lead prospect=%s.", prospect_id)
        return False


def template_email_relance_j1_landing(prenom: str, economie_annuelle: float) -> str:
    """Email récap envoyé J+1 après un lead landing (backend/workers/tasks.py
    ::relancer_email_j1_leads_landing, P3.2) — point de contact stratégique
    distinct du SMS immédiat, pour un prospect que le conseiller n'a pas
    encore réussi à joindre."""
    eco = int(economie_annuelle)
    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:560px;margin:auto">
      <h2>Bonjour {prenom},</h2>
      <p>Vous avez estimé hier vos économies possibles avec IA Conseil :
         <strong>jusqu'à {eco} €/an*</strong> sur vos abonnements.</p>
      <p>Notre conseiller n'a pas encore réussi à vous joindre par téléphone —
         répondez à cet email ou rappelez-nous pour fixer un créneau qui vous
         convient.</p>
      <p style="font-size:11px;color:#666;margin-top:32px">
        *Estimation indicative basée sur la médiane payée par nos clients dans la même catégorie.
        Résultat définitif après entretien conseiller.
      </p>
    </div>
    """


# ==============================================================================
#  SÉQUENCE DE NURTURING (P4.2) — 4 emails éducatifs J+2 à J+5 pour les leads
#  landing non convertis, dans la continuité de l'email récap J+1 ci-dessus.
#  Déclenchés par backend/workers/tasks.py::relancer_nurturing_leads_landing.
#  Chaque email inclut un lien de désabonnement en un clic (RGPD — retrait du
#  consentement aussi simple que son octroi), voir
#  backend/routers/leads_public.py::desabonner_lead.
# ==============================================================================
def _pied_email_nurturing(url_desabonnement: str) -> str:
    return f"""
      <p style="font-size:11px;color:#666;margin-top:32px">
        IA Conseil — vous recevez cet email suite à votre demande d'estimation sur notre landing.
        <a href="{url_desabonnement}" style="color:#666">Se désinscrire</a> de ces emails à tout moment.
      </p>
    """


def template_email_nurturing_j2(prenom: str, url_desabonnement: str) -> str:
    """« Les 3 pièges des forfaits mobile en 2026 » — contenu éducatif, pas de
    relance commerciale directe (P4.2)."""
    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:560px;margin:auto">
      <h2>Bonjour {prenom},</h2>
      <p>Avant votre prochain changement d'opérateur, voici 3 pièges fréquents sur les
         forfaits mobile en 2026 :</p>
      <ol>
        <li><strong>Le prix "à vie" qui ne l'est pas</strong> — beaucoup d'offres promotionnelles
            augmentent après 12 mois sans préavis explicite. Vérifiez la date de fin de promo.</li>
        <li><strong>La data "illimitée" plafonnée en 4G/5G</strong> — au-delà d'un certain volume,
            le débit est bridé sans que ce soit toujours mis en avant.</li>
        <li><strong>L'engagement caché sur le mobile associé à une box</strong> — certains packs
            box + mobile prolongent l'engagement des deux lignes en cas de changement d'une seule.</li>
      </ol>
      <p>Notre conseiller peut vérifier gratuitement votre contrat actuel pour ces 3 points.</p>
      {_pied_email_nurturing(url_desabonnement)}
    </div>
    """


def template_email_nurturing_j3(prenom: str, url_desabonnement: str) -> str:
    """« Comment changer d'opérateur sans coupure de service » (P4.2)."""
    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:560px;margin:auto">
      <h2>Bonjour {prenom},</h2>
      <p>La peur n°1 avant de changer d'opérateur : la coupure de service. Voici comment
         l'éviter :</p>
      <ul>
        <li><strong>Portabilité du numéro</strong> — votre numéro actuel est conservé
            automatiquement, aucune démarche à faire vous-même.</li>
        <li><strong>Chevauchement des deux lignes</strong> — le nouvel opérateur active votre
            ligne avant la résiliation de l'ancienne, il n'y a jamais de jour sans service.</li>
        <li><strong>Résiliation gérée pour vous</strong> — c'est notre conseiller qui s'occupe
            des démarches de résiliation auprès de votre ancien fournisseur, vous n'avez
            qu'à signer un mandat.</li>
      </ul>
      <p>Un conseiller peut vous expliquer le calendrier exact de la transition en 10 minutes.</p>
      {_pied_email_nurturing(url_desabonnement)}
    </div>
    """


def template_email_nurturing_j4(prenom: str, url_desabonnement: str) -> str:
    """« Le bon réflexe avant de renégocier vos factures d'énergie » (P4.2)."""
    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:560px;margin:auto">
      <h2>Bonjour {prenom},</h2>
      <p>Avant de renégocier votre contrat d'électricité ou de gaz, un seul réflexe compte :
         comparez le <strong>prix du kWh hors taxes</strong>, pas le montant total de la
         facture (qui dépend surtout de votre consommation, pas du fournisseur).</p>
      <p>Sur cette base, les écarts entre fournisseurs peuvent représenter plusieurs centaines
         d'euros par an pour un foyer moyen — sans changer vos habitudes de consommation.</p>
      <p>Notre conseiller compare pour vous les offres actuellement disponibles sur votre
         zone et vous indique s'il y a une économie réelle à la clé, sans engagement de
         votre part.</p>
      {_pied_email_nurturing(url_desabonnement)}
    </div>
    """


def template_email_nurturing_j5(prenom: str, economie_annuelle: float, url_desabonnement: str) -> str:
    """Dernier email de la séquence — relance directe avec l'estimation
    initiale en rappel (P4.2)."""
    eco = int(economie_annuelle)
    return f"""
    <div style="font-family:system-ui,sans-serif;max-width:560px;margin:auto">
      <h2>Bonjour {prenom},</h2>
      <p>Voici le dernier email de notre part sur cette estimation — votre économie potentielle
         restait estimée à <strong>jusqu'à {eco} €/an*</strong>.</p>
      <p>Si vous souhaitez qu'un conseiller y jette un œil, répondez simplement à cet email ou
         rappelez-nous — sinon, vous ne recevrez plus d'autre message de notre part à ce sujet.</p>
      <p style="font-size:11px;color:#666;margin-top:32px">
        *Estimation indicative basée sur la médiane payée par nos clients dans la même catégorie.
      </p>
      {_pied_email_nurturing(url_desabonnement)}
    </div>
    """


# ==============================================================================
#  NOTIFICATIONS MÉTIER — relances, alerte fin d'engagement, digest quotidien
#  admin, envoi du lien portail au prospect. Porté de src/notifications.py
#  (script cron/schtasks autonome, SMTP+Telegram) vers ce service async
#  déclenché par Celery Beat (backend/workers/tasks.py::envoyer_digest_quotidien
#  et ::alerter_fins_engagement) ; les canaux d'envoi (Resend/SMS) sont ceux
#  déjà en place ci-dessus, à la place de SMTP/Telegram.
# ==============================================================================


async def _lire_parametre(db: AsyncSession, cle: str) -> str | None:
    parametre = await db.get(Parametre, cle)
    return parametre.valeur if parametre else None


async def _destinataire_admin(db: AsyncSession) -> str | None:
    return await _lire_parametre(db, "notif_email_destinataire")


def _parser_date_courte(date_str: str | None):
    """Format d/m/Y — utilisé pour `date_fin_engagement` (saisi en texte libre
    "JJ/MM/AAAA", voir ContratForm.tsx). Ne pas réutiliser pour `date_relance`,
    qui est en ISO (voir _parser_date_relance ci-dessous)."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None


def _parser_date_relance(date_str: str | None):
    """`date_relance` est en ISO (YYYY-MM-DD) — les champs `<input type="date">`
    du frontend et `POST /prospects/{id}/relance-effectuee` produisent ce
    format nativement. Doit rester aligné avec backend/routers/dashboard.py::
    _parse_date_relance."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str.strip())
    except (ValueError, AttributeError):
        return None


def _jours_retard(date_relance_str: str | None) -> int | None:
    d = _parser_date_relance(date_relance_str)
    if d is None:
        return None
    return (datetime.now().date() - d).days


async def relances_du_jour(db: AsyncSession) -> list[dict]:
    """Prospects (statut 'À relancer'/'Relancé') et clients (statut_relance
    idem) dont la date de relance est aujourd'hui ou dépassée — même filtre
    que le tableau de bord."""
    statuts = ("À relancer", "Relancé")

    prospects = (
        await db.execute(select(Prospect).where(Prospect.statut.in_(statuts)))
    ).scalars().all()
    clients = (
        await db.execute(select(Client).where(Client.statut_relance.in_(statuts)))
    ).scalars().all()

    def _filtrer(entites, type_entite: str) -> list[dict]:
        out = []
        for e in entites:
            if not e.date_relance:
                continue
            retard = _jours_retard(e.date_relance)
            if retard is not None and retard >= 0:
                out.append({
                    "type": type_entite, "id": e.id,
                    "nom": f"{e.prenom or ''} {e.nom or ''}".strip(),
                    "telephone": e.telephone or "",
                    "economie": float(e.economie_estimee_an or 0),
                    "retard_jours": retard,
                })
        return out

    relances = _filtrer(prospects, "Prospect") + _filtrer(clients, "Client")
    return sorted(relances, key=lambda x: -x["retard_jours"])


def construire_message_relances(relances: list[dict]) -> str:
    if not relances:
        return "Aucune relance en attente aujourd'hui. Bonne journée !"
    lignes = [f"{len(relances)} relance(s) à traiter aujourd'hui :", ""]
    for r in relances:
        quand = f"en retard de {r['retard_jours']} j" if r["retard_jours"] > 0 else "aujourd'hui"
        lignes.append(
            f"- [{r['type']}] {r['nom']} — {r['telephone']} — "
            f"économie estimée {r['economie']:.0f} €/an ({quand})"
        )
    return "\n".join(lignes)


def _corps_email_fin_engagement(prenom: str, date_fin: str, offre_alternative: dict | None) -> str:
    """Email de rappel de fin d'engagement — proposition de renégociation si
    une offre moins chère a été identifiée dans le catalogue."""
    proposition = ""
    if offre_alternative:
        proposition = (
            f"<p>Nous avons identifié une offre à <b>{offre_alternative.get('prix_mensuel', 0)} €/mois</b> "
            f"({offre_alternative.get('nom', '')} — {offre_alternative.get('fournisseur', '')}) qui vous "
            f"ferait économiser <b>{round(offre_alternative.get('economie_annuelle', 0), 2)} €/an</b>.</p>"
        )
    return (
        f"<p>Bonjour {prenom},</p>"
        f"<p>Votre engagement actuel se termine le <b>{date_fin}</b>.</p>"
        f"{proposition}"
        "<p>Contactez-nous pour faire le point avant l'échéance et éviter toute reconduction non souhaitée.</p>"
    )


async def alerter_fin_engagement(db: AsyncSession, jours_avant: int = JOURS_AVANT_ALERTE_ENGAGEMENT) -> list[dict]:
    """Envoie, pour chaque contrat atteignant le seuil d'alerte (fin
    d'engagement dans exactement `jours_avant` jours — déclenche une seule
    fois), un email au client avec proposition d'offre alternative si une
    économie existe. Renvoie la liste des contrats traités (pour le digest
    admin)."""
    from backend.services import offres_engine

    contrats = (
        await db.execute(select(Contrat).where(Contrat.date_fin_engagement.is_not(None)))
    ).scalars().all()

    aujourdhui = datetime.now().date()
    traites: list[dict] = []
    for contrat in contrats:
        date_fin = _parser_date_courte(contrat.date_fin_engagement)
        if date_fin is None or (date_fin - aujourdhui).days != jours_avant:
            continue

        client = await db.get(Client, contrat.client_id) if contrat.client_id else None

        alternatives = await offres_engine.comparer_offres(
            db, contrat.univers, contrat.categorie, float(contrat.cout_mensuel or 0),
            fournisseur_exclu=contrat.fournisseur,
        )
        meilleure = alternatives[0] if alternatives and alternatives[0]["economie_annuelle"] > 0 else None

        envoye = False
        if client is not None and client.email:
            corps = _corps_email_fin_engagement(client.prenom or "", contrat.date_fin_engagement, meilleure)
            envoye = envoyer_email(client.email, "Votre engagement arrive à échéance", corps)

        traites.append({
            "nom": f"{client.prenom} {client.nom}".strip() if client else "",
            "fournisseur": contrat.fournisseur, "nom_offre": contrat.nom_offre,
            "date_fin_engagement": contrat.date_fin_engagement, "email_envoye": envoye,
        })
    return traites


def _construire_message_engagement(traites: list[dict]) -> str:
    if not traites:
        return ""
    lignes = [f"\n\n{len(traites)} contrat(s) arrivent à échéance dans "
              f"{JOURS_AVANT_ALERTE_ENGAGEMENT} jours (alerte client envoyée) :", ""]
    for t in traites:
        statut = "email envoyé" if t["email_envoye"] else "email NON envoyé (vérifier config client)"
        lignes.append(f"- {t['nom']} — {t['fournisseur']} {t['nom_offre']} — "
                       f"fin le {t['date_fin_engagement']} ({statut})")
    return "\n".join(lignes)


async def envoyer_digest_admin(texte: str, sujet: str, db: AsyncSession) -> bool:
    """Envoie un texte au conseiller/admin configuré (`Parametre
    notif_email_destinataire`, cf. Admin > Paramètres) — aucun envoi si non
    configuré."""
    destinataire = await _destinataire_admin(db)
    if not destinataire:
        logger.warning("notif_email_destinataire non configuré — notification admin non envoyée : %s", sujet)
        return False
    corps_html = "<pre style=\"font-family:inherit;white-space:pre-wrap;\">" + texte + "</pre>"
    return envoyer_email(destinataire, sujet, corps_html)


async def envoyer_digest_quotidien(db: AsyncSession, resume_hebdo: bool = False) -> dict:
    """Digest quotidien admin : relances du jour + alertes de fin
    d'engagement (email client envoyé le cas échéant) + résumé hebdomadaire
    optionnel (lundi). Porté de src/notifications.py::main()."""
    relances = await relances_du_jour(db)
    message = construire_message_relances(relances)

    contrats_traites = await alerter_fin_engagement(db)
    message += _construire_message_engagement(contrats_traites)

    if resume_hebdo:
        nb_prospects = len((await db.execute(select(Prospect.id))).all())
        nb_clients = len((await db.execute(select(Client.id))).all())
        eco_totale = sum(float(c.economie_estimee_an or 0) for c in (await db.execute(select(Client))).scalars().all())
        message += (
            "\n\nRésumé hebdomadaire :\n"
            f"- Prospects en base : {nb_prospects}\n"
            f"- Clients en base : {nb_clients}\n"
            f"- Économies totales estimées (clients) : {round(eco_totale, 2)} €/an"
        )

    envoye = await envoyer_digest_admin(message, f"IA Conseil — {len(relances)} relance(s) aujourd'hui", db)
    return {"relances": len(relances), "contrats_fin_engagement": len(contrats_traites), "envoye": envoye}


async def notifier_changement_prix(db: AsyncSession, alertes: list[dict]) -> bool:
    """Alerte admin immédiate quand `veille_engine.lancer_veille()` détecte un
    ou plusieurs changements de prix sur les sources surveillées."""
    if not alertes:
        return False
    lignes = [f"📈 {len(alertes)} changement(s) de prix détecté(s) — à valider dans "
              f"Admin > Veille prix :", ""]
    for a in alertes:
        sens = "🔺" if a["nouveau_prix"] > a["ancien_prix"] else "🔻"
        lignes.append(f"- {sens} {a['fournisseur']} {a['nom_offre']} — "
                       f"{a['ancien_prix']:.2f} € → {a['nouveau_prix']:.2f} €")
    texte = "\n".join(lignes)
    return await envoyer_digest_admin(texte, f"IA Conseil — {len(alertes)} changement(s) de prix détecté(s)", db)


async def notifier_nouvelles_offres_staging(db: AsyncSession, resume: dict) -> bool:
    """Alerte admin immédiate quand `catalogue_engine.ingerer_toutes_sources_actives()`
    détecte de nouvelles offres, des changements ou des offres à vérifier —
    à valider dans Admin > Catalogue > Offres détectées."""
    total = resume.get("detectees", 0) + resume.get("a_verifier", 0) + resume.get("changements", 0)
    if not total:
        return False
    lignes = [
        f"📚 Ingestion catalogue terminée — {total} offre(s) à examiner dans Admin > Catalogue :",
        "",
        f"- 🆕 Nouvelles offres : {resume.get('detectees', 0)}",
        f"- 🔄 Changements sur des offres existantes : {resume.get('changements', 0)}",
        f"- ⚠️ À vérifier (prix non détecté) : {resume.get('a_verifier', 0)}",
    ]
    texte = "\n".join(lignes)
    return await envoyer_digest_admin(texte, f"IA Conseil — {total} offre(s) détectée(s) au catalogue", db)


async def notifier_offres_moins_cheres(db: AsyncSession, alertes: list[dict]) -> bool:
    """Alerte admin immédiate quand `alertes_offres_engine.detecter_offres_moins_cheres()`
    détecte une ou plusieurs offres moins chères que le contrat actif d'un
    client — le conseiller valide ensuite chacune (Admin > Alertes offres)
    avant tout envoi au client (voir alertes_offres_engine.valider_alerte)."""
    if not alertes:
        return False
    lignes = [f"💰 {len(alertes)} offre(s) moins chère(s) détectée(s) — à valider dans "
              f"Admin > Alertes offres :", ""]
    for a in alertes:
        lignes.append(
            f"- {a['nom_client']} — {a['fournisseur']} {a['nom_offre']} — "
            f"{a['cout_actuel']:.2f} € → {a['cout_propose']:.2f} € "
            f"(économie {a['economie_annuelle']:.2f} €/an)"
        )
    texte = "\n".join(lignes)
    return await envoyer_digest_admin(texte, f"IA Conseil — {len(alertes)} offre(s) moins chère(s) détectée(s)", db)


async def notifier_veille_marche_hebdomadaire(db: AsyncSession, rapport) -> bool:
    """Alerte admin immédiate quand `veille_marche_agent.generer_rapport_hebdomadaire()`
    détecte une ou plusieurs offres pas encore au catalogue IA Conseil —
    à intégrer dans Admin > IA Conseil > Veille marché (§3.4)."""
    offres = rapport.offres_detectees or []
    if not offres:
        return False
    lignes = [
        f"🔍 Veille marché « {rapport.categorie_slug} » — {len(offres)} offre(s) potentiellement "
        f"nouvelle(s) à examiner dans Admin > IA Conseil > Veille marché :",
        "",
    ]
    for o in offres:
        prix = f"{o['prix_mensuel']:.2f} €/mois" if o.get("prix_mensuel") is not None else "prix à vérifier"
        confiance = "✅ fiable" if o.get("confiance") == "fiable" else "⚠️ à vérifier"
        lignes.append(f"- {o.get('fournisseur', '?')} — {o.get('nom_offre', '?')} — {prix} ({confiance})")
    texte = "\n".join(lignes)
    return await envoyer_digest_admin(
        texte, f"IA Conseil — {len(offres)} offre(s) détectée(s) en veille marché ({rapport.categorie_slug})", db
    )


def envoyer_demande_documents_prospect(prospect: dict, url: str, duree_jours: int) -> dict:
    """Envoie au prospect (SMS + email, selon les coordonnées disponibles sur
    sa fiche) le lien à usage personnel lui permettant de transmettre
    lui-même sa facture et un test de débit — évite au conseiller d'avoir à
    les lui redemander par téléphone. `url` et `duree_jours` sont générés en
    amont (token public prospect). Renvoie {"sms_envoye": bool, "email_envoye": bool}."""
    prenom = (prospect.get("prenom") or "").strip()
    salutation = f"Bonjour {prenom}," if prenom else "Bonjour,"

    message_sms = (
        f"{salutation} merci de nous transmettre votre facture et un test de débit "
        f"via ce lien sécurisé : {url} (valable {duree_jours} jours). Votre conseiller."
    )
    corps_email = (
        f"<p>{salutation}</p>"
        f"<p>Pour finaliser votre étude, merci de nous transmettre directement, "
        f"sans avoir à nous les envoyer par téléphone ou par un autre biais :</p>"
        f"<ul><li>votre dernière facture (photo ou PDF)</li>"
        f"<li>un test de débit (capture d'écran ou export PDF nPerf / Speedtest)</li></ul>"
        f'<p><a href="{url}">{url}</a></p>'
        f"<p>Ce lien est personnel et valable {duree_jours} jours.</p>"
        f"<p>Votre conseiller.</p>"
    )

    telephone = prospect.get("telephone") or ""
    email = prospect.get("email") or ""
    sms_envoye = envoyer_sms(telephone, message_sms) if telephone else False
    email_envoye = envoyer_email(
        email, "Merci de nous transmettre votre facture et votre test de débit", corps_email
    ) if email else False
    return {"sms_envoye": sms_envoye, "email_envoye": email_envoye}


async def creer_notification_conseiller(db: AsyncSession, dossier: "Dossier", message: str) -> None:
    """Notification in-app pour le conseiller responsable du dossier — utilisée
    quand le client agit de son côté (upload de document, speedtest, signature
    de mandat) ou qu'un dossier change de statut, sans que le conseiller ne le
    sache tant qu'il n'a pas rouvert le dossier. `Dossier.conseiller_responsable`
    stocke le nom complet (voir routers/dossiers.py::creer_dossier), pas le
    username — on le résout ici. Ne fait rien si le dossier n'a pas de
    conseiller assigné ou si son compte est introuvable (ne bloque jamais
    l'action du client)."""
    from backend.models.notification import Notification
    from backend.models.user import User

    if not dossier.conseiller_responsable:
        return
    utilisateur = (
        await db.execute(select(User).where(User.nom_complet == dossier.conseiller_responsable))
    ).scalars().first()
    if utilisateur is None:
        return
    db.add(Notification(
        conseiller_username=utilisateur.username,
        dossier_id=dossier.id,
        message=message,
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    ))
    await db.commit()


async def creer_notification_document(db: AsyncSession, dossier: "Dossier") -> None:
    """Variante de `creer_notification_conseiller` pour les uploads de
    documents : si un client envoie plusieurs pièces d'affilée, on ne veut
    qu'une seule notification "nouveau document" en attente par dossier plutôt
    qu'une par fichier — sinon la cloche du conseiller se remplit d'entrées
    redondantes pour un seul événement métier (le client a répondu à la
    demande de documents)."""
    from backend.models.notification import Notification
    from backend.models.user import User

    if not dossier.conseiller_responsable:
        return
    utilisateur = (
        await db.execute(select(User).where(User.nom_complet == dossier.conseiller_responsable))
    ).scalars().first()
    if utilisateur is None:
        return

    message = f"Nouveau document — dossier #{dossier.id}."
    deja_en_attente = (
        await db.execute(
            select(Notification).where(
                Notification.conseiller_username == utilisateur.username,
                Notification.dossier_id == dossier.id,
                Notification.message == message,
                Notification.lu.is_(False),
            )
        )
    ).scalars().first()
    if deja_en_attente is not None:
        return

    db.add(Notification(
        conseiller_username=utilisateur.username,
        dossier_id=dossier.id,
        message=message,
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    ))
    await db.commit()


async def creer_notification_prospect(db: AsyncSession, prospect: "Prospect", message: str) -> None:
    """Variante de `creer_notification_conseiller` pour un prospect pas encore
    client (pas de `Dossier`) — utilisée quand il agit lui-même depuis son lien
    personnel (upload de facture, mise à jour de sa situation actuelle) sans que
    son conseiller ne le sache. `Prospect.cree_par` stocke le nom complet du
    conseiller qui l'a créé, même convention que `Dossier.conseiller_responsable`
    (voir backend/routers/prospects.py). Ne fait rien si le prospect n'a pas de
    créateur identifié ou si son compte est introuvable (ne bloque jamais
    l'action du prospect)."""
    from backend.models.notification import Notification
    from backend.models.user import User

    if not prospect.cree_par:
        return
    utilisateur = (
        await db.execute(select(User).where(User.nom_complet == prospect.cree_par))
    ).scalars().first()
    if utilisateur is None:
        return
    db.add(Notification(
        conseiller_username=utilisateur.username,
        message=message,
        lien=f"/prospects/{prospect.id}",
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    ))
    await db.commit()


async def creer_notification_generique(
    db: AsyncSession, conseiller_id: int, message: str, *, lien: str | None = None
) -> None:
    """Notification in-app hors CRM (sous-système IA Conseil — §2.3, §2.6) :
    pas de `Dossier` à pointer, `lien` porte une route relative à la place.
    Résout le username depuis `conseiller_id` (Integer, `utilisateurs.id`),
    contrairement à `creer_notification_conseiller` qui part d'un nom complet
    stocké sur le dossier CRM. Ne fait rien si le compte est introuvable."""
    from backend.models.notification import Notification
    from backend.models.user import User

    utilisateur = await db.get(User, conseiller_id)
    if utilisateur is None:
        return
    db.add(Notification(
        conseiller_username=utilisateur.username,
        message=message,
        lien=lien,
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
    ))
    await db.commit()


def template_email_fin_engagement_conseil(prenom: str, categorie_slug: str | None) -> str:
    categorie = categorie_slug or "votre contrat"
    return (
        f"<p>Bonjour {prenom},</p>"
        f"<p>Votre engagement sur {categorie} arrive à échéance dans moins de 60 jours. "
        "C'est le bon moment pour comparer les offres du marché et voir si une économie est possible.</p>"
        "<p>Votre conseiller reprendra contact avec vous prochainement.</p>"
    )


def template_email_nps_j30_conseil(prenom: str) -> str:
    return (
        f"<p>Bonjour {prenom},</p>"
        "<p>Cela fait un mois que nous avons finalisé votre dossier — nous aimerions savoir si tout "
        "se passe bien. Répondez simplement à cet email pour nous faire part de votre retour.</p>"
    )
