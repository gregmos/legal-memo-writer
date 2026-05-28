# Visualize widget data payloads — schemas and notes

Canonical data-payload shapes for the four `visualize:show_widget` calls in the memo pipeline. The orchestrator builds these JSON objects from `state.json` and pipeline artifacts, then passes them to the widget generator per the cached `visualize:read_me` guidelines.

This document covers the **data payload** the orchestrator must build. The visual rendering rules (layout, color palette, accessibility, ≤size cap) live in the cached `visualize:read_me` output per module. The pre-flight check (`state.json.config.visualize_enabled`) for the memo pipeline widgets lives in `progress-tracker.md` (which also covers the 5-milestone tracker widget separate from the table below).

If `visualize_enabled == false` or the widget call throws, skip silently — every phase that uses these payloads has a documented graceful fallback in `SKILL.md`.

| § | Phase | Module | Size cap | Owner field for snapshot path |
|---|---|---|---|---|
| Elicitation | 2a | `elicitation` | ≤4KB JSON, ≤40KB HTML | `$WORK_DIR/widgets/intake-elicitation.html` |
| Mode mockup | 1.5 | `mockup` | ≤2KB JSON, ≤30KB HTML | `$WORK_DIR/widgets/phase15-mode-mockup.html` |
| Plan diagram | 4a | `diagram` | ≤2KB JSON, ≤40KB HTML | `$WORK_DIR/widgets/phase3-plan-diagram.html` |
| Final dashboard | 12 | `data_viz` | ≤2KB JSON, ≤30KB HTML | `$WORK_DIR/widgets/phase12-final-dashboard.html` |

## §Elicitation (Phase 2a)

Built from `checkpoints/intake-questions.json` after sanitization (header ≤12 chars, options 2..4, descriptions ≤200 chars — see SKILL.md Phase 2a step 1a for the sanitization rules). Letter-label each option (A/B/C/D in order) and merge must-answer + optional into a single ordered list with question numbers.

```json
{
  "task_id": "<id>",
  "framing": "<2-sentence summary of what the triage found>",
  "must_answer_count": <N>,
  "optional_count": <M>,
  "questions": [
    {"n": 1, "section": "must_answer", "text": "<question>", "options": [{"letter": "A", "label": "...", "description": "..."}, ...], "rationale": "<rationale_md if any>"},
    ...,
    {"n": N+1, "section": "optional", "text": "<question>", "options": [...], "rationale": "..."},
    ...
  ],
  "default_assumptions_if_skipped": ["...", "..."]
}
```

`show_widget` call arguments:
- `title`: `"Intake questions — answer in chat below"` (or RU equivalent).
- `loading_messages`: `["Preparing intake card...", "Rendering questions..."]`.
- `widget_code`: the generated HTML (≤40KB, no JavaScript callbacks).

Emit `visualize_widget_rendered` event with `{"phase": "2a-elicitation", "module": "elicitation", "question_count": <N+M>}`.

## §Sufficiency follow-up (Phase 6.6, v0.6.3+)

Reuses the §Elicitation HTML layout and `elicitation` module guidelines verbatim — same widget code shape, different data source. Built from `state.json.sufficiency_followup.questions` (mirror of `research-sufficiency.json.blocking_gaps[].followup_question` entries for `target_agent: "main-session"` gaps), after the same sanitization rules as §Elicitation (header ≤12 chars, options 2..4, descriptions ≤200 chars). Letter-label each option (A/B/C/D in order).

Difference from §Elicitation: there is no `must_answer` / `optional` partition (all follow-up questions are conceptually must-answer — they were generated specifically because the sufficiency reviewer flagged them as blocking — but skipping is permitted by accepting the `default_assumption_if_skipped`, same as intake). All questions render in a single `must_answer` section with `n` starting at 1.

```json
{
  "task_id": "<id>",
  "framing": "Research surfaced <N> fact(s) the analysis still needs from you before drafting can proceed. Skipping a question applies a conservative default assumption.",
  "must_answer_count": <N>,
  "optional_count": 0,
  "questions": [
    {"n": 1, "section": "must_answer", "text": "<question>", "options": [{"letter": "A", "label": "...", "description": "..."}, ...], "rationale": "<rationale_md>"},
    ...
  ],
  "default_assumptions_if_skipped": ["<default for Q1>", "<default for Q2>", ...]
}
```

`show_widget` call arguments:
- `title`: `"Research follow-up — answer in chat below"`.
- `loading_messages`: `["Preparing follow-up card...", "Rendering questions..."]`.
- `widget_code`: the generated HTML (≤40KB, no JavaScript callbacks; the SAME widget HTML template as §Elicitation — only the data payload differs).

Snapshot path: `$WORK_DIR/widgets/phase66-followup-elicitation.html` (overwritten on resume re-show via continue/SKILL.md §`research_sufficiency_followup_pending` Sub-path 3).

Emit `visualize_widget_rendered` event with `{"phase": "6.6-followup", "module": "elicitation", "question_count": <N>}`. On resume re-show, use `"phase": "6.6-followup-resume"` instead.

