# Cadrage du projet robotique autonome

Ce dossier constitue le référentiel de conception pour la suite du projet robot. Il reprend l'état du dépôt actuel, identifie les compétences déjà disponibles, formalise l'architecture fonctionnelle et technique cible, puis évalue la stratégie LLM la mieux adaptée.

## Objet

Le robot dispose aujourd'hui de briques de base : déplacement moteur, détection couleur, détection de distance, capture audio, STT et LLM local. L'objectif est désormais de passer d'un ensemble de compétences unitaires à un système capable d'exécuter des tâches complexes à partir d'une consigne vocale en français.

Les scénarios cibles incluent notamment :
- "suit la balle rouge"
- "fait un rond"
- "avance jusqu'à l'objet rouge puis tourne à gauche"
- "évite les obstacles et suit la cible"
- "cherche la balle jaune, approche-toi à 1 m puis suis-la pendant 5 min"

Le contrat livré pour ce dernier scénario est `search_and_approach_object` puis `follow_object` (`target="yellow"`, `stand_off_cm=100`, `duration_s=300`, `search_timeout_s` optionnel). Voir [l'inventaire à jour](01_skills_inventory.md#contrat-runtime-livré-2026-10-29) pour les skills, limites, estimation de distance et arrêts de sécurité. Les descriptions de phases de transition ci-dessous sont le cadrage historique, pas des fonctionnalités encore à implémenter.

## Livrables du cadrage

1. Inventaire des skills déjà disponibles et des écarts
2. Architecture fonctionnelle et technique cible
3. Stratégie de modèles LLM / orchestrateur
4. Plan de mise en œuvre (pour la phase de codage suivante)

## Hypothèse de conception

Le système doit respecter trois principes :
- la commande vocale est un input naturel, pas un ordre moteur direct ;
- le LLM ne doit pas piloter les GPIO directement ;
- l'exécution doit passer par un orchestrateur déterministe et des skills testables.

La logique recommandée est :
- audio -> transcription -> compréhension de l'intention -> plan exploitable -> exécution de skills -> boucle de monitorage -> arrêt / réussite / échec.

## Fichiers du dossier

- `01_skills_inventory.md` : inventaire des skills existantes et manquantes
- `02_functional_technical_architecture.md` : architecture du besoin et schéma technique
- `03_llm_model_strategy.md` : analyse des modèles, contraintes et recommandations
- [Étude et backlog du suivi humain avec marqueur](backlog/07_suivi_humain_marqueur_backlog.md) : nouveau besoin « suis-moi », réutilisation de l'existant, écarts, sécurité et plan de validation ; cadrage sans implémentation.

## Niveau de maturité actuel

Le projet est en phase de transition :
- composants matériels validés de manière unitaire ;
- modules Python existants et testés indépendamment ;
- besoin d'intégration et d'architecture globale manquante ;
- besoin d'un moteur de planification robuste et de contrôleurs de sécurité.

## Conclusion rapide

Le projet a une bonne base technique, mais il manque un niveau d'abstraction supplémentaire : le "planner" / "orchestrateur" qui décide quelles skills appeler, dans quel ordre, avec quels paramètres, selon l'état du robot et les conditions de sécurité.

## Règles de conception validées

Le cadrage a été ajusté pour aligner la hiérarchie des skills sur le besoin robotique réel :

- les skills primitives sont les actions atomiques du robot ;
- les comportements composites sont des séquences de primitives ;
- le LLM ne doit pas piloter directement les moteurs ni les GPIO ;
- l'orchestrateur est responsable de transformer une intention de haut niveau en séquence de skills primitives ;
- les règles de sécurité doivent être appliquées avant, pendant et après toutes les exécutions.

### Taxonomie recommandée

#### A. Skills primitives
- `move_forward`
- `move_backward`
- `turn_left`
- `turn_right`
- `stop_motion`

#### B. Skills de perception
- `detect_red_ball`
- `detect_obstacle`
- `read_distance`

#### C. Behaviors composites
- `follow_target`
- `follow_object`
- `align_to_target`
- `approach_target`
- `move_circle`
- `avoid_obstacle`

### Règle importante

`move_circle` n'est pas une skill primitive. C'est un comportement composite qui doit être décomposé en une séquence de primitives telles que :
- `turn_left`
- `move_forward`
- `stop_motion`

sur une durée et/ou une trajectoire paramétrées.

### Bonnes pratiques de conception

1. Garder les skills primitives petites, déterministes et facilement testables.
2. Ne pas exposer de logique métier complexe dans les primitives.
3. Toujours renvoyer un résultat standardisé (`SkillResult`) avec statut, message, données et confiance.
4. Validations de préconditions avant exécution.
5. Conditions de sécurité et d'arrêt d'urgence centrées sur l'orchestrateur.
6. Le comportement de haut niveau est décrit par l'intention, pas par un ensemble de commandes libres.

## Ce que le projet doit viser

Le robot doit être capable de :
- comprendre une instruction vocale en français ;
- extraire l'intention ;
- choisir un comportement pertinent ;
- transformer ce comportement en séquence de skills primitives ;
- exécuter la séquence avec sécurité ;
- accomplir la mission ou s'arrêter avec un diagnostic clair.
