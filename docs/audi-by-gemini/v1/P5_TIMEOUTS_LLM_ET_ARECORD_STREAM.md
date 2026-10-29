# Guide de Correction Rétroactif — Audit V1 : Priorité P5 (Timeouts LLM & Sécurisation arecord)

**Origine :** Audit Architecture & Qualité V1  
**Gravité :** Robustesse & Réactivité (P5)  
**Fichier cible :** `src/irobot/interfaces/voice_runtime.py`  
**Objectif :** Réduire le timeout réseau LLM de 120s à un délai strict de 5s maximum et sécuriser l'arrêt des processus audio.

---

## 1. Description du Problème

1. `LLM_TIMEOUT = 120` gelait tout le robot pendant 2 minutes si le modèle local `llama-server` mettait du temps à charger ou s'il était éteint.
2. `arecord` était lancé via `subprocess.Popen` sans context manager, laissant des processus orphelins verrouillant le périphérique audio ALSA en cas d'interruption.

---

## 2. Code à Modifier

Dans `src/irobot/interfaces/voice_runtime.py` :

### Étape A : Timeouts HTTP stricts
```python
[-] LLM_TIMEOUT = 120
[+] LLM_CONNECT_TIMEOUT_SECONDS = 1.0
[+] LLM_READ_TIMEOUT_SECONDS = 4.0
[+] LLM_HTTP_TIMEOUT = (LLM_CONNECT_TIMEOUT_SECONDS, LLM_READ_TIMEOUT_SECONDS)

    def ask_llm_for_intent(text: str) -> Intent:
        ...
        try:
[-]         response = requests.post(LLM_URL, json=payload, timeout=LLM_TIMEOUT)
[+]         response = requests.post(LLM_URL, json=payload, timeout=LLM_HTTP_TIMEOUT)
```

### Étape B : Gestionnaire de contexte `_arecord_stream`
```python
[+] @contextmanager
[+] def _arecord_stream(device: str):
[+]     args = ["arecord", "-D", device, "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"]
[+]     proc = subprocess.Popen(args, stdout=subprocess.PIPE)
[+]     try:
[+]         if proc.stdout is None:
[+]             raise RuntimeError("Flux audio arecord introuvable.")
[+]         yield proc.stdout
[+]     finally:
[+]         if proc.poll() is None:
[+]             proc.terminate()
[+]             try:
[+]                 proc.wait(timeout=1.0)
[+]             except subprocess.TimeoutExpired:
[+]                 proc.kill()
[+]                 proc.wait(timeout=1.0)
[+]         if proc.stdout is not None:
[+]             proc.stdout.close()
```

---

## 3. Comment Tester ?

Testez la bascule immédiate sur le parseur local lorsque le serveur LLM est éteint :
```bash
uv run pytest -k "test_voice_runtime_uses_parser_fallback_when_llm_plan_invalid"
```
*Résultat attendu :* Le test s'exécute en une fraction de seconde sans subir de temporisation de 120 s.
