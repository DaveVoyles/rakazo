#!/usr/bin/env python3
"""Fail-open contract for typesafe-classify.

classify() must NEVER raise, and must return None on every failure path --
disabled, missing key, network error, timeout, malformed response, low
confidence on ANY of the three questions, or a tripped breaker. It must also
never send more than subject/sender-domain/redacted-snippet.

Run: python3 typesafe-classify.test.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import urllib.error
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
_loader = SourceFileLoader("typesafe_classify", str(HERE / "typesafe-classify"))
spec = importlib.util.spec_from_loader(_loader.name, _loader)
tc = importlib.util.module_from_spec(spec)
sys.modules[_loader.name] = tc
_loader.exec_module(tc)

failures: list[str] = []
checks = 0


def check(ok: bool, label: str, detail: object = "") -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(f"{label} -- {detail}" if detail else label)


class _FakeResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _clean_env():
    tc.reset_breaker_for_test()
    for k in ("RAKAZO_TYPESAFE_ENABLED", "RAKAZO_TYPESAFE_API_KEY",
              "RAKAZO_TYPESAFE_TIMEOUT_SECS", "RAKAZO_TYPESAFE_MIN_CONFIDENCE"):
        os.environ.pop(k, None)


GOOD_BODY = {
    "answers": {
        "urgency": {"choice": "now", "confidence": 0.95},
        "requires_reply": {"choice": "yes", "confidence": 0.93},
        "nature": {"choice": "actionable", "confidence": 0.92},
    }
}

# --- disabled by default ---------------------------------------------------
_clean_env()
result = tc.classify("Server down", "ops@example.com", "please look at this now")
check(result is None, "D1: classify() returns None when RAKAZO_TYPESAFE_ENABLED is unset (default off)")

# --- explicitly disabled ----------------------------------------------------
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "0"
os.environ["RAKAZO_TYPESAFE_API_KEY"] = "fake-key"
result = tc.classify("Server down", "ops@example.com", "please look at this now")
check(result is None, "D2: classify() returns None when explicitly disabled, even with a key present")

# --- enabled, no key anywhere -----------------------------------------------
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "1"
with mock.patch("subprocess.run") as m:
    m.return_value = subprocess.CompletedProcess(args=[], returncode=44, stdout="", stderr="not found")
    result = tc.classify("Server down", "ops@example.com", "please look at this now")
check(result is None, "D3: classify() returns None when enabled but no API key is available")

# --- enabled, empty subject and snippet -------------------------------------
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "1"
os.environ["RAKAZO_TYPESAFE_API_KEY"] = "fake-key"
result = tc.classify("", "ops@example.com", "")
check(result is None, "D4: classify() returns None with no subject and no snippet, no network call made")

# --- network error never raises ---------------------------------------------
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "1"
os.environ["RAKAZO_TYPESAFE_API_KEY"] = "fake-key"
raised = False
with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no route")):
    try:
        result = tc.classify("Server down", "ops@example.com", "please look at this now")
    except Exception:
        raised = True
check(not raised, "D5: a network error is caught inside classify(), never propagated")
check(result is None, "D5b: a network error resolves to None")

# --- timeout never raises ----------------------------------------------------
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "1"
os.environ["RAKAZO_TYPESAFE_API_KEY"] = "fake-key"
raised = False
with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
    try:
        result = tc.classify("Server down", "ops@example.com", "please look at this now")
    except Exception:
        raised = True
check(not raised, "D6: a timeout is caught inside classify(), never propagated")
check(result is None, "D6b: a timeout resolves to None")

# --- malformed response never raises ----------------------------------------
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "1"
os.environ["RAKAZO_TYPESAFE_API_KEY"] = "fake-key"
raised = False
with mock.patch("urllib.request.urlopen", return_value=_FakeResponse({"unexpected": "shape"})):
    try:
        result = tc.classify("Server down", "ops@example.com", "please look at this now")
    except Exception:
        raised = True
check(not raised, "D7: a response missing an expected question is caught, never propagated")
check(result is None, "D7b: a malformed response resolves to None")

# --- low confidence on ANY of the three questions discards the whole answer -
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "1"
os.environ["RAKAZO_TYPESAFE_API_KEY"] = "fake-key"
os.environ["RAKAZO_TYPESAFE_MIN_CONFIDENCE"] = "0.9"
mixed_body = {
    "answers": {
        "urgency": {"choice": "now", "confidence": 0.95},
        "requires_reply": {"choice": "yes", "confidence": 0.40},  # below floor
        "nature": {"choice": "actionable", "confidence": 0.92},
    }
}
with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(mixed_body)):
    result = tc.classify("Server down", "ops@example.com", "please look at this now")
check(result is None, "D8: one low-confidence answer among three discards the whole result, not just that field")

# --- high confidence on all three returns a real result ---------------------
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "1"
os.environ["RAKAZO_TYPESAFE_API_KEY"] = "fake-key"
with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(GOOD_BODY)):
    result = tc.classify("Server down", "ops@example.com", "please look at this now")
check(result is not None, "D9: a high-confidence, well-formed response DOES return a TriageResult")
check(result is not None and result.urgency == "now", "D9b: urgency matches the response")
check(result is not None and result.requires_reply == "yes", "D9c: requires_reply matches the response")
check(result is not None and result.nature == "actionable", "D9d: nature matches the response")

# --- breaker trips after two failures in one process -------------------------
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "1"
os.environ["RAKAZO_TYPESAFE_API_KEY"] = "fake-key"
call_count = 0


def _counting_urlopen(*a, **kw):
    global call_count
    call_count += 1
    raise urllib.error.URLError("down")


with mock.patch("urllib.request.urlopen", side_effect=_counting_urlopen):
    tc.classify("s1", "a@example.com", "n1")
    tc.classify("s2", "a@example.com", "n2")
    tc.classify("s3", "a@example.com", "n3")
check(call_count == 2, "D10: after two failures the breaker trips and skips the network call entirely",
      f"urlopen was called {call_count} times, expected exactly 2")

# --- redaction: quoted replies and length cap -------------------------------
long_body = "line one\n" + ("x" * 50 + "\n") * 20
check(len(tc.redact_snippet(long_body)) <= tc.SNIPPET_MAX_CHARS,
      "D11: redact_snippet caps output at SNIPPET_MAX_CHARS")
quoted = "new content here\n> old quoted line\n> another quoted line"
check(tc.redact_snippet(quoted) == "new content here",
      "D12: redact_snippet strips '>'-quoted lines")
thread = "my new reply\nOn Tue, Jan 1, 2030, Alice wrote:\n> the old thread"
check(tc.redact_snippet(thread) == "my new reply",
      "D13: redact_snippet stops at an 'On ... wrote:' quote header")

# --- only subject/sender-domain/snippet ever reach the request payload -----
_clean_env()
os.environ["RAKAZO_TYPESAFE_ENABLED"] = "1"
os.environ["RAKAZO_TYPESAFE_API_KEY"] = "fake-key"
_sent = {}


def _capturing_urlopen(req, timeout=None):
    _sent["data"] = json.loads(req.data)
    return _FakeResponse(GOOD_BODY)


with mock.patch("urllib.request.urlopen", side_effect=_capturing_urlopen):
    tc.classify("Server down", "alice@example.com", "please look at this now")
check(_sent.get("data", {}).get("state", {}).get("sender_domain") == "example.com",
      "D14: only the sender's domain is sent, not the local part before @")
check("alice" not in json.dumps(_sent.get("data", {})),
      "D15: the sender's local part never appears anywhere in the request payload")

# --- CLI: silent, exit 0, on every fallback path ----------------------------
_clean_env()
env = dict(os.environ)
for k in ("RAKAZO_TYPESAFE_ENABLED", "RAKAZO_TYPESAFE_API_KEY"):
    env.pop(k, None)
r = subprocess.run(
    [sys.executable, str(HERE / "typesafe-classify"),
     "--subject", "Server down", "--sender", "ops@example.com",
     "--snippet", "please look at this now"],
    env=env, capture_output=True, text=True, timeout=10,
)
check(r.returncode == 0, "D16: the CLI exits 0 with TypeSafe disabled (default)", r.stderr)
check(r.stdout.strip() == "", "D17: the CLI prints nothing with TypeSafe disabled (default)", r.stdout)


def main() -> int:
    for f in failures:
        print(f"typesafe-classify.test: FAIL {f}", file=sys.stderr)
    print(f"== {checks - len(failures)} passed, {len(failures)} failed ==")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
