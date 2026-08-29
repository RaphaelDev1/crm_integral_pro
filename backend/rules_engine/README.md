# rules_engine

Moteur de trame adaptative et de recommandation — cœur du produit "IA Conseil"
(PLAN_IMPLEMENTATION_4_PHASES.md §0.4). Modules purs Python, sans dépendance à
la base de données : ils opèrent sur des dicts (trame, réponses, offres,
règles) déjà chargés, et sont donc directement unit-testables.

## Modules

| Module | Rôle |
|---|---|
| `condition_evaluator.py` | Évalue le DSL de condition JSON utilisé partout (`$eq $ne $gt $gte $lt $lte $in $nin $and $or $not $exists`). |
| `trame_runtime.py` | Calcule l'ensemble des questions encore éligibles compte tenu des réponses, des branches actives (`when`, `skip`) et des `show_if`. |
| `information_scorer.py` | Calcule `score_info(question)` (§Principe #1) : offres éliminées + règles utilisatrices + poids éthique − coût cognitif. |
| `question_selector.py` | ★ Cœur "escargot" ★ — choisit la question éligible de score maximal ; renvoie `None` dès que toutes les questions restantes sont sous le seuil (trame terminée sans épuiser le template). |
| `scoring.py` | Score chaque offre du catalogue (filtre puis scoring), retourne un classement avec justifications. |
| `alertes.py` | Génère les alertes (anti-survente, etc.) à partir des règles `type='alerte'`, avec templating `{{...}}`. |

## Le DSL de condition

Une condition est soit un opérateur logique en clé unique (`$and`/`$or`/`$not`
avec une liste ou une sous-condition), soit un ou plusieurs chemins de champs
en clé (`"reponses.conso_data_go"`), chacun associé à une valeur littérale
(raccourci `$eq`) ou à un dict d'opérateurs (`{"$gt": 10, "$lte": 100}` = ET
implicite entre opérateurs). Plusieurs clés au même niveau = ET implicite.

```json
{
  "$and": [
    {"reponses.conso_data_go": {"$lt": 10}},
    {"offre.caracteristiques.data_go": {"$gt": 50}}
  ]
}
```

Une valeur manquante (chemin introuvable) est distincte de `null` explicite :
`$exists` teste la présence réelle du chemin, les autres opérateurs traitent
une valeur manquante comme `None` (donc `$eq: null` matche aussi bien un champ
absent qu'un champ explicitement nul ; les opérateurs d'ordre `$gt/$gte/$lt/
$lte` renvoient `False` sur une valeur manquante ou de type incompatible,
jamais d'exception).

**Cas particulier `show_if` / `branches.when`** (`trame_runtime.py`) : pour
éviter qu'une question dérivée (ex. "voyages hors UE ?") ne devienne éligible
avant que sa dépendance directe (ex. "voyages en Europe ?") ait été répondue,
`trame_runtime` exige que les champs référencés directement par la condition
(hors `$or`/`$not`, où le champ requis n'est pas déterminable simplement)
existent déjà dans les réponses. Un `show_if` combiné avec `$or` n'a donc pas
cette garde — c'est une limitation connue, à contourner en structurant le
`show_if` avec `$and` si l'ordre importe.

## Simplifications assumées vis-à-vis du plan

Le plan illustre deux mécanismes avec du texte libre plutôt qu'un format
structuré. Pour rester cohérent (un seul DSL dans tout le moteur) et
réellement testable sans écrire un parseur d'expressions, ce module les
remplace par des équivalents structurés :

- `question.elimine_offres_si` : chaque scénario doit être une condition DSL
  (contexte `{"offre": ...}`), pas une chaîne du type `"offres.data_go > 40"`.
  Un scénario non conforme est ignoré silencieusement plutôt que de lever une
  erreur.
- `regle_recommandation.action` de type `score_adjust` : au lieu d'une
  pseudo-formule `IF(...)`, utiliser soit `{"valeur": N}` (ajustement
  constant), soit `{"bareme": [{"si": <condition>, "valeur": N}, ...],
  "defaut": N}` (équivalent d'un `IF/ELSE` imbriqué, première condition qui
  matche l'emporte).

## Tests

```
python -m pytest backend/rules_engine/tests -q --cov=backend.rules_engine --cov-report=term-missing
```

94 tests, 99% de couverture (objectif plan : > 80%).
