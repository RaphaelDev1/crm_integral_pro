# IA Conseil — CRM Intégral Pro
## Documentation technique complète

**Mise à jour :** 04/07/2026 — reflète l'état réel du code (`src/`), untracked compris (facturation, souscription assistée, notifications, OCR Vision, tests, CI, veille prix automatique, API REST interne JWT).

---

## 🧩 Prompt explicite — ce que propose l'application aujourd'hui

> IA Conseil est un CRM interne pour conseillers en économies Télécom / Énergie / Abonnements. Un conseiller fait passer un **diagnostic guidé en 4-5 étapes** à un prospect (import automatique de facture PDF/photo par OCR — regex ou IA Vision Claude —, et de speedtest PDF) ; l'app **compare la situation actuelle au catalogue d'offres** et calcule l'économie annuelle réalisable, univers par univers (Télécom, Énergie, Abonnements), avec une suggestion d'opérateur local basée sur la satisfaction réseau et le débit mesurés par les autres clients de la même ville. Le client obtient un **PDF/email "aperçu"** (économie totale chiffrée, sans le détail des offres) ; le détail complet (offres nommées, comparatif) ne se débloque qu'après un **devis d'honoraires signé et payé** (mandat de représentation en PDF, suivi de statut Devis envoyé → Payé → Démarches en cours → Terminé), modèle économique basé sur un pourcentage de l'économie trouvée. Une fois l'offre choisie, le conseiller peut **ouvrir le lien de souscription affilié en un clic**, ou pour Free/Bouygues **lancer un navigateur pré-rempli automatiquement** (Playwright) avec les coordonnées du client — jamais de soumission automatique, validation humaine obligatoire. Le prospect converti devient un **client avec contrats** (dont date de fin d'engagement), suivi par relances programmées (recalcul de score de priorité, historique d'audit complet), avec alerte automatique au client 60 jours avant l'échéance d'engagement. Un **script indépendant planifiable** (`notifications.py`, cron/tâche planifiée) envoie chaque matin par email et/ou Telegram la liste des relances du jour et des retards, plus un résumé hebdomadaire optionnel — sans dépendre de l'app Streamlit ouverte. Un second script planifiable (`veille_prix_engine.py`) surveille les pages tarifs des opérateurs (Playwright headless) et crée une alerte de changement de prix à valider par un admin avant répercussion au catalogue. Une **API FastAPI interne protégée par JWT** (`crm_api.py`) expose tout le CRUD (prospects/clients/contrats/offres) et le diagnostic pour de futures intégrations (mobile, portail client, webhooks) ; Streamlit l'appelle déjà via `api_client.py`, avec repli automatique et transparent sur un accès direct à la base si l'API n'est pas démarrée. L'app gère aussi les **utilisateurs et rôles** (Admin / Conseiller / Lecture), un **tableau de bord** (KPIs, relances groupées par urgence, échéances de contrats à 90 jours, performance par conseiller en vue Admin), la **recherche plein texte** (SQLite FTS5) sur prospects et clients, l'**export Excel**, et une **suite de tests automatisés** (pytest) exécutée en CI (GitHub Actions) à chaque push.

---

## 🎯 Pourquoi ce logiciel ?

Application interne pour conseillers **Télécom / Énergie / Abonnements** : diagnostic client guidé, comparaison d'offres, restitution "aperçu" puis complète après règlement d'honoraires, souscription assistée, suivi des prospects et clients jusqu'à la conversion en contrats signés — avec relances automatisées même app fermée.

---

## 🏗️ Stack technique

- **Backend / UI** : Python + Streamlit (une seule app multi-pages pilotée par un menu latéral)
- **Base de données** : SQLite en mode WAL (écritures concurrentes sécurisées), `PRAGMA foreign_keys=ON`, index **FTS5** pour la recherche plein texte
- **Auth** : PBKDF2-HMAC-SHA256 (260 000 itérations), comptage nominatif, 3 rôles
- **PDF** : lecture (PyPDF2 — factures/speedtest, texte embarqué) + lecture IA (API **Anthropic Claude Vision**, photo/scan/PDF image) + génération (fpdf2 — aperçu, restitution complète, devis, mandat)
- **Email** : SMTP (smtplib), gabarits HTML inline
- **Souscription assistée** : Playwright (navigateur visible, process détaché, pré-remplissage uniquement)
- **Notifications planifiées** : script Python autonome (cron / tâche planifiée Windows), email + Telegram
- **Veille prix** : Playwright headless (scraping planifiable) + tables `sources_veille`/`veille_historique_prix`/`veille_alertes`, validation admin avant impact catalogue
- **API REST interne** : FastAPI (`crm_api.py`), auth **JWT** (PyJWT, `jwt_auth.py`), process indépendant de Streamlit, consommée par Streamlit via `api_client.py` (repli auto sur accès direct BDD)
- **API chatbot publique** : FastAPI (`chatbot_api.py`), sans auth, dédiée au widget de site
- **Export** : Excel (openpyxl)
- **Tests** : pytest, suite dans `src/tests/`, CI GitHub Actions (`.github/workflows/tests.yml`) sur chaque push/PR

