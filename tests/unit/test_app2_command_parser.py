import argparse
from types import SimpleNamespace

import pytest

from irobot.app2 import app2
from irobot.app2.command_parser import (
    Command,
    parse_command_chain,
    parse_voice_command,
    split_wake_word,
)


def test_single_command_with_spoken_duration():
    assert parse_voice_command("suis moi pendant dix secondes") == Command("follow", "person:Moi", 10.0)
    assert parse_voice_command("avance") == Command("move", "forward", 1.0)
    assert parse_voice_command("cherche la balle rouge") == Command("search", "red_ball", 1.0)
    assert parse_voice_command("cherche Quentin") == Command("search", "person:Quentin")
    assert parse_voice_command("approche toi de Quentin") == Command("approach", "person:Quentin")


@pytest.mark.parametrize("text", ["", "bonjour", "cherche", "suis"])
def test_incomplete_phrases_are_rejected(text):
    assert parse_voice_command(text) is None


def test_chain_is_split_on_puis():
    assert parse_command_chain("avance deux secondes puis tourne a gauche puis approche la balle jaune") == [
        Command("move", "forward", 2.0),
        Command("move", "left", 1.0),
        Command("approach", "yellow_ball", 1.0),
    ]


def test_chain_is_all_or_nothing():
    assert parse_command_chain("avance puis blabla") is None
    assert parse_command_chain("avance puis") is None


def test_command_validates_vocabulary():
    with pytest.raises(ValueError):
        Command("move", "human")
    with pytest.raises(ValueError):
        Command("follow", "forward")
    with pytest.raises(ValueError):
        Command("search", "person:")
    with pytest.raises(ValueError):
        Command("dance", "forward")
    with pytest.raises(ValueError):
        Command("move", "forward", 0)


def test_wake_word_split():
    assert split_wake_word("Robot avance puis recule") == "avance puis recule"
    assert split_wake_word("robot") == ""
    assert split_wake_word("avance") is None
    assert split_wake_word("ok jarvis recule", "jarvis") == "recule"


def _args(**kwargs):
    return argparse.Namespace(wake_word="robot", input_device="auto", **kwargs)


def _patch_audio(monkeypatch, transcripts):
    import irobot.common.hardware.audio.audio_utils as audio_utils
    import irobot.common.hardware.audio.voice_input as voice_input

    monkeypatch.setattr(audio_utils, "resolve_input_device", lambda device: device)
    monkeypatch.setattr(voice_input, "transcribe_loop", lambda device: (text for text in transcripts))


def test_listen_loop_requires_wake_word_then_runs_chain(monkeypatch):
    executed = []
    monkeypatch.setattr(app2, "_run_commands", lambda registry, hardware, commands: executed.append(commands))
    _patch_audio(
        monkeypatch,
        [
            "avance",  # sans mot d'activation : ignoré
            "robot",  # armement
            "recule puis tourne a droite",  # commande sur la phrase suivante
            "robot suis moi dix secondes",  # mot d'activation et commande ensemble
            "robot blabla",  # incompris : rien n'est exécuté
        ],
    )
    with pytest.raises(RuntimeError, match="Flux audio terminé"):
        app2._listen_and_run(None, {}, _args())
    assert executed == [
        [Command("move", "backward"), Command("move", "right")],
        [Command("follow", "person:Moi", 10.0)],
    ]


def test_run_commands_stops_at_first_failure(monkeypatch):
    calls = []

    def runner(label, status):
        def run(registry, hardware, command):
            calls.append(label)
            return SimpleNamespace(status=status, message="", data={})

        return run

    monkeypatch.setitem(app2.RUNNERS, "move", runner("move", "failed"))
    monkeypatch.setitem(app2.RUNNERS, "follow", runner("follow", "success"))
    commands = [Command("move", "forward"), Command("follow", "human")]
    assert app2._run_commands(None, {"camera": object()}, commands) is False
    assert calls == ["move"]


def test_cli_builds_a_validated_command():
    _, commands = app2._parse_args(["--behavior", "follow", "--target", "human", "--duration", "200"])
    assert commands == [Command("follow", "human", 200.0)]
    with pytest.raises(SystemExit):
        app2._parse_args(["--behavior", "move", "--target", "marker"])


