# Architecture simplifiée (proposition)

Objectif : commander le robot avec un vocabulaire fermé (4 behaviors, 8 cibles,
une durée) sans LLM ni orchestrateur. [robot-test](../src/irobot/tools/robot_test/cli.py) en est
la première réalisation.

## Pourquoi sans LLM

- Le vocabulaire est petit : `parse_voice_command` le gère avec des mots-clés.
- La couche LLM/Intent/Parser de `src/irobot/app/` représente environ 2 700 lignes,
  contre 286 pour `robot-test`.
- Un LLM ajoute de la latence sur le Pi, du non-déterminisme et une dépendance
  lourde (modèle GGUF, serveur llama.cpp), pour un robot qui bouge.
- Ce que le LLM apporterait : enchaînements (« avance puis tourne »), langage très
  libre, missions composées. À confirmer selon vos besoins réels.

## Schéma

```
micro ──► STT (Vosk) ──► CommandParser (règles) ──► Command ──► Dispatcher ──► Skills ──► Hardware
                                  │                                  ▲
                                  └── (option) repli LLM ────────────┘
```

## Les 5 briques

| Brique | Rôle | Existant |
|---|---|---|
| Entrée | Texte (CLI) ou voix (STT) | `common/hardware/audio`, CLI de `robot-test` |
| `CommandParser` | Texte → `Command(behavior, target, duration)` | `parse_voice_command` dans `tools/robot_test` |
| `Command` | Structure validée (énumérations fermées) | arguments de `robot-test` |
| `Dispatcher` | `behavior` → skill (`move`, `search`, `approach`, `follow`) | `_run_*` de `robot-test` |
| Skills et hardware | Exécution réelle | `common/domain`, `common/hardware` |

## Règles de conception

1. **Un seul chemin** : toute entrée produit une `Command` ; le Dispatcher ignore
   son origine (CLI, voix, test).
2. **Vocabulaire fermé** : `behavior` et `target` sont des énumérations. Une phrase
   non comprise est refusée avec un message clair, jamais devinée.
3. **Sécurité hors parseur** : durée plafonnée, arrêt d'urgence et obstacle gérés
   dans les skills, indépendamment de l'entrée.
4. **Pas d'orchestrateur** : une commande = un skill, avec arrêt moteur garanti
   dans `finally`.

## Évolution par étapes

1. **Maintenant** : `robot-test` fait tout, parser inclus.
2. Extraire `parse_voice_command` dans `common/` (`command_parser.py`) et créer un
   type `Command`, utilisés par `robot-test` et les tests.
3. Boucle d'écoute continue (mot d'activation puis commande), toujours sans LLM.
4. Enchaînements : accepter une liste de `Command` (séparateur « puis ») avant
   d'envisager un LLM.
5. Seulement si nécessaire : repli LLM appelé quand le parseur échoue, qui renvoie
   aussi une `Command` validée par les mêmes énumérations.

## Ce qui devient optionnel

`app/domain/orchestrator/*` (planner, machine à états), `plan_guards`,
`plan_validator`, `voice_llm_transport` et `llm_intent_parser`. À conserver dans
`app/` tant que l'étape 5 n'est pas écartée.
