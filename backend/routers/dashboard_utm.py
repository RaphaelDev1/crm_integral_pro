# ==============================================================================
#  DASHBOARD UTM — tunnel de conversion par campagne (P4.1) et attribution
#  multi-touch premier/dernier contact (P4.3). Distinct de dashboard.py
#  (résumé relances/KPIs) pour ne pas surcharger ce fichier déjà volumineux.
#
#  P4.1 : leads / rappels effectués / conversions / CA généré / CAC par
#  couple (utm_source, utm_campaign) — le CAC dépend d'une dépense pub saisie
#  manuellement (`campagnes_couts`, faute d'intégration API Meta/TikTok/Google
#  Ads directe).
#
#  P4.3 : attribution "légère" — la landing (frontend-portail/lib/attribution.ts)
#  conserve un historique first-party des visites avant conversion
#  (`touchpoints`) ; on en tire premier contact vs dernier contact (le dernier
#  contact correspond toujours à l'UTM du prospect lui-même, capturé au moment
#  de la conversion). Pas de modélisation d'attribution pondérée (Markov,
#  Shapley…) — hors scope, voir la note "outil tiers" du roadmap.
# ==============================================================================
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import get_current_user, require_role
from backend.models.campagne_cout import CampagneCout
from backend.models.commission import Commission
from backend.models.dossier import Dossier
from backend.models.historique_action import HistoriqueAction
from backend.models.prospect import Prospect
from backend.models.touchpoint import Touchpoint
from backend.models.user import User
from backend.schemas.dashboard_utm import (
    CampagneCoutIn,
    CampagneCoutOut,
    CampagneStatsOut,
    DashboardAttributionOut,
    DashboardUtmInscritsOut,
    DashboardUtmOut,
    InscritUtmOut,
    ParcoursAttributionOut,
    RepartitionSourceOut,
)

# Réservé aux Admin ("Responsable" côté libellé affiché, voir frontend-conseiller/lib/roles.ts)
# — données marketing/commerciales agrégées, pas destinées à tous les conseillers.
router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_role("Admin"))])

SOURCE_DIRECTE = "direct"


def _parse_date_creation(valeur: str | None) -> date | None:
    """`Prospect.date_creation` est écrit en "%d/%m/%Y %H:%M" (voir
    backend/routers/leads_public.py::capturer_lead)."""
    if not valeur:
        return None
    try:
        return datetime.strptime(valeur.strip(), "%d/%m/%Y %H:%M").date()
    except ValueError:
        return None


def _dans_periode(valeur: date | None, debut: date | None, fin: date | None) -> bool:
    if valeur is None:
        return False
    if debut and valeur < debut:
        return False
    if fin and valeur > fin:
        return False
    return True


async def _prospects_periode(db: AsyncSession, debut: date | None, fin: date | None) -> list[Prospect]:
    prospects = (
        await db.execute(select(Prospect).where(Prospect.origine.like("Landing%")))
    ).scalars().all()
    return [p for p in prospects if _dans_periode(_parse_date_creation(p.date_creation), debut, fin)]


async def _ca_par_client(db: AsyncSession) -> dict[int, float]:
    """{client_id: somme des commissions (tous statuts confondus) des dossiers
    de ce client} — inclut donc les commissions "attendues" pas encore
    confirmées ; suffisant pour un indicateur de pilotage marketing."""
    dossiers = (await db.execute(select(Dossier.id, Dossier.client_id))).all()
    dossier_vers_client = {d.id: d.client_id for d in dossiers}
    commissions = (await db.execute(select(Commission.dossier_id, Commission.montant))).all()
    ca: dict[int, float] = {}
    for dossier_id, montant in commissions:
        client_id = dossier_vers_client.get(dossier_id)
        if client_id is None:
            continue
        ca[client_id] = ca.get(client_id, 0.0) + float(montant or 0.0)
    return ca


async def _prospects_relances(db: AsyncSession) -> set[int]:
    ids = (
        await db.execute(
            select(HistoriqueAction.entite_id).where(
                HistoriqueAction.entite_type == "prospect",
                HistoriqueAction.action == "Relance effectuée",
            )
        )
    ).scalars().all()
    return set(ids)


