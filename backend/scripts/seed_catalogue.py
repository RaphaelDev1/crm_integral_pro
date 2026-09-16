# ==============================================================================
#  SEED CATALOGUE — peuple `offres` avec un jeu de données de test couvrant les
#  fournisseurs télécom/énergie/abonnements déjà connus du moteur de catalogue
#  (backend/services/catalogue_engine.py::LISTE_OPERATEURS_TEL /
#  LISTE_FOURNISSEURS_ENERGIE / CATEGORIES_ABO). Prix et caractéristiques sont
#  fictifs — usage dev/test uniquement, ne pas exécuter en prod.
#
#  Usage :
#      python -m backend.scripts.seed_catalogue
# ==============================================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.offre import Offre

DATE_MAJ = datetime.now().strftime("%d/%m/%Y")


def _pg_engine():
    # psycopg2 attend `sslmode=require`, pas le `ssl=require` d'asyncpg/Neon —
    # sans cette traduction, psycopg2 rejette le DSN ("invalid connection
    # option \"ssl\"").
    url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("ssl=require", "sslmode=require")
    return create_engine(url)


# URL placeholder par défaut — ne résout jamais (domaine .invalid, RFC 2606),
# volontaire pour la plupart des fournisseurs tant qu'on n'a pas de vraie page
# de souscription + sélecteurs dédiés pour eux (voir OPERATEURS_SUPPORTES et
# SELECTEURS_PAR_OPERATEUR dans backend/services/souscription_engine.py — seul
# Free y a une automatisation fiable ; Bouygues y figure mais sans sélecteurs
# dédiés, donc repli sur les sélecteurs génériques uniquement, best-effort).
# Utiliser `url_souscription=` pour les offres où on a la vraie URL (ex. Free
# ci-dessous) : sans ça, "Pré-remplir la souscription" ouvre cette URL bidon
# et échoue toujours dès la navigation, avant même d'essayer de remplir quoi
# que ce soit.
URL_SOUSCRIPTION_DEFAUT = "https://exemple-test.invalid/souscription"


def _offre(univers, categorie, fournisseur, nom_offre, prix_mensuel, *,
           frais_activation=0.0, engagement_mois=0, data_go=0.0,
           commission_affiliation=0.0, caracteristiques="", code_affiliation="TEST",
           url_souscription=URL_SOUSCRIPTION_DEFAUT):
    return Offre(
        univers=univers,
        categorie=categorie,
        fournisseur=fournisseur,
        nom_offre=nom_offre,
        prix_mensuel=prix_mensuel,
        frais_activation=frais_activation,
        engagement_mois=engagement_mois,
        caracteristiques=caracteristiques,
        commission_affiliation=commission_affiliation,
        data_go=data_go,
        actif=True,
        url_souscription=url_souscription,
        code_affiliation=code_affiliation,
        date_maj=DATE_MAJ,
    )


