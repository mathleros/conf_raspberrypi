from __future__ import annotations

import re
import subprocess

CARD_NAME = "wm8960"


def _run_command(args: list[str]) -> str | None:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def find_wm8960_card() -> int | None:
    out = _run_command(["arecord", "-l"])
    if out is None:
        return None
    for line in out.splitlines():
        match = re.search(r"card (\d+):\s*(\S+)", line)
        if match and CARD_NAME in match.group(2).lower():
            return int(match.group(1))
    return None


def detect_bluetooth_input_device() -> str | None:
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
