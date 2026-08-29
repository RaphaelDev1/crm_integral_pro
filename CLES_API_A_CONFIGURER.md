# Clés API à configurer

> État réel vérifié le 2026-08-26 en lisant `backend/.env`, `frontend-portail/.env.local` et
> `frontend-conseiller/.env.local` (fichiers gitignorés, jamais commités). Toutes les fonctionnalités
> listées ici dégradent proprement si la clé est absente (pas de crash) — cette liste sert juste à
> activer ce qui est aujourd'hui désactivé.

## Comment remplir

Chaque clé va dans un fichier `.env` / `.env.local` (jamais dans `.env.example`, qui reste un modèle
vide committé). Après modification d'un `.env`, redémarrer le service concerné (le backend ne relit
pas `.env` à chaud).

---

## 🔴 Prioritaire — nouveau tunnel de capture `/economiser` (chantiers de cette session)

| Clé | Fichier | Où l'obtenir | Effet si vide |
|---|---|---|---|
| `TURNSTILE_SECRET_KEY` | `backend/.env` | [dash.cloudflare.com](https://dash.cloudflare.com/?to=/:account/turnstile) → Turnstile → créer un site → copier la **clé secrète** (gratuit, illimité) | Captcha désactivé, formulaire soumissible sans vérification anti-bot |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | `frontend-portail/.env.local` | Même écran Cloudflare que ci-dessus → **clé de site** (publique, différente de la clé secrète) | Widget Turnstile non rendu (aucune erreur visible) |
| `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` | `backend/.env` | [console.twilio.com](https://console.twilio.com) → créer un compte (essai gratuit avec crédit offert) → Account SID + Auth Token en page d'accueil | Validation téléphone (Twilio Lookup) désactivée — `telephone_verifie` reste `null`, aucun lead n'est jamais masqué |
| `SLACK_WEBHOOK_URL` | `backend/.env` | [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks) → créer une Incoming Webhook sur le canal de ton choix (ou une URL de webhook Discord, même format) | Pas de ping temps réel à la capture d'un lead — juste le SMS et l'email J+1 |
| `FRONTEND_CONSEILLER_BASE_URL` | `backend/.env` | Aucune inscription — juste ajouter la ligne (absente du `.env` actuel) : `FRONTEND_CONSEILLER_BASE_URL=http://localhost:3001` (ou l'URL de prod une fois déployé) | Le lien "Voir la fiche prospect" dans le message Slack ci-dessus pointera vers `localhost:3001` par défaut (valeur de repli du code) |

**Ne nécessitent aucune clé** (déjà actifs) : autocomplétion d'adresse (BAN, gratuite), détection FAI
par IP (ipapi.co, gratuit), éligibilité fibre niveau commune (`ELIGIBILITE_FIBRE_API_URL`, wrapper public
gratuit déjà pré-rempli dans `.env.example`).

⚠️ Si `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN` sont déjà remplis pour l'envoi de SMS (`SMS_PROVIDER=twilio`),
**la validation téléphone (Lookup) se réactive automatiquement avec les mêmes identifiants** — pas besoin
de compte séparé.

---

## 🟠 Existant depuis les sprints précédents — jamais rempli à ce jour

| Clé | Fichier | Où l'obtenir | Effet si vide |
|---|---|---|---|
| `CRM_API_SECRET` | `backend/.env` | Générer localement : `python -c "import secrets; print(secrets.token_urlsafe(48))"` | Un secret de dev prévisible est utilisé (`dev-secret-a-changer-en-production`) — **bloquant avant toute mise en ligne réelle** (le code refuse de démarrer en `APP_ENV=production` sans cette clé) |
| `S3_BUCKET` + `S3_ACCESS_KEY_ID` + `S3_SECRET_ACCESS_KEY` | `backend/.env` | [console.scaleway.com](https://console.scaleway.com) → Object Storage → créer un bucket privé région `fr-par` → générer une clé API dédiée | Upload de documents (KYC, mandats signés) impossible |
| `YOUSIGN_API_KEY` + `YOUSIGN_WEBHOOK_SECRET` | `backend/.env` | [developers.yousign.com](https://developers.yousign.com) → compte sandbox gratuit → clé API + secret webhook (HMAC signature `X-Yousign-Signature-256`) | Signature électronique des mandats indisponible |
| `AR24_API_KEY` (+ `AR24_LOGIN`/`AR24_PASSWORD` si nécessaire) | `backend/.env` | [ar24.fr](https://www.ar24.fr) → inscription, vérifier le schéma d'auth exact (bearer vs login/mdp) contre leur doc réelle avant prod | Génération des documents de démarche OK, mais l'envoi en LRE échoue proprement (`statut="echouee"`) |
| `STRIPE_API_KEY` + `STRIPE_WEBHOOK_SECRET` | `backend/.env` | [dashboard.stripe.com](https://dashboard.stripe.com) → clés API (mode test d'abord) | Facturation/abonnements indisponibles |
| `RESEND_API_KEY` | `backend/.env` | [resend.com](https://resend.com) → API Keys (généreux plan gratuit) | Tout email transactionnel désactivé — y compris l'email J+1 landing (P3.2) |
| `OVH_APPLICATION_KEY` + `OVH_APPLICATION_SECRET` + `OVH_CONSUMER_KEY` + `OVH_SMS_SERVICE_NAME` | `backend/.env` | [api.ovh.com/createToken](https://api.ovh.com/createToken/) (si `SMS_PROVIDER=ovh`, valeur par défaut) | SMS transactionnels désactivés (confirmation lead, lien client, etc.) — sauf à basculer `SMS_PROVIDER=twilio` avec les clés Twilio déjà listées plus haut |
| `SENTRY_DSN` | `backend/.env` | [sentry.io](https://sentry.io) → créer un projet Python (backend) | Pas de remontée d'erreurs — les exceptions restent seulement dans les logs locaux |
| `NEXT_PUBLIC_SENTRY_DSN` | `frontend-portail/.env.local` + `frontend-conseiller/.env.local` | Même projet Sentry, DSN équivalent côté JS (ou projet séparé) | Idem côté frontend |

---

## 🟢 Optionnel — marketing / tracking (déjà câblés, jamais renseignés)

| Clé | Fichier | Où l'obtenir | Effet si vide |
|---|---|---|---|
| `NEXT_PUBLIC_META_PIXEL_ID` | `frontend-portail/.env.local` | [business.facebook.com/events_manager](https://business.facebook.com/events_manager) → créer un pixel | Pas de tracking Meta Ads (retargeting impossible) |
| `NEXT_PUBLIC_TIKTOK_PIXEL_ID` | `frontend-portail/.env.local` | [ads.tiktok.com](https://ads.tiktok.com) → Assets → Events → créer un pixel | Idem côté TikTok Ads |
| `NEXT_PUBLIC_GA_MEASUREMENT_ID` | `frontend-portail/.env.local` | [analytics.google.com](https://analytics.google.com) → créer une propriété GA4 | Pas de statistiques GA4 sur la landing |
| `NEXT_PUBLIC_CALCOM_LINK` | `frontend-portail/.env.local` | [cal.com](https://cal.com) → créer un event type, copier son lien (`ton-compte/nom-event`) | Bouton "Choisir un créneau maintenant" masqué à l'étape 4 |

Voir `docs/RETARGETING_META_TIKTOK.md` pour la configuration des audiences une fois les pixels posés.

---

## Aucune action requise (fonctionne déjà)

- `DATABASE_URL` (Neon Postgres) ✅ configuré et migré (`0028` appliqué).
- `ANTHROPIC_API_KEY` ✅ configuré (KYC + agent d'audit).
- `REDIS_URL`, `RATE_LIMIT_STORAGE_URI` (`memory://` en dev, suffisant tant qu'un seul process tourne).
- `ELIGIBILITE_FIBRE_API_URL` (wrapper public gratuit, valeur par défaut déjà dans `.env.example`).
- Autocomplétion d'adresse (BAN) et détection FAI (ipapi.co) : aucune clé, aucune inscription.

---

## Ordre de priorité suggéré

1. **Turnstile** (5 min, gratuit) — coupe le spam/bots dès maintenant.
2. **Twilio** (Account SID + Auth Token, essai gratuit) — active en même temps Lookup (validation
   téléphone) et, si tu veux, l'envoi SMS (`SMS_PROVIDER=twilio`), sans repasser par OVH.
3. **Slack webhook** (2 min, gratuit) — tu vois les leads arriver en temps réel sans changer d'onglet.
4. **Resend** (5 min, plan gratuit généreux) — sans ça, l'email J+1 (P3.2) ne part jamais.
5. Le reste (S3, Yousign, Stripe, AR24, Sentry) selon les chantiers sur lesquels tu avances.


docs/REGISTRE_TRAITEMENTS_CNIL.md — section 1 "Responsable de traitement" (ligne 18-26) : Raison sociale, SIRET, Adresse, Représentant légal, Contact DPO. C'est la source de vérité — remplis celui-là en premier.
frontend-portail/app/mentions-legales/page.tsx — remplace chaque [À COMPLÉTER : ...] dans la section "1. Édition du site" (raison sociale, forme juridique, capital social, SIRET, siège social, directeur de publication, contact) et la section "2. Hébergement" (nom/adresse/tél de l'hébergeur).
frontend-portail/app/politique-confidentialite/page.tsx — plusieurs [À COMPLÉTER] : date de mise à jour (ligne 31), raison sociale + email DPO (ligne 37-40), liste des sous-traitants réels (ligne 89-95), email DPO pour l'exercice des droits (ligne 111-118).