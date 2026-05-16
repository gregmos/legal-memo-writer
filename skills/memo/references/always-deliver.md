# Always-deliver invariant — fallback matrix

Authoritative reference for every degradation path in the pipeline. The hard rule: **the user never ends up with nothing**. Every phase has a documented fallback action and a banner the final deliverable carries.

When a phase encounters failure or forced degradation, the orchestrator (`skills/memo/SKILL.md`) consults this matrix, executes the fallback, records the chosen fallback in `state.json.final_status` plus `events.jsonl`, and continues toward export. Banner text is injected into the docx by `md_to_docx.py` based on `state.json.final_status` and `state.json.fallback_banners[]`.

## Fallback matrix

### Phase 1 (init) — workspace creation fails

| Failure | Fallback | Banner |
|---|---|---|
| `${CLAUDE_PLUGIN_DATA}` not writable | Create working dir under user output folder instead (`<output_folder>/legal-memo-work/<task_id>/`); record alternate path in `state.json.work_dir` | none — silent fallback already deployed in current build |

### Phase 1.5 (mode choice) — user picks "Other" or skips

| Failure | Fallback | Banner |
|---|---|---|
| User picks Other in AskUserQuestion | Treat as Standard. Print one-line note "Defaulting to Standard mode; rerun with /memo if you wanted Quick or Deep." | none |

### Phase 5 (parallel research) — MCP outage

| Failure | Fallback | Banner |
|---|---|---|
| Legal Data Hunter + CourtListener both unavailable | Researchers proceed in WebFetch-only mode against vetted official portals (`eur-lex.europa.eu`, `courtlistener.com` public pages, `edpb.europa.eu`, national gazettes if mentioned in plan). Each research file's final line records `mcp_status: unavailable`. | "MCP servers unavailable. Research conducted via public WebFetch only — verify against primary sources before client use." |
| One MCP unavailable, the other up | Continue with the available MCP. Note the gap in each research file. | "Partial MCP coverage — only <available> was reachable." |
| Both MCP up but WebFetch also failing to a critical portal | Continue with what is reachable. Researcher writes explicit `gap:` entry per missing portal. | "Some primary sources were unreachable; gaps disclosed in research files." |

### Phase 6 (research sufficiency)

| Failure | Fallback | Banner |
|---|---|---|
| Verdict = `insufficient_for_client_ready_memo` and follow-up budget consumed | Proceed to drafting. Memo MUST contain a dedicated "Open questions / unverified facts" section listing what remains unanswered. | "Research sufficiency: insufficient. Open questions disclosed in section X — do not act on this memo without further investigation." |
| `research-sufficiency-reviewer` itself crashes | Re-dispatch once with explicit error context. If second attempt fails, proceed as if verdict = insufficient (above). | "Research sufficiency review unavailable; defaulting to insufficient status." |

### Phase 6 (currency check)

| Failure | Fallback | Banner |
|---|---|---|
| `currency-checker` reports ≥1 blocking issue | Drop the unverifiable source from source-pack candidates; reference its replacement (general guidance + verification reminder). | "Currency check raised <N> blocking issue(s); affected sources flagged in source pack." |
| `currency-checker` itself crashes | Treat all sources as `manual-check`; reference in banner. | "Currency check unavailable; verify every source manually before client use." |

### Phase 7 (source pack)

| Failure | Fallback | Banner |
|---|---|---|
| `source-pack-builder` fails or returns empty pack | Build a minimal source-pack from research file headings (one row per source headline + URL + tier from researcher markup); flag missing fields. | "Source pack incomplete; verify citations manually." |

### Phase 7→8 heartbeat (user choice)

| Choice | Action | Banner |
|---|---|---|
| "Continue full revision loop" | Proceed normally to Phase 8. | none |
| "Stop and deliver research summary" | Single `memo-writer` pass with template-id `research-summary-only` (or fallback to `executive-brief`); skip Phase 9 + Phase 10; jump to Phase 11 export. | "Research summary mode — full IRAC analysis not performed per user choice. The memo reports findings only; legal conclusions are not validated through the revision loop." |
| "Switch to Quick mode now" | Rewrite `state.json.config` to Quick values; log `mode_downgraded` event; proceed to Phase 8 normally. | none (Quick-mode banner if any other fallback fires later) |

