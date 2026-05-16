---
name: continue
description: Resume an interrupted legal memo task. Use only when explicitly invoked via /legal-memo-writer:continue with the task_id, optionally followed by one of answer, proceed, approve, cancel, or edit.
argument-hint: "<task_id> [answer: <facts>|proceed|approve|cancel|edit: <instructions>]"
allowed-tools: Read, Write, Edit, Bash, Task, AskUserQuestion
---

# legal-memo-writer / continue skill

You are the main session resuming an interrupted legal memo task. This is the **explicit recovery path** when automatic reentry on the `memo` skill did not pick up the previous state (closed tab, new session, long pause).

## Parse argument

Read `$ARGUMENTS`. Parse it as:
- first whitespace-delimited token → `task_id` (the slug of the working directory in `${CLAUDE_PLUGIN_DATA}/work/`);
- remaining text, if any → explicit intake or plan-review response (`answer: <facts>`, `proceed`, `approve`, `cancel`, or `edit: <instructions>`).

If `$ARGUMENTS` is empty:
1. List all directories in `${CLAUDE_PLUGIN_DATA}/work/` (Bash `ls`).
2. For each, read `state.json` and print `task_id | current_phase | created_at | user_query (first 100 chars)`.
3. Ask the user to re-invoke with `/legal-memo-writer:continue <task_id>`.
4. End turn.

If `task_id` is non-empty but the directory or `state.json` does not exist:
1. Print "task_id `<arg>` not found".
2. List available task_ids as above.
3. End turn.

## Resume by phase

Read `${CLAUDE_PLUGIN_DATA}/work/<task_id>/state.json`. Branch on `current_phase`:

Before executing the phase branch, print a concise resume progress update:
```markdown
**Progress — <task_id>**
- Current phase: `<current_phase>`
- Resuming from: `/legal-memo-writer:continue`
- Next: <what this invocation will do>
- Artifacts: <key existing paths for this phase>
```

After each resumed phase completes a material action, follow the same progress contract as `skills/memo/SKILL.md`: print current phase, completed action, next action, key artifact paths, and any verdict/blocker counts. Do not paste full research files or full drafts.

## Source acquisition strategy

Follow the same source-acquisition strategy as `skills/memo/SKILL.md` on every resumed branch:
- Legal Data Hunter and CourtListener are the bundled MCPs.
- Legal Data Hunter is the default retrieval layer for broad multi-jurisdictional legislation, case law, and doctrine.
- CourtListener is the default retrieval layer for US case law, PACER/RECAP dockets, citation networks, case status, and citation verification.
- Generic WebSearch is prohibited for primary law and allowed only in `doctrinal-researcher` under its authority filters.
- After `research/source-pack.md` exists, no resumed branch may discover new sources except through the one allowed targeted research follow-up from the sufficiency gate.

### `plan_approval_pending`

Four sub-paths, evaluated in order:

**Sub-path 1 — Explicit response in `$ARGUMENTS` (recovery / power-user).** If the text after `task_id` starts with one of the accepted keywords, handle immediately (same as `skills/memo/SKILL.md` Phase 4b):
- `approve` → `state.json.plan_approval.status = approved`, `final_plan_iteration = <current>`, `current_phase = research`. Print confirmation and continue inline to research (do NOT end turn).
- `edit: <text>` / `edit <text>` / `правки: <text>` → check `max_plan_edit_iterations`. If exceeded, print "Edit limit reached, reply approve or cancel" and end turn. Otherwise: apply edits to `plan.md`, append iteration to `checkpoints/plan-approval.md`, update `state.json.plan_approval.iterations`, re-summarize the plan in chat, then run **Sub-path 3** to re-ask the verdict.
- `cancel` / `отмена` → update status to cancelled, print confirmation, end turn.

**Sub-path 2 — Last user message contains a valid keyword** (backward-compatible plain-text recovery). If `$ARGUMENTS` is bare but the user's previous chat message begins with `approve` / `edit:` / `edit ` / `правки:` / `cancel` / `отмена`, treat that message as the response and run the same handlers as Sub-path 1.

**Sub-path 3 — Bare `/continue <task_id>` and AskUserQuestion is available** (preferred interactive path). Run the same interactive plan approval as `skills/memo/SKILL.md` Phase 4a Path A:

1. Print a 2-4 sentence resume framing (task_id, classification, jurisdictions, issues count, researchers planned), then embed the **full content of the task's `plan.md` inside a collapsible `<details>` block** so the user can click to expand. Below the block, reference the file path as fallback. Same format as `skills/memo/SKILL.md` Phase 4a Path A step 1:

   ````
   Возобновление задачи `<task_id>`: <classification>, <jurisdictions>, <N> issues, <M> researchers.

   <details>
   <summary>📄 Полный план — нажмите, чтобы развернуть</summary>

   <FULL TEXT of plan.md copied verbatim>

   </details>

   Файл: `${CLAUDE_PLUGIN_DATA}/work/<task_id>/plan.md`
   ````

   The collapsible block is mandatory; never just point to the file path without inlining the content.

