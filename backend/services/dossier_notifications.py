# ==============================================================================
#  DOSSIER NOTIFICATIONS — templates email/SMS par statut de dossier, envoyés
#  automatiquement à chaque transition (`notifier_transition`) et lors d'une
#  relance de stagnation (`notifier_relance`). S'appuie sur
#  `notification_engine` qui dégrade proprement (renvoie False, ne lève
#  jamais) si Resend/Twilio/OVH ne sont pas configurés.
# ==============================================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services import notification_engine

if TYPE_CHECKING:
    from backend.models.client import Client
    from backend.models.dossier import Dossier


# Seuil de jours sans transition avant relance automatique, par statut. Les
# statuts absents du dict (ou terminaux) ne sont jamais relancés.
SEUILS_JOURS_PAR_STATUT: dict[str, int] = {
    "initie": 2,
    "docs_demandes": 3,
    "docs_recus": 3,
    "mandat_a_signer": 5,
    "soumis_fournisseur": 7,
    "en_activation": 10,
}

# Statuts pour lesquels un email/SMS est envoyé automatiquement dès que le
# dossier y transite (les statuts absents ne déclenchent aucun envoi — ex.
# `initie`, `docs_recus`, `echec`, `annule`, `facture`).
TEMPLATES_STATUT: dict[str, dict[str, str]] = {
    "docs_demandes": {
        "sujet": "Documents à nous transmettre",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Pour avancer sur votre dossier, merci de nous transmettre les documents "
            "demandés via votre lien personnel.</p><p>Votre conseiller.</p>"
        ),
        "sms": "Bonjour {prenom}, merci de nous transmettre vos documents via votre lien personnel pour avancer votre dossier.",
    },
    "mandat_a_signer": {
        "sujet": "Votre mandat est prêt à signer",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Votre mandat est prêt : vous pouvez le signer en ligne en 2 minutes via votre lien personnel.</p>"
            "<p>Votre conseiller.</p>"
        ),
        "sms": "Bonjour {prenom}, votre mandat est prêt à signer en ligne via votre lien personnel.",
    },
    "mandat_signe": {
        "sujet": "Mandat signé — merci",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Nous avons bien reçu votre mandat signé. Nous transmettons votre dossier au fournisseur.</p>"
            "<p>Votre conseiller.</p>"
        ),
        "sms": "Bonjour {prenom}, votre mandat signé est bien reçu. Nous transmettons votre dossier au fournisseur.",
    },
    "soumis_fournisseur": {
        "sujet": "Votre dossier est envoyé au fournisseur",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Votre dossier a été transmis au fournisseur. L'activation suit sous peu.</p>"
            "<p>Votre conseiller.</p>"
        ),
        "sms": "Bonjour {prenom}, votre dossier est transmis au fournisseur, l'activation suit.",
    },
    "actif": {
        "sujet": "Votre nouvelle offre est active",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Bonne nouvelle : votre nouvelle offre est désormais active.</p>"
            "<p>Votre conseiller.</p>"
        ),
        "sms": "Bonjour {prenom}, votre nouvelle offre est désormais active.",
    },
}

_TEMPLATE_RELANCE = {
    "sujet": "Votre dossier est en attente",
    "corps_html": (
        "<p>Bonjour {prenom},</p>"
        "<p>Votre dossier est en attente depuis quelques jours à l'étape « {statut_label} ». "
        "N'hésitez pas à consulter votre lien personnel ou à nous recontacter si vous avez une question.</p>"
        "<p>Votre conseiller.</p>"
    ),
    "sms": "Bonjour {prenom}, votre dossier est en attente à l'étape « {statut_label} ». Contactez-nous si besoin.",
}

LABELS_STATUT: dict[str, str] = {
    "initie": "dossier initié",
    "docs_demandes": "documents demandés",
    "docs_recus": "documents reçus",
    "mandat_a_signer": "mandat à signer",
    "mandat_signe": "mandat signé",
    "soumis_fournisseur": "soumis au fournisseur",
    "en_activation": "activation en cours",
    "actif": "actif",
}


def _envoyer(client: "Client", sujet: str, corps_html: str, sms: str) -> None:
    prenom = client.prenom or ""
    notification_engine.envoyer_email(client.email or "", sujet, corps_html.format(prenom=prenom))
    notification_engine.envoyer_sms(client.telephone or "", sms.format(prenom=prenom))


def notifier_transition(dossier: "Dossier", client: "Client | None") -> None:
    """Envoie le template email/SMS correspondant au nouveau statut du
    dossier, si un template existe pour ce statut. Ne lève jamais — les
    fonctions d'envoi sous-jacentes dégradent déjà proprement."""
    if client is None:
        return
    template = TEMPLATES_STATUT.get(dossier.statut)
    if template is None:
        return
    _envoyer(client, template["sujet"], template["corps_html"], template["sms"])


def notifier_relance(dossier: "Dossier", client: "Client | None") -> None:
    """Envoie le template générique de relance pour un dossier stagnant."""
    if client is None:
        return
    statut_label = LABELS_STATUT.get(dossier.statut, dossier.statut)
    prenom = client.prenom or ""
    notification_engine.envoyer_email(
        client.email or "",
        _TEMPLATE_RELANCE["sujet"],
        _TEMPLATE_RELANCE["corps_html"].format(prenom=prenom, statut_label=statut_label),
    )
    notification_engine.envoyer_sms(
        client.telephone or "",
        _TEMPLATE_RELANCE["sms"].format(prenom=prenom, statut_label=statut_label),
    )
