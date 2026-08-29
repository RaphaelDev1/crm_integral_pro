# ==============================================================================
#  SESSIONS — cycle de vie d'une session de trame adaptative (créer, répondre,
#  recommandations, finalisation) + WebSocket temps réel. Sous-système neuf
#  "IA Conseil", isolé du CRM existant (préfixe /api/v1, voir
#  PLAN_IMPLEMENTATION_4_PHASES.md §0.5). Protégé par JWT (get_current_user
#  côté HTTP, get_current_user_ws côté WebSocket — la poignée de main WS ne
#  permet pas d'en-tête Authorization, le jeton est passé en query param).
# ==============================================================================
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import creer_session_view_token, decoder_session_view_token, get_current_user, get_current_user_ws
from backend.models.ia_conseil import ClientConseil, SessionFacture, SessionTrame
from backend.models.user import User
from backend.schemas.ia_conseil import (
    AlerteOverrideCreate,
    AlerteOverrideOut,
    CopilotIn,
    FactureAppliquerIn,
    NextQuestionOut,
    RecommandationOut,
    ReponseIn,
    SessionFactureOut,
    SessionPublicOut,
    SessionTrameCreate,
    SessionTrameOut,
    ShareTokenOut,
)
from backend.services import alertes_engine, copilot_engine, cross_sell_engine, ia_conseil_engine as engine
from backend.services import ia_conseil_facture, ia_conseil_pdf, ia_conseil_ws

router = APIRouter(prefix="/api/v1/sessions", tags=["ia_conseil_sessions"])


