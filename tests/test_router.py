#!/usr/bin/env python3
"""No-dependency tests. Run with: python3 tests/test_router.py"""

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "smart-router")
SCRIPTS = os.path.join(PLUGIN, "scripts")
sys.path.insert(0, SCRIPTS)

import route  # noqa: E402

CASES = {
    "simple": [
        "fix the typo in the README",
        "add docstrings to every function in utils.py",
        "rename getUser to fetchUser everywhere",
        "run the tests and tell me what fails",
        "which files use the old logger?",
        "[cheap] explain this regex",
    ],
    "normal": [
        "what does this function do?",
        "add a loading spinner to the settings page",
        "review the README for typos",
        "rename the user service across the entire codebase",
        "sort out the bug in checkout",
        "what format should the API return?",
    ],
    "complex": [
        "why does the login test fail? Traceback (most recent call last): ...",
        "design a caching layer for our API and plan the migration",
        "refactor the payment module for thread safety and explain the trade-offs",
        "[strong] fix the typo in the README",
    ],
}

failures = []


def check(name, ok, detail=""):
    if not ok:
        failures.append(f"{name} {detail}".strip())
        print(f"FAIL  {name} {detail}")
    else:
        print(f"ok    {name}")


def run_hook(stdin_text, extra_env=None):
    env = dict(os.environ)
    env.pop("SMART_ROUTER", None)
    env.pop("SMART_ROUTER_DEBUG", None)
    env["HOME"] = tempfile.mkdtemp()
    env.update(extra_env or {})
    proc = subprocess.run(
        [
            "bash",
            os.path.join(SCRIPTS, "run-python.sh"),
            os.path.join(SCRIPTS, "route.py"),
        ],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout.strip()


for expected, prompts in CASES.items():
    for prompt in prompts:
        label, score, reasons = route.classify(prompt)
        check(f"classify[{expected}] {prompt!r}", label == expected, f"got {label} ({score}, {reasons})")

code, out = run_hook(json.dumps({"prompt": "fix the typo in the README"}))
check("hook: simple prompt exits 0", code == 0)
check("hook: simple prompt mentions quick-helper", "quick-helper" in out)
try:
    parsed = json.loads(out)
    hso = parsed["hookSpecificOutput"]
    check(
        "hook: output shape",
        hso["hookEventName"] == "UserPromptSubmit" and "additionalContext" in hso,
    )
except Exception as exc:
    check("hook: output shape", False, str(exc))

code, out = run_hook(json.dumps({"user_prompt": "fix the typo in the README"}))
check("hook: user_prompt field works", code == 0 and "quick-helper" in out)

code, out = run_hook(json.dumps({"prompt": "design a caching layer and plan the migration"}))
check("hook: complex prompt outputs nothing", code == 0 and out == "")

code, out = run_hook(json.dumps({"prompt": "/model"}))
check("hook: slash command outputs nothing", code == 0 and out == "")

code, out = run_hook(json.dumps({"prompt": "!ls"}))
check("hook: bang command outputs nothing", code == 0 and out == "")

code, out = run_hook("not json {")
check("hook: invalid JSON exits 0 silently", code == 0 and out == "")

code, out = run_hook(
    json.dumps({"prompt": "fix the typo in the README"}), {"SMART_ROUTER": "off"}
)
check("hook: SMART_ROUTER=off outputs nothing", code == 0 and out == "")

home = tempfile.mkdtemp()
env = dict(os.environ, HOME=home, SMART_ROUTER_DEBUG="1")
env.pop("SMART_ROUTER", None)
subprocess.run(
    ["bash", os.path.join(SCRIPTS, "run-python.sh"), os.path.join(SCRIPTS, "route.py")],
    input=json.dumps({"prompt": "fix the typo in the README"}),
    capture_output=True,
    text=True,
    env=env,
)
log = os.path.join(home, ".claude", "smart-router.log")
check("hook: SMART_ROUTER_DEBUG=1 writes log", os.path.exists(log) and "simple" in open(log).read())

print()
if failures:
    print(f"{len(failures)} failure(s)")
    sys.exit(1)
print("all passed")
