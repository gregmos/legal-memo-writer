---
name: status
description: Show read-only status of a legal memo task by task_id, or list all tasks. Does not mutate state. Use only when explicitly invoked via /legal-memo-writer:status.
argument-hint: "[<task_id>] (omit to list all tasks)"
allowed-tools: Read, Bash
---

# legal-memo-writer / status skill

Read-only inspection of legal-memo-writer task state. **Never mutate state.json. Never dispatch worker subagents. Never run python scripts.** Only Read and Bash (for `ls`).

## Parse argument

Read `$ARGUMENTS`.

### Empty argument — list all tasks

1. `ls ${CLAUDE_PLUGIN_DATA}/work/` (Bash).
2. For each `memo-*` directory:
   - Read `state.json`.
   - Extract `task_id`, `current_phase`, `created_at`, `user_query` (first 100 chars), and `final_status` if set.
3. Print a table:
   ```
   | task_id                                            | phase                  | created             | query                            |
   |----------------------------------------------------|------------------------|---------------------|----------------------------------|
   | memo-2026-05-14T10-30-00-gdpr-biometrics-minors    | revision_loop          | 2026-05-14 10:30:00 | Can our product process biometr... |
   ```
4. End turn.

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
- Current iteration: <current_iteration> / <max_iterations>
- Current draft: <current_draft_path>

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
- Output docx: <final_docx_path or "not yet exported">

## Suggested next step
- If phase == intake_questions_pending → "Run `/legal-memo-writer:continue <task_id> answer: <facts>`, `/legal-memo-writer:continue <task_id> proceed`, or `/legal-memo-writer:continue <task_id> cancel`."
- If phase == plan_approval_pending → "Run `/legal-memo-writer:continue <task_id> approve`, `/legal-memo-writer:continue <task_id> edit: <instructions>`, or `/legal-memo-writer:continue <task_id> cancel`."
- If phase in {intake_preliminary_research, planning, research, research_sufficiency, currency_check, source_pack, drafting, revision_loop, client_readiness} → "Run `/legal-memo-writer:continue <task_id>` to resume."
- If phase == export → "Run `/legal-memo-writer:continue <task_id>` to finalize docx."
- If phase == done → "Task complete. Docx at `<final_docx_path>`."
- If phase == cancelled_by_user → "Task was cancelled. To start fresh: `/legal-memo-writer:memo`."
- If phase == failed → "Task failed. Inspect `${CLAUDE_PLUGIN_DATA}/work/<task_id>/` manually."
```

End turn.

## Hard constraints

- **Read-only.** Never call Write, Edit, or Agent. Never run scripts that modify state.
- If `state.json` malformed → print "state.json malformed; cannot parse" and the raw contents for the user.
- Do not auto-resume even if phase suggests it — surface info, let user decide.
