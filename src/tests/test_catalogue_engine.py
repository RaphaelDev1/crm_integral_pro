# ==============================================================================
#  TESTS — catalogue_engine.py : CRUD sources, ingestion, dédoublonnage, validation
# ==============================================================================
import pandas as pd

import catalogue_engine as ce
from offres_engine import ajouter_offre, lire_offres
from catalogue_engine import (
    ajouter_source_catalogue, hash_contenu, ingerer_source, lire_offres_staging,
    lire_sources_catalogue, maj_source_catalogue, rejeter_offre_staging,
    supprimer_source_catalogue, valider_offre_staging,
)


def _source_de_base():
    return {"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
            "url": "https://mobile.free.fr", "type_source": "page_officielle", "methode": "requests"}


def _offre_llm(fournisseur="Free", nom="Forfait 350Go", prix=19.99, engagement=0):
    return {"fournisseur": fournisseur, "nom_offre": nom, "univers": "Télécom", "categorie": "Mobile",
            "prix_mensuel": prix, "frais_activation": 0, "engagement_mois": engagement, "data_go": 350,
            "caracteristiques": "350 Go 5G", "url_souscription": "", "confiance": 0.9, "champs_incertains": []}


class TestSourcesCRUD:
    def test_ajouter_et_lire_source(self, tmp_db, monkeypatch):
        monkeypatch.setattr(ce, "verifier_robots", lambda url: True)
        sid = ajouter_source_catalogue(_source_de_base())
        df = lire_sources_catalogue()
        assert len(df) == 1
        assert df.iloc[0]["id"] == sid
        assert df.iloc[0]["actif"] == 1
        assert df.iloc[0]["robots_ok"] == 1

    def test_robots_interdit_stocke(self, tmp_db, monkeypatch):
        monkeypatch.setattr(ce, "verifier_robots", lambda url: False)
        ajouter_source_catalogue(_source_de_base())
        df = lire_sources_catalogue()
        assert df.iloc[0]["robots_ok"] == 0

    def test_maj_source(self, tmp_db, monkeypatch):
        monkeypatch.setattr(ce, "verifier_robots", lambda url: True)
        sid = ajouter_source_catalogue(_source_de_base())
        maj_source_catalogue(sid, "actif", 0)
        assert lire_sources_catalogue().iloc[0]["actif"] == 0

    def test_supprimer_source(self, tmp_db, monkeypatch):
        monkeypatch.setattr(ce, "verifier_robots", lambda url: True)
        sid = ajouter_source_catalogue(_source_de_base())
        supprimer_source_catalogue(sid)
        assert lire_sources_catalogue().empty


