# User-visible progress contract — chat messages, file references, mandatory checklist

Canonical specification for the chat-visible Progress channel between the orchestrator and the user. The `skills/memo/SKILL.md` preamble points here. **Read this on every orchestrator activation before doing pipeline work** — same convention as `operating-contract.md` and `events-contract.md`.

This document covers ONLY the chat-visible `**Progress —**` block schema, the file-reference UX rule, and the 16-row checklist of mandatory transitions. Separate concerns:
- `events-contract.md` covers the audit log (`events.jsonl`).
- `logging-contract.md` covers per-subagent `<work_dir>/logs/<agent>.log` files.
- `progress-tracker.md` covers the visualize milestone widget (5 render points).

## Why this exists

The user is a lawyer working in Cowork chat. They cannot see your internal todo list, your task panel ticks, your tool calls, or files written to `${CLAUDE_PLUGIN_DATA}`. **The only signal they have is what you print as plain assistant text in the chat — combined with the Cowork artifact cards that appear automatically when you use Write/Edit/Read tools.**

> **CRITICAL:** The chat `**Progress —**` block is the PRIMARY signal to the user. The right-side task panel (driven by `TodoWrite`) is a SECONDARY channel and does not replace a chat message. If you advance to a new phase and the user does not see a new "Progress" message in chat, **you have broken the contract** and the user will think the pipeline is stuck. But: as of v0.0.42, `TodoWrite` is REQUIRED in addition to chat Progress — it is the only way to populate the side panel and survive Cowork's text-batching between tool calls. See "TodoWrite side-panel channel" below.

**Print a `Progress —` block as a top-level assistant message at every phase transition listed below. Print it BEFORE moving to the next phase. Never batch progress updates. Never collapse two phases into one update. Never skip an update because "nothing interesting happened" — even uneventful phases need confirmation that they ran.**

## How file references work in Cowork — IMPORTANT (canonical D2 rule)

When you create or modify a file through `Write` or `Edit` (or read one through `Read`), Cowork's UI **automatically inserts an artifact card** above your next chat message with the file name and a click-to-open affordance. Those cards are the user's clickable access to files. Example you will see in the transcript:

```
Created state.json
state.json
Created events.jsonl
events.jsonl
```

Each `Created X / X` pair is a separate artifact card rendered by the Cowork UI from the tool result. Files created via `Write`/`Edit` get this treatment automatically. Files created via `Bash` subprocess (e.g. a Python script that writes to disk) typically do **NOT** get this treatment — Cowork tracks Anthropic native tool calls, not arbitrary bash side effects.

**Do NOT try to make file names clickable inside the Progress block.** Specifically:

- ✗ `Artifacts: state.json, events.jsonl` — bare filenames are not clickable. Don't bother — there's no `Artifacts:` field in the v3 template (see below).
- ✗ `[state.json](outputs/memoforge-work/.../state.json)` — markdown links on relative paths without an http(s):// scheme are NOT rendered as clickable file references by Cowork UI. This was confirmed empirically across multiple test runs in 0.0.30–0.0.32 (helper-script approach with URL-encoding also failed). The Cowork chat parses the markdown but ignores the path for file access.
- ✗ `[state.json](file:///sessions/.../state.json)` — `file://` URLs would open in the browser, not the Cowork file viewer.
- ✗ `[state.json](C:\Users\...\state.json)` — absolute platform paths are also not made clickable.

**Just write plain text.** The user already has the artifact card above the Progress block from the Write/Edit/Read tool call.

This rule (the "D2 file-reference rule") is canonical for this plugin. Every other phase in `SKILL.md` that mentions file paths in chat follows it. If you ever find yourself writing `[label](path)` for a file reference in user-visible chat, stop and rewrite it as plain text.

## Progress block format (v3 — plain text)

Use this exact format (top-level chat message, not inside a tool call):

```markdown
**Progress — <task_id>**
- Current phase: `<current_phase>`
- Completed: <what just finished, one short line>
- Next: <what will happen next, one short line>
- Notes: <1-2 important facts: sufficiency verdict, blockers count, iteration number, etc.>
```

That's four fields: `Current phase`, `Completed`, `Next`, `Notes`. There is intentionally **no `Artifacts:` field** — file references are surfaced by the Cowork artifact cards that Write/Edit/Read tools generate automatically. Mentioning the same file names again in `Artifacts:` as plain text would only duplicate what the UI already shows; making them markdown links does not work (see "How file references work" above).

