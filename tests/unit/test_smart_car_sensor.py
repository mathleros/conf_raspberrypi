from __future__ import annotations

import argparse
import importlib
import sys
import threading
from types import SimpleNamespace

import pytest

from irobot.config.settings import RuntimeSettings
from irobot.hardware.smart_car import smart_car as sc


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
    return sc.SmartCar2WD(distance_sensor=sensor, sleep_fn=clock.sleep)


def _hc_sr04(monkeypatch, clock):
    monkeypatch.setitem(
        sys.modules,
        "gpiozero",
        SimpleNamespace(DigitalOutputDevice=_Pin, DigitalInputDevice=_Pin),
    )
    module = importlib.import_module("irobot.hardware.sensors.hc_sr04")
    return module.HC_SR04(time_fn=clock, sleep_fn=clock.sleep)


def _mock_sensor_reads(sensor, clock, distances):
    pending = []
    sensor._trigger_pulse = lambda: None

    def wait_for_level(expected, timeout_s=0.05):
        if expected == 1:
            distance = next(distances)
            if distance is None:
                return False
            pending.append(distance)
            return True
        clock.now += pending.pop() * 2 / 34300
        return True

    sensor._wait_for_level = wait_for_level


def test_drive_speed_is_configured_by_constructor(monkeypatch):
    monkeypatch.setattr(
        sc, "load_runtime_settings",
        lambda: RuntimeSettings(drive_speed=0.65, obstacle_threshold_cm=8.0),
    )
    car = _car(monkeypatch, None, _Clock())
    assert car.speed == 0.65
    assert car.obstacle_threshold_cm == 8.0

    custom_car = sc.SmartCar2WD(
        sleep_fn=lambda _: None,
        drive_speed=0.7,
        obstacle_threshold_cm=12.0,
    )
    assert custom_car.speed == 0.7
    assert custom_car.obstacle_threshold_cm == 12.0


def test_smart_car_cli_threshold_defaults_to_runtime_settings(monkeypatch):
    monkeypatch.setattr(
        sc, "load_runtime_settings",
        lambda: RuntimeSettings(obstacle_threshold_cm=9.0),
    )

    args = sc.build_parser().parse_args(["forward"])

    assert args.obstacle_threshold_cm == 9.0


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


def test_sensor_cache_within_50ms_then_refresh(monkeypatch):
    clock = _Clock()
    sensor = _hc_sr04(monkeypatch, clock)
    _mock_sensor_reads(sensor, clock, iter([100.0, 80.0]))

    assert sensor.read_distance_cm() == 100.0
    clock.now += 0.049
    assert sensor.read_distance_cm() == 100.0
    clock.now += 0.002
    assert sensor.read_distance_cm() == pytest.approx(80.0)


def test_check_obstacle_retries_missing_sensor_reading(monkeypatch):
    sensor, clock = _Sensor([None, 3.0]), _Clock()
    car = _car(monkeypatch, sensor, clock)

    assert car.check_obstacle() is True  # 3 cm < 5 cm, après un retry sur None
    assert sensor.calls == 2


def test_no_sensor_obstacle_policy(monkeypatch):
    car = _car(monkeypatch, None, _Clock())
    assert car.check_obstacle() is False
    car.require_obstacle_sensor = True
    assert car.check_obstacle() is True


def test_sensor_concurrent_reads_are_serialized(monkeypatch):
    clock = _Clock()
    sensor = _hc_sr04(monkeypatch, clock)
    started = threading.Event()
    release = threading.Event()
    calls = []

    sensor._trigger_pulse = lambda: None

    def wait_for_level(expected, timeout_s=0.05):
        if expected == 1:
            calls.append(sensor._read_lock.locked())
            started.set()
            assert release.wait(2)
            return True
        clock.now += 42.0 * 2 / 34300
        return True

    sensor._wait_for_level = wait_for_level
    results = []
    threads = [threading.Thread(target=lambda: results.append(sensor.read_distance_cm())) for _ in range(4)]
    for t in threads:
        t.start()
    assert started.wait(1)
    release.set()
    for t in threads:
        t.join()
    assert calls == [True]
    assert results == [42.0] * 4


def test_sensor_does_not_cache_missing_measurements(monkeypatch):
    clock = _Clock()
    sensor = _hc_sr04(monkeypatch, clock)
    _mock_sensor_reads(sensor, clock, iter([None, 30.0]))

    assert sensor.read_distance_cm() is None
    clock.now += 0.001
    assert sensor.read_distance_cm() == 30.0
