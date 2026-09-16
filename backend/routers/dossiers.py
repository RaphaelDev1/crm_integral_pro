# ==============================================================================
#  DOSSIERS — CRUD + machine à états. Protégé par JWT (conseillers uniquement).
# ==============================================================================
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.client import Client
from backend.models.comparaison_offre import ComparaisonOffre
from backend.models.contrat import Contrat
from backend.models.dossier import Dossier
from backend.models.offre import Offre
from backend.models.user import User
from backend.schemas.comparaison_offre import ComparaisonOffreOut
from backend.schemas.dossier import (
    DossierCreate,
    DossierOut,
    DossierUpdate,
    EnvoiLienClient,
    EtapeTimeline,
    NoteDossierCreate,
    PreRemplirSouscriptionIn,
    PreRemplirSouscriptionOut,
    TransitionStatut,
)
from backend.services import (
    audit_engine,
    demarches_engine,
    dossier_engine,
    dossier_notifications,
    souscription_engine,
    token_engine,
)

router = APIRouter(prefix="/dossiers", tags=["dossiers"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[DossierOut])
async def lister_dossiers(
    statut: str | None = None,
    client_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Dossier).order_by(Dossier.id.desc())
    if statut:
        query = query.where(Dossier.statut == statut)
    if client_id:
        query = query.where(Dossier.client_id == client_id)
    result = await db.execute(query)
    dossiers = result.scalars().all()
    for dossier in dossiers:
        dossier.documents_requis = [
            d["type_document"] for d in dossier_engine.documents_requis_pour_univers(dossier.univers)
        ]
    return dossiers


@router.get("/stagnants", response_model=list[DossierOut])
async def lister_dossiers_stagnants(db: AsyncSession = Depends(get_db)):
    """Doit rester déclarée avant /{dossier_id} (typé int) pour ne pas être
    masquée par cette route paramétrée."""
    return await dossier_engine.dossiers_stagnants(db)


@router.get("/{dossier_id}", response_model=DossierOut)
async def obtenir_dossier(dossier_id: int, db: AsyncSession = Depends(get_db)):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    dossier.documents_requis = [
        d["type_document"] for d in dossier_engine.documents_requis_pour_univers(dossier.univers)
    ]
    dossier.offre_nom = None
    if dossier.offre_cible_id:
        offre = await db.get(Offre, dossier.offre_cible_id)
        dossier.offre_nom = offre.nom_offre if offre else None
    return dossier


@router.post("", response_model=DossierOut, status_code=status.HTTP_201_CREATED)
async def creer_dossier(
    payload: DossierCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dossier = Dossier(
        **payload.model_dump(),
        date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        conseiller_responsable=user.nom_complet,
        notes_workflow=[],
    )
    db.add(dossier)
    await db.commit()
    await db.refresh(dossier)
    return dossier


@router.put("/{dossier_id}", response_model=DossierOut)
async def maj_dossier(
    dossier_id: int, payload: DossierUpdate, db: AsyncSession = Depends(get_db)
):
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(dossier, champ, valeur)
    await db.commit()
    await db.refresh(dossier)
    return dossier


@router.post("/{dossier_id}/transition", response_model=DossierOut)
async def transiter_dossier(
    dossier_id: int,
    payload: TransitionStatut,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.models.client import Client

    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    client = await db.get(Client, dossier.client_id)
    try:
        await dossier_engine.transiter(
            db, dossier, payload.nouveau_statut,
            par=user.username, commentaire=payload.commentaire,
            on_transition=lambda d, _ancien: dossier_notifications.notifier_transition(d, client),
        )
        # Pas d'auto-notification si c'est le conseiller responsable lui-même
        # qui vient de faire la transition — seulement utile si quelqu'un
        # d'autre agit sur son dossier.
        if dossier.conseiller_responsable and dossier.conseiller_responsable != user.nom_complet:
            from backend.services import notification_engine
            await notification_engine.creer_notification_conseiller(
                db, dossier, f"Dossier #{dossier.id} passé à « {dossier.statut} » par {user.nom_complet}."
            )
    except dossier_engine.TransitionInvalide as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    return dossier


@router.get("/{dossier_id}/timeline", response_model=list[EtapeTimeline])
async def obtenir_timeline_dossier(dossier_id: int, db: AsyncSession = Depends(get_db)):
    """Étapes du stepper à afficher au conseiller (même construction que celle
    servie au client via /portail/{token}/suivi)."""
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    signaux = await dossier_engine.signaux_timeline(db, dossier)
    return dossier_engine.construire_timeline(dossier, **signaux)


@router.get("/{dossier_id}/comparaison", response_model=ComparaisonOffreOut | None)
async def obtenir_comparaison_dossier(dossier_id: int, db: AsyncSession = Depends(get_db)):
    """Dernière comparaison d'offres (voir ComparaisonOffre.offres_comparees)
    faite pour le client de ce dossier, dans le même univers — permet à la
    fiche dossier de proposer de choisir une autre offre parmi celles
    comparées lors du diagnostic. Filtre sur `univers` en plus de `client_id`
    (contrairement à `obtenir_pdf_restitution` ci-dessous) pour ne pas
    remonter la comparaison d'un autre univers si le client en a plusieurs."""
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")

    return (
        await db.execute(
            select(ComparaisonOffre)
            .where(ComparaisonOffre.client_id == dossier.client_id, ComparaisonOffre.univers == dossier.univers)
            .order_by(ComparaisonOffre.id.desc())
        )
    ).scalars().first()


@router.post("/{dossier_id}/souscription/pre-remplir", response_model=PreRemplirSouscriptionOut)
async def pre_remplir_souscription(
    dossier_id: int,
    payload: PreRemplirSouscriptionIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ouvre, sur la machine où tourne ce backend, un navigateur pré-rempli avec
    les coordonnées du client sur le formulaire de souscription de l'offre
    cible du dossier (Free/Bouygues uniquement pour l'instant — voir
    souscription_engine.OPERATEURS_SUPPORTES). Ne soumet jamais la commande :
    le conseiller vérifie puis valide lui-même sur le site de l'opérateur.
    Portage de src/souscription_engine.py (app Streamlit en cours d'extinction)
    — ne fonctionne que si ce backend tourne en local, pas depuis un
    déploiement distant (le navigateur s'ouvre sur l'écran du process)."""
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    if not dossier.offre_cible_id:
        return PreRemplirSouscriptionOut(ok=False, message="Aucune offre cible sélectionnée pour ce dossier.")
    offre = await db.get(Offre, dossier.offre_cible_id)
    if offre is None:
        return PreRemplirSouscriptionOut(ok=False, message="Offre cible introuvable.")
    client = await db.get(Client, dossier.client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")

    contrat_mobile = None
    if "Mobile" in (offre.categorie or ""):
        # Ligne mobile de référence du client — même sélection que l'aide-mémoire
        # souscription (ligne_principale en priorité, voir demarches_engine.
        # _synchroniser_contrat_portabilite) — pilote conserver_numero/type_sim
        # dans le tunnel d'options Free Mobile (souscription_engine.
        # _remplir_options_mobile_free).
        contrat_mobile = (await db.execute(
            select(Contrat)
            .where(Contrat.client_id == client.id, Contrat.categorie == "Forfait mobile")
            .order_by(Contrat.ligne_principale.desc(), Contrat.id)
        )).scalars().first()

    donnees = souscription_engine.construire_donnees_client(client, contrat_mobile)
    ok, message = souscription_engine.lancer_souscription(
        offre.fournisseur or "", offre.url_souscription or "", donnees,
        code_affiliation=offre.code_affiliation or "", nom_offre=offre.nom_offre or "",
        categorie=offre.categorie or "",
        position=payload.window_position if payload else None,
        taille=payload.window_size if payload else None,
    )
    await audit_engine.enregistrer_action(
        db, entite_type="dossier", entite_id=dossier_id,
        action="Pré-remplissage souscription",
        details=f"{offre.fournisseur} — {offre.nom_offre or ''} ({'ouvert' if ok else 'échec'})",
        auteur=user.nom_complet,
    )
    await db.commit()

    url_manuelle = None
    if not ok and offre.url_souscription and not (urlsplit(offre.url_souscription).hostname or "").endswith(".invalid"):
        url_manuelle = offre.url_souscription
    return PreRemplirSouscriptionOut(ok=ok, message=message, url_manuelle=url_manuelle)


@router.post("/{dossier_id}/notes", response_model=DossierOut)
async def ajouter_note_dossier(
    dossier_id: int,
    payload: NoteDossierCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ajoute une note manuelle au journal du dossier (compte-rendu d'appel,
    remarque) sans changer son statut."""
    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    return await dossier_engine.ajouter_note(db, dossier, payload.texte, par=user.username)


async def _marquer_docs_demandes_si_besoin(db: AsyncSession, dossier: Dossier, *, par: str) -> None:
    """Le conseiller n'a pas d'action de statut dédiée pour « je viens de
    demander les documents » — copier/envoyer le lien de collecte EST cette
    action. On fait donc avancer automatiquement le dossier de "initie" à
    "docs_demandes" à ce moment-là, sans déclencher le template email/SMS
    générique de transition (le lien vient déjà d'être transmis
    explicitement par l'appelant — un second message serait redondant)."""
    if dossier.statut == "initie":
        await dossier_engine.transiter(db, dossier, "docs_demandes", par=par)


@router.post("/{dossier_id}/token-client", response_model=dict)
async def generer_lien_client(
    dossier_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Génère un lien unique à envoyer au client (SMS/email) pour qu'il accède
    à son dossier sans se connecter.
    """
    from backend.core.config import settings

    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")

    token = await token_engine.generer_token(
        db,
        client_id=dossier.client_id,
        dossier_id=dossier.id,
        cree_par=user.username,
    )
    # Copier le lien fait déjà partie de la démarche de demande de documents
    # (le conseiller ne le génère que pour le transmettre) — voir
    # _marquer_docs_demandes_si_besoin et construire_timeline.
    await _marquer_docs_demandes_si_besoin(db, dossier, par=user.username)
    # Garantit que la trame de questions du secteur (audit_*/portabilite) et
    # les autres démarches attendues existent déjà quand le client arrive sur
    # son lien — voir demarches_engine.creer_demarches_manquantes.
    await demarches_engine.creer_demarches_manquantes(db, dossier)

    url = token_engine.construire_url_client(token.token, base_url=settings.portail_client_base_url)
    return {
        "token": token.token,
        "url": url,
        "expire_le": token.date_expiration,
        "message_sms_suggere": (
            f"Bonjour, voici votre lien personnel pour finaliser votre changement d'offre "
            f"en quelques clics : {url} (valable 30 jours). Votre conseiller."
        ),
    }


@router.post("/{dossier_id}/envoyer-lien-client", response_model=dict)
async def envoyer_lien_client(
    dossier_id: int,
    payload: EnvoiLienClient,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Génère un lien unique (comme /token-client) et l'envoie immédiatement au
    client par le canal choisi par le conseiller (SMS ou email, selon la
    préférence du client) — automatise l'étape manuelle « copier le lien puis
    le transmettre » du flux conseiller."""
    from backend.core.config import settings
    from backend.models.client import Client
    from backend.services import notification_engine

    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    client = await db.get(Client, dossier.client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")

    token = await token_engine.generer_token(
        db,
        client_id=dossier.client_id,
        dossier_id=dossier.id,
        cree_par=user.username,
    )
    await _marquer_docs_demandes_si_besoin(db, dossier, par=user.username)
    await demarches_engine.creer_demarches_manquantes(db, dossier)

    url = token_engine.construire_url_client(token.token, base_url=settings.portail_client_base_url)
    prenom = client.prenom or ""

    sms_envoye = False
    email_envoye = False
    if payload.canal == "sms":
        message_sms = (
            f"Bonjour {prenom}, voici votre lien personnel pour finaliser votre changement d'offre "
            f"en quelques clics : {url} (valable 30 jours). Votre conseiller."
        ).strip()
        sms_envoye = notification_engine.envoyer_sms(client.telephone or "", message_sms)
    else:
        corps_email = (
            f"<p>Bonjour {prenom},</p>"
            f"<p>Voici votre lien personnel pour suivre et finaliser votre dossier en quelques clics :</p>"
            f'<p><a href="{url}">{url}</a></p>'
            f"<p>Ce lien est valable 30 jours.</p>"
            f"<p>Votre conseiller.</p>"
        )
        email_envoye = notification_engine.envoyer_email(
            client.email or "", "Votre lien personnel — suivi de dossier", corps_email
        )

    return {
        "token": token.token,
        "url": url,
        "expire_le": token.date_expiration,
        "sms_envoye": sms_envoye,
        "email_envoye": email_envoye,
    }


@router.get("/{dossier_id}/pdf-restitution")
async def obtenir_pdf_restitution(
    dossier_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Génère à la volée le PDF de restitution « vendeur » (tableau
    comparatif multi-offres + habillage configurable, voir
    backend/services/restitution_pdf_engine.py) — outil conseiller, jamais
    exposé côté portail client."""
    from backend.models.client import Client
    from backend.services import mandat_engine, restitution_pdf_engine

    dossier = await db.get(Dossier, dossier_id)
    if dossier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")

    client = await db.get(Client, dossier.client_id) if dossier.client_id else None
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")

    comparaison = (
        await db.execute(
            select(ComparaisonOffre)
            .where(ComparaisonOffre.client_id == client.id)
            .order_by(ComparaisonOffre.id.desc())
        )
    ).scalars().first()
    if comparaison is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Aucune comparaison d'offres enregistrée pour ce client — créez-en une avant de générer le PDF.",
        )

    branding = await mandat_engine.charger_branding(db, client, user)
    pdf_bytes = restitution_pdf_engine.generer_pdf_restitution_dossier(dossier, client, comparaison, branding)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="restitution_dossier_{dossier_id}.pdf"'},
    )
