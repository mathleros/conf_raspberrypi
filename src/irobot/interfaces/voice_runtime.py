"""Runtime vocal complet : Vosk + LLM + intention + exécution de skills.

Ce point d'entrée transforme la parole en texte, puis en `Intent`, puis en plan
complet de skills validé par `LanguageController`. Le LLM n'est pas autorisé à
piloter les GPIO directement : il ne produit qu'une intention structurée et
validée par le système.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from typing import Any

import requests

try:
    import vosk  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - macOS/tests
    vosk = None

from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.interfaces.intent_parser import Intent, IntentParser, IntentValidator
from irobot.interfaces.language_controller import LanguageController

RATE = 16000
CARD_NAME = "wm8960"
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-fr-0.22")
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "ministral-3-3b"
LLM_TIMEOUT = 120
SYSTEM_PROMPT = (
    "Tu es un interprète de commande robotique. "
    "Réponds UNIQUEMENT en JSON valide avec les clés suivantes : "
    "intent, target, parameters, confidence. "
    "Les intents autorisées sont : follow_red_ball, avoid_obstacle, "
    "move_forward, move_backward, turn_left, turn_right, stop."
)


def _run_command(args: list[str]):
    """Exécute une commande système et retourne stdout si elle réussit."""
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def find_wm8960_card() -> int | None:
    """Retourne l'index ALSA de la carte WM8960, ou None."""
    out = _run_command(["arecord", "-l"])
    if out is None:
        return None
    for line in out.splitlines():
        match = re.search(r"card (\d+):\s*(\S+)", line)
        if match and CARD_NAME in match.group(2).lower():
            return int(match.group(1))
    return None


def detect_bluetooth_input_device() -> str | None:
    """Tente de détecter un périphérique audio Bluetooth comme source microphone."""
    for cmd in (["pactl", "list", "short", "sources"], ["pacmd", "list-sources"], ["arecord", "-L"]):
        out = _run_command(cmd)
        if out is None:
            continue
        for line in out.splitlines():
            lowered = line.lower()
            if any(token in lowered for token in ("bluez", "bluetooth", "headset", "hfp")):
                return "default"
    return None


def resolve_input_device(device_name: str | None) -> str:
    """Résout le device d'entrée audio à utiliser."""
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


def transcribe_loop(device: str):
    """Lit le flux brut du microphone et le transmet à Vosk."""
    if vosk is None:
        raise RuntimeError("La dépendance 'vosk' est absente. Installez les paquets Raspberry Pi requis.")

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
    recognizer = vosk.KaldiRecognizer(model, RATE)
    print(f"(parle dans le micro — device: {device} — Ctrl+C pour quitter)\n", flush=True)

    bytes_per_chunk = 8000
    while True:
        raw = proc.stdout.read(bytes_per_chunk)
        if not raw:
            break
        if recognizer.AcceptWaveform(raw):
            result = json.loads(recognizer.Result())
            text = result.get("text", "").strip()
            if text:
                yield text
                recognizer.Reset()


def _parse_llm_json_payload(content: str) -> dict[str, Any] | None:
    """Extrait un objet JSON depuis une réponse LLM, y compris si elle est entourée de backticks."""
    cleaned = content.strip()
    if not cleaned:
        return None
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned.split("\n", 1)[1].strip() if "\n" in cleaned else cleaned[4:].strip()
    try:
        payload = json.loads(cleaned)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    return None


def ask_llm_for_intent(text: str) -> Intent:
    """Demande un JSON de type Intent au LLM local, puis reconstruit l'objet Intent."""
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
        response = requests.post(LLM_URL, json=payload, timeout=LLM_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        parsed = _parse_llm_json_payload(content)
        if not parsed:
            return IntentParser().parse(text)

        intent_name = str(parsed.get("intent") or parsed.get("name") or "unknown").strip()
        target = parsed.get("target")
        parameters = parsed.get("parameters") or {}
        confidence = float(parsed.get("confidence") or 0.0)
        return Intent(
            name=intent_name,
            target=str(target) if target is not None else None,
            parameters=dict(parameters),
            confidence=max(0.0, min(1.0, confidence)),
            raw_text=text,
        )
    except Exception:
        return IntentParser().parse(text)


class VoiceRuntime:
    """Pipeline complet : microphone -> Vosk -> Intent -> LanguageController -> skills."""

    def __init__(
        self,
        *,
        robot=None,
        camera=None,
        sensor=None,
        registry: SkillRegistry | None = None,
        input_device: str = "auto",
        use_llm: bool = True,
    ):
        self.robot = robot
        self.camera = camera
        self.sensor = sensor
        self.input_device = input_device
        self.use_llm = use_llm
        self.controller = LanguageController(
            robot=robot,
            camera=camera,
            sensor=sensor,
            registry=registry or SkillRegistry.default(),
        )
        self.parser = IntentParser()
        self.validator = IntentValidator()

    def _resolve_intent(self, text: str) -> Intent:
        if not self.use_llm:
            return self.parser.parse(text)

        llm_intent = ask_llm_for_intent(text)
        if self.validator.validate(llm_intent):
            return llm_intent
        return self.parser.parse(text)

    def handle_text(self, text: str):
        intent = self._resolve_intent(text)
        if not self.validator.validate(intent):
            return {"intent": intent, "status": "rejected", "reason": "intent not allowed"}
        return self.controller.handle_intent(intent)

    def listen_once(self):
        device = resolve_input_device(self.input_device)
        for text in transcribe_loop(device):
            print(f"\n[VOIX] {text}", flush=True)
            result = self.handle_text(text)
            print(f"[RUNTIME] {result}", flush=True)
            return result
        return {"status": "no_transcript"}

    def listen_forever(self):
        device = resolve_input_device(self.input_device)
        try:
            for text in transcribe_loop(device):
                print(f"\n[VOIX] {text}", flush=True)
                result = self.handle_text(text)
                print(f"[RUNTIME] {result}", flush=True)
        except KeyboardInterrupt:
            print("\nInterruption clavier : arrêt du runtime vocal.")


def main():
    parser = argparse.ArgumentParser(
        description="Runtime vocal complet : Vosk → intent → skills -> robot."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ecoute une seule phrase puis s'arrête.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Utilise le parseur local au lieu du LLM pour interpréter la commande.",
    )
    parser.add_argument(
        "--input-device",
        default="auto",
        choices=["auto", "bluetooth", "wm8960", "default"],
        help="Source audio utilisée pour l'enregistrement.",
    )
    args = parser.parse_args()

    try:
        runtime = VoiceRuntime(input_device=args.input_device, use_llm=not args.no_llm)
        if args.once:
            runtime.listen_once()
            return
        runtime.listen_forever()
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
