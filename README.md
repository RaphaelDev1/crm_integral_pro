# IA Conseil — CRM Intégral Pro

Application interne (Streamlit + SQLite) pour conseillers Télécom /
Énergie / Abonnements : diagnostic client guidé, comparaison d'offres,
restitution PDF + email, suivi des prospects et clients.

## Démarrer

```
cd src
pip install -r requirements.txt
streamlit run app.py
```

Identifiants par défaut au premier lancement : `admin` / `Admin2026!`
(à changer immédiatement dans **Admin > Utilisateurs**).

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — organisation du code et du flux applicatif
- [docs/DATABASE.md](docs/DATABASE.md) — schéma SQLite
- [docs/API.md](docs/API.md) — placeholder pour une future API
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — conventions de contribution
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — historique des versions

Pour travailler avec Claude Code sur ce projet, voir `.claude/quick-context.txt`.