def test_cli_text_builds_a_chain_with_optional_wake_word():
    expected = [Command("move", "forward", 2.0), Command("follow", "person:Moi", 1.0)]
    for text in ("avance deux secondes puis suis moi", "robot avance deux secondes puis suis moi"):
        assert app2._parse_args(["--text", text])[1] == expected


def test_cli_text_builds_named_search_and_approach_commands():
    assert app2._parse_args(["--text", "cherche Quentin"])[1] == [
        Command("search", "person:Quentin"),
    ]
    assert app2._parse_args(["--text", "approche toi de Quentin"])[1] == [
        Command("approach", "person:Quentin"),
    ]


def test_cli_text_rejects_unknown_or_conflicting_input():
    with pytest.raises(SystemExit):
        app2._parse_args(["--text", "blabla"])
    with pytest.raises(SystemExit):
        app2._parse_args(["--text", "avance", "--audio"])


def test_follow_named_person():
    assert parse_voice_command("suis Mathieu") == Command("follow", "person:Mathieu")
    assert parse_voice_command("suis Quentin pendant 5 secondes") == Command("follow", "person:Quentin", 5.0)
    assert parse_voice_command("suis la balle rouge") == Command("follow", "red_ball")
    assert parse_voice_command("suis un humain") == Command("follow", "human")
    assert parse_voice_command("suis la balle") is None
    assert parse_voice_command("approche moi") == Command("approach", "human")


def test_cli_accepts_person_target():
    _, commands = app2._parse_args(["--behavior", "follow", "--target", "person:Mathieu"])
    assert commands == [Command("follow", "person:Mathieu")]
    for behavior in ("search", "approach", "follow"):
        _, commands = app2._parse_args(["--behavior", behavior, "--target", "person:Bob"])
        assert commands == [Command(behavior, "person:Bob")]
    for argv in (
        ["--behavior", "follow", "--target", "person:"],
        ["--behavior", "search", "--target", "person:"],
        ["--behavior", "move", "--target", "person:Bob"],
    ):
        with pytest.raises(SystemExit):
            app2._parse_args(argv)


def test_follow_unknown_person_fails_without_starting_the_skill():
    gallery = SimpleNamespace(resolve=lambda name: None)
    hardware = {"camera": SimpleNamespace(set_face_target=lambda *a: pytest.fail("camera touched")),
                "gallery": gallery}
    result = app2._run_follow(None, hardware, Command("follow", "person:Bob"))
    assert result.status == "failed"
    assert "Personne inconnue : Bob" in result.message


def test_approach_named_person_targets_gallery_face_and_clears_it(monkeypatch):
    embedding = object()
    camera = SimpleNamespace(calls=[], set_face_target=lambda *args: camera.calls.append(args))
    gallery = SimpleNamespace(resolve=lambda name: "Quentin", get=lambda name: embedding)
    hardware = {"robot": None, "sensor": None, "camera": camera, "gallery": gallery}
    captured = {}

    class _Executor:
        def __init__(self, context):
            captured["context"] = context

        def run(self, skill):
            captured["skill"] = skill
            return SimpleNamespace(status="success", message="", data={})

    monkeypatch.setattr(app2, "SkillExecutor", _Executor)
    registry = SimpleNamespace(get=lambda name: name)

    result = app2._run_approach(registry, hardware, Command("approach", "person:quentin"))

    assert result.status == "success"
    assert camera.calls == [("Quentin", embedding), (None,)]
    assert captured["context"].perception_target.value == "face"
    assert captured["context"].state.active_intent_parameters["target_object"] == "human"
    assert captured["skill"] == "approach_target"


def test_approach_unknown_person_fails_without_selecting_face():
    gallery = SimpleNamespace(resolve=lambda name: None)
    camera = SimpleNamespace(set_face_target=lambda *args: pytest.fail("camera touched"))

    result = app2._run_approach(None, {"camera": camera, "gallery": gallery}, Command("approach", "person:Bob"))

    assert result.status == "failed"
    assert "Personne inconnue : Bob" in result.message