@router.get("/utm-tunnel", response_model=DashboardUtmOut)
async def tunnel_conversion_utm(
    debut: str | None = None,
    fin: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    date_debut = date.fromisoformat(debut) if debut else None
    date_fin = date.fromisoformat(fin) if fin else None

    prospects = await _prospects_periode(db, date_debut, date_fin)
    ca_par_client = await _ca_par_client(db)
    relances = await _prospects_relances(db)

    couts = (await db.execute(select(CampagneCout))).scalars().all()
    couts_par_cle: dict[tuple[str, str | None], float] = {}
    for c in couts:
        if debut and c.mois < debut[:7]:
            continue
        if fin and c.mois > fin[:7]:
            continue
        cle = (c.utm_source, c.utm_campaign)
        couts_par_cle[cle] = couts_par_cle.get(cle, 0.0) + c.cout

    groupes: dict[tuple[str, str | None], dict] = {}
    for p in prospects:
        source = p.utm_source or SOURCE_DIRECTE
        cle = (source, p.utm_campaign)
        g = groupes.setdefault(cle, {"leads": 0, "rappels": 0, "conversions": 0, "ca": 0.0})
        g["leads"] += 1
        if p.id in relances:
            g["rappels"] += 1
        if p.converti_at:
            g["conversions"] += 1
            if p.client_id:
                g["ca"] += ca_par_client.get(p.client_id, 0.0)

    campagnes: list[CampagneStatsOut] = []
    total = {"leads": 0, "rappels": 0, "conversions": 0, "ca": 0.0, "cout": 0.0, "cout_renseigne": False}
    for (source, campaign), g in sorted(groupes.items(), key=lambda kv: -kv[1]["leads"]):
        cout = couts_par_cle.get((source, campaign))
        taux = (g["conversions"] / g["leads"] * 100) if g["leads"] else 0.0
        cac = (cout / g["conversions"]) if cout and g["conversions"] else None
        campagnes.append(CampagneStatsOut(
            utm_source=source, utm_campaign=campaign,
            leads=g["leads"], rappels_effectues=g["rappels"], conversions=g["conversions"],
            taux_conversion=round(taux, 1), ca_genere=round(g["ca"], 2),
            cout_pub=round(cout, 2) if cout is not None else None,
            cac=round(cac, 2) if cac is not None else None,
        ))
        total["leads"] += g["leads"]
        total["rappels"] += g["rappels"]
        total["conversions"] += g["conversions"]
        total["ca"] += g["ca"]
        if cout is not None:
            total["cout"] += cout
            total["cout_renseigne"] = True

    taux_total = (total["conversions"] / total["leads"] * 100) if total["leads"] else 0.0
    cac_total = (total["cout"] / total["conversions"]) if total["cout_renseigne"] and total["conversions"] else None

    return DashboardUtmOut(
        periode_debut=debut, periode_fin=fin,
        campagnes=campagnes,
        totaux=CampagneStatsOut(
            utm_source="Total", utm_campaign=None,
            leads=total["leads"], rappels_effectues=total["rappels"], conversions=total["conversions"],
            taux_conversion=round(taux_total, 1), ca_genere=round(total["ca"], 2),
            cout_pub=round(total["cout"], 2) if total["cout_renseigne"] else None,
            cac=round(cac_total, 2) if cac_total is not None else None,
        ),
    )


@router.get("/attribution", response_model=DashboardAttributionOut)
async def attribution_multi_touch(
    debut: str | None = None,
    fin: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    date_debut = date.fromisoformat(debut) if debut else None
    date_fin = date.fromisoformat(fin) if fin else None

    prospects = await _prospects_periode(db, date_debut, date_fin)
    ids = [p.id for p in prospects]
    touchpoints = (
        await db.execute(
            select(Touchpoint).where(Touchpoint.prospect_id.in_(ids)).order_by(Touchpoint.ordre)
        )
    ).scalars().all() if ids else []

    premiers_par_prospect: dict[int, str] = {}
    for tp in touchpoints:
        if tp.prospect_id not in premiers_par_prospect:
            premiers_par_prospect[tp.prospect_id] = tp.utm_source or SOURCE_DIRECTE

    parcours: dict[tuple[str, str], dict] = {}
    par_premier: dict[str, dict] = {}
    par_dernier: dict[str, dict] = {}
    for p in prospects:
        dernier = p.utm_source or SOURCE_DIRECTE
        premier = premiers_par_prospect.get(p.id, dernier)
        converti = bool(p.converti_at)

        cle = (premier, dernier)
        g = parcours.setdefault(cle, {"nb": 0, "conv": 0})
        g["nb"] += 1
        g["conv"] += 1 if converti else 0

        pg = par_premier.setdefault(premier, {"nb": 0, "conv": 0})
        pg["nb"] += 1
        pg["conv"] += 1 if converti else 0

        dg = par_dernier.setdefault(dernier, {"nb": 0, "conv": 0})
        dg["nb"] += 1
        dg["conv"] += 1 if converti else 0

    return DashboardAttributionOut(
        periode_debut=debut, periode_fin=fin,
        parcours=sorted(
            [
                ParcoursAttributionOut(
                    premier_touch_source=premier, dernier_touch_source=dernier,
                    nb_prospects=g["nb"], nb_conversions=g["conv"],
                )
                for (premier, dernier), g in parcours.items()
            ],
            key=lambda x: -x.nb_prospects,
        ),
        par_source_premier_touch=sorted(
            [RepartitionSourceOut(utm_source=s, nb_prospects=g["nb"], nb_conversions=g["conv"])
             for s, g in par_premier.items()],
            key=lambda x: -x.nb_prospects,
        ),
        par_source_dernier_touch=sorted(
            [RepartitionSourceOut(utm_source=s, nb_prospects=g["nb"], nb_conversions=g["conv"])
             for s, g in par_dernier.items()],
            key=lambda x: -x.nb_prospects,
        ),
    )


@router.get("/utm-inscrits", response_model=DashboardUtmInscritsOut)
async def inscrits_utm(
    debut: str | None = None,
    fin: str | None = None,
    utm_source: str | None = None,
    utm_campaign: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    date_debut = date.fromisoformat(debut) if debut else None
    date_fin = date.fromisoformat(fin) if fin else None

    prospects = await _prospects_periode(db, date_debut, date_fin)
    if utm_source:
        prospects = [p for p in prospects if (p.utm_source or SOURCE_DIRECTE) == utm_source]
    if utm_campaign:
        prospects = [p for p in prospects if p.utm_campaign == utm_campaign]

    prospects = sorted(prospects, key=lambda p: p.date_creation or "", reverse=True)[:500]

    inscrits = [
        InscritUtmOut(
            id=p.id,
            prenom=p.prenom,
            nom=p.nom,
            email=p.email,
            telephone=p.telephone,
            ville=p.ville,
            utm_source=p.utm_source or SOURCE_DIRECTE,
            utm_campaign=p.utm_campaign,
            date_creation=p.date_creation,
            statut=p.statut,
        )
        for p in prospects
    ]

    return DashboardUtmInscritsOut(periode_debut=debut, periode_fin=fin, total=len(inscrits), inscrits=inscrits)


@router.get("/couts-campagne", response_model=list[CampagneCoutOut])
async def lister_couts_campagne(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CampagneCout).order_by(CampagneCout.mois.desc()))
    return result.scalars().all()


@router.put("/couts-campagne", response_model=CampagneCoutOut)
async def enregistrer_cout_campagne(
    payload: CampagneCoutIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upsert par (utm_source, utm_campaign, mois) — permet de corriger une
    saisie sans créer de doublon dans le calcul du CAC."""
    existant = (
        await db.execute(
            select(CampagneCout).where(
                CampagneCout.utm_source == payload.utm_source,
                CampagneCout.utm_campaign == payload.utm_campaign,
                CampagneCout.mois == payload.mois,
            )
        )
    ).scalars().first()

    if existant is not None:
        existant.cout = payload.cout
        existant.notes = payload.notes
    else:
        existant = CampagneCout(
            utm_source=payload.utm_source, utm_campaign=payload.utm_campaign, mois=payload.mois,
            cout=payload.cout, notes=payload.notes, cree_par=user.nom_complet,
            date_creation=datetime.now().strftime("%d/%m/%Y %H:%M"),
        )
        db.add(existant)
    await db.commit()
    await db.refresh(existant)
    return existant


@router.delete("/couts-campagne/{cout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_cout_campagne(cout_id: int, db: AsyncSession = Depends(get_db)):
    cout = await db.get(CampagneCout, cout_id)
    if cout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entrée introuvable.")
    await db.delete(cout)
    await db.commit()
