# QUESTIONS PAR SECTEUR — TRAME ADAPTATIVE ESCARGOT

> **Règle absolue** : ne poser une question **QUE SI** sa réponse peut changer la recommandation. Si toutes les offres restantes donnent le même verdict → **STOP**, on passe au récap.
> Ordre suivi : questions à fort pouvoir de filtrage d'abord, questions "confort" jamais.

---

## 🧩 SOCLE COMMUN (à poser UNE SEULE FOIS par client, réutilisé pour tous secteurs)

| # | Question | Utilisé par |
|---|----------|-------------|
| S1 | Code postal + ville (adresse précise si box/énergie) | Box, Énergie, Mobile (couverture) |
| S2 | Type de logement : appart / maison — surface m² | Énergie, Box |
| S3 | Propriétaire ou locataire | Assurance hab (futur), Énergie (travaux) |
| S4 | Composition du foyer : nb adultes + nb enfants (+ âges enfants) | Mobile (multi-lignes), Streaming |
| S5 | Objectif principal : ① économiser ② simplifier ③ améliorer qualité ④ regrouper | Pondération scoring |
| S6 | Budget total actuel toutes dépenses récurrentes (€/mois) | Priorisation postes |

**Temps de saisie socle : 90 secondes max.** Ensuite, on entre dans la trame du secteur choisi.

---

# 📱 SECTEUR 1 — MOBILE

### 🎯 Objectif : audit complet en 6-8 questions max

### Questions socles secteur (toujours posées)

**M1. Combien de lignes mobiles à optimiser ?**
- `1 seule` → aller M2
- `2+` → poser **M1a** : *Toutes chez le même opérateur ?* — puis M2

**M2. Opérateur actuel + prix mensuel de la ligne ?**
- Note : si multi-lignes, demander prix total.
- ⚠️ Si prix < 8€ → prévenir : *"Vous êtes déjà très optimisé, vérifions juste que vous avez ce qu'il faut."*

**M3. Consommation data moyenne des 3 derniers mois ? (regarder facture ou app opérateur)**
- 🔴 **Question la plus importante** — filtre 60% du catalogue à elle seule.
- Réponse `< 5 Go` → **SKIP M6, M7** (5G, partage connexion inutiles) → aller M4
- Réponse `5-30 Go` → aller M4
- Réponse `30-100 Go` → aller M4
- Réponse `> 100 Go` → poser **M3a** : *Vous partagez votre connexion mobile pour votre domicile ?* — si OUI, orienter vers box 4G (cross-sell)

**M4. Voyages à l'étranger ?**
- `Jamais` → **SKIP** toute la branche roaming → aller M5
- `UE occasionnel/fréquent` → **SKIP M4a** (hors UE)
- `Hors UE occasionnel/fréquent` → poser **M4a** : *Quelles zones ? Combien de fois par an ?*

**M5. Qualité réseau à votre domicile et au travail ?**
- `Bonne partout` → poursuivre normalement
- `Moyenne ou mauvaise à un endroit` → **PRIORITÉ CHANGÉE** : le prix devient secondaire, on filtre par couverture opérateur à cette adresse (croiser avec ARCEP)

### Questions conditionnelles (posées SEULEMENT si pertinent)

**M6.** *(uniquement si data > 30 Go OU réponse M3a = OUI)*
Utilisez-vous la 5G ? Votre téléphone est-il compatible 5G ?
- Sinon → filtrer offres pour ne PAS payer d'option 5G inutile.

**M7.** *(uniquement si data > 50 Go)*
Partagez-vous souvent votre connexion (tethering) ?
- OUI → forfait avec option partage illimitée.

**M8. Sous engagement actuel ? Jusqu'à quand ?**
- Toujours poser en dernier — n'influence pas la reco, seulement le timing de switch.

**M9.** *(uniquement si M2 révèle prix > 20€/mois)*
Le téléphone est-il inclus dans votre forfait actuel ? Reste-t-il des mensualités ?
- Détecter subvention mobile masquée dans le prix.

### 🛑 STOP RULE
Le moteur arrête la trame dès que :
- Le top 3 des offres candidates est stable (les mêmes offres depuis 2 questions)
- ET l'écart de prix entre l'offre #1 et l'offre #4 est > 3€/mois (marge de sécurité)

### 📊 Sortie d'audit
- Forfait actuel : X €/mois pour Y Go réellement utilisés
- 3 offres recommandées avec justification
- Économie annuelle : Z €
- Timing conseillé pour le switch

---

# 🌐 SECTEUR 2 — BOX INTERNET / TV

### 🎯 Objectif : audit complet en 5-7 questions max

### Questions socles secteur

