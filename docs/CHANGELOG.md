# Changelog

## API REST interne + découplage Streamlit (2026-07-04)

- Nouveau module `crm_api.py` (roadmap 4.3) : API FastAPI interne, distincte
  de `chatbot_api.py` (publique, sans auth). CRUD complet prospects / clients
  / contrats / offres, endpoints diagnostic (`/diagnostic/comparer`,
  `/diagnostic/bilan`, `/diagnostic/complet`), authentification par JWT
  (`jwt_auth.py`). Documentation Swagger auto-générée sur `/docs`.
  Lancement : `uvicorn crm_api:app --port 8000`.
- Les mutations catalogue (`/offres`) restent réservées au rôle Admin, comme
  dans l'onglet Admin de Streamlit ; les autres écritures (prospects,
  clients, contrats) exigent Conseiller ou Admin — mêmes règles que
  `peut_modifier()`/`est_admin()` dans `app.py`.
- Nouveau module `api_client.py` : Streamlit (`app.py`) appelle désormais
  cette API au lieu d'accéder directement aux modules `*_engine.py`, pour les
  entités couvertes par l'API. Chaque fonction a la même signature que son
  équivalent `*_engine.py` et **retombe automatiquement** sur l'accès direct
  à la base si l'API n'est pas démarrée ou injoignable — aucune régression
  possible tant que l'API n'est pas systématiquement déployée (phase de test).
- Le login Streamlit reste inchangé (formulaire + session) ; un JWT est émis
  localement à la connexion (sans appel réseau) pour authentifier les appels
  à l'API au nom de l'utilisateur connecté.
- `db.enregistrer_action()` et les fonctions de mutation de
  `clients_engine.py` / `contrats_engine.py` acceptent désormais un paramètre
  `auteur` explicite, pour que l'audit trail attribue correctement les
  actions faites depuis l'API (hors contexte `st.session_state`).

## Veille prix automatique (2026-07-03)

- Nouveau module `veille_prix_engine.py` (roadmap 4.2) : surveille des pages
  tarifs opérateurs via Playwright headless et détecte les changements de
  prix. Nouvelles tables `sources_veille`, `veille_historique_prix`,
  `veille_alertes` (cf. `docs/DATABASE.md`).
- Le catalogue n'est **jamais** modifié automatiquement : chaque changement
  de prix détecté crée une alerte `en_attente` ; un admin valide (répercute
  le prix sur l'offre liée) ou rejette depuis **Admin > 📈 Veille prix**.
- Historique des prix par source (graphique `st.line_chart`) pour visualiser
  les tendances.
- Notification admin (email/Telegram, mêmes canaux que `notifications.py`)
  à chaque changement détecté — `notifier_changement_prix()`.
- Exécutable en tâche planifiée, comme `notifications.py` :
  `python veille_prix_engine.py` (schtasks / cron, cf. en-tête du fichier).

## Retours conseillers (2026-07-02)

- Étape 4 du wizard : la case « ⭐ Intéresse le client » est désormais
  disponible sur **toutes** les offres proposées — y compris la Box/Fibre
  et les Packs Box + Mobile en cross-sell (auparavant réservée à l'offre
  principale) — pour inciter à la vente complémentaire.
- Toute offre cochée « Intéresse le client » (principale ou cross-sell)
  est désormais reprise intégralement dans le **PDF de restitution** et
  dans l'**email envoyé au client** (auparavant seule la meilleure offre
  de chaque catégorie y figurait, indépendamment des cases cochées).
- Fiche prospect détaillée : la section « ⭐ Offres qui intéressaient le
  client » est affichée sous forme de cartes (nom, fournisseur, prix,
  économie/an, engagement) au lieu d'un dump JSON brut.
- Fiche prospect : le formulaire « ✏️ Modifier ce prospect » utilise
  désormais un seul bouton « 💾 Enregistrer » (`st.form`) au lieu d'un
  bouton de sauvegarde par champ.
- Relances : nouveau contrôle « 🔁 Automatique (+7 jours) / 📅 Date
  précise » (tableau de bord + fiche prospect) remplaçant le bouton
  « Marqué relancé aujourd'hui », qui fixait à tort la prochaine relance
  au jour même. Utile pour programmer une relance à une date précise sur
  les offres avec engagement.

## Étape 4 — IA (roadmap, non implémenté)

