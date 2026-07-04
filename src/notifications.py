# ==============================================================================
#  NOTIFICATIONS DE RELANCES — script autonome (cron / tâche planifiée)
#
#  Chaque matin, envoie par email et/ou Telegram la liste des relances du jour
#  + celles en retard (prospects et clients). Ne dépend pas de Streamlit :
#  tourne comme un process séparé, indépendant de l'application.
#
#  Configuration : menu 🛠️ Admin > 📧 Email dans l'application (persistée en
#  base — table `parametres`), donc partagée entre l'app et ce script.
#
#  Utilisation :
#     python notifications.py                  # relances du jour + retard
#     python notifications.py --resume-hebdo   # + résumé hebdo (à lancer le lundi)
#
#  Planification Windows (Terminal) :
#     schtasks /create /tn "IA Conseil - Relances" /sc daily /st 08:00 ^
#       /tr "python C:\chemin\vers\src\notifications.py"
#
#  Planification cron (Linux/macOS) :
#     0 8 * * *   cd /chemin/vers/src && python notifications.py
#     0 8 * * 1   cd /chemin/vers/src && python notifications.py --resume-hebdo
# ==============================================================================
import argparse
import smtplib
import urllib.parse
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from contrats_engine import lire_contrats_echeance
from db import get_conn, lire_parametre
from email_engine import construire_corps_email_fin_engagement
from offres_engine import comparer_offres
from utils import parser_date_relance, safe_float

JOURS_AVANT_ALERTE_ENGAGEMENT = 60   # ≈ 2 mois, cf. suivi post-souscription


def _lire_smtp_config() -> dict:
    return {
        "serveur":      lire_parametre("smtp_serveur"),
        "port":         int(safe_float(lire_parametre("smtp_port", "587"), 587)),
        "user":         lire_parametre("smtp_user"),
        "mdp":          lire_parametre("smtp_mdp"),
        "expediteur":   lire_parametre("smtp_expediteur"),
        "destinataire": lire_parametre("notif_email_destinataire"),
    }


def _envoyer_email_texte(destinataire: str, sujet: str, corps_texte: str) -> bool:
    cfg = _lire_smtp_config()
    if not (cfg["serveur"] and cfg["user"] and cfg["mdp"] and destinataire):
        print("Configuration SMTP ou destinataire manquant (Admin > Email) — email non envoyé.")
        return False
    msg = MIMEText(corps_texte, "plain", "utf-8")
    msg["From"], msg["To"], msg["Subject"] = cfg["expediteur"] or cfg["user"], destinataire, sujet
    try:
        with smtplib.SMTP(cfg["serveur"], cfg["port"], timeout=15) as s:
            s.starttls()
            s.login(cfg["user"], cfg["mdp"])
            s.send_message(msg)
        print(f"Email envoyé à {destinataire}.")
        return True
    except Exception as e:
        print(f"Échec de l'envoi email : {e}")
        return False


def _envoyer_email_html(destinataire: str, sujet: str, corps_html: str) -> bool:
    cfg = _lire_smtp_config()
    if not (cfg["serveur"] and cfg["user"] and cfg["mdp"] and destinataire):
        print("Configuration SMTP ou destinataire manquant (Admin > Email) — email non envoyé.")
        return False
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = cfg["expediteur"] or cfg["user"], destinataire, sujet
    msg.attach(MIMEText(corps_html, "html", "utf-8"))
    try:
        with smtplib.SMTP(cfg["serveur"], cfg["port"], timeout=15) as s:
            s.starttls()
            s.login(cfg["user"], cfg["mdp"])
            s.send_message(msg)
        print(f"Email envoyé à {destinataire}.")
        return True
    except Exception as e:
        print(f"Échec de l'envoi email : {e}")
        return False


def _envoyer_telegram(texte: str) -> bool:
    token   = lire_parametre("telegram_bot_token")
    chat_id = lire_parametre("telegram_chat_id")
    if not (token and chat_id):
        return False
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": texte}).encode("utf-8")
    try:
        urllib.request.urlopen(url, data=data, timeout=15)
        print("Message Telegram envoyé.")
        return True
    except Exception as e:
        print(f"Échec de l'envoi Telegram : {e}")
        return False


def _jours_retard(date_relance_str) -> int | None:
    d = parser_date_relance(date_relance_str)
    if d is None:
        return None
    return (datetime.now().date() - d).days


