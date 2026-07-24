# ==============================================================================
#  ÉVAL QUALITÉ — audit_agent.py (Chantier 2, étape 2.5)
#
#  Script MANUEL, volontairement exclu de pytest/CI : il appelle réellement
#  l'API Anthropic (coût + non-déterminisme), à relancer à la main après tout
#  changement du prompt système ou de la liste d'outils dans src/audit_agent.py.
#
#  Charge les 10 cas de src/tests/cas_audit_eval/*.json sur un catalogue de
#  démonstration connu (offres_engine.inserer_offres_demo, dans une base
#  SQLite jetable — jamais la base réelle), lance l'agent sur chacun, compare
#  au résultat attendu (fournisseur, économie ±5 %, catégories), imprime un
#  score X/10.
#
#  Utilisation :
#     python scripts/eval_audit.py
#     ANTHROPIC_API_KEY=sk-ant-...   python scripts/eval_audit.py   (si la clé
#     n'est pas déjà dans src/.env)
# ==============================================================================
import json
import os
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC_DIR = RACINE / "src"
CAS_DIR = SRC_DIR / "tests" / "cas_audit_eval"

sys.path.insert(0, str(SRC_DIR))

MARGE_ECONOMIE = 0.05  # ±5%, comme demandé par le roadmap Chantier 2 (2.5)


def _preparer_base_jetable():
    """Redirige db.py vers une base SQLite jetable pré-remplie avec le catalogue
    de démonstration — jamais la base réelle (ia_conseil_crm.db)."""
    import db as db_module
    tmp_dir = tempfile.mkdtemp(prefix="ia_conseil_eval_audit_")
    db_module.DB_NAME = str(Path(tmp_dir) / "eval_audit.db")
    db_module.initialiser_bdd()

    from offres_engine import comparer_offres, inserer_offres_demo, lire_offres
    lire_offres.clear()
    comparer_offres.clear()
    inserer_offres_demo()
    lire_offres.clear()
    comparer_offres.clear()


def _charger_cas():
    cas = []
    for f in sorted(CAS_DIR.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            cas.append((f.stem, json.load(fh)))
    return cas


def _evaluer_cas(nom: str, cas: dict, resultat: dict) -> tuple[bool, str]:
    attendu = cas["attendu"]
    offres = resultat.get("offres_recommandees") or []

    if not offres:
        return False, "aucune offre recommandée"

    fournisseurs = {r["offre"].get("fournisseur") for r in offres}
    if not (fournisseurs & set(attendu.get("fournisseurs_acceptables", []))):
        return False, f"fournisseur(s) obtenu(s) {fournisseurs} hors de {attendu.get('fournisseurs_acceptables')}"

    categories_attendues = attendu.get("categories_attendues")
    if categories_attendues:
        categories_obtenues = {r["offre"].get("categorie") for r in offres}
        if not categories_obtenues.issubset(set(categories_attendues)):
            return False, f"catégorie(s) hors périmètre attendu : {categories_obtenues}"

    eco = resultat.get("economie_totale_an", 0.0)
    eco_min = attendu.get("economie_an_min")
    eco_max = attendu.get("economie_an_max")
    if eco_min is not None and eco < eco_min * (1 - MARGE_ECONOMIE):
        return False, f"économie {eco} € trop basse (attendu >= ~{eco_min} €)"
    if eco_max is not None and eco > eco_max * (1 + MARGE_ECONOMIE):
        return False, f"économie {eco} € trop haute (attendu <= ~{eco_max} €)"

    if attendu.get("points_attention_attendus") and not resultat.get("points_attention"):
        return False, "points_attention vide alors qu'un signalement était attendu"

    return True, "ok"


def main():
    _preparer_base_jetable()
    import audit_agent
    import secrets_config

    api_key = os.environ.get("ANTHROPIC_API_KEY") or secrets_config.anthropic_api_key()
    if not audit_agent.ANTHROPIC_OK or not api_key:
        print("ANTHROPIC_API_KEY manquant (ni dans l'environnement, ni dans src/.env) — "
              "impossible de lancer l'éval réelle.")
        sys.exit(1)

    cas_list = _charger_cas()
    if not cas_list:
        print(f"Aucun cas trouvé dans {CAS_DIR}")
        sys.exit(1)

    reussis = 0
    for nom, cas in cas_list:
        resultat = audit_agent.lancer_audit(cas["situation"], api_key=api_key)
        ok, motif = _evaluer_cas(nom, cas, resultat)
        reussis += int(ok)
        print(f"[{'OK  ' if ok else 'FAIL'}] {nom} — {motif}"
              f"  (économie retenue : {resultat.get('economie_totale_an')} €)")

    print(f"\nScore : {reussis}/{len(cas_list)}")
    if reussis < 8:
        print("⚠️ Sous le seuil de 8/10 recommandé avant de considérer le prompt stable "
              "(voir IA.CONSEIL.MD § Agent d'audit autonome).")


if __name__ == "__main__":
    main()
