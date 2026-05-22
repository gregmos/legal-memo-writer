# legal-memo-writer

> Multi-agent legal memo drafting plugin for **Claude Cowork** (primary) and **Claude Code** (best-effort).
> Takes a free-form legal question, runs the full lawyer workflow — intake, research, drafting, review, polish — and ships a finished `.docx` memo.

**Version:** `0.1.0` · **Author:** Grigorii Moskalev · **License:** MIT

---

## What it does

You ask one legal question. The plugin runs a 15-agent pipeline that mimics how a real legal team produces a memo:

1. **Triage** — figures out what facts are missing and asks you for them.
2. **Plan** — picks a template, decides which jurisdictions and sources to search, and asks you to approve.
3. **Research** — three researchers run in parallel: statutes, case law, doctrine/regulator guidance.
4. **Sufficiency + currency check** — verifies the sources are enough and still current law.
5. **Draft** — writes the memo in IRAC structure with full citations.
6. **Review** — up to 5 specialist reviewers (logic, style, clarity, counter-arguments, citations) stress-test the draft.
7. **Mediation** — a mediator consolidates reviewer feedback and the writer revises (up to 3 rounds).
8. **Client-readiness polish** — final check before delivery.
9. **Export** — saves a formatted `.docx` and the full source pack to your output folder.

You get a memo that cites real statutes and judgments, names contrary authority, gives a concrete risk score per issue, and ends with actionable recommendations — not generic "consult a lawyer" hedges.

**Languages:** Ask in English (other major languages best-effort). The memo is written in the language of your query.

---

## Quick start

### 1. Install

**Cowork:** Settings → Plugins → drag-and-drop `legal-memo-writer-0.1.0.zip` from the [Releases page](../../releases), or install via marketplace.

**Claude Code (local dev):**
```bash
git clone https://github.com/gregmos/legal-memo-writer.git
claude --plugin-dir ./legal-memo-writer
```

The bundled MCP servers (Legal Data Hunter for multi-jurisdictional law, CourtListener for US case law) auto-register via `.mcp.json`. First MCP call may trigger an OAuth sign-in flow in the browser.

### 2. Run

```
/legal-memo-writer:memo "<your legal question>"
```

Examples:
- `/legal-memo-writer:memo "Can we process biometric data for minors in the EU under GDPR Art. 9 and Art. 22?"`
- `/legal-memo-writer:memo "Does our US SaaS need a CCPA notice at collection if we only have B2B users?"`
- `/legal-memo-writer:memo "Is a click-wrap arbitration clause enforceable against UK consumers under the Consumer Rights Act 2015?"`

### 3. Reply at the three checkpoints

The pipeline pauses three times. Reply with `/legal-memo-writer:continue <task_id> <action>`:

| Phase | What you'll see | How to reply |
|---|---|---|
| **Intake** | Up to 5 questions about missing facts | `answer: <facts>` or `proceed` (use defaults) |
| **Mode pick** | Choose Brief vs Full | `mode: brief` or `mode: full` |
| **Plan review** | The proposed research plan (jurisdictions, sources, issues) | `approve`, `edit: <instructions>`, or `cancel` |

After plan approval, the rest runs autonomously. You'll see live progress messages at each phase.

### 4. Get the memo

Output lands in (first that exists):
1. `$CLAUDE_PLUGIN_OPTION_OUTPUT_FOLDER/<task_id>/`
2. `$LEGAL_MEMO_OUTPUT_FOLDER/<task_id>/`
3. `~/Documents/legal-memos/<task_id>/` (default)

