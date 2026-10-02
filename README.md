# smart-router

A Claude Code plugin that saves tokens on simple, mechanical prompts by nudging Claude to hand them to a cheaper Haiku subagent.

## What it does

A `UserPromptSubmit` hook scores every prompt with free keyword and length rules. No API calls, no network. When a prompt looks simple and mechanical (a rename, a typo fix, running the tests), the hook adds a short note telling Claude to delegate the work to the `quick-helper` subagent, which runs on Haiku. Claude then reports the result in a sentence or two.

The hook never blocks a prompt and never changes your main model.

## Why a subagent and not a model switch

Switching the main model mid-session invalidates the prompt cache: the next turn has to re-read the whole conversation at full price. A subagent runs in its own context on its own model, so your main conversation, and its cache, stay untouched.

## Install

```
/plugin marketplace add Tornike512/smart-router
/plugin install smart-router@smart-router
```

## Tags and environment variables

| Setting | Effect |
| --- | --- |
| `[cheap]` anywhere in a prompt | Force "simple": suggest delegation |
| `[strong]` anywhere in a prompt | Force "complex": never delegate (wins over `[cheap]`) |
| `SMART_ROUTER=off` | Disable the hook |
| `SMART_ROUTER_DEBUG=1` | Append each decision (time, label, score, reasons, first 80 characters of the prompt) to `~/.claude/smart-router.log` |

Prompts starting with `/` or `!` are skipped.

## How it decides

`classify(prompt)` returns a label (`simple`, `normal` or `complex`), a score and the reasons.

- Complex hints add 2 each: architecture, design, refactor, debug/why/root cause, bug/broken/crash/failing, investigate, plan/strategy, migrate, performance, security, concurrency, algorithms, trade-offs, review, wide scope ("entire codebase", "from scratch").
- Simple hints subtract 2 each: rename, typo, formatting/lint, comments/docstrings, running tests/linter/build, listing files, finding usages, boilerplate, README/changelog/.gitignore, version bump, sort, imports, commit messages.
- Other signals: error output +3, code block +1, 12 words or fewer -1, over 40 words +1, over 120 words +3, three or more list lines +2.

A prompt is **simple** only if it has at least one simple hint, no complex hints, no error output, and 60 words or fewer. It is **complex** if the score is 3 or more. Everything else is **normal**. Only simple prompts get the nudge. The rules are deliberately conservative: sending a hard task to Haiku is worse than missing a saving.

## Limitations

- It is a nudge. Claude can ignore it, and does when it can finish in one quick step.
- English keywords only.
- Needs Python 3 (standard library only). On Windows, install it from python.org; the Microsoft Store stub does not work. If no Python is found, the hook prints a note to stderr and does nothing.

## Test locally

```
python3 tests/test_router.py
claude --plugin-dir ./plugins/smart-router
```

Validate the manifests:

```
claude plugin validate --strict ./plugins/smart-router
claude plugin validate --strict .
```

## Releasing updates

1. Change the code and bump `version` in `plugins/smart-router/.claude-plugin/plugin.json`.
2. Run the tests and the validators above.
3. Commit and push to `main`.
4. Users run `/plugin marketplace update smart-router` and then update the plugin.

## License

MIT, by tornike512.
