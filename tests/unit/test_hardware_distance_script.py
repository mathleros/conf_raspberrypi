from pathlib import Path
import runpy
import sys
from types import ModuleType


def test_distance_script_initializes_gpio_with_supported_arguments(monkeypatch, capsys):
    devices = []

    class OutputDevice:
        def __init__(self, pin):
            self.pin = pin
            self.closed = False
            devices.append(self)

        def close(self):
            self.closed = True

    class InputDevice(OutputDevice):
        def __init__(self, pin, *, pull_up):
            super().__init__(pin)
            self.pull_up = pull_up

    gpiozero = ModuleType("gpiozero")
    gpiozero.DigitalInputDevice = InputDevice
    gpiozero.DigitalOutputDevice = OutputDevice
    monkeypatch.setitem(sys.modules, "gpiozero", gpiozero)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_hardware_distance.py",
            "--trigger-pin", "17",
            "--echo-pin", "27",
            "--duration", "0",
        ],
    )
    script = Path(__file__).resolve().parents[1] / "hardware" / "test_hardware_distance.py"

    runpy.run_path(str(script), run_name="__main__")

    assert [device.pin for device in devices] == [17, 27]
    assert devices[1].pull_up is False
    assert all(device.closed for device in devices)
    assert "Aucune distance" in capsys.readouterr().out
