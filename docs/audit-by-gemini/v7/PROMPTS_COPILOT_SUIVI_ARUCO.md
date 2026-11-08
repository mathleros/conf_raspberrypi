# Guide des Prompts VS Code / Copilot — Implémentation Rapide « Suis-moi » (ArUco) & Simplification

Ce document contient la feuille de route exacte pour rendre le cas d'usage **« suis-moi » (ArUco + arrêt d'urgence « stop »)** opérationnel sur votre Raspberry Pi en un minimum de temps et avec une **consommation minimale de tokens**.

---

## 策略 Stratégie de Sessions Copilot (Économie maximale de tokens)

Pour éviter que Copilot ne réinjecte tout l'historique et ne s'emmêle les pinceaux avec les anciens contrats :
* **Toujours ouvrir un NOUVEAU Chat (`+ New Chat`)** à chaque étape structurante.
* Toujours cibler explicitement les fichiers avec la balise `#file:...` pour limiter le contexte injecté à quelques centaines de tokens au lieu de tout le projet.

---

## 📋 Étape 0 : Nettoyage des fichiers parasites (En terminal — 0 token LLM)

Avant d'utiliser Copilot, supprimez les fichiers morts et les verrous théoriques directement dans le terminal de VS Code :

```bash
# 1. Supprimer le fichier scorie à la racine
rm -f =

# 2. Supprimer les abstractions de sur-ingénierie qui verrouillent le robot
rm -f src/irobot/interfaces/protection.py
rm -f src/irobot/interfaces/robot_admission.py
rm -f src/irobot/interfaces/robot_supervision.py
rm -f src/irobot/interfaces/human_lifecycle.py
rm -f src/irobot/interfaces/human_follow_runtime.py
rm -f src/irobot/interfaces/human_follow_announcements.py
rm -f src/irobot/interfaces/human_follow_perception.py
rm -f src/irobot/interfaces/human_perception_contracts.py
rm -f src/irobot/interfaces/voice_protection.py
rm -f src/irobot/interfaces/mission_robot.py
rm -f src/irobot/interfaces/marker_calibration.py

# 3. Supprimer le harnais de tests virtuels isolés
rm -rf tests/isolated/
```

---

## 🚀 Prompt 1 : Détection ArUco dans le Pipeline Caméra Live

* **Conversation :** 🟢 **NOUVEAU CHAT**
* **Objectif :** Permettre à `CameraLivePerceptionPipeline` de détecter le marqueur ArUco (ID 1 de `DICT_4X4_50`) en direct et de renvoyer sa position (`left`/`center`/`right`) et une distance estimée.

```markdown
#file:src/irobot/hardware/camera/camera_live_pipeline.py
#file:src/irobot/interfaces/aruco_marker_decoder.py
#file:src/irobot/config/settings.py

Dans `camera_live_pipeline.py`, intègre la détection ArUco en direct :
1. Dans `__init__`, instancie `OpenCVArucoMarkerDecoder` avec l'identité configurée dans `settings.human_marker_identity` (défaut : famille "aruco", dictionnaire "DICT_4X4_50", identifiant "1").
2. Dans `_process_frame(frame_rgb)`, si la cible demandée est "marker" ou "me" (ou par défaut si aucun filtre balle n'est actif) :
   - Convertis l'image en niveaux de gris et passe-la à `decoder.detect(grayscale)`.
   - Si le marqueur est détecté (`VALID`) :
     * Calcule le centre X des 4 coins par rapport à la largeur de l'image (480px) :
       - X < 180px -> "left"
       - X > 300px -> "right"
       - Sinon -> "center"
     * Estime la distance en cm en fonction de la largeur apparente du carré en pixels (loi simple sténopé : `distance = (largeur_reelle_cm * focale_px) / largeur_pixels` avec largeur=8cm et focale=600px).
     * Renvoie `ObjectDetection(label="marker_1", position=pos, distance_cm=dist, confidence=1.0)`.
3. Conserve la compatibilité avec la détection de balle existante. Renvoie uniquement le code modifié.
```

---

## 🚀 Prompt 2 : Déblocage de « suis-moi » et Parser instantané (0 ms)

* **Conversation :** 🟢 **NOUVEAU CHAT**
* **Objectif :** Supprimer les verrous qui rejettent « suis-moi » et faire réagir le robot instantanément sans attendre le LLM.

