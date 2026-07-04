# ==============================================================================
#  TESTS — auth.py (hash_password / verify_password)
# ==============================================================================
from auth import hash_password, verify_password


class TestHashVerifyPassword:
    def test_round_trip_mot_de_passe_correct(self):
        stored = hash_password("MonSecret2026!")
        assert verify_password("MonSecret2026!", stored) is True

    def test_mot_de_passe_incorrect_refuse(self):
        stored = hash_password("MonSecret2026!")
        assert verify_password("MauvaisMotDePasse", stored) is False

    def test_hash_contient_sel_et_empreinte(self):
        stored = hash_password("abc")
        assert ":" in stored
        salt, h = stored.split(":", 1)
        assert len(salt) == 32          # secrets.token_hex(16) → 32 caractères hex
        assert len(h) == 64             # SHA-256 → 32 octets → 64 caractères hex

    def test_deux_hash_du_meme_mot_de_passe_different(self):
        # Sel aléatoire à chaque appel → jamais le même hash stocké deux fois
        assert hash_password("identique") != hash_password("identique")

    def test_verify_password_stored_invalide_ne_plante_pas(self):
        assert verify_password("abc", "pas-un-hash-valide") is False
        assert verify_password("abc", "") is False
