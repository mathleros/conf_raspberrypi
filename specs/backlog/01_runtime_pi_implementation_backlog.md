# Backlog — Passage au robot réel (Raspberry Pi)

## Objectif
Rendre exécutable sur robot réel la chaîne complète :
Commande naturelle -> plan LLM validé -> skills -> actions matérielles -> retour d'état sûr.

## Priorité globale
M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7

---

## M1 — Intégration moteur réelle
**But** : relier les primitives aux moteurs réels et calibrer les mouvements.
**Estimation** : 3 à 5 jours.

### Ticket M1.1 — Câblage logique `RobotController` -> driver moteur
- **Description** : brancher `forward/backward/left/right/stop` sur le backend matériel réel.
- **Livrables** : implémentation stable + logs d'exécution.
- **DoD** : commandes exécutées sans crash sur 10 runs.

### Ticket M1.2 — Calibration déplacement/rotation
- **Description** : convertir distance et angle en durées réalistes selon la base roulante.
- **Livrables** : constantes de calibration documentées.
- **DoD** : erreur moyenne < 20% sur distance/angle de test.

### Ticket M1.3 — Config de calibration
- **Description** : stocker les constantes dans configuration versionnée.
- **Livrables** : paramètres chargés au runtime.
- **DoD** : changement de config sans modifier le code métier.

---

## M2 — Perception caméra réelle
**But** : remplacer les mocks par une perception objet live.
**Estimation** : 4 à 6 jours.

### Ticket M2.1 — Détection objet live
- **Description** : produire `last_object_position` (`left/center/right/unknown`) en continu.
- **Livrables** : service perception branché à `DetectObjectSkill`.
- **DoD** : latence stable et état mis à jour en boucle.

### Ticket M2.2 — Proximité cible
- **Description** : définir un critère "close enough" pour l'approche.
- **Livrables** : seuil(s) en config + signal d'arrêt d'approche.
- **DoD** : arrêt cohérent sur 3 scénarios de distance.

### Ticket M2.3 — Gestion perte de cible
- **Description** : stratégie claire si la cible disparaît.
- **Livrables** : transition d'état robuste.
- **DoD** : pas de mouvement erratique en cas de perte.

---

## M3 — Boucle fermée "chercher + approcher"
**But** : réaliser une mission autonome de recherche et approche.
**Estimation** : 3 à 5 jours.

### Ticket M3.1 — Boucle de contrôle mission
- **Description** : `detect -> align -> approach -> re-detect` avec transitions explicites.
- **Livrables** : logique de boucle testable.
- **DoD** : mission complète réussie 3 fois de suite.

### Ticket M3.2 — Retry et timeout mission
- **Description** : retries bornés + timeout global + sortie contrôlée.
- **Livrables** : paramètres `max_retry`, `mission_timeout`.
- **DoD** : aucune boucle infinie.

### Ticket M3.3 — Conditions de fin de mission
- **Description** : succès, abandon, échec explicitement codifiés.
- **Livrables** : statuts finaux homogènes.
- **DoD** : logs exploitables pour chaque fin.

---

## M4 — Sécurité runtime
**But** : garantir l'arrêt sûr en cas de risque.
**Estimation** : 2 à 4 jours.

### Ticket M4.1 — Priorité obstacle
- **Description** : obstacle critique > toute autre action.
- **Livrables** : interruption de plan en cours + `stop`.
- **DoD** : arrêt immédiat validé en tests.

### Ticket M4.2 — Watchdog logiciel
- **Description** : timeout par étape + timeout global + kill-safe.
- **Livrables** : watchdog intégré au runtime.
- **DoD** : arrêt fiable si blocage/perte de contrôle.

### Ticket M4.3 — Bornage strict des paramètres
- **Description** : appliquer limites distance/angle/durée/steps côté exécution.
- **Livrables** : validation stricte centralisée.
- **DoD** : paramètres hors bornes rejetés avec raison explicite.

---

## M5 — Robustesse plan LLM
**But** : exécuter uniquement des plans sûrs et traçables.
**Estimation** : 2 à 3 jours.

### Ticket M5.1 — Validation complète de plan
- **Description** : valider chaque étape avant exécution réelle.
- **Livrables** : pipeline de validation unifié.
- **DoD** : action non whitelistée impossible à exécuter.

### Ticket M5.2 — Traçabilité complète
- **Description** : log commande brute, plan brut, plan normalisé, actions exécutées.
- **Livrables** : format de logs stable.
- **DoD** : diagnostic possible sans reproduire à l'identique.

### Ticket M5.3 — Fallback parser local
- **Description** : fallback si réponse LLM invalide/absente.
- **Livrables** : chemin de dégradation opérationnel.
- **DoD** : pas de crash si LLM indisponible.

---

## M6 — Tests d'intégration Raspberry Pi
**But** : valider les scénarios réels de bout en bout.
**Estimation** : 3 à 5 jours.

### Ticket M6.1 — Scénarios standard
- **Description** : avance, rotation, recherche+approche, obstacle soudain.
- **Livrables** : protocole de test reproductible.
- **DoD** : 3 runs passants par scénario.

### Ticket M6.2 — Mesures et tolérances
- **Description** : mesurer écart distance/angle/temps et définir tolérances.
- **Livrables** : tableau de résultats.
- **DoD** : tolérances validées et documentées.

### Ticket M6.3 — Rapport d'intégration
- **Description** : formaliser pass/fail et causes de défaut.
- **Livrables** : rapport markdown versionné.
- **DoD** : décision go/no-go possible.

---

## M7 — Exploitation terrain
**But** : permettre un run simple et diagnostiquer vite.
**Estimation** : 2 à 3 jours.

