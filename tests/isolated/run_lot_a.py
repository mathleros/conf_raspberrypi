"""Explicit offline selection. Run with python -I -S; never collect globally."""

from __future__ import annotations

import importlib.abc
import importlib.util
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import types
import unittest


ROOT = Path(__file__).resolve().parents[2]
SELECTED = (
    "test_follow_object.py", "test_follow_object_wiring.py",
    "test_scenario_yellow_ball.py", "test_primitive_safety_stop.py",
    "test_emergency_stop.py", "test_skills_primitives.py",
    "test_language_controller.py", "test_plan_guards.py", "test_voice_runtime.py",
)


class IsolationViolation(RuntimeError):
    pass


VIOLATIONS: list[str] = []
POLICY_PROBES: list[str] = []


def forbidden(label: str):
    VIOLATIONS.append(label)
    raise IsolationViolation(label)


class ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith((
            "irobot.hardware", "gpiozero", "RPi", "cv2", "picamera",
            "sounddevice", "pyaudio", "bluetooth", "vosk",
            "tests.integration", "tests.hardware",
        )):
            forbidden("import:" + fullname)
        return None


def audit(event, args):
    if event.startswith(("socket.", "subprocess.", "os.system", "os.posix_spawn", "os.exec", "os.fork")):
        forbidden(event)
    if event in {"open", "os.scandir", "os.listdir"} and args and isinstance(args[0], (str, bytes)):
        path = os.fsdecode(args[0])
        parts = Path(path).parts
        if ("models" in parts or "llama.cpp" in parts
                or (path.startswith("/dev/") and path != "/dev/null")):
            forbidden(event + ":" + path)


def install_guards():
    sys.meta_path.insert(0, ImportGuard())
    sys.addaudithook(audit)
    # Explicit complementary ports, installed BEFORE project imports/discovery.
    audio = types.ModuleType("irobot.hardware.audio.audio_utils")
    audio.resolve_input_device = lambda *_: forbidden("audio")
    sys.modules[audio.__name__] = audio
    vosk = types.ModuleType("vosk")
    vosk.Model = lambda *_: forbidden("vosk.Model")
    vosk.KaldiRecognizer = lambda *_: forbidden("vosk.KaldiRecognizer")
    sys.modules["vosk"] = vosk
    requests = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    class HTTPError(RequestException):
        pass

    class ConnectionError(RequestException):
        pass

    class Timeout(RequestException):
        pass

    class ReadTimeout(Timeout):
        pass

    requests.RequestException = RequestException
    requests.HTTPError = HTTPError
    requests.ConnectionError = ConnectionError
    requests.Timeout = Timeout
    requests.ReadTimeout = ReadTimeout
    requests.exceptions = types.SimpleNamespace(
        RequestException=RequestException, HTTPError=HTTPError,
        ConnectionError=ConnectionError, Timeout=Timeout, ReadTimeout=ReadTimeout,
    )
    requests.post = lambda *a, **k: forbidden("requests.post without explicit scenario double")
    sys.modules["requests"] = requests


def check_policy_without_resource_access():
    probes = (
        lambda: ImportGuard().find_spec("gpiozero"),
        lambda: audit("socket.connect", (None,)),
        lambda: audit("open", ("/dev/gpiomem", "r")),
    )
    for probe in probes:
        try:
            probe()
        except IsolationViolation as exc:
            if VIOLATIONS[-1] != str(exc):
                raise AssertionError("isolation observer inconsistent")
            POLICY_PROBES.append(VIOLATIONS.pop())
        else:
            raise AssertionError("isolation policy did not reject synthetic probe")


def main():
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("Use python -I -S to exclude site initialization and user paths")
    stdlib = "--stdlib" in sys.argv
    legacy = "--legacy-stdlib" in sys.argv
    arguments = [arg for arg in sys.argv[1:] if arg not in {"--stdlib", "--legacy-stdlib"}]
    root = Path(arguments[0]).resolve() if arguments else ROOT
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    for key in tuple(os.environ):
        if key.startswith(("PYTEST_ADDOPTS", "IROBOT_", "LLM_")):
            del os.environ[key]
    install_guards()
    check_policy_without_resource_access()
    sys.path[:0] = [str(root / "src"), str(root)]
    def timeout(*_):
        forbidden("external campaign wall bound exceeded (120 s)")

    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(120)
    before_threads = set(threading.enumerate())
    paths = [str(root / "tests" / "unit" / name) for name in SELECTED]
    with tempfile.TemporaryDirectory(prefix="irobot-lot-a-") as work:
        os.chdir(work)
        if stdlib or legacy:
            if legacy:
                spec = importlib.util.spec_from_file_location(
                    "lot_a_legacy_contract", ROOT / "tests" / "isolated" / "legacy_contract.py",
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                suite = unittest.defaultTestLoader.loadTestsFromModule(module)
            else:
                suite = unittest.defaultTestLoader.loadTestsFromName("tests.isolated.lot_a_cases")
            outcome = unittest.TextTestRunner(verbosity=2).run(suite)
            result = 0 if outcome.wasSuccessful() else 1
        else:
            packages = ROOT / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
            if not (packages / "pytest" / "__init__.py").is_file():
                raise RuntimeError("BLOCKED: pytest is not installed locally; do not install automatically")
            # Do not use site.addsitedir: .pth startup code must never execute here.
            sys.path.append(str(packages))
            import pytest
            result = pytest.main([
                "-q", "--noconftest", "--confcutdir=" + work,
                "-p", "no:cacheprovider", "--basetemp=" + work + "/pytest",
                "-k", "not warmup and not warm_up",
                *paths,
            ])
    signal.alarm(0)
    remaining = set(threading.enumerate()) - before_threads
    print(f"ISOLATION: forbidden accesses={len(VIOLATIONS)}; residual threads={len(remaining)}")
    print(f"POLICY: {len(POLICY_PROBES)} synthetic probes rejected; no resource operation performed")
    if VIOLATIONS or remaining:
        print("INCONCLUSIVE/FAILED ISOLATION:", VIOLATIONS, [t.name for t in remaining])
        return 2
    return result


if __name__ == "__main__":
    raise SystemExit(main())
