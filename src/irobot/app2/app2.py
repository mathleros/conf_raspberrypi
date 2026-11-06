"""Point d'entrée de test `app2` : appelle directement les skills (sans LLM ni orchestrateur).

Exemples :
    python -m irobot.app2.app2 --behavior move --target forward --duration 2
    python -m irobot.app2.app2 --behavior search --target marker --duration 10
    python -m irobot.app2.app2 --behavior approach --target red_ball --duration 8
    python -m irobot.app2.app2 --behavior follow --target human --duration 20
    python -m irobot.app2.app2 --audio        # ex. « suis moi pendant vingt secondes »
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata

from irobot.common.config.settings import RuntimeSettings, load_runtime_settings
from irobot.common.domain.orchestrator.executor import SkillExecutor
from irobot.common.domain.orchestrator.registry import SkillRegistry
from irobot.common.domain.perception import PerceptionTarget
from irobot.common.domain.skills.base_skill import SkillContext, SkillResult
from irobot.common.domain.skills.blackboard_state import BlackboardState
from irobot.common.hardware.runtime_factory import (
    build_hardware_runtime,
    close_hardware_runtime,
)

MOVE_TARGETS = {
    "forward": "move_forward",
    "backward": "move_backward",
    "left": "turn_left",
    "right": "turn_right",
}
VISION_TARGETS = ("marker", "red_ball", "yellow_ball", "human")
BEHAVIORS = ("move", "search", "approach", "follow")

# Nom d'intention "historique" : FollowObjectSkill en déduit sa distance de consigne.
FOLLOW_INTENT_BY_TARGET = {
    "human": "follow_person",
    "red_ball": "follow_red_ball",
}

SEARCH_STEP_S = 0.08
SEARCH_SETTLE_S = 0.15


DEFAULT_DURATION_S = 1.0

# Mots-clés (sans accents) reconnus dans la transcription Vosk française.
_BEHAVIOR_STEMS = {
    "search": ("cherch", "trouv", "search", "find"),
    "approach": ("approch", "rapproch", "rejoin", "approach"),
    "follow": ("suis", "suit", "suiv", "poursu", "follow"),
}
_MOVE_WORDS = {
    "forward": ("avanc", "avant", "forward"),
    "backward": ("recul", "arriere", "backward"),
    "left": ("gauche", "left"),
    "right": ("droite", "right"),
}
_VISION_WORDS = {
    "red_ball": ("rouge", "red"),
    "yellow_ball": ("jaune", "yellow"),
    "marker": ("marqueur", "marker", "aruco", "tag"),
    "human": ("humain", "personne", "visage", "human", "moi"),
}


def _normalize_speech(text: str) -> list[str]:
    from irobot.common.interfaces.text_normalizer import fr_numbers_to_digits

    lowered = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in lowered if unicodedata.category(ch) != "Mn")
    return re.findall(r"[a-z0-9]+", fr_numbers_to_digits(stripped))


def _has_stem(tokens: list[str], stems: tuple[str, ...]) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in stems)


def _first_match(tokens: list[str], table: dict[str, tuple[str, ...]]) -> str | None:
    return next((name for name, stems in table.items() if _has_stem(tokens, stems)), None)


def _spoken_duration(tokens: list[str]) -> float:
    for index, token in enumerate(tokens[:-1]):
        if not token.isdigit():
            continue
        unit = tokens[index + 1]
        if unit.startswith("sec"):
            return float(token)
        if unit.startswith("min"):
            return float(token) * 60.0
    return DEFAULT_DURATION_S


def parse_voice_command(text: str) -> tuple[str, str, float] | None:
    """Transforme une phrase en (behavior, target, duration) ; None si incomplète ou ambiguë."""
    tokens = _normalize_speech(text)
    duration = _spoken_duration(tokens)
    behavior = _first_match(tokens, _BEHAVIOR_STEMS)
    if behavior is not None:
        target = _first_match(tokens, _VISION_WORDS)
        return (behavior, target, duration) if target else None
    target = _first_match(tokens, _MOVE_WORDS)
    return ("move", target, duration) if target else None


def _listen_for_command(input_device: str) -> tuple[str, str, float]:
    # Import paresseux : la dépendance audio n'existe pas hors Raspberry Pi.
    from irobot.common.hardware.audio.audio_utils import resolve_input_device
    from irobot.common.hardware.audio.voice_input import transcribe_loop

    transcripts = transcribe_loop(resolve_input_device(input_device))
    try:
        for text in transcripts:
            print(f"[APP2] entendu : « {text} »", flush=True)
            command = parse_voice_command(text)
            if command is not None:
                return command
            print("[APP2] commande non comprise, j'écoute encore (Ctrl+C pour quitter).", flush=True)
    finally:
        transcripts.close()
    raise RuntimeError("Flux audio terminé sans commande exploitable.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test direct des skills : hardware + detectors, sans LLM.")
    parser.add_argument("--behavior", choices=BEHAVIORS)
    parser.add_argument(
        "--target",
        choices=[*MOVE_TARGETS, *VISION_TARGETS],
        help="move : forward|backward|left|right ; autres : marker|red_ball|yellow_ball|human.",
    )
    parser.add_argument(
        "--duration", type=float, default=DEFAULT_DURATION_S, help="Durée en secondes (défaut : 1).",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="Écoute une commande vocale (ex. « suis moi pendant dix secondes ») et remplit "
        "behavior, target et duration ; ces trois options sont alors ignorées.",
    )
    parser.add_argument(
        "--input-device",
        default="auto",
        choices=["auto", "bluetooth", "wm8960", "default"],
        help="Source audio utilisée avec --audio.",
    )
    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.audio:
        return args

    if args.behavior is None or args.target is None:
        parser.error("--behavior et --target sont requis (sauf avec --audio).")
    if args.duration <= 0:
        parser.error("--duration doit être > 0.")
    if args.behavior == "move" and args.target not in MOVE_TARGETS:
        parser.error(f"move accepte seulement : {', '.join(MOVE_TARGETS)}.")
    if args.behavior != "move" and args.target not in VISION_TARGETS:
        parser.error(f"{args.behavior} accepte seulement : {', '.join(VISION_TARGETS)}.")
    return args


def _build_context(hardware: dict, target: str | None, intent_name: str, params: dict) -> SkillContext:
    return SkillContext(
        robot=hardware["robot"],
        camera=hardware["camera"],
        sensor=hardware["sensor"],
        perception=hardware["camera"],
        perception_target=PerceptionTarget.from_value(target) if target else None,
        state=BlackboardState(
            active_intent_name=intent_name,
            active_intent_parameters=params,
            camera_ready=hardware["camera"] is not None,
        ),
    )


def _run_move(registry: SkillRegistry, hardware: dict, args: argparse.Namespace) -> SkillResult:
    context = _build_context(hardware, None, MOVE_TARGETS[args.target], {"duration": args.duration})
    return SkillExecutor(context).run(registry.get(MOVE_TARGETS[args.target]))


def _run_approach(registry: SkillRegistry, hardware: dict, args: argparse.Namespace) -> SkillResult:
    params = {
        "target_object": args.target,
        "tracking_timeout_s": args.duration,
        "search_timeout_s": args.duration,
    }
    context = _build_context(hardware, args.target, "search_and_approach_object", params)
    return SkillExecutor(context).run(registry.get("approach_target"))


def _run_follow(registry: SkillRegistry, hardware: dict, args: argparse.Namespace) -> SkillResult:
    params = {"target_object": args.target, "duration_s": args.duration}
    intent_name = FOLLOW_INTENT_BY_TARGET.get(args.target, "follow_object")
    context = _build_context(hardware, args.target, intent_name, params)
    return SkillExecutor(context).run(registry.get("follow_object"))


def _inject_detection(context: SkillContext) -> None:
    """Copie la dernière détection de la caméra dans le blackboard lu par detect_object."""
    detection = context.perception.detect(target=context.perception_target)
    context.state["last_object_position"] = detection.position if detection else None
    context.state["last_object_distance_cm"] = detection.distance_cm if detection else None
    if detection:
        context.state["target_object"] = detection.label


def _run_search(registry: SkillRegistry, hardware: dict, args: argparse.Namespace) -> SkillResult:
    """Rotation par impulsions + detect_object, jusqu'à détection ou fin de la durée."""
    context = _build_context(hardware, args.target, "search_and_approach_object", {"target_object": args.target})
    executor = SkillExecutor(context)
    detect_skill = registry.get("detect_object")
    turn_skill = registry.get("turn_right")
    deadline = time.monotonic() + args.duration
    steps = 0

    while time.monotonic() < deadline:
        _inject_detection(context)
        result = executor.run(detect_skill)
        if result.status == "success":
            result.data["search_steps"] = steps
            executor.run(registry.get("stop_motion"))
            return result

        context.state["active_intent_parameters"] = {"target_object": args.target, "duration": SEARCH_STEP_S}
        turn_result = executor.run(turn_skill)
        steps += 1
        if turn_result.status != "success" or turn_result.data.get("motion") == "stop":
            return turn_result
        time.sleep(SEARCH_SETTLE_S)

    executor.run(registry.get("stop_motion"))
    return SkillResult(
        status="failed",
        message=f"Cible '{args.target}' non trouvée en {args.duration:.1f} s.",
        data={"search_steps": steps},
    )


RUNNERS = {
    "move": _run_move,
    "search": _run_search,
    "approach": _run_approach,
    "follow": _run_follow,
}


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    settings: RuntimeSettings = load_runtime_settings()
    hardware = None
    try:
        if args.audio:
            args.behavior, args.target, args.duration = _listen_for_command(args.input_device)
            print(f"[APP2] commande : {args.behavior} / {args.target} / {args.duration:g} s", flush=True)
        hardware = build_hardware_runtime(settings=settings)
        if hardware["robot"] is None:
            raise RuntimeError("Hardware indisponible (Raspberry Pi/Linux requis).")
        if args.behavior != "move" and hardware["camera"] is None:
            raise RuntimeError("Caméra indisponible : perception impossible.")
        registry = SkillRegistry.default(settings)
        result = RUNNERS[args.behavior](registry, hardware, args)
        print(f"[APP2] {args.behavior}/{args.target} -> {result.status} : {result.message}", flush=True)
        print(f"[APP2] data={result.data}", flush=True)
        if result.status == "failed":
            sys.exit(1)
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)
    finally:
        if hardware is not None:
            close_hardware_runtime(hardware)


if __name__ == "__main__":
    main()
