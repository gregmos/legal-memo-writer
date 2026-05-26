# Always-deliver invariant — fallback matrix

Authoritative reference for every degradation path in the pipeline. The hard rule: **the user never ends up with nothing**. Every phase has a documented fallback action and a banner the final deliverable carries.

When a phase encounters failure or forced degradation, the orchestrator (`skills/memo/SKILL.md`) consults this matrix, executes the fallback, records the chosen fallback in `state.json.final_status` plus `events.jsonl`, and continues toward export. Banner text is injected into the docx by `md_to_docx.py` based on `state.json.final_status` and `state.json.fallback_banners[]`.

## Fallback matrix

### Phase 1 (init) — workspace creation fails

| Failure | Fallback | Banner |
|---|---|---|
| `${CLAUDE_PLUGIN_DATA}` not writable | Create working dir under user output folder instead (`<output_folder>/memoforge-work/<task_id>/`); record alternate path in `state.json.work_dir` | none — silent fallback already deployed in current build |

### Phase 1.5 (mode choice) — user picks "Other" or skips

| Failure | Fallback | Banner |
|---|---|---|
| User picks Other in AskUserQuestion | Treat as Full. Print one-line note "Defaulting to Full mode; rerun with /memo if you wanted Brief." | none |

### Phase 5 (parallel research) — MCP outage

| Failure | Fallback | Banner |
|---|---|---|
| Legal Data Hunter + CourtListener both unavailable | Researchers proceed in WebFetch-only mode against vetted official portals (`eur-lex.europa.eu`, `courtlistener.com` public pages, `edpb.europa.eu`, national gazettes if mentioned in plan). Each research file's final line records `mcp_status: unavailable`. | "MCP servers unavailable. Research conducted via public WebFetch only — verify against primary sources before client use." |
| One MCP unavailable, the other up | Continue with the available MCP. Note the gap in each research file. | "Partial MCP coverage — only <available> was reachable." |
| Both MCP up but WebFetch also failing to a critical portal | Continue with what is reachable. Researcher writes explicit `gap:` entry per missing portal. | "Some primary sources were unreachable; gaps disclosed in research files." |
| MCP returns explicit rate-limit / 429 / quota-exceeded error mid-run | Researcher invokes the rate-limit fallback per `skills/memo/references/mcp-ratelimit-contract.md`: stops calling the throttled MCP, switches to WebSearch + WebFetch on canonical URLs, marks each fallback item `[rate-limited fallback]` in the research file, appends a `mcp_ratelimit_fallback` event to `events.jsonl`. The orchestrator reads those events at the end of Phase 5 and pushes the banner. | "Some research sources were retrieved via web-search fallback due to MCP service rate limits. Items tagged `[rate-limited fallback]` in research files; verify the canonical URLs in the source pack." |

### Phase 6 (research sufficiency)

| Failure | Fallback | Banner |
|---|---|---|
| Verdict = `insufficient_for_client_ready_memo` and follow-up budget consumed | Proceed to drafting. Memo MUST contain a dedicated "Open questions / unverified facts" section listing what remains unanswered. | "Research sufficiency: insufficient. Open questions disclosed in section X — do not act on this memo without further investigation." |
| `research-sufficiency-reviewer` itself crashes | Re-dispatch once with explicit error context. If second attempt fails, proceed as if verdict = insufficient (above). | "Research sufficiency review unavailable; defaulting to insufficient status." |
| Phase 6.6 user-followup gate fired but reviewer JSON had `main-session` blocking_gap with `followup_question == null` (reviewer-output bug; v0.6.3+) | Log `research_sufficiency_schema_violation` event. Treat each malformed gap as if it were a researcher gap with `recommended_followup_prompt` fabricated from the `gap` text. Fall through to researcher re-dispatch (Branch B6b). | No user-facing banner — orchestrator-internal recovery, audit only. |
| Phase 6.6 user-followup gate fired, user answered, but Subset U gaps remain unresolved after re-run sufficiency (`attempts.research_followup >= 1` consumed; user gave answers that did not resolve the legal gap) | Promote remaining Subset U gaps to `drafting_warnings[]`; memo writer carries assumption-based caveats into the draft. | "Some facts material to the analysis remained ambiguous after follow-up. Memo proceeds on conservative default assumptions documented in the Assumptions section." |

### Phase 6.5 (currency check)

| Failure | Fallback | Banner |
|---|---|---|
| `currency-checker` reports ≥1 blocking issue | Drop the unverifiable source from source-pack candidates; reference its replacement (general guidance + verification reminder). | "Currency check raised <N> blocking issue(s); affected sources flagged in source pack." |
| `currency-checker` itself crashes | Treat all sources as `manual-check`; reference in banner. | "Currency check unavailable; verify every source manually before client use." |

