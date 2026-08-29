# Retargeting Meta + TikTok — audience "visiteurs landing 30j"

Guide de config pour récupérer les 90 % de visiteurs de `/economiser` qui ne
convertissent pas au premier passage. Les pixels sont déjà posés côté code
(`frontend-portail/lib/pixels.tsx`, monté via `<PixelsHead />` dans
`app/economiser/page.tsx`) — il ne reste qu'à créer les audiences côté
plateformes pub. ~30 min au total.

Événements déjà émis par la landing (voir `EstimationForm.tsx`) :

| Événement          | Déclenché quand                                   |
|---------------------|----------------------------------------------------|
| `PageView`          | arrivée sur `/economiser`                           |
| `Lead`              | estimation calculée avec succès (fin étape 3)       |
| `CompleteRegistration` | idem, en parallèle (utile pour du bidding séparé) |

Prérequis : `NEXT_PUBLIC_META_PIXEL_ID` et `NEXT_PUBLIC_TIKTOK_PIXEL_ID`
renseignés dans `frontend-portail/.env` (sinon les scripts ne se chargent
pas, voir `pixels.tsx`).

## 1. Meta Business Manager (Facebook + Instagram)

1. **Vérifier que le pixel reçoit des events** : Gestionnaire d'événements
   → sélectionner le pixel → onglet *Test des événements* → ouvrir
   `/economiser` en navigation privée → confirmer `PageView` puis `Lead`.
2. **Créer l'audience personnalisée** : Audiences → Créer une audience →
   Audience personnalisée → *Site web*.
   - Événement : `PageView` (tous les visiteurs) — ou `Lead` exclu pour ne
     cibler que les non-convertis (voir étape 3).
   - Durée de rétention : **30 jours**.
   - Nom : `LP-economiser-visiteurs-30j`.
3. **Exclure les convertis** (recommandé — évite de payer pour reharceler
   des gens déjà rappelés) : dans la même audience, ajouter une règle
   d'exclusion `CompleteRegistration` sur les 30 derniers jours. Nom :
   `LP-economiser-visiteurs-30j-non-convertis`.
4. **Créer la campagne de retargeting** : nouvelle campagne → objectif
   *Prospects* ou *Conversions* → ensemble de publicités → Audience
   personnalisée = celle créée à l'étape 3. Budget conseillé pour démarrer :
   5-10 €/jour, créatif orienté urgence/réassurance ("Toujours envie
   d'économiser sur vos abonnements ?").
5. *(Optionnel, phase 2)* Audience similaire (Lookalike 1 %) basée sur
   `Lead` une fois qu'on a >100 conversions cumulées — meilleure qualité
   d'acquisition froide que le ciblage par intérêts.

## 2. TikTok Ads Manager

1. **Vérifier la réception d'events** : TikTok Ads Manager → Bibliothèque
   d'actifs → Events → sélectionner le pixel → *Test d'événements* → même
   procédure qu'au-dessus.
2. **Créer l'audience personnalisée** : Bibliothèque d'actifs → Audiences →
   Créer une audience → Trafic du site web.
   - Règle : `PageView` sur `/economiser`, fenêtre **30 jours**.
   - Nom : `LP-economiser-visiteurs-30j`.
3. **Exclure les convertis** : dupliquer avec une règle combinée
   (`PageView` ET NON `CompleteRegistration`), fenêtre 30 jours. Nom :
   `LP-economiser-visiteurs-30j-non-convertis`.
4. **Créer la campagne** : objectif *Génération de prospects* ou
   *Conversions* → groupe d'annonces → Audience personnalisée = celle
   créée à l'étape 3. Format recommandé : vidéo courte (15-30s) format
   témoignage/avant-après économie réalisée.

## 3. Suivi

- Revoir la taille des audiences après 48h (Meta/TikTok ont besoin d'un
  minimum d'utilisateurs, généralement >1000, pour livrer correctement le
  ciblage — sous ce seuil, élargir la fenêtre à 60-90 jours temporairement).
- CAC attendu sur le retargeting : généralement **divisé par 2 à 3** par
  rapport à l'acquisition froide (source : bibliothèques de benchmarks Meta
  Ads Library / TikTok Creative Center, comparables cold vs retargeting).
- Ne pas laisser tourner une audience de retargeting sans plafond de
  fréquence — au-delà de ~5 impressions/semaine/utilisateur, le rendement
  marginal chute et la lassitude créative augmente le taux de "masquer la
  pub".
