# Cadrage du projet robotique autonome

Ce dossier constitue le référentiel de conception pour la suite du projet robot. Il reprend l'état du dépôt actuel, identifie les compétences déjà disponibles, formalise l'architecture fonctionnelle et technique cible, puis évalue la stratégie LLM la mieux adaptée.

## Objet

Le robot dispose aujourd'hui de briques de base : déplacement moteur, détection couleur, détection de distance, capture audio, STT et LLM local. L'objectif est désormais de passer d'un ensemble de compétences unitaires à un système capable d'exécuter des tâches complexes à partir d'une consigne vocale en français.

Les scénarios cibles incluent notamment :
- "suit la balle rouge"
- "fait un rond"
- "avance jusqu'à l'objet rouge puis tourne à gauche"
- "évite les obstacles et suit la cible"

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

## Niveau de maturité actuel

Le projet est en phase de transition :
- composants matériels validés de manière unitaire ;
- modules Python existants et testés indépendamment ;
- besoin d'intégration et d'architecture globale manquante ;
- besoin d'un moteur de planification robuste et de contrôleurs de sécurité.

## Conclusion rapide

Le projet a une bonne base technique, mais il manque un niveau d'abstraction supplémentaire : le "planner" / "orchestrateur" qui décide quelles skills appeler, dans quel ordre, avec quels paramètres, selon l'état du robot et les conditions de sécurité.