2. Call AskUserQuestion with three options:
   - `question`: "План ресёрча готов. Что делаем?"
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
     - `question`: "Какие правки в план? Выберите вариант или введите свой текст через 'Other'."
     - `header`: "Edits" (≤12 chars).
     - `options`:
       - "Add or remove jurisdiction" — Extend or narrow the geographic scope.
       - "Add or remove research issue" — Change which legal questions are analyzed.
       - "Switch template or scope" — Change between classical-memo / executive-brief / risk-assessment / regulatory-analysis / cross-jurisdictional.
     
     If user picked a category, optionally narrow with one more AskUserQuestion (e.g. "Which jurisdiction?" with auto-Other for free text). If user picked "Other" with text, use that text verbatim.
     
     Apply edits to `plan.md`, append iteration to `checkpoints/plan-approval.md`, update `state.json.plan_approval.iterations`, then loop back to step 1 of Sub-path 3 (re-summarize updated plan, re-ask verdict).

**Sub-path 4 — Bare `/continue <task_id>` and AskUserQuestion is unavailable** (text fallback). Re-show the text prompt and end turn:

```
Возобновление задачи `<task_id>`.

План ресёрча: `${CLAUDE_PLUGIN_DATA}/work/<task_id>/plan.md`

Прочтите и подтвердите одним из вариантов:
- `/legal-memo-writer:continue <task_id> approve` — продолжить как есть
- `/legal-memo-writer:continue <task_id> edit: <инструкции>` — внести правки
- `/legal-memo-writer:continue <task_id> cancel` — остановить

Короткие plain-text ответы `approve`, `edit: <инструкции>` и `cancel` могут сработать в той же сессии, но explicit `/continue ...` надёжнее.
```

**Anti-loop guard:** if a user has typed `/legal-memo-writer:continue <task_id>` 3+ times in a row without sending approve/edit/cancel between them, print:
> Вижу несколько подряд вызовов `/legal-memo-writer:continue` без явного ответа. Пожалуйста, используйте один из форматов: `/legal-memo-writer:continue <task_id> approve`, `/legal-memo-writer:continue <task_id> edit: <инструкции>` или `/legal-memo-writer:continue <task_id> cancel`.
And end turn.

### `research`

Check which research files exist in `research/`. For each missing researcher per the plan (`statutory`, `case-law`, `doctrinal` if doctrine_required), re-dispatch via Agent tool **in parallel** and remind each researcher to follow the source-acquisition policy above. Wait for completion. Update `state.json.current_phase = research_sufficiency`. Continue to research-sufficiency branch.

### `intake_preliminary_research`

If `intake/fact-assumption-report.md` or `checkpoints/intake-questions.md` is missing, dispatch `fact-assumption-analyst`. Then set `current_phase = intake_questions_pending`, re-show `checkpoints/intake-questions.md`, and end turn.

### `intake_questions_pending`

Three sub-paths, evaluated in order:

**Sub-path 1 — Explicit response in `$ARGUMENTS` (recovery / power-user path).** If the text after `task_id` starts with one of the accepted keywords, handle as before:
- `answer:` / `answers:` / `ответ:` / `ответы:` → write the remaining text to `intake/user-facts.md`, set `intake.status = answered`, `intake.user_response = <raw>`, `current_phase = planning`, and continue inline to planning.
- `proceed` / `assume` / `по assumptions` / `по допущениям` → write `intake/user-facts.md` with "User chose to proceed on default assumptions", set `intake.status = assumptions_accepted`, `assumptions_accepted = true`, `current_phase = planning`, and continue.
- `cancel` / `отмена` → set `current_phase = cancelled_by_user`, print confirmation, end turn.

**Sub-path 2 — Bare `/continue <task_id>` and `intake-questions.json` exists.** Run the same AskUserQuestion-based interactive flow as `skills/memo/SKILL.md` Phase 2a Path A:
1. Read both `checkpoints/intake-questions.json` and `checkpoints/intake-questions.md`. Print a brief one-paragraph framing in chat ("Resuming intake for `<task_id>`. Asking the must-answer questions inline now.") and reference the .md path for full rationale.
2. Walk `must_answer` in chunks of 4 via AskUserQuestion. Capture answers, including any "Other" free text.
3. Ask one yes/no AskUserQuestion: `Answer optional questions` vs `Skip and proceed`.
4. If user chose to answer optionals, walk `optional` in chunks of 4. Otherwise record `default_assumptions_if_skipped` as the assumed answer set.
5. Write `intake/user-facts.md` (same Q/A shape as memo Phase 2a Path A) and a compact JSON to `state.json.intake.user_response`. Set `intake.status = answered` (or `assumptions_accepted` if optionals were skipped with defaults), `current_phase = planning`. Append `intake_completed` to `events.jsonl`.
6. Print a progress update, **then continue inline to planning** — no end-turn.

