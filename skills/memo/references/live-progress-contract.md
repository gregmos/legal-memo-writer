# Live-progress contract — subagent-side artifact streaming

Canonical specification for the `mcp__cowork__create_artifact` + `mcp__cowork__update_artifact` based "Live artifacts" sidebar dashboard introduced in v0.5.0. Every subagent that emits progress updates references this document.

## Why this exists

Before v0.5.0, the orchestrator's text and tool-indicator strips between subagent dispatches buffered to end-of-turn — the user saw 5–40 minutes of chat silence during Phase 5→Phase 12 even when many subagents had completed work. v0.2.0 tried orchestrator-side `update_artifact` calls to bypass the buffer; that failed (postmortem `docs/postmortems/v0.2.0-live-progress.md` §5).

v0.5.0 resolves postmortem §9 with a different placement: **`update_artifact` calls made from INSIDE a dispatched subagent flush their tool-indicator strips AND refresh the sidebar artifact card in REAL TIME** in the parent orchestrator's chat scroll. Confirmed empirically on 2026-05-25 via `memoforge-0.5.0-probe.zip` E2E. User-visible result: every heavy subagent (memo-writer, researchers, reviewers, mediator, client-readiness) emits its own progress updates as it works, and the user sees them live in the chat surface.

## How the channel works

1. **Phase 1 step 3.5** (orchestrator) — `mcp__cowork__create_artifact` mints ONE master artifact with id `memo-<task_id>-live` and html_path `<work_dir>/live-progress.html`. State.json captures both. See `skills/memo/SKILL.md` §"Live-progress precheck and master-artifact mint (step 3.5)".

2. **Phase boundaries** (orchestrator) — at every `current_phase` change, the orchestrator updates `state.json.live_progress.timeline` and `live_progress.phase_started_at_iso`, then re-renders + calls `update_artifact`. **Orchestrator-side update_artifact calls buffer to end-of-turn** — that is acceptable, the chat-scroll signal is provided by the subagents' own calls during the next phase, not by the orchestrator's phase-transition update.

3. **Subagent internal steps** (subagent) — heavy subagents call `update_artifact` at their own internal step boundaries (per-issue, per-MCP-query, per-reviewer-section, etc.). These calls **stream live** to the parent's chat scroll. The user sees the sidebar card refresh and a small "Updated artifact" indicator strip in chat per step.

4. **Terminal phases** (orchestrator) — at `done` / `failed` / `cancelled_by_user`, orchestrator does a final `update_artifact` with `--status-tag` set appropriately ("delivered", "failed", "cancelled"). The dashboard's CSS pulse stops in terminal state.

## HARD RULE — `<work_dir>/live-progress.html` is owned by `render_live_progress.py` (v0.7.1+)

**The renderer at `scripts/render_live_progress.py` is the ONLY writer of `<work_dir>/live-progress.html`.** No other code path — orchestrator, subagent, hook, helper script — may write to this file.

Specifically, the orchestrator and every subagent MUST NOT:

- Use the `Write` tool to overwrite `live-progress.html` with custom HTML constructed inline (in an agent message body or a Bash heredoc).
- Use the `Edit` tool to mutate sections of `live-progress.html`.
- Use a `Bash` cat / printf / echo / tee / heredoc / `python3 -c` to emit HTML directly into `live-progress.html`.
- Call `mcp__cowork__update_artifact` with an `html_path` pointing at a file that was NOT produced by `render_live_progress.py` on this same render call.

The ONLY supported way to refresh the dashboard is the three-step sequence (referenced from "How the channel works" §2 above):

1. **Update `state.json.live_progress.*` fields** (timeline, active_subagents, source_counts, topic, phase_started_at_iso, etc.) via atomic Edit per `state-schema.md`.
2. **Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_live_progress.py" --state-json ... --current-step "..." --output <html_path>`** (this is the only tool that may write to `<html_path>`; it atomically writes `.tmp` then renames).
3. **Call `mcp__cowork__update_artifact(id=<artifact_id>, html_path=<html_path>, update_summary=...)`** so Cowork re-reads the refreshed file.

