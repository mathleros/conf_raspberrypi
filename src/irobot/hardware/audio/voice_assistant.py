from contextlib import contextmanager
import json
import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import requests

try:
    import vosk
except ModuleNotFoundError:  # pragma: no cover - tests/macOS
    vosk = None

from irobot.interfaces.voice_runtime import main as voice_runtime_main

RATE = 16000
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-fr-0.22")
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5-1.5b")
LLM_TIMEOUT = 120

SYSTEM_PROMPT = (
    "Tu es un assistant vocal embarqué sur un Raspberry Pi. "
    "Réponds de manière concise et en français."
)


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


def main() -> None:
    """Compatibilité CLI: redirige vers le runtime vocal unifié."""
    voice_runtime_main()


if __name__ == "__main__":
    main()