def offres_catalogue_test() -> list[Offre]:
    offres: list[Offre] = []

    # -- Télécom / Mobile -----------------------------------------------------
    offres += [
        _offre("Télécom", "Mobile", "Orange", "Forfait 100 Go", 19.99, data_go=100,
               commission_affiliation=25, caracteristiques="Appels/SMS illimités, 5G incluse"),
        # Free est le seul fournisseur avec une automatisation Playwright fiable
        # (voir OPERATEURS_SUPPORTES dans souscription_engine.py) — vraie URL de
        # souscription mobile (forfait seul, pas de vente de téléphone). Pour une
        # future offre mobile+téléphone, utiliser plutôt
        # "https://mobile.free.fr/shop?from=subscribe".
        _offre("Télécom", "Mobile", "Free", "Forfait 5G 150 Go", 19.99, data_go=150,
               commission_affiliation=20, caracteristiques="Appels/SMS illimités, 5G, roaming Europe/DOM",
               url_souscription="https://mobile.free.fr/souscription/options"),
        _offre("Télécom", "Mobile", "Free", "Série Free 110 Go", 12.99, data_go=110,
               commission_affiliation=15, caracteristiques="Appels/SMS illimités, sans engagement",
               url_souscription="https://mobile.free.fr/souscription/options"),
        _offre("Télécom", "Mobile", "SFR", "Forfait 130 Go", 17.99, data_go=130,
               commission_affiliation=22, caracteristiques="Appels/SMS illimités, 5G incluse"),
        _offre("Télécom", "Mobile", "Bouygues", "B&You 100 Go", 15.99, data_go=100,
               commission_affiliation=20, caracteristiques="Sans engagement, 5G incluse"),
        _offre("Télécom", "Mobile", "YouPrice (Réseau Orange)", "Forfait 60 Go", 9.99, data_go=60,
               commission_affiliation=15, caracteristiques="Sans engagement, réseau Orange"),
    ]

    # -- Télécom / Box / Fibre -------------------------------------------------
    offres += [
        _offre("Télécom", "Box / Fibre", "Orange", "Livebox Fibre", 39.99,
               frais_activation=49, engagement_mois=12, commission_affiliation=40,
               caracteristiques="Fibre jusqu'à 2 Gb/s, TV incluse"),
        _offre("Télécom", "Box / Fibre", "Free", "Freebox Pop", 29.99,
               frais_activation=0, engagement_mois=0, commission_affiliation=35,
               caracteristiques="Fibre jusqu'à 1 Gb/s, sans engagement",
               url_souscription="https://signup.free.fr/subscribe_promo/00_choose_offre.pl?pre_box=pop#pop"),
        _offre("Télécom", "Box / Fibre", "SFR", "Box Fibre", 35.99,
               frais_activation=49, engagement_mois=12, commission_affiliation=38,
               caracteristiques="Fibre jusqu'à 1 Gb/s, TV incluse"),
        _offre("Télécom", "Box / Fibre", "Bouygues", "Bbox Fibre", 33.99,
               frais_activation=49, engagement_mois=12, commission_affiliation=36,
               caracteristiques="Fibre jusqu'à 2 Gb/s"),
    ]

    # -- Télécom / Pack Box + Mobile -------------------------------------------
    offres += [
        _offre("Télécom", "Pack Box + Mobile", "Orange", "Pack Open Fibre", 54.99,
               frais_activation=49, engagement_mois=12, commission_affiliation=55,
               caracteristiques="Fibre + forfait mobile 100 Go inclus"),
        _offre("Télécom", "Pack Box + Mobile", "Free", "Freebox + Forfait", 45.99,
               frais_activation=0, engagement_mois=0, commission_affiliation=50,
               caracteristiques="Fibre + forfait mobile 150 Go inclus"),
        _offre("Télécom", "Pack Box + Mobile", "SFR", "Pack Fibre + Mobile", 49.99,
               frais_activation=49, engagement_mois=12, commission_affiliation=52,
               caracteristiques="Fibre + forfait mobile 130 Go inclus"),
        _offre("Télécom", "Pack Box + Mobile", "Bouygues", "Pack Bbox + B&You", 47.99,
               frais_activation=49, engagement_mois=12, commission_affiliation=50,
               caracteristiques="Fibre + forfait mobile 100 Go inclus"),
    ]

    # -- Télécom / Multi-lignes -------------------------------------------------
    offres += [
        _offre("Télécom", "Multi-lignes", "Orange", "Multi-SIM famille", 34.99, data_go=200,
               commission_affiliation=30, caracteristiques="3 lignes mobiles mutualisées, 200 Go partagés"),
        _offre("Télécom", "Multi-lignes", "SFR", "Multi-lignes Pro", 39.99, data_go=250,
               commission_affiliation=32, caracteristiques="Jusqu'à 5 lignes, 250 Go partagés"),
    ]

    # -- Énergie / Électricité --------------------------------------------------
    offres += [
        _offre("Énergie", "Électricité", "EDF", "Tarif Bleu", 85.0,
               commission_affiliation=45, caracteristiques="Tarif réglementé, prix indicatif 6 kVA"),
        _offre("Énergie", "Électricité", "Engie", "Elec Référence", 80.0,
               commission_affiliation=42, caracteristiques="Prix indexé, prix indicatif 6 kVA"),
        _offre("Énergie", "Électricité", "TotalEnergies", "Offre Verte Fixe", 78.0,
               commission_affiliation=40, caracteristiques="Prix fixe 1 an, électricité verte"),
        _offre("Énergie", "Électricité", "Eni", "Electricité Eco", 75.0,
               commission_affiliation=38, caracteristiques="Prix fixe 2 ans"),
        _offre("Énergie", "Électricité", "Vattenfall", "Electricité Online", 76.0,
               commission_affiliation=38, caracteristiques="Souscription 100% en ligne"),
        _offre("Énergie", "Électricité", "Ekwateur", "Elec 100% Verte", 82.0,
               commission_affiliation=44, caracteristiques="Électricité renouvelable garantie d'origine"),
        _offre("Énergie", "Électricité", "OHM Énergie", "Elec Eco", 74.0,
               commission_affiliation=36, caracteristiques="Prix indexé, service client digital"),
    ]

    # -- Énergie / Gaz -----------------------------------------------------------
    offres += [
        _offre("Énergie", "Gaz", "EDF", "Gaz Naturel", 65.0,
               commission_affiliation=40, caracteristiques="Tarif réglementé, prix indicatif"),
        _offre("Énergie", "Gaz", "Engie", "Gaz Référence", 62.0,
               commission_affiliation=38, caracteristiques="Prix indexé"),
        _offre("Énergie", "Gaz", "TotalEnergies", "Gaz Fixe", 63.0,
               commission_affiliation=38, caracteristiques="Prix fixe 1 an"),
    ]

    # -- Énergie / Électricité Pro & Gaz Pro --------------------------------------
    offres += [
        _offre("Énergie", "Électricité Pro", "EDF", "Elec Pro", 150.0,
               commission_affiliation=60, caracteristiques="Offre professionnelle, 12-36 kVA"),
        _offre("Énergie", "Gaz Pro", "Engie", "Gaz Pro", 140.0,
               commission_affiliation=58, caracteristiques="Offre professionnelle, petit conso"),
    ]

    # -- Abonnements ---------------------------------------------------------------
    offres += [
        _offre("Abonnements", "Streaming Vidéo", "Netflix", "Standard", 13.49,
               commission_affiliation=5, caracteristiques="2 écrans simultanés, HD"),
        _offre("Abonnements", "Streaming Vidéo", "Disney+", "Standard", 8.99,
               commission_affiliation=5, caracteristiques="Catalogue Disney/Marvel/Star Wars"),
        _offre("Abonnements", "Streaming Vidéo", "Amazon Prime Video", "Prime", 6.99,
               commission_affiliation=4, caracteristiques="Inclus avec Amazon Prime"),
        _offre("Abonnements", "Musique", "Spotify", "Premium", 10.99,
               commission_affiliation=4, caracteristiques="Sans publicité, écoute hors-ligne"),
        _offre("Abonnements", "Musique", "Deezer", "Premium", 10.99,
               commission_affiliation=4, caracteristiques="Sans publicité, écoute hors-ligne"),
        _offre("Abonnements", "Salle de sport", "Basic-Fit", "Comfort", 29.99,
               commission_affiliation=10, caracteristiques="Accès toutes salles France"),
        _offre("Abonnements", "Salle de sport", "Fitness Park", "Classique", 24.99,
               commission_affiliation=10, caracteristiques="Accès salle de rattachement"),
        _offre("Abonnements", "SaaS / Logiciel", "Microsoft", "Microsoft 365 Famille", 9.99,
               commission_affiliation=8, caracteristiques="6 utilisateurs, 1 To OneDrive chacun"),
        _offre("Abonnements", "SaaS / Logiciel", "Google", "Google Workspace Business Starter", 6.90,
               commission_affiliation=8, caracteristiques="Par utilisateur, 30 Go Drive"),
    ]

    return offres


def seed_catalogue() -> int:
    """Insère le catalogue de test si `offres` est vide. Renvoie le nombre de
    lignes créées (0 si la table contenait déjà des offres)."""
    engine = _pg_engine()
    with Session(engine) as session:
        n = session.execute(select(func.count()).select_from(Offre)).scalar()
        if n:
            return 0

        offres = offres_catalogue_test()
        session.add_all(offres)
        session.commit()
        return len(offres)


def main() -> None:
    n = seed_catalogue()
    if n == 0:
        print("La table offres contient déjà des données — rien créé.")
        return
    print(f"{n} offres de test insérées dans le catalogue.")


if __name__ == "__main__":
    main()
