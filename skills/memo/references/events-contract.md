# Events contract — `events.jsonl` schema and event taxonomy

Single source of truth for the orchestrator-owned audit log. `events.jsonl` lives at `<state.json.work_dir>/events.jsonl`, is created at Phase 1, and is append-only for the rest of the task. Each line is a strict JSON object conforming to the schema below.

`logging-contract.md` covers the SEPARATE per-subagent `<work_dir>/logs/<agent>.log` files (human-readable progress for long-running blocks). This document covers ONLY `events.jsonl`.

## Schema v1

Every event MUST have exactly these top-level fields:

```json
{
  "ts": "<ISO 8601 with milliseconds, UTC>",
  "event": "<kebab-case event name>",
  "phase": "<state.current_phase at emit time, or null>",
  "iteration": <int or null>,
  "actor": "memo-skill | continue-skill | <agent-name> | validator | md_to_docx",
  "severity": "info | warn | error",
  "data": { …event-specific payload… }
}
```

- **`ts`** — UTC timestamp, format `YYYY-MM-DDTHH:MM:SS.sssZ` (`.sss` = milliseconds). Always UTC. Always millisecond precision.
- **`event`** — kebab-case event name. MUST be from the enum below or a documented extension.
- **`phase`** — the value of `state.json.current_phase` at the moment of emission. For events fired BEFORE Phase 1 init (rare; e.g. reentry-check scanning), use `null`. For `phase_transition` events specifically, `phase` is the NEW phase; `data.from` and `data.to` carry the actual transition.
- **`iteration`** — `state.json.current_iteration` at emit time. `null` for events outside the revision loop (Phases 1–8, 10–12). Integer for events inside the revision loop or referring to a specific iteration.
- **`actor`** — who emitted the event. Use the canonical actor names:
  - `memo-skill` — main session running `memo` skill
  - `continue-skill` — main session running `continue` skill
  - `<agent-name>` — a subagent (e.g. `statutory-researcher`, `revision-mediator`); subagents emit only domain-specific events (e.g. `mcp_ratelimit_fallback`), not orchestration events
  - `validator` — `scripts/validate_state.py` or `scripts/validate_review_json.py` (orchestrator emits on behalf of the validator with this actor name, since the scripts themselves are silent)
  - `md_to_docx` — the docx export script (emitted from inside `md_to_docx.py` or from the orchestrator on its behalf)
- **`severity`** — `info` for normal flow, `warn` for fallbacks / degradations (still completing), `error` for hard failures (task moved to `failed` phase).
- **`data`** — event-specific JSON object. Per-event shapes documented below.

## How to emit (canonical pattern)

Use the helper script `scripts/log_event.py` from Bash:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/log_event.py" \
  --workdir "$WORK_DIR" \
  --event phase_transition \
  --phase research \
  --actor memo-skill \
  --data '{"from":"plan_approval_pending","to":"research","reason":"plan_approved"}'
