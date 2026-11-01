"""Public voice runtime and CLI; hardware and language services stay isolated."""

from __future__ import annotations

import argparse
import logging
import re
import sys
import threading
import time
from typing import Any

from irobot.config.settings import load_runtime_settings
from irobot.interfaces.intent_parser import Intent
from irobot.interfaces.plan_guards import is_pure_stop, fold, follow_request_refusal
from irobot.interfaces import voice_llm
from irobot.interfaces.voice_llm import LLMWarmup, warm_up_llm, warm_up_llm_async
from irobot.interfaces.voice_llm_transport import (
    _post_llm_chat,
    reset_response_format_cache,
    llm_warmup_wait_seconds,
    llm_response_format_mode,
)
from irobot.interfaces.voice_plan import VoicePlanMixin
from irobot.interfaces.voice_execution import VoiceExecutionMixin


def ask_llm_for_intent_plan_with_trace(text: str) -> tuple[list[Intent], dict[str, Any]]:
    return voice_llm.ask_llm_for_intent_plan_with_trace(text, post=_post_llm_chat)


def ask_llm_for_intent_plan(text: str) -> list[Intent]:
    intents, _ = ask_llm_for_intent_plan_with_trace(text)
    return intents


def transcribe_loop(device: str):
    from irobot.hardware.audio.voice_input import transcribe_loop as transcribe

    yield from transcribe(device)


def resolve_input_device(device: str) -> str:
    from irobot.hardware.audio.audio_utils import resolve_input_device as resolve

    return resolve(device)


def build_hardware_runtime() -> dict[str, Any]:
    settings = load_runtime_settings()
    if settings.protection_presence == "present":
        raise RuntimeError("Protection declared present: no qualified real P5 adapter; live assembly refused")
    from irobot.hardware.voice_runtime_factory import build_hardware_runtime as build

    return build(settings=settings)


class VoiceRuntime(VoicePlanMixin, VoiceExecutionMixin):
    """Microphone/text -> validated intents -> interruptible skill execution."""

    def _ask_plan(self, text: str) -> tuple[list[Intent], dict[str, Any]]:
        return ask_llm_for_intent_plan_with_trace(text)

    def _emergency_stop_requested(self) -> bool:
        if self._emergency_event.is_set():
            return True
        detector = getattr(self.robot, "is_emergency_stop_requested", None)
        if not callable(detector):
            return False
        try:
            return bool(detector())
        except Exception:
            logging.getLogger(__name__).exception("Impossible de lire l'arret d'urgence")
            return True

    def _safe_stop(self) -> None:
        stop = getattr(self.robot, "stop", None)
        if not callable(stop):
            return
        try:
            stop()
        except Exception:
            logging.getLogger(__name__).exception("Impossible d'arreter le robot")

    def handle_text_as_plan(self, text: str):
        return self._handle_text_as_plan(text)

    def listen_once(self):
        device = resolve_input_device(self.input_device)
        for text in transcribe_loop(device):
            print(f"\n[VOIX] {text}", flush=True)
            self._clear_emergency_stop()
            result = self.handle_text_as_plan(text)
            print(f"[RUNTIME] {result}", flush=True)
            return result
        return {"status": "no_transcript"}

    def _call_robot(self, method: str) -> None:
        func = getattr(self.robot, method, None)
        if callable(func):
            try:
                func()
            except Exception:
                logging.getLogger(__name__).exception("Echec de la commande robot %s", method)

    def _clear_emergency_stop(self) -> None:
        self._emergency_event.clear()
        self._call_robot("clear_emergency_stop")

    def _request_emergency_stop(self) -> None:
        self._emergency_event.set()
        if callable(getattr(self.robot, "request_emergency_stop", None)):
            self._call_robot("request_emergency_stop")
        else:
            self._safe_stop()

    def mission_running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _is_stop_phrase(self, text: str) -> bool:
        return is_pure_stop(text) or re.search(
            r"\b(?:stop|arrete|arret|halte|halt|pause)\b", fold(text),
        ) is not None

    def _mission_worker(self, text: str) -> None:
        try:
            self.last_result = self.handle_text_as_plan(text)
            print(f"[RUNTIME] {self.last_result}", flush=True)
        except Exception as exc:
            self.last_result = {"status": "failed", "error": str(exc)}
            print(f"[RUNTIME] erreur mission : {exc}", flush=True)
            self._safe_stop()

    def handle_transcript(self, text: str):
        """Stop immédiat pendant une mission, sinon démarre une nouvelle mission."""
        if self._is_stop_phrase(text):
            try:
                if self.robot is not None:
                    self.robot.stop()
            finally:
                self._request_emergency_stop()
                self.mission.abort("emergency stop")
            print("[RUNTIME] Arrêt d'urgence demandé.", flush=True)
            return None
        refusal = follow_request_refusal(text)
        if refusal:
            return {"status": "rejected", "reason": refusal}
        if self.mission_running():
            print("[RUNTIME] Mission en cours : phrase ignorée (dis « stop » pour arrêter).", flush=True)
            return None

        # Effacé ici (thread principal) et non dans le worker pour ne pas écraser un stop tardif.
        self._clear_emergency_stop()
        if not self.threaded:
            self.last_result = self.handle_text_as_plan(text)
            print(f"[RUNTIME] {self.last_result}", flush=True)
            return self.last_result
        self._worker = threading.Thread(
            target=self._mission_worker,
            args=(text,),
            name="mission-worker", daemon=True,
        )
        self._worker.start()
        return None

    def listen_forever(self):
        device = resolve_input_device(self.input_device)
        try:
            for text in transcribe_loop(device):
                print(f"\n[VOIX] {text}", flush=True)
                self.handle_transcript(text)
        except KeyboardInterrupt:
            print("\nInterruption clavier : arrêt du runtime vocal.")
            self._abort_mission()

    def _abort_mission(self) -> None:
        self._request_emergency_stop()
        worker = self._worker
        if worker is not None and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=2.0)
        self._safe_stop()

    def close(self) -> None:
        """Arrête proprement les périphériques matériels et les threads d'arrière-plan"""
        self._abort_mission()
        try:
            if self.perception is not None and hasattr(self.perception, "close"):
                self.perception.close()
        finally:
            if self.robot is not None and hasattr(self.robot, "stop"):
                self.robot.stop()


def _parse_args() -> argparse.Namespace:
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
    parser.add_argument(
        "--text",
        default=None,
        help="Traite cette phrase (sans micro) puis s'arrête.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    runtime = None
    try:
        warmup = LLMWarmup().start() if not args.no_llm else None
        hardware = build_hardware_runtime()
        runtime = VoiceRuntime(
            robot=hardware["robot"],
            camera=hardware["camera"],
            sensor=hardware["sensor"],
            perception=hardware["perception"],
            input_device=args.input_device,
            use_llm=not args.no_llm,
        )
        runtime.warmup = warmup
        # Une seule commande : la vraie requête attend le préchauffage ; écoute continue : arrière-plan.
        runtime.wait_for_warmup = bool(args.once or args.text)
        if args.text:
            runtime._clear_emergency_stop()
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
        if runtime is not None:
            runtime.close()


if __name__ == "__main__":
    main()
