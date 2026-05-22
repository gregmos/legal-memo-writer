# Pipeline progress tracker — milestone widget

This is the reusable spec for the 5 milestone-tracker widgets rendered during a `/memo` run. SKILL.md references this file from 5 places (after each major phase-group). Do not render the tracker anywhere else.

## When to render

Render exactly 5 times per run, at the END of each phase-group boundary listed below. NEVER render per text-Progress (would flood the chat) and NEVER render inside the revision loop per iteration.

| Milestone | Render AFTER | Insertion point in SKILL.md |
|---|---|---|
| 1 — Setup done | Phase 1.5 completes — `state.json.mode` is set, `config` is merged with the mode-canonical values, `current_phase = planning` is written atomically with the mode write — and BEFORE Phase 3 classifier work starts. Step numbering in `modes.md` and `continue/SKILL.md` may differ; the trigger is the atomic mode/phase write, not a particular step index. | `Phase 1.5` |
| 2 — Intake done | Phase 2b sets `current_phase = mode_pick_pending` (or Phase 2a Path A "answers recorded" branch) — `planning` is reached only AFTER Phase 1.5 mode pick advances the phase atomically with the mode write | `Phase 2a/2b` |
| 3 — Plan approved | Phase 4a Path A "Approve picked" branch (and Phase 4b reactivation `approve` branch) | `Phase 4a/4b` |
| 4 — Research done | Phase 7 after `source-pack-builder` returns and `research/source-pack.md` is written | `Phase 7` |
| 5 — Revision done | Phase 9 after mediator approved or forced-exit, before transitioning to Phase 10 client-readiness | `Phase 9` |

Phase 12 final dashboard widget (already in SKILL.md Phase 12) plays the role of the Delivery milestone — do not add a 6th tracker.

## Pre-flight check (every call)

Before rendering:

1. If `state.json.config.visualize_enabled != true` → SKIP the entire widget step; continue with normal text-Progress flow. Do not log anything.
2. If `state.json.cache.visualize_guidelines` is empty → call `<visualize_namespace>__read_me` with `{ "modules": ["diagram", "mockup", "data_viz"], "platform": "desktop" }` and persist the response. (This is usually populated by an earlier widget in the run; only the first widget call needs to fetch.)

## Data payload

Build a compact JSON object (≤2KB). Status of each phase is `completed | current | future`. For the current render, set `status` per the milestone definition:

```json
{
  "task_id": "<state.json.task_id>",
  "current_phase_index": <int 1-12>,
  "current_group": "Setup | Intake | Plan | Research | Drafting+Revision | Delivery",
  "phases": [
    {"id": "1", "label": "Init", "group": "Setup", "status": "completed"},
    {"id": "1.5", "label": "Mode", "group": "Setup", "status": "completed"},
    {"id": "2a", "label": "Intake", "group": "Intake", "status": "..."},
    {"id": "3", "label": "Classify", "group": "Plan", "status": "..."},
    {"id": "4", "label": "Approve", "group": "Plan", "status": "..."},
    {"id": "5", "label": "Research", "group": "Research", "status": "..."},
    {"id": "6", "label": "Sufficiency", "group": "Research", "status": "..."},
    {"id": "7", "label": "Source-pack", "group": "Research", "status": "..."},
    {"id": "8", "label": "Draft v1", "group": "Drafting+Revision", "status": "..."},
    {"id": "9", "label": "Revise", "group": "Drafting+Revision", "status": "..."},
    {"id": "10", "label": "Polish", "group": "Delivery", "status": "..."},
    {"id": "11", "label": "Export", "group": "Delivery", "status": "..."},
    {"id": "12", "label": "Summary", "group": "Delivery", "status": "..."}
  ],
  "stat_line": "<1-2 short stats from current group, see table below>"
}
```

### Per-milestone status map and stat_line

| Milestone | `current_phase_index` | `current_group` | All status assignments | Example `stat_line` |
|---|---|---|---|---|
| 1 — Setup done | 2 | Intake | `1, 1.5` = completed; `2a` = current; everything else = future | `Mode: <mode> · template: <template_id> · researchers: <count>` |
| 2 — Intake done | 3 | Plan | `1, 1.5, 2a` = completed; `3` = current; rest = future | `<N> must-answer recorded · <M> optional answered/skipped · assumptions: <count>` |
| 3 — Plan approved | 5 | Research | `1, 1.5, 2a, 3, 4` = completed; `5` = current; rest = future | `<N> issues · <M> jurisdictions · researchers queued: <list>` |
| 4 — Research done | 8 | Drafting+Revision | `1..7` = completed; `8` = current; rest = future | `<N> statutes · <M> cases · <K> doctrine · source-pack ready` |
| 5 — Revision done | 10 | Delivery | `1..9` = completed; `10` = current; `11, 12` = future. Exception: in Brief mode (`config.client_polish_enabled == false`), set `10` = completed and `11` = current. | `Final version: v<N> · status: <approved/forced_exit/manual_review> · blockers remaining: <count>` |

