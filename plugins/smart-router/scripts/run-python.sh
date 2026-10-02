#!/usr/bin/env bash
# Run a Python 3 script with whichever interpreter works. Never fails the hook.
# Probes by actually running Python, which skips the Windows Store stub.

script="$1"
shift

for candidate in "python3" "python" "py -3"; do
  # shellcheck disable=SC2086
  if $candidate -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    exec $candidate "$script" "$@"
  fi
done

echo "smart-router: no working Python 3 found, skipping." >&2
exit 0
