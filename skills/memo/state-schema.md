# state.json canonical schema

Single source of truth for `state.json` shape. All skills and agents that read or write it (memo, continue, status, revision-mediator) reference this schema. Field-level ownership noted in comments.

```jsonc
{
  "task_id": "memo-<ISO_timestamp>-<slug>",        // owner: memo Phase 1 (write-once)
  "user_query": "<original query string>",          // owner: memo Phase 1
  "created_at": "<ISO 8601 timestamp>",             // owner: memo Phase 1
  "language": "en",                                 // owner: memo Phase 1 (always en; plugin is English-only as of 0.0.35)

  "work_dir": "<absolute or platform-native path>", // owner: memo Phase 1 (write-once); USE FOR Read/Write/Bash filesystem operations. May be absolute in Cowork (/sessions/<id>/mnt/...).
  "rel_work_dir": "<CWD-relative form of work_dir>",// owner: memo Phase 1 (write-once); backfilled by continue/SKILL.md if missing on legacy tasks. USE FOR plain-text path display in chat ("Work directory: <path>" lines). Cowork does NOT render either relative or absolute paths as clickable inside chat text — clickability comes from artifact cards on Read/Write/Edit tool calls. This field exists purely so the user sees a short, readable path rather than the absolute Cowork mount path.
  "output_folder": "<parent of work_dir>",          // owner: memo Phase 1 (write-once); the resolved $CLAUDE_PLUGIN_OPTION_OUTPUT_FOLDER / $LEGAL_MEMO_OUTPUT_FOLDER / fallback.

  "mode": null | "brief" | "full",                  // owner: memo Phase 1.5 (write-once after user picks via AskUserQuestion). Legacy values "quick"|"standard"|"deep" are accepted on read by continue/SKILL.md and silently migrated.
  "config": {                                        // owner: memo Phase 1 initializes to {}; visualize precheck (Phase 1) populates visualize_* keys; Phase 1.5 MERGES mode-config from `skills/memo/references/modes.md` matrix (does NOT overwrite, preserves visualize_* keys). Mid-run mode change is not supported — config is set once at Phase 1.5 and is immutable after.
    "visualize_enabled": false | true,               // owner: memo Phase 1 visualize precheck; true iff `visualize:show_widget` and `read_me` are discoverable under a namespace containing `visualize`
    "visualize_namespace": null | "<prefix>",        // owner: memo Phase 1 visualize precheck; the full tool prefix up to but not including `__show_widget`
    "researcher_set": ["statutory", "case-law", "doctrinal"],   // CANDIDATE set (mode-dependent, NOT mutated by plan.doctrine_required). Brief = ["statutory"]; Full = ["statutory","case-law","doctrinal"]. The actually-dispatched subset (doctrinal filtered out when plan says Doctrine: no) lives in state.json.dispatched_researchers — see Fix 6 candidate vs dispatched in pipeline-contract.md.
    "reviewer_list": ["logic", "clarity", "style", "citations", "counterarguments"], // subset based on mode (added at Phase 1.5); canonical form is plural. Brief = 3 reviewers (logic, citations, counterarguments); Full = all 5.
    "max_iterations": 1 | 3,                         // mode-dependent (Brief=1, Full=3); single source of truth for the revision-loop iteration cap — there is NO top-level max_iterations
    "client_polish_enabled": false | true,           // Brief = false; Full = true
    "max_client_polish": 0 | 1,                      // Brief=0, Full=1
    "template_id": "executive-brief" | "classical-memo"  // direct mode→template binding (Brief → executive-brief, Full → classical-memo). Replaces the previous `template_constraint` object with its forced/bounded/open modes.
  },
  // "heartbeat_choice" — DEPRECATED in v0.0.43. The Phase 7.5 heartbeat gate (full vs research-summary) was replaced by the source-review checkpoint, which is a text-parsed continue/cancel gate (no full/summary branch). NEW tasks do not write this field. Legacy tasks created on v0.0.42 or earlier may still have it set; `skills/continue/SKILL.md` drops it on resume and logs `legacy_field_dropped`.
  "revision_gate_choice": null | "continue",  // v0.0.44: auto-advanced by Phase 9 step 6b (no user gate). Legacy v0.0.43 value `accepted_early` no longer written but accepted on read.
  "client_readiness_gate_choice": null | "continue",  // v0.0.44: auto-advanced by Phase 9 step 6c (no user gate). Legacy v0.0.43 value `skip_polish` no longer written; resume normalises it to `continue` and emits `legacy_value_migrated`.
  "polish_gate_choice": null | "apply",  // v0.0.44: auto-advanced by Phase 10 (no user gate). Legacy v0.0.43 value `skip` accepted on read but new tasks never write it.

  "fallback_banners": [],                            // owner: any fallback path in always-deliver.md; consumed by md_to_docx.py

  "intake": {
    "status": "preliminary_research" | "questions_pending" | "answered" | "assumptions_accepted",
    "questions_iteration": 1,
    "user_response": null | "<raw user intake response>",
    "assumptions_accepted": false
  },

  "classification": null | {                         // owner: memo Phase 3
    "type": "regulatory_analysis" | "transactional" | "litigation_risk" | "cross_border" | "compliance_check" | "mixed",
    "jurisdictions": ["EU", "CY", ...],
    "doctrine_required": true | false,
    "estimated_complexity": "low" | "medium" | "high",
    "selected_template_id": "classical-memo" | "executive-brief"  // set from config.template_id by Phase 3. Legacy values risk-assessment | regulatory-analysis | cross-jurisdictional remain readable for archived tasks but new tasks never write them; continue/SKILL.md migrates them to classical-memo on resume.
  },

  "plan_approval": {                                // owner: memo Phase 1/2 (writes), continue (writes during plan_approval_pending replay)
    "status": "not_started" | "pending" | "approved" | "cancelled",
    "iterations": [
      {
        "iteration": 1,                             // 1-indexed
        "shown_at": "<ISO>",
        "user_response": "approve" | "edit: ..." | "cancel" | null,
        "responded_at": "<ISO> | null"
      }
    ],
    "final_plan_iteration": null | <int>            // set to iteration number when status transitions to approved
  },

  "current_phase":                                  // owner: memo (sets), mediator (advances during loop), memo Phase 11 (sets done)
    "intake_preliminary_research" | "intake_questions_pending" | "mode_pick_pending" | "planning" | "plan_approval_pending" | "research" | "research_sufficiency" | "currency_check" | "source_pack" | "source_review_pending" | "drafting" | "revision_loop" | "client_readiness" | "export" | "done" | "failed" | "cancelled_by_user",
  // `source_review_pending` replaces the v0.0.42 `heartbeat_pending` (which is deprecated-legacy — see /continue migration). The phase ends the assistant turn explicitly so Cowork flushes chat after the parallel research block.
  // `mode_pick_pending` is the hard gate for Phase 1.5 mode choice. It sits between `intake_questions_pending` and `planning`. /continue must NOT advance from this phase to `planning` until `state.json.mode` is set via the Phase 1.5 AskUserQuestion.

  "dispatched_researchers": null | [                // owner: memo Phase 5; subset of config.researcher_set actually invoked (doctrinal omitted when plan.doctrine_required is false). Set BEFORE Agent dispatch, so audit (`phase5_dispatch` event) can compare candidate vs dispatched.
    "statutory" | "case-law" | "doctrinal"
  ],

  "current_iteration": 0,                           // owner: memo initializes to 1 after v1; revision-mediator advances/exits thereafter.
  // `max_iterations` lives ONLY under `config.max_iterations` (mode-dependent). No top-level field.
  "max_plan_edit_iterations": 5,                    // const; actively used by /continue plan_approval_pending branch to bound edit cycles
  "max_intake_iterations": 2,                       // DEPRECATED const (kept for backward compat — pre-0.0.30 logic tracked intake-edit cycles here; current intake parsers do not loop, so the field is unused. Phase 1 still writes it; validator requires its presence for legacy state shape; no logic reads it. Candidate for removal in a future release.)
  "exit_threshold_score": 85,                       // DEPRECATED const (informational — earlier design used a numeric score threshold for reviewer approval; current logic gates only on `blocking_issues == []`, so this field has no effect. Phase 1 still writes it; validator requires its presence for legacy state shape; no logic reads it. Candidate for removal in a future release.)
  "current_draft_path": null | "drafts/v<N>.md",    // owner: memo Phase 4 (sets v1), mediator (advances)

  "iterations": [                                   // owner: revision-mediator (appends one entry per completed iteration)
    {
      "version": <int>,
      "draft_path": "drafts/v<N>.md",
      "reviews": {
        "logic":     {"score": <int>, "blocking_count": <int>, "path": "reviews/v<N>-logic.json"}     | {"status": "failed"},
        "clarity":   {"score": <int>, "blocking_count": <int>, "path": "reviews/v<N>-clarity.json"}   | {"status": "failed"},
        "style":     {"score": <int>, "blocking_count": <int>, "path": "reviews/v<N>-style.json"}     | {"status": "failed"},
        "citations": {"score": <int>, "blocking_count": <int>, "path": "reviews/v<N>-citations.json"} | {"status": "failed"},
        "counterarguments": {"score": <int>, "blocking_count": <int>, "path": "reviews/v<N>-counterarguments.json"} | {"status": "failed"}
      },
      "mediator_path": "reviews/v<N>-mediator.md",
      "status": "approved" | "needs_revision" | "forced_exit",
      "completed_at": "<ISO>"
    }
  ],

  "client_readiness": null | {
    "verdict": "client_ready" | "needs_final_polish" | "manual_review_required",
    "path": "reviews/final-client-readiness.json",
    "polish_attempted": true | false,
    "blocking_issues": []
  },

  "final_status": null                              // owner: revision-mediator (writes during exit) or memo Phase 11 or Phase 9 step 6b
    | "approved_on_v<N>"
    | "forced_exit_on_v<N>_with_remaining_issues"
    | "manual_review_required_on_v<N>"
    | "accepted_early_on_v<N>"                       // user picked "Accept v<N> as final" at end-of-iteration gate
    | "fallback_research_summary_delivered"           // user-chosen research-summary mode (heartbeat → Phase 8 branch A); the docx banner says "RESEARCH SUMMARY MODE"
    | "fallback_summary_delivered",                  // universal catastrophic fallback per always-deliver.md (writes fallback-summary.md, may or may not invoke md_to_docx.py)
  "final_docx_path": null | "<absolute path>", // owner: memo Phase 11. ABSOLUTE path equal to `<state.json.work_dir>/memo-<slug>.docx` after a successful export, or `<state.json.work_dir>/memo-<slug>.md` if Phase 11 fell back to delivering markdown (per `always-deliver.md`). Validator (`scripts/validate_state.py`) requires `pathlib.Path(final_docx_path).is_file()` once `current_phase == done`. The legacy `final_artifacts_dir` field is removed — the audit trail folder IS `work_dir`.

  "attempts": {                                     // owner: memo/continue (retry-budget persistence)
    "research_followup": 0,
    "research_followup_pending_review": false,
    "client_readiness_polish": 0,
    "client_readiness_polish_pending_review": false,
    "sufficiency_regate": 0,                        // owner: memo Phase 6.5; incremented (max 1) when currency-checker invalidates sources and memo re-dispatches research-sufficiency-reviewer. Validator rejects > 1.
    "reviewer_json_retry": {"v<N>-logic": 1}
  },
  "remaining_blocking_issues": [],                  // owner: mediator/client-readiness; used by docx warning banner
  "events_path": "events.jsonl"
}
```

**Atomicity:** any writer of `state.json` must write to `state.json.tmp` then `mv state.json.tmp state.json` (preventing torn writes).
