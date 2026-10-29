"""Scénario bout en bout « cherche la balle jaune, approche-toi à 1 m puis suis-la 5 min ».

VoiceRuntime (sans LLM, synchrone) -> Intent -> validation -> Skills -> RobotController -> robot simulé.
Horloge entièrement simulée : aucune attente réelle.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from irobot.config.settings import RuntimeSettings
from irobot.domain.orchestrator.registry import SkillRegistry
from irobot.domain.skills import FollowObjectSkill, FollowTargetSkill
from irobot.interfaces.robot_controller import RobotController
from irobot.interfaces.voice_runtime import VoiceRuntime
from tests.unit.fake_robot import FakeRobot

SENTENCE = "cherche la balle jaune, approche toi à 1m de la balle jaune puis suit la pendant 5 min"

LINEAR_CM_S = RuntimeSettings().cm_per_second
TURN_DEG_S = 120.0
HALF_FOV_DEG = 25.0
CENTER_BAND_DEG = 8.0
STAND_OFF_CM = 100.0
TOLERANCE_CM = 15.0
FOLLOW_S = 300.0
MOTIONS = {"forward", "backward", "left", "right"}

APPEAR_AT_S = 4.0
INITIAL_DISTANCE_CM = 220.0
INITIAL_BEARING_DEG = 20.0
OUT_OF_FIELD_S = (160.0, 162.0)
# (début, fin, vitesse radiale cm/s : > 0 s'éloigne, vitesse latérale °/s)
BALL_MOTION = [
    (20.0, 80.0, 8.0, 0.0),
    (100.0, 150.0, -6.0, 0.0),
    (170.0, 230.0, 5.0, -0.3),
    (230.0, 290.0, -5.0, 0.3),
]


def _integral(t: float, column: int) -> float:
    return sum(seg[column] * max(0.0, min(t, seg[1]) - seg[0]) for seg in BALL_MOTION)


class SimWorld(FakeRobot):
    """Robot 2WD + balle jaune + caméra simulés ; le mouvement est intégré à chaque sleep()."""

    def __init__(self, *, ball_appears: bool = True, emergency_at: float | None = None, obstacle_at: float | None = None):
        super().__init__(time_fn=self.time)
        self.now = 0.0
        self.x_cm = 0.0
        self.heading_deg = 0.0
        self.ball_appears = ball_appears
        self.ball_anchor_deg: float | None = None
        self.emergency_at = emergency_at
        self.obstacle_at = obstacle_at
        self.controller: RobotController | None = None
        self.observations: list[tuple[float, str | None, float | None]] = []
        self.targets: set[str | None] = set()

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        dt = max(0.0, float(seconds))
        motion = self.commands[-1] if self.commands else "stop"
        if motion == "forward":
            self.x_cm += LINEAR_CM_S * dt
        elif motion == "backward":
            self.x_cm -= LINEAR_CM_S * dt
        elif motion == "right":
            self.heading_deg += TURN_DEG_S * dt
        elif motion == "left":
            self.heading_deg -= TURN_DEG_S * dt
        self.now += dt
        if self.emergency_at is not None and self.now >= self.emergency_at and self.controller is not None:
            self.emergency_at = None
            # Équivaut au thread d'écoute qui entend « stop » pendant la mission.
            self.controller.request_emergency_stop()

    def check_obstacle(self) -> bool:
        return self.obstacle_at is not None and self.now >= self.obstacle_at

    def distance_cm(self) -> float:
        return INITIAL_DISTANCE_CM + _integral(self.now, 2) - self.x_cm

    def detect(self, *, target=None):
        self.targets.add(target)
        if not self.ball_appears or self.now < APPEAR_AT_S:
            self.observations.append((self.now, None, None))
            return None
        if self.ball_anchor_deg is None:
            self.ball_anchor_deg = self.heading_deg + INITIAL_BEARING_DEG
        bearing = self.ball_anchor_deg + _integral(self.now, 3) - self.heading_deg
        if OUT_OF_FIELD_S[0] <= self.now < OUT_OF_FIELD_S[1]:
            bearing += 2 * HALF_FOV_DEG
        if abs(bearing) > HALF_FOV_DEG:
            self.observations.append((self.now, None, None))
            return None
        position = "right" if bearing > CENTER_BAND_DEG else "left" if bearing < -CENTER_BAND_DEG else "center"
        distance = self.distance_cm()
        self.observations.append((self.now, position, distance))
        return SimpleNamespace(label=f"{target}_ball", position=position, distance_cm=distance)


def _timed(skill, world: SimWorld, spans: dict[str, list[tuple[float, float, object]]]):
    execute = skill.execute

    def wrapper(context):
        started = world.time()
        result = execute(context)
        spans.setdefault(skill.name, []).append((started, world.time(), result))
        return result

    skill.execute = wrapper
    return skill


def run_scenario(tmp_path: Path, **world_kwargs):
    world = SimWorld(**world_kwargs)
    controller = RobotController(world, time_fn=world.time, sleep_fn=world.sleep)
    world.controller = controller
    settings = RuntimeSettings()
    spans: dict[str, list[tuple[float, float, object]]] = {}
    registry = SkillRegistry.default()
    registry.register(_timed(FollowTargetSkill(settings=settings, time_fn=world.time, sleep_fn=world.sleep), world, spans))
    registry.register(_timed(FollowObjectSkill(settings=settings, time_fn=world.time, sleep_fn=world.sleep), world, spans))
    runtime = VoiceRuntime(
        robot=controller,
        perception=world,
        registry=registry,
        use_llm=False,
        threaded=False,
        trace_dir=str(tmp_path),
    )
    result = runtime.handle_transcript(SENTENCE)
    events = [json.loads(line) for line in Path(result["trace_path"]).read_text(encoding="utf-8").splitlines()]
    return world, result, events, spans


def _event_names(events: list[dict]) -> list[str]:
    return [event["event"] for event in events]


def _step_intents(events: list[dict]) -> list[str]:
    return [event["intent"]["name"] for event in events if event["event"] == "step_result"]


def _assert_stopped_since(world: SimWorld, since_s: float) -> None:
    after = [cmd for t, cmd in world.timed_commands if t >= since_s]
    assert after and set(after) == {"stop"}, after
    first_stop_at = next(t for t, cmd in world.timed_commands if t >= since_s)
    assert first_stop_at <= since_s + 0.05
    assert world.commands[-1] == "stop"


def test_full_mission_search_approach_and_follow_five_minutes(tmp_path):
    world, result, events, spans = run_scenario(tmp_path)

    assert result["status"] == "accepted", result
    assert result["mission"]["phase"] == "success"
    assert [s["intent"].name for s in result["steps"]] == ["search_and_approach_object", "follow_object"]
    assert world.targets == {"yellow"}

    # 1. Balle absente pendant 4 s, puis vue à droite à 220 cm.
    assert all(pos is None for t, pos, _ in world.observations if t < APPEAR_AT_S)
    first_seen = next(obs for obs in world.observations if obs[1] is not None)
    assert first_seen[0] >= APPEAR_AT_S
    assert first_seen[1] == "right"
    assert abs(first_seen[2] - INITIAL_DISTANCE_CM) < 1.0
    assert any(cmd == "right" for t, cmd in world.timed_commands if t < APPEAR_AT_S)

    # 2. Centrage puis approche jusqu'au stand-off.
    approach_end = spans["follow_target"][-1][1]
    approach_result = spans["follow_target"][-1][2]
    assert approach_result.status == "success"
    assert approach_result.data["close_enough"] is True
    assert abs(approach_result.data["distance_cm"] - STAND_OFF_CM) <= TOLERANCE_CM
    assert any(pos == "center" for t, pos, _ in world.observations if APPEAR_AT_S <= t <= approach_end)
    assert approach_end < BALL_MOTION[0][0]

    # 3. Suivi pendant 300 s simulées à 100 ± 15 cm, malgré éloignement, rapprochement et sortie du champ.
    follow_start, follow_end, follow_result = spans["follow_object"][0]
    assert follow_result.status == "success"
    assert follow_result.data["duration_s"] == FOLLOW_S
    assert FOLLOW_S <= follow_end - follow_start < FOLLOW_S + 0.5
    followed = [(t, pos, d) for t, pos, d in world.observations if follow_start <= t <= follow_end]
    distances = [d for _, pos, d in followed if pos is not None]
    assert len(distances) > 1000
    assert all(abs(d - STAND_OFF_CM) <= TOLERANCE_CM + 0.5 for d in distances), (min(distances), max(distances))
    assert {"forward", "backward", "left", "right"} <= {cmd for t, cmd in world.timed_commands if t >= follow_start}
    lost = [t for t, pos, _ in followed if pos is None]
    assert lost and all(OUT_OF_FIELD_S[0] <= t < OUT_OF_FIELD_S[1] for t in lost)
    assert not [cmd for t, cmd in world.timed_commands if OUT_OF_FIELD_S[0] <= t < OUT_OF_FIELD_S[1] and cmd in MOTIONS]

    # 4. Fin de mission : robot arrêté, stop en dernier.
    _assert_stopped_since(world, follow_end)
    names = _event_names(events)
    assert names[:3] == ["input", "plan_raw", "plan_validated"]
    assert names[-1] == "mission_result"
    assert events[-1]["status"] == "accepted"
    assert "emergency_stop" not in names and "obstacle_stop" not in names
    assert _step_intents(events)[-1] == "follow_object"
    assert [e["status"] for e in events if e["event"] == "step_result"][-1] == "accepted"


def test_ball_never_found_ends_incomplete_without_following(tmp_path):
    world, result, events, spans = run_scenario(tmp_path, ball_appears=False)

    assert result["status"] == "incomplete", result
    assert result["mission"]["phase"] == "failed"
    assert [s["intent"].name for s in result["steps"]] == ["search_and_approach_object"]
    assert "follow_object" not in spans
    searches = spans["follow_target"]
    assert searches and all(r.status == "failed" and r.data["target_lost"] is True for _, _, r in searches)
    search_timeout = RuntimeSettings().search_timeout_seconds
    assert all(end - start >= search_timeout for start, end, _ in searches)
    assert all(pos is None for _, pos, _ in world.observations)

    assert world.commands[-1] == "stop"
    _assert_stopped_since(world, searches[-1][1])
    names = _event_names(events)
    assert names[-1] == "mission_result" and events[-1]["status"] == "incomplete"
    assert set(_step_intents(events)) == {"search_and_approach_object"}
    assert "emergency_stop" not in names and "obstacle_stop" not in names


def test_emergency_stop_at_60s_interrupts_mission(tmp_path):
    world, result, events, spans = run_scenario(tmp_path, emergency_at=60.0)

    assert result["status"] == "aborted", result
    assert result["mission"]["phase"] == "aborted"
    assert result["mission"]["last_error"] == "emergency stop"
    follow_start, follow_end, follow_result = spans["follow_object"][0]
    assert follow_start < 60.0 <= follow_end < 60.5
    assert follow_result.data["emergency_stop"] is True
    assert result["steps"][-1]["reason"] == "emergency stop"

    _assert_stopped_since(world, 60.0)
    names = _event_names(events)
    assert "emergency_stop" in names
    assert names.index("emergency_stop") < names.index("mission_result")
    assert events[-1]["status"] == "aborted"
    assert len([e for e in events if e["event"] == "step_result" and e["intent"]["name"] == "follow_object"]) == 1


def test_obstacle_at_100s_stops_robot_and_aborts_mission(tmp_path):
    world, result, events, spans = run_scenario(tmp_path, obstacle_at=100.0)

    assert result["status"] == "aborted", result
    assert result["mission"]["last_error"] == "obstacle"
    follow_start, follow_end, follow_result = spans["follow_object"][0]
    assert follow_start < 100.0 <= follow_end < 100.5
    assert follow_result.data["obstacle_detected"] is True
    assert "emergency_stop" not in follow_result.data

    # Une impulsion de recul (sans contrôle d'obstacle avant) peut finir après 100 s : aucune commande avant n'est émise.
    assert not [cmd for t, cmd in world.timed_commands if t >= 100.0 and cmd in {"forward", "left", "right"}]
    assert world.commands[-1] == "stop"
    assert world.timed_commands[-1][0] >= 100.0
    names = _event_names(events)
    assert "obstacle_stop" in names and "emergency_stop" not in names
    assert names.index("obstacle_stop") < names.index("mission_result")
    assert events[-1]["status"] == "aborted"
