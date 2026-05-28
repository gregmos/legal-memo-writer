#!/usr/bin/env python3
"""Render the live-progress dashboard HTML for the memoforge plugin.

Reads state.json + a current-step text + the current ISO timestamp, then
writes an HTML file that mcp__cowork__create_artifact / update_artifact
pins to the sidebar "Live artifacts" card. The HTML is regenerated fresh
on every call — there is no incremental update logic; the renderer is
idempotent and stateless.

Called by:
  - skills/memo/SKILL.md Step 1 sub-step 1d (initial mint of the master artifact)
  - skills/memo/SKILL.md at phase boundaries (orchestrator-side updates)
  - heavy subagents at internal step boundaries (memo-writer per-section,
    researchers per-issue, reviewers start/done, mediator per-reviewer, etc.)

Usage:
  python3 scripts/render_live_progress.py \
    --state-json <absolute path to state.json> \
    --current-step "<short string describing what's happening NOW>" \
    --output <absolute path to write the HTML>

Optional:
  --extra-detail "<text>"   — small secondary line under the current step
                              (e.g. "iteration 2 of 3" during revision)
  --status-tag "<text>"     — small colored chip next to the phase label
                              (e.g. "blocking-fixed", "rate-limited fallback")

Atomic write contract: writes to <output>.tmp first, then renames to
<output>. The mcp__cowork__update_artifact tool can read the destination
file even under concurrent subagent updates without seeing a torn write.

HTML contract:
  - Every produced file includes <meta charset="UTF-8"> in <head>.
    Cowork's artifact iframe does not auto-detect UTF-8 — em-dashes /
    curly quotes / Cyrillic render as mojibake without this.
  - Inline JavaScript block ≤30 lines for real-time tickers (setInterval
    on elapsed seconds; reads data-* attributes; no fetch, no postMessage,
    no harness callback). If the Cowork iframe sandbox blocks <script>,
    the dashboard still works — tickers just go static between renders.
  - Flat design: no box-shadow, no gradients, soft borders only at
    section breaks. Hero current-step block is the visual headline.

Tested at scripts/tests/test_render_live_progress.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import sys
from pathlib import Path
from typing import Any

# Canonical 14-box phase enumeration. Order MATCHES ACTUAL EXECUTION
# (v0.6.1+) — Intake comes before Mode because the orchestrator runs intake
# elicitation first (gathering facts) and only after the user answers does
# it pick the memo mode (Brief / Full). Earlier versions inherited a
# v0.0.x ordering where Mode-pick was planned before intake; that ordering
# never matched runtime behavior and the legacy "1.5" / "2a" IDs only
# confused the user. State-schema current_phase values map onto these
# boxes via the state_phases lists — those state-phase strings are
# unchanged (they are the canonical enum); only the display id, display
# label, and PHASES position changed.
PHASES: list[dict[str, Any]] = [
    {"id": "1",    "label": "Init",         "group": "Setup",              "state_phases": ["intake_preliminary_research"]},
    {"id": "2",    "label": "Intake",       "group": "Intake",             "state_phases": ["intake_questions_pending"]},
    {"id": "3",    "label": "Mode",         "group": "Setup",              "state_phases": ["mode_pick_pending"]},
    {"id": "4",    "label": "Plan",         "group": "Plan",               "state_phases": ["planning"]},
    {"id": "5",    "label": "Approve",      "group": "Plan",               "state_phases": ["plan_approval_pending"]},
    {"id": "6",    "label": "Research",     "group": "Research",           "state_phases": ["research"]},
    {"id": "7",    "label": "Sufficiency",  "group": "Research",           "state_phases": ["research_sufficiency", "research_sufficiency_followup_pending", "currency_check"]},
    {"id": "8",    "label": "Source-pack",  "group": "Research",           "state_phases": ["source_pack", "source_review_pending"]},
    {"id": "9",    "label": "Draft v1",     "group": "Drafting+Revision",  "state_phases": ["drafting"]},
    {"id": "10",   "label": "Revise",       "group": "Drafting+Revision",  "state_phases": ["revision_loop"]},
    {"id": "11",   "label": "Polish",       "group": "Delivery",           "state_phases": ["client_readiness"]},
    {"id": "12",   "label": "Export",       "group": "Delivery",           "state_phases": ["export"]},
    {"id": "13",   "label": "Summary",      "group": "Delivery",           "state_phases": ["done", "failed", "cancelled_by_user"]},
]

TERMINAL_PHASES = {"done", "failed", "cancelled_by_user"}
REVISION_LOOP_PHASES = {"revision_loop"}

# Canonical schema for state.live_progress.source_counts is
# {"statutes", "cases", "doctrine"} per state-schema.md and
# source-pack-builder.md §"State.json source_counts". Past production runs
# have occasionally produced non-canonical keys at the writer side because
# nearby schemas in the codebase use different conventions:
#   - widget-schemas.md §"Phase 12 final dashboard" `source_breakdown` uses
#     singular kebab: {"statute", "case-law", "doctrine", "soft-law"};
#   - research/raw/case-law/_index.json `layer` field uses snake: "case_law";
#   - currency-checker.md schema mixes plural "statutes" with snake "case_law".
# The renderer accepts the small alias set below so a single LLM keying
# mistake does not silently zero out the 📊 chip. When an alias fires we
# emit a stderr warning so the responsible writer can be tightened — the
# canonical schema is still the contract; the aliases are belt-and-suspenders.
_SOURCE_COUNT_ALIASES: dict[str, tuple[str, ...]] = {
    "statutes": ("statutes", "statute"),
    "cases": ("cases", "case_law", "case-law"),
    "doctrine": ("doctrine",),
}


def _coerce_count(v: Any) -> int:
    """Best-effort coercion of a count value to a non-negative int. None / bad
    types / non-numeric strings fall through to 0 rather than crashing the
    render. Booleans are intentionally rejected (int(True) == 1 would be a
    confusing render value for a count field)."""
    if v is None or isinstance(v, bool):
        return 0
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    return n if n >= 0 else 0


def normalize_source_counts(raw: Any) -> dict[str, int] | None:
    """Read state.live_progress.source_counts tolerantly.

    Returns a dict with the three canonical keys (all ints) when the input is
    a dict — even an empty or partial one. Returns None when the input is not
    a dict, preserving the existing "no chip" behavior for null / unset
    source_counts.

    Accepts the canonical key plus a small alias set (see _SOURCE_COUNT_ALIASES
    above) and logs a stderr warning when an alias is used. Extra unknown keys
    in the input are silently ignored.
    """
    if not isinstance(raw, dict):
        return None
    normalized: dict[str, int] = {}
    for canon, aliases in _SOURCE_COUNT_ALIASES.items():
        chosen_key: str | None = None
        for k in aliases:
            if k in raw:
                chosen_key = k
                break
        if chosen_key is None:
            normalized[canon] = 0
            continue
        if chosen_key != canon:
            sys.stderr.write(
                f"render_live_progress: source_counts has non-canonical key "
                f"{chosen_key!r} (expected {canon!r}); accepting via alias. "
                f"Fix the writer (see agents/source-pack-builder.md §State.json "
                f"source_counts) — alias fallbacks may be removed in a future "
                f"release.\n"
            )
        normalized[canon] = _coerce_count(raw[chosen_key])
    return normalized


def find_phase_index(current_phase: str) -> int | None:
    """Map a state.json current_phase string to a PHASES index (0..12)."""
    for i, p in enumerate(PHASES):
        if current_phase in p["state_phases"]:
            return i
    return None


def parse_iso(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def format_elapsed(seconds: float) -> str:
    """1m 24s, 12s, 1h 5m, 3d 4h."""
    if seconds < 0:
        seconds = 0
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        if secs == 0:
            return f"{minutes}m"
        return f"{minutes}m {secs:02d}s"
    hours = minutes // 60
    mins = minutes % 60
    if hours < 24:
        if mins == 0:
            return f"{hours}h"
        return f"{hours}h {mins:02d}m"
    days = hours // 24
    hrs = hours % 24
    return f"{days}d {hrs:02d}h"


def render_html(
    state: dict[str, Any],
    current_step: str,
    extra_detail: str | None = None,
    status_tag: str | None = None,
    now: dt.datetime | None = None,
) -> str:
    """Pure render — no I/O. The atomic-write wrapper is in main()."""
    now = now or dt.datetime.now(dt.timezone.utc)

    task_id = str(state.get("task_id", "(unknown)"))
    user_query = str(state.get("user_query", "") or "")
    current_phase = str(state.get("current_phase", "") or "")
    mode = str(state.get("mode", "") or "")
    config = state.get("config", {}) or {}
    current_iteration = state.get("current_iteration") or 0
    max_iterations = config.get("max_iterations") or 0

    lp = state.get("live_progress", {}) or {}
    started_at_iso_raw = lp.get("started_at_iso") or ""
    phase_started_iso_raw = lp.get("phase_started_at_iso") or ""
    started_at = parse_iso(started_at_iso_raw)
    phase_started = parse_iso(phase_started_iso_raw)
    timeline = lp.get("timeline", []) or []
    topic = (lp.get("topic") or "").strip()
    source_counts = normalize_source_counts(lp.get("source_counts"))

    # active_subagents: list[str] (v0.6.2). Backwards-compat: accept bare
    # string (v0.6.0–v0.6.1) and wrap it into a single-element list.
    raw_active = lp.get("active_subagents")
    if raw_active is None:
        raw_active = lp.get("active_subagent")  # legacy field name
    if raw_active is None:
        active_subagents: list[str] = []
    elif isinstance(raw_active, str):
        active_subagents = [raw_active] if raw_active.strip() else []
    elif isinstance(raw_active, list):
        active_subagents = [str(x).strip() for x in raw_active if str(x).strip()]
    else:
        active_subagents = []

    current_idx = find_phase_index(current_phase)
    is_terminal = current_phase in TERMINAL_PHASES
    in_revision_loop = current_phase in REVISION_LOOP_PHASES

    elapsed_total = (now - started_at).total_seconds() if started_at else 0
    elapsed_phase = (now - phase_started).total_seconds() if phase_started else 0

    now_iso = now.isoformat(timespec="seconds")

    # Build phase pills
    phase_pills_html = []
    for i, p in enumerate(PHASES):
        if current_idx is None:
            status = "future"
        elif is_terminal and i <= current_idx:
            status = "completed"
        elif i < current_idx:
            status = "completed"
        elif i == current_idx:
            status = "current"
        else:
            status = "future"
        cls = f"pill pill-{status}"
        phase_pills_html.append(
            f'<div class="{cls}" title="{html.escape(p["id"] + " · " + p["label"])}">'
            f'<span class="pill-id">{html.escape(p["id"])}</span>'
            f'<span class="pill-label">{html.escape(p["label"])}</span>'
            f"</div>"
        )

    current_label = PHASES[current_idx]["label"] if current_idx is not None else "—"
    current_group = PHASES[current_idx]["group"] if current_idx is not None else "—"
    current_phase_id = PHASES[current_idx]["id"] if current_idx is not None else "—"
    completed_count = current_idx if (current_idx is not None) else 0
    if is_terminal and current_idx is not None:
        completed_count = current_idx + 1
    total_phases = len(PHASES)

    # Build chips row — only show chips that have data.
    chips_html_parts: list[str] = []

    # Source-counts chip (only when state.live_progress.source_counts populated, typically post-Phase-7).
    # source_counts is already normalized (canonical keys, int values) by normalize_source_counts() above.
    if source_counts is not None:
        statutes_n = source_counts["statutes"]
        cases_n = source_counts["cases"]
        doctrine_n = source_counts["doctrine"]
        chips_html_parts.append(
            f'<div class="chip chip-sources" title="Source counts from research files">'
            f'<span class="chip-icon" aria-hidden="true">📊</span>'
            f'<span class="chip-text">{statutes_n} statutes · {cases_n} cases · {doctrine_n} doctrine</span>'
            f"</div>"
        )

    # Active-subagent chips (one chip per element of active_subagents list;
    # parallel dispatches show multiple chips side-by-side). Suppressed when
    # the pipeline is terminal.
    if active_subagents and not is_terminal:
        for name in active_subagents:
            chips_html_parts.append(
                f'<div class="chip chip-subagent" title="Subagent currently running">'
                f'<span class="chip-icon" aria-hidden="true">🛠</span>'
                f'<span class="chip-text">{html.escape(name)}</span>'
                f"</div>"
            )

    # Iteration chip (only during revision loop)
    if in_revision_loop and current_iteration and max_iterations:
        chips_html_parts.append(
            f'<div class="chip chip-iteration" title="Revision loop iteration counter">'
            f'<span class="chip-icon" aria-hidden="true">🔁</span>'
            f'<span class="chip-text">iteration {int(current_iteration)} of {int(max_iterations)}</span>'
            f"</div>"
        )

    chips_html = (
        f'<div class="chips-row">{"".join(chips_html_parts)}</div>'
        if chips_html_parts else ""
    )

    # Timeline rows
    timeline_rows_html = []
    for entry in timeline:
        if not isinstance(entry, dict):
            continue
        phase_key = entry.get("phase", "")
        idx = find_phase_index(phase_key)
        if idx is None:
            continue
        st = parse_iso(entry.get("started_at_iso"))
        en = parse_iso(entry.get("completed_at_iso"))
        if st is None:
            continue
        if en is None:
            duration_s = (now - st).total_seconds()
            duration_text = f"{format_elapsed(duration_s)} (running)"
            row_class = "tl-row tl-row-running"
        else:
            duration_s = (en - st).total_seconds()
            duration_text = format_elapsed(duration_s)
            row_class = "tl-row tl-row-done"
        timeline_rows_html.append(
            f'<div class="{row_class}">'
            f'<span class="tl-phase">{html.escape(PHASES[idx]["label"])}</span>'
            f'<span class="tl-duration">{html.escape(duration_text)}</span>'
            f"</div>"
        )

    if not timeline_rows_html:
        timeline_rows_html.append('<div class="tl-empty">No phases completed yet — pipeline just started.</div>')

    # Status tag chip in hero (small)
    status_tag_html = ""
    if status_tag:
        status_tag_html = f'<span class="status-tag">{html.escape(status_tag)}</span>'

    extra_detail_html = ""
    if extra_detail:
        extra_detail_html = f'<div class="extra-detail">{html.escape(extra_detail)}</div>'

    # Dashboard header line: prefer `live_progress.topic` (clean 3-7 word theme
    # generated by orchestrator at Step 1d), fall back to truncated user_query
    # when topic is null/empty.
    if topic:
        header_line = topic
    else:
        header_line = user_query.strip().replace("\n", " ")
        if len(header_line) > 140:
            header_line = header_line[:137] + "…"

    mode_chip_html = ""
    if mode:
        mode_chip_html = f'<span class="mode-chip mode-{html.escape(mode)}">{html.escape(mode.upper())}</span>'

    # JS data-attributes for tickers
    started_attr = html.escape(started_at_iso_raw)
    phase_started_attr = html.escape(phase_started_iso_raw)
    render_iso_attr = html.escape(now_iso)

    # Compose
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Live progress — {html.escape(task_id)}</title>
<style>
  :root {{
    --bg: #ffffff;
    --fg: #0f172a;
    --muted: #64748b;
    --subtle: #94a3b8;
    --accent: #2563eb;
    --accent-soft: #eff6ff;
    --accent-border: #bfdbfe;
    --completed: #16a34a;
    --completed-soft: #f0fdf4;
    --completed-border: #bbf7d0;
    --future: #f1f5f9;
    --future-fg: #94a3b8;
    --border: #e2e8f0;
    --border-soft: #f1f5f9;
    --terminal: #475569;
    --warn: #d97706;
    --warn-soft: #fffbeb;
    --warn-border: #fde68a;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0b1020;
      --fg: #e2e8f0;
      --muted: #94a3b8;
      --subtle: #64748b;
      --accent: #60a5fa;
      --accent-soft: #172554;
      --accent-border: #1e40af;
      --completed: #4ade80;
      --completed-soft: #052e1a;
      --completed-border: #14532d;
      --future: #1e293b;
      --future-fg: #64748b;
      --border: #1e293b;
      --border-soft: #1a2333;
      --terminal: #94a3b8;
      --warn: #fbbf24;
      --warn-soft: #1f1503;
      --warn-border: #422006;
    }}
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    padding: 0;
    background: var(--bg);
    color: var(--fg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", sans-serif;
    font-size: 14px;
    line-height: 1.45;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }}
  body {{
    padding: 1.25rem 1.5rem;
    max-width: 780px;
    margin: 0 auto;
  }}
  /* Top meta strip */
  .meta-row {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }}
  .meta-row .spacer {{ flex: 1; }}
  .mode-chip {{
    font-size: 10px;
    font-weight: 700;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    letter-spacing: 0.05em;
    border: 1px solid var(--accent-border);
  }}
  .task-id {{
    font-size: 10px;
    color: var(--subtle);
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    word-break: break-all;
    margin-bottom: 0.5rem;
    text-transform: none;
    letter-spacing: 0;
    font-weight: 400;
  }}
  .query-line {{
    font-size: 13px;
    color: var(--muted);
    margin-bottom: 1rem;
    font-style: italic;
    line-height: 1.4;
  }}
  /* HERO current-step block — flat-design headline */
  .hero {{
    border: 1px solid var(--accent-border);
    background: var(--accent-soft);
    border-left-width: 3px;
    padding: 1rem 1.2rem;
    border-radius: 6px;
    margin-bottom: 1rem;
  }}
  .hero.hero-terminal {{
    background: transparent;
    border-color: var(--border);
    border-left-color: var(--terminal);
    color: var(--terminal);
  }}
  .hero-eyebrow {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-bottom: 0.4rem;
  }}
  .hero-eyebrow .pulse-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
    animation: hero-pulse 1.8s ease-in-out infinite;
  }}
  .hero.hero-terminal .pulse-dot {{ animation: none; opacity: 0.4; }}
  @keyframes hero-pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50%      {{ opacity: 0.35; transform: scale(0.75); }}
  }}
  .hero-step {{
    font-size: 19px;
    font-weight: 600;
    line-height: 1.3;
    color: var(--fg);
    margin-bottom: 0.3rem;
  }}
  .hero-meta {{
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.4rem 1rem;
    color: var(--muted);
    font-size: 12px;
  }}
  .hero-meta .label {{ color: var(--subtle); }}
  .hero-meta .value {{ color: var(--muted); font-family: ui-monospace, "SF Mono", Menlo, monospace; font-weight: 500; }}
  .extra-detail {{
    font-size: 12px;
    color: var(--muted);
    margin-top: 0.4rem;
  }}
  .status-tag {{
    background: var(--warn-soft);
    color: var(--warn);
    border: 1px solid var(--warn-border);
    padding: 0.12rem 0.4rem;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    text-transform: none;
    letter-spacing: 0;
  }}
  /* Phase pills (compact secondary row) */
  .pills {{
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    margin-bottom: 0.85rem;
  }}
  .pill {{
    flex: 1 1 50px;
    min-width: 48px;
    padding: 0.3rem 0.25rem;
    border-radius: 4px;
    border: 1px solid var(--border);
    text-align: center;
    background: var(--bg);
    transition: background 0.2s ease, border-color 0.2s ease;
  }}
  .pill-id {{
    display: block;
    font-size: 9px;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    opacity: 0.65;
    line-height: 1;
    margin-bottom: 2px;
  }}
  .pill-label {{
    display: block;
    font-size: 10px;
    font-weight: 500;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }}
  .pill-completed {{
    background: var(--completed-soft);
    border-color: var(--completed-border);
    color: var(--completed);
  }}
  .pill-current {{
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
    font-weight: 700;
  }}
  .pill-future {{
    background: var(--future);
    border-color: var(--border);
    color: var(--future-fg);
  }}
  /* Phase summary line */
  .phase-summary {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 1rem;
  }}
  .phase-summary .left {{ font-weight: 500; }}
  .phase-summary .right {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; }}
  /* Chips row */
  .chips-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 1rem;
  }}
  .chip {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.3rem 0.6rem;
    border-radius: 999px;
    background: var(--bg);
    border: 1px solid var(--border);
    font-size: 12px;
    color: var(--fg);
    line-height: 1;
  }}
  .chip-icon {{
    font-size: 13px;
    line-height: 1;
  }}
  .chip-text {{
    font-weight: 500;
  }}
  .chip-sources {{ background: var(--completed-soft); border-color: var(--completed-border); color: var(--completed); }}
  .chip-subagent {{ background: var(--accent-soft); border-color: var(--accent-border); color: var(--accent); }}
  .chip-iteration {{ background: var(--warn-soft); border-color: var(--warn-border); color: var(--warn); }}
  /* Timeline */
  .timeline-block {{
    border-top: 1px solid var(--border-soft);
    padding-top: 0.85rem;
    margin-bottom: 0.85rem;
  }}
  .timeline-header {{
    font-size: 10px;
    color: var(--subtle);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.5rem;
    font-weight: 600;
  }}
  .tl-row {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 12px;
    padding: 0.2rem 0;
  }}
  .tl-row + .tl-row {{ border-top: 1px dashed var(--border-soft); }}
  .tl-row-done .tl-phase {{ color: var(--muted); }}
  .tl-row-done .tl-duration {{ color: var(--subtle); font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; }}
  .tl-row-running .tl-phase {{ color: var(--accent); font-weight: 600; }}
  .tl-row-running .tl-duration {{ color: var(--accent); font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; font-weight: 500; }}
  .tl-empty {{
    font-size: 12px;
    color: var(--subtle);
    font-style: italic;
    padding: 0.2rem 0;
  }}
  /* Footer */
  .footer {{
    border-top: 1px solid var(--border-soft);
    padding-top: 0.5rem;
    margin-top: 0.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 10px;
    color: var(--subtle);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}
  .footer-alive {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }}
  .footer-alive .alive-dot {{
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--completed);
    animation: alive-pulse 2.4s ease-in-out infinite;
  }}
  .footer.footer-terminal .alive-dot {{ background: var(--subtle); animation: none; }}
  @keyframes alive-pulse {{
    0%, 100% {{ opacity: 1; }}
    50%      {{ opacity: 0.25; }}
  }}
</style>
</head>
<body>
  <div class="meta-row">
    <span>Legal Memo Writer · Live</span>
    <span class="spacer"></span>
    {mode_chip_html}
  </div>
  <div class="task-id">{html.escape(task_id)}</div>
  {('<div class="query-line">' + html.escape(header_line) + '</div>') if header_line else ''}

  <div class="hero {'hero-terminal' if is_terminal else ''}">
    <div class="hero-eyebrow">
      <span class="pulse-dot" aria-hidden="true"></span>
      <span>Phase {html.escape(current_phase_id)} · {html.escape(current_label)} · {html.escape(current_group)}</span>
      {status_tag_html}
    </div>
    <div class="hero-step">{html.escape(current_step) if current_step else "—"}</div>
    {extra_detail_html}
    <div class="hero-meta">
      <span><span class="label">in phase</span> <span class="value" data-phase-started-at-iso="{phase_started_attr}" data-elapsed-tick="phase">{html.escape(format_elapsed(elapsed_phase))}</span></span>
      <span><span class="label">total</span> <span class="value" data-started-at-iso="{started_attr}" data-elapsed-tick="total">{html.escape(format_elapsed(elapsed_total))}</span></span>
    </div>
  </div>

  <div class="pills">
    {''.join(phase_pills_html)}
  </div>
  <div class="phase-summary">
    <span class="left">{completed_count} of {total_phases} phases complete</span>
    <span class="right">{html.escape(current_group)}</span>
  </div>

  {chips_html}

  <div class="timeline-block">
    <div class="timeline-header">Phase timeline</div>
    {''.join(timeline_rows_html)}
  </div>

  <div class="footer {'footer-terminal' if is_terminal else ''}">
    <span class="footer-alive">
      <span class="alive-dot" aria-hidden="true"></span>
      <span>{'pipeline complete' if is_terminal else 'pipeline alive'}</span>
    </span>
    <span data-render-iso="{render_iso_attr}" data-elapsed-tick="since-update">Updated {html.escape(now_iso)}</span>
  </div>

<script>
/* v0.6.0 inline JS — self-contained tickers. No fetch, no postMessage, no
   harness callback. Pure DOM mutation reading data-* attributes set by
   render_live_progress.py. If the Cowork iframe sandbox blocks <script>,
   the dashboard still works — tickers just stay frozen between renders. */
(function() {{
  function parseIso(s) {{
    if (!s) return null;
    try {{ var d = new Date(s); return isNaN(d.getTime()) ? null : d; }}
    catch (e) {{ return null; }}
  }}
  function fmtElapsed(secs) {{
    if (secs < 0) secs = 0;
    secs = Math.floor(secs);
    if (secs < 60) return secs + "s";
    var m = Math.floor(secs / 60), s = secs % 60;
    if (m < 60) return s === 0 ? (m + "m") : (m + "m " + (s < 10 ? "0" : "") + s + "s");
    var h = Math.floor(m / 60), mm = m % 60;
    if (h < 24) return mm === 0 ? (h + "h") : (h + "h " + (mm < 10 ? "0" : "") + mm + "m");
    var d = Math.floor(h / 24), hh = h % 24;
    return d + "d " + (hh < 10 ? "0" : "") + hh + "h";
  }}
  function fmtSince(secs) {{
    if (secs < 0) secs = 0;
    secs = Math.floor(secs);
    if (secs < 5) return "Updated just now";
    if (secs < 60) return "Updated " + secs + "s ago";
    var m = Math.floor(secs / 60);
    if (m < 60) return "Updated " + m + "m ago";
    var h = Math.floor(m / 60);
    return "Updated " + h + "h ago";
  }}
  function tick() {{
    var now = Date.now();
    var nodes = document.querySelectorAll("[data-elapsed-tick]");
    for (var i = 0; i < nodes.length; i++) {{
      var node = nodes[i];
      var kind = node.getAttribute("data-elapsed-tick");
      var attrName = kind === "phase" ? "data-phase-started-at-iso"
                   : kind === "total" ? "data-started-at-iso"
                   : kind === "since-update" ? "data-render-iso" : null;
      if (!attrName) continue;
      var iso = node.getAttribute(attrName);
      var t = parseIso(iso);
      if (!t) continue;
      var secs = (now - t.getTime()) / 1000;
      node.textContent = (kind === "since-update") ? fmtSince(secs) : fmtElapsed(secs);
    }}
  }}
  try {{ tick(); setInterval(tick, 1000); }} catch (e) {{ /* sandbox blocked — leave static values */ }}
}})();
</script>
</body>
</html>
"""
    return html_out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render live-progress dashboard HTML from state.json + a current-step string."
    )
    parser.add_argument("--state-json", required=True, help="Absolute path to state.json")
    parser.add_argument("--current-step", default="", help="Short description of what's happening NOW")
    parser.add_argument("--extra-detail", default=None, help="Optional secondary line under current-step")
    parser.add_argument("--status-tag", default=None, help="Optional colored chip next to phase label")
    parser.add_argument("--output", required=True, help="Absolute path to write HTML output")
    args = parser.parse_args(argv)

    state_path = Path(args.state_json)
    if not state_path.is_file():
        print(f"state.json not found: {state_path}", file=sys.stderr)
        return 1
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"state.json is malformed: {e}", file=sys.stderr)
        return 2

    rendered = render_html(
        state,
        current_step=args.current_step or "",
        extra_detail=args.extra_detail,
        status_tag=args.status_tag,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(rendered, encoding="utf-8")
    os.replace(tmp_path, output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
