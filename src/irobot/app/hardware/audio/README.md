# Audio matériel

Ce package fournit les fonctions audio de bas niveau utilisées par le runtime
vocal. Il ne planifie pas les commandes et ne pilote pas le robot.

- `audio_utils.py` détecte les sources disponibles et résout le périphérique
  d'entrée (Bluetooth, WM8960 ou périphérique ALSA par défaut).
- `voice_input.py` capture le son avec `arecord` et le transcrit avec Vosk.

Le runtime vocal (`irobot.interfaces.voice_runtime`) assemble ces composants :
il choisit le périphérique, récupère les transcriptions, puis les transmet à
la logique d'interprétation.