Files you'll find there:
- `memo.docx` — the final memo, formatted (Arial 12pt, 1" margins, numbered sections)
- `drafts/v*.md` — every draft revision
- `research/` — statutes, case law, doctrine notes, source pack
- `reviews/` — every reviewer's findings (JSON)
- `state.json` — full pipeline state
- `events.jsonl` — audit log

---

## Commands

| Command | What it does |
|---|---|
| `/legal-memo-writer:memo "<query>"` | Start a new memo |
| `/legal-memo-writer:continue <task_id> <action>` | Reply to an open checkpoint or resume a paused task |
| `/legal-memo-writer:status [<task_id>]` | Show phase, progress, blockers for one task or list all tasks |

`<task_id>` is the slug of the working directory (e.g. `memo-20260522T143010Z`). The pipeline prints it when the task starts.

---

## Modes — Brief vs Full

You pick the mode at the second checkpoint. Both produce a real memo with citations; they differ in depth.

|  | **Brief** | **Full** |
|---|---|---|
| Template | `executive-brief.md` | `classical-memo.md` |
| Target length | 1–3 pages | 5–15 pages |
| Researchers | Statutes + case law (doctrine optional) | All three in parallel |
| Reviewers | 3 (logic, citations, client-readiness) | 5 (all) |
| Revision rounds | 1 | up to 3 |
| Use case | Quick risk read for a known issue | Pre-launch sign-off, regulator response, cross-jurisdictional question |
| Typical runtime | 15–25 min | 40–50 min |

Mid-run switching is not supported — cancel and rerun if you picked the wrong mode.

---

## The pipeline — phase by phase

```
   ┌──────────────────────────────────────────────────────────────┐
   │  Phase 1   Task setup (resolve output folder, create state)  │
   │  Phase 2   Intake — fact-assumption-analyst                  │
   │  Phase 2a  ⏸  User checkpoint: answer or proceed             │
   │  Phase 3   Classification + template selection               │
   │  Phase 4   Research plan                                     │
   │  Phase 4a  ⏸  User checkpoint: approve / edit / cancel       │
   │  Phase 5   Parallel research (3 agents)                      │
   │  Phase 6   Research sufficiency review                       │
   │  Phase 7   Currency check + source pack build                │
   │  Phase 7.5 ⏸  Optional checkpoint: continue / summary-only   │
   │  Phase 8   Drafting — memo-writer                            │
   │  Phase 9   Revision loop — 5 reviewers + mediator (×N)       │
   │  Phase 10  Client-readiness polish                           │
   │  Phase 11  Export to .docx                                   │
   └──────────────────────────────────────────────────────────────┘
```

State persists between turns in `state.json` inside the work directory. If the host session dies, `/legal-memo-writer:continue <task_id>` resumes from the last completed phase.

---

## The agents — what each one does

The main session orchestrates; specialized worker subagents do the actual work. Plugin-shipped subagents cannot spawn other subagents (Anthropic security sandbox), so the orchestrator dispatches them via the `Agent` tool.

### Intake (Phase 2)
| Agent | Role |
|---|---|
| **fact-assumption-analyst** | Reads the query, identifies missing facts that would change the answer, drafts safe default assumptions, and produces up to 5 must-answer intake questions. |

### Researchers (Phase 5, parallel)
| Agent | Role |
|---|---|
| **statutory-researcher** | Primary normative acts: statutes, regulations, directives, secondary legislation. Routes through Legal Data Hunter MCP first; falls back to eCFR/govinfo via WebFetch for US. |
| **case-law-researcher** | Judgments, decisions, opinions. US case law goes to CourtListener MCP; multi-jurisdictional case law to Legal Data Hunter. Structures findings as prevailing / conflicting / recent positions. |
| **doctrinal-researcher** | Activated only when the plan calls for it. Searches regulator guidance (EDPB, national DPAs, etc.), soft law, and peer-reviewed academic commentary. The only researcher allowed to cite third-party authoritative sources for primary-law-adjacent material. |

### Quality gates (Phases 6–7, 11)
| Agent | Role |
|---|---|
| **research-sufficiency-reviewer** | Checks every planned issue has enough primary sources, contrary authority, and explicit gaps before drafting starts. |
| **currency-checker** | Verifies sources are still current law: cross-references between acts, status of cited judgments, age of doctrinal guidance, URL reachability. Produces a blocking / non-blocking report. |
| **source-pack-builder** | Consolidates research and currency reports into a structured evidence table the writer and citation auditor work from. After this, no later agent discovers new sources (source-pack freeze). |
| **citation-auditor** | After drafting, audits every citation against the source pack — verifies the claim is grounded, the paraphrase matches the source, and currency-blocking sources weren't cited. |

### Drafting (Phase 8)
| Agent | Role |
|---|---|
| **memo-writer** | Writes (v1) or rewrites (vN) the memo per the selected template (executive-brief or classical-memo). Produces IRAC analysis per issue, full citations, risk scores, and recommendations. Reads `state.json` to honor mode, assumptions-accepted flag, and currency-blocked sources. |

### Reviewers (Phase 9, run in parallel)
Five specialists in Full mode, three in Brief. Each returns a structured JSON report with `blocking_issues[]` and `improvements[]`.

| Agent | What they check |
|---|---|
| **logic-reviewer** | IRAC soundness, premise-conclusion validity, inter-issue consistency, risk-score drift across sections, Material Assumption ↔ Open Question mapping. |
| **citation-auditor** | Every normative / case / doctrinal claim is grounded, paraphrases match sources, currency-blocked sources respected. |
| **style-reviewer** *(Full only)* | AI-tells, em-dash overuse, vague attributions, heading discipline (no questions, no skip-jumps), `(§ N)` cross-references, action-verb recommendations. |
| **clarity-reviewer** *(Full only)* | Sentence length (≤40 words), paragraph length (≤3 sentences / 100 words), jargon-without-explanation, accessibility for a non-lawyer business stakeholder, per-section length proportionality. |
| **counterargument-reviewer** *(Full only)* | Contrary authority, overconfidence at medium verdicts, trigger conditions for counter-arguments that don't prevail. |

### Mediation & polish (Phases 9–10)
| Agent | Role |
|---|---|
| **revision-mediator** | Consolidates parallel reviewer JSONs into a single actionable revision list for the writer. Resolves reviewer conflicts via house-style priority (logic ≈ citations > style > clarity). Decides whether another iteration is needed. |
| **client-readiness-reviewer** | Final external-client gate. Checks tone, disclaimers, confidentiality, recommendation quality, and whether the memo ships with minimal manual edits. In Brief mode, also runs the style / clarity / counter-argument safety-net checks that were skipped earlier. |

---

## Skills

The plugin ships six skills. Three are entry points (slash commands), three are auto-loaded methodology.

| Skill | Type | Purpose |
|---|---|---|
| `memo` | Entry (`/legal-memo-writer:memo`) | Main orchestrator. Loaded once at task start, drives the whole pipeline. |
| `continue` | Entry (`/legal-memo-writer:continue`) | Reply to checkpoints or resume a paused task. |
| `status` | Entry (`/legal-memo-writer:status`) | Inspect one task or list all tasks. |
| `legal-memo-prose-style` | Auto-invoked | House style: tone, four-beat Risk pattern, definitions format, anti-AI-tells, reviewer conflict priorities. Edit this file to customize style. |
| `legal-memo-docx-render` | Auto-invoked (Phase 11) | DOCX export: Arial 12pt, 1" margins, blockquote indent, optional yellow warning banner. Uses `md_to_docx.py` (python-docx) with Pandoc as fallback. |
| `revision-loop` | Auto-invoked (Phase 9) | Methodology for the mode-aware revision loop (3 reviewers Brief, 5 Full; 1 iter Brief, up to 3 Full). |

---

## MCP and web search policy

Single source of truth: `skills/memo/references/pipeline-contract.md §WebSearch`.

- **Bundled MCPs:** Legal Data Hunter (`https://legaldatahunter.com/mcp`), CourtListener (`https://mcp.courtlistener.com`).
- **Primary law search:** MCPs first. Legal Data Hunter for broad multi-jurisdictional sources; CourtListener for US case law, PACER/RECAP dockets, citation networks, and citation verification.
- **WebSearch:** discovery only (find CELEX numbers, docket IDs, canonical URLs, news of amendments). **WebSearch results MUST NEVER be cited as the source of a legal claim.** The canonical text is retrieved via MCP or WebFetch on the discovered official URL.
- **`doctrinal-researcher` exception:** may cite WebFetch results from official regulator guidance, peer-reviewed journals, SSRN-style repositories, and authoritative soft-law sources.
- **MCP unavailable:** WebFetch against known official portals. If no canonical URL is available, the gap is documented explicitly — never fabricated.
- **MCP rate-limited:** back off once with same query, then WebFetch on canonical URLs. Logs `mcp_ratelimit_fallback` event and surfaces a partial-research banner in the memo.

---

## Customization

### House style
Edit `skills/legal-memo-prose-style/SKILL.md` to change:
- Default jurisdictions priority
- Reviewer conflict priorities (default: logic ≈ citations > style > clarity)
- Tone and confidentiality rules
- Anti-patterns to avoid

In Cowork: edit at `~/.claude/plugins/cache/legal-memo-writer/skills/legal-memo-prose-style/SKILL.md`.
In Claude Code dev mode: edit the file directly in your plugin source directory.

### Output folder (resolution order)
1. `CLAUDE_PLUGIN_OPTION_OUTPUT_FOLDER` (set in Cowork plugin settings)
2. `LEGAL_MEMO_OUTPUT_FOLDER` (env var)
3. `~/Documents/legal-memos/` (default)

---

## Live progress

The plugin emits **at least 17 chat progress messages** in a Full run — phase transitions, agent dispatches, gate answers, validator runs. File references in chat are plain text; clickable artifact cards come from the host's tool-call UI (Cowork's Read/Write/Edit indicators).

