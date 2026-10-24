# Tests unitaires des skills

Ce dossier contient les tests unitaires pour valider les compétences du robot sans dépendre du matériel réel.

## Objectif

Les tests doivent vérifier les règles de contrat des skills :
- validation du contexte
- exécution de la commande correct
- retour d'un `SkillResult` standardisé
- gestion des erreurs de manière explicite
- logique de sécurité et de comportement

## Structure

- `fake_robot.py` : robot factice pour simuler le matériel sans GPIO ni Raspberry Pi
- `test_skills_primitives.py` : tests sur les actions de base du robot
- `test_skills_perception.py` : tests sur la détection d'objets et d'obstacles
- `test_skills_behaviors.py` : tests sur les comportements composites

## Commande d'exécution

Depuis la racine du projet :

```bash
uv run pytest -q tests/unit
```

## Règles

- les tests doivent rester portables sur Mac et sur Raspberry Pi ;
- ils doivent utiliser un robot factice, pas le hardware réel ;
- chaque fine-grained test doit valider un comportement simple et clair ;
- les comportements composites doivent être testés avec un contexte métier réaliste.

## Exemple de validité

Un test valide typiquement :
- le bon appel est effectué (`forward`, `left`, `stop`, etc.)
- le `SkillResult.status` est bien `success` ou `failed`
- les données de retour contiennent les bons éléments
- la `next_action` correspond à la prochaine étape logique