**Sub-path 3 — Bare `/continue <task_id>` and no valid `intake-questions.json` (fallback).** Re-show the text prompt and end turn:
```
Вопросы intake: `${CLAUDE_PLUGIN_DATA}/work/<task_id>/checkpoints/intake-questions.md`

Ответьте:
- `/legal-memo-writer:continue <task_id> answer: <ответы>`
- `/legal-memo-writer:continue <task_id> proceed`
- `/legal-memo-writer:continue <task_id> cancel`
```

### `planning`

Execute `skills/memo/SKILL.md` Phase 3: read original query, intake report, user facts/assumptions, classify, choose template, write `plan.md`, initialize `checkpoints/plan-approval.md`, set `current_phase = plan_approval_pending`, and show the plan. End turn.

### `research_sufficiency`

If `research/research-sufficiency.json` is missing, dispatch `research-sufficiency-reviewer`. If verdict is `targeted_followup_needed`, check `state.json.attempts.research_followup` before doing anything:
- If `0`, atomically increment to `1`, set `attempts.research_followup_pending_review = true`, append `research_followup_started` to `events.jsonl`, re-dispatch the relevant researcher(s) once with targeted follow-up prompts, then re-run the sufficiency reviewer once and set `attempts.research_followup_pending_review = false`.
- If `>= 1` and `attempts.research_followup_pending_review = true`, do NOT re-dispatch follow-up on resume. Re-run `research-sufficiency-reviewer` once against the current research files, then set `attempts.research_followup_pending_review = false`.
- If `>= 1` and `attempts.research_followup_pending_review = false`, do NOT re-dispatch follow-up. Treat remaining gaps as either `insufficient_for_client_ready_memo` or explicit drafting warnings.

If verdict is `insufficient_for_client_ready_memo`, either fail with a clear reason or continue only with explicit drafting warnings recorded. Then run `currency-checker` if `research/currency-report.md` is missing: before dispatching it, set `current_phase = currency_check`; after it writes `research/currency-report.md`, set `current_phase = source_pack` and continue.

### `currency_check`

Check if `research/currency-report.md` exists. If yes, set `current_phase = source_pack` and continue. If no, dispatch `currency-checker` via Agent tool, wait, then continue.

### `source_pack`

If `research/source-pack.md` is missing, dispatch `source-pack-builder`. Then set `current_phase = drafting` and continue.

### `drafting`

If `drafts/v1.md` does not exist, dispatch `memo-writer` via Agent tool to produce v1. Pass intake files, research files, research sufficiency, currency report, and source pack. Then set `current_phase = revision_loop`, `current_iteration = 1`, and continue to revision-loop branch. If `drafts/v1.md` already exists, only set `current_iteration = 1` when it is currently `0` or missing.

### `revision_loop`

Read `current_iteration = N`. Check which reviewer outputs exist (`reviews/vN-<reviewer>.json`):

