# API

Il n'y a pas d'API HTTP aujourd'hui : `src/app.py` est une application
Streamlit monolithique, l'UI appelle directement les fonctions Python
d'accès aux données (voir [DATABASE.md](DATABASE.md) et
[ARCHITECTURE.md](ARCHITECTURE.md)).

Ce fichier est un placeholder à remplir si/quand une API (ex. FastAPI)
est ajoutée devant ou à côté de l'app Streamlit — par exemple pour
exposer les CRUD prospects/clients/contrats/offres à un autre client
(mobile, intégration externe).

Fonctions actuelles qui deviendraient naturellement des endpoints :

| Domaine | Fonctions `app.py` | Endpoint envisageable |
|---|---|---|
| Prospects | `ajouter_prospect`, `lire_prospects`, `maj_prospect`, `supprimer_prospect` | `POST/GET/PATCH/DELETE /prospects` |
| Clients | `ajouter_client`, `lire_clients`, `maj_client`, `supprimer_client` | `POST/GET/PATCH/DELETE /clients` |
| Contrats | CRUD contrats (section 6) | `.../clients/{id}/contrats` |
| Offres | CRUD offres (section 7) | `GET/POST /offres` |
| Auth | `authentifier_utilisateur`, `hash_password` | `POST /auth/login` (à adapter : sessions → JWT) |

À date, aucune décision n'a été prise sur le framework ni sur
l'authentification pour cette API — à documenter ici le jour où le
besoin se concrétise.