User reply parsing follows the same syntax as §Elicitation: `1A 2C 3:my free text` (letter answer per question, with `<n>:custom text` escape for free-form). The `proceed` shortcut accepts ALL `default_assumption_if_skipped` values at once. The `cancel` shortcut stops the pipeline cleanly. See `skills/memo/SKILL.md` Phase 6 Branch B6a framing-message template for the exact instructions printed alongside the widget.

## §Mode mockup (Phase 1.5)

Compact 2-column comparison of Brief / Full modes. Source of truth for the values: `references/modes.md` mode matrix — keep this payload in sync with that file when modes evolve.

```json
{
  "modes": [
    {"id": "brief", "label": "Brief", "pages": "2-3", "words": "500-1200", "researchers": ["statutory"], "reviewers": ["logic", "citations", "counterarg"], "iterations": 1, "polish": false, "template": "executive-brief", "use_case": "Preliminary check / low-stakes"},
    {"id": "full", "label": "Full", "pages": "5-8", "words": "3000-6000", "researchers": ["statutory", "case-law", "doctrinal"], "reviewers": ["logic", "clarity", "style", "citations", "counterarg"], "iterations": 3, "polish": true, "template": "classical-memo", "use_case": "Client-facing default"}
  ]
}
```

Rendering note (per cached `mockup` module): each column has a header with mode label and "~N pages" hero, a mini memo-structure silhouette beneath, a stats block (researchers / reviewers / iterations / polish), and a one-line use-case caption. Neutral palette with one accent color per mode. No JavaScript.

`show_widget` call arguments:
- `title`: `"Choose pipeline mode"`.
- `loading_messages`: `["Preparing mode comparison...", "Rendering Brief / Full cards..."]`.
- `widget_code`: generated HTML (≤30KB).

Emit `visualize_widget_rendered` event with `{"phase": "1.5", "module": "mockup", "size_bytes": <html length>}`.

## §Plan diagram (Phase 4a)

Built from `plan.md` + `state.json.classification` after the plan summary block has been printed. Keep issue titles tight (≤60 chars); fall back to plain enumeration if `plan.md` doesn't expose clean titles.

```json
{
  "central_question": "<query summary, ≤120 chars>",
  "classification": {"type": "<type>", "complexity": "<low|medium|high>", "jurisdictions": ["EU", "DE", "..."]},
  "issues": [
    {"id": 1, "title": "<short title>", "jurisdictions": ["EU"], "researchers": ["statutory", "case-law"], "source_types": ["regulation", "EDPB guidance"]}
  ],
  "template_id": "<selected_template_id>",
  "researcher_set": ["statutory", "case-law", "doctrinal"]
}
```

Layout (per cached `diagram` module): tree/radial diagram. Central node = `central_question`; first ring = issues; per-issue sub-branches for jurisdictions, researchers, and source types. Color-code issues by complexity (low = neutral, medium = amber, high = warm red — use accessible palette). Include a small legend mapping researcher icons to labels. No JavaScript.

`show_widget` call arguments:
- `title`: `"Research plan diagram"`.
- `loading_messages`: `["Mapping issues and jurisdictions...", "Rendering research plan..."]`.
- `widget_code`: generated HTML (≤40KB).

Emit `visualize_widget_rendered` event with `{"phase": "3", "module": "diagram"}`.

## §Final dashboard (Phase 12)

Built from `state.json` + source pack. Source counts: read `research/source-pack.md` and count sources by category (statute / case-law / doctrine / soft-law). Final word count: `wc -w "<current_draft_path>"` (Bash; or read file and split on whitespace). Duration: `(now - state.json.created_at)` in minutes.

```json
{
  "task_id": "<id>",
  "mode": "brief|full",
  "template_id": "executive-brief|classical-memo",
  "final_word_count": <int — count words in the final draft file>,
  "source_breakdown": {"statute": <int>, "case-law": <int>, "doctrine": <int>, "soft-law": <int>},
  "iterations": <int — state.json.current_iteration>,
  "final_status": "approved|manual_review_required|forced_exit",
  "blocking_issues_remaining": <int>,
  "duration_minutes": <int — (now - state.json.created_at) in minutes>,
  "artifacts": [
    {"label": "Final docx", "path": "<final_docx_path>"},
    {"label": "Markdown draft", "path": "<current_draft_path>"},
    {"label": "Source pack", "path": "research/source-pack.md"},
    {"label": "Mediator brief", "path": "reviews/v<N>-mediator.md"},
    {"label": "Working directory", "path": "<state.json.work_dir>"}
  ]
}
```

Layout (per cached `data_viz` module): top row of KPI cards (mode, template, final word count, iterations, final status with color-coded chip), a small bar/donut chart for source breakdown by category, and a vertical list of artifact paths labelled clearly. Status color: green for `approved`, amber for `forced_exit`, red for `manual_review_required`. No JavaScript.

`show_widget` call arguments:
- `title`: `"Memo delivered — <task_id>"` (or RU equivalent).
- `loading_messages`: `["Compiling deliverables...", "Rendering final dashboard..."]`.
- `widget_code`: generated HTML (≤30KB).

Emit `visualize_widget_rendered` event with `{"phase": "12", "module": "data_viz"}`.
