import argparse
from contextlib import contextmanager
import json
import os
import re
import subprocess
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import requests

try:
    import vosk
except ModuleNotFoundError:  # pragma: no cover - tests/macOS
    vosk = None

from irobot.hardware.smart_car.smart_car import SmartCar2WD
from irobot.hardware.audio.audio_utils import resolve_input_device
from irobot.interfaces.voice_runtime import main as voice_runtime_main

RATE = 16000
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-fr-0.22")
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "ministral-3-3b"
LLM_TIMEOUT = 120

SYSTEM_PROMPT = (
    "Tu es un assistant vocal embarqué sur un Raspberry Pi. "
    "Réponds de manière concise et en français."
)


class VoiceCarController:
    """Contrôle d'une voiture à partir de commandes vocales, en français ou anglais."""

    def __init__(self, default_speed: float = 0.5):
        self.car = SmartCar2WD()
        self.speed = max(0.0, min(1.0, default_speed))
        self.current_direction = "stop"
        self.car.set_speed(self.speed)

    @staticmethod
    def parse_duration(text: str) -> float:
        """Extrait la durée d'exécution depuis une commande vocale.

        Accepte des formules du type :
        - 'pendant 2 seconde'
        - 'for 2 seconds'
        - '2s'
        - '2.5 sec'
        """
        cleaned = text.lower().strip()

        patterns = [
            r"(?:pendant|pour|durant)\s*(\d+(?:[.,]\d+)?)\s*(?:seconde|secondes|sec|secs|s)\b",
            r"(?:for|during)\s*(\d+(?:[.,]\d+)?)\s*(?:second|seconds|sec|secs|s)\b",
            r"\b(\d+(?:[.,]\d+)?)\s*(?:s|sec|second|seconde|seconds|secondes)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                value = float(match.group(1).replace(",", "."))
                return max(0.1, value)
        return 1.0

    def _set_direction(self, direction: str) -> str:
        if direction == "forward":
            self.car.forward()
            self.current_direction = "forward"
            return f"Avance à {self.speed:.2f}."
        if direction == "backward":
            self.car.backward()
            self.current_direction = "backward"
            return f"Recule à {self.speed:.2f}."
        if direction == "left":
            self.car.left()
            self.current_direction = "left"
            return f"Tourne à gauche à {self.speed:.2f}."
        if direction == "right":
            self.car.right()
            self.current_direction = "right"
            return f"Tourne à droite à {self.speed:.2f}."
        if direction == "stop":
            self.car.stop()
            self.current_direction = "stop"
            return "Arrêt moteur."
        return "Commande inconnue."

    def _execute_direction(self, direction: str, duration: float = 1.0) -> str:
        self.car.set_speed(self.speed)
        self._set_direction(direction)
        if duration > 0:
            time.sleep(duration)
            self.car.stop()
            return f"Commande '{direction}' exécutée pendant {duration:.1f}s."
        self.car.stop()
        return f"Commande '{direction}' arrêtée immédiatement."

    def handle_text(self, text: str) -> str:
        cleaned = text.strip().lower()
        if not cleaned:
            return "Aucune commande reçue."

        duration = self.parse_duration(cleaned)

        if any(keyword in cleaned for keyword in ["plus vite", "go faster", "faster", "accelere", "accelerate", "augmente"]):
            self.speed = max(0.0, min(1.0, self.speed + 0.1))
            if self.current_direction != "stop":
                self._set_direction(self.current_direction)
            return f"Vitesse augmentée à {self.speed:.2f}."

        if any(keyword in cleaned for keyword in ["moins vite", "go slower", "slower", "ralenti", "decelerate", "baisse"]):
            self.speed = max(0.0, min(1.0, self.speed - 0.1))
            if self.current_direction != "stop":
                self._set_direction(self.current_direction)
            return f"Vitesse réduite à {self.speed:.2f}."

        if any(keyword in cleaned for keyword in ["stop", "arrêt", "arrete", "stop car", "halt", "pause"]):
            return self._set_direction("stop")

        if any(keyword in cleaned for keyword in ["avance", "avancer", "va tout droit", "go forward", "forward", "go", "move forward", "avant"]):
            return self._execute_direction("forward", duration)

        if any(keyword in cleaned for keyword in ["recule", "reculer", "go back", "backward", "back", "move backward", "arriere", "arrière"]):
            return self._execute_direction("backward", duration)

        if any(keyword in cleaned for keyword in ["gauche", "tourne a gauche", "turn left", "left", "left turn"]):
            return self._execute_direction("left", duration)

        if any(keyword in cleaned for keyword in ["droite", "tourne a droite", "turn right", "right", "right turn"]):
            return self._execute_direction("right", duration)

        for pattern in [r"vitesse\s*[:=]?\s*(0\.?\d+|1(?:\.0+)?)", r"speed\s*[:=]?\s*(0\.?\d+|1(?:\.0+)?)"]:
            match = re.search(pattern, cleaned)
            if match:
                self.speed = max(0.0, min(1.0, float(match.group(1))))
                self.car.set_speed(self.speed)
                if self.current_direction != "stop":
                    self._set_direction(self.current_direction)
                return f"Vitesse réglée à {self.speed:.2f}."

        return "Commande vocale non reconnue pour la voiture."

    def cleanup(self) -> None:
        self.car.stop()
        self.car.cleanup()


def transcribe_loop(device):
    """Lit le flux brut du microphone et le transmet à Vosk."""
    if vosk is None:
        raise RuntimeError("La dépendance 'vosk' est absente. Installez les paquets Raspberry Pi requis.")

    @contextmanager
    def _arecord_stream():
        args = [
            "arecord",
            "-D",
            device,
            "-f",
            "S16_LE",
            "-r",
            str(RATE),
            "-c",
            "1",
            "-t",
            "raw",
        ]
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        try:
            if proc.stdout is None:
                raise RuntimeError("Impossible d'ouvrir le flux audio arecord.")
            yield proc.stdout
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1.0)
            if proc.stdout is not None:
                proc.stdout.close()

    model = vosk.Model(MODEL_PATH)
    rec = vosk.KaldiRecognizer(model, RATE)
    print(f"(parle dans le micro — device: {device} — Ctrl+C pour quitter)\n", flush=True)

    bytes_per_chunk = 8000
    with _arecord_stream() as audio_stream:
        while True:
            raw = audio_stream.read(bytes_per_chunk)
            if not raw:
                break
            if rec.AcceptWaveform(raw):
                result = json.loads(rec.Result())
                text = result.get("text", "").strip()
                if text:
                    yield text
                    rec.Reset()