- If any of the five reviewer JSONs missing → dispatch missing reviewers in parallel via Agent tool.
- Before dispatching `revision-mediator`, validate all five review files with:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_review_json.py" \
    --workdir "${CLAUDE_PLUGIN_DATA}/work/<task_id>" \
    --iteration <N>
  ```
  If `python3` is unavailable, try `python`. If invalid reviewers remain, re-dispatch only those reviewers once, after atomically incrementing `state.json.attempts.reviewer_json_retry["v<N>-<reviewer>"]` and appending `reviewer_json_retry_started` to `events.jsonl`. Validate again. If still invalid, run the same validator with `--write-failure-stubs`, then validate once more.
- If all five valid JSON files exist but `reviews/vN-mediator.md` missing → dispatch mediator.
- After mediator returns, validate `state.json` with `scripts/validate_state.py`. If invalid, re-dispatch mediator once with the validation errors; if still invalid, stop and surface "state.json corrupted; manual intervention required".
- If mediator already finished and `state.json.revision_gate_choice` is missing for this iteration → the user is resuming at an end-of-iteration gate (or forced-exit gate) that hasn't been answered yet. Run the same Phase 9 step 6 logic from `skills/memo/SKILL.md`:
  - If verdict = `approved_on_v<N>` → no gate, jump to Phase 10.
  - If verdict = `needs_revision` AND `config.max_iterations > 1` AND N < max_iterations → run step 6b AskUserQuestion gate (Continue iter N+1 / Accept v<N>).
  - If verdict = `forced_exit_on_v<N>_with_remaining_issues` OR N == max_iterations → run step 6c AskUserQuestion gate (Continue to client-readiness / Export as-is now).
  - Branch per user answer exactly as documented in `memo` SKILL Phase 9 step 6.
- If mediator already finished AND `state.json.revision_gate_choice` is set → re-read state.json, follow the recorded choice (continue to next iteration or proceed to client-readiness or export).

Continue the loop per the `memo` skill Phase 9 logic.

### `client_readiness`

If `reviews/final-client-readiness.json` is missing, dispatch `client-readiness-reviewer` with the same expanded context as the `memo` skill: final draft, `state.json`, latest mediator report if present, intake files, `research/source-pack.md`, `research/research-sufficiency.json`, `research/currency-report.md`, and house style.

If verdict is `needs_final_polish`, check `state.json.attempts.client_readiness_polish` AND `state.json.polish_gate_choice`:
- If `config.client_polish_enabled == false` (Quick mode) → no gate, no polish. Set `final_status = manual_review_required_on_v<N>`, preserve blockers, proceed to export.
- If `attempts.client_readiness_polish == 0` AND `polish_gate_choice` is missing → user is resuming at the pre-polish gate. Run the same Phase 10 pre-polish gate logic from `skills/memo/SKILL.md`: AskUserQuestion "Apply polish pass / Export as-is", then branch per answer.
- If `polish_gate_choice == "apply"` AND `attempts.client_readiness_polish == 0` → execute polish: atomically increment to `1`, set `attempts.client_readiness_polish_pending_review = true`, append `client_readiness_polish_started` to `events.jsonl`, dispatch `memo-writer` once for final polish, and re-run client-readiness reviewer once. After the re-run, set `attempts.client_readiness_polish_pending_review = false`.
- If `polish_gate_choice == "skip"` → no polish. Set `final_status = manual_review_required_on_v<N>`, preserve blockers, proceed to export.
- If `attempts.client_readiness_polish >= 1` and `attempts.client_readiness_polish_pending_review == true`, do NOT mark manual review yet. Re-run client-readiness reviewer once against `state.json.current_draft_path`, then set `attempts.client_readiness_polish_pending_review = false`.
- If `attempts.client_readiness_polish >= 1` and `attempts.client_readiness_polish_pending_review == false`, or the post-polish client-readiness review is still not ready, set `final_status = manual_review_required_on_v<N>`, preserve reviewer `blocking_issues` in `state.json.client_readiness.blocking_issues` and `state.json.remaining_blocking_issues`, and proceed to export with warning status.

If verdict is `manual_review_required`, preserve the blockers in `state.json.client_readiness.blocking_issues` and `state.json.remaining_blocking_issues`, set `final_status = manual_review_required_on_v<N>`, and proceed to export with warning status. Set `current_phase = export`.

### `export`

Run the docx export procedure (same as `memo` skill export phase): python3 md_to_docx.py via Bash, then copy to user output folder, then update state.

### `done`

Print summary of the completed task:
- `final_docx_path`
- Memo summary (3-5 sentences read from the final draft)
- Template used
- Status (approved, forced exit, or manual review required)
- Stats

End turn. Do NOT re-run the pipeline.

### `cancelled_by_user`

Print: "Task `<task_id>` was cancelled. To start a fresh task, use `/legal-memo-writer:memo`. To delete this working directory, remove `${CLAUDE_PLUGIN_DATA}/work/<task_id>/`."

End turn.

### `failed`

Print the failure reason from state.json (if recorded). Do NOT auto-retry — surface the error and let the user decide.

End turn.

## Hard constraints

- Same as `memo` skill: do not bypass the plan-review checkpoint, do not write state outside `${CLAUDE_PLUGIN_DATA}/work/<task_id>/`, do not fall back to generic WebSearch for primary sources.
- Idempotency: if a phase's outputs already exist, do not regenerate them blindly. Re-check `state.json` and the files before re-dispatching subagents.
- Use the shared validators before trusting reviewer JSONs or mediator-written state: `scripts/validate_review_json.py` and `scripts/validate_state.py`.
- Retry budgets in `state.json.attempts` are authoritative. Do not repeat research follow-up or client-readiness polish after their persisted counters are consumed.
- If `state.json` is corrupted (malformed JSON, missing required fields), do NOT attempt repair — print "state.json is corrupted; manual intervention required" and end turn.