### Why this rule exists

Production runs on v0.6.x–v0.7.0 showed orchestrators occasionally constructing custom HTML inline — typically after a heavy subagent returned (e.g. `case-law-researcher` with a rich `final_response_summary`) the orchestrator built a research-phase-specific dashboard with `DONE`/`RUNNING` badges per researcher and per-step citations, wrote it to `live-progress.html`, then called `update_artifact`. Visually the result was sometimes nicer than the standard renderer output, BUT:

- **Non-deterministic.** Re-running the same task with identical inputs produces a different dashboard depending on whether the orchestrator improvises.
- **Not data-driven.** The custom HTML embeds research findings literally (case citations, gap text) that aren't in `state.json`. The renderer cannot reproduce them on the next render call, so as soon as the next subagent or phase transition fires `render_live_progress.py` via the canonical flow, the rich view disappears — the user sees the dashboard "flicker" between rich-custom and standard-renderer views in the same run.
- **Bypasses tests.** `scripts/tests/test_render_live_progress.py` covers the renderer's invariants (flat design, UTF-8 meta, JS ticker block, chip-rendering rules, phase-pill coverage). Inline HTML bypasses every one.
- **Bypasses schema.** The renderer reads ONLY documented `state.json.live_progress.*` fields (see `state-schema.md`). Inline HTML reads from agent return summaries / orchestrator scratch which have no schema contract — there is no audit trail for "what data the dashboard showed at moment X".
- **Bypasses backward-compat.** v0.6.2 added the `active_subagents` LIST migration with a backward-compat path for the legacy `active_subagent` STRING. Inline HTML doesn't go through the renderer's compat logic — so a legacy task that resumes on a newer plugin gets weird rendering whenever an orchestrator improvises.

### What to do INSTEAD when the standard dashboard feels insufficient

- **Want a different visual?** Edit `scripts/render_live_progress.py` + `scripts/tests/test_render_live_progress.py`. Bump plugin version. Ship. The renderer is small (~780 lines) and self-contained; visual changes land in one file plus tests.
- **Want more data on the dashboard?** Add a new field under `state.json.live_progress` documented in `state-schema.md`, populate it from the appropriate writer (orchestrator at a phase boundary, or a specific subagent on its done emission), then extend the renderer to surface it. The v0.6.0 `source_counts` (written by `source-pack-builder`) and v0.6.2 `topic` (written by orchestrator at Step 1d) additions are the canonical examples — both took fewer than 100 LoC across the three files.
- **Want a one-off rich view at a specific moment?** Use `mcp__cowork__create_artifact` to mint a SEPARATE artifact with a different id (e.g. `memo-<task_id>-research-summary` or `memo-<task_id>-mediator-iter2`). Do NOT touch the master `memo-<task_id>-live` artifact's `html_path` — that file remains the renderer's exclusive domain. The plugin hook auto-approves `mcp__cowork__create_artifact` for any id, so a one-off side-car artifact is permitted; the user sees both artifacts in the sidebar. Document the side-car artifact's purpose in the agent prompt that creates it.

### Enforcement posture

This rule is instruction-following discipline, not a runtime check (the filesystem permits any write). The contract relies on three reinforcement layers:

1. **HARD RULE block in this contract document** (the canonical reference every agent file points to).
2. **STOP-block reminders at the two SKILL.md render call sites**: Step 1d-3 (initial mint render) and the downstream-responsibility block (phase-transition re-render). These are the two places where the orchestrator is most tempted to improvise; the reminders sit immediately above the canonical render invocation.
3. **Future hardening (v0.7.2+ candidate, NOT yet implemented):** `render_live_progress.py` can check the existing `live-progress.html`'s mtime against the renderer's last-written timestamp. If the existing file is newer than the renderer's last write, log a `live_progress_html_overwrite_detected` event to `events.jsonl`. Non-blocking observation (the renderer still proceeds with its atomic write), but the audit trail catches improvisation post-hoc.