If a particular file name needs to appear inside the `Completed:`, `Next:`, or `Notes:` line for clarity (e.g. "Completed: drafts/v1.md produced"), write it as plain text. Don't wrap it in `[label](path)`. The user can find the file via the artifact card above the Progress block, or by opening the work directory.

**First Progress block per task** — include the work directory once so the user knows where the audit trail lives:

```markdown
**Progress — <task_id>**
- Current phase: `intake_preliminary_research`
- Completed: Task initialized; MCP and visualize prechecks done
- Next: Dispatching fact-assumption-analyst to triage missing facts
- Work directory: <state.json.rel_work_dir>
- Notes: LDH ✓, CourtListener ✓, visualize ✓
```

The `Work directory:` field is plain text (not a markdown link). The user will see the path and can navigate there directly; subsequent Progress blocks omit this field.

Also append a corresponding event to `<state.json.work_dir>/events.jsonl` for audit (this is filesystem write, not chat output).

Do not paste full research files or full draft text into chat. Surface phase, verdicts, counts, and blockers. The full artifacts stay in the work directory (and Cowork shows cards for the ones the orchestrator opens via Read/Write).

## Required progress updates — checklist

Print a chat `Progress —` block at each of these points. This is exhaustive — if you finish a phase that's on this list, the next thing the user must see is a chat message.

| # | When | --phase | What to put in Completed/Next/Notes |
|---|------|---------|--------------------------------------|
| 1 | After task initialization, before dispatching `fact-assumption-analyst` | `intake_preliminary_research` | Completed: "Task initialized; MCP/visualize prechecks done". Next: "Dispatching fact-assumption-analyst". Include `Work directory:` once here. |
| 2 | After `fact-assumption-analyst` returns, before showing intake | `intake_questions_pending` | Notes: must-answer count, optional count, whether assumptions are available |
| 3 | After intake answers are collected (Phase 2 → 3) | `planning` | Completed: "Intake recorded". Next: "Building plan" |
| 4 | After plan is written, before plan-approval question | `plan_approval_pending` | Notes: classification, template, jurisdictions, issue count, researchers to run |
| 5 | After plan is approved | `research` | Completed: "Plan approved". Next: "Dispatching researchers in parallel: <list>" |
| 6 | After all researchers return (Phase 5 end) | `research_sufficiency` | Notes: which research files were produced; any explicit gaps each researcher reported |
| 7 | After `research-sufficiency-reviewer` returns | `research_sufficiency` | Notes: sufficiency verdict, follow-up status (none/triggered/exhausted), blocker count, drafting-warning count |
| 8 | After `currency-checker` returns | `currency_check` | Notes: blocking issue count, manual-check count |
| 9 | After `source-pack-builder` returns | `source_pack` | Notes: evidence row count, do-not-use count, manual-check count |
| 9.5 | After source-pack, at the source-review checkpoint (Phase 7.5). The assistant turn ENDS here; this Progress block is the last chat output before user reply. | `source_review_pending` | Notes: research summary counts (statutes/cases/doctrine), evidence rows, blocking-currency issues, mode active. The Progress block is followed by the 📋 digest + `continue`/`cancel` instructions (see Phase 7.5 template in SKILL.md). |
| 10 | After `memo-writer` produces `drafts/v<N>.md` | `drafting` or `revision_loop` | Notes: version number, revision basis (initial draft / mediator feedback) |
| 11 | At the START of each revision iteration N (before reviewer dispatch) | `revision_loop` | Notes: iteration N, reviewer list |
| 12 | After all configured reviewers return + validator runs | `revision_loop` | Notes: iteration N, valid reviewer count, invalid/retried count, whether failure stubs were used |
| 13 | After `revision-mediator` returns | `revision_loop` | Notes: iteration N, verdict, blocking issue count, next action (loop / client-readiness / forced-exit) |
| 14 | After `client-readiness-reviewer` returns | `client_readiness` | Notes: client-readiness verdict, polish-attempt status, manual-review blocker count, final_status |
| 15 | Before docx export | `export` | Notes: final_status, output target folder |
| 16 | After docx export | `done` | Notes: summary stats (statutes/cases/doctrine counts, revision iterations, plan edits). See `SKILL.md` Phase 12 for the special `Read` + `.md mirror` procedure that makes the docx visible in chat. |

