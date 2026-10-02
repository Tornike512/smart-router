#!/usr/bin/env python3
"""smart-router: UserPromptSubmit hook.

Scores a prompt with free keyword and length rules. When the prompt looks
simple and mechanical, adds context nudging Claude to delegate to the
quick-helper subagent (Haiku). Never blocks a prompt, never switches the main
model, and exits 0 with no output on any error.
"""

import json
import os
import re
import sys
import time

COMPLEX_HINTS = [
    ("architecture", r"\barchitect(?:ure|ural)?\b"),
    ("design", r"\bdesign(?:s|ed|ing)?\b"),
    ("refactor", r"\brefactor\w*"),
    ("debugging", r"\bdebug\w*|\bwhy\b|\broot cause\b"),
    ("bug report", r"\b(?:bugs?|broken|crash(?:es|ed|ing)?|failing|not working)\b"),
    ("investigation", r"\binvestigat\w*"),
    ("planning", r"\bplan(?:s|ning)?\b|\bstrateg\w*"),
    ("migration", r"\bmigrat\w*"),
    ("performance", r"\bperformance\b|\boptimi[sz]\w*|\bslow\w*"),
    ("security", r"\bsecurity\b|\bauthenticat\w*|\bauthoriz\w*"),
    (
        "concurrency",
        r"\bconcurren\w*|\brace conditions?\b|\bthread[- ]safe\w*|\bthread safety\b",
    ),
    ("algorithms", r"\balgorithms?\b"),
    ("trade-offs", r"\btrade-?offs?\b|\bshould i\b|\bbest way\b"),
    ("review", r"\breview\w*"),
    (
        "wide scope",
        r"\b(?:entire|whole)\s+(?:codebase|repo|repository|project|code base)\b"
        r"|\bfrom scratch\b",
    ),
]

SIMPLE_HINTS = [
    ("rename", r"\brenam\w*"),
    ("typo", r"\btypos?\b|\bmisspell\w*|\bspelling\b"),
    (
        "formatting",
        r"\b(?:re)?format\s+(?:the\s+|this\s+|these\s+|my\s+|all\s+|every\s+)?"
        r"(?:code|files?|source|project|repo|codebase)\b"
        r"|\bformatting\b|\bprettier\b|\blint\w*",
    ),
    (
        "comments/docstrings",
        r"\bdocstrings?\b|\b(?:add|write|update)\s+(?:\w+\s+)?comments?\b|\bjsdoc\b",
    ),
    (
        "run tests/linter",
        r"\brun\s+(?:the\s+|all\s+|my\s+|our\s+)?(?:unit\s+|existing\s+)?"
        r"(?:tests?|test suite|linters?|lint|build)\b",
    ),
    ("list files", r"\blist\s+(?:the\s+|all\s+)?(?:files|directories|folders)\b"),
    (
        "find usages",
        r"\bwhere (?:is|are)\b|\bwhich files?\b"
        r"|\bfind\s+(?:all\s+)?(?:usages?|references?|uses|callers)\b",
    ),
    ("boilerplate", r"\bboilerplate\b|\bstubs?\b|\bscaffold\w*"),
    ("docs/config file", r"\breadme\b|\bchangelog\b|\bgitignore\b"),
    ("version bump", r"\bbump\b|\bversion bump\b"),
    ("sort", r"\bsort(?:s|ed|ing)?\b(?!\s+out\b)"),
    (
        "imports",
        r"\bunused imports?\b|\borgani[sz]e\s+(?:the\s+|my\s+|all\s+)?imports?\b"
        r"|\bimports?\s+organi[sz]\w*",
    ),
    ("commit message", r"\bcommit messages?\b"),
]

ERROR_RE = re.compile(
    r"Traceback \(most recent call last\)|\b[A-Za-z_]\w*(?:Error|Exception):"
)
LIST_LINE_RE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+", re.MULTILINE)

COMPLEX_HINTS = [(n, re.compile(p, re.IGNORECASE)) for n, p in COMPLEX_HINTS]
SIMPLE_HINTS = [(n, re.compile(p, re.IGNORECASE)) for n, p in SIMPLE_HINTS]

NOTE = (
    "[smart-router] This request looks simple and mechanical ({reasons}). "
    "To save tokens: if it will take more than a couple of tool calls, hand it "
    "to the quick-helper agent (it runs on a cheaper model), then report its "
    "result in a sentence or two. If you can do it in one quick step or answer "
    "in a few sentences, just do that yourself. If it turns out to be harder "
    "than it looks, handle it yourself."
)


def classify(prompt):
    """Return (label, score, reasons); label is simple, normal or complex."""
    lowered = prompt.lower()
    if "[strong]" in lowered:
        return "complex", 99, ["tag [strong]"]
    if "[cheap]" in lowered:
        return "simple", -99, ["tag [cheap]"]

    words = len(prompt.split())
    score = 0
    simple_reasons = []
    complex_reasons = []

    for name, pattern in COMPLEX_HINTS:
        if pattern.search(prompt):
            score += 2
            complex_reasons.append(name)
    for name, pattern in SIMPLE_HINTS:
        if pattern.search(prompt):
            score -= 2
            simple_reasons.append(name)

    has_error = bool(ERROR_RE.search(prompt))
    if has_error:
        score += 3
        complex_reasons.append("error output")
    if "```" in prompt:
        score += 1
    if words <= 12:
        score -= 1
    if words > 120:
        score += 3
    elif words > 40:
        score += 1
    if len(LIST_LINE_RE.findall(prompt)) >= 3:
        score += 2

    if score >= 3:
        return "complex", score, complex_reasons or ["long or structured prompt"]
    if simple_reasons and not complex_reasons and not has_error and words <= 60:
        return "simple", score, simple_reasons
    return "normal", score, complex_reasons or simple_reasons


def log_decision(label, score, reasons, prompt):
    path = os.path.join(os.path.expanduser("~"), ".claude", "smart-router.log")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    snippet = " ".join(prompt[:80].split())
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{stamp}\t{label}\t{score}\t{','.join(reasons)}\t{snippet}\n")


def main():
    if os.environ.get("SMART_ROUTER", "").strip().lower() == "off":
        return
    data = json.load(sys.stdin)
    prompt = data.get("prompt") or data.get("user_prompt") or ""
    if not isinstance(prompt, str):
        return
    prompt = prompt.strip()
    if not prompt or prompt[0] in "/!":
        return

    label, score, reasons = classify(prompt)

    if os.environ.get("SMART_ROUTER_DEBUG") == "1":
        try:
            log_decision(label, score, reasons, prompt)
        except Exception:
            pass

    if label != "simple":
        return
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": NOTE.format(reasons=", ".join(reasons)),
        }
    }
    sys.stdout.write(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
