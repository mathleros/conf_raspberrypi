"""ALSA capture and lazy Vosk transcription; no planning or motor logic."""

import json
import os
import subprocess
from contextlib import contextmanager

RATE = 16000
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-fr-0.22")


@contextmanager


def _arecord_stream(device: str):
    """Ouvre un flux arecord et garantit son arrêt même en cas d'exception."""
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


def transcribe_loop(device: str):
    """Lit le flux brut du microphone et le transmet à Vosk."""
    try:
        import vosk
    except ModuleNotFoundError as exc:
        raise RuntimeError("La dépendance 'vosk' est absente. Installez les paquets Raspberry Pi requis.") from exc

    model = vosk.Model(MODEL_PATH)
    recognizer = vosk.KaldiRecognizer(model, RATE)
    print(f"(parle dans le micro — device: {device} — Ctrl+C pour quitter)\n", flush=True)

    bytes_per_chunk = 8000
    with _arecord_stream(device) as audio_stream:
        while True:
            raw = audio_stream.read(bytes_per_chunk)
            if not raw:
                break
            if recognizer.AcceptWaveform(raw):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    yield text
                    recognizer.Reset()