def ask_llm(text):
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 256,
        "stream": False,
    }
    try:
        resp = requests.post(LLM_URL, json=payload, timeout=LLM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"[erreur LLM] {exc}"


def legacy_main():
    parser = argparse.ArgumentParser(
        description="Assistant vocal : microphone Bluetooth/WM8960 → Vosk (STT) → Ministral 3 3B → stdout"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Transcrire une seule phrase puis s'arrêter (mode test unitaire)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Afficher la transcription sans interroger le LLM",
    )
    parser.add_argument(
        "--input-device",
        default="auto",
        choices=["auto", "bluetooth", "wm8960", "default"],
        help="Source audio utilisée pour l'enregistrement. 'auto' = Bluetooth si disponible, sinon ReSpeaker, sinon par défaut.",
    )
    parser.add_argument(
        "--car",
        action="store_true",
        help="Contrôle la smart-car via commandes vocales en français ou anglais (avance, recule, gauche, droite, stop, vitesse).",
    )
    parser.add_argument(
        "--car-speed",
        type=float,
        default=0.5,
        help="Vitesse de base de la voiture en mode contrôle vocal, entre 0.0 et 1.0.",
    )
    args = parser.parse_args()

    try:
        device = resolve_input_device(args.input_device)
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)

    if args.car:
        controller = VoiceCarController(default_speed=args.car_speed)
        try:
            for text in transcribe_loop(device):
                print(f"\n[VOIX] {text}", flush=True)
                action = controller.handle_text(text)
                print(f"[VOITURE] {action}", flush=True)
                if args.once:
                    return
        except KeyboardInterrupt:
            print("\nInterruption clavier : arrêt du contrôle vocal voiture.")
        finally:
            controller.cleanup()
        return

    for text in transcribe_loop(device):
        print(f"\n[VOIX] {text}", flush=True)
        if args.no_llm:
            if args.once:
                return
            continue
        print("[LLM…]", flush=True)
        start = time.time()
        answer = ask_llm(text)
        elapsed = time.time() - start
        print(f"[RÉPONSE ({elapsed:.1f}s)] {answer}", flush=True)
        if args.once:
            return


def main() -> None:
    """Compatibilité CLI: redirige vers le runtime vocal unifié."""
    voice_runtime_main()


if __name__ == "__main__":
    main()