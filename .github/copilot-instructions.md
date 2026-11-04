# Instructions d'Optimisation de Tokens (Mode Concis)

## 1. REGLES DE STRUCTURE ET DE RAILLE DU CODE (STRICT)
- **FIchiers Python :** Ne jamais dépasser ***500 lignes*** par fichier (idéalement entre 300 et 450 lignes). Si un module grandit, sépare la logique (sépare les responsabilités dans plusieurs fichiers).
- **Fonctions et Méthodes :** Ne jamais dépasser **50 lignes** par fonction (idéalement entre 10 et 30 lignes). une fonction = une seule responsabilité (Clean code).
- **Privilégie le code simple et direct :** pas de méthode qui ne fait que déléguer.
- **Pas de Callable/injection de fonction :** N'utilise pas de Callable/injection de fonction sauf besoin explicite ; préfère un appel direct ou un Protocol.
- **Pas de nouvelle couche d'abstraction :** Ne crée pas de nouvelle couche d'abstraction sans que je la demande.
- **Type hints complets et noms explicites :** Utilise des annotations de type complètes et des noms de variables explicites.

## 2. RÈGLES DE RÉPONSE ÉCONOMIQUES
- **Pas de prose inutile :** Supprime toute formule de politesse, préambule, introduction ("Voici le code...") ou conclusion.
- **Diffs uniquement :** Ne réécris jamais un fichier complet. Renvoie uniquement le bloc de code modifié ou le patch diff avec le chemin du fichier.
- **Maximum 2 phrases d'explication :** Sauf demande explicite d'explication technique, limite tes explications textuelles au strict minimum.

## 3. GESTION DES CLARIFICATIONS
- **Maximum 1 question :** Si la demande manque de clarté, ne déroule pas une longue liste de questions. Pose au maximum **1 seule question fermée** (Choix A/B ou Oui/Non).
- **Hypothèses par défaut :** Fais les hypothèses les plus standard et exécute la tâche directement au lieu de demander confirmation.

## 4. OPÉRATIONS GIT (`/cp` ou "commit push")
- Quand l'utilisateur demande de commiter/pusher ou tape `/cp` :
  - Génère un message de commit concis au format Conventional Commits basés sur les diffs.
  - Génère et exécute directement la commande terminal sans aucun texte explicatif autour.

## 5. RÈGLES ANTI-SUR-INGÉNIERIE (KISS & YAGNI)
- **Objectif Projet Réel :** Le projet est un banc d'essai robotique physique (Smart Car 2WD + Raspberry Pi 5), PAS un système aérospatial ou médical normé. Privilégie TOUJOURS la solution la plus directe, courte et pragmatique qui fait tourner le robot.
- **Interdiction formelle de sur-spécifier :**
  - Ne crée JAMAIS de nouveaux contrats théoriques, protocoles de certification, jetons d'armement, matrices de lot (Lot A, B...), permis de mission ou machines d'états à multiples couches d'abstractions.
  - Ne fragmente pas le code en myriades de mixins, de wrappers ou de sous-modules pour des fonctionnalités simples.
  - Pas de création de fichiers intermédiaires (`*_contracts.py`, `*_runtime_adapter.py`, etc.) sans demande explicite.
- **Pragmatisme Robotique :**
  - Un mouvement = une impulsion moteur claire (`forward`, `left`, `right`, `stop`).
  - Une commande vocale directe (« stop », « suis-moi ») = une regex dans `intent_parser.py` (0 ms de latence), JAMAIS un appel réseau LLM de plusieurs secondes.
  - La sécurité matérielle = vérifier le capteur d'obstacle et couper immédiatement les moteurs au mot « stop ». N'invente pas de verrous logiciels qui empêchent le robot d'avancer.
- **Contrôle du volume de code :**
  - Si un problème peut être résolu en modifiant 5 lignes dans un fichier existant, n'en écris pas 50 dans un nouveau fichier.
  - Tout code mort, fonction non appelée ou test théorique sur des mocks impossibles doit être éliminé.


## 6. CONNAISSANCE DU CONTEXTE
- Les conventions du projet, les décisions d'architecture et l'état actuel sont maintenus dans `PROJECT_CONTEXT.md`.
- Aligne systématiquement la génération de code et tes recommandations sur les règles et l'état définis dans `PROJECT_CONTEXT.md`.
- **Mise à jour du contexte :** Ne mets à jour `PROJECT_CONTEXT.md` QUE lors d'une décision d'architecture majeure, de la fin d'une fonctionnalité complète ou à la demande explicite de l'utilisateur. Ne le modifie pas pour de petits correctifs.
