# Checklist avant chaque commit

- [ ] `streamlit run src/app.py` démarre sans erreur.
- [ ] Le flux critique testé manuellement : connexion → tableau de bord →
      nouveau diagnostic → prospects/clients.
- [ ] Toute nouvelle colonne BDD est présente dans **et**
      `initialiser_bdd()` **et** `_migrer_bdd()` (docs/DATABASE.md à jour).
- [ ] Toute colonne éditable via un formulaire est ajoutée au bon
      ensemble `CHAMPS_*` (sinon la mise à jour sera silencieusement
      refusée ou vulnérable).
- [ ] Aucune valeur dynamique concaténée directement dans une requête SQL
      (paramétrage `?` uniquement).
- [ ] Aucun secret (mot de passe SMTP, token) commité en dur — vérifier
      qu'il ne traîne pas dans le code ou dans `src/ia_conseil_crm.db`
      versionné par erreur.
- [ ] `st.rerun()` présent après toute mutation qui doit rafraîchir
      l'écran (création/suppression/conversion prospect-client).
- [ ] `docs/CHANGELOG.md` mis à jour si le changement est visible pour
      un utilisateur (nouvelle page, nouveau champ, comportement modifié).
- [ ] `docs/ARCHITECTURE.md` mis à jour si une section du fichier a été
      ajoutée/déplacée/renommée.
