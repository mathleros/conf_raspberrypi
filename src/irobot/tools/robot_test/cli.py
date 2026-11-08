"""Point d'entrée `robot-test` : banc de test du noyau, appelle directement les skills (sans LLM ni orchestrateur).

Exemples :
    uv run robot-test --behavior move --target forward --duration 2
    uv run robot-test --behavior search --target marker --duration 10
    uv run robot-test --behavior approach --target red_ball --duration 8
    uv run robot-test --behavior follow --target human --duration 20
    uv run robot-test --behavior follow --target person:Mathieu --duration 20   # assets/face/Mathieu.jpg
    uv run robot-test --text "avance deux secondes puis suis moi"   # sans micro
    uv run robot-test --audio        # écoute en continu : « robot, avance puis suis moi »
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING

from irobot.common.config.settings import RuntimeSettings, load_runtime_settings
from irobot.common.domain.orchestrator.executor import SkillExecutor
from irobot.common.domain.orchestrator.registry import SkillRegistry
from irobot.common.domain.perception import PerceptionTarget
from irobot.common.domain.skills.base_skill import SkillContext, SkillResult
from irobot.common.domain.skills.blackboard_state import BlackboardState
from irobot.common.hardware.runtime_factory import (
    build_hardware_runtime,
    close_hardware_runtime,
    load_face_gallery,
)
from irobot.common.interfaces.wake_word import DEFAULT_WAKE_WORD, split_wake_word
from irobot.tools.robot_test.command_parser import (
    BEHAVIORS,
    DEFAULT_DURATION_S,
    DEFAULT_VISION_DURATION_S,
    MOVE_TARGETS,
    PERSON_PREFIX,
    VISION_TARGETS,
    Command,
    parse_command_chain,
)

if TYPE_CHECKING:
    from irobot.common.hardware.camera.detector.face_gallery import FaceGallery

MOVE_SKILLS = {
    "forward": "move_forward",
    "backward": "move_backward",
    "left": "turn_left",
    "right": "turn_right",
}

# Nom d'intention "historique" : FollowObjectSkill en déduit sa distance de consigne.
FOLLOW_INTENT_BY_TARGET = {
    "human": "follow_person",
    "red_ball": "follow_red_ball",
}

def _listen_and_run(registry: SkillRegistry, hardware: dict, args: argparse.Namespace) -> None:
    """Boucle d'écoute : mot d'activation, puis commande (même phrase ou phrase suivante)."""
    # Import paresseux : la dépendance audio n'existe pas hors Raspberry Pi.
    from irobot.common.hardware.audio.audio_utils import resolve_input_device
    from irobot.common.hardware.audio.voice_input import transcribe_loop

    transcripts = transcribe_loop(resolve_input_device(args.input_device))
    armed = False
    print(f"[ROBOT-TEST] j'écoute : dites « {args.wake_word} » puis une commande (Ctrl+C pour quitter).", flush=True)
    try:
        for text in transcripts:
            print(f"[ROBOT-TEST] entendu : « {text} »", flush=True)
            remainder = split_wake_word(text, args.wake_word)
            if remainder is None and not armed:
                print(f"[ROBOT-TEST] mot d'activation « {args.wake_word} » absent : phrase ignorée.", flush=True)
                continue
            phrase = remainder if remainder is not None else text
            if not phrase:
                armed = True
                print("[ROBOT-TEST] oui ? j'attends votre commande.", flush=True)
                continue
            commands = parse_command_chain(phrase)
            armed = False
            if commands is None:
                print("[ROBOT-TEST] commande non comprise (tout ou rien).", flush=True)
                continue
            _run_commands(registry, hardware, commands)
    finally:
        transcripts.close()
    raise RuntimeError("Flux audio terminé.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test direct des skills : hardware + detectors, sans LLM.")
    parser.add_argument("--behavior", choices=BEHAVIORS)
    parser.add_argument(
        "--target",
        help=f"move : {'|'.join(MOVE_TARGETS)} ; autres : {'|'.join(VISION_TARGETS)} ; "
        f"search/approach/follow : {PERSON_PREFIX}<Prénom> (photo assets/face/<Prénom>.jpg).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Durée en secondes (défaut : 1 pour move, 15 pour search/approach/follow).",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="Écoute en continu : mot d'activation puis commande, enchaînements avec « puis » "
        "(ex. « robot avance deux secondes puis suis moi »). Ignore --behavior/--target/--duration.",
    )
    parser.add_argument(
        "--text",
        help="Phrase à interpréter comme à la voix, sans micro (ex. \"avance puis suis moi\"). "
        "Ignore --behavior/--target/--duration.",
    )
    parser.add_argument("--wake-word", default=DEFAULT_WAKE_WORD, help="Mot d'activation avec --audio.")
    parser.add_argument(
        "--input-device",
        default="auto",
        choices=["auto", "bluetooth", "wm8960", "default"],
        help="Source audio utilisée avec --audio.",
    )
    return parser


def _parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[Command] | None]:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.audio and args.text is not None:
        parser.error("--audio et --text sont exclusifs.")
    if args.audio:
        return args, None
    if args.text is not None:
        # Le mot d'activation reste facultatif : « robot avance » et « avance » sont équivalents.
        phrase = split_wake_word(args.text, args.wake_word)
        commands = parse_command_chain(args.text if phrase is None else phrase)
        if commands is None:
            parser.error(f"commande non comprise : {args.text!r}.")
        return args, commands

    if args.behavior is None or args.target is None:
        parser.error("--behavior et --target sont requis (sauf avec --audio ou --text).")
    try:
        duration = args.duration
        if duration is None:
            duration = DEFAULT_DURATION_S if args.behavior == "move" else DEFAULT_VISION_DURATION_S
        return args, [Command(args.behavior, args.target, duration)]
    except ValueError as exc:
        parser.error(str(exc))


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


def _run_move(registry: SkillRegistry, hardware: dict, command: Command) -> SkillResult:
    skill_name = MOVE_SKILLS[command.target]
    context = _build_context(hardware, None, skill_name, {"duration": command.duration})
    return SkillExecutor(context).run(registry.get(skill_name))


def _run_approach(registry: SkillRegistry, hardware: dict, command: Command) -> SkillResult:
    face_target: str | None = None
    if command.target.startswith(PERSON_PREFIX):
        name = command.target[len(PERSON_PREFIX):].strip()
        gallery: FaceGallery | None = hardware.get("gallery")
        canonical = gallery.resolve(name) if gallery is not None else None
        if gallery is None or canonical is None:
            message = f"Personne inconnue : {name}"
            print(f"[ROBOT-TEST] {message}", flush=True)
            return SkillResult(status="failed", message=message)
        face_target = canonical
    else:
        gallery = None

    target = "human" if face_target is not None else command.target
    params = {
        "target_object": target,
        "tracking_timeout_s": command.duration,
        "search_timeout_s": command.duration,
    }
    try:
        if face_target is not None:
            hardware["camera"].set_face_target(face_target, gallery.get(face_target))
        context = _build_context(hardware, target, "search_and_approach_object", params)
        return SkillExecutor(context).run(registry.get("approach_target"))
    finally:
        if face_target is not None:
            hardware["camera"].set_face_target(None)


def _run_follow_person(registry: SkillRegistry, hardware: dict, command: Command) -> SkillResult:
    name = command.target[len(PERSON_PREFIX):].strip()
    gallery: FaceGallery | None = hardware.get("gallery")
    canonical = gallery.resolve(name) if gallery is not None else None
    if canonical is None:
        message = f"Personne inconnue : {name}"
        print(f"[ROBOT-TEST] {message}", flush=True)
        return SkillResult(status="failed", message=message)
    params = {"target_object": "human", "duration_s": command.duration}
    context = _build_context(hardware, "human", "follow_person", params)
    hardware["camera"].set_face_target(canonical, gallery.get(canonical))
    try:
        return SkillExecutor(context).run(registry.get("follow_object"))
    finally:
        hardware["camera"].set_face_target(None)


def _run_follow(registry: SkillRegistry, hardware: dict, command: Command) -> SkillResult:
    if command.target.startswith(PERSON_PREFIX):
        return _run_follow_person(registry, hardware, command)
    params = {"target_object": command.target, "duration_s": command.duration}
    intent_name = FOLLOW_INTENT_BY_TARGET.get(command.target, "follow_object")
    context = _build_context(hardware, command.target, intent_name, params)
    return SkillExecutor(context).run(registry.get("follow_object"))


RUNNERS = {
    "move": _run_move,
    "search": _run_approach,
    "approach": _run_approach,
    "follow": _run_follow,
}


def _run_commands(registry: SkillRegistry, hardware: dict, commands: list[Command]) -> bool:
    """Exécute les commandes dans l'ordre ; s'arrête à la première qui échoue."""
    try:
        for index, command in enumerate(commands, start=1):
            label = f"{command.behavior}/{command.target}/{command.duration:g}s"
            if command.behavior != "move" and hardware["camera"] is None:
                print(f"[ROBOT-TEST] {label} -> caméra indisponible : perception impossible.", flush=True)
                return False
            print(f"[ROBOT-TEST] ({index}/{len(commands)}) {label}", flush=True)
            result = RUNNERS[command.behavior](registry, hardware, command)
            print(f"[ROBOT-TEST] {label} -> {result.status} : {result.message}", flush=True)
            print(f"[ROBOT-TEST] data={result.data}", flush=True)
            if result.status == "failed":
                return False
        return True
    finally:
        if hardware["camera"] is not None:
            hardware["camera"].release_target()



def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s %(name)s %(message)s")
    args, commands = _parse_args(argv)
    settings: RuntimeSettings = load_runtime_settings()
    hardware = None
    try:
        hardware = build_hardware_runtime(settings=settings)
        if hardware["robot"] is None:
            raise RuntimeError("Hardware indisponible (Raspberry Pi/Linux requis).")
        registry = SkillRegistry.default(settings)
        hardware["gallery"] = load_face_gallery(settings)
        if args.audio:
            _listen_and_run(registry, hardware, args)
        elif not _run_commands(registry, hardware, commands):
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n[ROBOT-TEST] arrêt demandé.", flush=True)
    except RuntimeError as exc:
        print(f"Erreur : {exc}")
        sys.exit(1)
    finally:
        if hardware is not None:
            close_hardware_runtime(hardware)


if __name__ == "__main__":
    main()
