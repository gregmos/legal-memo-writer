# memoforge

> **From one legal question to a finished `.docx` memorandum, with sources cited and contrary authority surfaced — in a single command.**

![version](https://img.shields.io/badge/version-1.0.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) ![for](https://img.shields.io/badge/built%20for-Cowork-purple)

---

## What it does

**memoforge** is a Cowork plugin that turns a research-grade legal question into a structured, footnoted legal memorandum.

It runs a multi-agent pipeline that mirrors how a small legal team produces a memo: a triage analyst clarifies missing facts, three researchers pull primary sources in parallel (statutes, case law, regulator guidance), a currency check confirms the law is still good, a writer produces an IRAC draft, five reviewers stress-test it from different angles (logic, clarity, style, citations, counter-arguments), a mediator consolidates their findings, and the writer revises — up to three rounds — before a client-readiness polish and export to `.docx`.

You ask. The plugin works. You read.

Typical domains it handles well include EU data-protection (GDPR, AI Act, NIS2, DSA), US privacy (CCPA, HIPAA, sectoral), UK consumer law, cross-border compliance questions, and similar regulated-industry research. The pipeline does not assume a specific jurisdiction — it classifies your query and picks researchers accordingly.

---

## What you get

After one command and a few approval clicks, you walk away with:

- **`memo.docx`** — a formatted memorandum (Arial 12pt, 1″ margins, numbered sections, IRAC analysis per issue, footnoted citations).
- **A complete source pack** — every statute, case, and regulator document the analysis relies on, with verbatim quotations and current-as-of dates.
- **Reviewer findings** — JSON files showing what each reviewer flagged, what the mediator kept, and what the writer changed in response.
- **An honest verdict** — the memo is marked `approved`, `forced_exit_on_v3` (revision budget reached with unresolved issues), or `manual_review_required`. No false confidence.
- **A full audit trail** — `state.json`, `events.jsonl`, all draft versions, and the changelog of revisions, so you can show your work to a partner.

---

## Quick start

### 1 · Install

In Cowork: **Settings → Plugins → drag-and-drop `memoforge-1.0.0.zip`** from the [Releases page](../../releases). The plugin auto-registers two bundled MCP servers via `.mcp.json`.

### 2 · Connect the two legal databases

From the plugin panel, click **Connect** next to `legal-data-hunter` (multi-jurisdictional law) and `courtlistener` (US case law). The first call may trigger an OAuth sign-in.

If you skip this step, the pipeline still runs — research falls back to WebFetch against official portals only, and the final memo carries a banner asking you to verify each citation against a primary source.

### 3 · Ask your question

```
/memoforge:memo "Can we process biometric data for minors in the EU under GDPR Art. 9 and Art. 22?"
```

A few more examples that work well:

```
/memoforge:memo "Does our US SaaS need a CCPA notice at collection for B2B-only users?"
/memoforge:memo "Is a click-wrap arbitration clause enforceable against UK consumers under the Consumer Rights Act 2015?"
/memoforge:memo "Risk analysis for using AI to classify employee emails under the EU AI Act."
```

---

## How it works

```
   you             memoforge                            you
    │                  │                                 │
    ▼                  ▼                                 ▼
  query  ──► intake ──► plan ──► research ──► source pack
                                                    │
                                                    ▼
                                             draft  v1
                                                    │
                                            ┌───────┴───────┐
                                            ▼               ▼
                                    5 reviewers       mediator
                                    (parallel)              │
                                            └───────┬───────┘
                                                    │
                                              revise (up to 3×)
                                                    │
                                                    ▼
                                                  polish
                                                    │
                                                    ▼
                                                 memo.docx
```

You choose how thorough to be with one click before the pipeline starts:

| Mode | Pages | Researchers | Reviewers | Revisions | Polish | Best for |
|---|---|---|---|---|---|---|
| **Brief** | 2–3 | statutory only | 3 | 1 | no | Quick check, low-stakes question |
| **Full** | 5–8 | statutory + case-law + doctrine | 5 | up to 3 | yes | Client-facing, contested or novel issues |

A Full-mode run on a complex question takes roughly 60–90 minutes wall-clock and uses heavy parallel work; Brief is faster.

---

## What you'll see along the way

The pipeline pauses **four times** to ask for your input. Everything between pauses runs autonomously, with a live dashboard tracking progress in the sidebar.

1. **Intake card** — up to 10 questions about facts the triage analyst flagged as missing. Answer in chat, or type `proceed` to accept conservative defaults.
2. **Mode pick** — Brief or Full. Pick once per task.
3. **Plan review** — the proposed research plan (jurisdictions, issues, source types). Approve, edit, or cancel.
4. **Source review** — after research and source-pack assembly, a checkpoint to inspect what was found before drafting begins. Continue or cancel.

That is the full set of human touch points. From source-review approval onward, the pipeline finishes on its own and delivers the docx.

---

## Customization — your own house style

By default the writer follows a built-in house style (concise, no em-dashes, OSCOLA-flavoured citations). To override it with your firm's style, the **Style Studio** turns your example memos or written rules into a saved profile:

```
/memoforge:style new my-firm --examples ~/memos/2025-q4/ --mode full
/memoforge:style use my-firm
```

Profiles live in `~/.claude/plugin-data/memoforge/profiles/<name>/` as plain markdown — open and tweak them by hand if you want. When a profile is active, all reviewers defer to your rules; substantive checks (citation accuracy, IRAC structure, contrary authority) remain uniform.

If you never create a profile, the plugin runs identically to its defaults — no extra prompts.

### Where memos land

First writable wins:

1. `$CLAUDE_PLUGIN_OPTION_OUTPUT_FOLDER` (Cowork plugin setting)
2. `$MEMOFORGE_OUTPUT_FOLDER` (env var)
3. `~/Documents/memoforge/` (default)

---

## What it won't do

- **It is not a substitute for a lawyer.** The memo is a research-grade draft. A qualified lawyer must review before any client use, especially for regulated advice.
- **English on the output.** You can ask in other languages but the memo is written in English.
- **It does not interview the client.** The intake step asks about facts you already know; it does not ask follow-up questions about the underlying business.
- **It cannot guarantee currency.** The currency-check phase is best-effort against the connected databases. For litigation-sensitive citations, verify each judgment is still good law before relying on the memo.

---

## Privacy and data

Everything memoforge writes lives **on your machine**, inside the output folder you chose (defaults to `~/Documents/memoforge/`). There is no shared backend, no server, no telemetry uploaded anywhere.

MCP calls go through the connectors you authenticated in Cowork — they reach the providers' servers (Legal Data Hunter, CourtListener, and any official portals you allow via WebFetch) using your credentials. The plugin never proxies or stores credentials itself.

The audit trail (`events.jsonl`, draft versions, reviewer outputs) stays in the task folder until you delete it.

---

## Going deeper

For the canonical orchestrator specification, agent prompts, pipeline contracts, and state-schema, see `skills/memo/references/` inside the plugin. For release history and architecture decisions, see [`CHANGELOG.md`](CHANGELOG.md).

If you want to fork or contribute: the plugin is two skills (`memo`, `style`), one continue/status helper, ~15 agents, and a small library of canonical reference docs. Everything is plain markdown plus a handful of Python scripts for state validation and live-progress HTML rendering.

---

## License and contact

MIT License — see [`LICENSE`](LICENSE).

Author: Grigorii Moskalev. Issues, ideas, or production stories: open a GitHub issue at [github.com/gregmos/memoforge/issues](https://github.com/gregmos/memoforge/issues).