## Files and tools

| File / Tool | Purpose |
|---|---|
| `scripts/render_live_progress.py` | The canonical HTML renderer. Reads `state.json` + `--current-step` text, writes atomic HTML output. Called by orchestrator AND by every instrumented subagent. Tested at `scripts/tests/test_render_live_progress.py` (32 tests). |
| `<work_dir>/live-progress.html` | The artifact's backing HTML file. Overwritten on every render (atomic .tmp + rename). |
| `mcp__cowork__create_artifact` | Called ONCE at Phase 1 step 3.5 (by orchestrator). First-write-wins; resumed tasks may catch a collision — fall back to `update_artifact` instead. |
| `mcp__cowork__update_artifact` | Called many times — at every phase transition (orchestrator) and at every internal step boundary (subagent). |

## Subagent skip rule

**Every instrumented subagent MUST read `state.json.config.live_progress_enabled` before attempting any `update_artifact` call.** If false (precheck failed, or running outside Cowork), the subagent SKIPS all live-progress emissions silently — no error, no log spam. The subagent's substantive work (drafting, reviewing, researching) proceeds normally.

This rule preserves the plugin's "best-effort live progress" posture: the pipeline must work even when live progress can't be rendered. The contract is: live progress is a nice-to-have, not a critical-path dependency.

## Canonical subagent update pattern

Every instrumented subagent uses this exact Bash invocation at its step boundaries. The agent prompt documents which step boundaries trigger an update (per-issue, per-MCP-query, etc.) — this block is the mechanical pattern. **The renderer is the ONLY supported way for a subagent to write `<work_dir>/live-progress.html`** (see HARD RULE above) — do not Write/Edit the file directly with custom HTML, even if your subagent has richer data than the standard chips show.

```bash
# Subagent step-boundary live-progress update.
# Reads artifact_id + html_path from state.json. Skips entirely if disabled.

STATE_JSON="<absolute path to state.json — passed in by orchestrator>"
ENABLED=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); c=d.get('config',{}); print('1' if c.get('live_progress_enabled') else '0')" "$STATE_JSON" 2>/dev/null || echo "0")

if [ "$ENABLED" = "1" ]; then
  ARTIFACT_ID=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print((d.get('live_progress') or {}).get('artifact_id',''))" "$STATE_JSON")
  HTML_PATH=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print((d.get('live_progress') or {}).get('html_path',''))" "$STATE_JSON")
  CURRENT_STEP="<short description of what's happening NOW>"   # set per call site

  if [ -n "$ARTIFACT_ID" ] && [ -n "$HTML_PATH" ]; then
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_live_progress.py" \
      --state-json "$STATE_JSON" \
      --current-step "$CURRENT_STEP" \
      --output "$HTML_PATH"
  fi
fi
```

Then, in the same agent message after the Bash block, the subagent calls `mcp__cowork__update_artifact` with the resolved id and path (only if enabled — gate via if-check on the bash output, or check `state.json.config.live_progress_enabled` directly before the tool call). The `update_summary` field is a short string like `step=issue-3-of-7` or `mcp-query=ldh-resolve-celex-32016R0679`. This summary appears in the chat-scroll "Updated artifact: …" strip alongside the artifact id and is the user's only attribution back to "which subagent did what" — keep it concise and informative.

## When subagents call update_artifact (the rules)

Each instrumented agent documents its OWN call sites in its agent file under a "Live progress" section. The rules of thumb (current as of v0.6.0):

