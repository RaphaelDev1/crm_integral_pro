# Registre des traitements — RGPD (Art. 30)

> **⚠️ Statut : brouillon à valider.** Ce registre est un point de départ minimaliste,
> pas un document juridique final. Les champs entre crochets `[À COMPLÉTER : ...]`
> doivent être remplis avec les informations réelles de l'entreprise avant toute
> utilisation opposable. Une relecture par un juriste/DPO est recommandée avant le
> lancement des premières campagnes publicitaires (Meta/TikTok/Google Ads).
>
> Rappel réglementaire (voir roadmap V3, P5.3) : depuis le RGPD, il n'y a plus
> d'obligation de *déclaration* préalable à la CNIL, mais l'obligation de **tenir**
> un registre des traitements demeure pour toute structure de plus de 250 salariés,
> ou dès lors qu'un traitement présente un risque (données sensibles, mineurs,
> profilage à grande échelle). Les traitements ci-dessous (contact commercial,
> données financières déclaratives) ne sont pas considérés comme sensibles, mais
> un registre minimaliste reste une bonne pratique de conformité et sert de preuve
> en cas de contrôle.

## 1. Responsable de traitement

| Champ | Valeur |
|---|---|
| Raison sociale | [À COMPLÉTER : ex. IA Conseil SAS] |
| SIRET | [À COMPLÉTER] |
| Adresse | [À COMPLÉTER] |
| Représentant légal | [À COMPLÉTER] |
| Contact DPO / RGPD | [À COMPLÉTER : email dédié, ex. dpo@iaconseil.fr] |

## 2. Traitement n°1 — Capture de leads (landing publique `/economiser`)

| Champ | Détail |
|---|---|
| Finalité | Estimation d'économies personnalisée et prise de contact commerciale par un conseiller. |
| Base légale | Consentement explicite (case à cocher obligatoire, voir `consentement_rgpd`) ; consentement distinct pour le démarchage téléphonique (`consentement_demarchage`). |
| Catégories de données | Identité (prénom), contact (téléphone, email optionnel), adresse (facultative), dépenses déclarées (mobile, box, énergie, assurances), âge, données techniques (IP, user-agent, UTM de la campagne publicitaire). |
| Personnes concernées | Visiteurs de la landing publique ayant rempli le formulaire d'estimation. |
| Destinataires internes | Conseillers commerciaux (accès via `frontend-conseiller`, authentifié). |
| Sous-traitants | Hébergeur base de données (Neon/Postgres), hébergeur applicatif, prestataire d'envoi SMS (OVH ou Twilio), prestataire d'envoi email (Resend). [À COMPLÉTER : lister les sous-traitants réels et vérifier l'existence d'un DPA (Data Processing Agreement) avec chacun.] |
| Transferts hors UE | [À COMPLÉTER : vérifier la localisation des sous-traitants ci-dessus — Twilio/Resend peuvent traiter des données hors UE, nécessitant des clauses contractuelles types (SCC).] |
| Durée de conservation | 3 ans maximum après le dernier contact, sauf conversion en client (durée alignée sur la relation contractuelle + obligations légales comptables). |
| Mesures de sécurité | Authentification JWT sur l'accès conseiller, rate limiting + captcha (Turnstile) sur le formulaire public, chiffrement en transit (HTTPS). |
| Table(s) technique(s) | `prospects`, `touchpoints` (backend/models/prospect.py, backend/models/touchpoint.py). |

## 3. Traitement n°2 — Suivi client et gestion des dossiers de souscription

| Champ | Détail |
|---|---|
| Finalité | Gestion de la relation client, suivi des dossiers de changement d'offre, facturation, mandat de représentation. |
| Base légale | Exécution du contrat (mandat signé) / intérêt légitime pour le suivi commercial. |
| Catégories de données | Identité, contact, données contractuelles (opérateurs, contrats, factures), documents transmis (facture, test de débit), signature électronique (Yousign). |
| Personnes concernées | Clients ayant signé un mandat. |
| Sous-traitants | Yousign (signature électronique), AR24 (lettre recommandée électronique), hébergeur de stockage de documents (S3). [À COMPLÉTER : vérifier les DPA.] |
| Durée de conservation | Durée de la relation contractuelle + délais légaux de prescription applicables (généralement 5 ans après la fin de la relation). [À COMPLÉTER : faire valider par un juriste.] |
| Mesures de sécurité | Accès restreint par conseiller assigné, stockage de documents chiffré, journalisation des actions (`historique_actions`). |

## 4. Traitement n°3 — Cookies et mesure d'audience publicitaire

| Champ | Détail |
|---|---|
| Finalité | Mesure de performance publicitaire (Meta Ads, TikTok Ads, Google Analytics) et retargeting. |
| Base légale | Consentement (bannière cookies, voir P5.2 — `frontend-portail/lib/consent.ts`). |
| Catégories de données | Identifiants publicitaires (cookies tiers Meta/TikTok/GA4), UTM de campagne, pages visitées. |
| Personnes concernées | Visiteurs de la landing publique. |
| Destinataires | Meta (Facebook/Instagram), TikTok, Google — en tant que responsables de traitement conjoints pour leurs pixels respectifs. |
| Transferts hors UE | Oui (Meta, TikTok, Google) — encadrés par les clauses contractuelles types de chaque plateforme. |
| Durée de conservation | Selon la politique de chaque plateforme tierce ; côté first-party, l'historique d'attribution (`touchpoints`) suit la durée du traitement n°1. |
| Opt-out | Bannière de consentement avec refus aussi simple que l'acceptation (voir `/politique-confidentialite`). |

## 5. Droits des personnes concernées

Toute personne peut exercer ses droits d'accès, de rectification, d'effacement, de
limitation, d'opposition et de portabilité en écrivant à [À COMPLÉTER : email DPO].
Le désabonnement des emails marketing peut également se faire en un clic depuis le
lien présent en pied de chaque email de nurturing (voir
`backend/routers/leads_public.py::desabonner_lead`).

## 6. Prochaines étapes avant le lancement des campagnes publicitaires

1. Compléter tous les champs `[À COMPLÉTER]` ci-dessus avec les informations réelles.
2. Faire vérifier ce registre par un juriste ou un DPO externe (obligation de moyens,
   pas de forme imposée par la CNIL pour une structure de cette taille).
3. Vérifier l'existence d'un DPA avec chaque sous-traitant listé.
4. Publier les pages légales correspondantes (`/politique-confidentialite`,
   `/mentions-legales`) — voir P5.1.
5. Activer la bannière de consentement cookies avant tout pixel Meta/TikTok/GA4 — voir P5.2.