A pipeline run from intake to export should produce **at least 17 chat `Progress —` messages**. If you reach the end with fewer, audit the run and re-emit the missing ones.

## What does NOT count as a progress update

- The Cowork task-panel auto-checking phases (the panel is a secondary channel — see "TodoWrite side-panel channel" below; it complements chat Progress, never replaces it).
- Writing `events.jsonl`.
- Calling a tool whose output the user sees as a side-effect (e.g. `Created plan.md` artifact card). Artifact cards are great for clickability but they are not Progress messages — the user still needs the standalone `**Progress —` chat message that explains what just happened and what's next.
- Printing a tool call inside a thinking block.

The user must see a chat message **from you** with the `**Progress —`** prefix. If they don't, they think you're stuck.

## TodoWrite side-panel channel (mandatory since v0.0.42)

Cowork buffers assistant text between tool calls until the user types — so a chat `**Progress —**` block emitted between two phases may not render immediately even though the pipeline has advanced. The user reports "the chat is stuck on the first agent" while in reality 3 phases have already completed. The `TodoWrite` channel is the only reliable real-time signal into the right-side panel; updating it during a phase transition shows the user that work is moving.

**Rules:**

1. `TodoWrite` is REQUIRED in addition to chat Progress, not instead of it. Every `Progress —` block that this contract demands must still be printed. The `TodoWrite` call goes alongside.
2. Initialize the todo list ONCE near the top of Phase 1, with all 14 phases as items. Use this exact item set (order matters — Cowork renders them top-to-bottom):

   | # | content | activeForm |
   |---|---------|------------|
   | 1 | "Intake — fact triage and questions" | "Triaging facts and asking intake questions" |
   | 2 | "Mode pick (Brief / Full)" | "Picking pipeline mode" |
   | 3 | "Build research plan" | "Building research plan" |
   | 4 | "Plan approval" | "Awaiting plan approval" |
   | 5 | "Parallel research (3 agents)" | "Running 3 parallel researchers" |
   | 6 | "Research sufficiency review" | "Reviewing research sufficiency" |
   | 7 | "Currency check of sources" | "Checking source currency" |
   | 8 | "Source pack assembly" | "Assembling source pack" |
   | 9 | "Source review" | "Awaiting source review confirmation" |
   | 10 | "Draft v1 (memo-writer)" | "Drafting memo v1" |
   | 11 | "Revision loop" | "Running revision loop" |
   | 12 | "Client-readiness review" | "Reviewing client readiness" |
   | 13 | "Export to docx" | "Exporting to docx" |
   | 14 | "Finalize and summarize" | "Finalizing run" |

   At Phase 1 start, the first item is `in_progress` and the rest are `pending`.

3. On every phase transition, call `TodoWrite` to:
   - Mark the just-completed phase as `completed`.
   - Mark the next phase as `in_progress`.
   - Exactly ONE item should be `in_progress` at any time.

4. **Phase 5 special case — per-researcher sub-todos.** When dispatching researchers, BEFORE the parallel Agent calls, add three temporary sub-items right under item #5:
   - "  · statutory-researcher" (activeForm: "Running statutory-researcher") = `in_progress`
   - "  · case-law-researcher" (activeForm: "Running case-law-researcher") = `in_progress` (if in `dispatched_researchers`)
   - "  · doctrinal-researcher" (activeForm: "Running doctrinal-researcher") = `in_progress` (if in `dispatched_researchers`)
   
   The leading two spaces are deliberate — they visually nest under #5 in the panel. After ALL researchers return, mark each sub-item `completed` and #5 `completed`. The sub-items stay in the list (they document what ran in parallel — this is the user's only signal that 3 agents ran simultaneously, since Cowork may have only shown 1 tile in chat).

5. **Phase 11 revision iterations.** If a second or third iteration happens, do NOT add new sub-items — keep #11 `in_progress` with an updated activeForm: "Running revision loop (iteration N)".

6. **On resume** (`/memoforge:continue <task_id>`): re-issue the full 14-item TodoWrite based on `state.json.current_phase`. Everything up to the current phase = `completed`, the current phase = `in_progress`, everything after = `pending`. The Phase 5 sub-items are added only if currently in Phase 5.

7. **Failure modes**: if `TodoWrite` is unavailable (host without the tool), continue without it — do NOT block the pipeline. The chat Progress channel is still primary.