def relances_du_jour() -> list[dict]:
    """Prospects (statut 'À relancer'/'Relancé') et clients (statut_relance idem) dont
    la date de relance est aujourd'hui ou dépassée — même filtre que le tableau de bord."""
    conn = get_conn()
    prospects = conn.execute(
        "SELECT id, prenom, nom, telephone, economie_estimee_an, date_relance FROM prospects "
        "WHERE statut IN ('À relancer', 'Relancé') AND date_relance IS NOT NULL AND date_relance != ''"
    ).fetchall()
    clients = conn.execute(
        "SELECT id, prenom, nom, telephone, economie_estimee_an, date_relance FROM clients "
        "WHERE statut_relance IN ('À relancer', 'Relancé') AND date_relance IS NOT NULL AND date_relance != ''"
    ).fetchall()
    conn.close()

    def _filtrer(rows, type_entite):
        out = []
        for r in rows:
            retard = _jours_retard(r["date_relance"])
            if retard is not None and retard >= 0:
                out.append({
                    "type": type_entite, "id": r["id"],
                    "nom": f"{r['prenom']} {r['nom']}".strip(),
                    "telephone": r["telephone"] or "",
                    "economie": safe_float(r["economie_estimee_an"]),
                    "retard_jours": retard,
                })
        return out

    relances = _filtrer(prospects, "Prospect") + _filtrer(clients, "Client")
    return sorted(relances, key=lambda x: -x["retard_jours"])


def construire_message(relances: list[dict]) -> str:
    if not relances:
        return "Aucune relance en attente aujourd'hui. Bonne journée !"
    lignes = [f"{len(relances)} relance(s) à traiter aujourd'hui :", ""]
    for r in relances:
        quand = f"en retard de {r['retard_jours']} j" if r["retard_jours"] > 0 else "aujourd'hui"
        lignes.append(
            f"- [{r['type']}] {r['nom']} — {r['telephone']} — "
            f"économie estimée {r['economie']:.0f} €/an ({quand})"
        )
    return "\n".join(lignes)


def resume_hebdo() -> str:
    conn = get_conn()
    nb_prospects = conn.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
    nb_clients   = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    eco_totale   = conn.execute(
        "SELECT COALESCE(SUM(economie_estimee_an), 0) FROM clients").fetchone()[0]
    conn.close()
    return (
        "\n\nRésumé hebdomadaire :\n"
        f"- Prospects en base : {nb_prospects}\n"
        f"- Clients en base : {nb_clients}\n"
        f"- Économies totales estimées (clients) : {round(safe_float(eco_totale), 2)} €/an"
    )


def contrats_a_alerter(jours_avant: int = JOURS_AVANT_ALERTE_ENGAGEMENT):
    """Contrats dont la fin d'engagement tombe exactement dans `jours_avant` jours —
    déclenche l'alerte une seule fois (le jour où le compte à rebours atteint ce seuil)."""
    df = lire_contrats_echeance(jours_avant)
    if df.empty:
        return df
    return df[df["jours_restants"] == jours_avant]


def alerter_fin_engagement(jours_avant: int = JOURS_AVANT_ALERTE_ENGAGEMENT) -> list[dict]:
    """Envoie, pour chaque contrat atteignant le seuil d'alerte, un email au client
    (avec proposition d'offre alternative si une économie existe) et consigne l'action
    dans l'audit trail. Renvoie la liste des contrats traités (pour le message conseiller)."""
    from db import enregistrer_action

    traites = []
    for _, row in contrats_a_alerter(jours_avant).iterrows():
        alternatives = comparer_offres(row["univers"], row["categorie"],
                                        safe_float(row["cout_mensuel"]),
                                        fournisseur_exclu=row["fournisseur"])
        meilleure = alternatives[0] if alternatives and alternatives[0]["economie_annuelle"] > 0 else None
        corps = construire_corps_email_fin_engagement(
            row["client_prenom"], row["date_fin_engagement"], meilleure)
        envoye = False
        if row.get("client_email"):
            envoye = _envoyer_email_html(row["client_email"], "Votre engagement arrive à échéance", corps)
        enregistrer_action("client", int(row["client_id"]), "Alerte fin d'engagement",
                            f"Contrat {row['nom_offre']} (#{int(row['id'])}) — fin le "
                            f"{row['date_fin_engagement']} — email client "
                            f"{'envoyé' if envoye else 'non envoyé'}")
        traites.append({
            "nom": f"{row['client_prenom']} {row['client_nom']}".strip(),
            "fournisseur": row["fournisseur"], "nom_offre": row["nom_offre"],
            "date_fin_engagement": row["date_fin_engagement"], "email_envoye": envoye,
        })
    return traites


