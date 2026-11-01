# Rapport de Revue de Code & Plan de Simplification — Suivi Humain ArUco (« Suis-moi »)

**Date :** 1er novembre 2026  
**Projet :** `irobot` / Banc d'essai robotique autonome Raspberry Pi 5  
**Objet :** Déblocage opérationnel rapide du use-case « Suis-moi » (ArUco + Arrêt vocal) et élimination de la sur-ingénierie logicielle.

---

## 1. Diagnostic Global : Constat de Sur-Ingénierie (Over-Engineering)

L'inspection de la version exportée (v6) révèle une dérive architecturale majeure :
Pour satisfaire un cadre théorique de sûreté industrielle (spécifications Lot A / SH-01 à SH-11), plus de 2 500 lignes de code d'abstractions contractuelles ont été greffées au projet (`protection.py`, `human_lifecycle.py`, `robot_admission.py`, `robot_supervision.py`, etc.).

### Conséquences directes sur le robot physique :
1. **Verrouillage logiciel actif :** Le code est configuré pour refuser formellement tout suivi humain :
   * `plan_guards.py:requests_human_follow()` intercepte « suis-moi » et renvoie systématiquement `human_capability_unavailable`.
   * `language_controller.py` rejette immédiatement l'intention `follow_person`.
   * `voice_runtime_factory.py` bloque le démarrage dès que `protection_presence == "present"` faute d'adaptateur physique P5 certifié.
2. **Rupture matérielle de la chaîne de perception :**
   * Le module caméra en temps réel (`camera_live_pipeline.py`) ne traite que les balles de couleur rouge/jaune.
   * Le décodage ArUco existe (`aruco_marker_decoder.py`) mais est isolé dans un outil de diagnostic graphique (`marker_diagnostic.py`), sans lien avec les actionneurs moteurs.
3. **Complexité disproportionnée :**
   * Près de 35 fichiers d'interfaces, de contrats et de tests virtuels ont été ajoutés pour prouver en simulation que le robot refuse de rouler tant qu'un arrêt d'urgence matériel indépendant n'est pas qualifié.

---

## 2. Volet 1 : Ce qu'il reste à faire pour atteindre le use-case « Suis-moi »

Pour tester immédiatement le suivi du marqueur ArUco (ID 1 de `DICT_4X4_50`) avec arrêt vocal sans latence, 4 interventions directes sont nécessaires :

```text
Entrée Vocale ("suis-moi" / "stop")
       │
       ▼
  IntentParser (Regex directes : 0 ms)
       │
       ├─► "stop" / "arrête"  ──► RobotController.request_emergency_stop() ──► Arrêt immédiat (0 ms)
       │
       └─► "suis-moi"         ──► Skill follow_target
                                      ▲
                                      │ (Écart X, Distance estimée)
                                      │
                         CameraLivePerceptionPipeline (Décodage OpenCV ArUco)
```

### 1. Lever les verrous logiciels de refus
* Supprimer la fonction de blocage `follow_request_refusal()` dans `plan_guards.py`.
* Valider `follow_person` dans `IntentValidator.validate()` et `language_controller.py`.

### 2. Intégrer la détection ArUco dans le flux caméra en direct
* Dans `camera_live_pipeline.py`, brancher `OpenCVArucoMarkerDecoder` sur les trames Picamera2 640×480.
* Calculer à chaque frame :
  * **L'orientation horizontale** : centre X du carré par rapport à la zone centrale (gauche si $X < 180\text{ px}$, droite si $X > 300\text{ px}$, centre sinon).
  * **La distance estimée** : basée sur la largeur apparente en pixels ($D = \frac{\text{largeur\_réelle\_cm} \times \text{focale\_px}}{\text{largeur\_pixels}}$).
* Publier une détection typée : `ObjectDetection(label="marker_1", position=pos, distance_cm=dist)`.

### 3. Ajuster le comportement de suivi (Zéro recul)
* Dans `follow_target.py` :
  * Si la cible est le marqueur et la distance $> 120\text{ cm}$ : avance (`forward`).
  * Si le marqueur est désaxé : pivote doucement (`left` ou `right`).
  * Si la distance $\le 120\text{ cm}$ : arrêt (`stop`). **Strictement aucun recul.**
  * Si le marqueur est perdu : arrêt immédiat (`stop`). **Aucune rotation folle sur place.**

### 4. Réactivité instantanée de l'arrêt d'urgence
* Le mot « stop », « arrête » ou « halte » est déjà intercepté localement par `is_pure_stop()`.
* Garantir que l'écoute Vosk dans le thread principal coupe instantanément les PWM moteur sans attendre une fin de temporisation.

---

## 3. Volet 2 : Plan d'Élagage et de Simplification du Code

