# Guide de Correction Rétroactif — Audit V1 : Priorité P1 (Packaging & Entrypoints)

**Origine :** Audit Architecture & Qualité V1  
**Gravité :** Critique (P1)  
**Fichier cible :** `pyproject.toml`  
**Objectif :** Rétablir le bon fonctionnement des commandes CLI (`uv run smart-car`, `uv run camera-live`, etc.) suite au déplacement des modules sous `irobot.hardware.*`.

---

## 1. Description du Problème

Suite à la réorganisation du code dans le sous-dossier `src/irobot/hardware/`, la section `[project.scripts]` de `pyproject.toml` pointait toujours vers les anciens chemins (`irobot.smart_car`, `irobot.camera`, etc.).
Lancer une commande déclenchait immédiatement une erreur `ModuleNotFoundError`.

---

## 2. Code à Modifier

Ouvrez `pyproject.toml` à la section `[project.scripts]`.

### Repères visuels :
* `[-]` : Ligne supprimée
* `[+]` : Ligne ajoutée
* `[u]` : Ligne modifiée

```toml
[project.scripts]
test = "irobot:main"
[-] camera-live = "irobot.camera.camera_live:main"
[-] color-detector = "irobot.camera.color_detector:main"
[-] balle-rouge = "irobot.camera.color_detector:main"
[-] voice-assistant = "irobot.voice_assistant.voice_assistant:main"
[+] camera-live = "irobot.hardware.camera.camera_live:main"
[+] color-detector = "irobot.hardware.camera.color_detector:main"
[+] balle-rouge = "irobot.hardware.camera.color_detector:main"
[+] voice-assistant = "irobot.hardware.audio.voice_assistant:main"
voice-runtime = "irobot.interfaces.voice_runtime:main"
[-] smart-car = "irobot.smart_car.smart_car:main"
[-] hc-sr04 = "irobot.sensors.hc_sr04:main"
[+] smart-car = "irobot.hardware.smart_car.smart_car:main"
[+] hc-sr04 = "irobot.hardware.sensors.hc_sr04:main"
```

---

## 3. Comment Tester ?

Synchronisez et testez l'appel d'aide sur les CLI :
```bash
uv sync --project .
uv run smart-car --help
uv run color-detector --help
```
*Résultat attendu :* L'aide s'affiche sans lever de `ModuleNotFoundError`.
