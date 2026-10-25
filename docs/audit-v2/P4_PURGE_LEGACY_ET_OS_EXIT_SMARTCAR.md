# Guide de Correction Rétroactif — Audit V2 : Priorité P4 (Purge Legacy & os._exit dans SmartCar)

**Origine :** Audit Architecture & Qualité V2  
**Gravité :** Propreté & Dette Technique (P4)  
**Fichiers cibles :** `src/irobot/hardware/audio/voice_assistant.py` et `src/irobot/hardware/smart_car/smart_car.py`  
**Objectif :** Éliminer 150 lignes de code mort et supprimer l'appel brutal à `os._exit(0)` dans `smart_car.py`.

---

## 1. Description du Problème

1. `voice_assistant.py` contenait la classe `VoiceCarController` et la fonction `legacy_main()`, qui court-circuitaient l'architecture officielle `VoiceRuntime` et créaient de la confusion.
2. `smart_car.py` appelait `os._exit(0)` à la fin de `main()`, tuant l'interpréteur Python sans laisser les destructeurs libérer la mémoire ou flusher les logs.

---

## 2. Code à Modifier

### Étape A : Purge dans `src/irobot/hardware/audio/voice_assistant.py`
Suppression de la classe obsolète et redirection directe vers le runtime unifié :

```python
[-] class VoiceCarController:
[-]     ... (110 lignes supprimées)
[-] def legacy_main():
[-]     ... (35 lignes supprimées)

def main() -> None:
    """Compatibilité CLI: redirige vers le runtime vocal unifié."""
[+] voice_runtime_main()

if __name__ == "__main__":
    main()
```

### Étape B : Suppression de `os._exit(0)` dans `src/irobot/hardware/smart_car/smart_car.py`
Dans le bloc `finally` de `def main():` :

```python
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        run_command(args)
    except ValueError as exc:
        parser.error(str(exc))
[-] finally:
[-]     os._exit(0)
```

---

## 3. Comment Tester ?

Vérifiez que la commande `voice-assistant` lance bien le runtime moderne :
```bash
uv run voice-assistant --help
```
*Résultat attendu :* L'aide du runtime vocal unifié s'affiche sans référence à l'ancien contrôleur.
