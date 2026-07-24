# ==============================================================================
#  CONFIGURATION PYTEST — s'assure que la racine du dépôt est sur sys.path
#  pour que `import backend...` fonctionne quel que soit le répertoire courant
#  depuis lequel pytest est lancé.
# ==============================================================================
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# backend/core/database.py lève une RuntimeError à l'import si DATABASE_URL est
# absent (Postgres non provisionné en dev/CI, voir ROADMAP_EXECUTION.md sprint 2).
# La création d'un engine SQLAlchemy async est paresseuse (aucune connexion tant
# qu'aucune requête n'est exécutée) : une URL syntaxiquement valide suffit à
# rendre backend.core.security/backend.main importables dans les tests qui ne
# frappent pas réellement la base (ex. get_current_user surchargé).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_ia_conseil")
