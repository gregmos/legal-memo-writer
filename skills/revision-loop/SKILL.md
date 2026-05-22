---
name: revision-loop
description: Methodology for the mode-aware revision loop in the legal-memo-writer pipeline (3 reviewers in Brief mode, 5 in Full). Use when main session is in revision_loop phase or about to enter it from drafting.
---

# Revision loop methodology

Reference playbook for the main session when running the revision loop. The main session reads this skill before the revision-loop phase of the `memo` skill workflow. Worker subagents do **not** read this skill — they have their own focused system prompts.

## Roles in the loop

Up to five reviewer kinds; the active set is `state.json.config.reviewer_list` (3 in Brief: `logic`, `citations`, `counterarguments` — 5 in Full: all five). Reviewers run in parallel each iteration N.

**Two reviewer classes** (the difference matters because it sets which Agent prompts may carry research-file paths and which may not):

| Class | Reviewers | What they see |
|---|---|---|
| **Isolated** | `logic`, `clarity`, `style` | Only `drafts/vN.md`. No research files, no prior reviews, no state.json, no house-style. |
| **Augmented** | `citations` (citation-auditor), `counterarguments` (counterargument-reviewer) | `drafts/vN.md` PLUS research files + (for counterarguments) intake files. They have research access by design because their jobs — source grounding and contrary-authority discovery — cannot be done from the draft alone. |

Per-reviewer detail:
- **logic-reviewer** *(isolated)* — IRAC structure, logical coherence, inter-issue consistency. Reads: `drafts/vN.md` only. Model: Haiku.
- **clarity-reviewer** *(isolated, Full mode only)* — sentence length, jargon without explanation, accessibility for non-lawyer stakeholders. Reads: `drafts/vN.md` only. Model: Haiku.
- **style-reviewer** *(isolated, Full mode only)* — AI-tells, em-dash overuse, inflated symbolism, grammar. Reads: `drafts/vN.md` only. Model: Haiku.
- **citation-auditor** *(augmented)* — every normative/case/doctrine claim in the draft is grounded in `research/*.md` and `research/source-pack.md`; currency blocking issues respected. Reads: `drafts/vN.md` + research files + `research/raw/`. Model: Sonnet.
- **counterargument-reviewer** *(augmented)* — stress-tests overconfident conclusions, contrary authority, hidden assumptions, and client-risk attack vectors. Reads: `drafts/vN.md` + `research/source-pack.md` + `research/statutes.md` + `research/case-law.md` + `research/doctrine.md` (if exists) + intake files. Model: Sonnet.

After reviewers complete, **revision-mediator** (Opus) consolidates the configured review JSONs into a single actionable list and updates `state.json`.

## Dispatch pattern

In ONE message from the main session, issue one Agent tool call per reviewer kind in `state.json.config.reviewer_list` (parallel):

```
# Full — all five
Agent(subagent_type="logic-reviewer", prompt="Review drafts/vN.md ...")
Agent(subagent_type="clarity-reviewer", prompt="Review drafts/vN.md ...")
Agent(subagent_type="style-reviewer", prompt="Review drafts/vN.md ...")
Agent(subagent_type="citation-auditor", prompt="Audit drafts/vN.md against research/ and source-pack ...")
Agent(subagent_type="counterargument-reviewer", prompt="Stress-test drafts/vN.md against source-pack and intake assumptions ...")

# Brief — three only
Agent(subagent_type="logic-reviewer", prompt="...")
Agent(subagent_type="citation-auditor", prompt="...")
Agent(subagent_type="counterargument-reviewer", prompt="...")
```

Wait for all dispatched reviewers to return (tool calls block).

Then in a separate (sequential) call, dispatch the mediator:
```
Agent(subagent_type="revision-mediator", prompt="Consolidate reviews v<N> for task ...")
```

## JSON validation and retry