- Extraction de facture par LLM au lieu du regex (beaucoup plus fiable).
- Scoring intelligent des recommandations.

## Corrections diagnostic (2026-07-02)

- Étape 3 du wizard : le choix « Technologie » se limite à 4G/5G quand le
  service principal est « Mobile uniquement » (plus de FIBRE/ADSL hors sujet).
- Bug corrigé : les boutons +/- des débits (descendant/montant) nécessitaient
  deux clics pour s'incrémenter — les widgets sont maintenant liés à
  `st.session_state` via `key=` au lieu de `value=`, ce qui règle le décalage.
- Moteur de recommandations : si le client n'est pas pleinement satisfait de
  son réseau actuel (« Ça va » ou « Pas du tout »), les offres du même
  opérateur sont exclues des recommandations (`fournisseur_exclu` sur
  `comparer_offres()` / `construire_recommandations()`).
- Nouveau bouton « ⬅️ Corriger une information » à l'étape 4 du diagnostic,
  pour revenir à l'étape 3 sans réinitialiser tout le wizard.
- Étape 4 : chaque offre principale proposée peut être cochée « ⭐ Intéresse
  le client » ; la sélection est stockée en JSON dans la nouvelle colonne
  `prospects.offres_interet` et affichée sur la fiche prospect.
- Nouvelle fonction `note_couverture_par_zone()` : agrège la satisfaction
  réseau moyenne par opérateur pour la ville du client (prospects + clients
  confondus) et affiche une suggestion d'opérateur local à l'étape 3 quand la
  satisfaction n'est pas maximale — première brique vers une note de
  couverture réseau par zone.

## Étape 3 — Améliorations fonctionnelles (2026-07-02)

- **Tableau de bord conseiller** : la section « Relances à traiter » compare
  désormais les dates réelles (`parser_date_relance()`) au lieu de trier la
  colonne `date_relance` comme du texte (faux dès qu'on change de mois/année).
  Les relances sont réparties en 4 groupes : 🔴 En retard, 🟠 Aujourd'hui,
  🟢 À venir, ⚪ Sans date.
- **Export Excel** des listes Prospects et Clients (en plus du PDF de
  restitution existant, qui reste un export par client) : bouton
  « 📥 Exporter en Excel (.xlsx) » sur chaque page de liste, via
  `exporter_excel()` (moteur `openpyxl`, nouvelle dépendance).
- **Historique des actions sur la fiche client** : nouvelle table
  `historique_actions` (voir `docs/DATABASE.md`) alimentée par
  `enregistrer_action()` à chaque création, modification ou suppression
  de client, ajout/modification/suppression de contrat, et conversion
  prospect → client. Affiché en lecture seule (qui a fait quoi, quand)
  dans la fiche client, visible même en rôle Lecture.

## 2026-07-02

- Réorganisation du projet : le code applicatif passe de
  `crm_integral_pro.py` (racine) à `src/app.py`, la base SQLite le suit
  dans `src/ia_conseil_crm.db`.
- Le chemin de la base est désormais résolu relativement à `app.py`
  (`os.path.dirname(__file__)`) au lieu d'un chemin relatif au répertoire
  de lancement.
- Ajout de `docs/` (architecture, API, base de données, contribution) et
  de `.claude/` (contexte, règles, checklist, prompts types).
- **Suppression de la page d'accueil** (`🏠 Accueil`) : après connexion,
  l'utilisateur arrive directement sur le **Tableau de bord**, qui devient
  la page d'atterrissage par défaut (y compris après déconnexion/
  reconnexion).

## Étape 2 — Fiabiliser l'existant

- Bug critique : `st.rerun()` manquant en fin d'étape 5 du wizard (page
  bloquée après création client).
- Bug : `generer_ref()` pouvait produire des doublons en accès concurrent.
- Bug : calcul d'économie des abonnements ignorait le coût client réel.
- Validation email + téléphone avant enregistrement.
- `safe_float()` — conversions numériques protégées, plus de crash.
- Spinner sur les opérations lentes (comparaison, génération PDF).
- Filtre par statut sur la page Prospects.
- Confirmation avant suppression prospect / client.
- Affichage propre quand la recherche client ne retourne rien.
- Notes auto-enrichies à la création.

## Étape 1 — Fondations solides

- Mode WAL SQLite, comptes nominatifs, rôles, traçabilité, sécurité SQL
  (whitelists `CHAMPS_*`, requêtes paramétrées).