Dépendances (`src/requirements.txt`) : `streamlit`, `pandas`, `PyPDF2`, `fpdf2`, `openpyxl`, `anthropic`, `playwright`, `fastapi`, `uvicorn`, `pyjwt`, `requests`.
Dépendances dev (`src/requirements-dev.txt`) : `+ pytest`.

---

## 📁 Organisation du code (`src/`)

| Fichier | Rôle |
|---|---|
| `app.py` | Point d'entrée Streamlit : session, navigation, toutes les pages/UI |
| `db.py` | Connexion SQLite, création du schéma, migrations incrémentales, audit trail (`historique_actions`), table `parametres` (clé/valeur), index FTS5 |
| `auth.py` | Hash/vérification mot de passe, CRUD utilisateurs, création admin par défaut |
| `constants.py` | Listes déroulantes métier (opérateurs, fournisseurs énergie, univers, catégories, rôles, statuts facture…) |
| `utils.py` | Helpers génériques : validation email/tél, parsing date, export Excel, génération de référence, construction de lien affilié |
| `prospects_engine.py` | CRUD prospects + widget de relance (`widget_relance`) + scoring de priorité (`calculer_score_prospect`) + recherche FTS5 |
| `clients_engine.py` | CRUD clients + couverture réseau par ville (satisfaction et débit) + widget de relance client + recherche FTS5 |
| `contrats_engine.py` | CRUD contrats rattachés à un client + liste des contrats arrivant à échéance |
| `offres_engine.py` | Catalogue d'offres (avec lien de souscription/affiliation) + moteur de comparaison/recommandation |
| `pdf_engine.py` | Extraction facture/speedtest (PyPDF2 regex + Claude Vision) + génération PDF (aperçu, restitution complète, devis, mandat) |
| `facturation_engine.py` | CRUD devis d'honoraires, cycle de statut, signature du mandat, rattachement au client à la conversion |
| `souscription_engine.py` | Pré-remplissage assisté (Playwright) du formulaire de souscription en ligne (Free/Bouygues), sans jamais soumettre |
| `email_engine.py` | Envoi SMTP + gabarits HTML (bilan, alerte fin d'engagement) |
| `notifications.py` | Script autonome planifiable : digest quotidien des relances (email/Telegram) + alerte fin d'engagement + résumé hebdo + notification immédiate de nouveau prospect chatbot |
| `chatbot_engine.py` | Chatbot public : boucle agentique Claude (tool-use) qui collecte progressivement les infos du diagnostic et crée le prospect en fin de conversation |
| `chatbot_api.py` | API FastAPI **publique, sans auth** (process indépendant de Streamlit) exposant le chatbot et les endpoints prospects/offres/bilan au widget JS |
| `static/chatbot_widget.js` | Widget de chat embarquable sur n'importe quel site (aucune dépendance, à charger via `<script src=".../widget/chatbot_widget.js" data-api-url="...">`) |
| `crm_api.py` | API FastAPI **interne, protégée par JWT** (process indépendant de Streamlit) : CRUD complet prospects/clients/contrats/offres + endpoints diagnostic ; doc Swagger sur `/docs` |
| `jwt_auth.py` | Émission/validation des JWT (`creer_token`, `get_current_user`, `require_role`) — secret lu dans `CRM_API_SECRET` |
| `api_client.py` | Utilisé par `app.py` à la place des modules `*_engine.py` : mêmes signatures, appelle `crm_api.py` en HTTP et retombe automatiquement sur l'accès direct à la base si l'API est injoignable |
| `veille_prix_engine.py` | Script planifiable : scrape (Playwright headless) les pages tarifs opérateurs, détecte les changements de prix, crée des alertes `en_attente` validées/rejetées par un admin |
| `tests/` | Suite pytest (auth, offres, utils, pdf, prospects, souscription, chatbot) + `conftest.py` |
| `pytest.ini` | Configuration pytest |
| `ia_conseil_crm.db` | Base SQLite (créée/migrée automatiquement au premier lancement) |

---

## 🗄️ Base de données

```
utilisateurs        id, username, nom_complet, password_hash, role, actif, date_creation
prospects           id, ref, identité, ville/CP, univers_interesse, situation actuelle
                     (opérateur, techno, data, coût, satisfaction, débits ⬇️⬆️),
                     énergie (fournisseur, coûts), abonnements (JSON), lignes_multi (JSON),
                     economie_estimee_an, notes, statut, date_creation, date_relance,
                     cree_par, offres_interet (JSON — offres cochées "intéresse le client"),
                     score (priorité de relance, recalculée à chaque affichage)
clients              mêmes champs de situation que prospects, + date_relance, statut_relance
                     ("Aucune" / "À relancer" / "Relancé")
contrats             id, client_id (FK), univers, categorie, fournisseur, nom_offre,
                     cout_mensuel, economie_mensuelle, reference_contrat, statut_contrat,
                     date_souscription, date_fin_engagement, notes, cree_par
offres               catalogue : id, univers, categorie, fournisseur, nom_offre, prix_mensuel,
                     frais_activation, engagement_mois, data_go, caracteristiques,
                     commission_affiliation, url_souscription, code_affiliation, actif, date_maj
factures             devis d'honoraires : id, reference, prospect_id, client_id, identité,
                     economie_annuelle, taux_honoraires, montant_honoraires, statut
                     (Devis envoyé → Payé → Démarches en cours → Terminé), date_creation,
                     date_paiement, mandat_signe, mandat_signataire, mandat_date_signature,
                     notes, cree_par
parametres           clé/valeur générique : config SMTP, nom société, taux d'honoraires par
                     défaut, clé API Anthropic, destinataire notifications, jeton/chat Telegram
historique_actions   audit trail insert-only : entite_type, entite_id, action, details,
                     auteur, date_action
sources_veille       page tarif surveillée : id, univers, categorie, fournisseur, nom_offre,
                     offre_id (FK offres, nullable), url, selecteur_prix, actif, dernier_prix,
                     date_derniere_verif, date_creation
veille_historique_prix  relevé de prix insert-only : id, source_id (FK), prix, date_releve
veille_alertes       changement de prix détecté : id, source_id (FK), ancien_prix, nouveau_prix,
                     statut (en_attente / validee / rejetee), date_detection, date_traitement
```

Index **FTS5** (`prospects`, `clients`) synchronisé automatiquement pour la recherche plein texte (nom, ville, email, opérateur…).

Les migrations (`db._migrer_bdd`) ajoutent automatiquement les colonnes/tables manquantes à chaque démarrage — aucune action manuelle requise en cas de mise à jour du code.

---

## 🔐 Rôles & permissions

| Rôle | Voir | Modifier | Admin |
|---|---|---|---|
| Admin | ✅ | ✅ | ✅ |
| Conseiller | ✅ | ✅ | ❌ |
| Lecture | ✅ | ❌ | ❌ |

Chaque création/modification est tracée (`cree_par` + `historique_actions`). Un conseiller ne voit par défaut que ses propres prospects/clients ; l'Admin peut activer une « vue globale ».

---

## 🚀 Étapes une à une — du lancement à la conversion

### 1. Lancer l'application
```bash
cd src
pip install -r requirements.txt
streamlit run app.py
```
Au tout premier lancement, un compte admin est créé automatiquement : `admin` / `Admin2026!` (à changer immédiatement dans **Admin > Utilisateurs**).

### 2. Se connecter
Panneau latéral gauche → identifiant + mot de passe → **Se connecter**. La sidebar affiche ensuite le menu de navigation (📊 Tableau de bord, 🧭 Nouveau diagnostic, 📇 Prospects, 👥 Clients & contrats, 🧾 Facturation, 🛠️ Admin) et 3 compteurs personnels (mes prospects, à relancer, mes clients).

### 3. Démarrer un diagnostic (menu « 🧭 Nouveau diagnostic »)
Wizard en 4 à 5 étapes :

1. **Besoins + import** : cocher les univers à analyser (Télécom / Énergie / Abonnements), choisir le service télécom recherché, importer en option une facture (PDF, photo ou scan — analysée par IA Vision Claude si une clé API est configurée, sinon extraction PyPDF2 classique par regex, PDF texte uniquement) et/ou un speedtest PDF (pré-remplit les débits).
2. **Coordonnées client** : type (Particulier/Pro), identité, téléphone, email, ville/CP — validation format email/téléphone en temps réel.
3. **Situation actuelle** :
   - *Télécom* : opérateur, technologie, offre/coût actuels, débits mesurés, satisfaction réseau, lignes multi. Si le client n'est pas pleinement satisfait et que la ville est renseignée, deux encarts informatifs apparaissent : le meilleur opérateur local par **satisfaction** déclarée, et le meilleur opérateur local par **débit mesuré** (⬇️/⬆️ Mbps moyens chez les prospects/clients de la même ville).
   - *Énergie* : fournisseur actuel, coûts élec/gaz.
   - *Abonnements* : ajout libre d'abonnements existants (nom + coût).
4. **Recommandations** : le moteur compare aux offres du catalogue et affiche, par univers, l'offre la mieux classée (toujours incluse) + les alternatives, avec économie annuelle. Chaque offre proposée (Télécom, Énergie, Abonnements) peut être cochée **⭐ Intéresse le client** — ces offres sont reprises dans la fiche prospect et débloqueront la restitution complète après paiement. Pour chaque offre avec lien de souscription, un bouton **🔗 Souscrire** ouvre le lien affilié (avec code d'affiliation + coordonnées client en paramètres), et l'action est tracée. En bas de page — **restitution "aperçu"** (l'économie totale, sans le détail des offres ; le détail se débloque via un devis d'honoraires, menu 🧾 Facturation) :
   - 📄 Télécharger le PDF (aperçu)
   - 📧 Envoyer au client (nécessite un SMTP configuré et un email client)
   - 📇 Enregistrer prospect
   - ✅ Convertir en client (directement, sans passer par prospect)