def notifier_nouveau_prospect_chatbot(prospect_id: int, infos_client: dict, total_eco: float) -> bool:
    """Alerte immédiate (email + Telegram, mêmes canaux que le digest quotidien, configurés
    dans Admin > Email) quand le chatbot public crée un prospect pré-qualifié. Appelée en
    import direct depuis chatbot_engine.py (pas seulement via le script cron `main()`)."""
    nom_complet = f"{infos_client.get('prenom', '')} {infos_client.get('nom', '')}".strip() or "Prospect"
    contact = infos_client.get("telephone") or infos_client.get("email") or "coordonnées non fournies"
    univers = infos_client.get("univers_interesse", "")
    texte = (
        f"🤖 Nouveau prospect via le chatbot — {nom_complet}\n"
        f"Contact : {contact}\n"
        f"Univers : {univers}\n"
        f"Économie estimée : {total_eco:.0f} €/an\n"
        f"Fiche prospect #{prospect_id} — à rappeler."
    )
    cfg = _lire_smtp_config()
    envoye = False
    if cfg["destinataire"]:
        envoye = _envoyer_email_texte(
            cfg["destinataire"], f"Nouveau prospect chatbot — {nom_complet}", texte
        ) or envoye
    envoye = _envoyer_telegram(texte) or envoye
    if not envoye:
        print("Nouveau prospect chatbot créé, mais aucun canal de notification configuré "
              "(voir Admin > Email).")
    return envoye


def notifier_changement_prix(alertes: list[dict]) -> bool:
    """Alerte immédiate (email + Telegram, mêmes canaux que le digest quotidien)
    quand `veille_prix_engine.lancer_veille()` détecte un ou plusieurs changements
    de prix sur les sources surveillées. Appelée en import direct depuis
    veille_prix_engine.py (script autonome), pas seulement via ce module."""
    if not alertes:
        return False
    lignes = [f"📈 {len(alertes)} changement(s) de prix détecté(s) — à valider dans "
              f"Admin > Veille prix :", ""]
    for a in alertes:
        sens = "🔺" if a["nouveau_prix"] > a["ancien_prix"] else "🔻"
        lignes.append(f"- {sens} {a['fournisseur']} {a['nom_offre']} — "
                       f"{a['ancien_prix']:.2f} € → {a['nouveau_prix']:.2f} €")
    texte = "\n".join(lignes)

    cfg = _lire_smtp_config()
    envoye = False
    if cfg["destinataire"]:
        envoye = _envoyer_email_texte(
            cfg["destinataire"], f"IA Conseil — {len(alertes)} changement(s) de prix détecté(s)", texte
        ) or envoye
    envoye = _envoyer_telegram(texte) or envoye
    if not envoye:
        print("Changement(s) de prix détecté(s), mais aucun canal de notification "
              "configuré (voir Admin > Email).")
    return envoye


def construire_message_engagement(traites: list[dict]) -> str:
    if not traites:
        return ""
    lignes = [f"\n\n{len(traites)} contrat(s) arrivent à échéance dans "
              f"{JOURS_AVANT_ALERTE_ENGAGEMENT} jours (alerte client envoyée) :", ""]
    for t in traites:
        statut = "email envoyé" if t["email_envoye"] else "email NON envoyé (vérifier config SMTP/email client)"
        lignes.append(f"- {t['nom']} — {t['fournisseur']} {t['nom_offre']} — "
                       f"fin le {t['date_fin_engagement']} ({statut})")
    return "\n".join(lignes)


def main():
    parser = argparse.ArgumentParser(description="Notifications de relances IA Conseil")
    parser.add_argument("--resume-hebdo", action="store_true",
                         help="Ajoute le résumé hebdomadaire (à lancer le lundi)")
    args = parser.parse_args()

    relances = relances_du_jour()
    message  = construire_message(relances)

    contrats_traites = alerter_fin_engagement()
    message += construire_message_engagement(contrats_traites)

    if args.resume_hebdo:
        message += resume_hebdo()

    cfg = _lire_smtp_config()
    envoye = False
    if cfg["destinataire"]:
        envoye = _envoyer_email_texte(
            cfg["destinataire"], f"IA Conseil — {len(relances)} relance(s) aujourd'hui", message,
        ) or envoye
    envoye = _envoyer_telegram(message) or envoye

    if not envoye:
        print("Aucun canal de notification configuré ou envoi impossible "
              "(voir Admin > Email dans l'application).")

    print("\n--- Contenu du message ---")
    print(message)


if __name__ == "__main__":
    main()
