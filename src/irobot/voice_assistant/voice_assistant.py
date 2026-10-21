import argparse
import json
import os
import re
import subprocess
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import requests
import vosk

RATE = 16000
CARD_NAME = "wm8960"
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-fr-0.22")
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "ministral-3-3b"
LLM_TIMEOUT = 120

SYSTEM_PROMPT = (
    "Tu es un assistant vocal embarqué sur un Raspberry Pi. "
    "Réponds de manière concise et en français."
)


def _run_command(args):
    """Exécute une commande externe et retourne le résultat texte."""
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def find_wm8960_card():
    """Retourne l'index ALSA de la carte WM8960, ou None."""
    out = _run_command(["arecord", "-l"])
    if out is None:
        return None
    for line in out.splitlines():
        m = re.search(r"card (\d+):\s*(\S+)", line)
        if m and CARD_NAME in m.group(2).lower():
            return int(m.group(1))
    return None


def detect_bluetooth_input_device():
    """Tente de trouver un périphérique audio Bluetooth comme source microphone.

    La détection est volontairement tolérante : on vérifie d'abord les sources
    PulseAudio/PipeWire, puis la liste ALSA. Si rien n'est trouvé, on retourne None.
    """
    for cmd in (["pactl", "list", "short", "sources"], ["pacmd", "list-sources"], ["arecord", "-L"]):
        out = _run_command(cmd)
        if out is None:
            continue
        for line in out.splitlines():
            lowered = line.lower()
            if any(token in lowered for token in ("bluez", "bluetooth", "headset", "hfp")):
                return "default"
    return None


def resolve_input_device(device_name: str | None):
    """Résout le device d'entrée audio à utiliser.

    - auto : privilégie le casque Bluetooth si détecté, sinon WM8960, sinon default
    - wm8960 : force la carte ReSpeaker
    - bluetooth : force le micro Bluetooth si disponible
    - default : utilise la source audio par défaut du système
    - sinon : on considère la chaîne comme un device ALSA explicite
    """
    if device_name and device_name != "auto":
        if device_name == "wm8960":
            card = find_wm8960_card()
            if card is not None:
                return f"plughw:{card},0"
            raise RuntimeError("Aucune carte WM8960 détectée.")
        if device_name == "bluetooth":
            bt = detect_bluetooth_input_device()
            if bt is not None:
                return bt
            raise RuntimeError("Aucun casque Bluetooth détecté comme source audio.")
        return device_name

    bt = detect_bluetooth_input_device()
    if bt is not None:
        return bt

    card = find_wm8960_card()
    if card is not None:
        return f"plughw:{card},0"

    return "default"


def transcribe_loop(device):
    """Lit le flux brut du microphone et le transmet à Vosk."""
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

    model = vosk.Model(MODEL_PATH)
    rec = vosk.KaldiRecognizer(model, RATE)
    print(f"(parle dans le micro — device: {device} — Ctrl+C pour quitter)\n", flush=True)

    bytes_per_chunk = 8000
    while True:
        raw = proc.stdout.read(bytes_per_chunk)
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


def main():
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
    args = parser.parse_args()

    try:
        device = resolve_input_device(args.input_device)
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)

    if device == "default":
        print(
            "Aucun microphone matériel détecté (WM8960 ou Bluetooth). "
            "Le système va tenter d'utiliser le périphérique audio par défaut."
        )

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


if __name__ == "__main__":
    main()