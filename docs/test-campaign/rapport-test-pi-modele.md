# Compte rendu de campagne Raspberry Pi — après audit V6

À copier dans le dossier de résultats créé en P01 du [plan de test](plan-test-pi-post-audit-v6.md). Remplir au fil de l'exécution ; ne pas modifier ce modèle pour y enregistrer une campagne.

## 1. Référence testée

- Identifiant / date UTC :
- Opérateur / observateur :
- Commit ou identifiant d'archive, modifications locales :
- Pi / RAM / OS / Python / uv :
- Modèle GGUF / empreinte / version llama.cpp / alias :
- Configuration LLM effective et éventuelles surcharges :
- Micro / périphérique / distance de parole / bruit :
- Alimentation Pi / batterie moteurs / charge début et fin :
- Caméra / montage / résolution / orientation :
- Balle(s), diamètre réel / focale :
- Configuration runtime / fusion ultrason :
- Sol / éclairage / zone dégagée / coupure moteurs :
- Dossier des preuves :
- Campagne liée après redémarrage :

## 2. Exécution

Valeurs : **PASS / FAIL / BLOCKED / N/A justifié**. Pour chaque répétition, noter le journal, la trace et les mesures ; ajouter des lignes si nécessaire.

| Cas | Verdict | Répétitions / résultat mesuré | Journal / trace / vidéo | Anomalie |
|---|---|---|---|---|
| P01 Livraison et environnement | | | | |
| P02 Service/API/modèle | | | | |
| P03 Tests logiciels Pi | | Passés / ignorés / échecs / durée : | | |
| H01 HC-SR04 | | | | |
| H02 Calibration caméra | | | | |
| H03 Matériel réellement utilisé | | | | |
| H04 Audio/transcription | | 12 arrêts : | | |
| H05 Moteurs et fin de commande | | | | |
| H06 Obstacle | | 3 essais + obstacle initial : | | |
| H07 Arrêts et concurrence | | Local 3 / LLM 3 / Ctrl+C : | | |
| GATE A | | Autorisation au sol : | | |
| M01 Calibration mouvements | | 3 essais par commande : | | |
| M02 Défauts et séquence | | | | |
| L01 Froid/chaud et plans LLM | | 5 essais chauds + autres commandes : | | |
| L02 Hors périmètre | | 3 refus sans mouvement : | | |
| L03 Repli et stop sans serveur | | Service restauré : | | |
| E01 Recherche/approche | | Gauche / droite / apparition à 4 s : | | |
| E02 Suivi 30 s | | 3 essais : | | |
| E03 Perte et réacquisition | | Courte / longue / absence totale : | | |
| E04 Mission vocale 300 s | | 3 missions : | | |
| E05-stop | | | | |
| E05-obstacle | | | | |
| E05-clavier | | | | |
| GATE B | | Bout en bout : | | |
| Q01 Endurance et redémarrage | | E04 après redémarrage : | | |
| Q02 Fusion optionnelle | | | | |
| Q03 Réserves examinées | | | | |

## 3. Mesures

### Capteurs et calibration

| Capteur / commande | Consigne réelle | Mesures / moyenne / dispersion | Erreur | Verdict |
|---|---:|---|---|---|
| HC-SR04 | 10 cm | | | |
| HC-SR04 | 20 cm | | | |
| HC-SR04 | 50 cm | | | |
| HC-SR04 | 100 cm | | | |
| Caméra | 50 cm | | | |
| Caméra | 100 cm | | | |
| Caméra | 150 cm | | | |
| Caméra | 200 cm | | | |
| Avance | 10 cm | R1 / R2 / R3 : | | |
| Avance | 20 cm | R1 / R2 / R3 : | | |
| Avance | 50 cm | R1 / R2 / R3 : | | |
| Recul | 10 cm | R1 / R2 / R3 : | | |
| Droite | 45° | R1 / R2 / R3 : | | |
| Droite | 90° | R1 / R2 / R3 : | | |
| Gauche | 90° | R1 / R2 / R3 : | | |

### Arrêts

Ajouter une ligne par essai, y compris les échecs. Séparer délai acoustique/Vosk et délai après transcription.

| Essai | Fin de parole → arrêt | `[VOIX]` → arrêt | Obstacle → arrêt | Résultat final / événement | Arrêt réel / reprise ? |
|---|---:|---:|---:|---|---|
| | | | | | |

### LLM

| Essai | Source / plan conforme ? | Préchauffage / attente | Latence LLM | Requêtes / format | Tokens / débit serveur | Erreur / repli |
|---|---|---|---:|---|---|---|
| Froid | | | | | | |
| Chaud 1 | | | | | | |
| Chaud 2 | | | | | | |
| Chaud 3 | | | | | | |
| Chaud 4 | | | | | | |
| Chaud 5 | | | | | | |

- Latence chaude médiane / maximum :
- Replis / total d'essais et causes :
- Faux rejets ou paramètres incorrects :

### Missions de cinq minutes

Pour chaque mission, joindre les 10 mesures stabilisées minimum (instant, distance réelle, écart), la durée d'approche et la durée de suivi séparées.

| Mission | Plan LLM conforme | Approche (s) | Suivi réel (s) | Mesures à 85–115 cm / total | Arrêt final + 10 s immobile | Résultat / trace |
|---|---|---:|---:|---|---|---|
| E04-1 | | | | | | |
| E04-2 | | | | | | |
| E04-3 | | | | | | |
| Après redémarrage | | | | | | |

### Ressources

| Instant | CPU | RAM / swap | Température | `get_throttled` actif / historique | Observation |
|---|---|---|---|---|---|
| Repos | | | | | |
| Mission 1 | | | | | |
| Mission 3 | | | | | |
| Après missions | | | | | |

## 4. Anomalies et décision

| Identifiant | Cas / reproduction | Attendu / observé | Impact sécurité ou fonctionnel | Preuves | Correction / retest |
|---|---|---|---|---|---|
| | | | | | |

- Configuration finale sauvegardée :
- Réserves connues / options non livrées / dérogations explicitement acceptées :
- État final du service LLM / moteurs coupés / runtimes fermés :
- Décision : **GO / NO-GO** :
- Justification (tout cas obligatoire FAIL ou BLOCKED impose NO-GO) :
- Validation opérateur / observateur / date :
