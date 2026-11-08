# `robot-test` : banc de test du noyau

Rôle : tester la logique cœur (skills, comportements, parseur de commandes) sans LLM ni intents, en appelant directement les skills.

```bash
uv run robot-test --behavior move --target forward --duration 2
uv run robot-test --text "avance deux secondes puis suis moi"   # sans micro
uv run robot-test --audio                                       # écoute « robot, ... »
```

Différence avec `robot` (`app/`) : `robot-test` n'utilise ni LLM ni intents ni missions ; il exécute directement les commandes du parseur de règles.
