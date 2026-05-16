# legal-memo-writer

Multi-agent plugin for **Claude Cowork** (primary) and **Claude Code** (best-effort) that automates legal memo drafting: intake questions -> classification -> research -> sufficiency review -> source pack -> currency check -> drafting -> 5-reviewer revision loop -> client-readiness review -> docx export.

Version: **0.0.2**

## What it does

Takes a free-form legal query (RU/EN), performs preliminary legal triage, asks the user for missing facts or permission to proceed on assumptions, classifies the request, picks a memo template, builds a research plan, asks the user to approve/edit/cancel the plan, runs parallel research (statutes / case law / doctrine), checks research sufficiency, builds a structured source pack, checks source currency, drafts the memo, runs 5 independent reviewers (logic / clarity / style / citations / counterarguments) with a mediator (up to 3 iterations), runs a final client-readiness review, then exports a docx.

## Setup

### Cowork (primary)

1. Install plugin: Settings -> Plugins -> marketplace identifier OR drag-and-drop ZIP.
2. Legal Data Hunter and CourtListener are bundled by the plugin through `.mcp.json`; the user should not need to add them manually in Connectors:
   ```json
   {
     "mcpServers": {
       "legal-data-hunter": {
         "type": "http",
          "url": "https://legaldatahunter.com/mcp"
        },
        "courtlistener": {
          "type": "http",
          "url": "https://mcp.courtlistener.com"
        }
     }
   }
   ```
   The first MCP tool use may still prompt for OAuth/sign-in; authentication cannot be pre-bundled in the plugin.
3. Legal Court is not bundled. For US case law, PACER/RECAP dockets, citation networks, and citation verification, the pipeline uses the official CourtListener MCP from Free Law Project.
4. Verify `/legal-memo-writer:memo` is available in a new Cowork task.
5. Test run: `/legal-memo-writer:memo "test query"` -- pipeline should reach plan review and wait.

### Claude Code (best-effort)

1. Install: `claude plugin install legal-memo-writer@<marketplace>` or `claude --plugin-dir ./legal-memo-writer` for local dev.
2. Legal Data Hunter and CourtListener are bundled by the plugin through `.mcp.json`; no separate `claude mcp add ...` command is required. OAuth flow triggers in browser on first use if the user is not already authenticated.
3. Legal Court is not required. The default US case-law/PACER path is the official CourtListener MCP.
4. Verify inside a Claude Code session with `/mcp` after the plugin is enabled. `claude mcp list` reports user/project MCPs and may not show plugin-provided servers before the plugin session is loaded.
5. Test: `/legal-memo-writer:memo "test query"`.

**Caveat:** state-persistence between turns in Claude Code interactive CLI mode may differ from Cowork. v0.0.2 guarantees Cowork only; Claude Code is best-effort.

## Usage

```
/legal-memo-writer:memo "<your legal question, RU or EN>"
/legal-memo-writer:continue <task_id>
/legal-memo-writer:status [<task_id>]
```

After a `memo` invocation, the main session first asks intake questions, then writes a plan and asks for confirmation. Reply with:
- `/legal-memo-writer:continue <task_id> answer: <facts>` -- answer intake questions
- `/legal-memo-writer:continue <task_id> proceed` -- proceed on default assumptions
- `/legal-memo-writer:continue <task_id> approve` -- proceed
- `/legal-memo-writer:continue <task_id> edit: <instructions>` -- modify the plan
- `/legal-memo-writer:continue <task_id> cancel` -- stop

`continue` and `status` operate on `task_id` (slug of the working directory).

## User-visible progress

The plugin prints progress updates at each major phase: intake, plan approval, research, sufficiency, currency check, source pack, drafting, every revision iteration, client-readiness, and export. Full artifacts are saved under `${CLAUDE_PLUGIN_DATA}/work/<task_id>/`; the chat shows phase, next action, artifact paths, verdicts, counts, and blockers.

## MCP and web search policy

- Bundled MCPs: Legal Data Hunter at `https://legaldatahunter.com/mcp`; CourtListener at `https://mcp.courtlistener.com`.
- Primary law search: Legal Data Hunter for broad multi-jurisdictional legislation/case law/doctrine; CourtListener for US case law, PACER/RECAP dockets, citation networks, case status, and citation verification.
- Generic WebSearch is prohibited for statutes, regulations, case law, and case status. If MCP is unavailable, use WebFetch only against known official portals or URLs returned by MCP/research files; otherwise report an explicit gap.
- Doctrine/guidance search: Legal Data Hunter first. `doctrinal-researcher` may use WebSearch for official regulator guidance, recognized academic/legal journals, SSRN-style academic repositories, and authoritative soft-law sources.
- After `research/source-pack.md` is built, no later writer/reviewer discovers new sources. Remaining gaps go through the one allowed targeted research follow-up or become manual-review warnings.

## Customization

House style lives in `skills/legal-memo-house-style/SKILL.md`. Edit it to change:
- Default jurisdictions priority
- Reviewer conflict priorities (default: logic ~= citations > style > clarity)
- Confidentiality rules
- Anti-patterns to avoid

In Cowork: edit through plugin UI or directly at `~/.claude/plugins/cache/legal-memo-writer/skills/legal-memo-house-style/SKILL.md`.
In Claude Code dev mode: edit the file in your plugin source directory.

Output folder for docx is read from `CLAUDE_PLUGIN_OPTION_OUTPUT_FOLDER`, then `LEGAL_MEMO_OUTPUT_FOLDER`, then defaults to `~/Documents/legal-memos/`.

## Architecture

- Main session loads `skills/memo/SKILL.md` and orchestrates the pipeline directly. Plugin-shipped subagents cannot spawn other subagents (Anthropic security sandbox), so orchestration runs in the main session.
- 15 worker subagents in `agents/`: intake analyst, 3 researchers, research-sufficiency reviewer, source-pack builder, currency-checker, memo-writer, 5 reviewers, mediator, client-readiness reviewer.
- 6 skills: `memo`, `continue`, `status` (entry skills with `disable-model-invocation: true`); `revision-loop` (methodology); `legal-memo-house-style` (auto-invocable house style); `legal-memo-style` (docx export instructions + `scripts/md_to_docx.py`).
- State persists in `${CLAUDE_PLUGIN_DATA}/work/<task_id>/` between turns.
- Legal Data Hunter and CourtListener MCPs are bundled in `.mcp.json` as plugin-provided MCP servers.

## Known limitations (v0.0.2)

- No long-term memory between separate memo tasks.
- No interactive UI widgets (text/file-based HITL only).
- Two user checkpoints: intake questions and plan review. Mediator output is applied automatically.
- Pandoc fallback for docx export is best-effort; primary path is `scripts/md_to_docx.py` via python-docx.
- For statutes and case law, no fallback to generic WebSearch when MCP unavailable -- only official primary sources via WebFetch, otherwise gap is reported explicitly.