Every task also writes an audit log at `<work_dir>/events.jsonl` — JSONL events for `phase_transition`, `agent_dispatched`, `agent_returned`, `gate_answered`, `validator_ran`, and Tier-0 events (`task_created`, `mcp_precheck_result`, `mode_selected`, `mcp_ratelimit_fallback`, etc.). Useful for debugging or replaying a pipeline run.

---

## Always-deliver invariant

Every termination path produces a user-facing artifact. If the docx export fails, the plugin falls back to:
1. Pandoc-based docx render
2. Plain markdown delivery (last resort)

You never end a session with nothing. See `skills/memo/references/always-deliver.md` for the full fallback matrix.

---

## Known limitations

- **No cross-task memory.** Each memo is a fresh task; the plugin does not learn from prior memos.
- **HITL UI** depends on the host. Cowork shows interactive widgets via `visualize:show_widget`; Claude Code falls back to text/file-based checkpoints.
- **Three mandatory user checkpoints** in the default path: intake (Phase 2a), mode (Phase 1.5), plan (Phase 4a). Two optional gates: heartbeat (Phase 7.5) and pre-polish (Phase 9/10).
- **Pandoc docx fallback** is best-effort; primary path is `md_to_docx.py` via python-docx.
- **No generic WebSearch fallback** for statutes / case law when MCP is down. Either canonical primary source via WebFetch, or the gap is reported explicitly.
- **Mid-run mode switching** is not supported — cancel and rerun in the other mode.
- **Claude Code state persistence** between turns differs from Cowork; v0.1.0 guarantees Cowork, Claude Code is best-effort.

---

## Repo layout

```
legal-memo-writer/
├── .claude-plugin/plugin.json     # Plugin manifest
├── .mcp.json                      # Bundled MCP servers (Legal Data Hunter, CourtListener)
├── agents/                        # 15 worker subagents
├── skills/                        # 6 skills (3 entry, 3 auto)
├── templates/                     # classical-memo, executive-brief, research-summary-only
├── scripts/                       # log_event.py, validators, tests
├── dist/                          # Build artifacts (gitignored, except releases)
├── README.md
└── CHANGELOG.md                   # Version history
```

---

## Versioning

Plugin version is the single source of truth in `.claude-plugin/plugin.json`. The README badge, the latest `dist/*.zip` filename, and the latest `git tag` MUST match. CHANGELOG follows a relaxed [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contributing

Issues and PRs welcome. For non-trivial changes, please open an issue first to discuss the approach. Run `python3 -m unittest discover -s scripts/tests` before submitting.
