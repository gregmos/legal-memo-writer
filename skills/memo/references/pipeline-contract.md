# Pipeline contract

Single source of truth for the memoforge runtime. All other docs (README, `skills/memo/SKILL.md`, `skills/continue/SKILL.md`, `lib/revision-loop.md`, `skills/memo/references/modes.md`, `skills/memo/references/always-deliver.md`, `skills/memo/state-schema.md`, agent prompts) cite this file as canonical instead of restating. If those docs ever appear to diverge from this file, **this file wins** — file a follow-up to bring the diverging doc back in sync.

Last revised: 2026-05-20 (0.0.40).

---

## Phase table

For each phase: who owns it, what state fields it requires to be set already, what artifacts it consumes, what artifacts it produces, what state fields it writes, what tools it may use, what phase it transitions to next, what mode-branches exist, what gates exist.

The phase name in column 1 is the literal `state.json.current_phase` value.

| Phase | Owner | Requires (state) | Inputs (files) | Tools allowed | Writes (state) | Outputs (files) | Next phase | Mode branches | Gates |
|-------|-------|-------|--------|--------|---------|---------|------|--------|-----|
| `intake_preliminary_research` | memo Phase 1 | (write-once from $ARGUMENTS) | none | Read, Write, Bash, MCP (LDH, CourtListener), WebFetch, WebSearch (discovery), AskUserQuestion, TodoWrite, mark_chapter | task_id, work_dir, rel_work_dir, output_folder, mode=null, config={}, fallback_banners=[], …all Phase 1 fields (heartbeat_choice removed in v0.0.43) | `state.json`, `events.jsonl`, `intake/fact-assumption-report.md`, `checkpoints/intake-questions.{md,json}` | `intake_questions_pending` | no | none |
| `intake_questions_pending` | memo Phase 2a-c | intake fields | `checkpoints/intake-questions.json` | AskUserQuestion (Path A) or text (Path B); Read, Write | `intake.status="answered"\|"assumptions_accepted"`, `intake.user_response` | `intake/intake-answers.md` | `mode_pick_pending` | no | AskUserQuestion (Path A) |
| `mode_pick_pending` | memo Phase 1.5 | intake done | none | AskUserQuestion, Read, Write, Bash, visualize widgets (optional) | `mode`, `config` (MERGED with existing config — preserves visualize_*) | `state.json`, `$WORK_DIR/widgets/phase15-mode-mockup.html` (optional) | `planning` | Brief → executive-brief; Full → classical-memo (direct binding via `config.template_id`) | AskUserQuestion (Mode) — **hard gate**: must run before any `planning` work. /continue must NOT skip this when resuming a task with `mode=null`. |
| `planning` | memo Phase 3 | mode, config | intake + research, classification template | classify-internal logic + Read/Write + AskUserQuestion (plan approval) | `classification.{type,jurisdictions,doctrine_required,estimated_complexity,selected_template_id}` | `plan.md`, `$WORK_DIR/widgets/phase3-plan-diagram.html` (optional) | `plan_approval_pending` | `selected_template_id = config.template_id` (direct copy, no classifier branching) | none |
| `plan_approval_pending` | memo Phase 4a-b | classification, plan.md | `plan.md` | AskUserQuestion (Path A) or text (Path B); Read, Write | `plan_approval.status="approved"\|"cancelled"\|"pending"`, plan_approval.iterations | `state.json` | `research` | no | AskUserQuestion (Plan approval) |
| `research` | memo Phase 5 | plan_approval.status=approved | `plan.md`, intake | Researcher subagents inherit MCP (LDH, CourtListener), WebFetch, WebSearch (discovery), Read, Write | `dispatched_researchers` (subset of `config.researcher_set` actually invoked — doctrinal skipped when plan `Doctrine: no`) | `research/statutes.md`, `research/case-law.md`, `research/doctrine.md` (per `dispatched_researchers`) | `research_sufficiency` | researcher_set varies by mode; doctrinal conditional on plan `Doctrine` flag | none |
| `research_sufficiency` | memo Phase 6 | research files | research files | research-sufficiency-reviewer subagent | `attempts.research_followup`, `attempts.research_followup_pending_review`, `attempts.sufficiency_regate` | `research/research-sufficiency.json` | `currency_check` (next) or `research` (if follow-up needed) | no mode-driven override — verdict honoured verbatim | sufficiency verdict |
| `currency_check` | memo Phase 6.5 | sufficiency done | research files | currency-checker subagent | `attempts.sufficiency_regate` (if re-gate fires) | `research/currency-report.md` (human view), `research/currency-report.json` (machine view — canonical for downstream readers) | `research_sufficiency` (re-gate, if `currency-report.json.blocking` non-empty AND `attempts.sufficiency_regate == 0`) OR `source_pack` | no | currency blocking issues; bounded re-gate via `attempts.sufficiency_regate` (max 1) |
| `source_pack` | memo Phase 7 | currency report | research files + currency report | source-pack-builder subagent | none | `research/source-pack.md` (and per the freeze contract, NO later agent discovers new sources) | `source_review_pending` | no | source-pack freeze |
| `source_review_pending` | memo Phase 7.5 (v0.0.43+) | source pack | source pack + currency report | Read (artifact cards), text-parse on resume | none (no AskUserQuestion — text-parsed `continue` / `cancel`) | `state.json` | `drafting` (on `continue`) OR `cancelled_by_user` (on `cancel`) | end-of-turn flush mechanism; legacy `heartbeat_pending` migrates here on resume | text reply (`continue` / `cancel`) — assistant turn ENDS explicitly here so Cowork flushes chat (issues #26805/#29773 family) |
| `drafting` | memo Phase 8 | source-review confirmation | intake + research + sufficiency + currency + source-pack | memo-writer subagent (Read, Write, Edit) | `current_draft_path="drafts/v1.md"`, `current_iteration=1` | `drafts/v1.md`, `changelog.md`, optional `$WORK_DIR/widgets/progress-04-research-done.html` | `revision_loop` | full pipeline path only (research-summary mode was removed in v0.0.43) | none |
| `revision_loop` | memo Phase 9 | mode, config, current_draft_path, current_iteration | `drafts/v<N>.md` + research files | reviewer subagents (per `config.reviewer_list`) + revision-mediator subagent + scripts/validate_review_json.py + scripts/validate_state.py | `iterations[]`, `current_iteration`, `final_status`, `revision_gate_choice` (auto-advanced) | `reviews/v<N>-{logic,clarity,style,citations,counterarguments}.json` (only kinds in `reviewer_list`), `reviews/v<N>-mediator.md`, optional `$WORK_DIR/widgets/progress-05-revision-done.html` | `client_readiness` (after exit) | Brief = 3 reviewers, 1 iter; Full = 5 reviewers, up to 3 iters | **none — auto-advance per mediator verdict (v0.0.44+).** Former 6b iteration gate and 6c forced-exit gate were removed; pipeline always loops on `needs_revision` with budget and always advances to client-readiness on `approved` or `forced_exit`. |
| `client_readiness` | memo Phase 10 | final_status from revision_loop | final draft | client-readiness-reviewer subagent + (if config.client_polish_enabled) memo-writer polish pass | `client_readiness.{verdict,polish_attempted,blocking_issues}`, `attempts.client_readiness_polish`, `polish_gate_choice` (auto-advanced) | `reviews/final-client-readiness.json` | `export` | Brief skips polish (config.client_polish_enabled=false); Full allows 1 polish pass | **none — auto-advance per reviewer verdict (v0.0.44+).** Former pre-polish gate removed; pipeline always applies polish when enabled and verdict needs it, up to `max_client_polish`. |
| `export` | memo Phase 11 | final_status set | `drafts/v<N>.md`, `state.json` | lib/docx-render/scripts/md_to_docx.py + Read | `final_docx_path`, `current_phase="done"` | `<state.json.work_dir>/memo-<slug>.docx` (writes directly into work_dir — NO copy step) | `done` | Brief → executive-brief docx; Full → classical-memo docx; banner injected from `fallback_banners[]` and `final_status`. (Legacy `research-summary-only` template path was removed in v0.0.43.) | none |
| `done` | terminal | export complete | none | none | none | none | n/a | n/a | n/a |
| `failed`, `cancelled_by_user` | terminal error states | varies | varies | none | none | none | n/a | n/a | n/a |

## §WebSearch — canonical policy

**WebSearch is permitted as a DISCOVERY tool only**, in `statutory-researcher`, `case-law-researcher`, `currency-checker`, and `doctrinal-researcher`. Discovery means finding CELEX numbers, docket identifiers, canonical portal URLs, news of amendments / repeals / follow-on judgments.

**A WebSearch result MUST NEVER be cited as the source of a legal claim.** Citations always come from MCP retrieval or from WebFetch against a canonical issuing-body portal that was either discovered via WebSearch or supplied by MCP.

**`doctrinal-researcher` exception:** doctrinal is the only researcher that may CITE WebFetch results from non-issuing-body sources — official regulator guidance, peer-reviewed academic/legal journals, SSRN-style repositories, and authoritative soft-law sources. The other three researchers must convert WebSearch findings into canonical citations via MCP or WebFetch on issuing-body portals.

**`fact-assumption-analyst` also inherits the WebSearch tool surface** (per the Tool inheritance table below — it omits `tools:` in its frontmatter and so inherits the entire main-session set). Its WebSearch use is **constrained to preliminary triage** — identifying potentially-relevant jurisdictions, naming probable acts/regulators, surfacing missing facts. It MUST NOT cite WebSearch results as legal sources in `fact-assumption-report.md`; the intake report is advisory only, and primary citations come from researchers in Phase 5. The §WebSearch whitelist of "four researchers" is about CITATION authority — fact-assumption-analyst is also permitted to USE WebSearch for triage, but never to cite it.

**MCP failure modes — two distinct fallback paths** (full table in `skills/memo/references/always-deliver.md`):

- *MCP unavailable* (not authenticated / not connected) → WebFetch against known official portals or URLs returned by previous MCP calls; if no canonical URL is reachable, document the gap explicitly in the source pack rather than fabricating.
- *MCP rate-limited / 5xx* → one retry with the same query, then WebFetch against the canonical URL discovered via WebSearch; log `mcp_ratelimit_fallback` event (this is the canonical name — agents emit it, memo skill Phase 5 greps for it, always-deliver.md table cites it) and surface the partial-research banner via `fallback_banners[]`.

**Source-pack freeze:** after `research/source-pack.md` is built, no later writer/reviewer/auditor may discover new sources. Remaining gaps go through the one allowed Phase 6 targeted follow-up or become manual-review warnings.

## §State schema — canonical reference

See `skills/memo/state-schema.md`. The fields below are required at Phase 1 initialisation; phase-aware required fields are enforced by `scripts/validate_state.py` (see §Validators below).

**Always required from Phase 1:**
- `task_id`, `user_query`, `created_at`, `language` (always `"en"`).
- `work_dir`, `rel_work_dir`, `output_folder`.
- `mode` (null until Phase 1.5).
- `config` (initialised to `{}`; visualize precheck populates `visualize_enabled` / `visualize_namespace`; Phase 1.5 MERGES mode config into existing object, preserving visualize fields).
- (`heartbeat_choice` was removed in v0.0.43 — Phase 7.5 is now the text-parsed source-review checkpoint; new state.json does not initialize this field.)
- `revision_gate_choice`, `client_readiness_gate_choice`, `polish_gate_choice` (all null until their gate fires).
- `fallback_banners: []`.
- `classification`, `intake`, `plan_approval`, `current_phase`, `current_iteration`, `max_plan_edit_iterations`, `max_intake_iterations`, `exit_threshold_score`.
- `current_draft_path`, `iterations[]`, `client_readiness`, `final_status`, `final_docx_path`, `attempts`, `remaining_blocking_issues`, `events_path`.

**Required to be populated by `planning` onward:**
- `mode ∈ {brief, full}`.
- `config.{researcher_set, reviewer_list, max_iterations, client_polish_enabled, max_client_polish, template_id}`.

**Required to be populated by `research_sufficiency` onward:**
- `dispatched_researchers: string[]` — written by memo Phase 5 after the parallel Agent dispatch. Subset of `config.researcher_set` filtered by the plan's Doctrine flag (doctrinal omitted if plan says `Doctrine: no`). The `phase5_dispatch` event records BOTH `candidate` (= `config.researcher_set`) and `dispatched` (= this field). The "malformed dispatch" check compares the number of Agent tool calls in the dispatch message against `len(dispatched_researchers)`, NOT `len(researcher_set)` — a Doctrine: no skip is legitimate and must not flag malformed.

**Required to be populated by `done`:**
- `final_docx_path`: absolute path. Equal to `<work_dir>/memo-<slug>.docx` after a successful Phase 11 export, or `<work_dir>/memo-<slug>.md` if Phase 11 fell back to delivering the markdown (per `always-deliver.md`). Validator enforces `is_file()` at `done`.

**Single source of truth for max_iterations:** `state.json.config.max_iterations` only. There is NO top-level `max_iterations` field. The validator rejects state files that include one.

**Canonical reviewer-kind names (plural):** `logic`, `clarity`, `style`, `citations`, `counterarguments`. Always the plural form `counterarguments` — the validator rejects the singular `counterargument`.

## §Tool inheritance

The memo skill's frontmatter `allowed-tools` defines the maximum tool surface that subagents can inherit. As of 0.0.39:

```
allowed-tools: Read, Write, Edit, Bash, Task, AskUserQuestion, WebFetch, WebSearch,
               mcp__*,
               mcp__plugin_memoforge_courtlistener__*,
               mcp__plugin_memoforge_legal-data-hunter__*
```

The `mcp__*` wildcard is required because in Cowork (the primary host) MCP tools surface under an opaque UUID namespace (see Phase 1 precheck in `skills/memo/SKILL.md:186`), not the static `mcp__plugin_memoforge_*` prefix the manifest declares. The plugin-scoped prefix is retained as a hint for hosts that honor it; the wildcard ensures MCP works wherever the UUID-prefix policy applies. The `continue` skill frontmatter mirrors this set so resumed research / follow-up / currency dispatches inherit the same MCP / WebFetch / WebSearch surface.

Subagents that omit `tools:` in their frontmatter inherit the entire set. Subagents that declare `tools:` get exactly that set (and no MCP unless `mcp__*` or a matching namespace prefix is explicitly listed).

Per-agent tool sets:

| Agent | Frontmatter `tools:` | Inherits MCP / WebFetch / WebSearch? |
|-------|----------------------|-----|
| `fact-assumption-analyst` | (omitted — inherits, as of 0.0.39) | YES (full set) — previously had an explicit MCP allowlist hard-coding the plugin namespace; that was removed in 0.0.39 to match the function-name detection policy |
| `statutory-researcher`, `case-law-researcher`, `currency-checker`, `doctrinal-researcher` | (omitted — inherits) | YES (full set) |
| `memo-writer`, `revision-mediator` | `Read, Write, Edit` | NO |
| `citation-auditor` | `Read, Write, Glob` (Glob added in 0.0.39 so verbatim verification can enumerate `research/raw/`) | NO |
| `counterargument-reviewer`, `logic-reviewer`, `clarity-reviewer`, `style-reviewer`, `client-readiness-reviewer` | `Read, Write` | NO |
| `research-sufficiency-reviewer`, `source-pack-builder` | `Read, Write, Glob, Grep` | NO |

## §Validators

Two Python scripts enforce contracts. The pipeline shells into them via Bash.

### `scripts/validate_state.py`

Phase-aware. Enforces the canonical state schema (above). Rejects:
- Missing always-required fields.
- Top-level `max_iterations` (single source of truth is `config.max_iterations`).
- `current_phase` not in the enumeration.
- `heartbeat_choice` (deprecated since v0.0.43) — only enforced on legacy tasks where the field still exists: must be in `{pending, continue_full, research_summary_only}` (the `switch_to_quick` value was removed in 0.0.39). New tasks do not write this field.
- After `planning` phase: missing `mode` or any `config` shape key.
- `current_iteration > config.max_iterations` in `revision_loop`.
- Missing `final_status` in `export` and later.
- `counterargument` (singular) in `config.reviewer_list` (must be `counterarguments` plural).

### `scripts/validate_review_json.py`

Mode-aware. Resolves the reviewer set in this priority:
1. `--reviewers <comma_list>` CLI flag.
2. `state.json.config.reviewer_list`.
3. Default: all five (`logic`, `clarity`, `style`, `citations`, `counterarguments`).

Validates ONLY the resolved set. Brief mode (3 reviewers) passes without `clarity` or `style` files. Each reviewer JSON must include `reviewer`, `version_reviewed`, `overall_score` (0-100), `blocking_issues` (list), `nice_to_have` (list), `verdict` (`approved` or `needs_revision`).

## §Fallback banners

`state.json.fallback_banners[]` accumulates one string entry per fallback path that fires. The string is the user-facing banner text (per the matrix in `skills/memo/references/always-deliver.md`). `lib/docx-render/scripts/md_to_docx.py:add_warning_banner` renders the array as bulleted items in the yellow warning box at the top of the docx.

Banners fire even when `final_status` begins with `approved`, because some fallbacks (MCP rate-limited, MCP unavailable) can complete the pipeline successfully but still need to disclose what was downgraded.

## §File-link UX (chat)

**Plain text only.** Do NOT wrap file paths in markdown link syntax `[label](path)` in chat output. Empirical Cowork behaviour (0.0.30-0.0.32): relative and absolute paths inside chat text are NOT rendered as clickable file references. Clickability comes from the artifact card Cowork inserts automatically when the model uses `Read` / `Write` / `Edit` tools.

Operational rule for every assistant chat message:
- File names appear as plain text (e.g. `intake-questions.md`) or as plain-text paths (e.g. `outputs/memoforge-work/<task_id>/intake-questions.md`).
- The artifact card from the underlying `Write` tool call is the user's click-to-open affordance.
- If a file needs to be referenced but no Write/Read/Edit fired for it in this turn, mention it as plain text and tell the user where to find it ("see `<state.json.rel_work_dir>/...`").

## §Release hygiene

- `README.md` version line, `.claude-plugin/plugin.json:4` version, latest `git tag`, and the latest `dist/*.zip` MUST all match.
- New release procedure (single command, atomic):
  1. Update `.claude-plugin/plugin.json` version.
  2. Update `README.md` version line.
  3. Prepend a `CHANGELOG.md` entry.
  4. Build the dist zip (name encodes the version).
  5. Tag `v<version>`.

`CHANGELOG.md` lives at the repo root.
