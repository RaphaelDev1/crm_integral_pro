# ==============================================================================
#  ANTI_BIAIS_ENGINE — garde-fou §2.6 : le modèle économique d'IA Conseil est
#  une commission % à la souscription, un conseiller a donc un intérêt
#  financier à recommander l'offre la plus commissionnée plutôt que la mieux
#  notée pour le client. Ce module détecte, par conseiller, la fréquence à
#  laquelle l'offre souscrite (1) n'est pas la mieux classée (rang 1) et (2)
#  rapporte plus de commission que celle qui l'était — signal de biais
#  possible, jamais une preuve, à faire vérifier par un superviseur.
#
#  Aucune colonne "commission" dénormalisée sur Recommandation : la commission
#  d'une offre se calcule à la demande via offre.fournisseur_id ->
#  fournisseur.taux_commission, comme le fait déjà
#  routers/ia_conseil_souscriptions.py::_calculer_commission_prevue.
# ==============================================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.ia_conseil import Fournisseur, OffreConseil, Recommandation, Souscription
from backend.models.parametre import Parametre
from backend.models.user import User
from backend.services import notification_engine

SEUIL_RATIO_DEFAUT = 0.3
CLE_PARAMETRE_SEUIL_RATIO = "seuil_alerte_biais_commercial"


async def _lire_seuil_ratio(db: AsyncSession) -> float:
    parametre = await db.get(Parametre, CLE_PARAMETRE_SEUIL_RATIO)
    if parametre and parametre.valeur:
        try:
            return float(parametre.valeur)
        except ValueError:
            pass
    return SEUIL_RATIO_DEFAUT


async def _commission_offre(db: AsyncSession, offre_id) -> float | None:
    offre = await db.get(OffreConseil, offre_id)
    if offre is None or offre.fournisseur_id is None or offre.prix_mensuel is None:
        return None
    fournisseur = await db.get(Fournisseur, offre.fournisseur_id)
    if fournisseur is None or fournisseur.taux_commission is None:
        return None
    return float(offre.prix_mensuel) * float(fournisseur.taux_commission) / 100


async def auditer_biais_commercial(db: AsyncSession) -> list[dict]:
    """Pour chaque souscription rattachée à une session de trame, compare la
    commission de l'offre souscrite à celle de la recommandation classée
    rang 1 de cette même session. Renvoie, par conseiller, le nombre de
    souscriptions concernées et le ratio de cas où l'offre souscrite n'était
    pas le rang 1 et rapportait davantage de commission ('biais possible')."""
    souscriptions = (
        await db.execute(select(Souscription).where(Souscription.session_id.is_not(None)))
    ).scalars().all()

    stats: dict[int | None, dict[str, int]] = {}
    for souscription in souscriptions:
        recommandations = (
            await db.execute(
                select(Recommandation)
                .where(Recommandation.session_id == souscription.session_id)
                .order_by(Recommandation.rang.asc())
            )
        ).scalars().all()
        if not recommandations:
            continue
        meilleure = recommandations[0]
        if meilleure.offre_id is None or souscription.offre_id is None:
            continue

        conseiller_stats = stats.setdefault(souscription.conseiller_id, {"nb_souscriptions_avec_session": 0, "nb_biais_possible": 0})
        conseiller_stats["nb_souscriptions_avec_session"] += 1

        if souscription.offre_id == meilleure.offre_id:
            continue  # offre souscrite = mieux classée, jamais un biais

        commission_souscrite = await _commission_offre(db, souscription.offre_id)
        commission_meilleure = await _commission_offre(db, meilleure.offre_id)
        if commission_souscrite is None or commission_meilleure is None:
            continue
        if commission_souscrite > commission_meilleure:
            conseiller_stats["nb_biais_possible"] += 1

    seuil_ratio = await _lire_seuil_ratio(db)
    resultats: list[dict] = []
    for conseiller_id, valeurs in stats.items():
        nb_total = valeurs["nb_souscriptions_avec_session"]
        ratio = valeurs["nb_biais_possible"] / nb_total if nb_total else 0.0
        resultats.append({
            "conseiller_id": conseiller_id,
            "nb_souscriptions_avec_session": nb_total,
            "nb_biais_possible": valeurs["nb_biais_possible"],
            "ratio": round(ratio, 3),
            "au_dela_du_seuil": ratio > seuil_ratio,
        })
    return resultats


async def auditer_et_notifier_superviseurs(db: AsyncSession) -> list[dict]:
    """Variante utilisée par la tâche Celery hebdomadaire : calcule l'audit,
    puis notifie chaque compte Admin pour tout conseiller au-delà du seuil."""
    resultats = await auditer_biais_commercial(db)
    conseillers_a_risque = [r for r in resultats if r["au_dela_du_seuil"] and r["conseiller_id"] is not None]
    if not conseillers_a_risque:
        return resultats

    admins = (await db.execute(select(User).where(User.role == "Admin"))).scalars().all()
    for admin in admins:
        for r in conseillers_a_risque:
            message = (
                f"Conseiller #{r['conseiller_id']} : {r['nb_biais_possible']}/{r['nb_souscriptions_avec_session']} "
                f"souscriptions favorisent une offre plus commissionnée que la mieux recommandée "
                f"(ratio {r['ratio']:.0%}) — à vérifier."
            )
            await notification_engine.creer_notification_generique(
                db, admin.id, message, lien="/ia-conseil/dashboard/anti-biais"
            )
    return resultats
