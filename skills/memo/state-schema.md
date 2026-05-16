# state.json canonical schema

Single source of truth for `state.json` shape. All skills and agents that read or write it (memo, continue, status, revision-mediator) reference this schema. Field-level ownership noted in comments.

```jsonc
{
  "task_id": "memo-<ISO_timestamp>-<slug>",        // owner: memo Phase 1 (write-once)
  "user_query": "<original query string>",          // owner: memo Phase 1
  "created_at": "<ISO 8601 timestamp>",             // owner: memo Phase 1
  "language": "ru" | "en",                          // owner: memo Phase 1 (auto-detected)

  "mode": null | "quick" | "standard" | "deep",     // owner: memo Phase 1.5 (write-once after user picks via AskUserQuestion)
  "config": null | {                                 // owner: memo Phase 1.5 (resolved from `skills/memo/references/modes.md` matrix); heartbeat may downgrade to Quick
    "researcher_set": ["statutory", "case-law", "doctrinal"],   // subset based on mode + plan.doctrine_required
    "reviewer_list": ["logic", "clarity", "style", "citations", "counterargument"], // subset based on mode
    "max_iterations": 1 | 3,                         // mode-dependent; overrides the default constant below for the running task
    "targeted_followup_forced": false | true,        // Deep mode forces one follow-up regardless of sufficiency verdict
    "client_polish_enabled": false | true,           // Quick = false
    "max_client_polish": 0 | 1 | 2                   // Quick=0, Standard=1, Deep=2
  },
  "heartbeat_choice": null | "continue_full" | "research_summary_only" | "switch_to_quick",  // owner: memo Phase 7.5

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
    "selected_template_id": "classical-memo" | "executive-brief" | "risk-assessment" | "regulatory-analysis" | "cross-jurisdictional"
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
    "intake_preliminary_research" | "intake_questions_pending" | "planning" | "plan_approval_pending" | "research" | "research_sufficiency" | "currency_check" | "source_pack" | "drafting" | "revision_loop" | "client_readiness" | "export" | "done" | "failed" | "cancelled_by_user",

  "current_iteration": 0,                           // owner: memo initializes to 1 after v1; revision-mediator advances/exits thereafter.
  "max_iterations": 3,                              // const
  "max_plan_edit_iterations": 5,                    // const
  "max_intake_iterations": 2,                       // const
  "exit_threshold_score": 85,                       // const (informational)
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

  "final_status": null                              // owner: revision-mediator (writes during exit) or memo Phase 11
    | "approved_on_v<N>"
    | "forced_exit_on_v<N>_with_remaining_issues"
    | "manual_review_required_on_v<N>",
  "final_docx_path": null | "<absolute path in user output folder>", // owner: memo Phase 11

  "attempts": {                                     // owner: memo/continue (retry-budget persistence)
    "research_followup": 0,
    "research_followup_pending_review": false,
    "client_readiness_polish": 0,
    "client_readiness_polish_pending_review": false,
    "reviewer_json_retry": {"v<N>-logic": 1}
  },
  "remaining_blocking_issues": [],                  // owner: mediator/client-readiness; used by docx warning banner
  "events_path": "events.jsonl"
}
```

**Atomicity:** any writer of `state.json` must write to `state.json.tmp` then `mv state.json.tmp state.json` (preventing torn writes).