Pour rendre le projet lisible et maintenable par un développeur seul, il convient de supprimer la bureaucratie de spécification et de fusionner les modules éclatés.

### 1. Fichiers à supprimer immédiatement (Gain : > 2 500 lignes)

| Fichier / Dossier | Rôle initial | Raison de la suppression |
|---|---|---|
| `src/irobot/interfaces/protection.py` | Contrat de 17 préconditions (`HumanConditions`, P5) | Pure abstraction théorique sans matériel associé, bloque les moteurs. |
| `src/irobot/interfaces/robot_admission.py` | Gestion de jetons d'armement de mission | Inutile pour un prototype 2WD mono-utilisateur. |
| `src/irobot/interfaces/robot_supervision.py` | Surveillance complexe des cycles de contrôle | Sur-ingénierie mimant un automate de sécurité industrielle. |
| `src/irobot/interfaces/human_lifecycle.py` | Machine d'états à 6 phases d'acquisition | Empêche le départ tant que 3 trames synthétiques ne sont pas acquises. |
| `src/irobot/interfaces/human_follow_runtime.py` | Seam intermédiaire de session humaine | Couche d'indirection superflue sans pilotage moteur réel. |
| `src/irobot/interfaces/human_follow_announcements.py` | Générateur d'annonces vocales rigides | Génère des messages superflus au lieu de se concentrer sur l'action. |
| `src/irobot/interfaces/human_follow_perception.py` | Validation de trames opaques | Abstraction redondante entre la caméra et le contrôleur. |
| `src/irobot/interfaces/human_perception_contracts.py` | Déclarations de protocoles dupliquées | Doublon partiel de `human_perception.py`. |
| `src/irobot/interfaces/voice_protection.py` | Mixin de levée d'exceptions `ProtectionFault` | Bloque les commandes vocales naturelles. |
| `src/irobot/interfaces/mission_robot.py` | Façade restreinte pour actionneurs | Interdit les appels directs aux méthodes du robot. |
| `src/irobot/interfaces/marker_calibration.py` | Outils de damier de calibration d'échecs | Inutile pour une estimation de distance relative par ArUco. |
| `tests/isolated/` (dossier complet) | Harnais de tests virtuels avec audit Unix | Tests créés pour vérifier que le code refuse d'accéder au matériel. |
| Fichier `=` à la racine | Scorie de build `llama.cpp` | Fichier orphelin accidentel. |

### 2. Rationalisation et regroupements

1. **Suppression de la dépendance LLM pour « suis-moi » :**
   * Les modèles 1,5B locaux mettent entre 4 et 8 secondes à répondre sur Raspberry Pi 5.
   * En routant « suis-moi » directement par regex dans `IntentParser`, la décision est prise en **moins de 1 ms**, sans chauffer le CPU ni saturer la RAM.
2. **Unification des comportements de suivi :**
   * `follow_object.py` et `follow_target.py` doivent converger vers une logique unique : la source de perception change (balle de couleur vs marqueur ArUco), mais l'asservissement angulaire et longitudinal reste le même.
3. **Consolidation de `VoiceRuntime` :**
   * Les mixins éclatés (`voice_state.py`, `voice_plan.py`, `voice_execution.py`) peuvent être regroupés pour offrir un point d'entrée unique clair et facile à déboguer.

---

## 4. Architecture Cible Simplifiée (Pragmatique & Fonctionnelle)

L'architecture épurée finale tient en une arborescence minimale et robuste :

```text
src/irobot/
├── config/
│   ├── settings.py                # Chargement TOML (seuils, vitesses, ID ArUco = 1)
├── hardware/
│   ├── smart_car/smart_car.py     # Contrôle PWM L298N + Capteur ultrason HC-SR04
│   ├── camera/
│   │   ├── camera_live_pipeline.py# Thread Picamera2 (Couleur + ArUco en direct)
│   ├── audio/
│   │   ├── voice_input.py         # Capture ALSA + Reconnaissance Vosk (STT local)
├── interfaces/
│   ├── robot_controller.py        # Contrôle moteur cadencé à 20 ms + Arrêt d'urgence
│   ├── intent_parser.py           # Parsing regex instantané ("stop", "suis-moi", etc.)
│   ├── voice_runtime.py           # Boucle principale : Écoute ──► Dispatch intention
└── domain/
    └── skills/
        ├── primitives/            # forward, backward, left, right, stop
        └── behaviors/
            └── follow_target.py   # Asservissement : garde la cible au centre à ~1,2 m
```

---

## 5. Livrables et Guides Associés

Le guide opérationnel contenant les prompts prêts à être copiés/collés dans VS Code (avec la stratégie de gestion des chats pour économiser les tokens) a été généré dans :

👉 **[`PROMPTS_COPILOT_SUIVI_ARUCO.md`](PROMPTS_COPILOT_SUIVI_ARUCO.md)**