### Ticket M7.1 — Commande unique de mission
- **Description** : script unique de démarrage mission sur Pi.
- **Livrables** : commande documentée.
- **DoD** : lancement en une commande.

### Ticket M7.2 — Check-list pré-run
- **Description** : capteurs, caméra, moteurs, batterie, endpoint LLM.
- **Livrables** : check-list opérateur.
- **DoD** : blocage explicite si prérequis manquants.

### Ticket M7.3 — Logs + replay
- **Description** : logs horodatés et replay simple des commandes.
- **Livrables** : utilitaire minimal de replay.
- **DoD** : reproduction partielle d'un incident possible.

---

## Définition de prêt (Go test réel)
Le système est prêt à être testé en conditions réelles si :
1. primitives moteur calibrées et reproductibles,
2. perception objet réelle active (sans mock),
3. mission `search_and_approach_object` passe 3 fois de suite,
4. arrêt obstacle validé,
5. logs complets exploitables.

---

## Template de ticket (copiable)

### [ID] Titre
- **Milestone** : Mx
- **Priorité** : High / Medium / Low
- **Description** :
- **Changements attendus** :
- **Dépendances** :
- **Risques** :
- **Tests à exécuter** :
- **Definition of Done (DoD)** :
- **Estimation** :

---

## Découpage clair par environnement d'exécution

## A) Tickets réalisables sur Mac (développement + préparation)

Ces tickets peuvent être développés et validés majoritairement sur Mac (unit tests, intégration simulée, logs, validation de plan).

### A.1 — Tickets Mac "code principal"
- `M1.3` Config de calibration
- `M2.3` Gestion perte de cible (machine d'état)
- `M3.2` Retry et timeout mission
- `M3.3` Conditions de fin de mission
- `M4.2` Watchdog logiciel
- `M4.3` Bornage strict des paramètres
- `M5.1` Validation complète de plan
- `M5.2` Traçabilité complète
- `M5.3` Fallback parser local
- `M6.3` Rapport d'intégration (rédaction)
- `M7.3` Logs + replay

### A.2 — Tickets Mac "partiels" (préparation avant Pi)
- `M1.1` Câblage logique `RobotController` -> driver moteur (abstraction, interfaces)
- `M1.2` Calibration déplacement/rotation (structure, helpers)
- `M2.1` Détection objet live (pipeline simulé, contrats)
- `M2.2` Proximité cible (logique des seuils)
- `M3.1` Boucle de contrôle mission (logique et tests simulés)
- `M4.1` Priorité obstacle (logique d'arbitrage)
- `M6.1` Scénarios standard (préparer scripts/protocole)
- `M6.2` Mesures et tolérances (préparer feuille de mesures)
- `M7.1` Commande unique de mission (prototype script)
- `M7.2` Check-list pré-run (version doc)

### A.3 — Actions manuelles à faire sur Mac
- Exécuter la suite unitaire + intégration simulée.
- Vérifier les logs (input brut, plan brut, plan normalisé, exécution).
- Tester les cas d'erreur LLM (JSON invalide, timeout, serveur coupé).
- Préparer les documents de test Pi (protocole, grilles de mesures, template rapport).

---

## B) Tickets à faire sur Raspberry Pi (implémentation réelle + validation terrain)

Ces tickets nécessitent le robot, les capteurs, les moteurs, la caméra, et des tests physiques.

### B.1 — Tickets Pi "obligatoires"
- `M1.1` Câblage logique `RobotController` -> driver moteur
- `M1.2` Calibration déplacement/rotation
- `M2.1` Détection objet live
- `M2.2` Proximité cible
- `M2.3` Gestion perte de cible (validation réelle)
- `M3.1` Boucle de contrôle mission (validation réelle)
- `M4.1` Priorité obstacle
- `M6.1` Scénarios standard
- `M6.2` Mesures et tolérances
- `M7.1` Commande unique de mission (finalisation)
- `M7.2` Check-list pré-run (validation terrain)

### B.2 — Actions matériel (câblage / manipulations physiques)
- Monter et vérifier le câblage moteur (L298N, GPIO, alimentation commune, polarités).
- Vérifier capteur distance (position, portée, bruit).
- Monter/fixer la caméra (angle, stabilité, focus).
- Préparer zone de test au sol (repères 10/20/50 cm, angles 45/90/180).
- Contrôler batterie/tension avant chaque session.

### B.3 — Tests manuels à faire sur Raspberry Pi

#### Mouvement et sécurité (M1/M4)
1. `forward` 1s puis `stop`.
2. `backward` 1s puis `stop`.
3. `left/right` 0.5s.
4. arrêt d'urgence en mouvement.
5. obstacle soudain pendant `forward` puis pendant `approach`.

#### Calibration (M1.2)
1. mesurer 10 cm, 20 cm, 50 cm (3 répétitions chacune).
2. mesurer 45°, 90°, 180° (3 répétitions chacune).
3. ajuster config puis re-tester.

#### Vision et approche (M2/M3)
1. cible gauche/centre/droite/hors champ.
2. approche jusqu'au seuil de proximité.
3. perte de cible en cours d'approche -> recherche -> timeout/abandon.

#### Intégration complète (M6)
1. scénario "avance".
2. scénario "rotation".
3. scénario "cherche + approche".
4. scénario "obstacle en mission".
5. faire 3 runs par scénario et consigner les résultats.

---

## C) Synthèse rapide (planning pratique)

### Sprint Mac (préparation)
- Finaliser tous les tickets de `A.1`
- Préparer `A.2` pour réduire le risque Pi
- Produire protocole + templates de mesures

### Sprint Pi (réel)
- Exécuter `B.1` avec priorité : `M1 -> M2 -> M3 -> M4 -> M6 -> M7`
- Appliquer les actions matériel `B.2`
- Exécuter systématiquement les tests manuels `B.3`
