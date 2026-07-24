# ==============================================================================
#  OFFRES (CATALOGUE) + MOTEUR DE COMPARAISON & RECOMMANDATIONS
# ==============================================================================
from datetime import datetime

import pandas as pd
import streamlit as st

from db import get_conn

CHAMPS_OFFRE = {
    "prix_mensuel", "frais_activation", "engagement_mois", "caracteristiques",
    "commission_affiliation", "actif", "nom_offre", "fournisseur", "categorie", "data_go",
    "url_souscription", "code_affiliation",
}


# ------------------------------------------------------------------------------
#  CATALOGUE
# ------------------------------------------------------------------------------
def ajouter_offre(d: dict):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO offres
        (univers, categorie, fournisseur, nom_offre, prix_mensuel, frais_activation,
         engagement_mois, caracteristiques, commission_affiliation, data_go,
         url_souscription, code_affiliation, actif, date_maj)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,?)
    """, (
        d.get("univers"),         d.get("categorie"),       d.get("fournisseur"),
        d.get("nom_offre"),       d.get("prix_mensuel", 0.0),d.get("frais_activation", 0.0),
        d.get("engagement_mois", 0),d.get("caracteristiques"),d.get("commission_affiliation", 0.0),
        d.get("data_go", 0.0),
        d.get("url_souscription", ""), d.get("code_affiliation", ""),
        datetime.now().strftime("%d/%m/%Y"),
    ))
    conn.commit()
    conn.close()
    lire_offres.clear()
    comparer_offres.clear()


@st.cache_data(ttl=300)
def lire_offres(univers=None, categorie=None, actif_seulement=True):
    conn   = get_conn()
    q      = "SELECT * FROM offres WHERE 1=1"
    params = []
    if actif_seulement:
        q += " AND actif=1"
    if univers:
        q += " AND univers=?";    params.append(univers)
    if categorie:
        q += " AND categorie=?";  params.append(categorie)
    q += " ORDER BY prix_mensuel ASC"
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    return df


def maj_offre(oid: int, champ: str, valeur):
    if champ not in CHAMPS_OFFRE:
        raise ValueError(f"Champ non autorisé : {champ}")
    conn = get_conn()
    c    = conn.cursor()
    c.execute(f"UPDATE offres SET {champ}=?, date_maj=? WHERE id=?",
              (valeur, datetime.now().strftime("%d/%m/%Y"), oid))
    conn.commit()
    conn.close()
    lire_offres.clear()
    comparer_offres.clear()


def supprimer_offre(oid: int):
    conn = get_conn()
    c    = conn.cursor()
    c.execute("DELETE FROM offres WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    lire_offres.clear()
    comparer_offres.clear()


def compter_offres() -> int:
    conn = get_conn()
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM offres WHERE actif=1")
    n = c.fetchone()[0]
    conn.close()
    return n


def inserer_offres_demo():
    """Catalogue de démonstration — à charger depuis Admin > Pré-remplir.
    Les URL de souscription sont des exemples (page d'accueil du fournisseur) à remplacer
    par vos vrais liens d'affiliation (Awin, Effiliation, Kwanko…) et vos propres codes."""
    demo = [
        # ---- TÉLÉCOM : Mobile ---- (u, cat, fournisseur, nom, prix, frais, engagement, caracteristiques, commission, data_go, url_souscription, code_affiliation)
        ("Télécom","Mobile","Free","Forfait Free 5G 350 Go",19.99,10,0,"350 Go - 5G - Appels/SMS illimités - Europe incluse",30,350,"https://mobile.free.fr","DEMO-FREE"),
        ("Télécom","Mobile","Bouygues","B&You 200 Go",13.99,0,0,"200 Go - 5G - Illimité - 35 Go Europe",25,200,"https://www.byou.fr","DEMO-BOUYGUES"),
        ("Télécom","Mobile","SFR","RED 130 Go",12.99,0,0,"130 Go - 5G - Illimité - 25 Go Europe",22,130,"https://www.red-by-sfr.fr","DEMO-SFR"),
        ("Télécom","Mobile","YouPrice (Réseau Orange)","Le Series 100 Go",9.99,0,0,"100 Go - Réseau Orange - Illimité",20,100,"https://www.youprice.fr","DEMO-YOUPRICE"),
        ("Télécom","Mobile","Orange","Forfait 5G 150 Go",24.99,0,0,"150 Go - 5G+ - Meilleure couverture",35,150,"https://boutique.orange.fr","DEMO-ORANGE"),
        ("Télécom","Mobile","Free","Forfait Free 2€",2.00,0,0,"2h appels - SMS illimités - 50 Mo",5,0,"https://mobile.free.fr","DEMO-FREE"),
        # ---- TÉLÉCOM : Box / Fibre (data_go non applicable) ----
        ("Télécom","Box / Fibre","Free","Freebox Pop Fibre",29.99,0,0,"Jusqu'à 5 Gbps - WiFi 7 - TV incluse",50,0,"https://signup.free.fr/subscribe_promo/#new","DEMO-FREE"),
        ("Télécom","Box / Fibre","Bouygues","Bbox Fibre Must",31.99,0,0,"2 Gbps - WiFi 6 - 180 chaînes",45,0,"https://www.bouyguestelecom.fr","DEMO-BOUYGUES"),
        ("Télécom","Box / Fibre","SFR","SFR Fibre Power",34.99,0,0,"2 Gbps - décodeur 4K",42,0,"https://www.sfr.fr","DEMO-SFR"),
        ("Télécom","Box / Fibre","Orange","Livebox Fibre",39.99,0,0,"2 Gbps - WiFi 6 - réseau Orange",55,0,"https://boutique.orange.fr","DEMO-ORANGE"),
        ("Télécom","Box / Fibre","Free","Freebox Ultra",49.99,0,0,"8 Gbps - WiFi 7 - Netflix/Disney+ inclus",60,0,"https://signup.free.fr/subscribe_promo/#new","DEMO-FREE"),
        # ---- TÉLÉCOM : Pack Box + Mobile (data_go = quota mobile inclus dans le pack) ----
        ("Télécom","Pack Box + Mobile","Bouygues","Pack Bbox + Forfait 200 Go",42.99,0,0,"Fibre 2 Gbps + 200 Go 5G",60,200,"https://www.bouyguestelecom.fr","DEMO-BOUYGUES"),
        ("Télécom","Pack Box + Mobile","SFR","Pack Fibre + RED 130 Go",44.99,0,0,"Fibre 2 Gbps + 130 Go",55,130,"https://www.sfr.fr","DEMO-SFR"),
        ("Télécom","Pack Box + Mobile","Free","Freebox Pop + Forfait 350 Go",39.98,0,0,"Fibre 5 Gbps + 350 Go 5G",70,350,"https://signup.free.fr/subscribe_promo/#new","DEMO-FREE"),
        ("Télécom","Pack Box + Mobile","Orange","Livebox + Forfait 150 Go",54.99,0,0,"Fibre 2 Gbps + 150 Go 5G",75,150,"https://boutique.orange.fr","DEMO-ORANGE"),
        # ---- TÉLÉCOM : Multi-lignes ----
        ("Télécom","Multi-lignes","Free","2 lignes Free 350 Go",35.98,0,0,"2 forfaits 350 Go (-10% 2e ligne)",50,350,"https://mobile.free.fr","DEMO-FREE"),
        ("Télécom","Multi-lignes","Bouygues","Pack famille 4 lignes",49.99,0,0,"4 forfaits 100 Go - réduction famille",70,100,"https://www.byou.fr","DEMO-BOUYGUES"),
        # ---- ÉNERGIE (data_go non applicable) ----
        ("Énergie","Électricité","TotalEnergies","Offre Verte Fixe Élec",89.00,0,12,"Prix kWh bloqué 1 an - 100% renouvelable",40,0,"https://www.totalenergies.fr","DEMO-TOTALENERGIES"),
        ("Énergie","Électricité","Ekwateur","Élec 100% renouvelable",92.00,0,0,"Sans engagement - électricité verte",35,0,"https://www.ekwateur.fr","DEMO-EKWATEUR"),
        ("Énergie","Électricité","Engie","Élec Référence",95.00,0,12,"Prix indexé - service client FR",38,0,"https://particuliers.engie.fr","DEMO-ENGIE"),
        ("Énergie","Électricité","EDF","Tarif Bleu",99.00,0,0,"Tarif réglementé - sans engagement",25,0,"https://particulier.edf.fr","DEMO-EDF"),
        ("Énergie","Gaz","TotalEnergies","Gaz Fixe",78.00,0,12,"Prix bloqué 1 an",35,0,"https://www.totalenergies.fr","DEMO-TOTALENERGIES"),
        ("Énergie","Gaz","Eni","Astucio Gaz",82.00,0,12,"Prix fixe - compensation carbone",33,0,"https://www.eni.com/fr-fr","DEMO-ENI"),
        ("Énergie","Gaz","Engie","Gaz Référence",85.00,0,0,"Indexé - sans engagement",30,0,"https://particuliers.engie.fr","DEMO-ENGIE"),
        # ---- ABONNEMENTS (data_go non applicable) ----
        ("Abonnements","Streaming Vidéo","Netflix","Netflix Standard avec pub",5.99,0,0,"1080p - 2 écrans",0,0,"https://www.netflix.com/fr","DEMO-NETFLIX"),
        ("Abonnements","Streaming Vidéo","Disney+","Disney+ Standard pub",5.99,0,0,"1080p",0,0,"https://www.disneyplus.com/fr-fr","DEMO-DISNEYPLUS"),
        ("Abonnements","Streaming Vidéo","Prime Video","Amazon Prime Video",6.99,0,0,"Inclus dans Prime",0,0,"https://www.primevideo.com","DEMO-PRIMEVIDEO"),
        ("Abonnements","Musique","Spotify","Spotify Premium",11.12,0,0,"Sans pub - hors ligne",0,0,"https://www.spotify.com/fr","DEMO-SPOTIFY"),
        ("Abonnements","Musique","Deezer","Deezer Premium",11.99,0,0,"Sans pub - HiFi option",0,0,"https://www.deezer.com/fr","DEMO-DEEZER"),
        ("Abonnements","Salle de sport","Basic-Fit","Abonnement Confort",29.99,30,12,"Accès illimité tous clubs",0,0,"https://www.basic-fit.com/fr-fr","DEMO-BASICFIT"),
        ("Abonnements","SaaS / Logiciel","Microsoft","Microsoft 365 Famille",10.00,0,0,"Office + 1 To OneDrive - 6 pers.",0,0,"https://www.microsoft.com/fr-fr/microsoft-365","DEMO-MICROSOFT"),
    ]
    for u, cat, fourn, nom, prix, frais, eng, carac, comm, dgo, url, code in demo:
        ajouter_offre({"univers": u, "categorie": cat, "fournisseur": fourn, "nom_offre": nom,
                       "prix_mensuel": prix, "frais_activation": frais, "engagement_mois": eng,
                       "caracteristiques": carac, "commission_affiliation": comm, "data_go": dgo,
                       "url_souscription": url, "code_affiliation": code})


# ------------------------------------------------------------------------------
#  MOTEUR DE COMPARAISON & RECOMMANDATIONS
# ------------------------------------------------------------------------------
@st.cache_data(ttl=300)
def comparer_offres(univers, categorie, cout_actuel_mensuel, fournisseurs_autorises=None,
                     fournisseur_exclu=None, data_go_min=None):
    """data_go_min : si fourni, exclut les offres mobiles dont le quota data est inférieur à la
    consommation actuelle du client (renseignée à l'étape 3). Sans effet sur les offres dont le
    quota est 0 en catalogue (Box/Fibre, Énergie, Abonnements — data non applicable)."""
    df = lire_offres(univers=univers, categorie=categorie)
    if df.empty:
        return []
    resultats = []
    for _, o in df.iterrows():
        if fournisseurs_autorises and o["fournisseur"] not in fournisseurs_autorises:
            continue
        if fournisseur_exclu and o["fournisseur"] == fournisseur_exclu:
            continue
        data_go_offre = float(o.get("data_go", 0) or 0)
        if data_go_min and data_go_offre and data_go_offre < data_go_min:
            continue
        prix     = float(o["prix_mensuel"] or 0)
        frais    = float(o["frais_activation"] or 0)
        eco_mens = round(cout_actuel_mensuel - prix, 2)
        resultats.append({
            "id": int(o["id"]), "nom": o["nom_offre"], "fournisseur": o["fournisseur"],
            "categorie": categorie, "univers": univers,
            "prix_mensuel": prix, "frais_activation": frais,
            "engagement": int(o["engagement_mois"] or 0),
            "caracteristiques": o["caracteristiques"] or "",
            "commission": float(o["commission_affiliation"] or 0),
            "data_go": data_go_offre,
            "economie_mensuelle": eco_mens, "economie_annuelle": round(eco_mens * 12, 2),
            "cout_1_an": round(prix * 12 + frais, 2),
            "url_souscription": o.get("url_souscription") or "",
            "code_affiliation": o.get("code_affiliation") or "",
        })
    resultats.sort(key=lambda x: x["economie_annuelle"], reverse=True)
    return resultats


def construire_recommandations(service_principal, cout_tel, fournisseurs_autorises=None,
                                fournisseur_exclu=None, data_go_min=None):
    f   = fournisseurs_autorises
    top = lambda cat: comparer_offres("Télécom", cat, cout_tel, f, fournisseur_exclu, data_go_min)[:3]

    if service_principal == "Mobile uniquement":
        principal = ("📱 Vos meilleures offres Mobile", top("Mobile"))
        cross     = [("🏠 Et si vous regardiez aussi la Box / Fibre ?", top("Box / Fibre")),
                     ("📦 Nos packs Box + Mobile (pour aller plus loin)", top("Pack Box + Mobile"))]
    elif service_principal == "Box / Fibre uniquement":
        principal = ("🏠 Vos meilleures offres Box / Fibre", top("Box / Fibre"))
        cross     = [("📦 Top 3 de nos packs Box + Mobile", top("Pack Box + Mobile")),
                     ("📱 Nos 3 meilleurs forfaits Mobile", top("Mobile"))]
    elif service_principal == "Pack Box + Mobile":
        # Un pack combine box + mobile : le comparer à une offre Mobile seule ou Box seule
        # n'a pas de sens (le client perdrait l'autre service). On ne compare donc les packs
        # qu'entre eux, sans cross-sell vers du Mobile ou du Box / Fibre isolé.
        principal = ("📦 Vos meilleurs packs Box + Mobile", top("Pack Box + Mobile"))
        cross     = []
    else:
        ml        = top("Multi-lignes") or top("Mobile")
        principal = ("📲 Vos meilleures offres Multi-lignes", ml)
        cross     = [("📦 Top 3 de nos packs Box + Mobile", top("Pack Box + Mobile")),
                     ("🏠 Nos 3 meilleures offres Box / Fibre", top("Box / Fibre"))]

    return {"principal": principal, "cross_sell": cross}
