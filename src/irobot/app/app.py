"""Point d'entrée `voice-runtime` : assemble le matériel et le runtime vocal."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable

from irobot.app.interfaces.intent.llm_intent_parser import LLMWarmup
from irobot.app.interfaces.voice_runtime import VoiceRuntime
from irobot.common.config.settings import load_runtime_settings
from irobot.common.hardware.runtime_factory import (
    build_hardware_runtime,
    close_hardware_runtime,
    load_face_gallery,
)
from irobot.common.interfaces.wake_word import DEFAULT_WAKE_WORD


def _microphone_transcripts(input_device: str) -> Iterable[str]:
    # Import paresseux : la dépendance audio n'existe pas hors Raspberry Pi.
    from irobot.common.hardware.audio.audio_utils import resolve_input_device
    from irobot.common.hardware.audio.voice_input import transcribe_loop

    return transcribe_loop(resolve_input_device(input_device))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Runtime vocal complet : Vosk → intent → skills -> robot.",
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
    parser.add_argument(
        "--text",
        default=None,
        help="Traite cette phrase (sans micro) puis s'arrête.",
    )
    parser.add_argument(
        "--wake-word",
        default=DEFAULT_WAKE_WORD,
        help="Mot d'activation en écoute continue ; chaîne vide pour désactiver",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    runtime = None
    hardware = None
    try:
        warmup = LLMWarmup().start() if not args.no_llm else None
        settings = load_runtime_settings()
        hardware = build_hardware_runtime(settings=settings)
        runtime = VoiceRuntime(
            robot=hardware["robot"],
            camera=hardware["camera"],
            sensor=hardware["sensor"],
            perception=hardware["camera"],
            input_device=args.input_device,
            wake_word=args.wake_word,
            transcript_source=_microphone_transcripts,
            use_llm=not args.no_llm,
            settings=settings,
            gallery=load_face_gallery(settings),
        )
        runtime.command_service.warmup = warmup
        # Une seule commande : la vraie requête attend le préchauffage ; écoute continue : arrière-plan.
        runtime.command_service.wait_for_warmup = bool(args.once or args.text)
        if args.text:
            runtime.clear_emergency_stop()
            result = runtime.handle_text_as_plan(args.text)
            print(f"[RUNTIME] {result}", flush=True)
            return
        if args.once:
            runtime.listen_once()
            return
        runtime.listen_forever()
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)
    finally:
        try:
            if runtime is not None:
                runtime.close()
        finally:
            if hardware is not None:
                close_hardware_runtime(hardware)


if __name__ == "__main__":
    main()
