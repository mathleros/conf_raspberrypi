#!/usr/bin/env python3
"""Test minimal de connectivité et de délai de réponse du LLM local.

Usage:
  python scripts/test/check_llm_latency.py
  python scripts/test/check_llm_latency.py --base-url http://127.0.0.1:8080 --read-timeout 30
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from urllib.parse import urlparse

import requests

DEFAULT_MODEL = os.environ.get("LLM_MODEL", "qwen2.5-1.5b")


def _run_step(name: str, fn) -> tuple[bool, float, str]:
    started = time.perf_counter()
    try:
        detail = fn()
        return True, time.perf_counter() - started, detail
    except requests.exceptions.ConnectTimeout:
        return False, time.perf_counter() - started, "connect timeout"
    except requests.exceptions.ReadTimeout:
        return False, time.perf_counter() - started, "read timeout"
    except requests.exceptions.RequestException as exc:
        return False, time.perf_counter() - started, f"HTTP error: {exc}"
    except OSError as exc:
        return False, time.perf_counter() - started, f"socket error: {exc}"
    except Exception as exc:  # pragma: no cover - garde-fou diagnostic
        return False, time.perf_counter() - started, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--connect-timeout", type=float, default=1.0)
    parser.add_argument("--read-timeout", type=float, default=20.0)
    args = parser.parse_args()

    parsed = urlparse(args.base_url)
    if not parsed.hostname:
        print("[FAIL] base-url invalide: hostname manquant")
        return 1

    timeout = (args.connect_timeout, args.read_timeout)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    def tcp_connect() -> str:
        with socket.create_connection((host, port), timeout=args.connect_timeout):
            return f"{host}:{port}"

    def list_models() -> str:
        response = requests.get(f"{args.base_url}/v1/models", timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        count = len(payload.get("data", [])) if isinstance(payload, dict) else 0
        return f"HTTP {response.status_code}, {count} model(s)"

    def chat_completion() -> str:
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": "Réponds uniquement: ok"}],
            "temperature": 0,
            "max_tokens": 8,
        }
        response = requests.post(
            f"{args.base_url}/v1/chat/completions",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
        text = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        return f"HTTP {response.status_code}, réponse={text!r}"

    checks = [
        ("Connexion TCP", tcp_connect),
        ("GET /v1/models", list_models),
        ("POST /v1/chat/completions (warm-up)", chat_completion),
        ("POST /v1/chat/completions (à chaud)", chat_completion),
    ]

    print(f"Base URL: {args.base_url}")
    print(
        f"Timeouts: connect={args.connect_timeout}s read={args.read_timeout}s | model={args.model}"
    )

    all_ok = True
    for name, fn in checks:
        ok, elapsed, detail = _run_step(name, fn)
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {name} - {elapsed:.2f}s - {detail}")
        if not ok:
            all_ok = False
            break

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())