| Subagent | Cadence (v0.6.0) | Approximate calls per dispatch |
|---|---|---|
| `memo-writer` | Start + per-section (Exec Summary, Background, Facts, Conclusion, Sources) + per-issue (N issues) + assembling + done | 9 + N |
| `statutory-researcher` | Start + per-issue (N) + done | 2 + N |
| `case-law-researcher` | Start + per-issue (N) + done | 2 + N |
| `doctrinal-researcher` | Start + per-issue (N) + done | 2 + N |
| `research-sufficiency-reviewer` | Start + done (per pass; 1-2 passes) | 2 × passes |
| `currency-checker` | Start + done | 2 |
| `source-pack-builder` | Start + done. Also writes `state.json.live_progress.source_counts` on done. | 2 |
| `style-reviewer` / `clarity-reviewer` / `logic-reviewer` / `counterargument-reviewer` / `citation-auditor` | Start + done (per review pass) | 2 |
| `revision-mediator` | Start + per-reviewer-consumed (3-5) + done (per iteration) | 5-7 × iterations |
| `client-readiness-reviewer` | Start + done | 2 |
| `fact-assumption-analyst` | Start + done | 2 |
| `style-extractor` | Not instrumented (Style Studio only) | 0 |

**Budget per typical run:** Brief mode ~45 calls; Full-mode 2-iteration run ~75 calls; Full-mode 5-iteration run ~110 calls.

## v0.6.0+ additions: orchestrator-owned state fields

Three new fields in `state.json.live_progress` power the dashboard chips and header. The renderer surfaces each chip ONLY when its source field is populated; all default to null.

- **`live_progress.active_subagents`** — list of subagent names currently running. Set by ORCHESTRATOR (memo skill) before every `Task(subagent_type=...)` dispatch; cleared (set back to null or `[]`) after the dispatch(es) return. Renders as ONE `🛠 <subagent-name>` chip per list element, so a parallel-3-researcher dispatch shows three chips side-by-side. v0.6.0–v0.6.1 used a bare-string `active_subagent` (singular) field which collapsed parallel dispatches into a coarse label like `"3 researchers (parallel)"` — list form (v0.6.2+) gives per-subagent visibility. Backwards-compat: renderer accepts the legacy `active_subagent` string and treats it as a single-element list. See SKILL.md §"MANDATORY — orchestrator's active_subagents plumbing".

- **`live_progress.source_counts`** — populated by `source-pack-builder` agent (Phase 7) on its `done` emission. Shape: `{statutes: <int>, cases: <int>, doctrine: <int>}`. Renders as a `📊 N statutes · M cases · K doctrine` chip once present. Set by no other agent. Once set, persists for the rest of the run (Phase 7 onwards). See source-pack-builder.md §"State.json source_counts".

- **`live_progress.topic`** (v0.6.2+) — short 3–7 word theme generated by orchestrator at Step 1d (mint) from `user_query`. Replaces the truncated raw user_query line in the dashboard header — clean theme line vs `"We're a US-based SaaS company..."` truncation. Examples: `"GDPR compliance for AI support feature"`, `"Schrems II transfer assessment"`, `"DPA-vs-clickwrap dispute analysis"`. When null/empty, renderer falls back to truncating `user_query` to ≤137 chars + "…".

## v0.6.0 additions: real-time JS tickers in the rendered HTML

`render_live_progress.py` v0.6.0 embeds an inline `<script>` block (~30 lines) at the end of the HTML. The script:
- Reads `data-phase-started-at-iso`, `data-started-at-iso`, `data-render-iso` attributes set by the Python renderer.
- Uses `setInterval(tick, 1000)` to update three `<span>` nodes: elapsed-in-phase, total elapsed, and "Updated X ago".
- Does NOT use `fetch`, `postMessage`, or any harness callback. Pure self-contained DOM mutation.
- Wraps everything in a `try { ... } catch (e) { }` so if the Cowork iframe sandbox blocks `<script>` execution, the tickers just stay at the values the Python renderer last computed (which is the prior v0.5.x baseline behavior — no regression).

The tickers run between `update_artifact` calls, so the dashboard feels alive even during long quiet phases. Each tick is local DOM-only, so the iframe does not generate any new MCP traffic.

**Concurrency note for Phase 5 parallel research.** The 3 researchers dispatch in parallel and update the SAME `<work_dir>/live-progress.html` file via the SAME `artifact_id`. The renderer's atomic write (`.tmp` + rename) prevents torn HTML. The user sees the sidebar card alternate between researchers' current-step messages — that visible turbulence IS informative ("multiple things are running in parallel"). Last-writer-wins on the card content is acceptable; no lock file or coordination is required.

