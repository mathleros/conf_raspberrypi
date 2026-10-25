# Guide de Correction — Priorité P2 : Fermeture Propre de la Caméra au Shutdown

**Gravité :** Stabilité Matérielle (P2)  
**Fichier cible :** `src/irobot/interfaces/voice_runtime.py`  
**Objectif :** Garantir que le pilote caméra CSI est proprement libéré à l'arrêt du programme (via `Ctrl+C` ou `--once`), évitant l'erreur `Device or resource busy`.

---

## 1. Description du Problème

Dans `CameraLivePerceptionPipeline`, le thread de capture est marqué en `daemon=True`.
Lorsqu'un script Python s'arrête (par exemple lors d'un `Ctrl+C` ou à la fin de `--once`), Python termine les threads daemons sans exécuter leurs blocs `finally`.
* **Conséquence :** `camera.stop()` n'est pas appelé de manière déterministe. Le périphérique de capture CSI (`/dev/video*` ou interface libcamera) reste parfois verrouillé par le kernel Linux, obligeant à relancer le service ou à redémarrer le Raspberry Pi.

---

## 2. Code à Modifier

Dans `src/irobot/interfaces/voice_runtime.py` :

### Repères visuels :
* `[-]` : Ligne à supprimer
* `[+]` : Ligne à ajouter
* `[u]` : Ligne modifiée

---

### Étape A : Ajouter la méthode `close()` dans la classe `VoiceRuntime`
Localisez la fin de la classe `VoiceRuntime` (juste au-dessus de `def build_hardware_runtime()`) :

```python
    def listen_forever(self):
        device = resolve_input_device(self.input_device)
        try:
            for text in transcribe_loop(device):
                print(f"\n[VOIX] {text}", flush=True)
                result = self.handle_text(text)
                print(f"[RUNTIME] {result}", flush=True)
        except KeyboardInterrupt:
            print("\nInterruption clavier : arrêt du runtime vocal.")

[+] def close(self) -> None:
[+]     """Arrête proprement les périphériques matériels et les threads d'arrière-plan."""
[+]     if self.perception is not None and hasattr(self.perception, "close"):
[+]         try:
[+]             self.perception.close()
[+]         except Exception:
[+]             pass
[+]     if self.robot is not None and hasattr(self.robot, "stop"):
[+]         try:
[+]             self.robot.stop()
[+]         except Exception:
[+]             pass
```

---

### Étape B : Encadrer `main()` avec un bloc `try...finally`
Dans `def main():` de `voice_runtime.py` :

```python
def main():
    parser = argparse.ArgumentParser(
        description="Runtime vocal complet : Vosk → intent → skills -> robot."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ecoute une seule phrase puis s'arrête.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Utilise le parseur local au lieu du LLM pour interpréter la commande.",
    )
    parser.add_argument(
        "--input-device",
        default="auto",
        choices=["auto", "bluetooth", "wm8960", "default"],
        help="Source audio utilisée pour l'enregistrement.",
    )
    args = parser.parse_args()

[+] runtime = None
    try:
        hardware = build_hardware_runtime()
[u]     runtime = VoiceRuntime(
            robot=hardware["robot"],
            camera=hardware["camera"],
            sensor=hardware["sensor"],
            perception=hardware["perception"],
            input_device=args.input_device,
            use_llm=not args.no_llm,
        )
        if args.once:
            runtime.listen_once()
            return
        runtime.listen_forever()
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)
[+] finally:
[+]     if runtime is not None:
[+]         runtime.close()
```

---

### Résultat final propre de `main()` :
```python
def main():
    parser = argparse.ArgumentParser(
        description="Runtime vocal complet : Vosk → intent → skills -> robot."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ecoute une seule phrase puis s'arrête.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Utilise le parseur local au lieu du LLM pour interpréter la commande.",
    )
    parser.add_argument(
        "--input-device",
        default="auto",
        choices=["auto", "bluetooth", "wm8960", "default"],
        help="Source audio utilisée pour l'enregistrement.",
    )
    args = parser.parse_args()

    runtime = None
    try:
        hardware = build_hardware_runtime()
        runtime = VoiceRuntime(
            robot=hardware["robot"],
            camera=hardware["camera"],
            sensor=hardware["sensor"],
            perception=hardware["perception"],
            input_device=args.input_device,
            use_llm=not args.no_llm,
        )
        if args.once:
            runtime.listen_once()
            return
        runtime.listen_forever()
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)
    finally:
        if runtime is not None:
            runtime.close()
```

---

## 3. Comment Tester ?

### Test 1 : Vérification de non-régression unitaire
```bash
uv run pytest -q tests/unit
```

### Test 2 : Relance successive sur Raspberry Pi sans blocage
Exécutez deux fois de suite la commande :
```bash
uv run voice-runtime --once --no-llm
uv run voice-runtime --once --no-llm
```
*Résultat attendu :* La caméra s'ouvre, se ferme proprement, et la seconde exécution démarre immédiatement sans erreur de ressource occupée.
