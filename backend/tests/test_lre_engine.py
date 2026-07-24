# ==============================================================================
#  TESTS — backend/services/lre_engine.py : dégradation (lève LreEngineError,
#  ne renvoie jamais silencieusement un échec) tant qu'AR24 n'est pas
#  configuré, et comportement nominal une fois configuré (httpx mocké, aucun
#  appel réseau réel).
# ==============================================================================
import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.services import lre_engine


def _run(coro):
    return asyncio.run(coro)


def test_envoyer_lre_leve_erreur_si_non_configure():
    with patch.object(lre_engine.settings, "ar24_api_key", ""):
        with pytest.raises(lre_engine.LreEngineError, match="AR24_API_KEY absente"):
            _run(lre_engine.envoyer_lre({"prenom": "A", "nom": "B", "email": "a@b.fr"}, "sujet", b"pdf", "x.pdf"))


def test_verifier_statut_lre_leve_erreur_si_non_configure():
    with patch.object(lre_engine.settings, "ar24_api_key", ""):
        with pytest.raises(lre_engine.LreEngineError):
            _run(lre_engine.verifier_statut_lre("lre-123"))


def test_envoyer_lre_leve_erreur_si_appel_http_echoue():
    reponse_erreur = httpx.Response(500, text="boom", request=httpx.Request("POST", "https://api.ar24.fr/lre/send"))
    with patch.object(lre_engine.settings, "ar24_api_key", "fake-key"), \
         patch.object(httpx.AsyncClient, "request", new=AsyncMock(return_value=reponse_erreur)):
        with pytest.raises(lre_engine.LreEngineError, match="500"):
            _run(lre_engine.envoyer_lre({"prenom": "A", "nom": "B", "email": "a@b.fr"}, "sujet", b"pdf", "x.pdf"))


def test_envoyer_lre_retourne_lre_id_et_statut_si_ok():
    reponse_ok = httpx.Response(
        200, json={"id": "lre-42", "status": "envoyee"},
        request=httpx.Request("POST", "https://api.ar24.fr/lre/send"),
    )
    with patch.object(lre_engine.settings, "ar24_api_key", "fake-key"), \
         patch.object(httpx.AsyncClient, "request", new=AsyncMock(return_value=reponse_ok)):
        resultat = _run(lre_engine.envoyer_lre({"prenom": "A", "nom": "B", "email": "a@b.fr"}, "sujet", b"pdf", "x.pdf"))

    assert resultat == {"lre_id": "lre-42", "statut": "envoyee"}


def test_verifier_statut_lre_ok():
    reponse_ok = httpx.Response(
        200, json={"status": "distribue"},
        request=httpx.Request("GET", "https://api.ar24.fr/lre/lre-42/status"),
    )
    with patch.object(lre_engine.settings, "ar24_api_key", "fake-key"), \
         patch.object(httpx.AsyncClient, "request", new=AsyncMock(return_value=reponse_ok)):
        resultat = _run(lre_engine.verifier_statut_lre("lre-42"))

    assert resultat == {"lre_id": "lre-42", "statut": "distribue"}


def test_telecharger_preuve_depot_leve_erreur_si_appel_http_echoue():
    reponse_erreur = httpx.Response(404, request=httpx.Request("GET", "https://api.ar24.fr/lre/lre-42/proof"))
    with patch.object(lre_engine.settings, "ar24_api_key", "fake-key"), \
         patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=reponse_erreur)):
        with pytest.raises(lre_engine.LreEngineError):
            _run(lre_engine.telecharger_preuve_depot("lre-42"))
