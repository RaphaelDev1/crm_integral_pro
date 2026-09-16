# ==============================================================================
#  RELANCE_ENGINE — calcule la prochaine date de relance en tenant compte du
#  jour de rappel souhaité par le prospect (Prospect.plage_horaire_rappel,
#  ex. "Samedi · Matin (9h-12h)"), au lieu d'un simple +7 jours fixe.
# ==============================================================================
from datetime import date, datetime, timedelta

# Lundi=0 ... Samedi=5 (aucune option "Dimanche" dans JOURS_RAPPEL_OPTIONS côté
# frontend — voir frontend-conseiller/lib/diagnosticConstants.ts).
_JOURS_SEMAINE = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
}

SEPARATEUR_CRENEAU_RAPPEL = " · "


def _jour_prefere(plage_horaire_rappel: str | None) -> int | None:
    if not plage_horaire_rappel:
        return None
    jour = plage_horaire_rappel.split(SEPARATEUR_CRENEAU_RAPPEL)[0].strip().lower()
    return _JOURS_SEMAINE.get(jour)


def prochaine_date_relance(
    plage_horaire_rappel: str | None,
    base_jours: int = 7,
    reference: date | None = None,
) -> date:
    """Date de la prochaine relance : par défaut `reference + base_jours`, sauf
    si le prospect a indiqué un jour de rappel préféré (Lundi-Samedi), auquel
    cas on retient l'occurrence de ce jour la plus proche de l'échéance à
    `base_jours` — avant ou après, jamais reportée d'une semaine complète.
    Ex. échéance à 7 jours tombant un vendredi, préférence "Samedi" : le samedi
    le plus proche est à 5 jours (avant) plutôt qu'à 12 jours (la semaine
    suivante) — on retient donc J+5."""
    reference = reference or datetime.now().date()
    cible = reference + timedelta(days=base_jours)

    jour = _jour_prefere(plage_horaire_rappel)
    if jour is None:
        return cible

    meilleur_ecart = None
    meilleure_date = cible
    for decalage in range(-3, 4):
        candidate = cible + timedelta(days=decalage)
        if candidate.weekday() != jour:
            continue
        ecart = abs(decalage)
        if meilleur_ecart is None or ecart < meilleur_ecart:
            meilleur_ecart = ecart
            meilleure_date = candidate
    return meilleure_date