```

Optional flags:
- `--iteration <int>` — include when emitting from inside the revision loop
- `--severity warn|error` — default is `info`

The helper:
- Stamps `ts` with current UTC ISO 8601 + milliseconds
- Ensures `data` is a JSON object (rejects arrays / strings)
- Creates `<workdir>` and `events.jsonl` if they do not exist
- Appends one JSONL line atomically
- Returns 0 on success, 1 on filesystem error, 2 on bad arguments

**Best-effort discipline.** If `log_event.py` fails (filesystem read-only, disk full, etc.), the orchestrator MUST swallow the error and continue the pipeline. NEVER fail a task because logging failed. This mirrors the rule in `logging-contract.md` for per-agent logs.

## When to emit — core five events (Tier 1)

These five event types form the minimal observability slab. They MUST be emitted at every point the contract calls for. Adding them is what makes the audit log usable for debugging.

### `phase_transition`

Fired EVERY time `state.json.current_phase` changes. This is the timeline. Without it, audit log cannot reconstruct phase ordering.

- **Actor:** the writer of `state.json.current_phase` (usually `memo-skill` or `continue-skill`; for mediator-driven transitions in Phase 9, `memo-skill` emits AFTER reading the updated state.json)
- **`phase`** — the new phase value (matches `data.to`)
- **`iteration`** — current iteration if inside revision_loop, else null
- **`data` shape:**
  ```json
  {
    "from": "<previous phase>",
    "to": "<new phase>",
    "reason": "<short kebab-case reason: plan_approved | sufficiency_sufficient | mediator_approved | …>"
  }
  ```

Example reasons by transition (non-exhaustive):
- `intake_preliminary_research → intake_questions_pending`: `fact_assumption_complete`
- `intake_questions_pending → mode_pick_pending`: `intake_answered` | `intake_assumptions_accepted`
- `mode_pick_pending → planning`: `mode_selected`
- `planning → plan_approval_pending`: `plan_written`
- `plan_approval_pending → research`: `plan_approved`
- `research → research_sufficiency`: `all_researchers_returned`
- `research_sufficiency → currency_check`: `sufficiency_sufficient` | `sufficiency_followup_complete`
- `research_sufficiency → research_sufficiency`: `followup_dispatched` (re-entry)
- `currency_check → research_sufficiency`: `currency_invalidated_sources_regate`
- `currency_check → source_pack`: `currency_clean` | `regate_used`
- `source_pack → source_review_pending`: `source_pack_built` (v0.0.43+; replaces `source_pack → heartbeat_pending`)
- `source_review_pending → drafting`: `source_review_continue`
- `source_review_pending → cancelled_by_user`: `source_review_cancel`
- Legacy: `heartbeat_pending → source_review_pending`: `legacy_phase_migrated` (continue/SKILL.md only, when resuming v0.0.42 tasks)
- `drafting → revision_loop`: `v1_written`
- (Legacy `drafting → export: research_summary_branch` was removed in v0.0.43 — full pipeline only.)
- `revision_loop → revision_loop`: `iteration_advance` (mediator) | `auto_continue` (v0.0.44+ — orchestrator auto-advances on mediator `needs_revision` with budget remaining)
- `revision_loop → client_readiness`: `mediator_approved` | `auto_forced_exit` (v0.0.44+; replaces v0.0.43 `gate_accept_early` / `gate_continue_to_client_readiness`)
- (Legacy `revision_loop → export: gate_skip_polish` was removed in v0.0.44 — pipeline never skips client-readiness. Legacy tasks resumed via continue/SKILL.md with `client_readiness_gate_choice == "skip_polish"` are normalised to continue.)
- `client_readiness → client_readiness`: `polish_applied` (v0.0.44+ — auto-polish loop re-runs reviewer)
- `client_readiness → export`: `client_ready` | `polish_complete` | `manual_review_required`
- `export → done`: `docx_written` | `markdown_fallback_written`
- `<any> → failed`: `<failure-specific reason>`
- `<any> → cancelled_by_user`: `user_cancelled`

### `agent_dispatched`

Fired immediately BEFORE every `Task(subagent_type=...)` call.

- **Actor:** caller (memo-skill or continue-skill)
- **`data` shape:**
  ```json
  {
    "subagent_type": "<e.g. statutory-researcher>",
    "purpose": "<short kebab-case: initial-research | followup-research | revision | polish | …>",
    "expected_outputs": ["research/statutes.md"],
    "dispatch_id": "<unique-per-task short id, e.g. phase5-statutory-1>"
  }
  ```

`dispatch_id` lets you pair `agent_dispatched` with the matching `agent_returned` event (the same id appears on both). Useful when 5 reviewers dispatch in parallel — you need to pair returns.

### `agent_returned`

Fired immediately AFTER a `Task(...)` Agent call returns.

- **Actor:** caller (memo-skill or continue-skill)
- **`data` shape:**
  ```json
  {
    "subagent_type": "<e.g. statutory-researcher>",
    "dispatch_id": "<same id as agent_dispatched>",
    "duration_seconds": <float, computed by orchestrator>,
    "outputs_written": ["research/statutes.md", "research/raw/statutes/_index.json"],
    "final_response_summary": "<≤120-char one-line summary of agent's text response>"
  }
  ```

`duration_seconds` is end-of-Bash-timestamp minus start, captured by the orchestrator. If timing is unavailable, omit the field rather than fake it.

### `gate_answered`

Fired AFTER every `AskUserQuestion` resolution OR text-based gate parse. Canonical gates as of v0.6.3: Phase 1.5 mode (AskUserQuestion), Phase 2a intake (visualize widget + text parse), Phase 4a plan approval (AskUserQuestion), Phase 6.6 sufficiency follow-up (visualize widget + text parse, v0.6.3+), Phase 7.5 source-review (text-parsed since v0.0.43). Phase 9.6b/6c iteration and Phase 10 polish gates were removed in v0.0.44 — they now fire `gate_auto_advanced` (see below) instead.

- **Actor:** the calling skill
- **`data` shape:**
  ```json
  {
    "gate_name": "mode-pick | intake-elicitation | plan-approval | sufficiency-followup | source-review",
    "options_offered": ["continue", "cancel"],
    "chosen": "continue",
    "was_fallback": false,
    "fallback_reason": null
  }
  ```

- `was_fallback = true` when AskUserQuestion was unavailable OR the user dismissed without picking AND the orchestrator applied a documented default. In that case `chosen` reflects the applied default and `fallback_reason` explains why ("askuserquestion_unavailable" | "user_dismissed" | …).
- Source-review gate is text-parsed, not AskUserQuestion (see Phase 7.5 in `skills/memo/SKILL.md` — Cowork issues #29773 family). `gate_name: "source-review"` fires with `was_fallback: false` on a clean `continue`/`cancel` reply; `was_fallback: true` with reason `"reprompt"` if the orchestrator re-showed the checkpoint due to an unparseable reply.
- Sufficiency-followup gate (v0.6.3+) is the Phase 6.6 user-followup gate that fires conditionally when `research-sufficiency.json.overall_verdict == "targeted_followup_needed"` AND at least one `blocking_gap.target_agent == "main-session"`. It is rendered as a visualize elicitation widget when `visualize_enabled` (preferred path) or as text fallback otherwise. `gate_name: "sufficiency-followup"` `options_offered: ["letter-answers", "free-text", "proceed-on-defaults", "cancel"]`. `chosen` values: `"provided_facts"` (user answered via `followup: 1A 2C ...`), `"proceed-on-defaults"` (user typed `proceed`), `"cancel"`. A `gate_announced` event SHOULD also fire when the gate is first rendered (separate from `gate_answered` which fires when the user replies in the next turn). At most ONE Phase 6.6 gate per task — bounded by `attempts.research_followup`.
- (Legacy `gate_name: "heartbeat"` events appear in audit logs of tasks created on v0.0.42 or earlier — accept on read, do not emit on write.)
- (Legacy `gate_name: "revision-iter" | "revision-forced-exit" | "polish"` events appear in audit logs of tasks created on v0.0.43 or earlier — accept on read; new tasks emit `gate_auto_advanced` instead.)

### `gate_auto_advanced` (v0.0.44+)

Fired when the orchestrator advances past a former user gate without user input (the v0.0.44 autonomous post-source-review block). Audit-only event — records the decision the orchestrator made automatically based on mediator/reviewer verdict.

- **Actor:** the calling skill
- **`data` shape:**
  ```json
  {
    "gate_name": "revision-iter | revision-forced-exit | polish",
    "chosen": "continue | apply",
    "reason": "<short kebab-case: mediator_needs_revision_with_budget | mediator_forced_exit | needs_final_polish_with_budget>"
  }
  ```

These fire in Phase 9 step 6b auto-advance (`revision-iter` / `continue`), Phase 9 step 6c auto-advance (`revision-forced-exit` / `continue`), and Phase 10 auto-polish (`polish` / `apply`). No corresponding `gate_answered` event fires.

### `validator_ran`

Fired AFTER every `python3 scripts/validate_*.py` subprocess call.

- **Actor:** `validator` (with the orchestrator skill noted in `data.invoked_by`)
- **`data` shape:**
  ```json
  {
    "script": "validate_state.py | validate_review_json.py",
    "args_summary": "<short string: --state .../state.json | --workdir ... --iteration 2>",
    "exit_code": 0,
    "errors_count": 0,
    "warnings_count": 0,
    "invoked_by": "memo-skill | continue-skill",
    "purpose": "<short: post-mediator | post-export | reviewer-json-check | …>"
  }
  ```

When the validator returns non-empty errors, set `severity = "warn"` (orchestrator may still recover via retry) or `severity = "error"` (fatal, moving to `failed`).

## Existing event taxonomy (Tier 0 — already emitted, kept)

These 23 events are emitted by the current pipeline and remain canonical. They should be migrated to the schema-v1 shape (`{ts, event, phase, iteration, actor, severity, data}`) over time, but for now they remain in their historical shape. The helper `log_event.py` accepts any of them.

| Event | Actor | When | Severity |
|---|---|---|---|
| `task_created` | memo-skill | Phase 1 init | info |
| `work_dir_resolved` | memo-skill | Phase 1 init (after candidate walk) | info |
| `mcp_precheck_result` | memo-skill | Phase 1 step 2 | info |
| `visualize_precheck_result` | memo-skill | Phase 1 step 3 | info |
| `header_sanitized` | memo-skill | Phase 2a sanitization | warn |
| `question_skipped_invalid_options` | memo-skill | Phase 2a sanitization | warn |
| `options_truncated` | memo-skill | Phase 2a sanitization | warn |
| `description_truncated` | memo-skill | Phase 2a sanitization | warn |
| `visualize_widget_rendered` | memo-skill | Phase 1.5/3/7/9/12 | info |
| `visualize_call_failed` | memo-skill | Phase 1.5/3/12 | warn |
| `mode_selected` | memo-skill | Phase 1.5 AskUserQuestion | info |
| `intake_completed` | memo-skill | Phase 2b parser exit | info |
| `plan_approved` | memo-skill | Phase 4a/4b approval | info |
| `phase5_dispatch` | memo-skill | Phase 5 before researchers | info |
| `mcp_ratelimit_fallback` | `<researcher>` | mid-research throttle | warn |
| `research_followup_started` | memo/continue-skill | Phase 6 before re-dispatch | info |
| `currency_invalidated_sources` | memo/continue-skill | Phase 6.5 before re-gate | warn |
| `revision_gate_continue` | memo-skill | Phase 9.6b answer | info |
| `revision_gate_accept_early` | memo-skill | Phase 9.6b answer | info |
| `client_readiness_skipped` | memo-skill | Phase 9.6c answer | warn |
| `client_readiness_polish_started` | memo/continue-skill | Phase 10 before polish | info |
| `polish_skipped_by_user` | memo-skill | Phase 10 answer | info |
| `reviewer_json_retry_started` | memo/continue-skill | Phase 9 step 2 retry | warn |
| `fallback_invoked` | memo/continue-skill | any fallback path | warn |

`gate_answered` is the NEW canonical event for AskUserQuestion outcomes. The existing `mode_selected` / `revision_gate_*` / `polish_skipped_by_user` events SHOULD continue to be emitted (they carry richer per-gate context like the chosen mode or polish attempt number), but the orchestrator SHOULD ALSO emit a `gate_answered` event with the canonical shape so cross-gate aggregation works.

## Tier 2 — Cross-run learning events (v0.7.0+)

These events were added with the Layer B / Lessons Studio system. They emit at Phase 11.5 (post-export) and carry summary counts of what the `lessons-extractor` agent produced for this task.

| Event | Actor | When | Severity |
|---|---|---|---|
| `lessons_extracted` | memo-skill | Phase 11.5 after lessons-extractor returns | info (warn on extraction_failed) |

### `lessons_extracted`

Fired once per task at the end of Phase 11.5 after the `lessons-extractor` subagent returns. Records the per-task signal extraction count and any lessons that crossed thresholds and were promoted: Tier 1 hints auto-applied to `learned-patterns.md` with audit records under `lessons/applied/auto/`; Tier 2/3 candidates written to `lessons/pending/` for Studio review. Tier 0 stats are recomputed unconditionally each run and do NOT count toward `lessons_promoted` or `auto_applied_count`.

- **Actor:** `memo-skill`
- **`phase`** — `done` (the agent runs after `phase = done` has been set)
- **`iteration`** — `null` (post-loop)
- **`severity`** — `info` on success; `warn` if extractor reported `extraction_failed: true`
- **`data` shape:**
  ```json
  {
    "signals_written": <int>,                    // number of new signal files written under signals/<task_id>-*.json
    "lessons_promoted": <int>,                   // total lessons promoted this run (Tier 1+2+3) — equals auto_applied_count + pending_count. Tier 0 stats refreshes are NOT counted here (they happen unconditionally every run and have no lesson_id; see lessons-extractor §"Always-recompute Tier 0 sections")
    "auto_applied_count": <int>,                 // Tier 1 only — advisory hints (intake/currency/MCP-health) appended to learned-patterns.md with audit records under applied/auto/<lesson_id>.md
    "pending_count": <int>,                      // Tier 2+3 — written to lessons/pending/ for Studio review
    "groups_examined": <int>,                    // number of pattern_key groups that crossed numeric threshold this run, BEFORE semantic clustering or quality gate (pre-merge count)
    "clustering_merges": <int>,                  // number of semantic merges performed this run (merging near-threshold groups within the same kind prefix); see lessons-extractor §Semantic clustering
    "quality_gate_vetoed": <int>,                // number of above-threshold candidates that failed at least one of the four quality-gate checks and were NOT promoted to a pending lesson file
    "lessons_dir": "<absolute path to plugin-data/memoforge/lessons>",
    "extraction_failed": false | true,           // true if Pass 1 or Pass 2 errored; details in `error` field
    "error": null | "<short reason>"             // populated only when extraction_failed
  }
  ```

**Invariants:** `lessons_promoted == auto_applied_count + pending_count`. Roughly `lessons_promoted ≤ groups_examined + clustering_merges` (some examined groups get vetoed; merges may add to promotions when they push a synthesized group above threshold). When `extraction_failed == true`, the three judgment counters (groups_examined / clustering_merges / quality_gate_vetoed) may be 0 reflecting the truncated run rather than the corpus reality.

Example success entry (steady-state run):
```json
{"ts":"2026-05-26T18:42:11.124Z","event":"lessons_extracted","phase":"done","iteration":null,"actor":"memo-skill","severity":"info","data":{"signals_written":4,"lessons_promoted":1,"auto_applied_count":1,"pending_count":0,"groups_examined":3,"clustering_merges":1,"quality_gate_vetoed":2,"lessons_dir":"/home/user/.claude/plugin-data/memoforge/lessons","extraction_failed":false,"error":null}}
```

Reading this entry: 4 signals written this task; 3 pattern_key groups crossed threshold; 1 semantic merge happened; the LLM quality gate vetoed 2 of the resulting candidates and let 1 through (auto-applied as a Tier 1 advisory hint into learned-patterns.md, with an audit record in lessons/applied/auto/); 0 pending lessons for Studio review. (Tier 0 stats sections were also unconditionally refreshed during this run, but Tier 0 doesn't contribute to these counters.)

Example failure entry (extractor crashed during Pass 2; Pass 1 may still have written signals):
```json
{"ts":"2026-05-26T18:42:11.124Z","event":"lessons_extracted","phase":"done","iteration":null,"actor":"memo-skill","severity":"warn","data":{"signals_written":4,"lessons_promoted":0,"auto_applied_count":0,"pending_count":0,"groups_examined":0,"clustering_merges":0,"quality_gate_vetoed":0,"lessons_dir":"/home/user/.claude/plugin-data/memoforge/lessons","extraction_failed":true,"error":"pass2_corpus_read_failed"}}
```

This event is informational — never blocks Phase 12. Downstream consumers (the `lessons` skill / "Studio") read the lessons files directly, not this event; the event exists for audit and debugging.

## Where each event SHOULD be added (T1 implementation roadmap)

These are the explicit insertion points in `skills/memo/SKILL.md` and `skills/continue/SKILL.md`:

### `phase_transition`

Every place that writes `state.json.current_phase`. In the current code base (after Batch 1–4 fixes), these include:

In `skills/memo/SKILL.md`:
- Phase 1: init writes `intake_preliminary_research` (implicit from `task_created`; no transition event needed since there is no "from" state)
- After Phase 1 step 4 (fact-assumption-analyst returns): `→ intake_questions_pending`
- After Phase 2b parsers exit: `→ mode_pick_pending`
- After Phase 1.5 atomic mode/config merge: `→ planning`
- After Phase 3 plan written: `→ plan_approval_pending`
- After Phase 4 approval: `→ research`
- After Phase 5 all researchers return: `→ research_sufficiency`
- Phase 6: branch into `→ currency_check` (sufficient or follow-up done) OR `→ research_sufficiency` (re-entry on follow-up dispatch)
- Phase 6.5: branch into `→ research_sufficiency` (currency re-gate) OR `→ source_pack`
- Phase 7 source-pack-builder returns: `→ source_review_pending` (v0.0.43+; legacy tasks may have `heartbeat_pending` and are migrated by continue/SKILL.md)
- Phase 7.5 source-review reply parsed: `→ drafting` (on `continue`) OR `→ cancelled_by_user` (on `cancel`)
- Phase 8: `→ revision_loop` (full pipeline only — research-summary mode removed in v0.0.43)
- Phase 9 mediator (v0.0.44+): `→ revision_loop` (next iteration — auto-advance per mediator `needs_revision`) OR `→ client_readiness` (auto-advance on mediator `approved` or `forced_exit`). The `→ export skip_polish` transition was removed in v0.0.44 (pipeline always runs client-readiness).
- Phase 10: `→ export`
- Phase 11: `→ done`

In `skills/continue/SKILL.md`:
- Each per-phase resume branch that completes a transition emits the same event (mirror of memo).

### `agent_dispatched` / `agent_returned`

Around every `Task(subagent_type=…)` call:

- Phase 1 step 4: `fact-assumption-analyst`
- Phase 5: 1–3 researchers in parallel (each gets its own dispatch_id, e.g. `phase5-statutory-1`, `phase5-case-law-1`, `phase5-doctrinal-1`)
- Phase 6: `research-sufficiency-reviewer` (possibly twice: initial + re-gate)
- Phase 6.5: `currency-checker`
- Phase 7: `source-pack-builder`
- Phase 8: `memo-writer` for v1 (full pipeline only — research-summary mode removed in v0.0.43)
- Phase 9 each iteration: 3 or 5 reviewers in parallel + `revision-mediator` sequential + `memo-writer` for v<N+1>
- Phase 10: `client-readiness-reviewer` (possibly + `memo-writer` for polish)
- Phase 10 polish re-review: `client-readiness-reviewer` again

### `gate_answered`

After every `AskUserQuestion` resolution:

- Phase 1.5 mode pick (`gate_name: mode-pick`) — AskUserQuestion
- Phase 2a intake elicitation widget OR Phase 2b text parser (`gate_name: intake-elicitation`) — visualize widget + text parse
- Phase 4a plan approval (`gate_name: plan-approval`) — AskUserQuestion; on `edit:` answer the gate is re-asked, so multiple `gate_answered` events may fire for the same task
- Phase 6.6 sufficiency follow-up (`gate_name: sufficiency-followup`, v0.6.3+) — visualize widget + text parse (`followup: 1A 2C 3:my answer` / `proceed` / `cancel`); fires conditionally when sufficiency reviewer returns `targeted_followup_needed` with at least one `main-session` blocking_gap; bounded to one-per-task by `attempts.research_followup`. A paired `gate_announced` event fires when the gate is first rendered.
- Phase 7.5 source-review (`gate_name: source-review`) — text-parsed `continue` / `cancel`, NOT AskUserQuestion (per v0.0.43 Cowork end-of-turn flush design)
- (Phase 9.6b iteration gate, Phase 9.6c forced-exit gate, Phase 10 polish gate were removed in v0.0.44 — they fire `gate_auto_advanced` instead, see below.)

### `validator_ran`

After every `python3 scripts/validate_*.py` subprocess:

- Phase 9 step 2: `validate_review_json.py` (and again after each retry / failure-stub pass)
- Phase 9 step 4: `validate_state.py` (after mediator)
- Phase 11 export: `validate_state.py` (final state sanity check before docx write — orchestrator decision)

## Migration policy

New code MUST use schema v1 via `log_event.py`. Existing emission points (the 23 Tier 0 events) MAY use either:
1. Their historical shape (just `printf` + `>>` to events.jsonl); OR
2. The canonical helper `log_event.py` with their event name in `--event` and existing payload in `--data`.

When a Tier 0 emission point is touched for any other reason, migrate it to the helper.

## Reading / debugging

To read events for a task:

```bash
cat "$WORK_DIR/events.jsonl" | python3 -m json.tool --no-indent
```

To filter:

```bash
grep '"event":"phase_transition"' "$WORK_DIR/events.jsonl"
grep '"severity":"warn"' "$WORK_DIR/events.jsonl"
grep '"severity":"error"' "$WORK_DIR/events.jsonl"
```

To extract the phase timeline:

```bash
grep '"phase_transition"' "$WORK_DIR/events.jsonl" \
  | python3 -c "import json,sys
for line in sys.stdin:
  ev = json.loads(line)
  print(f\"{ev['ts']}  {ev['data']['from']} -> {ev['data']['to']}  ({ev['data'].get('reason','')})\")"
```

A higher-level summary script is on the roadmap (Tier 5 — `scripts/summarize_events.py`).

## What this contract does NOT cover

- Per-subagent `<work_dir>/logs/<agent>.log` files — covered by `logging-contract.md`. Those carry step-level human progress (`step=issue-3-of-7 detail=...`); they are NOT the audit log.
- Chat-visible progress blocks (`**Progress —**`) — covered by `progress-contract.md`. They are visible to the user; events.jsonl is not.
- `state.json` mutations — captured by validator + state-schema.md, not by events.jsonl. (A `state_field_updated` event for the most critical fields is a Tier 3 improvement, not part of this contract.)
- MCP tool call telemetry — handled by the MCP host, not the plugin.

## Versioning

This is `schema_version: 1`. Backwards-incompatible changes (e.g. renaming a top-level field, changing `data` shape for an existing event) require a `schema_version: 2` bump and an explicit migration policy.
