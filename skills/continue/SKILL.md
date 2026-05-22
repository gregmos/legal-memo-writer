---
name: continue
description: Resume an interrupted legal memo task. Use only when explicitly invoked via /legal-memo-writer:continue with the task_id, optionally followed by one of answer, proceed, approve, cancel, or edit.
argument-hint: "<task_id> [answer: <facts>|proceed|approve|cancel|edit: <instructions>]"
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task, AskUserQuestion, WebFetch, WebSearch, mcp__*, mcp__plugin_legal-memo-writer_courtlistener__*, mcp__plugin_legal-memo-writer_legal-data-hunter__*
---

# legal-memo-writer / continue skill

You are the main session resuming an interrupted legal memo task. This is the **explicit recovery path** when automatic reentry on the `memo` skill did not pick up the previous state (closed tab, new session, long pause).

## Parse argument

Read `$ARGUMENTS`. Parse it as:
- first whitespace-delimited token → `task_id` (the slug of the working directory; `task_id` always starts with `memo-`);
- remaining text, if any → explicit intake or plan-review response (`answer: <facts>`, `proceed`, `approve`, `cancel`, or `edit: <instructions>`).

## Task discovery (where to find the working directory)

The plugin used to stage tasks under `${CLAUDE_PLUGIN_DATA}/work/` then copy them to the user output folder at the end. As of v0.0.29 there is **no staging** — every task lives directly in the user's output folder from Phase 1 onwards.

Resolution order (first writable that contains a matching `<task_id>` directory wins):

1. `$CLAUDE_PLUGIN_OPTION_OUTPUT_FOLDER/<task_id>/` (plugin option set by the user).
2. `$LEGAL_MEMO_OUTPUT_FOLDER/<task_id>/` (environment variable).
3. `$HOME/Documents/legal-memos/<task_id>/` (default for desktop installs).
4. `outputs/legal-memo-work/<task_id>/` (sandbox fallback, relative to CWD).
5. `<WORK_DIR>/` (legacy fallback for tasks created before v0.0.29).

For each candidate, check via `Bash test -d "<candidate>"` then `test -f "<candidate>/state.json"`. The first match is the working directory; bind it to `WORK_DIR` and use it for all subsequent Read/Write/Bash operations.

**Resolve the relative-to-CWD form for chat output.** Read `state.json.rel_work_dir`. If the field is absent (legacy task created before this field existed), compute it now and write it back to state.json:

```bash
REL_WORK_DIR=$(realpath --relative-to="$(pwd)" "$WORK_DIR" 2>/dev/null \
  || python3 -c "import os.path,sys; print(os.path.relpath(sys.argv[1]))" "$WORK_DIR" 2>/dev/null \
  || python  -c "import os.path,sys; print(os.path.relpath(sys.argv[1]))" "$WORK_DIR" 2>/dev/null \
  || echo "$WORK_DIR")
```

