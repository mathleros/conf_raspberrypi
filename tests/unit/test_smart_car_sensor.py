from __future__ import annotations

import argparse
import threading

from irobot.config.settings import RuntimeSettings
from irobot.hardware.smart_car import smart_car as sc
from irobot.interfaces.robot_controller import RobotController


class _Pin:
    value = 0

    def __init__(self, *a, **k):
        pass

    def on(self):
        pass

    def off(self):
        pass

    def close(self):
        pass


class _Sensor:
    def __init__(self, values):
        self.values = list(values)
        self.calls = 0
        self.cleanup_calls = 0
        self.active = 0
        self.max_active = 0

    def read_distance_cm(self):
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.active -= 1
        return self.values.pop(0) if self.values else self.values_default

    values_default = 100.0

    def cleanup(self):
        self.cleanup_calls += 1


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def _car(monkeypatch, sensor, clock):
    monkeypatch.setattr(sc, "DigitalOutputDevice", _Pin)
    monkeypatch.setattr(sc, "PWMOutputDevice", _Pin)
    return sc.SmartCar2WD(distance_sensor=sensor, time_fn=clock, sleep_fn=clock.sleep)


def test_drive_speed_is_configured_by_constructor(monkeypatch):
    monkeypatch.setattr(sc, "load_runtime_settings", lambda: RuntimeSettings(drive_speed=0.65))
    car = _car(monkeypatch, None, _Clock())
    assert car.speed == 0.65

    custom_car = sc.SmartCar2WD(
        time_fn=_Clock(),
        sleep_fn=lambda _: None,
        drive_speed=0.7,
    )
    assert custom_car.speed == 0.7


def test_cleanup_releases_injected_sensor_once(monkeypatch):
    sensor = _Sensor([])
    car = _car(monkeypatch, sensor, _Clock())

    car.cleanup()
    car.cleanup()

    assert sensor.cleanup_calls == 1


def test_smart_car_cli_builds_and_cleans_injected_sensor(monkeypatch):
    sensor = _Sensor([])
    monkeypatch.setattr(sc, "DigitalOutputDevice", _Pin)
    monkeypatch.setattr(sc, "PWMOutputDevice", _Pin)
    monkeypatch.setattr(sc, "HC_SR04", lambda: sensor)
    args = argparse.Namespace(
        command="stop",
        duration=0,
        speed=0.5,
        obstacle_threshold_cm=20.0,
        obstacle_check_interval=0.2,
    )

    sc.run_command(args)

    assert sensor.cleanup_calls == 1


def test_cache_within_50ms_then_refresh(monkeypatch):
    sensor, clock = _Sensor([100.0, 80.0]), _Clock()
    car = _car(monkeypatch, sensor, clock)

    assert car.read_distance_cm() == 100.0
    clock.now += 0.049
    assert car.read_distance_cm() == 100.0
    assert sensor.calls == 1
    clock.now += 0.002
    assert car.read_distance_cm() == 80.0
    assert sensor.calls == 2


def test_check_obstacle_shares_cache_and_none_is_not_cached(monkeypatch):
    sensor, clock = _Sensor([None, 3.0]), _Clock()
    car = _car(monkeypatch, sensor, clock)

    assert car.check_obstacle() is True  # 3 cm < 5 cm, après un retry sur None
    assert sensor.calls == 2
    assert car.read_distance_cm() == 3.0  # servi par le cache
    assert sensor.calls == 2


def test_no_sensor_returns_none(monkeypatch):
    car = _car(monkeypatch, None, _Clock())
    assert car.read_distance_cm() is None
    assert RobotController(car).read_distance_cm() is None


def test_concurrent_reads_are_serialized(monkeypatch):
    sensor, clock = _Sensor([]), _Clock()
    car = _car(monkeypatch, sensor, clock)
    car._time_fn = lambda: 0.0
    car._last_distance_at = None
    held = []
    original = sensor.read_distance_cm

    def slow_read():
        held.append(car._sensor_lock.locked())
        return original()

    sensor.read_distance_cm = slow_read
    threads = [threading.Thread(target=car.read_distance_cm) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(held) and sensor.max_active == 1
    assert sensor.calls == 1  # les autres threads sont servis par le cache
