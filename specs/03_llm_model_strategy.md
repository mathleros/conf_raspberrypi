# 3. Analyse de la stratégie LLM et du choix de modèle

## 3.1 État actuel du projet

Le projet utilise actuellement :
- Vosk pour la transcription vocale
- un modèle local LLM via `llama.cpp`
- modèle installé : `Qwen2.5-1.5B-Instruct` (GGUF Q4_K_M, `qwen2.5-1.5b-instruct-q4_k_m.gguf`), `--ctx-size 2048`, service `llm.service`
- API compatible OpenAI sur `127.0.0.1:8080`

C'est une base solide pour :
- compréhension française de commande simple,
- génération de texte court,
- aide à la traduction / reformulation,
- extraction d'intention à partir d'une phrase.

## 3.2 Force du modèle actuel

### Points forts

- assez léger pour tourner localement sur Raspberry Pi 5 (CPU seul, 1,5B quantisé)
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

### 5. Petit modèle : consignes longues et nombres en lettres

Un modèle de 1,5B suit mal les consignes longues et convertit mal les nombres écrits en lettres (sortie de Vosk). Sur Pi 5, l'appel est non streamé avec un timeout de lecture de 8 s (configurable) : évaluation du prompt + génération doivent tenir dans ce budget.

## 3.3 bis Stratégie retenue (étape 8)

- **Prétraitement déterministe** (`interfaces/text_normalizer.py`, `preprocess`) : nombres en lettres -> chiffres, « N minutes » -> N×60 secondes, « N mètres » -> N×100 centimètres ; le LLM reçoit un texte déjà normalisé. Le parseur local réutilise la même conversion de nombres.
- **Prompt court et statique** (`SYSTEM_PROMPT_PLAN`, identique à `scripts/test/eval_prompt_plan.py`) placé en tête, texte utilisateur en dernier : le préfixe reste en cache (`cache_prompt: true`, préchauffage au démarrage du runtime).
- **Sortie JSON minimale** : `{"steps":[{"intent","target","parameters"}]}`, `confidence` remplie côté code (0,8), distances en cm sans `unit`. Plan : `response_format` `json_schema` strict (`PLAN_SCHEMA`), puis sur HTTP 400 `json_object`+schéma, `json_object`, sans ; le premier format accepté est mémorisé. `temperature` 0, `max_tokens` 120 (plan) / 96 (intent unique).
- **Gardes déterministes** (`interfaces/plan_guards.py`, étape 8b, portées de `eval_prompt_plan.py`) : phrase d'arrêt pure (`is_pure_stop`) -> plan `[stop]` local sans LLM (source `local_stop`) ; `grounding_check` sur le texte prétraité : intent non justifié par un mot de la phrase -> plan rejeté (`unsupported command`, source `llm_ungrounded`, sans repli ni mouvement), `stop` parasite et paramètres non gérés supprimés, nombre absent de la phrase supprimé (aucun chiffre) ou plan rejeté (chiffres présents).
- **Hors périmètre explicite** : `{"steps":[]}` -> commande rejetée (`unsupported command`), aucun mouvement, pas de repli.
- **Filet de sécurité** : timeout, erreur HTTP, JSON invalide ou `steps` absent -> parseur local `IntentParser`. Une étape malformée est ignorée seule.
- Réglages par variables d'environnement : `LLM_MODEL`, `LLM_CONNECT_TIMEOUT_SECONDS` (1,0), `LLM_READ_TIMEOUT_SECONDS` (8,0), `LLM_MAX_TOKENS_PLAN` (120), `LLM_MAX_TOKENS_INTENT` (96).
- Mesure : `python3 scripts/test/eval_prompt_plan.py --repeat 3` (taux de plans corrects, latence, tokens/s).

## 3.4 Recommandation générale

Le bon modèle pour ce projet n'est pas "un grand LLM directement pilotant le robot", mais un LLM de planification contrôlée.

### Règle de conception

- LLM = interprète de la consigne + générateur de plan structuré
- contrôle moteur = logique déterministe dédiée
- sécurité = règles de garde-fou et conditions de stop

## 3.5 Stratégie recommandée

### Option A. Stratégie simple et robuste (recommandée pour la phase 1)

- Garder le modèle local actuel `Qwen2.5-1.5B-Instruct`
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
- Conserver `Qwen2.5-1.5B-Instruct` (GGUF Q4_K_M) comme modèle principal
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

## 3.9 Règle de hiérarchie entre LLM, behaviors et skills primitives

Le LLM ne doit pas choisir les commandes bas niveau du robot de manière libre.

Le bon flux est :

1. le texte vocal est transcrit ;
2. le LLM détermine l'intention de haut niveau ;
3. le planner transforme cette intention en un comportement ou un plan de tâches ;
4. le planner décompose ensuite ce comportement en skills primitives ;
5. les skills primitives exécutent le mouvement réel via le `RobotController`.

Exemple :

- Entrée : "fait un rond"
- Intention LLM : `move_circle`
- Plan : `turn_left + move_forward + repeat + stop_motion`
- Exécution : `TurnLeftSkill`, `MoveForwardSkill`, `StopMotionSkill`

Autre exemple :

- Entrée : "suit la balle rouge"
- Intention LLM : `follow_target`
- Plan : `detect_red_ball -> align_to_target -> move_forward -> stop_on_loss_or_obstacle`
- Exécution : primitives du mouvement combinées aux skills de perception

### Règles de bonnes pratiques

- le LLM ne doit pas décider directement des GPIO ;
- le LLM ne doit pas produire des ordres mécanistes non validés ;
- le planner doit toujours vérifier le plan avant exécution ;
- les périmètres de sécurité restent dans le moteur de contrôle, pas dans le modèle linguistique ;
- les compétences complexes doivent être décomposées dans un orchestrateur, pas laissées “flottantes” dans le modèle.

Cette hiérarchie est la clé pour conserver à la fois flexibilité du langage naturel et robustesse robotique.
