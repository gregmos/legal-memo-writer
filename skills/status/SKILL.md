---
name: status
description: Show read-only status of a legal memo task by task_id, or list all tasks. Does not mutate state. Use only when explicitly invoked via /legal-memo-writer:status.
argument-hint: "[<task_id>] (omit to list all tasks)"
disable-model-invocation: true
allowed-tools: Read, Bash
---

# legal-memo-writer / status skill

Read-only inspection of legal-memo-writer task state. **Never mutate state.json. Never dispatch worker subagents. Never run python scripts.** Only Read and Bash (for `ls`).

## Output format — file references via Cowork artifact cards

This skill is read-only. To give the user clickable access to files, **call the `Read` tool on each file you want to surface** — Cowork's UI inserts an artifact card above your next message for any Read tool call, which is the user's clickable affordance. Then print plain-text paths in the report body so the user knows where things live on disk.

Path display in chat text uses `state.json.rel_work_dir` (canonical CWD-relative path field set by `skills/memo/SKILL.md` Phase 1 Task setup). If a legacy task is missing this field, compute it on the fly via:

```bash
REL_WORK_DIR=$(realpath --relative-to="$(pwd)" "$WORK_DIR" 2>/dev/null \
  || python3 -c "import os.path,sys; print(os.path.relpath(sys.argv[1]))" "$WORK_DIR" 2>/dev/null \
  || python  -c "import os.path,sys; print(os.path.relpath(sys.argv[1]))" "$WORK_DIR" 2>/dev/null \
  || echo "$WORK_DIR")
```

(This skill is read-only — do NOT write the recomputed value back to state.json; just use it inline for the chat output.)

**Do not wrap file paths in markdown link syntax.** Cowork does not render relative or absolute paths as clickable file references inside chat text — clickability comes from the `Read` tool's artifact cards. Print all paths as plain text and rely on the Read calls for click access.

## Parse argument

Read `$ARGUMENTS`.

### Empty argument — list all tasks

1. Scan the four canonical output-folder candidates (same resolution order as `skills/continue/SKILL.md` Task discovery): `$CLAUDE_PLUGIN_OPTION_OUTPUT_FOLDER`, `$LEGAL_MEMO_OUTPUT_FOLDER`, `$HOME/Documents/legal-memos`, `outputs/legal-memo-work`. For each parent that exists, run `ls "$parent"/memo-* 2>/dev/null` and collect unique `task_id` directories (a task_id appearing in two parents is deduped, but record the resolved parent path per task).
2. For each found `memo-*` directory:
   - Read `state.json`.
   - Extract `task_id`, `current_phase`, `created_at`, `user_query` (first 100 chars), `final_status` if set, and `rel_work_dir` (compute if absent).
3. For each found task, call `Read` on `<resolved_path>/state.json` — Cowork will insert an artifact card so the user can click to inspect each one.
4. Then print a plain-text table summarizing what was read:
   ```
   | task_id                                          | phase                  | created             | query                                | path                          |
   |--------------------------------------------------|------------------------|---------------------|--------------------------------------|-------------------------------|
   | memo-2026-05-14T10-30-00-gdpr-biometrics-minors  | revision_loop          | 2026-05-14 10:30:00 | Can our product process biometr...   | <rel_work_dir>/                |
   ```

   The path column shows `state.json.rel_work_dir` as plain text — not a markdown link. Users get clickable access via the Read artifact cards inserted above this message.
5. End turn.

### Non-empty argument — single task report

Validate the task_id exists. If not, print "task_id `<arg>` not found" and end.

Read `state.json` and produce a human-readable report:

```
# Task: <task_id>

## Basic info
- Created: <created_at>
- Language: <language>
- Query: <user_query>

## Classification
- Type: <classification.type>
- Jurisdictions: <classification.jurisdictions>
- Doctrine required: <classification.doctrine_required>
- Complexity: <classification.estimated_complexity>
- Template: <classification.selected_template_id>

## Plan approval
- Intake status: <intake.status>
- Intake assumptions accepted: <intake.assumptions_accepted>
- Final iteration: <plan_approval.final_plan_iteration>
- Edit iterations recorded: <len(plan_approval.iterations)>
- Latest user response: <last iteration user_response>

## Pipeline state
- Current phase: <current_phase>
- Current iteration: <current_iteration> / <config.max_iterations>
- Current draft: <basename of current_draft_path> at <state.json.rel_work_dir>/<relative path inside work dir>, or "none yet" if current_draft_path is null. Before printing this line, call `Read` on the draft so Cowork inserts an artifact card for it.

## Revision iterations (if any)
For each entry in state.iterations:
- vN: logic <score>/blocking, clarity <score>/blocking, style <score>/blocking, citations <score>/blocking, counterarguments <score>/blocking → mediator: <status>

## Client readiness
- Verdict: <client_readiness.verdict or "not yet reviewed">
- Polish attempted: <client_readiness.polish_attempted or attempts.client_readiness_polish > 0>

## Retry budgets
- Research follow-up used: <attempts.research_followup or 0> / 1
- Research follow-up pending review: <attempts.research_followup_pending_review or false>
- Client-readiness polish used: <attempts.client_readiness_polish or 0> / 1
- Client-readiness polish pending review: <attempts.client_readiness_polish_pending_review or false>
- Reviewer JSON retries: <attempts.reviewer_json_retry or {}>

## Final
- Status: <final_status or "pending">
- Remaining blocking issues: <len(remaining_blocking_issues or [])>
- Output artifact: print `<basename of final_docx_path>` at `<state.json.rel_work_dir>/<basename of final_docx_path>` (the basename may end in `.docx` on the success path OR `.md` if Phase 11 fell back to delivering the markdown — derive the extension from `final_docx_path` itself, do NOT assume `.docx`). Print "not yet exported" if `final_docx_path` is null. If the file exists, call `Read` on it first so Cowork inserts an artifact card.

## Suggested next step
- If phase == intake_questions_pending → "Run `/legal-memo-writer:continue <task_id> answer: <facts>`, `/legal-memo-writer:continue <task_id> proceed`, or `/legal-memo-writer:continue <task_id> cancel`."
- If phase == plan_approval_pending → "Run `/legal-memo-writer:continue <task_id> approve`, `/legal-memo-writer:continue <task_id> edit: <instructions>`, or `/legal-memo-writer:continue <task_id> cancel`."
- If phase == source_review_pending → "Run `/legal-memo-writer:continue <task_id> continue` to draft, or `/legal-memo-writer:continue <task_id> cancel` to stop."
- If phase in {intake_preliminary_research, planning, research, research_sufficiency, currency_check, source_pack, heartbeat_pending (legacy v0.0.42, migrated to source_review_pending on resume), drafting, revision_loop, client_readiness} → "Run `/legal-memo-writer:continue <task_id>` to resume."
- If phase == export → "Run `/legal-memo-writer:continue <task_id>` to finalize docx."
- If phase == done → "Task complete. Final artifact at <state.json.rel_work_dir>/<basename of final_docx_path> (extension may be .docx on success path or .md on markdown-fallback path — derive from final_docx_path). See the Read artifact card above for click access."
- If phase == cancelled_by_user → "Task was cancelled. To start fresh: `/legal-memo-writer:memo`."
- If phase == failed → "Task failed. Inspect <state.json.rel_work_dir>/ manually in the Cowork file viewer."
```

End turn.

## Hard constraints

- **Read-only.** Never call Write, Edit, or Agent. Never run scripts that modify state.
- If `state.json` malformed → print "state.json malformed; cannot parse" and the raw contents for the user.
- Do not auto-resume even if phase suggests it — surface info, let user decide.
