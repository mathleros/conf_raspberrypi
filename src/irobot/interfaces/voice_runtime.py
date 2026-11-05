"""Public voice runtime; the CLI and hardware assembly live in irobot.app."""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.interfaces.command_service import CommandService
from irobot.interfaces.perception_contracts import ObjectPerceptionPipeline
from irobot.interfaces.plan_guards import fold, is_pure_stop


class VoiceRuntime:
    """Microphone/text adapter with immediate stop handling."""

    def __init__(
        self,
        *,
        robot=None,
        camera=None,
        sensor=None,
        perception: ObjectPerceptionPipeline | None = None,
        registry: SkillRegistry | None = None,
        input_device: str = "auto",
        use_llm: bool = True,
        trace_dir: str | None = None,
        threaded: bool = True,
    ):
        self.robot = robot
        self.input_device = input_device
        self.threaded = threaded
        self._worker: threading.Thread | None = None
        self.last_result: Any = None
        self.camera = camera
        self.perception = perception
        self.command_service = CommandService(
            robot=robot,
            camera=camera,
            sensor=sensor,
            perception=perception,
            registry=registry,
            use_llm=use_llm,
            trace_dir=trace_dir,
        )
        self._emergency_event = self.command_service.emergency_event

    def handle_text_as_plan(self, text: str):
        return self.command_service.handle_text(text)

    def _transcripts(self):
        # Import paresseux : la dépendance audio n'existe pas hors Raspberry Pi.
        from irobot.hardware.audio.audio_utils import resolve_input_device
        from irobot.hardware.audio.voice_input import transcribe_loop

        return transcribe_loop(resolve_input_device(self.input_device))

    def listen_once(self):
        for text in self._transcripts():
            print(f"\n[VOIX] {text}", flush=True)
            self.clear_emergency_stop()
            result = self.handle_text_as_plan(text)
            print(f"[RUNTIME] {result}", flush=True)
            return result
        return {"status": "no_transcript"}

    def clear_emergency_stop(self) -> None:
        self._emergency_event.clear()
        clear = getattr(self.robot, "clear_emergency_stop", None)
        if callable(clear):
            try:
                clear()
            except Exception:
                logging.getLogger(__name__).exception("Echec de la commande robot clear_emergency_stop")

    def _request_emergency_stop(self) -> None:
        self._emergency_event.set()
        request = getattr(self.robot, "request_emergency_stop", None)
        if callable(request):
            try:
                request()
            except Exception:
                logging.getLogger(__name__).exception("Echec de la commande robot request_emergency_stop")
        else:
            self.command_service.safe_stop()

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
            self.command_service.safe_stop()

    def handle_transcript(self, text: str):
        """Stop immédiat pendant une mission, sinon démarre une nouvelle mission."""
        if self._is_stop_phrase(text):
            try:
                if self.robot is not None:
                    self.robot.stop()
            finally:
                self._request_emergency_stop()
                self.command_service.mission_orchestrator.state_machine.abort("emergency stop")
            print("[RUNTIME] Arrêt d'urgence demandé.", flush=True)
            return None
        if self.mission_running():
            print("[RUNTIME] Mission en cours : phrase ignorée (dis « stop » pour arrêter).", flush=True)
            return None

        # Effacé ici (thread principal) et non dans le worker pour ne pas écraser un stop tardif.
        self.clear_emergency_stop()
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
        try:
            for text in self._transcripts():
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
        self.command_service.safe_stop()

    def close(self) -> None:
        """Interrompt la mission en cours ; la fermeture du matériel est faite par app.main()."""
        self._abort_mission()