Write the value back to `state.json.rel_work_dir` atomically (write `.tmp`, mv). **Every informational path reference printed by this skill MUST use `state.json.rel_work_dir`, not `WORK_DIR`** — `rel_work_dir` gives the user a short, human-readable path. (Cowork does NOT render relative or absolute paths as clickable links inside chat text — clickable file access comes from Cowork's artifact cards on `Read`/`Write`/`Edit` tool calls, not from text content. Use `rel_work_dir` purely for readability.)

If `$ARGUMENTS` is empty:
1. Scan all four candidate parents (1-4 above) for `memo-*` directories.
2. For each found `task_id`, **call `Read` on `<resolved_path>/state.json`** (this gives Cowork's UI an artifact card for the state file so the user can click it open) and **print one row** as plain text: `<task_id> | <current_phase> | <created_at> | <user_query truncated to 100 chars> | path: <state.json.rel_work_dir>/`. Don't bother with markdown link syntax — it doesn't render as clickable in chat. The `Read` call above is what makes the file accessible.
3. Ask the user to re-invoke with `/legal-memo-writer:continue <task_id>`.
4. End turn.

If `task_id` is non-empty but no candidate parent contains the directory:
1. Print: "task_id `<arg>` not found in any of the standard output folders."
2. List available task_ids as above (plain text rows with `Read` on each state.json so Cowork inserts artifact cards).
3. End turn.

## Resume by phase

Read `<WORK_DIR>/state.json`.

### Legacy state migration (run FIRST, before phase branching)

Tasks created before the modes-and-templates simplification (pre-2-mode release) use the three-mode names (`quick` / `standard` / `deep`), the `template_constraint` config object, the `targeted_followup_forced` field, and the deleted template ids (`risk-assessment`, `regulatory-analysis`, `cross-jurisdictional`). On resume, silently migrate them to the current schema BEFORE branching on `current_phase`. The migration is idempotent — running it on already-migrated state is a no-op.

```bash
python3 - <<'PY'
import json, pathlib, datetime
p = pathlib.Path("<WORK_DIR>/state.json")
s = json.loads(p.read_text())
changed = False
dropped = []

# Mode rename: quick → brief; standard|deep → full
legacy_mode = s.get("mode")
if legacy_mode == "quick":
    s["mode"] = "brief"
    changed = True
elif legacy_mode in ("standard", "deep"):
    s["mode"] = "full"
    changed = True

cfg = s.setdefault("config", {})

# Drop deprecated config keys; remember which were present for the audit event.
for key in ("template_constraint", "targeted_followup_forced"):
    if key in cfg:
        dropped.append(key)
        cfg.pop(key, None)
        changed = True

# Backfill direct template_id from the new mode. Only fires when mode is set
# (post-Phase-1.5 tasks); pre-mode-pick tasks have mode=None and stay without
# template_id until Phase 1.5 writes it.
if "template_id" not in cfg:
    if s.get("mode") == "brief":
        cfg["template_id"] = "executive-brief"
        changed = True
    elif s.get("mode") == "full":
        cfg["template_id"] = "classical-memo"
        changed = True

# Deep allowed up to 2 polish passes — collapse to Full's single-pass budget.
if cfg.get("max_client_polish", 0) > 1:
    cfg["max_client_polish"] = 1
    changed = True

# Map deprecated selected_template_id values to classical-memo, then sync
# selected_template_id with the new config.template_id so the validator's
# cross-field check (selected_template_id == config.template_id) passes.
# This catches the edge case where a legacy Standard task picked
# `executive-brief` via the now-removed `bounded` template_constraint —
# after migration to Full + classical-memo, selected_template_id must
# follow. The legacy short draft (if any) will be expanded to classical-memo
# on the next revision iteration; for already-completed tasks, the inflight
# resume path is moot (done tasks don't resume).
classification = s.get("classification") or {}
deprecated_templates = {"risk-assessment", "regulatory-analysis", "cross-jurisdictional"}
if classification.get("selected_template_id") in deprecated_templates:
    classification["selected_template_id"] = "classical-memo"
    s["classification"] = classification
    changed = True
# Sync selected_template_id with config.template_id when both are set and
# disagree (skip the research-summary-only heartbeat carve-out — validator
# accepts that combination separately).
new_tid = cfg.get("template_id")
sel_tid = classification.get("selected_template_id")
if (
    new_tid in ("executive-brief", "classical-memo")
    and sel_tid is not None
    and sel_tid != new_tid
    and sel_tid != "research-summary-only"
):
    classification["selected_template_id"] = new_tid
    s["classification"] = classification
    changed = True

if changed:
    # Append audit event to events.jsonl.
    ev = pathlib.Path("<WORK_DIR>/events.jsonl")
    payload = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "event": "state_migrated_legacy_modes",
        "phase": s.get("current_phase"),
        "actor": "continue-skill",
        "data": {"from_mode": legacy_mode, "to_mode": s.get("mode"), "dropped_keys": dropped}
    }
    with ev.open("a") as f:
        f.write(json.dumps(payload) + "\n")
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(s, indent=2))
    tmp.replace(p)
PY
```

This MUST run before any phase-specific resume logic so downstream readers see the current-schema state. If the script errors (e.g. corrupted JSON), surface to the user and stop — do not attempt to resume on a half-migrated state.

Branch on `current_phase`:

Before executing the phase branch, print a resume Progress block as plain assistant text (same v3 format documented in `skills/memo/references/progress-contract.md` §"Progress block format"):

```
**Progress — <task_id>**
- Current phase: `<current_phase>`
- Resuming from: `/legal-memo-writer:continue`
- Next: <what this invocation will do>
- Work directory: <state.json.rel_work_dir>
- Notes: <iteration N if revision_loop; blocker count if relevant; key files for this phase: <comma-separated list from mapping below>>
```

Per-phase key files mapping — use this list inside `Notes:` (as plain text, no markdown links) so the user knows what artifacts exist for the current phase. Files mentioned here are NOT clickable inside the Progress block, but the user can find them under `<state.json.rel_work_dir>/` in the Cowork file viewer. The next time you touch any of these files via `Read`/`Write`/`Edit`, Cowork's UI will insert an artifact card for that file automatically.

| current_phase                                       | Key files at this phase                                                                        |
|-----------------------------------------------------|------------------------------------------------------------------------------------------------|
| intake_preliminary_research                         | state.json, events.jsonl                                                                       |
| intake_questions_pending                            | state.json, intake/fact-assumption-report.md, checkpoints/intake-questions.md                  |
| mode_pick_pending                                   | state.json, intake/user-facts.md, $WORK_DIR/widgets/phase15-mode-mockup.html (if visualize)    |
| planning                                            | state.json, intake/user-facts.md                                                               |
| plan_approval_pending                               | state.json, plan.md, checkpoints/plan-approval.md                                              |
| research                                            | state.json, plan.md, research/ (folder)                                                        |
| research_sufficiency / currency_check / source_pack / source_review_pending (or legacy `heartbeat_pending`) | state.json, research/source-pack.md (if exists), research/ (folder)                            |
| drafting                                            | state.json, drafts/v\<latest\>.md                                                              |
| revision_loop                                       | state.json, drafts/v\<N\>.md, reviews/v\<N\>-mediator.md                                       |
| client_readiness                                    | state.json, drafts/v\<final\>.md, reviews/client-readiness.md                                  |
| export / done                                       | state.json, memo-\<slug\>.docx                                                                 |
| cancelled_by_user / failed                          | state.json, events.jsonl                                                                       |

After each resumed phase completes a material action, print another plain-text Progress block (this time with `Completed:` instead of `Resuming from:`). Same v3 format per `skills/memo/references/progress-contract.md`. Do not paste full research files or full drafts.

## TodoWrite restoration on resume

Before printing the resume Progress block above, call `TodoWrite` ONCE to rebuild the side-panel state. Without this call the right panel is empty after resume and the user cannot tell what has and has not run.

Use this mapping `current_phase → TodoWrite snapshot`. Items #1–#14 follow the canonical list in `skills/memo/references/progress-contract.md` §"TodoWrite side-panel channel". For each phase, mark everything strictly before the current phase as `completed`, mark the current phase as `in_progress`, mark everything strictly after as `pending`. Special cases noted below the table.

| current_phase                | Completed (status=completed)              | In progress (status=in_progress)            | Pending (status=pending) |
|------------------------------|-------------------------------------------|----------------------------------------------|---------------------------|
| intake_preliminary_research  | —                                          | #1 Intake                                    | #2–#14 |
| intake_questions_pending     | —                                          | #1 Intake                                    | #2–#14 |
| mode_pick_pending            | #1                                         | #2 Mode pick                                 | #3–#14 |
| planning                     | #1, #2                                     | #3 Build research plan                       | #4–#14 |
| plan_approval_pending        | #1, #2, #3                                 | #4 Plan approval                             | #5–#14 |
| research                     | #1–#4                                      | #5 Parallel research (+ sub-items per researcher in `state.json.dispatched_researchers`, each `in_progress`) | #6–#14 |
| research_sufficiency         | #1–#5 (+ Phase 5 sub-items completed)      | #6 Research sufficiency review               | #7–#14 |
| currency_check               | #1–#6 (+ sub-items)                        | #7 Currency check                            | #8–#14 |
| source_pack                  | #1–#7 (+ sub-items)                        | #8 Source pack assembly                      | #9–#14 |
| source_review_pending (or legacy `heartbeat_pending`) | #1–#8 (+ sub-items)                        | #9 Source review                             | #10–#14 |
| drafting                     | #1–#9 (+ sub-items)                        | #10 Draft v1                                 | #11–#14 |
| revision_loop                | #1–#10 (+ sub-items)                       | #11 Revision loop (activeForm `"Running revision loop (iteration <state.json.current_iteration>)"`) | #12–#14 |
| client_readiness             | #1–#11 (+ sub-items)                       | #12 Client-readiness review                  | #13–#14 |
| export                       | #1–#12 (+ sub-items)                       | #13 Export to docx                           | #14 |
| done                         | all #1–#14 (+ sub-items)                   | —                                            | — |
| cancelled_by_user / failed   | everything strictly before `<last_seen_phase>` | —                                        | the remaining items stay `pending` |

If `current_phase` is `research`, also re-add the per-researcher sub-items right under #5 using `state.json.dispatched_researchers` (one sub-item per entry: `"  · statutory-researcher"`, `"  · case-law-researcher"`, `"  · doctrinal-researcher"` with leading two-space indent). After research returns, the sub-items remain in the list as `completed` for the rest of the run.

If `TodoWrite` is unavailable in the host, skip this step silently — chat Progress remains the primary channel.

## Events contract (audit log)

Continue skill MUST emit the same canonical events as `memo` skill per `skills/memo/references/events-contract.md`. The five Tier 1 events apply identically:

| Event | When in continue |
|---|---|
| `phase_transition` | Every time you write `state.json.current_phase` in any resume branch (including mediator-driven transitions in `revision_loop`). Set `--actor continue-skill`. |
| `agent_dispatched` / `agent_returned` | Around every `Task(subagent_type=...)` call: re-dispatching researchers, re-dispatching reviewers, dispatching `revision-mediator`, dispatching polish `memo-writer`, dispatching `client-readiness-reviewer`, etc. |
| `gate_answered` | After every `AskUserQuestion` resolution OR text-based gate parse in resume branches: mode pick, intake elicitation, plan approval, source review (text-based). (Revision iteration / forced-exit and polish gates were removed in v0.0.44; they fire `gate_auto_advanced` instead — see `references/events-contract.md`.) |
| `validator_ran` | After every `python3 scripts/validate_*.py` subprocess (reviewer JSON validation in `revision_loop` branch; state validation post-mediator). |

Helper: `scripts/log_event.py` — see `events-contract.md` for the full call shape. Best-effort: a logging failure NEVER aborts the resume.

When emitting on resume, the convention is `--actor continue-skill` (vs. `memo-skill` in fresh runs). This lets downstream analysis distinguish events from initial pipeline vs. resume paths.

## Source acquisition strategy

Follow the same source-acquisition strategy as `skills/memo/SKILL.md` on every resumed branch. Canonical policy is `skills/memo/references/pipeline-contract.md §WebSearch` (mirrored in README). Operational summary:
- Bundled MCPs: Legal Data Hunter (multi-jurisdictional primary law + doctrine) and CourtListener (US case law, PACER/RECAP, citation status).
- **WebSearch is permitted as a DISCOVERY tool only** in the four discovery-capable researchers (`statutory-researcher`, `case-law-researcher`, `currency-checker`, `doctrinal-researcher`). NEVER cite a WebSearch result; cite the canonical text retrieved via MCP or WebFetch on the discovered official URL.
- `doctrinal-researcher` is the only researcher that may CITE WebFetch results from non-issuing-body sources (regulator guidance, peer-reviewed journals, SSRN, soft-law).
- MCP failure → two distinct fallbacks: *unavailable* (WebFetch on known official portals; document gaps), *rate-limited / 5xx* (one retry then WebFetch; log `mcp_ratelimit_fallback`).
- After `research/source-pack.md` exists, no resumed branch may discover new sources except through the one allowed targeted research follow-up from the sufficiency gate.

### `plan_approval_pending`

Four sub-paths, evaluated in order:

**Sub-path 1 — Explicit response in `$ARGUMENTS` (recovery / power-user).** If the text after `task_id` starts with one of the accepted keywords, handle immediately (same as `skills/memo/SKILL.md` Phase 4b):
- `approve` → `state.json.plan_approval.status = approved`, `final_plan_iteration = <current>`, `current_phase = research`. Print confirmation and continue inline to research (do NOT end turn).
- `edit: <text>` / `edit <text>` → check `max_plan_edit_iterations`. If exceeded, print "Edit limit reached, reply approve or cancel" and end turn. Otherwise: apply edits to `plan.md`, append iteration to `checkpoints/plan-approval.md`, update `state.json.plan_approval.iterations`, re-summarize the plan in chat, then run **Sub-path 3** to re-ask the verdict.
- `cancel` → update status to cancelled, print confirmation, end turn.

**Sub-path 2 — Last user message contains a valid keyword** (backward-compatible plain-text recovery). If `$ARGUMENTS` is bare but the user's previous chat message begins with `approve` / `edit:` / `edit ` / `cancel`, treat that message as the response and run the same handlers as Sub-path 1.

**Sub-path 3 — Bare `/continue <task_id>` and AskUserQuestion is available** (preferred interactive path). Run the same interactive plan approval as `skills/memo/SKILL.md` Phase 4a Path A:

1. Print a compact summary block (same rule as memo skill Phase 4a Path A step 1 — Cowork's chat renderer strips `<details>` HTML inconsistently, leaving the full plan as an unfoldable wall of text, so **do NOT inline plan.md content in chat**). Touch `plan.md` via `Read` (the artifact card from that tool call is the user's click-to-open affordance) and print:
   - A 2-4 sentence resume framing (task_id, classification, jurisdictions, issues count, researchers planned).
   - A 5-8 bullet "what's in the plan" preview so the user can decide without opening the file.
   - A plain-text reference to `plan.md` (no markdown link).

   Required format (verbatim structure — only the placeholders change):

   ````
   Resuming task `<task_id>`: <classification>, <jurisdictions>, <N> issues, <M> researchers.

   📄 Open full plan: plan.md (see artifact card above; full path: <state.json.rel_work_dir>/plan.md)

   **Plan at a glance:**
   - **Issues (<N>):** <short comma list of issue titles, ≤80 chars total>
   - **Researchers:** <set from config.researcher_set>
   - **Template:** `<selected_template_id>` (forced / bounded / open per mode)
   - **Doctrine:** <yes/no + 1-line reason>
   - **Sources:** <hierarchy short summary, 1 line>
   - **Critical missing facts:** <count, or "none flagged">
   - **Assumptions adopted:** <count>
   ````

   The bullet preview is mandatory; never inline the full plan text (Cowork rendering issue documented in memo SKILL.md Phase 4a Path A step 1). Users who want full audit text click the `plan.md` artifact card.

2. Call AskUserQuestion with three options:
   - `question`: "Research plan is ready. What's next?"
   - `header`: "Plan review" (≤12 chars).
   - `multiSelect`: false.
   - `options`:
     - "Approve plan" — Dispatch researchers as planned and proceed.
     - "Request edits" — Next prompt collects your edit instructions.
     - "Cancel task" — Stop the pipeline; work directory persists, resumable later.

3. Branch on answer:
   - **Approve** → set plan_approval.status=approved, current_phase=research, append `plan_approved` event. Continue inline to research dispatch (no end turn).
   - **Cancel** → set status=cancelled, current_phase=cancelled_by_user, print confirmation, end turn.
   - **Request edits** → check `max_plan_edit_iterations`. If exceeded, re-ask the same question without the Edit option. Otherwise, call a second AskUserQuestion:
     - `question`: "Which edits to the plan? Pick an option or enter your own text via 'Other'."
     - `header`: "Edits" (≤12 chars).
     - `options`:
       - "Add or remove jurisdiction" — Extend or narrow the geographic scope.
       - "Add or remove research issue" — Change which legal questions are analyzed.

     (No template-switch edit: template is bound to mode — Brief → executive-brief, Full → classical-memo. To change templates, cancel and rerun in the other mode.)

     If user picked a category, optionally narrow with one more AskUserQuestion (e.g. "Which jurisdiction?" with auto-Other for free text). If user picked "Other" with text, use that text verbatim.
     
     Apply edits to `plan.md`, append iteration to `checkpoints/plan-approval.md`, update `state.json.plan_approval.iterations`, then loop back to step 1 of Sub-path 3 (re-summarize updated plan, re-ask verdict).

**Sub-path 4 — Bare `/continue <task_id>` and AskUserQuestion is unavailable** (text fallback). Re-show the text prompt and end turn:

```
Resuming task `<task_id>`.

Research plan: plan.md (see artifact card above; full path: <state.json.rel_work_dir>/plan.md)

Review and confirm with one of:
- `/legal-memo-writer:continue <task_id> approve` — proceed as is
- `/legal-memo-writer:continue <task_id> edit: <instructions>` — apply edits
- `/legal-memo-writer:continue <task_id> cancel` — stop

The short plain-text replies `approve`, `edit: <instructions>`, and `cancel` may work in the same session, but explicit `/continue ...` is more reliable.
```

**Anti-loop guard:** if a user has typed `/legal-memo-writer:continue <task_id>` 3+ times in a row without sending approve/edit/cancel between them, print:
> I see several `/legal-memo-writer:continue` calls in a row without an explicit response. Please use one of: `/legal-memo-writer:continue <task_id> approve`, `/legal-memo-writer:continue <task_id> edit: <instructions>`, or `/legal-memo-writer:continue <task_id> cancel`.
And end turn.

### `research`

Read `state.json.dispatched_researchers` (set by memo Phase 5 BEFORE the parallel dispatch — subset of `config.researcher_set` filtered by plan's `Doctrine` flag, per Fix 6 candidate-vs-dispatched semantics). If the field is null/missing (legacy task pre-0.0.40), recompute: `dispatched = config.researcher_set` minus `["doctrinal"]` when plan says `Doctrine: no`. Write the recomputed list to `state.json.dispatched_researchers` so subsequent resumes don't redo this work.

Check which research files exist in `research/`. For each missing researcher in `dispatched_researchers`, re-dispatch via Agent tool **in parallel** and remind each researcher to follow the source-acquisition policy above. Wait for completion. Update `state.json.current_phase = research_sufficiency`. Continue to research-sufficiency branch.

### `intake_preliminary_research`

If `intake/fact-assumption-report.md` or `checkpoints/intake-questions.md` is missing, dispatch `fact-assumption-analyst`. Then set `current_phase = intake_questions_pending`, re-show `checkpoints/intake-questions.md`, and end turn.

### `intake_questions_pending`

Three sub-paths, evaluated in order:

**Sub-path 1 — Explicit response in `$ARGUMENTS` (recovery / power-user path).** If the text after `task_id` starts with one of the accepted keywords, handle as before:
- `answer:` / `answers:` → write the remaining text to `intake/user-facts.md`, set `intake.status = answered`, `intake.user_response = <raw>`, `current_phase = mode_pick_pending`, and continue inline to the `mode_pick_pending` branch (Phase 1.5 mode choice). Do NOT skip to `planning` — the mode pick is a hard gate.
- `proceed` / `assume` → write `intake/user-facts.md` with "User chose to proceed on default assumptions", set `intake.status = assumptions_accepted`, `assumptions_accepted = true`, `current_phase = mode_pick_pending`, and continue inline to the `mode_pick_pending` branch.
- `cancel` → set `current_phase = cancelled_by_user`, print confirmation, end turn.

**Sub-path 2 — Bare `/continue <task_id>` and `intake-questions.json` exists and is valid.** Two sub-cases, mirroring memo skill Phase 2a:

**Sub-path 2a — visualize available** (`state.json.config.visualize_enabled == true`). Run the same visualize elicitation flow as memo skill Phase 2a Path A:
1. Read both `checkpoints/intake-questions.json` (apply the same defensive sanitization documented in memo Phase 2a step 1a — header ≤12 chars, options 2-4, descriptions ≤200 chars) and `checkpoints/intake-questions.md`.
2. Build the elicitation data payload (letter-labeled options, merged must_answer + optional) per memo Phase 2a step 1b.
3. Render the elicitation widget via `<visualize_namespace>__show_widget` with title `"Intake questions — answer in chat below"`. Save snapshot to `$WORK_DIR/widgets/intake-elicitation.html`. Append `visualize_widget_rendered` event with `{"phase": "2a-elicitation-resume", ...}`.
4. Print the framing + answer instructions to chat (same `1A 2C` format as memo Phase 2a step 1d, with the resume framing "Resuming task `<task_id>`. Pick a letter per question in the card above.").
5. **End turn.** The next user chat message will be parsed in the `intake_questions_pending` branch above via Parser 1/3/4/5 (memo Phase 2b parsers).

**Sub-path 2b — visualize NOT available** (`state.json.config.visualize_enabled == false` OR namespace missing). Same as Sub-path 3 below — re-show the text prompt and end turn. Do NOT attempt an AskUserQuestion walk through the questions; production runs have shown that path to fail silently for multi-question payloads, which is exactly why memo Phase 2a moved off AskUserQuestion.

**Sub-path 3 — Bare `/continue <task_id>` and no valid `intake-questions.json` (legacy task / agent failure / corruption).** Re-show the text prompt and end turn:
```
Intake questions: intake-questions.md (see artifact card above; full path: <state.json.rel_work_dir>/checkpoints/intake-questions.md)

Reply with one of:
- `/legal-memo-writer:continue <task_id> answer: <your answers>`
- `/legal-memo-writer:continue <task_id> proceed`
- `/legal-memo-writer:continue <task_id> cancel`
```

### `mode_pick_pending`

The Phase 1.5 mode choice is a hard gate (per `skills/memo/references/pipeline-contract.md` and `skills/memo/SKILL.md` Phase 1.5). A task may be in `mode_pick_pending` either because intake just completed in this same session, or because /continue is resuming a task that was interrupted between intake and mode pick. /continue MUST NOT skip this gate to `planning`.

Execute `skills/memo/SKILL.md` Phase 1.5 inline:
1. Read `skills/memo/references/modes.md` for the canonical mode matrix and AskUserQuestion call shape.
2. If `state.json.config.visualize_enabled == true`, render the mode-comparison widget (per memo Phase 1.5 step 1b). If visualize is unavailable or the call throws, skip silently.
3. **MUST call AskUserQuestion** with two options (Brief / Full) using the descriptions from `modes.md`. Do NOT pre-fill the answer, do NOT interpret the original query as the answer, do NOT skip the gate based on intake content.
4. Record the answer: MERGE the resolved mode config into `state.json.config` (preserving any pre-existing `visualize_*` keys), set `state.json.mode = <chosen>`, and in the SAME atomic write set `state.json.current_phase = planning`. Append `mode_selected` event AND emit canonical audit events per `events-contract.md`:
   ```bash
   # Gate audit (the AskUserQuestion outcome)
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/log_event.py" \
     --workdir "$WORK_DIR" --event gate_answered --phase planning --actor continue-skill \
     --data '{"gate_name":"mode-pick","options_offered":["Brief","Full"],"chosen":"<chosen-label>","was_fallback":false,"fallback_reason":null}'

   # Phase transition (mode_pick_pending → planning, atomic with mode/config merge)
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/log_event.py" \
     --workdir "$WORK_DIR" --event phase_transition --phase planning --actor continue-skill \
     --data '{"from":"mode_pick_pending","to":"planning","reason":"mode_selected"}'
   ```
5. Print the standard Phase 1.5 Progress block (template in memo/SKILL.md Phase 1.5 step 5).
6. Continue inline to the `planning` branch below.

If `state.json.mode` is already non-null when /continue enters this branch (i.e. the previous session got past the AskUserQuestion but crashed before the atomic write completed and `current_phase` failed to advance), do NOT re-ask — verify `state.json.config` has the canonical shape via `scripts/validate_state.py`, set `current_phase = planning`, continue.

### `planning`

**Guard — must run first.** If `state.json.mode is None` when entering this branch, that means a prior session set `current_phase = planning` without completing Phase 1.5 (legacy bug pre-0.0.40). Atomically rewrite `current_phase = mode_pick_pending`, jump to the `mode_pick_pending` branch above, and continue from there. Never run Phase 3 with a null mode.

Execute `skills/memo/SKILL.md` Phase 3: read original query, intake report, user facts/assumptions, classify, choose template, write `plan.md`, initialize `checkpoints/plan-approval.md`, set `current_phase = plan_approval_pending`, and show the plan. End turn.

### `research_sufficiency`

If `research/research-sufficiency.json` is missing, dispatch `research-sufficiency-reviewer`. Read the JSON.

If verdict is `sufficient`, proceed to currency check. (No mode-driven override exists any more — the verdict is honoured verbatim.)

If verdict is `targeted_followup_needed`, check `state.json.attempts.research_followup` before doing anything:
- If `0`, atomically increment to `1`, set `attempts.research_followup_pending_review = true`, append `research_followup_started` to `events.jsonl`, re-dispatch the relevant researcher(s) once with targeted follow-up prompts, then re-run the sufficiency reviewer once and set `attempts.research_followup_pending_review = false`.
- If `>= 1` and `attempts.research_followup_pending_review = true`, do NOT re-dispatch follow-up on resume. Re-run `research-sufficiency-reviewer` once against the current research files, then set `attempts.research_followup_pending_review = false`.
- If `>= 1` and `attempts.research_followup_pending_review = false`, do NOT re-dispatch follow-up. Treat remaining gaps as either `insufficient_for_client_ready_memo` or explicit drafting warnings.

If verdict is `insufficient_for_client_ready_memo`, either fail with a clear reason or continue only with explicit drafting warnings recorded. Then run `currency-checker` if `research/currency-report.json` is missing: before dispatching it, set `current_phase = currency_check`; after it writes `research/currency-report.md` + `research/currency-report.json`, fall through to the `currency_check` branch's re-gate logic below.

### `currency_check`

Check if `research/currency-report.json` exists (canonical machine-readable view per `skills/memo/references/pipeline-contract.md` Phase 6.5 outputs). If missing, dispatch `currency-checker` via Agent tool, wait. After currency-checker has written both files:

**Re-gate sufficiency on currency invalidation** (memo Phase 6.5 contract). Read `research/currency-report.json`. If `len(currency.blocking) > 0` AND `state.json.attempts.sufficiency_regate == 0`:
1. Append `currency_invalidated_sources` event to `events.jsonl`.
2. Atomically: set `current_phase = research_sufficiency`, `attempts.sufficiency_regate = 1`, `attempts.research_followup_pending_review = false`.
3. Re-dispatch `research-sufficiency-reviewer` ONCE (pass `research/currency-report.json` explicitly).
4. Read the new sufficiency verdict, handle per the `research_sufficiency` branch above.
5. Then set `current_phase = source_pack` and continue.

Otherwise (no blocking sources, or re-gate already used), set `current_phase = source_pack` and continue.

### `source_pack`

If `research/source-pack.md` is missing, dispatch `source-pack-builder`. Then set `current_phase = source_review_pending` and continue inline to the source-review-pending branch (do NOT skip directly to drafting).

### `source_review_pending` (replaces v0.0.42 `heartbeat_pending`)

Re-show the source-review checkpoint per memo skill Phase 7.5 — `Read` the source-pack and currency-report files (artifact cards), print the 📋 source digest block, print the `continue` / `cancel` instructions, end turn.

**Legacy migration from v0.0.42 `heartbeat_pending`.** If `state.json.current_phase == "heartbeat_pending"` (a task created on v0.0.42 or earlier):
1. Atomically set `current_phase = source_review_pending`.
2. If `state.json.heartbeat_choice` field exists with any value, drop it (delete the key). Log `legacy_field_dropped` event with `{"field":"heartbeat_choice","value":<old_value>}`. The v0.0.43 flow does not branch on this field.
3. Append `legacy_phase_migrated` event with `{"from":"heartbeat_pending","to":"source_review_pending"}`.
4. Continue with the source-review-pending re-show.

**In-session resume (user replied at source-review).** If the latest user message is non-empty:
- Starts with `continue` (or `proceed` / `go` / `draft` / `yes` / `ok`, case-insensitive) → set `current_phase = drafting`, emit `gate_answered` event with `chosen: "continue"`, continue inline to the drafting branch.
- Starts with `cancel` (or `stop` / `abort` / `no`) → set `current_phase = cancelled_by_user`, emit `gate_answered` event with `chosen: "cancel"`, print stop message, end turn.
- Anything else → re-show the source-review checkpoint instructions, end turn.

### `drafting`

If `drafts/v1.md` does not exist, dispatch `memo-writer` via Agent tool to produce v1. Pass intake files, research files, research sufficiency, currency report, and source pack. Then set `current_phase = revision_loop`, `current_iteration = 1`, and continue to revision-loop branch. If `drafts/v1.md` already exists, only set `current_iteration = 1` when it is currently `0` or missing.

**Legacy compatibility.** Tasks resumed from v0.0.42 with `state.json.heartbeat_choice == "research_summary_only"` are migrated to the full-pipeline path silently (the research-summary mode was removed in v0.0.43). Log `legacy_mode_migrated` with `{"from":"research_summary_only","to":"continue_full"}`. The vestigial `templates/research-summary-only.md` stays on disk but no path leads to it.

### `revision_loop`

Read `current_iteration = N`. Check which reviewer outputs exist (`reviews/vN-<reviewer>.json`):

- If any reviewer JSON listed in `state.json.config.reviewer_list` is missing → dispatch missing reviewers in parallel via Agent tool (one per missing reviewer kind, using the kind→subagent_type mapping from the memo skill Phase 9 step 1).
- Before dispatching `revision-mediator`, validate the configured set with:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_review_json.py" \
    --workdir "<WORK_DIR>" \
    --iteration <N>
  ```
  The validator reads `state.json.config.reviewer_list` and validates ONLY those kinds. If `python3` is unavailable, try `python`. If invalid reviewers remain, re-dispatch only those reviewers once, after atomically incrementing `state.json.attempts.reviewer_json_retry["v<N>-<reviewer>"]` and appending `reviewer_json_retry_started` to `events.jsonl`. Validate again. If still invalid, run the same validator with `--write-failure-stubs`, then validate once more.
- If every valid JSON for kinds in `state.json.config.reviewer_list` exists but `reviews/vN-mediator.md` is missing → dispatch mediator.
- After mediator returns, validate `state.json` with `scripts/validate_state.py`. If invalid, re-dispatch mediator once with the validation errors; if still invalid, stop and surface "state.json corrupted; manual intervention required".
- If mediator already finished → auto-advance per verdict (v0.0.44+ — no AskUserQuestion). Mirror Phase 9 step 6 logic from `skills/memo/SKILL.md`:
  - Verdict = `approved_on_v<N>` → render milestone-5 tracker if enabled, advance to Phase 10.
  - Verdict = `needs_revision` AND `config.max_iterations > 1` AND N < `config.max_iterations` → write `revision_gate_choice = "continue"`, emit `gate_auto_advanced`, dispatch memo-writer for v<N+1>.
  - Verdict = `forced_exit_on_v<N>_with_remaining_issues` OR N == `config.max_iterations` → write `client_readiness_gate_choice = "continue"`, emit `gate_auto_advanced`, render milestone-5, advance to Phase 10. (No "Export as-is" option as of v0.0.44 — pipeline always runs client-readiness; the unresolved-blockers banner from mediator is already in fallback_banners[].)
- Legacy `revision_gate_choice` / `client_readiness_gate_choice` values from v0.0.43-and-earlier tasks (`continue` / `accepted_early` / `skip_polish`) are still read on resume: `continue` and `accepted_early` advance to Phase 10; the legacy `skip_polish` value is normalised to `continue` and a `legacy_value_migrated` event is logged (the skip-polish path is no longer reachable for new tasks).

Continue the loop per the `memo` skill Phase 9 logic.

### `client_readiness`

If `reviews/final-client-readiness.json` is missing, dispatch `client-readiness-reviewer` with the same expanded context as the `memo` skill: final draft, `state.json`, latest mediator report if present, intake files, `research/source-pack.md`, `research/research-sufficiency.json`, `research/currency-report.md`, and house style.

If verdict is `needs_final_polish`, auto-advance per `state.json.attempts.client_readiness_polish` (v0.0.44+ — no AskUserQuestion):
- If `config.client_polish_enabled == false` (Brief mode) → no polish. Set `final_status = manual_review_required_on_v<N>`, preserve blockers, proceed to export.
- If `attempts.client_readiness_polish < config.max_client_polish` (polish budget remains): write `polish_gate_choice = "apply"`, emit `gate_auto_advanced` with `gate_name: "polish"`, `chosen: "apply"`. Atomically increment counter, set `attempts.client_readiness_polish_pending_review = true`, dispatch memo-writer polish pass, re-run client-readiness reviewer. After re-run, set `attempts.client_readiness_polish_pending_review = false`. If verdict is still `needs_final_polish` and budget remains, loop.
- If `attempts.client_readiness_polish >= config.max_client_polish` (budget exhausted): set `final_status = manual_review_required_on_v<N>`, preserve reviewer `blocking_issues` in `state.json.client_readiness.blocking_issues` and `state.json.remaining_blocking_issues`, proceed to export with warning status.
- If `attempts.client_readiness_polish_pending_review == true` on entry (resume from interrupted polish): do NOT increment again, do NOT re-dispatch polish — re-run client-readiness reviewer once against `state.json.current_draft_path`, then set `attempts.client_readiness_polish_pending_review = false` and re-evaluate verdict from the top.
- Legacy `polish_gate_choice == "skip"` from v0.0.43-and-earlier tasks: respect it on resume (proceed to export with manual_review_required banner), but new tasks never write this value.

If verdict is `manual_review_required`, preserve the blockers in `state.json.client_readiness.blocking_issues` and `state.json.remaining_blocking_issues`, set `final_status = manual_review_required_on_v<N>`, and proceed to export with warning status. Set `current_phase = export`.

### `export`

Run the full docx export procedure documented in `memo/SKILL.md` Phase 11 — including the always-deliver.md fallback chain. Resume here MUST mirror the same three steps:

1. **Primary path** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/legal-memo-docx-render/scripts/md_to_docx.py --input "<work_dir>/drafts/v<N>.md" --output "<work_dir>/memo-<slug>.docx" --template-id <selected_template_id> --final-status <final_status> --state "<work_dir>/state.json" --language en` via Bash. The docx is written directly into `state.json.work_dir` (no staging, no copy).

2. **Pandoc fallback** (if step 1 fails) — `pandoc "<work_dir>/drafts/v<N>.md" -o "<work_dir>/memo-<slug>.docx"`. Pandoc is not guaranteed; expect failure if missing.

3. **Markdown delivery fallback** (if BOTH python and pandoc fail) — per `skills/memo/references/always-deliver.md` Phase 11 row. Source selection is deterministic to survive the no-polish path (where `v<N>-client-ready.md` does not exist):
   1. If `drafts/v<N>-client-ready.md` exists for the highest N → use it.
   2. Else read `state.json.current_draft_path` (always points at the latest `drafts/v<N>.md` after Phase 8/9) → use that.
   3. Else `ls drafts/v*.md` and pick the highest-N file as a last resort.
   - `cp "<resolved source>" "<work_dir>/memo-<slug>.md"`.
   - Update `state.json.final_docx_path` to the absolute path of the `.md` file (extension `.md`, not `.docx`).
   - Push banner `"docx export failed — markdown file delivered. Convert manually with pandoc or save-as docx."` into `state.json.fallback_banners[]` (dedupe).
   - Call `Read` on `<work_dir>/memo-<slug>.md` so Cowork inserts an artifact card.

4. **UX-visibility step** (on the success path of step 1 or step 2) — `Read` the docx (so Cowork registers an artifact card for the binary) AND write a `<work_dir>/memo-<slug>.md` markdown mirror with the final draft contents (Cowork reliably renders artifact cards for markdown).

5. Update `state.json`: `final_docx_path` (absolute path; `.docx` on success path, `.md` on markdown-delivery fallback), `final_status`, `current_phase = done`. Inline continue to the `done` branch.

Never leave the resume in a state where `current_phase = done` exists without a real file on disk — the validator enforces `Path(final_docx_path).is_file()` at `done`.

### `done`

Print summary of the completed task:
- `final_docx_path`
- Memo summary (3-5 sentences read from the final draft)
- Template used
- Status (approved, forced exit, or manual review required)
- Stats

End turn. Do NOT re-run the pipeline.

### `cancelled_by_user`

Print: "Task `<task_id>` was cancelled. To start a fresh task, use `/legal-memo-writer:memo`. To delete this working directory, remove the folder at <state.json.rel_work_dir>/."

End turn.

### `failed`

Print the failure reason from state.json (if recorded). Do NOT auto-retry — surface the error and let the user decide.

End turn.

## Hard constraints

- Same as `memo` skill: do not bypass the plan-review checkpoint, do not write state outside `<WORK_DIR>/`, do not fall back to generic WebSearch for primary sources.
- Idempotency: if a phase's outputs already exist, do not regenerate them blindly. Re-check `state.json` and the files before re-dispatching subagents.
- Use the shared validators before trusting reviewer JSONs or mediator-written state: `scripts/validate_review_json.py` and `scripts/validate_state.py`.
- Retry budgets in `state.json.attempts` are authoritative. Do not repeat research follow-up or client-readiness polish after their persisted counters are consumed.
- If `state.json` is corrupted (malformed JSON, missing required fields), do NOT attempt repair — print "state.json is corrupted; manual intervention required" and end turn.
