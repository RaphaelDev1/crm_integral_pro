# ==============================================================================
#  TESTS — utils.py (safe_float, valider_email, valider_telephone, generer_ref)
# ==============================================================================
import re

import pytest

from utils import safe_float, valider_email, valider_telephone, generer_ref


class TestSafeFloat:
    def test_chaine_numerique(self):
        assert safe_float("12.5") == 12.5

    def test_int_passthrough(self):
        assert safe_float(7) == 7.0

    def test_chaine_invalide_retombe_sur_defaut(self):
        assert safe_float("abc") == 0.0

    def test_none_retombe_sur_defaut(self):
        assert safe_float(None) == 0.0

    def test_chaine_vide_retombe_sur_defaut(self):
        assert safe_float("") == 0.0

    def test_defaut_personnalise(self):
        assert safe_float("abc", default=42.0) == 42.0


class TestValiderEmail:
    @pytest.mark.parametrize("email", [
        "jean.dupont@example.fr",
        "a@b.co",
        "prenom.nom+tag@sous-domaine.example.com",
    ])
    def test_emails_valides(self, email):
        assert valider_email(email) is True

    @pytest.mark.parametrize("email", [
        "pas-un-email",
        "manque-arobase.fr",
        "@manque-partie-locale.fr",
        "espace dans@email.fr",
    ])
    def test_emails_invalides(self, email):
        assert valider_email(email) is False

    def test_email_vide_est_permissif(self):
        # Champ optionnel côté formulaire : le vide n'est pas bloqué (juste un
        # avertissement UI non bloquant côté app.py).
        assert valider_email("") is True
        assert valider_email("   ") is True


class TestValiderTelephone:
    @pytest.mark.parametrize("tel", [
        "0601020304",
        "06 01 02 03 04",
        "06-01-02-03-04",
        "+33601020304",
    ])
    def test_telephones_valides(self, tel):
        assert valider_telephone(tel) is True

    @pytest.mark.parametrize("tel", [
        "060102030",     # 9 chiffres — trop court
        "16010203045",   # ne commence pas par 0 ou +33
        "abcdefghij",    # pas des chiffres
        "1234567890",    # ne commence pas par 0 ou +33
    ])
    def test_telephones_invalides(self, tel):
        assert valider_telephone(tel) is False

    def test_telephone_vide_est_permissif(self):
        assert valider_telephone("") is True


class TestGenererRef:
    def test_format(self):
        ref = generer_ref("CLI")
        assert re.match(r"^CLI-\d{4}-\d{4}-\d{6}$", ref)

    def test_prefixe_respecte(self):
        assert generer_ref("PROS").startswith("PROS-")

    def test_unicite_sur_1000_appels(self):
        """generer_ref() combine un compteur atomique (thread-safe, incrémenté à
        chaque appel) et un suffixe aléatoire : sur 1000 appels consécutifs, le
        compteur (mod 1000) parcourt exactement une fois chaque valeur de 0 à 999,
        ce qui garantit l'unicité même en rafale/accès concurrent au sein d'un
        même process — le cas de tous les conseillers connectés au même serveur."""
        refs = [generer_ref("REF") for _ in range(1000)]
        assert len(set(refs)) == len(refs)

    def test_unicite_sous_charge_concurrente(self):
        """Vérifie l'absence de collision quand plusieurs threads (conseillers
        simultanés sur le même process Streamlit) appellent generer_ref() en même
        temps — c'est le scénario concret que le compteur atomique protège."""
        import threading

        refs = []
        lock = threading.Lock()

        def worker():
            ref = generer_ref("CONC")
            with lock:
                refs.append(ref)

        threads = [threading.Thread(target=worker) for _ in range(200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(refs) == 200
        assert len(set(refs)) == 200
