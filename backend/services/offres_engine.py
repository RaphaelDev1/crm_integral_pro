# ==============================================================================
#  OFFRES — moteur de comparaison et de recommandations, porté de
#  src/offres_engine.py (Streamlit, synchrone, `st.cache_data`) vers un
#  service async utilisable aussi bien par l'API (backend/routers/offres.py)
#  que par les tâches internes (ex. alerte fin d'engagement dans
#  notification_engine.alerter_fin_engagement). `ajouter_offre`/`maj_offre`
#  sont utilisées par backend/services/catalogue_engine.py lors de la
#  validation d'une offre détectée (offres_staging → offres).
# ==============================================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.offre import Offre


async def comparer_offres(
    db: AsyncSession,
    univers: str,
    categorie: str,
    cout_actuel_mensuel: float,
    fournisseurs_autorises: list[str] | None = None,
    fournisseur_exclu: str | None = None,
    data_go_min: float | None = None,
) -> list[dict]:
    """Compare les offres actives du catalogue pour un (univers, catégorie)
    donné à `cout_actuel_mensuel`. `data_go_min` : si fourni, exclut les
    offres mobiles dont le quota data est inférieur à la consommation
    actuelle du client — sans effet sur les offres dont le quota est 0 en
    catalogue (Box/Fibre, Énergie, Abonnements — data non applicable)."""
    resultat = await db.execute(
        select(Offre).where(
            Offre.actif.is_(True),
            Offre.univers == univers,
            Offre.categorie == categorie,
        )
    )
    resultats = []
    for o in resultat.scalars().all():
        if fournisseurs_autorises and o.fournisseur not in fournisseurs_autorises:
            continue
        if fournisseur_exclu and o.fournisseur == fournisseur_exclu:
            continue
        data_go_offre = float(o.data_go or 0)
        if data_go_min and data_go_offre and data_go_offre < data_go_min:
            continue
        prix = float(o.prix_mensuel or 0)
        frais = float(o.frais_activation or 0)
        frais_sim = float(o.frais_sim or 0)
        frais_resiliation = float(o.frais_resiliation or 0)
        frais_portabilite = float(o.frais_portabilite or 0)
        frais_annexes_total = round(frais + frais_sim + frais_resiliation + frais_portabilite, 2)
        eco_mens = round(cout_actuel_mensuel - prix, 2)
        eco_annuelle = round(eco_mens * 12, 2)
        resultats.append({
            "id": o.id, "nom": o.nom_offre, "fournisseur": o.fournisseur,
            "categorie": categorie, "univers": univers,
            "prix_mensuel": prix, "frais_activation": frais,
            "frais_sim": frais_sim, "frais_resiliation": frais_resiliation,
            "frais_portabilite": frais_portabilite, "frais_annexes_total": frais_annexes_total,
            "engagement": int(o.engagement_mois or 0),
            "caracteristiques": o.caracteristiques or "",
            "commission": float(o.commission_affiliation or 0),
            "data_go": data_go_offre,
            "economie_mensuelle": eco_mens, "economie_annuelle": eco_annuelle,
            "economie_annee_1": round(eco_annuelle - frais_annexes_total, 2),
            "cout_1_an": round(prix * 12 + frais, 2),
            "url_souscription": o.url_souscription or "",
            "code_affiliation": o.code_affiliation or "",
        })
    resultats.sort(key=lambda x: x["economie_annuelle"], reverse=True)
    return resultats