## Failure modes and graceful degradation

| Situation | Behavior | Recovery |
|---|---|---|
| Cowork unavailable / artifact tools absent | Phase 1 step 3.5 detects → `live_progress_enabled = false` → all subagents skip silently | Pipeline runs without live progress; everything else unchanged. |
| `create_artifact` fails with "id already exists" (resumed task) | Orchestrator falls back to `update_artifact` to refresh existing card | Log `live_progress_existing_artifact_reused` event. No user-visible change. |
| `update_artifact` call errors mid-pipeline | Treat as best-effort; do NOT fail the task. Log `live_progress_update_failed` event with error. Continue. | Same as before: live progress is best-effort; substantive work proceeds. |
| `render_live_progress.py` script error (e.g. malformed state.json) | The Bash render step fails; subagent SKIPS the `update_artifact` call for this step but continues its substantive work | Validator catches malformed state.json at the next `validate_state.py` invocation if any. |
| HTML file written but renderer's atomic .tmp left behind | Worst case is a `live-progress.html.tmp` file in work_dir. No functional impact. Cleaned up next render. | None needed. |
| User closes the "Live artifacts" sidebar | The artifact still exists; user can reopen via Cowork sidebar selector. No data loss. | None needed. |

## What this contract is NOT

- **Not a replacement for chat Progress blocks.** The mandatory `**Progress —**` chat messages defined in `progress-contract.md` remain primary. Live-progress is a SUPPLEMENTARY visual channel — it makes "what's happening RIGHT NOW between Progress blocks" visible.
- **Not a replacement for `TodoWrite` side-panel updates.** TodoWrite remains the canonical side-panel channel (right-side task list). Live-progress is sidebar (left-side artifacts card).
- **Not a replacement for `progress-tracker.md` visualize widget.** The 5 milestone renders defined in progress-tracker.md remain. They are snapshot views at phase-group boundaries; live-progress is continuous between them.
- **Not a replacement for the events.jsonl audit log.** `events.jsonl` is the forensic record; live-progress is the user-facing UI surface. Both exist.
- **Not a multi-turn architecture.** v0.5.0 deliberately does NOT use `ScheduleWakeup` to self-resume the orchestrator across multiple turns. The architecture stays single-turn-per-pipeline-segment (Phase 1→Phase 7.5, then Phase 8→Phase 12 after `continue`). Multi-turn was investigated and deferred — see `C:\Users\User\.claude\plans\c-users-user-desktop-cowork-claude-memo-inherited-gizmo.md` for the deferred design.

## Atomic-write and state.json discipline

- `live-progress.html` MUST be written via the `render_live_progress.py` script, which uses atomic .tmp + rename. Subagents MUST NOT write the HTML file directly — they invoke the script.
- `state.json.live_progress.timeline` and `phase_started_at_iso` are owned by the **orchestrator** (memo skill's Phase boundary handling). Subagents MUST NOT write to these fields. Subagents only read.
- `state.json.live_progress.artifact_id` and `html_path` are set ONCE at Phase 1 step 3.5 and immutable thereafter.
- `state.json.config.live_progress_enabled` is set ONCE at Phase 1 step 3.5 and immutable thereafter.

## Encoding requirement (still binding from v0.2.0 work)

Every HTML rendered for a Cowork artifact MUST include `<meta charset="UTF-8">` in `<head>`. Cowork's artifact iframe does NOT auto-detect UTF-8 — em-dashes, curly quotes, and Cyrillic render as mojibake (`â€"`) without the meta tag. `render_live_progress.py` enforces this in its template; do not write the HTML by hand and skip the meta tag.

## Where this is read

This document is loaded:
- ONCE on orchestrator activation (after `operating-contract.md`, `events-contract.md`, `progress-contract.md`).
- By every instrumented subagent on its activation (each agent file's "Live progress" section points here).
- By `references/INDEX.md` and `references/operating-contract.md` (authority hierarchy entry).
