# ==============================================================================
#  EMAIL — envoi SMTP + gabarit HTML du bilan
# ==============================================================================
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

import streamlit as st


def envoyer_email(destinataire, sujet, corps_html, pdf_bytes=None, nom_pdf="bilan.pdf"):
    cfg      = st.session_state.get("smtp_config", {})
    serveur  = cfg.get("serveur", "")
    port     = int(cfg.get("port", 587))
    user     = cfg.get("user", "")
    mdp      = cfg.get("mdp", "")
    expediteur = cfg.get("expediteur", user)
    if not (serveur and user and mdp):
        return False, "Configuration SMTP incomplète (voir Admin > Paramètres email)."
    try:
        msg = MIMEMultipart()
        msg["From"], msg["To"], msg["Subject"] = expediteur, destinataire, sujet
        msg.attach(MIMEText(corps_html, "html", "utf-8"))
        if pdf_bytes:
            piece = MIMEApplication(pdf_bytes, _subtype="pdf")
            piece.add_header("Content-Disposition", "attachment", filename=nom_pdf)
            msg.attach(piece)
        with smtplib.SMTP(serveur, port, timeout=15) as s:
            s.starttls(); s.login(user, mdp); s.send_message(msg)
        return True, "Email envoyé avec succès."
    except Exception as e:
        return False, f"Échec de l'envoi : {e}"


def construire_corps_email(client, recommandations, total_eco_an):
    nom   = client.get("prenom", "")
    lignes = ""
    for r in recommandations:
        o = r.get("offre", {})
        lignes += f"""<tr>
          <td style="padding:10px;border-bottom:1px solid #eee;">
            <b>{r.get('univers','')} – {r.get('categorie','')}</b></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">
            {o.get('nom','')}<br>
            <span style="color:#888;font-size:12px;">{o.get('fournisseur','')}</span></td>
          <td style="padding:10px;border-bottom:1px solid #eee;">{o.get('prix_mensuel',0)} €/mois</td>
          <td style="padding:10px;border-bottom:1px solid #eee;color:#009650;">
            <b>+{o.get('economie_annuelle',0)} €/an</b></td>
        </tr>"""
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:660px;margin:auto;
                border:1px solid #eee;border-radius:8px;overflow:hidden;">
      <div style="background:#1a3c6e;color:#fff;padding:24px;">
        <h1 style="margin:0;font-size:22px;">Votre bilan d'économies</h1>
        <p style="margin:6px 0 0;opacity:.85;">Préparé spécialement pour vous</p>
      </div>
      <div style="padding:24px;">
        <p style="font-size:15px;">Bonjour {nom},</p>
        <p>Suite à notre échange, voici les offres que nous avons sélectionnées :</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <thead><tr style="background:#f4f7fb;text-align:left;">
            <th style="padding:10px;">Univers</th><th style="padding:10px;">Offre</th>
            <th style="padding:10px;">Tarif</th><th style="padding:10px;">Économie</th>
          </tr></thead>
          <tbody>{lignes}</tbody>
        </table>
        <div style="background:#009650;color:#fff;padding:16px;border-radius:6px;
                    text-align:center;margin-top:20px;font-size:18px;">
          <b>Économie totale estimée : {round(total_eco_an,2)} € / an</b>
        </div>
        <p style="margin-top:20px;">Le détail complet est en pièce jointe.
           Nous nous occupons de toutes les démarches de changement.</p>
        <p style="color:#aaa;font-size:11px;margin-top:24px;">
          Estimations indicatives, sans valeur contractuelle.</p>
      </div>
    </div>"""


def construire_corps_email_fin_engagement(prenom: str, date_fin: str, offre_alternative: dict = None):
    """Email de rappel de fin d'engagement — proposition de renégociation si une offre
    moins chère a été identifiée dans le catalogue (offre_alternative=None → pas de proposition)."""
    proposition = ""
    if offre_alternative:
        proposition = f"""
        <p>Nous avons identifié une offre à <b>{offre_alternative.get('prix_mensuel', 0)} €/mois</b>
           ({offre_alternative.get('nom','')} — {offre_alternative.get('fournisseur','')}) qui vous
           ferait économiser <b>{round(offre_alternative.get('economie_annuelle', 0), 2)} €/an</b>.</p>"""
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:660px;margin:auto;
                border:1px solid #eee;border-radius:8px;overflow:hidden;">
      <div style="background:#1a3c6e;color:#fff;padding:24px;">
        <h1 style="margin:0;font-size:22px;">Votre engagement arrive à échéance</h1>
        <p style="margin:6px 0 0;opacity:.85;">Préparé spécialement pour vous</p>
      </div>
      <div style="padding:24px;">
        <p style="font-size:15px;">Bonjour {prenom},</p>
        <p>Votre engagement actuel se termine le <b>{date_fin}</b>.</p>
        {proposition}
        <p style="margin-top:20px;">Contactez-nous pour faire le point avant l'échéance et éviter
           toute reconduction non souhaitée.</p>
        <p style="color:#aaa;font-size:11px;margin-top:24px;">
          Estimations indicatives, sans valeur contractuelle.</p>
      </div>
    </div>"""


def construire_corps_email_teaser(client, univers_analyses, economie_totale):
    """Variante « teaser » du bilan — économie totale visible, sans le détail des offres
    (noms/fournisseurs/prix), envoyée avant règlement des honoraires de conseil."""
    nom     = client.get("prenom", "")
    postes  = "".join(f"<li style='margin:4px 0;'>{u}</li>" for u in univers_analyses)
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:660px;margin:auto;
                border:1px solid #eee;border-radius:8px;overflow:hidden;">
      <div style="background:#1a3c6e;color:#fff;padding:24px;">
        <h1 style="margin:0;font-size:22px;">Votre étude d'économies</h1>
        <p style="margin:6px 0 0;opacity:.85;">Préparée spécialement pour vous</p>
      </div>
      <div style="padding:24px;">
        <p style="font-size:15px;">Bonjour {nom},</p>
        <p>Notre analyse de votre situation a permis d'identifier des pistes d'économies sur :</p>
        <ul style="font-size:14px;">{postes}</ul>
        <div style="background:#009650;color:#fff;padding:16px;border-radius:6px;
                    text-align:center;margin-top:20px;font-size:18px;">
          <b>Économie totale estimée : {round(economie_totale,2)} € / an</b>
        </div>
        <p style="margin-top:20px;">Le détail des offres et fournisseurs recommandés, ainsi que
           la prise en charge des démarches, vous seront communiqués après règlement de nos
           honoraires de conseil (devis joint en pièce jointe).</p>
        <p style="color:#aaa;font-size:11px;margin-top:24px;">
          Estimations indicatives, sans valeur contractuelle.</p>
      </div>
    </div>"""