If a phase that's normally in the pipeline was skipped (e.g. doctrinal-researcher skipped because plan said `Doctrine: no`), keep it in the array but mark it `completed` so the visual chain stays unbroken. Note that Phase 7.5 in v0.0.43+ is the **source-review checkpoint** (text-parsed gate, replaces the v0.0.42 heartbeat) — it is always present, never skipped.

## Widget rendering

HTML/SVG generation rules (follow cached `diagram` module guidelines from visualize:read_me; if visualize doesn't expose explicit horizontal-pipeline pattern, render raw HTML/SVG inline):

- **Layout:** 13 phase-boxes in a single horizontal row (12 phases + small spacer between groups). Adaptive width; if container narrows, allow 2-row wrap with break at group boundary.
- **Group brackets:** thin horizontal line above each group with the group label centered above its boxes.
- **Box dimensions:** ~64-80px wide, ~48-56px tall. Inside: phase id (e.g. "1.5") on top in small mono font, label below in slightly larger sans-serif.
- **Status styling:**
  - `completed` — soft green fill (`#d8f3dc` light theme / `#1e3a2e` dark theme acceptable; let visualize guidelines pick), checkmark icon overlay top-right of box, dark text.
  - `current` — accent color fill (visualize guidelines pick — typically a saturated blue/orange), bolder border (2px), lightning icon overlay, optional CSS `animation: pulse 2s infinite` on the box border (visual only, no JS).
  - `future` — light gray outline, no fill, light-gray text, no icon.
- **Below the pipeline:** one summary line in slightly larger text — `**Progress: <X>/12 phases · <current_group>**` — followed on the next line by the `stat_line` value in regular text.
- **Total height:** keep ≤150px so the widget doesn't dominate chat scrollback.
- **No JavaScript** that calls back to the harness. CSS animations OK. ResizeObserver inside the iframe handles auto-sizing.

## Call sequence

```
1. Compute data payload per milestone status map above.
2. Generate HTML/SVG (≤30KB) per cached diagram guidelines.
3. Save snapshot to `work/<task_id>/widgets/progress-<NN>-<milestone-name>.html`
   where NN ∈ {01, 02, 03, 04, 05} and milestone-name ∈
   {setup-done, intake-done, plan-approved, research-done, revision-done}.
4. Call `<visualize_namespace>__show_widget` with:
   - `title`: "Pipeline progress: <current_group>" (or RU equivalent matching state.json.language).
   - `loading_messages`: ["Updating pipeline tracker...", "Rendering progress..."].
   - `widget_code`: the generated HTML.
5. If the call throws, log a `visualize_call_failed` event with `{ "milestone": "<NN>", "error": "<message>" }` and continue silently. Do not retry; do not block the pipeline.
6. On success, append `visualize_widget_rendered` event with
   `{ "phase": "milestone-<NN>", "module": "diagram", "size_bytes": <len(widget_code)> }`.
7. Continue inline to the next phase action — never end-turn just because the widget rendered.
```

## Hard rules

- **Never replace text Progress with widgets.** Text `Progress —` blocks (per `progress-contract.md` §"Required progress updates — checklist") MUST still print on every documented phase-transition. Widgets supplement, not substitute.
- **Never render per-revision-iteration.** Inside the Phase 9 loop (which can run up to 3 iterations), only text Progress prints. Milestone-5 fires once at loop exit.
- **Never render in Path B if AskUserQuestion was unavailable to the host.** Path B is the text-fallback path for hosts without rich UI; widgets there make no sense. Phase 2b reactivation `approve` and Phase 4b `approve` branches do still render widgets — those branches are reactivation of an originally interactive session, not Path B host-fallback.
- **Never render two consecutive widgets without intervening text.** If a milestone is reached immediately after another widget (e.g. final dashboard right after milestone-5 in some forced-exit paths), make sure the text Progress block prints between them so the chat has rhythm.
