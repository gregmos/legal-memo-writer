"""Unit tests for scripts/render_live_progress.py (v0.6.0 schema)."""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = THIS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import render_live_progress as r  # noqa: E402


FROZEN_NOW = dt.datetime(2026, 5, 26, 15, 45, 0, tzinfo=dt.timezone.utc)


def _state(
    current_phase="research",
    started_at_iso="2026-05-26T15:30:00+00:00",
    phase_started_at_iso="2026-05-26T15:40:00+00:00",
    timeline=None,
    mode="full",
    user_query="GDPR analysis on biometric data for minors",
    active_subagent=None,            # legacy v0.6.0-0.6.1 field (string); kept for backwards-compat tests
    active_subagents=None,           # v0.6.2+ field (list[str])
    source_counts=None,
    current_iteration=0,
    max_iterations=3,
    topic=None,
):
    if timeline is None:
        timeline = [
            {"phase": "intake_preliminary_research", "started_at_iso": "2026-05-26T15:30:00+00:00", "completed_at_iso": "2026-05-26T15:30:30+00:00"},
            {"phase": "mode_pick_pending", "started_at_iso": "2026-05-26T15:30:30+00:00", "completed_at_iso": "2026-05-26T15:30:45+00:00"},
            {"phase": "planning", "started_at_iso": "2026-05-26T15:30:45+00:00", "completed_at_iso": "2026-05-26T15:31:20+00:00"},
            {"phase": "plan_approval_pending", "started_at_iso": "2026-05-26T15:31:20+00:00", "completed_at_iso": "2026-05-26T15:32:00+00:00"},
            {"phase": "research", "started_at_iso": "2026-05-26T15:40:00+00:00", "completed_at_iso": None},
        ]
    return {
        "task_id": "memo-20260526T1530-gdpr-biometric-minors",
        "user_query": user_query,
        "current_phase": current_phase,
        "mode": mode,
        "current_iteration": current_iteration,
        "config": {
            "max_iterations": max_iterations,
        },
        "live_progress": {
            "started_at_iso": started_at_iso,
            "phase_started_at_iso": phase_started_at_iso,
            "timeline": timeline,
            "active_subagent": active_subagent,
            "active_subagents": active_subagents,
            "source_counts": source_counts,
            "topic": topic,
        },
    }


class TestFindPhaseIndex(unittest.TestCase):
    def test_maps_each_canonical_phase_to_some_index(self):
        for ph in [
            "intake_preliminary_research",
            "intake_questions_pending",
            "mode_pick_pending",
            "planning",
            "plan_approval_pending",
            "research",
            "research_sufficiency",
            "research_sufficiency_followup_pending",
            "currency_check",
            "source_pack",
            "source_review_pending",
            "drafting",
            "revision_loop",
            "client_readiness",
            "export",
            "done",
            "failed",
            "cancelled_by_user",
        ]:
            with self.subTest(phase=ph):
                idx = r.find_phase_index(ph)
                self.assertIsNotNone(idx, f"phase {ph} should map to a PHASES index")

    def test_unknown_phase_returns_none(self):
        self.assertIsNone(r.find_phase_index(""))
        self.assertIsNone(r.find_phase_index("nonsense_phase"))