Each reviewer writes `reviews/vN-<reviewer>.json`. After dispatch, the main session checks:
- File exists.
- JSON is parseable.
- Required keys present: `reviewer`, `version_reviewed`, `overall_score`, `blocking_issues`, `nice_to_have`, `verdict`.

Use the shared validator instead of ad hoc inspection:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_review_json.py" \
  --workdir "<state.json.work_dir>" \
  --iteration <N>
```
Substitute `<state.json.work_dir>` with the resolved working-directory path (typically the user's output folder; no `${CLAUDE_PLUGIN_DATA}/work/` staging since v0.0.29). If `python3` is unavailable, try `python`.

If any reviewer's output fails validation:
1. Re-dispatch that single reviewer with the same prompt + a note "your previous response was not valid JSON; emit only JSON conforming to the schema".
2. If second attempt also fails, run the validator with `--write-failure-stubs` to create valid blocking failure stubs for the remaining invalid reviewers.
   Then proceed to the mediator. Do not let missing or malformed reviewer output count as approval.

Mediator treats reviewer failure stubs as blocking issues. A task can only be approved when every reviewer in `state.json.config.reviewer_list` has a valid JSON file AND returns `verdict = approved`.

## Mediator output

Mediator writes:
- `reviews/vN-mediator.md` — human-readable consolidated revision list with resolution explanations for conflicts.
- Updates `state.json`:
  - `iterations[N-1]` entry with reviewer summary scores and statuses.
  - `current_iteration` and `current_phase` per exit decision.

## Exit conditions

Mediator decides:
1. **Every reviewer in `state.json.config.reviewer_list` reports `verdict = approved` and zero `blocking_issues`** → `state.json.final_status = approved_on_v<N>`, `current_phase = client_readiness`. Loop ends.
2. **Blocking issues remain AND `current_iteration < state.json.config.max_iterations`** → `current_phase = revision_loop`, increment `current_iteration`. Main session dispatches `memo-writer` for v<N+1>.
3. **`current_iteration == state.json.config.max_iterations` AND blocking issues remain** → `final_status = forced_exit_on_v<N>_with_remaining_issues`, `current_phase = client_readiness`. Loop ends with warning.

## Reviewer isolation contract

The main session must enforce isolation through the Agent prompts:
- logic / clarity / style reviewers: pass ONLY the path to `drafts/vN.md`. Do NOT mention research files, changelog, previous reviews, or state.json. Their system prompts already restrict them, but Agent prompts should not leak extra context.
- citation-auditor: pass the path to `drafts/vN.md`, `research/source-pack.md`, and all `research/*.md` paths. Citation-auditor needs source grounding. Still do not pass previous reviews or changelog.
- counterargument-reviewer: pass `drafts/vN.md`, `research/source-pack.md`, and intake files. Do not pass previous reviews or changelog.
- Mediator: pass one review JSON path per reviewer in `state.json.config.reviewer_list` + state.json path + house-style skill path. If any reviewer failed validation, pass the failure stub path, not a missing path.

## Iteration ceiling

The iteration cap lives ONLY at `state.json.config.max_iterations` (Brief=1, Full=3 — resolved at Phase 1.5 from `skills/memo/references/modes.md`). After the cap is reached, force exit even if blockers remain — the docx warning banner alerts the user that manual review is needed.

## Edge cases

- **Reviewer takes too long** (>10 min): if observed, retry with a stricter "respond in ≤100 words" reminder. Persistent slow runs → switch reviewer model to Sonnet temporarily (not in v0.0.1 default).
- **Mediator returns invalid state.json update**: re-dispatch mediator once. Then surface the error and end turn with a "manual intervention required" message in the user output.
- **State validation**: after mediator returns, run `scripts/validate_state.py` against `state.json` before trusting `current_iteration`, `current_phase`, or `final_status`.
- **A reviewer marks the draft `approved` with high score but lists nice-to-have items**: nice-to-have are NEVER applied. Only blocking_issues drive the writer's next revision.
