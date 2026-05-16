# Modes — Quick / Standard / Deep

Read this at Phase 1.5 of `skills/memo/SKILL.md` before calling AskUserQuestion. The user picks one of three modes; the choice rewrites `state.json.config` and changes how downstream phases behave.

## Modes overview

| Field | Quick | Standard (default) | Deep |
|---|---|---|---|
| `researcher_set` | `["statutory"]` | `["statutory", "case-law", "doctrinal"]` (doctrinal only if `Doctrine: yes` in plan) | same as Standard |
| `reviewer_list` | `["logic", "citations", "counterargument"]` | `["logic", "clarity", "style", "citations", "counterargument"]` | same as Standard |
| `max_iterations` | 1 | 3 | 3 |
| `targeted_followup_forced` | false | conditional on sufficiency verdict | true (force one targeted follow-up regardless of verdict) |
| `client_polish_enabled` | false | true (1 polish pass on `needs_final_polish`) | true (up to 2 polish passes) |
| `max_client_polish` | 0 | 1 | 2 |

## AskUserQuestion call shape

At Phase 1.5, after intake answers are recorded and `current_phase = planning` is set, call AskUserQuestion with this single question:

- `question`: "Какой режим пайплайна использовать?" (or "Which pipeline mode?" for EN sessions)
- `header`: "Mode"
- `multiSelect`: false
- `options`:
  - label: "Quick", description: "Statutory research only, 1 revision iteration with 3 reviewers, no client-readiness polish. Fastest delivery; best for low-stakes or preliminary checks."
  - label: "Standard", description: "Full 3-researcher set (statutory + case-law + doctrinal as needed), 3 iterations with 5 reviewers, client-readiness polish. Default for client-facing memos."
  - label: "Deep", description: "Standard plus one forced targeted-followup research pass and up to 2 client-readiness polish passes. For regulator-facing or high-risk memos."

The user's choice is the literal mode name. Auto-Other is enabled but should not be used here — if user picks Other, default to Standard and print a short note explaining the fallback.

## State.json updates after the answer

When mode is chosen, write:

```json
{
  "mode": "<quick|standard|deep>",
  "config": {
    "researcher_set": [...],
    "reviewer_list": [...],
    "max_iterations": <int>,
    "targeted_followup_forced": <bool>,
    "client_polish_enabled": <bool>,
    "max_client_polish": <int>
  }
}
```

Append event `mode_selected` to `events.jsonl` with the chosen mode and the resolved config.

Print a progress block immediately after:

```
**Progress — <task_id>**
- Current phase: `planning`
- Completed: Mode selected (`<mode>`)
- Next: Building research plan
- Notes: Config — <N> researchers, <max_iterations> iteration(s), <M> reviewers per iteration, client polish <on/off>
```

## How each downstream phase reads config

- **Phase 5 (parallel research)**: dispatch only the agents listed in `config.researcher_set`. If `case-law` is absent, do not dispatch `case-law-researcher`. If `doctrinal` is in the set but the plan says `Doctrine: no`, skip it anyway.
- **Phase 6 (sufficiency)**: if `config.targeted_followup_forced` is `true` and verdict came back `sufficient`, override to one follow-up cycle anyway, with prompts asking the relevant researcher to deepen the most contestable issue.
- **Phase 9 (revision loop)**: dispatch reviewers only from `config.reviewer_list`. Cap iterations at `config.max_iterations`. Mediator priority order from house style still applies; reviewers absent from the list contribute zero blocking issues.
- **Phase 10 (client-readiness)**: if `config.client_polish_enabled` is `false`, skip the polish pass entirely. On `needs_final_polish` verdict, proceed straight to manual-review status. If enabled, allow up to `config.max_client_polish` polish-then-re-review cycles before falling back.

## Mid-run mode escalation

If a fallback (per `always-deliver.md`) wants to upgrade the user from Standard → Deep mid-run, that requires a fresh AskUserQuestion gate. Do not silently rewrite `config`. The user must opt in.

Downgrade direction (Standard → Quick mid-run) is allowed silently only when triggered by the explicit Phase 7→8 heartbeat option "Switch to Quick mode now"; in that case rewrite `config` to Quick values and log `mode_downgraded` event.

## Why three modes (not a slider)

A three-option discrete choice gives the user enough control without parametric overload. Empirically, "how many reviewers" or "how many iterations" are not decisions a lawyer wants to make in dollars and minutes. They want "how thorough" framed as three named tiers tied to use case (preliminary check / client-facing / regulator-facing).