### Phase 7 (source pack)

| Failure | Fallback | Banner |
|---|---|---|
| `source-pack-builder` fails or returns empty pack | Build a minimal source-pack from research file headings (one row per source headline + URL + tier from researcher markup); flag missing fields. | "Source pack incomplete; verify citations manually." |

### Phase 7→8 source-review checkpoint (user choice) — v0.0.43+

| Choice | Action | Banner |
|---|---|---|
| User replies `continue` (or proceed/go/draft/yes/ok) | Set `current_phase = drafting`, proceed to Phase 8. | none |
| User replies `cancel` (or stop/abort/no) | Set `current_phase = cancelled_by_user`. Work directory and source-pack preserved for later resume. | none |
| Unparseable reply | Re-show the source-review checkpoint instructions. Do NOT advance. | none |
| User does nothing | Pipeline waits. The assistant turn already ended at Phase 7.5; nothing happens until user replies. | none |

(The v0.0.42 "Continue full loop / Research summary only" heartbeat AskUserQuestion was removed in v0.0.43 — the gate was unreliable post-parallel-Task per Anthropic issues #26805/#29773 family. Plain text checkpoint + explicit end-of-turn is the reliable mechanism. Research-summary mode was removed at the same time; the full pipeline is now the only path. The `templates/research-summary-only.md` file remains on disk as vestigial.)

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
| Both python and pandoc fail | Deliver the markdown file as the final artifact. **Source selection (deterministic):** (1) if `drafts/v<N>-client-ready.md` exists for the highest N, use that; (2) else use `state.json.current_draft_path` (which always points at the most recent `drafts/v<N>.md`); (3) else pick the highest-N file matching `drafts/v*.md`. Copy that file to `<work_dir>/memo-<slug>.md`. Update `state.json.final_docx_path` to the absolute path of the .md file. | "docx export failed — markdown file delivered. Convert manually with pandoc or save-as docx." |
| Copy to user output folder fails (permissions) | Keep artifact in the resolved working directory (`<state.json.work_dir>/`, same folder used since Phase 1 — no separate "plugin data" location exists in v0.0.29+). Call `Read` on the final memo-<slug>.docx so Cowork inserts an artifact card for it; surface the work-directory path in chat as plain text. | "Output folder write failed; final artifact memo-<slug>.docx remains in working directory at <state.json.rel_work_dir>/. See the Read tool card above for clickable access." |

## Universal final fallback

If a phase still cannot complete and none of the above applies:

1. Write `<state.json.work_dir>/fallback-summary.md` (the working directory used since Phase 1 — there is no separate plugin data directory in v0.0.29+) containing:
   - task_id, mode, last successful phase, current_phase, ISO timestamp
   - `state.json` snapshot (pretty-printed)
   - one-paragraph plain-text description of what was learned (use whatever survives in `research/`, `drafts/`, `reviews/`)
   - explicit list of what failed
2. Update `state.json.final_status = fallback_summary_delivered`.
3. Make `fallback-summary.md` visible to Cowork: call the `Read` tool on `<state.json.work_dir>/fallback-summary.md` so Cowork's UI inserts an artifact card for it (this gives the user a clickable way to open the file).
4. Print the final Progress block as plain assistant text (v3 format — see `skills/memo/references/progress-contract.md` §"Progress block format"):

   ```
   **Progress — <task_id>**
   - Current phase: `failed`
   - Completed: Pipeline failed gracefully; fallback-summary.md written
   - Next: Manual review required
   - Notes: Last successful phase: <X>; see the fallback-summary.md artifact card above for details
   ```

   Do not wrap any file names in markdown links — they don't render as clickable in chat. The artifact card from the Read call above is the user's clickable access.
5. End turn.

**Never end the pipeline silently. The user must always see a final chat message and a file at the documented output path.**

## State fields used by this matrix

| Field | Set by | Read by |
|---|---|---|
| `state.json.final_status` | each fallback that fires | Phase 11 export (banner injection), Phase 12 summary |
| `state.json.fallback_banners` | array, appended by every fallback that fires | `md_to_docx.py` for the docx warning section |
| `state.json.attempts.<budget_name>` | mediator, sufficiency-reviewer, client-readiness-reviewer | orchestrator to decide retry vs. give up |
| `events.jsonl` | every fallback writes one event with `type: fallback_invoked`, fallback_name, reason | audit / debugging |
