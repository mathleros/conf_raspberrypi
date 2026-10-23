# 3. Analyse de la stratégie LLM et du choix de modèle

## 3.1 État actuel du projet

Le projet utilise actuellement :
- Vosk pour la transcription vocale
- un modèle local LLM via `llama.cpp`
- modèle installé : `Ministral 3 3B Instruct`
- API compatible OpenAI sur `127.0.0.1:8080`

C'est une base solide pour :
- compréhension française de commande simple,
- génération de texte court,
- aide à la traduction / reformulation,
- extraction d'intention à partir d'une phrase.

## 3.2 Force du modèle actuel

### Points forts

- léger enough pour tourner localement sur Raspberry Pi 5
- bon pour le français
- utile pour le parsing de consigne simple
- compatible avec API OpenAI locale
- facile à intégrer avec un orchestrateur Python

### Cas d'usage pour lesquels il est adapté

- "donne-moi un plan de la commande"
- "transforme cette phrase en structure JSON"
- "choisis les skills nécessaires pour suivre une balle rouge"
- "extrait le target, la vitesse, le mode et la condition d'arrêt"

Le modèle actuel est donc suffisant pour la couche de compréhension linguistique et de planification simple, tant que la tâche reste limitée et structurée.

## 3.3 Limites du modèle actuel

### 1. Gestion de la planification complexe

Le robot ne doit pas décider de mouvements moteurs en fonction d'un raisonnement libre et non supervisé. Le LLM doit produire un plan structuré, pas des ordres en temps réel.

### 2. Déterminisme insuffisant pour la robotique

Pour une tâche comme "suit la balle rouge", il faut :
- détecter une cible,
- calculer sa position,
- corriger l'orientation,
- avancer progressivement,
- réguler la vitesse,
- arrêter si la cible est perdue,
- s'arrêter si obstacle proches.

Cette logique doit être déterministe et robuste. Les décisions temps réel doivent être prises par une boucle de contrôle, pas par le LLM.

### 3. Connaissance visuelle limitée

Les compétences de perception visuelle du projet ne passent pas par le LLM. La caméra et le détecteur de couleur sont des outils dédiés. Le LLM ne doit pas décider du pixel target ; il décide du plan.

### 4. Risk de sortie non conforme

Un LLM libre peut produire des réponses improvisées, des ordres illisibles ou des plans non verifiables. Cela est dangereux en robotique si on laisse le modèle décider sans l'intermédiaire d'un validateur.

## 3.4 Recommandation générale

Le bon modèle pour ce projet n'est pas "un grand LLM directement pilotant le robot", mais un LLM de planification contrôlée.

### Règle de conception

- LLM = interprète de la consigne + générateur de plan structuré
- contrôle moteur = logique déterministe dédiée
- sécurité = règles de garde-fou et conditions de stop

## 3.5 Stratégie recommandée

### Option A. Stratégie simple et robuste (recommandée pour la phase 1)

- Garder le modèle local actuel `Ministral 3 3B`
- Le faire produire uniquement du JSON ou du YAML
- Ajouter un validateur strict avant exécution
- Utiliser des rules de sécurité déterministes

Exemple de contrat de sortie attendu :

```json
{
  "intent": "follow_target",
  "target": "red_ball",
  "skills": ["detect_red_ball", "align_to_target", "approach_target"],
  "max_duration": 20,
  "stop_conditions": ["target_lost", "obstacle_close", "manual_stop"]
}
```

Ce mode est viable et réaliste pour commencer le codage.

### Option B. Modèle plus puissant local (si besoin de plus de puissance)

Si l'on veut améliorer le raisonnement global, on peut envisager :
- Qwen2.5 7B Instruct quantisé
- Llama 3.1 8B Instruct quantisé
- Gemma 7B IT quantisé

Avantages :
- meilleur raisonnement de planification
- meilleure robustesse sur les consignes naturelles longues
- meilleur suivi de plusieurs contraintes

Inconvénients :
- plus lent sur Raspberry Pi
- plus gourmand en RAM / CPU
- peut être moins stable pour des boucles temps réel

### Option C. Modèle hybride

Cette stratégie est souvent la meilleure en robotique :
- un modèle local compact pour le parsing / l'analyse du langage,
- un second modèle plus puissant (local ou distant) pour la validation du plan,
- un moteur de règles pour l'exécution.

Exemple de hiérarchie :
1. `IntentClassifier` : détecte la tâche et le target
2. `Planner` : décide la séquence de skills
3. `SafetyValidator` : vérifie cohérence et sécurité
4. `Executor` : exécute les skills

## 3.6 Recommandation concrète pour ce projet

### Phase 1 : architecture de base
- Conserver `Ministral 3 3B` comme modèle principal
- exiger un schéma JSON strict
- utiliser un planner Python déterministe

### Phase 2 : si besoin d'un vrai niveau d'intelligence plus avancé
- intégrer un modèle plus puissant localement ou via API externe
- surtout pour les tâches complexes ou la commande française longue

### Phase 3 : gestion de mission multi-étape
- S'appuyer sur un orchestrateur non LLM, avec règles et états
- le LLM ne sert plus qu'à reformuler et planifier de haut niveau

## 3.7 Recommandation de sécurité

Le LLM ne doit jamais :
- envoyer directement des ordres de GPIO brut
- décider sans validation d'un mouvement pouvant provoquer un collision
- sortir un texte libre comme "avance vite et évite tout"

Il doit produire un plan dont chaque étape est vérifiable et encodable dans un moteur de skills pris en charge par Python.

## 3.8 Conclusion

Le modèle actuel est bien adapté comme couche d'analyse linguistique et de plan de haut niveau, mais insuffisant seul pour piloter un robot autonome de manière sûre et déterministe. La bonne architecture est donc :
- LLM = planificateur de niveau supérieur
- robotique = moteur de contrôle à base de skills
- sécurité = règles de garde-fou et validation

C'est cette architecture qui permettra de réaliser les tâches complexes décrites par le client sans perdre la robustesse du système embarqué.
