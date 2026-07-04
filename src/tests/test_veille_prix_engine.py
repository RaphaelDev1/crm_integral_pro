# ==============================================================================
#  TESTS — veille_prix_engine.py : parsing prix, CRUD sources, veille, alertes
# ==============================================================================
import veille_prix_engine as vpe
from offres_engine import ajouter_offre, lire_offres
from veille_prix_engine import (
    ajouter_source, extraire_prix, lancer_veille, lire_alertes, lire_historique_prix,
    lire_sources, maj_source, rejeter_alerte, supprimer_source, valider_alerte,
)


class TestExtrairePrix:
    def test_prix_avec_virgule(self):
        assert extraire_prix("Seulement 19,99 € par mois") == 19.99

    def test_prix_avec_point(self):
        assert extraire_prix("24.99€ engagement 0") == 24.99

    def test_prix_symbole_avant(self):
        assert extraire_prix("à partir de €13,99 / mois") == 13.99

    def test_aucun_prix_renvoie_none(self):
        assert extraire_prix("Offre indisponible pour le moment") is None

    def test_texte_vide_renvoie_none(self):
        assert extraire_prix("") is None
        assert extraire_prix(None) is None


def _source_de_base(offre_id=None):
    return {"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
            "nom_offre": "Forfait 350Go", "offre_id": offre_id,
            "url": "https://mobile.free.fr", "selecteur_prix": ".price"}


class TestSourcesCRUD:
    def test_ajouter_et_lire_source(self, tmp_db):
        sid = ajouter_source(_source_de_base())
        df = lire_sources()
        assert len(df) == 1
        assert df.iloc[0]["id"] == sid
        assert df.iloc[0]["actif"] == 1

    def test_maj_source(self, tmp_db):
        sid = ajouter_source(_source_de_base())
        maj_source(sid, "actif", 0)
        df = lire_sources()
        assert df.iloc[0]["actif"] == 0

    def test_supprimer_source(self, tmp_db):
        sid = ajouter_source(_source_de_base())
        supprimer_source(sid)
        assert lire_sources().empty


class TestLancerVeille:
    def test_premier_releve_ne_cree_pas_d_alerte(self, tmp_db, monkeypatch):
        ajouter_source(_source_de_base())
        monkeypatch.setattr(vpe, "scraper_source", lambda source: 19.99)
        alertes = lancer_veille()
        assert alertes == []
        df = lire_sources()
        assert df.iloc[0]["dernier_prix"] == 19.99
        hist = lire_historique_prix(int(df.iloc[0]["id"]))
        assert len(hist) == 1

    def test_changement_de_prix_cree_une_alerte(self, tmp_db, monkeypatch):
        ajouter_source(_source_de_base())
        prix_successifs = iter([19.99, 24.99])
        monkeypatch.setattr(vpe, "scraper_source", lambda source: next(prix_successifs))

        lancer_veille()
        alertes = lancer_veille()

        assert len(alertes) == 1
        assert alertes[0]["ancien_prix"] == 19.99
        assert alertes[0]["nouveau_prix"] == 24.99
        df_alertes = lire_alertes(statut="en_attente")
        assert len(df_alertes) == 1

    def test_prix_inchange_ne_cree_pas_d_alerte(self, tmp_db, monkeypatch):
        ajouter_source(_source_de_base())
        monkeypatch.setattr(vpe, "scraper_source", lambda source: 19.99)
        lancer_veille()
        alertes = lancer_veille()
        assert alertes == []

    def test_scraper_echoue_ignore_la_source(self, tmp_db, monkeypatch):
        ajouter_source(_source_de_base())
        monkeypatch.setattr(vpe, "scraper_source", lambda source: None)
        alertes = lancer_veille()
        assert alertes == []
        assert lire_historique_prix(1).empty


class TestValidationAlertes:
    def _creer_alerte(self, tmp_db, monkeypatch, offre_id):
        ajouter_source(_source_de_base(offre_id=offre_id))
        prix_successifs = iter([19.99, 24.99])
        monkeypatch.setattr(vpe, "scraper_source", lambda source: next(prix_successifs))
        lancer_veille()
        lancer_veille()
        return lire_alertes(statut="en_attente").iloc[0]["id"]

    def test_valider_alerte_met_a_jour_le_catalogue(self, tmp_db, monkeypatch):
        ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
                       "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99})
        offre_id = int(lire_offres(actif_seulement=False).iloc[0]["id"])
        alerte_id = self._creer_alerte(tmp_db, monkeypatch, offre_id)

        ok, msg = valider_alerte(int(alerte_id))
        assert ok
        df_o = lire_offres(actif_seulement=False)
        assert df_o.iloc[0]["prix_mensuel"] == 24.99
        assert lire_alertes(statut="en_attente").empty

    def test_rejeter_alerte_ne_touche_pas_au_catalogue(self, tmp_db, monkeypatch):
        ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
                       "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99})
        offre_id = int(lire_offres(actif_seulement=False).iloc[0]["id"])
        alerte_id = self._creer_alerte(tmp_db, monkeypatch, offre_id)

        rejeter_alerte(int(alerte_id))
        df_o = lire_offres(actif_seulement=False)
        assert df_o.iloc[0]["prix_mensuel"] == 19.99
        assert lire_alertes(statut="en_attente").empty

    def test_valider_alerte_deja_traitee_echoue(self, tmp_db, monkeypatch):
        alerte_id = self._creer_alerte(tmp_db, monkeypatch, offre_id=None)
        rejeter_alerte(int(alerte_id))
        ok, msg = valider_alerte(int(alerte_id))
        assert not ok
