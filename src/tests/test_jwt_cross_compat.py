# ==============================================================================
#  TESTS — compatibilité croisée des jetons JWT après la bascule de l'auth sur
#  backend/ : un jeton émis par backend/core/security.py doit rester décodable
#  par src/jwt_auth.py et exposer les champs lus par src/crm_api.py
#  (current["nom_complet"], current["role"]) — voir backend/core/security.py::
#  _creer_token, corrigé pour inclure nom_complet (régression-guard).
# ==============================================================================
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# backend/core/database.py lève une RuntimeError à l'import si DATABASE_URL est
# absent — une URL syntaxiquement valide suffit ici (aucune connexion réelle,
# creer_access_token() ne touche pas la base). Même idiome que backend/tests/conftest.py.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_ia_conseil")

import jwt_auth  # noqa: E402 — après l'ajustement de sys.path/DATABASE_URL ci-dessus
from backend.core.security import creer_access_token, creer_refresh_token  # noqa: E402
from backend.models.user import User  # noqa: E402


def _user(**kwargs) -> User:
    base = dict(
        id=42, username="conseiller1", nom_complet="Jean Conseiller",
        role="Conseiller", password_hash="x", actif=True,
    )
    base.update(kwargs)
    return User(**base)


def test_jeton_acces_backend_decode_par_jwt_auth_avec_les_champs_attendus_par_crm_api():
    token = creer_access_token(_user())

    payload = jwt_auth.decoder_token(token)

    # Champs effectivement lus par src/crm_api.py (current["nom_complet"] à 7
    # endroits, current["role"] via require_role) — sans nom_complet, ces
    # routes plantent en KeyError malgré un décodage réussi.
    assert payload["nom_complet"] == "Jean Conseiller"
    assert payload["role"] == "Conseiller"
    assert payload["user_id"] == 42
    assert payload["sub"] == "conseiller1"
    assert payload["type"] == "access"


def test_jeton_refresh_backend_inclut_aussi_nom_complet():
    """_creer_token() est un chemin de code unique pour access/refresh — même
    correctif pour les deux, même si le refresh token n'est jamais envoyé à
    crm_api.py (cohérence du payload plutôt que nécessité fonctionnelle)."""
    token = creer_refresh_token(_user())

    payload = jwt_auth.decoder_token(token)

    assert payload["nom_complet"] == "Jean Conseiller"