async def construire_recommandations(
    db: AsyncSession,
    service_principal: str,
    cout_tel: float,
    fournisseurs_autorises: list[str] | None = None,
    fournisseur_exclu: str | None = None,
    data_go_min: float | None = None,
) -> dict:
    """Construit le bloc de recommandations (offre principale + cross-sell)
    affiché à l'étape 4 du diagnostic, selon le service souscrit par le
    client (Mobile seul, Box/Fibre seule, Pack, ou Multi-lignes)."""
    async def top(categorie: str) -> list[dict]:
        resultats = await comparer_offres(
            db, "Télécom", categorie, cout_tel, fournisseurs_autorises, fournisseur_exclu, data_go_min
        )
        return resultats[:3]

    if service_principal == "Mobile uniquement":
        principal = ("📱 Vos meilleures offres Mobile", "Mobile", await top("Mobile"))
        cross = [
            ("🏠 Et si vous regardiez aussi la Box / Fibre ?", "Box / Fibre", await top("Box / Fibre")),
            ("📦 Nos packs Box + Mobile (pour aller plus loin)", "Pack Box + Mobile", await top("Pack Box + Mobile")),
        ]
    elif service_principal == "Box / Fibre uniquement":
        principal = ("🏠 Vos meilleures offres Box / Fibre", "Box / Fibre", await top("Box / Fibre"))
        cross = [
            ("📦 Top 3 de nos packs Box + Mobile", "Pack Box + Mobile", await top("Pack Box + Mobile")),
            ("📱 Nos 3 meilleurs forfaits Mobile", "Mobile", await top("Mobile")),
        ]
    elif service_principal == "Pack Box + Mobile":
        # Un pack combine box + mobile : le comparer à une offre Mobile seule ou Box seule
        # n'a pas de sens (le client perdrait l'autre service). On ne compare donc les packs
        # qu'entre eux, sans cross-sell vers du Mobile ou du Box / Fibre isolé.
        principal = ("📦 Vos meilleurs packs Box + Mobile", "Pack Box + Mobile", await top("Pack Box + Mobile"))
        cross = []
    else:
        ml = await top("Multi-lignes") or await top("Mobile")
        principal = ("📲 Vos meilleures offres Multi-lignes", "Multi-lignes", ml)
        cross = [
            ("📦 Top 3 de nos packs Box + Mobile", "Pack Box + Mobile", await top("Pack Box + Mobile")),
            ("🏠 Nos 3 meilleures offres Box / Fibre", "Box / Fibre", await top("Box / Fibre")),
        ]

    return {"principal": principal, "cross_sell": cross}


async def ajouter_offre(db: AsyncSession, d: dict) -> Offre:
    """Crée une nouvelle offre active dans le catalogue — porté de
    src/offres_engine.py::ajouter_offre, utilisé par catalogue_engine lors de
    la validation d'une offre détectée en staging."""
    offre = Offre(
        univers=d.get("univers"),
        categorie=d.get("categorie"),
        fournisseur=d.get("fournisseur"),
        nom_offre=d.get("nom_offre"),
        prix_mensuel=d.get("prix_mensuel", 0.0),
        frais_activation=d.get("frais_activation", 0.0),
        engagement_mois=d.get("engagement_mois", 0),
        caracteristiques=d.get("caracteristiques"),
        commission_affiliation=d.get("commission_affiliation", 0.0),
        data_go=d.get("data_go", 0.0),
        url_souscription=d.get("url_souscription", ""),
        code_affiliation=d.get("code_affiliation", ""),
        actif=True,
        date_maj=datetime.now().strftime("%d/%m/%Y"),
    )
    db.add(offre)
    await db.flush()
    return offre


CHAMPS_OFFRE_MODIFIABLES = {
    "prix_mensuel", "frais_activation", "engagement_mois", "caracteristiques",
    "commission_affiliation", "actif", "nom_offre", "fournisseur", "categorie", "data_go",
    "url_souscription", "code_affiliation",
}


async def maj_offre(db: AsyncSession, offre_id: int, champ: str, valeur) -> Offre | None:
    """Met à jour un champ d'une offre existante — porté de
    src/offres_engine.py::maj_offre."""
    if champ not in CHAMPS_OFFRE_MODIFIABLES:
        raise ValueError(f"Champ non autorisé : {champ}")
    offre = await db.get(Offre, offre_id)
    if offre is None:
        return None
    setattr(offre, champ, valeur)
    offre.date_maj = datetime.now().strftime("%d/%m/%Y")
    await db.flush()
    return offre