**B1. Fibre disponible à votre adresse ?**
- *(à vérifier automatiquement via API adresse.data.gouv + ARCEP maObservatoire)*
- `OUI fibre dispo` → poursuivre B2
- `NON, uniquement ADSL/VDSL` → **BRANCHE ALTERNATIVE B1-bis**
- `Zone 4G/5G couverte mais ADSL très faible` → **PRIORISER box 4G/5G**

**B1-bis (si pas de fibre).** Quel débit ADSL constaté au speedtest ?
- `< 8 Mbps` → recommander box 4G/5G (souvent meilleur + moins cher)
- `> 20 Mbps` → ADSL suffit pour usage modéré

**B2. Opérateur actuel + prix mensuel ?**

**B3. Regardez-vous la TV via la box ? (chaînes TNT + chaînes payantes du bouquet)**
- 🔴 **Question critique anti-survente**
- `Jamais, uniquement streaming` → **SKIP B3a, B3b** → filtrer offres SANS TV (économie 5-15€/mois)
- `Oui, quelques chaînes` → poser **B3a** : *Lesquelles précisément ?* → comparer coût box+TV vs box nue + OTT direct
- `Oui, bouquet premium (Canal+, beIN, etc.)` → poser **B3b** : *Quels abonnements payants en plus ?*

**B4. Nombre d'utilisateurs simultanés en streaming ? Vidéo 4K ?**
- `1-2 personnes, HD` → 100-200 Mbps suffit
- `3+ personnes ou 4K` → 500 Mbps+
- `Console/gaming en ligne` → priorité au ping/latence

**B5. Télétravail ? Fréquence des visios ?**
- `Non` → skip
- `Oui régulièrement` → besoin upload minimum 200 Mbps → filtrer fibre symétrique

### Questions conditionnelles

**B6.** *(si M3 mobile > 100 Go OU si résidence secondaire mentionnée)*
Une box 4G/5G pourrait-elle remplacer votre box actuelle ?

