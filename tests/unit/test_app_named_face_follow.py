from types import SimpleNamespace

import numpy as np

from irobot.app.domain.intent import Intent
from irobot.app.interfaces.command_service import CommandService
from irobot.app.interfaces.language_controller import LanguageController
from irobot.app.interfaces.plan_guards import follow_request_refusal, requests_human_follow


class _Camera:
    def __init__(self) -> None:
        self.calls: list[tuple[str | None, object]] = []

    def set_face_target(self, name, embedding) -> None:
        self.calls.append((name, embedding))


class _Gallery:
    def __init__(self) -> None:
        self._embeddings = {"Mathieu": np.ones(4, dtype=np.float32), "Moi": np.zeros(4, dtype=np.float32)}

    def resolve(self, name: str) -> str | None:
        return {"mathieu": "Mathieu", "moi": "Moi"}.get(name.lower())

    def get(self, name: str):
        canonical = self.resolve(name)
        return None if canonical is None else self._embeddings[canonical]


def test_named_follow_is_accepted_by_guards() -> None:
    assert requests_human_follow("suis Mathieu")
    assert follow_request_refusal("suis Mathieu") is None


def test_named_follow_does_not_swallow_objects_or_articles() -> None:
    assert follow_request_refusal("suis le chat") == "unsupported_follow_target"
    assert follow_request_refusal("suis un chat") == "unsupported_follow_target"


def test_select_face_target_uses_gallery_for_named_person() -> None:
    camera = _Camera()
    controller = LanguageController(camera=camera, gallery=_Gallery())
    intent = SimpleNamespace(name="follow_person", parameters={"person": "mathieu"})

    controller._select_face_target(intent)

    assert camera.calls[0][0] == "Mathieu"
    assert np.array_equal(camera.calls[0][1], np.ones(4, dtype=np.float32))


def test_select_face_target_resets_to_any_face_without_name() -> None:
    camera = _Camera()
    controller = LanguageController(camera=camera, gallery=_Gallery())
    controller._select_face_target(SimpleNamespace(name="follow_person", parameters={}))
    controller._select_face_target(SimpleNamespace(name="move_forward", parameters={}))

    assert camera.calls == [(None, None), (None, None)]


def test_local_parser_extracts_person_name() -> None:
    from irobot.app.interfaces.intent.text_intent_parser import TextIntentParser

    intent = TextIntentParser().parse("suis Mathieu")

    assert intent.name == "follow_person"
    assert intent.parameters == {"person": "Mathieu"}
    assert TextIntentParser().parse("suis le chat").name != "follow_person"


def test_search_and_approach_selects_named_face_target() -> None:
    camera = _Camera()
    controller = LanguageController(camera=camera, gallery=_Gallery())
    controller._select_face_target(
        SimpleNamespace(name="search_and_approach_object", parameters={"person": "Mathieu"}),
    )
    controller._select_face_target(SimpleNamespace(name="search_and_approach_object", parameters={}))

    assert camera.calls[0][0] == "Mathieu"
    assert np.array_equal(camera.calls[0][1], np.ones(4, dtype=np.float32))
    assert camera.calls[1] == (None, None)


def test_plan_refusal_flags_unknown_person_only() -> None:
    service = CommandService(use_llm=False, gallery=_Gallery())

    def refusal(name: str):
        intent = Intent(
            name="search_and_approach_object", target="face", parameters={"person": name}, raw_text="approche toi",
        )
        return service._plan_refusal([intent], {"source": "local"})

    assert refusal("Inconnu") == "personne inconnue"
    assert refusal("mathieu") is None
