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

## 5. SUIVI HUMAIN — IMPLÉMENTATION PAR ÉTAPES
- Réfère-toi à `specs/backlog/07_suivi_humain_marqueur_backlog.md` et `specs/backlog/08_lot_a_rapport_sh09.md` pour l'état, les décisions et les preuves. Ne rouvre pas les décisions validées et ne redemande pas confirmation pour un choix qui découle directement des exigences ; consigne brièvement les choix dérivés. Demande une clarification uniquement pour un choix structurant ou un changement de périmètre.
- Avance par blocs cohérents, bornés et aussi autonomes que possible. Pour chaque bloc, annonce le livrable et ses limites, implémente-le, lance les tests ciblés pertinents, puis à la fin exécute la campagne isolée et la non-régression couvrant les surfaces modifiées. Évite les validations répétées après chaque micro-changement ; relance les vérifications affectées après toute correction. Ne réduis pas les contrôles nécessaires à la qualité.
- Conserve les résultats négatifs et inconclusifs dans le bilan. Distingue clairement tests synthétiques, exécution sur Pi, observations rapportées par l'utilisateur et preuves matérielles ; ne déduis jamais une qualification d'une preuve d'un autre niveau.
- À la fin d'un bloc, résume en quelques lignes le livrable, les vérifications/résultats, les limites ou blocages et le prochain bloc proposé. Ne mets à jour les documents de suivi que pour refléter les changements réellement réalisés et leurs preuves.
- L'objectif de tester le robot en réel n'est pas en soi une autorisation d'action matérielle. N'ouvre pas de caméra réelle, ne lance pas de commande sur le Pi, ne manipule pas le robot et ne commande aucun mouvement sans autorisation explicite portant sur l'étape et l'action concernées, ainsi que ses préconditions et limites. Respecte les portes de sécurité et de recette du backlog ; aucun résultat logiciel ou prompt généré ne vaut Go physique.
- Quand l'utilisateur demande de rédiger le prompt de l'étape suivante, rédige un prompt prêt à l'emploi qui : reprend l'état et les décisions acquises sans les re-questionner ; fixe un objectif/livrable borné et les vérifications proportionnées à ce bloc ; demande de consigner résultats, limites et étape suivante ; sépare explicitement travail logiciel, validation sur Pi et essai physique ; précise les préconditions et l'autorisation distincte requise avant toute action matérielle. Le prompt doit accélérer les étapes logicielles sans présenter une autorisation future comme déjà accordée.