**B7.** *(uniquement si le client a un téléphone fixe et l'utilise)*
Combien d'appels fixes par mois ? Vers l'international ?
- Si `0 appel` → forfait sans fixe (souvent -3€/mois)

**B8. Sous engagement ? Jusqu'à quand ?**
- En dernier, pour le timing.

### 🛑 STOP RULE
- Éligibilité technique (fibre/ADSL/4G) est fixée
- Usage TV clarifié
- Débit nécessaire calculé
- Top 3 stable
→ Audit possible.

### 📊 Sortie d'audit
- Situation actuelle vs offre optimale
- TV : garder / supprimer (avec alternatives OTT si applicable)
- Économie annuelle
- Frais de résiliation vs économie sur 24 mois

---

# ⚡ SECTEUR 3 — ÉNERGIE (ÉLECTRICITÉ + GAZ)

### 🎯 Objectif : audit complet en 6-9 questions max (plus long car deux énergies possibles)

### Questions socles secteur

**E1. Chauffage principal du logement ?**
- 🔴 **Question clé** : détermine tout le reste.
- `Électrique (convecteurs, radiants, PAC)` → **branche ELEC SEULE**
- `Gaz` → **branche ELEC + GAZ**
- `Bois / fioul / pompe à chaleur air-eau` → **branche ELEC + AUXILIAIRE**
- `Chauffage collectif inclus dans charges` → **SKIP tout le volet chauffage** → conso élec basse attendue

**E2. Eau chaude sanitaire : électrique ou gaz ?**
- *(inutile de re-demander si déjà déduit de E1)*

**E3. Cuisson : électrique/induction ou gaz ?**
- Uniquement si E1 = gaz (savoir si résilier gaz possible en passant à plaques induction)

**E4. Consommation annuelle (kWh) — élec + gaz séparés**
- 🔴 À lire sur la facture. Si le client ne l'a pas → estimer via surface + composition foyer + type chauffage (utiliser barème INSEE).
- Réponse permet immédiatement de :
  - Détecter sur/sous-consommation vs profil type
  - Filtrer offres au bon segment tarifaire

**E5. Puissance souscrite (kVA) — sur facture, cadre en haut**
- `3 kVA` → très petit logement
- `6 kVA` → standard, généralement OK
- `9 kVA` → poser **E5a** : *Avez-vous une clim, une piscine, un véhicule électrique, ou des plaques induction puissantes ?*
  - Si NON → **RECOMMANDATION FORTE** : baisser à 6 kVA (économie 40-80€/an)
- `12 kVA+` → même logique

**E6. Option tarifaire actuelle : Base / Heures Pleines-Creuses / Tempo ?**
- Croiser avec E7 pour recommander.

**E7. Y a-t-il des gros consommateurs pilotables la nuit ?**
- Chauffe-eau, VE en charge, chauffage électrique programmable ?
- `OUI` → HP/HC ou Tempo peuvent être très rentables
- `NON, tout est utilisé le jour` → rester en Base (HP/HC coûte + cher)

### Questions conditionnelles

**E8.** *(uniquement si sensibilité écologique déclarée au socle)*
Souhaitez-vous une électricité 100% renouvelable certifiée ?
- Filtre le catalogue vers Enercoop, Ilek, Planète Oui (prévenir : +5 à 15%).

**E9.** *(uniquement si conso élec > 15 000 kWh/an dans une maison)*
Votre logement est-il bien isolé ? Année de construction ? DPE ?
- Cross-sell rénovation énergétique (MaPrimeRénov, CEE).

**E10. Fournisseur actuel + prix du kWh + prix de l'abonnement + prix total mensuel**

**E11. Sous engagement ? Prix fixé/indexé ? Durée restante ?**
- ⚠️ Certaines offres prix fixe long terme sont piégeuses si le marché baisse.

### 🛑 STOP RULE
Le moteur arrête dès que :
- Type d'énergie(s) clarifié (élec seule vs élec+gaz)
- Consommation quantifiée (facture ou estimation)
- Puissance validée ou correction identifiée
- Profil HP/HC vs Base décidé
- Sensibilité verte connue
→ Le catalogue est filtré, audit possible.

### 📊 Sortie d'audit
- Consommation actuelle vs profil type INSEE (sur/sous-consommation ?)
- Puissance à ajuster ? Économie immédiate ?
- Option tarifaire optimale
- Top 3 fournisseurs avec justification (prix / verdissement / stabilité)
- Économie annuelle
- Cross-sell éventuel : isolation, VE, panneaux solaires

---

# 🎛️ RÈGLES DE FONCTIONNEMENT GLOBAL

### Ordre recommandé sur un rendez-vous complet
1. **Socle client (S1-S6)** : 90 sec
2. **Secteur choisi par le client** (celui qui l'intéresse le plus) : ~5 min
3. **Autres secteurs** : le moteur pré-remplit à partir du socle → ne pose que 3-4 questions supplémentaires par secteur
4. **Cross-sell** en fin de session (10 sec par suggestion)

### Bouton "Creuser" à chaque étape
Le conseiller peut à tout moment forcer une question skippée si le client veut affiner. Ex : *"Le client dit qu'il n'a pas besoin de TV mais hésite → je pose quand même B3a pour le rassurer."*

### Bouton "Terminer maintenant"
Si le client presse ou refuse une question sensible, le conseiller termine l'audit avec les infos déjà collectées. Le moteur signale visuellement les recommandations "à confirmer" (moins précises car données manquantes).

### Questions **INTERDITES** (à ne JAMAIS poser)
- Revenus exacts (sauf éligibilité LEP énergie/santé Phase 2+)
- Historique bancaire détaillé
- Informations médicales
- Toute donnée non strictement nécessaire à l'audit

### Formulation cliente-friendly
- ❌ "Quelle est votre consommation data mensuelle en gigaoctets ?"
- ✅ "Sur votre facture mobile, ligne 'consommation data', c'est quoi en moyenne sur les 3 derniers mois ?"

Toujours donner **où trouver l'info** dans la question.

---

# 🧪 TESTS DE VALIDATION DE LA TRAME

Pour vérifier que le principe escargot fonctionne bien, tester sur 5 profils extrêmes :

| Profil | Nb questions attendues | Économie attendue détectée |
|--------|-----------------------|---------------------------|
| Étudiant, appart 20m², forfait 30€/mois pour 3 Go conso, pas de box | Mobile : 4 | Oui : forfait 5€ |
| Famille 4 pers, maison 130m², chauffage élec, box+TV Orange 60€, 4 mobiles Orange | Mobile : 5, Box : 6, Élec : 7 | Oui : convergent ou séparé + offre sans TV |
| Sénior 70 ans, appart 60m², chauffage gaz, box SFR 40€ pour Molotov uniquement, mobile Free 20€ | Mobile : 3, Box : 5, Élec+Gaz : 8 | Oui : box sans TV, forfait low-cost |
| Freelance télétravail, maison, VE chargeable, gros consommateur data | Mobile : 6, Box : 6, Élec : 8 | Oui : fibre symétrique + HP/HC ou Tempo |
| Résidence secondaire vide 8 mois/an | Mobile : 2, Box : 4, Élec : 6 | Oui : box 4G sans engagement + abo élec réduit |

Si un profil dépasse 10 questions par secteur → règle défaillante, refactorer.