async def _charger_session(db: AsyncSession, session_id: uuid.UUID, user: User) -> SessionTrame:
    session = await db.get(SessionTrame, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session introuvable.")
    if user.role != "Admin" and session.conseiller_id is not None and session.conseiller_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cette session appartient à un autre conseiller.")
    return session


async def _resultat_next_question(db: AsyncSession, session: SessionTrame) -> NextQuestionOut:
    resultat = await engine.prochaine_question_session(db, session)
    return NextQuestionOut(
        question=resultat.question,
        questions_restantes_estimees=resultat.questions_restantes_estimees,
        terminee=resultat.question is None,
    )


def _vers_recommandation_out(entree: dict) -> RecommandationOut:
    return RecommandationOut(
        offre_id=entree["offre_id"],
        offre=entree["offre"],
        score=entree["score"],
        rang=entree["rang"],
        justifications=entree["justifications"],
        alertes=entree["alertes"],
        economie_mensuelle=entree["economie_mensuelle"],
        economie_annuelle=entree["economie_annuelle"],
    )


@router.post("", response_model=SessionTrameOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_user)])
async def creer_session(
    payload: SessionTrameCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        session = await engine.creer_session(db, payload.client_id, payload.categorie_slug, user.id, payload.canal)
    except engine.TrameIntrouvableError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{session_id}", response_model=SessionTrameOut, dependencies=[Depends(get_current_user)])
async def obtenir_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await _charger_session(db, session_id, user)


@router.get("/{session_id}/next-question", response_model=NextQuestionOut, dependencies=[Depends(get_current_user)])
async def next_question(session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    session = await _charger_session(db, session_id, user)
    return await _resultat_next_question(db, session)


@router.post("/{session_id}/answer", response_model=NextQuestionOut, dependencies=[Depends(get_current_user)])
async def repondre(
    session_id: uuid.UUID,
    payload: ReponseIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = await _charger_session(db, session_id, user)
    if session.etat != "en_cours":
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette session n'est plus en cours.")

    await engine.enregistrer_reponse(db, session, payload.question_id, payload.valeur)
    resultat = await _resultat_next_question(db, session)
    recommandations = await engine.calculer_recommandations(db, session)
    await db.commit()

    await ia_conseil_ws.publier(
        session_id,
        {
            "type": "reponse",
            "question_id": payload.question_id,
            "next_question": resultat.model_dump(),
            "recommandations": [_vers_recommandation_out(r).model_dump(mode="json") for r in recommandations],
        },
    )
    return resultat


@router.get("/{session_id}/recommandations", response_model=list[RecommandationOut], dependencies=[Depends(get_current_user)])
async def recommandations(session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    session = await _charger_session(db, session_id, user)
    resultats = await engine.calculer_recommandations(db, session)
    await db.commit()
    return [_vers_recommandation_out(r) for r in resultats]


@router.post("/{session_id}/finalize", response_model=SessionTrameOut, dependencies=[Depends(get_current_user)])
async def finaliser(session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    session = await _charger_session(db, session_id, user)
    if session.etat != "en_cours":
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette session n'est plus en cours.")

    await engine.calculer_recommandations(db, session)
    await engine.finaliser_session(db, session)
    await db.commit()
    await db.refresh(session)

    suggestions = await cross_sell_engine.suggestions_cross_sell(db, session.client_id) if session.client_id else []
    session.suggestions_cross_sell = suggestions

    await ia_conseil_ws.publier(session_id, {"type": "finalisee"})
    return session


@router.post("/{session_id}/override-alerte", response_model=AlerteOverrideOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_user)])
async def lever_alerte(
    session_id: uuid.UUID,
    payload: AlerteOverrideCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lève une alerte critique bloquante pour ce couple (session, offre) —
    justification obligatoire, auditée (§2.1). Ne rouvre pas la souscription :
    le conseiller doit la retenter après cet appel."""
    await _charger_session(db, session_id, user)
    override = await alertes_engine.enregistrer_override(
        db, session_id, payload.offre_id, payload.regle_nom, payload.justification, user.id
    )
    await db.commit()
    await db.refresh(override)
    return override


@router.post("/{session_id}/copilot", dependencies=[Depends(get_current_user)])
async def copilot(
    session_id: uuid.UUID,
    payload: CopilotIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Copilote conseiller en temps réel (§3.2) — réponse en streaming SSE.
    3 modes : suggestion (prochaine question), incoherence (détection),
    reformulation (aide à la reformulation d'une objection client)."""
    if payload.mode not in copilot_engine.MODES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Mode invalide : {payload.mode!r}.")

    session = await _charger_session(db, session_id, user)
    contexte = await copilot_engine.construire_contexte(db, session)
    await db.commit()

    return StreamingResponse(
        copilot_engine.stream_copilot(payload.mode, contexte, payload.message),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache, no-transform", "connection": "keep-alive"},
    )


@router.post(
    "/{session_id}/facture", response_model=SessionFactureOut, status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(get_current_user)],
)
async def televerser_facture(
    session_id: uuid.UUID,
    fichier: UploadFile,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Facture téléversée pendant la session (§3.1) — analysée en tâche de
    fond (voir facture(), qui reflète le statut le temps de l'analyse) puis
    proposée pour auto-remplissage, jamais appliquée automatiquement (voir
    appliquer_facture())."""
    session = await _charger_session(db, session_id, user)
    contenu = await fichier.read()
    try:
        facture = await ia_conseil_facture.televerser(db, session, contenu, fichier.filename or "")
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    await db.commit()
    await db.refresh(facture)

    from backend.workers.tasks import analyser_facture_session_task
    analyser_facture_session_task.delay(str(facture.id))

    return facture


@router.get(
    "/{session_id}/facture/{facture_id}", response_model=SessionFactureOut, dependencies=[Depends(get_current_user)]
)
async def facture(
    session_id: uuid.UUID, facture_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    await _charger_session(db, session_id, user)
    facture = await db.get(SessionFacture, facture_id)
    if facture is None or facture.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Facture introuvable.")
    return facture


@router.post(
    "/{session_id}/facture/{facture_id}/appliquer", response_model=NextQuestionOut,
    dependencies=[Depends(get_current_user)],
)
async def appliquer_facture(
    session_id: uuid.UUID,
    facture_id: uuid.UUID,
    payload: FactureAppliquerIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Applique les réponses confirmées/corrigées par le conseiller à partir
    d'une extraction de facture — jamais l'extraction brute directement."""
    session = await _charger_session(db, session_id, user)
    facture_obj = await db.get(SessionFacture, facture_id)
    if facture_obj is None or facture_obj.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Facture introuvable.")

    await ia_conseil_facture.appliquer(db, session, facture_obj, payload.reponses)
    resultat = await _resultat_next_question(db, session)
    recommandations = await engine.calculer_recommandations(db, session)
    await db.commit()

    await ia_conseil_ws.publier(
        session_id,
        {
            "type": "reponse",
            "next_question": resultat.model_dump(),
            "recommandations": [_vers_recommandation_out(r).model_dump(mode="json") for r in recommandations],
        },
    )
    return resultat


@router.get("/{session_id}/pdf", dependencies=[Depends(get_current_user)])
async def telecharger_pdf(session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    session = await _charger_session(db, session_id, user)
    client = await db.get(ClientConseil, session.client_id) if session.client_id else None
    if client is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Session sans client associé.")

    recommandations = await engine.calculer_recommandations(db, session)
    await db.commit()
    if not recommandations:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Aucune recommandation à synthétiser pour cette session.")

    conseiller = await db.get(User, session.conseiller_id) if session.conseiller_id else None
    pdf_bytes = await ia_conseil_pdf.generer_pdf_synthese(db, client, session, recommandations, conseiller)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"content-disposition": f'attachment; filename="synthese-ia-conseil-{session_id}.pdf"'},
    )


@router.post("/{session_id}/share-token", response_model=ShareTokenOut, dependencies=[Depends(get_current_user)])
async def creer_lien_partage(session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Émet un jeton lecture-seule (§1.5.1, multi-canal) : le conseiller envoie
    l'URL /trame/{id}/partage?token=... par SMS avant la visio, ou l'ouvre sur
    sa tablette en rendez-vous physique — pas d'authentification requise côté
    client."""
    await _charger_session(db, session_id, user)
    return ShareTokenOut(token=creer_session_view_token(session_id))


@router.get("/{session_id}/public", response_model=SessionPublicOut)
async def obtenir_session_publique(session_id: uuid.UUID, token: str, db: AsyncSession = Depends(get_db)):
    """Endpoint public (pas de Depends(get_current_user)) — protégé par le
    jeton `session_view` uniquement. Ne renvoie jamais conseiller_id, réponses
    brutes, ni aucune donnée de commission (déjà absente de OffreConseilOut/
    RecommandationOut)."""
    try:
        session_id_du_jeton = decoder_session_view_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Lien de partage invalide ou expiré.")
    if session_id_du_jeton != session_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Lien de partage invalide ou expiré.")

    session = await db.get(SessionTrame, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session introuvable.")

    next_question = await _resultat_next_question(db, session)
    recommandations = await engine.calculer_recommandations(db, session)
    await db.commit()

    return SessionPublicOut(
        id=session.id,
        categorie_slug=session.categorie_slug,
        etat=session.etat,
        demarree_le=session.demarree_le,
        terminee_le=session.terminee_le,
        next_question=next_question,
        recommandations=[_vers_recommandation_out(r) for r in recommandations],
    )


@router.websocket("/{session_id}/live")
async def live(
    websocket: WebSocket,
    session_id: uuid.UUID,
    user: User = Depends(get_current_user_ws),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(SessionTrame, session_id)
    if session is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if user.role != "Admin" and session.conseiller_id is not None and session.conseiller_id != user.id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    client, pubsub = ia_conseil_ws.ouvrir_abonnement(session_id)
    await pubsub.subscribe(ia_conseil_ws.canal_session(session_id))
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(ia_conseil_ws.canal_session(session_id))
        await pubsub.aclose()
        await client.aclose()