class TestFormatElapsed(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(r.format_elapsed(0), "0s")
        self.assertEqual(r.format_elapsed(45), "45s")
        self.assertEqual(r.format_elapsed(59), "59s")

    def test_minutes(self):
        self.assertEqual(r.format_elapsed(60), "1m")
        self.assertEqual(r.format_elapsed(124), "2m 04s")
        self.assertEqual(r.format_elapsed(3599), "59m 59s")

    def test_hours(self):
        self.assertEqual(r.format_elapsed(3600), "1h")
        self.assertEqual(r.format_elapsed(3900), "1h 05m")
        self.assertEqual(r.format_elapsed(86399), "23h 59m")

    def test_days(self):
        self.assertEqual(r.format_elapsed(86400), "1d 00h")
        self.assertEqual(r.format_elapsed(90000), "1d 01h")

    def test_negative_seconds_clamped(self):
        self.assertEqual(r.format_elapsed(-30), "0s")


class TestRenderHtmlCore(unittest.TestCase):
    def test_includes_meta_charset_utf8(self):
        """Memory rule: every HTML written for Cowork artifacts must include UTF-8 meta."""
        html = r.render_html(_state(), current_step="Researching statute 3 of 8", now=FROZEN_NOW)
        self.assertIn('<meta charset="UTF-8">', html)

    def test_includes_task_id_in_output(self):
        html = r.render_html(_state(), current_step="x", now=FROZEN_NOW)
        self.assertIn("memo-20260526T1530-gdpr-biometric-minors", html)

    def test_includes_user_query_truncated(self):
        long_query = "A" * 200
        st = _state(user_query=long_query)
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("A" * 137, html)
        self.assertIn("…", html)

    def test_current_step_is_html_escaped(self):
        html = r.render_html(_state(), current_step="A & B <not a tag>", now=FROZEN_NOW)
        self.assertIn("A &amp; B &lt;not a tag&gt;", html)
        self.assertNotIn("<not a tag>", html)

    def test_phase_pill_current_marked_for_research(self):
        html = r.render_html(_state(current_phase="research"), current_step="x", now=FROZEN_NOW)
        self.assertIn('class="pill pill-current"', html)
        self.assertEqual(html.count('class="pill pill-current"'), 1)

    def test_completed_count_for_research(self):
        html = r.render_html(_state(current_phase="research"), current_step="x", now=FROZEN_NOW)
        self.assertIn("5 of 13 phases", html)

    def test_terminal_phase_marks_all_pills_completed(self):
        html = r.render_html(_state(current_phase="done"), current_step="Memo delivered.", now=FROZEN_NOW)
        self.assertEqual(html.count('class="pill pill-current"'), 0)
        self.assertEqual(html.count('class="pill pill-completed"'), 13)
        self.assertIn("13 of 13 phases", html)

    def test_terminal_phase_uses_hero_terminal_class(self):
        html_done = r.render_html(_state(current_phase="done"), current_step="x", now=FROZEN_NOW)
        html_running = r.render_html(_state(current_phase="research"), current_step="x", now=FROZEN_NOW)
        # CSS rules also mention `.hero.hero-terminal` — check the actual element class attribute.
        self.assertIn('class="hero hero-terminal"', html_done)
        self.assertIn('class="hero "', html_running)
        self.assertIn("pipeline complete", html_done)
        self.assertIn("pipeline alive", html_running)

    def test_extra_detail_rendered(self):
        html = r.render_html(_state(), current_step="x", extra_detail="iteration 2 of 3", now=FROZEN_NOW)
        self.assertIn("iteration 2 of 3", html)
        self.assertIn('class="extra-detail"', html)

    def test_extra_detail_omitted_when_none(self):
        html = r.render_html(_state(), current_step="x", extra_detail=None, now=FROZEN_NOW)
        self.assertNotIn('class="extra-detail"', html)

    def test_status_tag_rendered(self):
        html = r.render_html(_state(), current_step="x", status_tag="rate-limited fallback", now=FROZEN_NOW)
        self.assertIn("rate-limited fallback", html)
        self.assertIn('class="status-tag"', html)

    def test_timeline_running_phase_visible(self):
        html = r.render_html(_state(current_phase="research"), current_step="x", now=FROZEN_NOW)
        self.assertIn("Research", html)
        self.assertIn("(running)", html)

    def test_timeline_completed_phases_show_durations(self):
        html = r.render_html(_state(current_phase="research"), current_step="x", now=FROZEN_NOW)
        self.assertIn("30s", html)

    def test_timeline_empty_when_no_phases_completed(self):
        st = _state(timeline=[])
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("No phases completed yet", html)

    def test_mode_chip_uppercase(self):
        html_full = r.render_html(_state(mode="full"), current_step="x", now=FROZEN_NOW)
        html_brief = r.render_html(_state(mode="brief"), current_step="x", now=FROZEN_NOW)
        self.assertIn(">FULL<", html_full)
        self.assertIn(">BRIEF<", html_brief)

    def test_mode_chip_omitted_when_no_mode(self):
        st = _state(mode="")
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertNotIn('<span class="mode-chip', html)

    def test_unknown_current_phase_does_not_crash(self):
        st = _state(current_phase="some_future_phase_not_in_enum")
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertEqual(html.count('class="pill pill-current"'), 0)
        self.assertEqual(html.count('class="pill pill-future"'), 13)
        self.assertIn("0 of 13 phases", html)

    def test_missing_live_progress_block(self):
        st = {"task_id": "memo-x", "current_phase": "intake_preliminary_research", "user_query": "test"}
        html = r.render_html(st, current_step="Starting up", now=FROZEN_NOW)
        self.assertIn("Starting up", html)
        self.assertIn("No phases completed yet", html)

    def test_empty_user_query_does_not_break_layout(self):
        st = _state(user_query="")
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        # When query is empty, the query-line block is omitted entirely
        self.assertNotIn('class="query-line"', html)


class TestRenderHtmlV060NewElements(unittest.TestCase):
    """Tests for v0.6.0-specific elements: chips, JS block, data-* attrs, flat-design discipline."""

    def test_includes_javascript_block(self):
        """v0.6.0 ships an inline <script> block for setInterval-driven tickers."""
        html = r.render_html(_state(), current_step="x", now=FROZEN_NOW)
        self.assertIn("<script>", html)
        self.assertIn("setInterval", html)
        # The script must be self-contained — no actual fetch / postMessage CALLS.
        # The literal word "postMessage" appears in a comment naming forbidden APIs;
        # check the active call sites, not the substring.
        self.assertNotIn("fetch(", html)
        self.assertNotIn(".postMessage(", html)
        self.assertNotIn("window.postMessage", html)

    def test_phase_started_at_data_attribute(self):
        html = r.render_html(
            _state(phase_started_at_iso="2026-05-26T15:40:00+00:00"),
            current_step="x",
            now=FROZEN_NOW,
        )
        self.assertIn('data-phase-started-at-iso="2026-05-26T15:40:00+00:00"', html)
        self.assertIn('data-elapsed-tick="phase"', html)

    def test_started_at_data_attribute(self):
        html = r.render_html(
            _state(started_at_iso="2026-05-26T15:30:00+00:00"),
            current_step="x",
            now=FROZEN_NOW,
        )
        self.assertIn('data-started-at-iso="2026-05-26T15:30:00+00:00"', html)
        self.assertIn('data-elapsed-tick="total"', html)

    def test_render_iso_data_attribute_in_footer(self):
        html = r.render_html(_state(), current_step="x", now=FROZEN_NOW)
        self.assertIn('data-render-iso="2026-05-26T15:45:00+00:00"', html)
        self.assertIn('data-elapsed-tick="since-update"', html)

    def test_source_counts_chip_rendered_when_present(self):
        st = _state(source_counts={"statutes": 23, "cases": 14, "doctrine": 8})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn('class="chip chip-sources"', html)
        self.assertIn("23 statutes", html)
        self.assertIn("14 cases", html)
        self.assertIn("8 doctrine", html)
        self.assertIn("📊", html)

    def test_source_counts_chip_omitted_when_null(self):
        st = _state(source_counts=None)
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertNotIn('class="chip chip-sources"', html)
        self.assertNotIn("📊", html)

    def test_source_counts_alias_statute_singular_accepted(self):
        """Regression: agent wrote 'statute' (singular) instead of 'statutes' — must still render."""
        st = _state(source_counts={"statute": 8, "cases": 5, "doctrine": 6})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("8 statutes", html)
        self.assertIn("5 cases", html)
        self.assertIn("6 doctrine", html)

    def test_source_counts_alias_case_law_snake_accepted(self):
        """Regression: agent wrote 'case_law' (snake) instead of 'cases' — must still render."""
        st = _state(source_counts={"statutes": 8, "case_law": 5, "doctrine": 6})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("8 statutes", html)
        self.assertIn("5 cases", html)
        self.assertIn("6 doctrine", html)

    def test_source_counts_alias_case_law_kebab_accepted(self):
        """Regression: agent wrote 'case-law' (kebab, from widget-schemas) instead of 'cases'."""
        st = _state(source_counts={"statutes": 8, "case-law": 5, "doctrine": 6})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("5 cases", html)

    def test_source_counts_mixed_aliases_with_extra_keys(self):
        """The actual prod failure mode: 'statute' + 'case_law' + spurious 'evidence_rows'."""
        st = _state(source_counts={"statute": 8, "case_law": 5, "doctrine": 6, "evidence_rows": 38})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("8 statutes", html)
        self.assertIn("5 cases", html)
        self.assertIn("6 doctrine", html)
        # evidence_rows must NOT appear anywhere — it's not in the schema.
        self.assertNotIn("38", html)
        self.assertNotIn("evidence_rows", html)

    def test_source_counts_string_value_coerced_to_int(self):
        """Agent might write '"statutes": "8"' (stringified int) — accept it."""
        st = _state(source_counts={"statutes": "8", "cases": "5", "doctrine": "6"})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("8 statutes", html)

    def test_source_counts_partial_dict_zero_fills_missing(self):
        """Agent might write only doctrine; statutes/cases default to 0."""
        st = _state(source_counts={"doctrine": 6})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("0 statutes", html)
        self.assertIn("0 cases", html)
        self.assertIn("6 doctrine", html)

    def test_source_counts_empty_dict_renders_all_zeros(self):
        """Empty dict is a dict — render the chip with all zeros (preserves v0.6.0 behavior)."""
        st = _state(source_counts={})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn('class="chip chip-sources"', html)
        self.assertIn("0 statutes", html)
        self.assertIn("0 cases", html)
        self.assertIn("0 doctrine", html)

    def test_source_counts_non_dict_treated_as_null(self):
        """If source_counts is a string / list / int (wrong type), suppress the chip."""
        for bad in ["foo", ["statutes", "cases"], 5, True]:
            with self.subTest(value=bad):
                st = _state(source_counts=bad)
                html = r.render_html(st, current_step="x", now=FROZEN_NOW)
                self.assertNotIn('class="chip chip-sources"', html)

    def test_source_counts_bad_value_types_coerce_to_zero(self):
        """None / bool / non-numeric strings / lists in value positions coerce to 0, no crash."""
        st = _state(source_counts={"statutes": None, "cases": "not-a-number", "doctrine": [1, 2, 3]})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("0 statutes", html)
        self.assertIn("0 cases", html)
        self.assertIn("0 doctrine", html)

    def test_source_counts_negative_coerced_to_zero(self):
        """Negative counts make no sense for a count field; coerce to 0."""
        st = _state(source_counts={"statutes": -5, "cases": 5, "doctrine": 6})
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("0 statutes", html)

    def test_source_counts_alias_emits_stderr_warning(self):
        """Using a non-canonical key must log to stderr so the writer can be fixed."""
        import io
        from contextlib import redirect_stderr
        buf = io.StringIO()
        with redirect_stderr(buf):
            r.normalize_source_counts({"statute": 8, "case_law": 5, "doctrine": 6})
        warnings = buf.getvalue()
        self.assertIn("non-canonical key", warnings)
        self.assertIn("'statute'", warnings)
        self.assertIn("'case_law'", warnings)
        # Canonical 'doctrine' must NOT trigger a warning.
        self.assertNotIn("'doctrine'", warnings)

    def test_source_counts_canonical_keys_do_not_warn(self):
        """Canonical schema must be silent — warnings should only fire on aliases."""
        import io
        from contextlib import redirect_stderr
        buf = io.StringIO()
        with redirect_stderr(buf):
            r.normalize_source_counts({"statutes": 8, "cases": 5, "doctrine": 6})
        self.assertEqual(buf.getvalue(), "")

    def test_active_subagent_chip_rendered_legacy_string(self):
        """Backwards-compat: bare string in `active_subagent` should still render one chip."""
        st = _state(active_subagent="case-law-researcher")
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertEqual(html.count('class="chip chip-subagent"'), 1)
        self.assertIn("case-law-researcher", html)
        self.assertIn("🛠", html)

    def test_active_subagents_list_renders_one_chip_per_element(self):
        """v0.6.2: list-form `active_subagents` renders ONE chip per element."""
        st = _state(active_subagents=["statutory", "case-law", "doctrinal"])
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        # Three separate chips, not a single "3 researchers (parallel)" chip.
        self.assertEqual(html.count('class="chip chip-subagent"'), 3)
        self.assertIn("statutory", html)
        self.assertIn("case-law", html)
        self.assertIn("doctrinal", html)
        # 🛠 emoji appears 3 times (one per chip).
        self.assertEqual(html.count("🛠"), 3)

    def test_active_subagents_single_element_list_renders_one_chip(self):
        st = _state(active_subagents=["memo-writer"])
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertEqual(html.count('class="chip chip-subagent"'), 1)
        self.assertIn("memo-writer", html)

    def test_active_subagent_chip_omitted_when_null(self):
        st = _state(active_subagent=None, active_subagents=None)
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertNotIn('class="chip chip-subagent"', html)
        self.assertNotIn("🛠", html)

    def test_active_subagent_chip_omitted_when_empty_list(self):
        st = _state(active_subagents=[])
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertNotIn('class="chip chip-subagent"', html)

    def test_active_subagent_chip_omitted_in_terminal_phase(self):
        """When the pipeline is done/failed, the active subagent chip(s) should not show."""
        st = _state(current_phase="done", active_subagents=["memo-writer"])
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertNotIn('class="chip chip-subagent"', html)

    def test_topic_replaces_truncated_query_in_header(self):
        """v0.6.2: live_progress.topic, when set, replaces the truncated user_query line."""
        long_query = "We are a US-based SaaS company planning to launch a new feature that uses AI to analyze customer support chat transcripts from EU users and we want to know about GDPR and AI Act compliance"
        st = _state(user_query=long_query, topic="GDPR + AI Act compliance for chat-transcript AI feature")
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        # The topic appears verbatim.
        self.assertIn("GDPR + AI Act compliance for chat-transcript AI feature", html)
        # The truncated query (with "…") does NOT appear since topic took over.
        self.assertNotIn("planning to launch a new feature that uses AI to analyze customer", html)

    def test_topic_omitted_falls_back_to_query_truncation(self):
        """When topic is null/empty, the renderer falls back to truncating user_query."""
        long_query = "A" * 200
        st = _state(user_query=long_query, topic=None)
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("A" * 137, html)
        self.assertIn("…", html)

    def test_topic_empty_string_falls_back_to_query(self):
        st = _state(user_query="some query", topic="")
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn("some query", html)

    def test_iteration_chip_during_revision_loop(self):
        st = _state(current_phase="revision_loop", current_iteration=2, max_iterations=3)
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertIn('class="chip chip-iteration"', html)
        self.assertIn("iteration 2 of 3", html)
        self.assertIn("🔁", html)

    def test_iteration_chip_omitted_outside_revision_loop(self):
        st = _state(current_phase="research", current_iteration=2, max_iterations=3)
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertNotIn('class="chip chip-iteration"', html)

    def test_iteration_chip_omitted_when_counters_zero(self):
        st = _state(current_phase="revision_loop", current_iteration=0, max_iterations=0)
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertNotIn('class="chip chip-iteration"', html)

    def test_chips_row_omitted_when_no_chips(self):
        st = _state(active_subagent=None, source_counts=None, current_phase="research")
        html = r.render_html(st, current_step="x", now=FROZEN_NOW)
        self.assertNotIn('class="chips-row"', html)

    def test_flat_design_no_box_shadow(self):
        """Flat design discipline check — no box-shadow in CSS."""
        html = r.render_html(_state(), current_step="x", now=FROZEN_NOW)
        self.assertNotIn("box-shadow", html)

    def test_flat_design_no_gradient(self):
        """Flat design discipline check — no linear-gradient / radial-gradient in CSS."""
        html = r.render_html(_state(), current_step="x", now=FROZEN_NOW)
        self.assertNotIn("gradient", html.lower())

    def test_hero_step_present(self):
        html = r.render_html(_state(), current_step="Researching statute 3 of 8", now=FROZEN_NOW)
        self.assertIn('class="hero-step"', html)
        self.assertIn("Researching statute 3 of 8", html)

    def test_alive_dot_in_footer(self):
        html_running = r.render_html(_state(current_phase="research"), current_step="x", now=FROZEN_NOW)
        html_done = r.render_html(_state(current_phase="done"), current_step="x", now=FROZEN_NOW)
        self.assertIn('class="alive-dot"', html_running)
        self.assertIn('class="alive-dot"', html_done)
        # CSS rule `.footer.footer-terminal` also contains the string — check element class attr.
        self.assertIn('class="footer footer-terminal"', html_done)
        self.assertIn('class="footer "', html_running)


class TestAtomicWrite(unittest.TestCase):
    def test_main_writes_html_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            output_path = tmp_path / "live-progress.html"
            state_path.write_text(json.dumps(_state()), encoding="utf-8")

            rc = r.main([
                "--state-json", str(state_path),
                "--current-step", "Test step",
                "--output", str(output_path),
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(output_path.exists())
            tmp_file = output_path.with_suffix(output_path.suffix + ".tmp")
            self.assertFalse(tmp_file.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("Test step", content)
            self.assertIn('<meta charset="UTF-8">', content)

    def test_main_creates_output_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            output_path = tmp_path / "sub" / "nested" / "live-progress.html"
            state_path.write_text(json.dumps(_state()), encoding="utf-8")

            rc = r.main([
                "--state-json", str(state_path),
                "--current-step", "x",
                "--output", str(output_path),
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(output_path.exists())

    def test_main_fails_cleanly_when_state_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "live-progress.html"
            rc = r.main([
                "--state-json", str(tmp_path / "does-not-exist.json"),
                "--current-step", "x",
                "--output", str(output_path),
            ])
            self.assertEqual(rc, 1)
            self.assertFalse(output_path.exists())

    def test_main_fails_cleanly_when_state_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            state_path.write_text("{not valid json", encoding="utf-8")
            output_path = tmp_path / "live-progress.html"
            rc = r.main([
                "--state-json", str(state_path),
                "--current-step", "x",
                "--output", str(output_path),
            ])
            self.assertEqual(rc, 2)
            self.assertFalse(output_path.exists())

    def test_concurrent_writes_do_not_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            output_path = tmp_path / "live-progress.html"
            state_path.write_text(json.dumps(_state()), encoding="utf-8")

            for i in range(5):
                rc = r.main([
                    "--state-json", str(state_path),
                    "--current-step", f"step {i}",
                    "--output", str(output_path),
                ])
                self.assertEqual(rc, 0)
                content = output_path.read_text(encoding="utf-8")
                self.assertIn(f"step {i}", content)
                self.assertIn('<meta charset="UTF-8">', content)


if __name__ == "__main__":
    unittest.main()