5. **Confirmation conversion** (si étape 4 → « Convertir en client ») : cocher/ajuster les offres réellement souscrites → création du client + des contrats correspondants.

### 4. Suivre les prospects (menu « 📇 Prospects »)
- Liste filtrable par statut, **recherche plein texte** (FTS5 — nom, ville, email, opérateur…), export Excel.
- Fiche détaillée : coordonnées, situation, offres qui l'intéressaient (avec bouton **🔗 Souscrire**, et pour Free/Bouygues un bouton de **pré-remplissage automatique** qui ouvre un navigateur avec le formulaire de souscription rempli — validation manuelle obligatoire, rien n'est jamais soumis automatiquement), historique.
- Tri optionnel par **🔥 score de priorité** (activé par défaut), avec colonnes `priorité`/`score` dans le tableau.
- **Modifier** le prospect (champs clés en un clic « 💾 Enregistrer »).
- **Convertir en client** : ouvre un écran de sélection des offres cochées « intéresse le client » (case à cocher + prix/économie éditables par offre) avant de créer le client et ses contrats — le prospect est alors supprimé et l'action tracée dans l'historique ; les devis d'honoraires existants du prospect sont rattachés au nouveau client.
- **Relance** : bouton principal « ✅ Relance effectuée » qui reprogramme automatiquement à +7 jours ; option repliée « 📅 Date précise » pour les cas avec engagement en cours. Un prospect nouvellement créé est toujours positionné sur « aujourd'hui » (relance = jour-J).
- Suppression (avec confirmation).

