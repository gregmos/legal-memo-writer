"""Smoke tests for scripts/log_event.py.

Run from the plugin root:
    python -m unittest scripts.tests.test_log_event

Verifies:
- Event is appended to <workdir>/events.jsonl with the canonical schema.
- All required fields (ts, event, phase, iteration, actor, severity, data) are present.
- Multiple invocations append (not overwrite).
- Bad --data JSON returns non-zero without crashing.
- Bad --severity rejected by argparse.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "scripts" / "log_event.py"

ISO_MS_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def run_log_event(workdir: Path, **kwargs) -> tuple[int, str, str]:
    args = [sys.executable, str(SCRIPT), "--workdir", str(workdir)]
    for k, v in kwargs.items():
        args.extend([f"--{k}", str(v)])
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def read_events(workdir: Path) -> list[dict]:
    p = workdir / "events.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


class LogEventTests(unittest.TestCase):
    def test_appends_minimal_event(self):
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            code, out, err = run_log_event(
                wd,
                event="phase_transition",
                actor="memo-skill",
                data='{"from":"intake_preliminary_research","to":"intake_questions_pending"}',
            )
            self.assertEqual(code, 0, msg=f"stderr={err}")
            events = read_events(wd)
            self.assertEqual(len(events), 1)
            ev = events[0]
            for key in ("ts", "event", "phase", "iteration", "actor", "severity", "data"):
                self.assertIn(key, ev)
            self.assertEqual(ev["event"], "phase_transition")
            self.assertEqual(ev["actor"], "memo-skill")
            self.assertEqual(ev["severity"], "info")
            self.assertIsNone(ev["phase"])
            self.assertIsNone(ev["iteration"])
            self.assertEqual(ev["data"]["to"], "intake_questions_pending")
            self.assertTrue(ISO_MS_REGEX.match(ev["ts"]), msg=ev["ts"])

    def test_full_event_with_phase_iteration_severity(self):
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            code, _, err = run_log_event(
                wd,
                event="agent_returned",
                phase="revision_loop",
                iteration=2,
                actor="memo-skill",
                severity="warn",
                data='{"subagent_type":"logic-reviewer","duration_seconds":47,"verdict":"needs_revision"}',
            )
            self.assertEqual(code, 0, msg=err)
            events = read_events(wd)
            self.assertEqual(len(events), 1)
            ev = events[0]
            self.assertEqual(ev["phase"], "revision_loop")
            self.assertEqual(ev["iteration"], 2)
            self.assertEqual(ev["severity"], "warn")
            self.assertEqual(ev["data"]["duration_seconds"], 47)

    def test_appends_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            for i, event_name in enumerate(["task_created", "mcp_precheck_result", "phase_transition"], start=1):
                code, _, err = run_log_event(
                    wd,
                    event=event_name,
                    actor="memo-skill",
                    data=f'{{"i":{i}}}',
                )
                self.assertEqual(code, 0, msg=err)
            events = read_events(wd)
            self.assertEqual(len(events), 3)
            self.assertEqual([e["event"] for e in events], ["task_created", "mcp_precheck_result", "phase_transition"])

    def test_bad_data_json_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            code, _, err = run_log_event(
                wd,
                event="phase_transition",
                actor="memo-skill",
                data="not-json",
            )
            self.assertEqual(code, 2)
            self.assertIn("invalid --data JSON", err)
            # No event should have been written
            self.assertEqual(read_events(wd), [])

    def test_data_must_be_object_not_array(self):
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            code, _, err = run_log_event(
                wd,
                event="phase_transition",
                actor="memo-skill",
                data='["this","is","an","array"]',
            )
            self.assertEqual(code, 2)
            self.assertIn("must be a JSON object", err)

    def test_workdir_autocreated_if_missing(self):
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td) / "deep" / "nested" / "task"
            # Do NOT mkdir — log_event must create parents.
            code, _, err = run_log_event(
                wd,
                event="task_created",
                actor="memo-skill",
                data="{}",
            )
            self.assertEqual(code, 0, msg=err)
            self.assertTrue((wd / "events.jsonl").exists())

    def test_invalid_severity_rejected_by_argparse(self):
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            code, _, err = run_log_event(
                wd,
                event="phase_transition",
                actor="memo-skill",
                severity="critical",  # not in {info, warn, error}
                data="{}",
            )
            self.assertNotEqual(code, 0)
            self.assertIn("invalid choice", err)

    def test_unicode_in_data_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            code, _, err = run_log_event(
                wd,
                event="gate_answered",
                actor="memo-skill",
                data='{"chosen":"Запрос на правки","reason":"Юзер передумал"}',
            )
            self.assertEqual(code, 0, msg=err)
            events = read_events(wd)
            self.assertEqual(events[0]["data"]["chosen"], "Запрос на правки")


if __name__ == "__main__":
    unittest.main()
