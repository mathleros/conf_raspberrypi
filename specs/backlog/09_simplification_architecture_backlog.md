# Chantier différé — étude de simplification après le suivi humain

**Demande utilisateur du 2026-10-30 :** terminer d'abord le travail engagé dans le [backlog de suivi humain](07_suivi_humain_marqueur_backlog.md), puis examiner ensemble les options de simplification du projet. Statut : à étudier ultérieurement, non commencé. Ce chantier ne modifie ni les priorités actuelles, ni les décisions validées, ni les autorisations requises pour poursuivre le suivi humain.

**Objectif :** réduire les chemins d'exécution concurrents et les responsabilités mélangées, sans réécriture générale ni retour à un script monolithique. Le nombre de fichiers n'est pas le critère de réussite.

Options à examiner, sur la base du code qui existera alors :

- [ ] **SIM-01 — Unifier l'exécution des commandes.** Étudier la convergence des chemins texte/intention et commande simple/plan : une commande simple serait une mission d'une seule étape. Supprimer les duplications de préparation du contexte et d'exécution dans [LanguageController](../../src/irobot/interfaces/language_controller.py), sans perdre les contrôles ni les résultats utiles.
- [ ] **SIM-02 — Centraliser la décomposition des intentions.** Choisir un seul responsable pour transformer les commandes de haut niveau en étapes exécutables, aujourd'hui réparties notamment entre le [planificateur](../../src/irobot/domain/orchestrator/planner.py) et le [runtime vocal](../../src/irobot/interfaces/voice_runtime.py).
- [ ] **SIM-03 — Alléger les responsabilités du runtime.** Examiner la séparation entre acquisition audio, interprétation, validation, progression des missions et traces. Conserver un parseur local et un LLM interchangeables produisant les mêmes commandes structurées, sans dupliquer l'exécution ni ajouter d'abstractions inutiles.
- [ ] **SIM-04 — Clarifier les frontières des comportements et protections.** Garder des comportements lisibles et testables, ainsi qu'un point de contrôle des mouvements clairement identifié ; étudier la centralisation des règles transversales sans retirer les vérifications nécessaires.

**Invariants à préserver :**

- Même assistant et même runtime pour les capacités balle et humain ; aucun mode manuel supplémentaire.
- Séparation matériel/comportements, simulation portable et tests existants.
- Validation des commandes avant exécution ; aucun pilotage direct des moteurs par le LLM.
- Arrêts prioritaires, protections, réservation, suspension/reprise, limites et refus définis par le suivi humain ; aucune simplification par suppression de ces garanties.
- Comportements existants et différences intentionnelles entre suivi de balle et suivi humain.

**Méthode et critères de sortie de l'étude :**

1. Après le travail engagé sur le suivi humain, relire l'état réel du code et des preuves ; les constats du 2026-10-30 ne constituent pas un diagnostic définitif de cette future version.
2. Comparer les options avec leurs bénéfices, risques et impacts, puis choisir ensemble un périmètre explicite avant toute modification.
3. Pour chaque lot retenu, établir une référence de comportement et des tests de non-régression couvrant commandes simples/composées, parseur local/LLM simulé, refus, erreurs, arrêts et transitions de session.
4. Réaliser uniquement les changements approuvés, vérifier les comportements préservés et analyser les qualifications à renouveler si des chemins protégés sont affectés. Une réussite logicielle ne vaut ni qualification physique ni nouveau Go.

Cette inscription autorise uniquement le suivi du chantier dans le backlog : aucune refactorisation ni nouvelle exécution n'est engagée.
