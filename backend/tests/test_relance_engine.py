# ==============================================================================
#  TESTS — services/relance_engine.py::prochaine_date_relance.
# ==============================================================================
from datetime import date

from backend.services.relance_engine import prochaine_date_relance


def test_sans_preference_retombe_sur_j_plus_7():
    reference = date(2026, 8, 24)  # lundi
    assert prochaine_date_relance(None, reference=reference) == date(2026, 8, 31)


def test_peu_importe_retombe_sur_j_plus_7():
    reference = date(2026, 8, 24)  # lundi
    assert prochaine_date_relance("Peu importe · Matin (9h-12h)", reference=reference) == date(2026, 8, 31)


def test_jour_prefere_plus_proche_avant_l_echeance_pas_la_semaine_suivante():
    # reference = lundi 24/08 -> échéance à J+7 = lundi 31/08.
    # Le client veut être rappelé le samedi : le samedi le plus proche est
    # le 29/08 (J+5, avant l'échéance), pas le 05/09 (J+12, la semaine suivante).
    reference = date(2026, 8, 24)
    resultat = prochaine_date_relance("Samedi · Après-midi (12h-17h)", reference=reference)
    assert resultat == date(2026, 8, 29)
    assert resultat.weekday() == 5


def test_jour_prefere_plus_proche_apres_l_echeance():
    # reference = mardi 25/08 -> échéance à J+7 = mardi 01/09.
    # Préférence "Mercredi" : le mercredi le plus proche est le 02/09 (J+8),
    # plus proche que celui d'avant (27/08, J+2).
    reference = date(2026, 8, 25)
    resultat = prochaine_date_relance("Mercredi · Soir (17h-20h)", reference=reference)
    assert resultat == date(2026, 9, 2)
    assert resultat.weekday() == 2


def test_jour_non_reconnu_retombe_sur_j_plus_7():
    reference = date(2026, 8, 24)
    assert prochaine_date_relance("Dimanche · Matin (9h-12h)", reference=reference) == date(2026, 8, 31)
