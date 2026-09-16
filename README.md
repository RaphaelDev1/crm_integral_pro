# IA Conseil — CRM Intégral Pro

Application interne (Streamlit + SQLite) pour conseillers Télécom /
Énergie / Abonnements : diagnostic client guidé, comparaison d'offres,
restitution PDF + email, suivi des prospects et clients.

## Fonctionnalités clés

- **Wizard de diagnostic** en 4 étapes (univers → besoins → comparaison →
  recommandations) avec calcul d'économie automatique.
- **Offres favorites du client** : chaque offre proposée (principale, box,
  pack) peut être cochée « ⭐ Intéresse le client » ; toutes les offres
  cochées sont reprises intégralement dans le PDF de restitution et l'email
  envoyé, et affichées sous forme de cartes sur la fiche prospect.
- **Fiche prospect** : édition en un seul clic (« 💾 Enregistrer » global,
  pas un bouton par champ), conversion en client, suppression.
- **Relances** : planification automatique à +7 jours ou choix d'une date
  précise (utile pour les offres avec engagement), avec vue « en retard /
  aujourd'hui / à venir » sur le tableau de bord.
- **Suivi & reporting** : export Excel des listes, historique des actions
  par client, performance par conseiller (vue Admin).
- **Souscription assistée** : bouton « 🖊️ Pré-remplir la souscription » (fiche
  prospect et contrats client, opérateurs Free/Bouygues) — ouvre le formulaire
  de souscription réel dans un navigateur, pré-rempli avec les données du CRM ;
  le conseiller vérifie et valide lui-même, aucune soumission automatique.

## Démarrer

```
cd src
pip install -r requirements.txt
playwright install chromium
streamlit run app.py
```

Identifiants par défaut au premier lancement : `admin` / `Admin2026!`
(à changer immédiatement dans **Admin > Utilisateurs**).

## Documentation

- [docs/CARTOGRAPHIE_APPLICATION.md](docs/CARTOGRAPHIE_APPLICATION.md) — vue d'ensemble de a à z : ce que fait l'application, comment elle est construite (backend, frontends, module IA Conseil), structure des dossiers
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — organisation du code et du flux applicatif (legacy Streamlit)
- [docs/DATABASE.md](docs/DATABASE.md) — schéma SQLite
- [docs/API.md](docs/API.md) — placeholder pour une future API
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — conventions de contribution
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — historique des versions

Pour travailler avec Claude Code sur ce projet, voir `.claude/quick-context.txt`.
