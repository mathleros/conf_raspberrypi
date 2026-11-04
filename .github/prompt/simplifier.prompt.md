---
description: Exécute un prompt de simplification numéroté (passe-plats, Callable inutiles, code mort) depuis refacto-prompts.md
agent: agent
---

Tu réalises un refactoring de SIMPLIFICATION dans ce dépôt Python (package `irobot`), sans changer le comportement.

Numéro du prompt à exécuter : ${input:numero:Numéro du prompt (0 à 14)}

## Marche à suivre

1. Lis le fichier [refacto-prompts.md](refacto-prompts.md) (dans `.github/prompts/`).
2. Trouve la section `## Prompt N`, où N est le numéro indiqué ci-dessus. Si elle n'existe pas, liste-moi les numéros disponibles et arrête-toi.
3. Lis aussi la section `## Règles communes` du même fichier : elle s'applique à tous les prompts.
4. Ouvre le « Fichier cible » et les « Fichiers liés » de cette section. Si elle indique un « Prérequis » (autre prompt), vérifie dans le code que ce prérequis est déjà fait, sinon arrête-toi et dis-le-moi.
5. Exécute uniquement les consignes du bloc de code de cette section. N'exécute aucun autre prompt et ne corrige rien en dehors de son périmètre.

## Déroulement

- **Étape A (analyse)** : sans rien modifier, donne-moi le tableau « élément | problème | action proposée | risque ». Pour chaque suppression ou renommage, indique le résultat de ta recherche de références (tests inclus). Puis demande-moi mon accord et attends.
- **Étape B (modification)** : après mon « ok », applique les changements un par un, en respectant les règles communes (comportement, signatures publiques et ordre des vérifications de sécurité inchangés, aucune nouvelle classe ou fonction hors de celles autorisées dans le prompt).
- **Fin** : résume les changements fichier par fichier, lance les tests existants si tu peux (par exemple `uv run pytest`), sinon dis-moi quoi lancer, et propose un message de commit du type `refacto: simplifie <fichier>`.

Si un cas est ambigu, pose-moi la question plutôt que de deviner.