```markdown
#file:src/irobot/interfaces/intent_parser.py
#file:src/irobot/interfaces/plan_guards.py
#file:src/irobot/interfaces/language_controller.py

Débloque le use-case « suis-moi » et supprime les verrous de refus :
1. Dans `plan_guards.py` :
   - Supprime le refus `follow_request_refusal()` qui renvoie `human_capability_unavailable`.
   - Autorise l'intention `follow_person`.
2. Dans `intent_parser.py` :
   - Ajoute `follow_person` dans `ALLOWED_INTENTS`.
   - Dans `parse()`, intercepte directement les phrases contenant "suis-moi", "suis moi", "suivez-moi" et renvoie instantanément `Intent(name="follow_person", target="marker", confidence=1.0, raw_text=text)`.
   - Dans `IntentValidator.validate()`, valide `follow_person`.
3. Dans `language_controller.py` :
   - Supprime le bloc de rejet `if intent.name in {"follow_person", ...}`.
   - Associe `follow_person` à l'exécution de la skill de suivi correspondante.
Renvoie uniquement les diffs des fonctions modifiées.
```

---

## 🚀 Prompt 3 : Comportement de Suivi Déterministe (Sans recul)

* **Conversation :** 🟢 **NOUVEAU CHAT**
* **Objectif :** Raccorder le planner et s'assurer que le suivi garde la cible à ~1,2 m et stoppe net sans reculer ni tourner en rond en cas de perte.

```markdown
#file:src/irobot/domain/orchestrator/planner.py
#file:src/irobot/domain/skills/behaviors/follow_target.py

Adapte le comportement de suivi pour l'intention `follow_person` :
1. Dans `planner.py` :
   - Ajoute le mapping `"follow_person": ["follow_target"]` dans `INTENT_TO_SKILLS`.
2. Dans `follow_target.py` :
   - Lorsque la cible est le marqueur ArUco :
     * Si position == "center" et distance > 120 cm : avance (`forward`).
     * Si position == "left" : pivote doucement à gauche (`left`).
     * Si position == "right" : pivote doucement à droite (`right`).
     * Si distance <= 120 cm (zone de confort) : arrêt (`stop`). STRICTEMENT AUCUN RECUL.
     * Si le marqueur n'est plus détecté : arrêt immédiat (`stop`). Ne pas effectuer de balayage ou rotation sur place.
Renvoie uniquement les diffs nécessaires.
```

---

## 🚀 Prompt 4 : Nettoyage final du Runtime et Priorité du « Stop »

* **Conversation :** 🟢 **NOUVEAU CHAT**
* **Objectif :** Nettoyer les imports des fichiers supprimés à l'étape 0 et s'assurer que « stop » coupe les moteurs dans le thread principal en continu.

```markdown
#file:src/irobot/interfaces/voice_runtime.py
#file:src/irobot/interfaces/robot_controller.py

Nettoie les références aux anciens modules supprimés et garantit la réactivité du stop :
1. Dans `voice_runtime.py` :
   - Supprime les imports de `protection.py`, `human_follow_runtime.py`, `voice_protection.py`.
   - Simplifie la classe `VoiceRuntime` : supprime les mixins de protection devenus inutiles.
   - Dans `handle_transcript()` : confirme que toute détection du mot "stop", "arrête", "halte" ou "pause" appelle immédiatement `self.robot.stop()` et `self._request_emergency_stop()`, et stoppe la mission en cours.
2. Dans `robot_controller.py` :
   - Supprime les imports de `robot_admission`, `robot_supervision` et le mode protégé complexe.
   - Conserve le contrôle des mouvements temporisés `_run_motion_for()`, la détection d'obstacle par ultrason et l'arrêt d'urgence instantané `stop()`.
Renvoie les fichiers allégés et fonctionnels.
```

---

## 🧪 Étape Finale : Validation et Roulage sur le Pi

Une fois les 4 prompts appliqués :

1. **Lancer les tests unitaires :**
   ```bash
   uv run pytest -q tests/unit/
   ```
2. **Tester la caméra et la détection de votre marqueur ID 1 :**
   ```bash
   uv run marker-detect-live
   ```
3. **Lancer le suivi complet sur le robot :**
   ```bash
   uv run robot
   ```
   * Dites : **« Suis-moi »** ➔ Le robot vous détecte et avance derrière vous.
   * Dites : **« Stop »** ou **« Arrête »** ➔ Le robot coupe immédiatement ses moteurs.
