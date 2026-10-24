# Instructions d'Optimisation de Tokens (Mode Concis)

## 1. CONNAISSANCE DU CONTEXTE
- Les conventions du projet, les décisions d'architecture et l'état actuel sont maintenus dans `PROJECT_CONTEXT.md`.
- Aligne systématiquement la génération de code et tes recommandations sur les règles et l'état définis dans `PROJECT_CONTEXT.md`.
- **Mise à jour du contexte :** Ne mets à jour `PROJECT_CONTEXT.md` QUE lors d'une décision d'architecture majeure, de la fin d'une fonctionnalité complète ou à la demande explicite de l'utilisateur. Ne le modifie pas pour de petits correctifs.

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