### 5. Suivre le tableau de bord (menu « 📊 Tableau de bord »)
- KPIs : prospects total, à relancer, clients signés, économies générées.
- **Relances prospects à traiter** : groupées Retard / Aujourd'hui / À venir / Sans date, triées par **score de priorité** décroissant dans chaque groupe (🔴 chaud / 🟡 tiède / 🟢 froid), avec action rapide (relancer, convertir, supprimer) sur un prospect sélectionné.
- **Relances clients à traiter** : même logique de groupement, cadence par défaut à +1 mois (le temps d'appeler et faire le point) — un client n'entre dans ce suivi que lorsqu'une relance a été programmée manuellement sur sa fiche.
- **Contrats arrivant à échéance (90 jours)** : liste des contrats dont la date de fin d'engagement tombe dans les 90 prochains jours, triés par urgence, avec envoi manuel de l'email de rappel au client (proposition d'offre alternative si une économie a été identifiée dans le catalogue). Une alerte est aussi envoyée **automatiquement** 60 jours avant l'échéance par le script `notifications.py`.
- Derniers clients enregistrés.
- Vue Admin : bascule « vue globale » (toute l'équipe) + tableau de performance par conseiller.

### 6. Gérer les clients & contrats (menu « 👥 Clients & contrats »)
- Recherche plein texte (FTS5 : nom, ville, email, réf., opérateur…), export Excel.
- Fiche client : coordonnées, situation, statut de relance courant + bouton pour programmer/reprogrammer une relance (par défaut +1 mois, option date précise).
- Modification des informations, liste des contrats (total mensuel / économie mensuelle), ajout/modification/suppression de contrat — dont une **date de fin d'engagement** optionnelle qui alimente le suivi d'échéance (Tableau de bord) et l'alerte automatique. Pour un contrat Free/Bouygues, un bouton de **pré-remplissage automatique** du formulaire de souscription est disponible.
- Suppression du client (supprime aussi ses contrats — confirmation requise).
- Historique complet des actions sur la fiche.

### 7. Facturation (menu « 🧾 Facturation ») — devis d'honoraires & mandat
Le business model : l'économie totale est annoncée gratuitement (PDF/email "aperçu"), mais le **détail des offres** ne se débloque qu'après ce parcours.

- **Créer un devis** : sélection d'un prospect, économie annuelle (pré-remplie), taux d'honoraires (% de l'économie, valeur par défaut réglable en Admin) → montant calculé automatiquement, devis créé (référence `FAC-...`, statut initial « Devis envoyé »).
- **Fiche devis** : téléchargement du **PDF devis** et du **PDF mandat de représentation**, cycle de statut en un clic (Devis envoyé → Payé → Démarches en cours → Terminé, avec date de paiement fixée automatiquement au premier passage à « Payé »), enregistrement de la **signature du mandat** (nom du signataire + date).
- **Restitution complète (post-paiement)** : une fois le statut « Payé »/« Démarches en cours »/« Terminé » atteint, le **PDF complet** (détail des offres, comparatif) devient téléchargeable, reconstruit depuis les offres d'intérêt du prospect ou les contrats du client.
- Liste filtrable par statut, compteur total.

### 8. Administration (menu « 🛠️ Admin », réservé Admin)
8 onglets :
- **👤 Utilisateurs** : création de comptes, modification (nom/rôle/statut actif/mot de passe), suppression.
- **📚 Catalogue** : liste des offres, modification de prix, activation/désactivation, suppression, **lien de souscription + code d'affiliation** par offre.
- **➕ Ajouter une offre** : formulaire (dont URL de souscription/code d'affiliation) + lien direct vers un comparateur externe selon l'univers.
- **⚡ Pré-remplir (démo)** : charge un jeu d'offres type pour tester rapidement.
- **📧 Email** : nom de société (en-tête PDF/email), configuration SMTP (serveur, port, identifiant, mot de passe), et **réglages de `notifications.py`** (email du conseiller à notifier, jeton bot + chat ID Telegram) — persistés en base pour être réutilisables par le script planifié.
- **💶 Facturation** : taux d'honoraires par défaut appliqué à la création d'un devis.
- **🔍 OCR Vision** : activation de l'extraction de facture par IA (clé API Anthropic, stockée en base, jamais affichée en clair) — sans clé, l'app retombe automatiquement sur l'extraction PyPDF2 classique.
- **📈 Veille prix** : 3 sous-onglets — **Sources surveillées** (ajout d'une page tarif à surveiller : univers/catégorie/fournisseur/URL/sélecteur CSS, offre du catalogue à mettre à jour après validation, bouton « 🔎 Lancer la veille maintenant »), **Alertes en attente** (valider ou rejeter chaque changement de prix détecté), **Historique des prix** (graphique de tendance par source). Nécessite `playwright install chromium` pour scraper réellement (sinon message d'avertissement).

### 9. API REST interne (menu Admin exclu — `crm_api.py`, process séparé, JWT)

À distinguer de l'API chatbot publique (section 🤖 plus bas) : celle-ci est **authentifiée** et réservée aux intégrations internes/futures (CRUD complet, diagnostic). Streamlit s'y connecte déjà via `api_client.py` mais continue de fonctionner normalement si elle n'est pas lancée (repli silencieux sur la base directe, avec un `st.toast` d'avertissement une fois par session).

```bash
cd src
uvicorn crm_api:app --host 0.0.0.0 --port 8000
```
- `POST /auth/login` (username/password → JWT, 8h de validité) puis `Authorization: Bearer <token>` sur toutes les routes suivantes.
- CRUD `GET/POST/PATCH/DELETE` sur `/prospects`, `/clients`, `/clients/{id}/contrats`, `/contrats/{id}` — écriture réservée aux rôles Conseiller/Admin.
- CRUD `/offres` réservé au rôle Admin (comme l'onglet Catalogue).
- Diagnostic authentifié : `POST /diagnostic/comparer`, `/diagnostic/bilan`, `/diagnostic/complet` (multi-univers Télécom + Énergie + Abonnements, pour de futurs clients headless : app mobile, portail client, webhooks).
- `GET /health`, doc Swagger sur `GET /docs`.
- Secret JWT via la variable d'environnement `CRM_API_SECRET` (sinon secret de dev affiché en avertissement — à définir avant tout déploiement réel). Côté Streamlit, `CRM_API_URL` (défaut `http://127.0.0.1:8000`) et `CRM_API_TIMEOUT` (défaut 3s) sont configurables par variable d'environnement.

### 10. Notifications planifiées (`notifications.py`, hors app Streamlit)
Script autonome à lancer via une tâche planifiée quotidienne, indépendant de Streamlit :
```bash
python notifications.py                  # relances du jour + retard + alertes fin d'engagement
python notifications.py --resume-hebdo   # + résumé hebdomadaire (à lancer le lundi)
```
- Envoie par **email et/ou Telegram** la liste des relances (prospects + clients) du jour et en retard.
- Déclenche l'**alerte client automatique** (email HTML, avec offre alternative si économie identifiée) pour tout contrat atteignant le seuil de 60 jours avant fin d'engagement, et journalise l'action dans l'audit trail.
- Option résumé hebdomadaire : nombre de prospects/clients en base, économies totales estimées.
- Planification Windows : `schtasks /create /tn "IA Conseil - Relances" /sc daily /st 08:00 /tr "python C:\chemin\src\notifications.py"`. Planification cron : `0 8 * * * cd /chemin/src && python notifications.py`.

---

## ⚙️ Fonctionnalités clés en détail

### Moteur de comparaison (`offres_engine.py`)
```python
comparer_offres(univers, categorie, cout_actuel_mensuel, fournisseurs_autorises=None, fournisseur_exclu=None)
→ liste d'offres triées par économie annuelle décroissante
```
`construire_recommandations()` adapte l'offre principale et les cross-sell au service télécom recherché (Mobile / Box / Pack / Multi-lignes).

### Analyse de facture — deux moteurs (`pdf_engine.py`)
- `analyser_facture(texte)` : détecte opérateur/fournisseur, prix, code postal/ville, nom du client, téléphone, email, data mobile — par expressions régulières, tolérant aux formats hétérogènes (PDF texte uniquement).
- `analyser_facture_vision(contenu, nom_fichier, api_key, model="claude-sonnet-5")` : mêmes champs, extraits par l'API **Claude Vision** — fonctionne sur PDF, JPG, PNG (photo/scan compris) ; retombe silencieusement sur `None` (→ fallback PyPDF2) si le package `anthropic`, la clé API ou le format sont absents/invalides.
- `analyser_speedtest_pdf()` : extrait débit descendant/montant.

### Génération PDF (`pdf_engine.py`)
- `generer_pdf_teaser()` : PDF "aperçu" envoyé après le diagnostic — économie totale chiffrée, sans détail des offres.
- `generer_pdf_restitution()` : PDF complet multi-pages, cartes d'offres détaillées + bandeau d'économie totale.
- `generer_pdf_devis()` / `generer_pdf_mandat()` : devis d'honoraires et mandat de représentation, générés depuis un enregistrement `factures`.

### Souscription
- **Lien affilié direct** (`utils.construire_lien_affilie`) : bouton « 🔗 Souscrire » sur toute offre disposant d'une URL de souscription, avec code d'affiliation et coordonnées client en paramètres d'URL ; chaque clic est tracé dans l'audit.
- **Pré-remplissage assisté** (`souscription_engine.py`, Playwright) : pour Free et Bouygues (`OPERATEURS_SUPPORTES`), ouvre un vrai navigateur visible (process détaché, indépendant de Streamlit) sur le formulaire de souscription du site opérateur, pré-rempli avec les coordonnées du prospect/client — le formulaire **n'est jamais soumis automatiquement** : le conseiller vérifie et valide lui-même sur le site.

### Réseau le plus fort par ville (`clients_engine.py`)
- `note_couverture_par_zone(ville)` : moyenne de satisfaction réseau déclarée par opérateur (prospects + clients de la ville).
- `meilleur_debit_par_zone(ville)` : moyenne des débits ⬇️/⬆️ mesurés par opérateur (même périmètre) — recommandation objective complémentaire à la satisfaction subjective.

### Relances
- Prospects : `widget_relance()` — bouton « Relance effectuée » (+7 j auto) + date précise en option ; nouveau prospect toujours positionné sur aujourd'hui.
- Clients : `widget_relance_client()` — même principe, cadence par défaut +30 jours, activation manuelle depuis la fiche client.
- Relais hors app : `notifications.py` (voir section 10) envoie le digest quotidien même app fermée.

### Veille prix (`veille_prix_engine.py`)
- `extraire_prix(texte)` : regex sur le texte de la page (pas de dépendance IA).
- `scraper_source(source)` / `_recuperer_texte_page()` : Playwright **headless**, isolé pour être simulé (monkeypatch) dans les tests sans navigateur réel.
- `lancer_veille()` : relève le prix de chaque source active, journalise toujours dans `veille_historique_prix`, crée une `veille_alertes` (`en_attente`) uniquement si l'écart dépasse `SEUIL_ECART_PRIX` (0,01 €). Ne touche jamais `offres` directement.
- `valider_alerte(alerte_id)` : seule fonction qui répercute le nouveau prix sur l'offre du catalogue (si la source y est rattachée) — action explicite d'un admin, tracée dans l'audit. `rejeter_alerte(alerte_id)` classe sans effet.
- Exécutable en tâche planifiée (voir en-tête du fichier pour les commandes `schtasks`/cron) ; notifie l'admin (email/Telegram) via `notifications.notifier_changement_prix()` à chaque changement détecté.

### API REST interne & découplage Streamlit (`crm_api.py`, `jwt_auth.py`, `api_client.py`)
- `jwt_auth.creer_token(user)` : émet un JWT (HS256, 8h) signé avec `CRM_API_SECRET` (secret de dev affiché en avertissement si absent).
- `jwt_auth.get_current_user` / `require_role(*roles)` : dépendances FastAPI qui protègent chaque route de `crm_api.py` (401 si jeton absent/invalide, 403 si rôle insuffisant).
- Chaque fonction d'`api_client.py` a exactement la même signature que son équivalent `*_engine.py` : `app.py` peut donc appeler l'un ou l'autre sans changement de logique. En cas d'échec réseau (`_ApiIndisponible`), repli **silencieux et automatique** sur l'accès direct à la base — un `st.toast` avertit une fois par session que l'API est injoignable.
- Le login Streamlit (formulaire + `st.session_state`) reste inchangé : un JWT est simplement émis localement (sans appel réseau) au moment de la connexion, et stocké dans `st.session_state.api_token` pour authentifier les futurs appels à `crm_api.py`.

### Scoring de priorité des prospects (`prospects_engine.py`)
```python
calculer_score_prospect(prospect, dernier_contact=None)
→ score = economie_estimee_an*2 + jours_depuis_dernier_contact*3
        + (satisfaction_basse ? +20 : 0) + (veut_rester ? -15 : 0)
        + (type_pro ? +10 : 0)
```
- `jours_depuis_dernier_contact` est déduit de l'historique d'audit (dernière relance effectuée/programmée sur ce prospect), ou à défaut de sa date de création.
- `recalculer_scores_prospects()` recalcule et persiste le score de tous les prospects (colonne `score`) — appelé à chaque affichage du Tableau de bord et de la liste Prospects.
- `indicateur_score(score)` renvoie l'étiquette visuelle 🔴 chaud / 🟡 tiède / 🟢 froid utilisée dans les tableaux et la fiche prospect.
- Sert à trier les relances par priorité business plutôt que par simple date d'échéance.

### Recherche plein texte
- Index **SQLite FTS5** sur `prospects` et `clients`, tenu à jour automatiquement.
- `recherche_fts(table, terme)` renvoie les IDs correspondants — utilisé dans les pages Prospects et Clients pour une recherche instantanée multi-champs (nom, ville, email, opérateur…).

### Facturation & mandat (`facturation_engine.py`)
- `creer_facture()`, `lire_factures()`, `maj_facture()`, `changer_statut()` (fixe automatiquement la date de paiement au premier passage à « Payé »), `marquer_mandat_signe()`.
- `lier_facture_a_client()` : rattache les devis existants d'un prospect au client créé lors de la conversion.

### Sécurité
- Mots de passe : PBKDF2-SHA256, 260 000 itérations, sel aléatoire par compte, comparaison en temps constant.
- Toute requête SQL utilise des paramètres liés (pas de concaténation) → pas d'injection SQL.
- Clé API Anthropic stockée en base (table `parametres`), jamais affichée en clair dans l'UI.
- Traçabilité systématique : `cree_par` sur chaque enregistrement + table d'audit insert-only (inclut les clics sur liens affiliés et les pré-remplissages de souscription).
- API interne (`crm_api.py`) protégée par JWT (`CRM_API_SECRET` à définir hors dev) ; API chatbot (`chatbot_api.py`) volontairement publique mais rate-limitée (30 req/min/IP).

### Tests & CI
- Suite **pytest** (`src/tests/`) couvrant auth, moteur d'offres, utils, pdf_engine, prospects_engine, souscription_engine (`conftest.py` pour les fixtures communes).
- **GitHub Actions** (`.github/workflows/tests.yml`) : installe `requirements-dev.txt` et lance `pytest -q` à chaque push et pull request.

---

## 🤖 Chatbot public (diagnostic 24/7, `chatbot_api.py` + `chatbot_engine.py`)

Un second process, indépendant de Streamlit, partage la même base SQLite pour offrir un point d'entrée public (site web / futur WhatsApp) :

```bash
cd src
uvicorn chatbot_api:app --host 0.0.0.0 --port 8001
```

- `POST /api/chat` — fait progresser une conversation (`session_id`, `message`) ; Claude (tool-use, clé configurée dans Admin > OCR Vision — `anthropic_api_key`) collecte progressivement prénom/nom, contact, ville, et la situation Télécom/Énergie actuelle, puis crée le prospect (`origine='Chatbot'`) et notifie le conseiller (mêmes canaux email/Telegram que `notifications.py`).
- `POST /api/prospects`, `POST /api/offres/comparer`, `POST /api/bilan` — endpoints structurés réutilisables indépendamment du chat.
- `GET /docs` — documentation Swagger auto-générée.
- Widget d'intégration : `<script src="https://votre-api/widget/chatbot_widget.js" data-api-url="https://votre-api"></script>` (bulle de chat flottante, aucune dépendance).
- Aucune authentification sur ces endpoints (usage public assumé) — un limiteur de débit basique en mémoire (30 req/min/IP) protège contre le spam le plus simple ; CORS ouvert à tout domaine pour permettre l'intégration sur n'importe quel site.

---

## 📊 Sorties du logiciel

- Fiche prospect / client complète avec historique d'actions
- PDF "aperçu" (économie totale) + PDF de restitution complète (après paiement du devis) + email HTML
- Devis d'honoraires PDF + mandat de représentation PDF
- Contrats liés à chaque client (création, modification, suppression)
- Exports Excel (listes prospects/clients)
- Tableau de bord commercial temps réel (KPIs, relances, performance équipe)
- Digest quotidien de relances (email/Telegram) + alertes automatiques de fin d'engagement, via `notifications.py`

---

## 🎬 Vision à terme

Les phases 1 à 4 de la roadmap (fondations, automatisations, IA — chatbot, veille prix, API REST) sont **toutes livrées**. Reste la phase 5 (scale) : app mobile conseiller, portail client self-service, multi-tenant SaaS, agent IA totalement autonome capable d'analyser une facture, recommander et souscrire sans intervention humaine sauf cas complexes. Roadmap détaillée : voir `IA_CONSEIL_ROADMAP.md`.
