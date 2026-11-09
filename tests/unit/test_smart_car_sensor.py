from __future__ import annotations

import argparse
import importlib
import sys
import threading
from types import SimpleNamespace

import pytest

from irobot.app.hardware.smart_car import smart_car as sc
from irobot.app.hardware.smart_car import cli
from irobot.app.interfaces.robot_controller import RobotController


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
    return sc.SmartCar2WD()


def _hc_sr04(monkeypatch, clock):
    monkeypatch.setitem(
        sys.modules,
        "gpiozero",
        SimpleNamespace(DigitalOutputDevice=_Pin, DigitalInputDevice=_Pin),
    )
    module = importlib.import_module("irobot.app.hardware.sensors.hc_sr04")
    # Le module peut déjà être importé avec le vrai gpiozero (ex. via cli.py sur Raspberry Pi).
    monkeypatch.setattr(module, "DigitalOutputDevice", _Pin)
    monkeypatch.setattr(module, "DigitalInputDevice", _Pin)
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


def test_drive_speed_is_set_by_the_caller(monkeypatch):
    monkeypatch.setattr(sc, "DigitalOutputDevice", _Pin)
    monkeypatch.setattr(sc, "PWMOutputDevice", _Pin)
    car = sc.SmartCar2WD(drive_speed=0.7)
    assert car.speed == 0.7


def test_smart_car_cli_threshold_defaults_to_runtime_settings(monkeypatch):
    from irobot.app.config.settings import RuntimeSettings

    monkeypatch.setattr(
        cli, "load_runtime_settings",
        lambda: RuntimeSettings(obstacle_threshold_cm=9.0),
    )

    args = cli.build_parser().parse_args(["forward"])

    assert args.obstacle_threshold_cm == 9.0


def test_cleanup_releases_gpio_once(monkeypatch):
    monkeypatch.setattr(sc, "DigitalOutputDevice", _Pin)
    monkeypatch.setattr(sc, "PWMOutputDevice", _Pin)
    car = sc.SmartCar2WD()

    car.cleanup()
    car.cleanup()

    assert car._closed is True


def test_smart_car_cli_builds_and_cleans_injected_sensor(monkeypatch):
    sensor = _Sensor([])
    calls = []

    class Car:
        def __init__(self, *, drive_speed):
            self.speed = drive_speed

        def stop(self):
            calls.append("stop")

        def set_speed(self, speed):
            self.speed = speed

        def cleanup(self):
            calls.append("car cleanup")

    monkeypatch.setattr(cli, "SmartCar2WD", Car)
    monkeypatch.setattr(cli, "HC_SR04", lambda: sensor)
    args = argparse.Namespace(
        command="stop",
        duration=0,
        speed=0.5,
        obstacle_threshold_cm=20.0,
        obstacle_check_interval=0.2,
    )

    cli.run_command(args)

    assert sensor.cleanup_calls == 1
    assert calls == ["stop", "car cleanup"]


def test_smart_car_cli_routes_obstacle_stop_through_controller(monkeypatch, capsys):
    sensor = _Sensor([1.0])
    calls = []

    class Car:
        def __init__(self, *, drive_speed):
            self.speed = drive_speed

        def forward(self):
            calls.append("forward")

        def stop(self):
            calls.append("stop")

        def set_speed(self, speed):
            self.speed = speed

        def cleanup(self):
            calls.append("car cleanup")

    monkeypatch.setattr(cli, "SmartCar2WD", Car)
    monkeypatch.setattr(cli, "HC_SR04", lambda: sensor)
    args = argparse.Namespace(
        command="forward",
        duration=1,
        speed=0.5,
        obstacle_threshold_cm=20.0,
        obstacle_check_interval=0.2,
    )

    cli.run_command(args)

    assert calls == ["forward", "stop", "car cleanup"]
    assert sensor.cleanup_calls == 1
    assert "Obstacle détecté" in capsys.readouterr().out


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
    controller = RobotController(
        _car(monkeypatch, None, clock),
        distance_sensor=sensor,
        obstacle_threshold_cm=5.0,
        sleep_fn=clock.sleep,
    )

    assert controller.check_obstacle() is True
    assert sensor.calls == 2


def test_no_sensor_obstacle_policy(monkeypatch):
    clock = _Clock()
    robot = _car(monkeypatch, None, clock)
    assert RobotController(robot).check_obstacle() is False
    assert RobotController(robot, require_obstacle_sensor=True).check_obstacle() is True


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
