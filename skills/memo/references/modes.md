# Modes — Brief / Full

Read this at Phase 1.5 of `skills/memo/SKILL.md` before calling AskUserQuestion. The user picks one of two modes; the choice rewrites `state.json.config` and changes how downstream phases behave.

## Modes overview

| Field | Brief | Full |
|---|---|---|
| `researcher_set` | `["statutory"]` | `["statutory", "case-law", "doctrinal"]` (doctrinal only dispatched if `Doctrine: yes` in plan) |
| `reviewer_list` | `["logic", "citations", "counterarguments"]` | `["logic", "clarity", "style", "citations", "counterarguments"]` |
| `max_iterations` | 1 | 3 |
| `client_polish_enabled` | false | true |
| `max_client_polish` | 0 | 1 |
| `template_id` | `"executive-brief"` | `"classical-memo"` |

**Template binding.** Each mode hard-codes its template — Brief always produces an `executive-brief`, Full always produces a `classical-memo`. The classifier in Phase 3 does NOT pick the template; it reads `config.template_id` directly. If the user wants a different output shape, they cancel and rerun in the other mode.

**Brief length cap.** `executive-brief` carries a hard cap of 1200 words including footnotes. If research material genuinely cannot fit defensibly under the cap, the writer flags `length_overflow_recommendation: true` in the draft front-matter and the pipeline routes to `manual_review_required` with a recommendation to rerun in Full mode.

## AskUserQuestion call shape

At Phase 1.5, after intake answers are recorded and `current_phase = mode_pick_pending` is set (intake parsers in memo Phase 2b set this — `planning` is only reached AFTER the user has picked a mode and `state.json.mode` is non-null, atomically advanced in the same write as the mode/config merge), call AskUserQuestion with this single question:

- `question`: "Which pipeline mode?"
- `header`: "Mode"
- `multiSelect`: false
- `options`:
  - label: "Brief", description: "Short executive brief (~2-3 pages, 500-1200 words). Statutory research only, 1 revision iteration with 3 reviewers, no client polish. Fastest delivery; best for low-stakes or preliminary checks."
  - label: "Full", description: "Full memo (~5-8 pages, 3000-6000 words). 3-researcher set (statutory + case-law + doctrinal as needed), 3 iterations with 5 reviewers, 1 client-polish pass. Default for client-facing memos."

The user's choice is the literal mode name (lowercase: `brief` or `full`). Auto-Other is enabled but should not be used here — if user picks Other, default to Full and print a short note explaining the fallback.

## State.json updates after the answer

When mode is chosen, write:

```json
{
  "mode": "<brief|full>",
  "config": {
    "researcher_set": [...],
    "reviewer_list": [...],
    "max_iterations": <int>,
    "client_polish_enabled": <bool>,
    "max_client_polish": <int>,
    "template_id": "<executive-brief|classical-memo>"
  }
}
```

Append event `mode_selected` to `events.jsonl` with the chosen mode and the resolved config.

Print a plain-text Progress block immediately after (v3 format — see `references/progress-contract.md` §"Progress block format"):

```
**Progress — <task_id>**
- Current phase: `planning`
- Completed: Mode selected (`<mode>`)
- Next: Building research plan
- Notes: Config — <N> researchers, <max_iterations> iteration(s), <M> reviewers per iteration, client polish <on/off>, template `<template_id>`
```

Print this as a top-level assistant chat message. Do not include an `Artifacts:` field — file references in chat text are not clickable in Cowork; users get clickable file access via the artifact cards Cowork inserts automatically when you use `Read`/`Write`/`Edit` tools. (The widget HTML for Phase 1.5, if rendered, will have its own card from the visualize MCP — no need to mention it here.)

## How each downstream phase reads config

- **Phase 3 (classify & build plan)**: set `selected_template_id = config.template_id`. The classifier still produces `type`/`jurisdictions`/`doctrine_required`/`complexity` for context and to gate the doctrinal researcher dispatch, but it does NOT choose the template.
- **Phase 5 (parallel research)**: dispatch only the agents listed in `config.researcher_set`. If `case-law` is absent (Brief), do not dispatch `case-law-researcher`. If `doctrinal` is in the set but the plan says `Doctrine: no`, skip it anyway.
- **Phase 6 (sufficiency)**: read the sufficiency-reviewer verdict verbatim — no mode-driven override. `targeted_followup_needed` triggers the existing one-shot follow-up budget; `sufficient` proceeds directly.
- **Phase 8 (writing)**: writer reads `selected_template_id`. If it is `executive-brief`, the 1200-word cap is a hard limit; if the writer cannot fit defensible analysis under the cap, it MUST flag `length_overflow_recommendation` in the draft front-matter rather than silently overflow. For `classical-memo`, the length guidance in the template file is a target range, not a hard cap.
- **Phase 9 (revision loop)**: dispatch reviewers only from `config.reviewer_list`. Cap iterations at `config.max_iterations`. Mediator priority order from house style still applies; reviewers absent from the list contribute zero blocking issues.
- **Phase 10 (client-readiness)**: if `config.client_polish_enabled` is `false` (Brief), skip the polish pass entirely. On `needs_final_polish` verdict, proceed straight to manual-review status. If enabled (Full), allow up to `config.max_client_polish` polish-then-re-review cycles (currently 1) before falling back.

## Mid-run mode change

Mid-run mode changes are not supported. To switch modes, the user cancels the current task and reruns `/legal-memo-writer:memo "<query>"` from the start. The earlier infrastructure for Standard→Deep escalation and Standard/Deep→Quick downgrade has been removed alongside the three-mode split — with only two modes and a hard mode→template binding, an in-flight rewrite of `state.json.config` would invalidate too much downstream state (drafts already written, reviewers already returned) to be worth supporting.

## Why two modes (not a slider, not three)

The earlier three-mode pipeline (Quick / Standard / Deep) bundled three orthogonal axes — research depth, review thoroughness, and output format — into one knob. In practice the Quick→Standard step was a real change (1 vs 3 researchers, 3 vs 5 reviewers, 1 vs 3 iterations, polish off vs on) while Standard→Deep was cosmetic (one extra forced follow-up, one extra polish pass, two more templates allowed). Users could not predict the difference between Standard and Deep, and the forced follow-up in Deep mode actively overrode the sufficiency reviewer's `sufficient` verdict to do busywork.

Brief / Full reflects the actual decision the user faces: "do I want a quick preliminary read or a full client-facing memo?" Anything more granular is parametric tuning that lawyers don't want to make in dollars and minutes.