class TestHashContenu:
    def test_hash_stable(self):
        o = {"fournisseur": "Free", "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99, "engagement_mois": 0}
        assert hash_contenu(o) == hash_contenu(dict(o))

    def test_hash_insensible_casse_accents(self):
        o1 = {"fournisseur": "Free", "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99, "engagement_mois": 0}
        o2 = {"fournisseur": "FREE", "nom_offre": "forfait 350go", "prix_mensuel": 19.99, "engagement_mois": 0}
        assert hash_contenu(o1) == hash_contenu(o2)

    def test_hash_different_si_prix_different(self):
        o1 = {"fournisseur": "Free", "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99, "engagement_mois": 0}
        o2 = {"fournisseur": "Free", "nom_offre": "Forfait 350Go", "prix_mensuel": 24.99, "engagement_mois": 0}
        assert hash_contenu(o1) != hash_contenu(o2)


class TestIngestion:
    def _creer_source(self, monkeypatch):
        monkeypatch.setattr(ce, "verifier_robots", lambda url: True)
        return ajouter_source_catalogue(_source_de_base())

    def test_offre_sans_prix_part_en_a_verifier(self, tmp_db, monkeypatch):
        sid = self._creer_source(monkeypatch)
        monkeypatch.setattr(ce, "_recuperer_page", lambda url, methode="requests": "<html>page</html>")
        offre_sans_prix = _offre_llm(prix=None)
        monkeypatch.setattr(ce, "extraire_offres_llm", lambda texte, source, api_key="", model=None: [offre_sans_prix])

        resume = ingerer_source(sid)

        assert resume["a_verifier"] == 1
        assert resume["detectees"] == 0
        df_stg = lire_offres_staging(statut="a_verifier")
        assert len(df_stg) == 1
        assert pd.isna(df_stg.iloc[0]["prix_mensuel"])

    def test_nouvelle_offre_part_en_attente(self, tmp_db, monkeypatch):
        sid = self._creer_source(monkeypatch)
        monkeypatch.setattr(ce, "_recuperer_page", lambda url, methode="requests": "<html>page</html>")
        monkeypatch.setattr(ce, "extraire_offres_llm", lambda texte, source, api_key="", model=None: [_offre_llm()])

        resume = ingerer_source(sid)

        assert resume["detectees"] == 1
        df_stg = lire_offres_staging(statut="en_attente")
        assert len(df_stg) == 1
        assert df_stg.iloc[0]["fournisseur"] == "Free"
        assert pd.isna(df_stg.iloc[0]["offre_existante_id"])

    def test_deuxieme_ingestion_identique_ne_cree_pas_de_doublon(self, tmp_db, monkeypatch):
        sid = self._creer_source(monkeypatch)
        monkeypatch.setattr(ce, "_recuperer_page", lambda url, methode="requests": "<html>page</html>")
        monkeypatch.setattr(ce, "extraire_offres_llm", lambda texte, source, api_key="", model=None: [_offre_llm()])

        ingerer_source(sid)
        resume2 = ingerer_source(sid)

        assert resume2["doublons"] == 1
        assert resume2["detectees"] == 0
        assert len(lire_offres_staging(statut="en_attente")) == 1

    def test_prix_different_d_une_offre_existante_cree_un_changement(self, tmp_db, monkeypatch):
        sid = self._creer_source(monkeypatch)
        ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
                       "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99})
        monkeypatch.setattr(ce, "_recuperer_page", lambda url, methode="requests": "<html>page</html>")
        monkeypatch.setattr(ce, "extraire_offres_llm",
                             lambda texte, source, api_key="", model=None: [_offre_llm(prix=24.99)])

        resume = ingerer_source(sid)

        assert resume["changements"] == 1
        assert resume["detectees"] == 0
        df_stg = lire_offres_staging(statut="en_attente")
        assert len(df_stg) == 1
        assert not pd.isna(df_stg.iloc[0]["offre_existante_id"])

    def test_prix_identique_a_une_offre_existante_est_un_doublon(self, tmp_db, monkeypatch):
        sid = self._creer_source(monkeypatch)
        ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
                       "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99})
        monkeypatch.setattr(ce, "_recuperer_page", lambda url, methode="requests": "<html>page</html>")
        monkeypatch.setattr(ce, "extraire_offres_llm",
                             lambda texte, source, api_key="", model=None: [_offre_llm(prix=19.99)])

        resume = ingerer_source(sid)

        assert resume["doublons"] == 1
        assert lire_offres_staging(statut="en_attente").empty

    def test_fetch_echoue_ne_cree_rien(self, tmp_db, monkeypatch):
        sid = self._creer_source(monkeypatch)
        monkeypatch.setattr(ce, "_recuperer_page", lambda url, methode="requests": None)
        resume = ingerer_source(sid)
        assert resume == {"detectees": 0, "doublons": 0, "a_verifier": 0, "changements": 0}

    def test_robots_interdit_ignore_la_source(self, tmp_db, monkeypatch):
        monkeypatch.setattr(ce, "verifier_robots", lambda url: False)
        sid = ajouter_source_catalogue(_source_de_base())
        appelle = {"fait": False}

        def _fake_fetch(url, methode="requests"):
            appelle["fait"] = True
            return "<html>page</html>"
        monkeypatch.setattr(ce, "_recuperer_page", _fake_fetch)

        resume = ingerer_source(sid)

        assert not appelle["fait"]
        assert resume == {"detectees": 0, "doublons": 0, "a_verifier": 0, "changements": 0}


class TestValidationStaging:
    def _detecter_nouvelle_offre(self, tmp_db, monkeypatch):
        monkeypatch.setattr(ce, "verifier_robots", lambda url: True)
        sid = ajouter_source_catalogue(_source_de_base())
        monkeypatch.setattr(ce, "_recuperer_page", lambda url, methode="requests": "<html>page</html>")
        monkeypatch.setattr(ce, "extraire_offres_llm", lambda texte, source, api_key="", model=None: [_offre_llm()])
        ingerer_source(sid)
        return int(lire_offres_staging(statut="en_attente").iloc[0]["id"])

    def test_valider_nouvelle_offre_l_ajoute_au_catalogue(self, tmp_db, monkeypatch):
        staging_id = self._detecter_nouvelle_offre(tmp_db, monkeypatch)
        ok, msg = valider_offre_staging(staging_id, "Test Admin")
        assert ok
        df_o = lire_offres(actif_seulement=False)
        assert len(df_o) == 1
        assert df_o.iloc[0]["fournisseur"] == "Free"
        assert lire_offres_staging(statut="en_attente").empty

    def test_valider_changement_met_a_jour_le_prix_existant(self, tmp_db, monkeypatch):
        monkeypatch.setattr(ce, "verifier_robots", lambda url: True)
        sid = ajouter_source_catalogue(_source_de_base())
        ajouter_offre({"univers": "Télécom", "categorie": "Mobile", "fournisseur": "Free",
                       "nom_offre": "Forfait 350Go", "prix_mensuel": 19.99})
        monkeypatch.setattr(ce, "_recuperer_page", lambda url, methode="requests": "<html>page</html>")
        monkeypatch.setattr(ce, "extraire_offres_llm",
                             lambda texte, source, api_key="", model=None: [_offre_llm(prix=24.99)])
        ingerer_source(sid)
        staging_id = int(lire_offres_staging(statut="en_attente").iloc[0]["id"])

        ok, msg = valider_offre_staging(staging_id)

        assert ok
        df_o = lire_offres(actif_seulement=False)
        assert len(df_o) == 1
        assert df_o.iloc[0]["prix_mensuel"] == 24.99

    def test_rejeter_offre_ne_touche_pas_au_catalogue(self, tmp_db, monkeypatch):
        staging_id = self._detecter_nouvelle_offre(tmp_db, monkeypatch)
        rejeter_offre_staging(staging_id)
        assert lire_offres(actif_seulement=False).empty
        assert lire_offres_staging(statut="en_attente").empty

    def test_valider_offre_deja_traitee_echoue(self, tmp_db, monkeypatch):
        staging_id = self._detecter_nouvelle_offre(tmp_db, monkeypatch)
        rejeter_offre_staging(staging_id)
        ok, msg = valider_offre_staging(staging_id)
        assert not ok