### Phase 8 (drafting v1)

| Failure | Fallback | Banner |
|---|---|---|
| `memo-writer` crashes or returns malformed draft | Re-dispatch once with explicit error context and a stricter prompt. If second attempt fails, emit a partial-draft note containing whatever was salvaged plus the prompt that was used. | "Drafting incomplete — partial draft below; manual completion required." |
| `memo-writer` returns empty/zero-issue draft | Treat as drafting failure → same retry → if still empty, fall back to research-summary template. | "Drafting produced no analysis; delivered research summary instead." |

### Phase 9 (revision loop)

| Failure | Fallback | Banner |
|---|---|---|
| Reviewer JSON validator reports invalid output after retry + failure stubs | Force exit at iteration N with last validated draft. | "Revision loop forced exit at iteration N — N reviewer outputs malformed; latest draft delivered." |
| Mediator state-write validator fails after one retry | Force exit at iteration N with `drafts/v<N>.md` as final draft. | "Mediator state corruption detected; exited at last validated draft v<N>." |
| `current_iteration` reaches `config.max_iterations` with unresolved blockers | Existing forced-exit path: `final_status = forced_exit_on_v<N>_with_remaining_issues`. | "REVIEWER NOTES NOT FULLY RESOLVED — <N> blocking issues remain (listed in appendix)." |

### Phase 10 (client-readiness)

| Failure | Fallback | Banner |
|---|---|---|
| Verdict = `manual_review_required` AND `config.client_polish_enabled = false` | Proceed to export. Append blocker list to memo as an appendix section. | "Client-readiness: manual_review_required. Blocking issues in appendix." |
| Verdict = `needs_final_polish` AND polish budget consumed | Proceed to export with banner. | "Client-readiness: post-polish concerns remain; verify before client delivery." |
| `client-readiness-reviewer` crashes after retry | Treat as `manual_review_required` (above). | "Client-readiness review unavailable; treated as manual review required." |

### Phase 11 (docx export)

| Failure | Fallback | Banner |
|---|---|---|
| `python3 md_to_docx.py` fails | Try `pandoc <input> -o <output>` as best-effort fallback. | none if pandoc succeeds |
| Both python and pandoc fail | Deliver the markdown file as the final artifact: copy `drafts/v<N>-client-ready.md` (or latest available) to `<output>/<task_id>/memo-<slug>.md`. Update `state.json.final_docx_path` to the .md path. | "docx export failed — markdown file delivered. Convert manually with pandoc or save-as docx." |
| Copy to user output folder fails (permissions) | Keep artifact in `${CLAUDE_PLUGIN_DATA}/work/<task_id>/final/` and surface its full path in chat as a clickable reference. | "Output folder not writable; final artifact remains in plugin data directory. Path: <full_path>." |

## Universal final fallback

If a phase still cannot complete and none of the above applies:

1. Write `${CLAUDE_PLUGIN_DATA}/work/<task_id>/final/fallback-summary.md` containing:
   - task_id, mode, last successful phase, current_phase, ISO timestamp
   - `state.json` snapshot (pretty-printed)
   - one-paragraph plain-text description of what was learned (use whatever survives in `research/`, `drafts/`, `reviews/`)
   - explicit list of what failed
2. Copy that file to `<output>/<task_id>/fallback-summary.md`.
3. Update `state.json.final_status = fallback_summary_delivered`.
4. Print final progress block with the fallback path.
5. End turn.

**Never end the pipeline silently. The user must always see a final chat message and a file at the documented output path.**

## State fields used by this matrix

| Field | Set by | Read by |
|---|---|---|
| `state.json.final_status` | each fallback that fires | Phase 11 export (banner injection), Phase 12 summary |
| `state.json.fallback_banners` | array, appended by every fallback that fires | `md_to_docx.py` for the docx warning section |
| `state.json.attempts.<budget_name>` | mediator, sufficiency-reviewer, client-readiness-reviewer | orchestrator to decide retry vs. give up |
| `events.jsonl` | every fallback writes one event with `type: fallback_invoked`, fallback_name, reason | audit / debugging |
