#!/usr/bin/env python3
"""Append a structured event to events.jsonl per the canonical schema.

Canonical schema (events-contract.md §Schema v1):

    {
      "ts": "<ISO 8601 with milliseconds, UTC>",
      "event": "<kebab-case event name>",
      "phase": "<state.current_phase at emit time, or null>",
      "iteration": <int or null>,
      "actor": "memo-skill | continue-skill | <agent-name> | validator | md_to_docx",
      "severity": "info | warn | error",
      "data": { ...event-specific payload... }
    }

Best-effort: if events.jsonl is not writable the script writes the error to
stderr and exits non-zero, but the caller (orchestrator) is documented in
`events-contract.md` to swallow this error and continue the pipeline. The
pipeline NEVER fails because logging failed.

Usage from Bash:

    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/log_event.py" \\
      --workdir "$WORK_DIR" \\
      --event phase_transition \\
      --phase research \\
      --actor memo-skill \\
      --data '{"from":"plan_approval_pending","to":"research","reason":"plan_approved"}'

`--phase` is the value of `state.json.current_phase` at the moment of emission;
for `phase_transition` events specifically, the `data.from` and `data.to`
fields tell the actual transition while `--phase` should be the NEW phase.

`--iteration` is omitted for events outside the revision loop.

`--data` MUST be a JSON object string (use single-quoted heredoc in Bash).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys


VALID_SEVERITY = ("info", "warn", "error")


def utc_iso_ms() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"


def append_event(events_path: pathlib.Path, event: dict) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append a canonical event to <workdir>/events.jsonl"
    )
    parser.add_argument("--workdir", required=True, help="Task working directory")
    parser.add_argument("--event", required=True, help="Event name (kebab-case)")
    parser.add_argument(
        "--phase",
        default=None,
        help="state.json.current_phase at emit time (null for pre-init events)",
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=None,
        help="Revision-loop iteration (omit outside revision_loop)",
    )
    parser.add_argument(
        "--actor",
        required=True,
        help="memo-skill | continue-skill | <agent-name> | validator | md_to_docx",
    )
    parser.add_argument(
        "--severity",
        default="info",
        choices=VALID_SEVERITY,
        help="info | warn | error (default: info)",
    )
    parser.add_argument(
        "--data",
        default="{}",
        help="Event-specific payload as a JSON object string (default: {})",
    )
    args = parser.parse_args()

    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f"log_event: invalid --data JSON: {exc.msg} at column {exc.colno}\n"
        )
        return 2
    if not isinstance(data, dict):
        sys.stderr.write("log_event: --data must be a JSON object\n")
        return 2

    event = {
        "ts": utc_iso_ms(),
        "event": args.event,
        "phase": args.phase,
        "iteration": args.iteration,
        "actor": args.actor,
        "severity": args.severity,
        "data": data,
    }

    events_path = pathlib.Path(args.workdir) / "events.jsonl"
    try:
        append_event(events_path, event)
    except OSError as exc:
        sys.stderr.write(f"log_event: could not write {events_path}: {exc}\n")
        return 1

    # On success the script is silent — the orchestrator does not need stdout.
    return 0


if __name__ == "__main__":
    sys.exit(main())
