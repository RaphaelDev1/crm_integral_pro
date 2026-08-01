# ==============================================================================
#  SPEEDTEST BACKEND — implémentation minimale du protocole du client
#  LibreSpeed (garbage/empty/upload/getIP) pour un test de débit auto-hébergé,
#  appelé par le widget vendorisé dans frontend-portail/public/js/speedtest.js.
#
#  Aucune donnée client ne transite ici — ces routes ne font que mesurer la
#  bande passante brute (données jetées, jamais persistées). C'est pourquoi
#  elles restent publiques et hors du système de token : la soumission du
#  résultat mesuré, elle, reste gatée par le token public
#  (POST /portail/{token}/speedtest, voir backend/routers/portail_public.py).
# ==============================================================================
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/speedtest-backend", tags=["speedtest_backend"])

_TAILLE_CHUNK = 1024 * 1024  # 1 Mo
_CHUNK = b"\x00" * _TAILLE_CHUNK
_NB_CHUNKS_MAX = 1000  # borne défensive : 1 Go max par requête garbage


@router.get("/garbage")
async def garbage(ckSize: int = 4):
    """Cible du test de download : renvoie `ckSize` Mo de zéros."""
    nb_chunks = max(1, min(ckSize, _NB_CHUNKS_MAX))

    def _stream():
        for _ in range(nb_chunks):
            yield _CHUNK

    return StreamingResponse(
        _stream(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=garbage.bin"},
    )


@router.get("/empty")
async def ping():
    """Cible du test de ping/jitter : réponse vide la plus rapide possible."""
    return Response(status_code=200)


@router.post("/upload")
async def upload(request: Request):
    """Cible du test d'upload : draine le corps de la requête sans le stocker."""
    async for _ in request.stream():
        pass
    return Response(status_code=200)


@router.get("/getIP")
async def get_ip(request: Request):
    ip = request.client.host if request.client else ""
    return {"processedString": ip}
