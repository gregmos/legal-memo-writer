# Subagent logging contract

Long-running subagents (those that block the main session for >30 seconds) write per-step progress to a per-subagent log file in the task working directory. This lets the user open the file during a "silent block" to see live progress instead of guessing whether the agent is stuck.

`events.jsonl` (in the same work dir) is separate and remains the authoritative audit log — it is owned by the orchestrator and records phase transitions, fallbacks, and structured retry events. Its schema and event taxonomy live in `events-contract.md`. Subagents emit domain-specific events (e.g. `mcp_ratelimit_fallback`); the orchestrator emits orchestration events (`phase_transition`, `agent_dispatched`, `agent_returned`, `gate_answered`, `validator_ran`). Use `scripts/log_event.py` to append a schema-conformant entry. The `logs/` folder described in this document is **for human debugging during a run**, not for downstream consumption.

## File path

`<work_dir>/logs/<your-name>.log`

One file per subagent. The directory is created on first write (`Write` tool auto-creates parent dirs; `Bash` users should `mkdir -p` first). Researchers write three separate files (`statutory-researcher.log`, `case-law-researcher.log`, `doctrinal-researcher.log`). The memo writer writes `memo-writer.log`. If additional long-running agents (reviewers, mediator) adopt this contract later, each writes its own file named after the agent slug.

## Format

Plain text, one entry per line:

```
# <agent-name> log for task <task_id>
<ISO timestamp> step=<short_slug> detail=<one short line, ≤120 chars>
<ISO timestamp> step=<short_slug> detail=<one short line, ≤120 chars>
```

- **ISO timestamp**: `YYYY-MM-DDTHH:MM:SSZ` (UTC) at write time.
- **step**: short kebab-case slug. Conventions: `start`, `done`, `issue-3-of-7`, `search-<short>`, `outlining`, `assembling`. Keep slugs human-scannable.
- **detail**: one short line describing what you're about to do or what just finished. No verbatim source text, no PII from user facts, no full prompts. Trim long messages to ≤120 chars.

## When to log

At a minimum:

1. **Start** — one line at the very beginning, before any expensive tool call, listing what you received and what you intend to produce.
2. **Each major step** — before starting a chunk of work that will take >30 seconds (one issue, one search batch, one section). Granularity should keep the file under ~30 entries per run.
3. **End** — one final line summarizing what was produced (file paths, counts, gaps).

If your work has natural sub-phases each taking >1 min, log them. If not, just start/middle/end is enough. Do not log every tool call — that creates noise.

## How to append

**Subagents that inherit `Bash`** (no `tools:` allowlist — researchers, source-pack-builder, etc.) — append via `Bash`:

```bash
mkdir -p "<work_dir>/logs"
printf "%sZ step=%s detail=%s\n" "$(date -u +%Y-%m-%dT%H:%M:%S)" "<step>" "<detail>" >> "<work_dir>/logs/<your-name>.log"
```

If the file does not yet exist, the `printf >>` call creates it; the header line is optional but helpful — write it once on the first call:

```bash
[ -f "<work_dir>/logs/<your-name>.log" ] || printf "# <your-name> log for task %s\n" "<task_id>" > "<work_dir>/logs/<your-name>.log"
```

**Subagents with a restrictive `tools:` allowlist** (e.g. memo-writer's `Read, Write, Edit`) — use a cumulative `Write` pattern:

1. Maintain an in-memory list of log entries (one string per entry, including the timestamp).
2. On the first log entry of the run, `Write` the file with the header + the first entry.
3. On each subsequent log entry, append to the in-memory list and `Write` the file with the full cumulative content (overwriting). For ≤30 short entries the file stays well under 10 KB; the overhead is negligible compared to the agent's own work.

## Failure mode

Logging is **best-effort**. If a log write fails (path unwritable, disk error, Bash unavailable, etc.) — swallow the error and continue your actual work. Never sacrifice output correctness for logging. Do NOT retry the log write; do NOT escalate to the orchestrator. The orchestrator's `events.jsonl` already records phase-level failures.

## What NOT to log

- Verbatim source text (statutes, judgments, doctrine passages). Sources belong in `research/raw/` and `research/<name>.md`.
- PII or sensitive content from `intake/user-facts.md` or the user's query.
- Full prompts received from the main session.
- Stack traces or tool error dumps (these belong in `events.jsonl` at the orchestrator level if escalated).

If you find yourself wanting to log >120 chars on a single `detail=`, the right move is usually a shorter summary plus a file path the user can open if they want full context.

## Tier 2 — Structured tool-call telemetry (v0.7.0+)

In addition to the plain-text human-readable log above (Tier 1), agents that make external tool calls (MCP, WebSearch, WebFetch) ALSO append a structured JSONL entry per call to a sibling file:

`<work_dir>/logs/<your-name>-tools.jsonl`

Tier 1 is for human debugging during a run. Tier 2 is machine-readable per-call telemetry — kept structured so future tooling can parse it deterministically (event counts, latency distributions, rate-limit patterns) without re-scanning prose logs. Both files are best-effort and independent — a failure in one does not affect the other.

### Schema (one JSON object per line)

```jsonc
{
  "ts": "<ISO 8601 UTC, e.g. 2026-05-26T14:23:11Z>",
  "tool": "<full tool name, e.g. mcp__plugin_memoforge_legal-data-hunter__search | WebSearch | WebFetch>",
  "category": "mcp | websearch | webfetch",
  "query": "<short summary of args, ≤120 chars; NEVER the full argument blob>",
  "topic_key": "<short kebab-case slug for grouping reformulation attempts, e.g. eu-aiact-art-14>",
  "result": "ok | empty | error | ratelimited | timeout",
  "latency_ms": <int>,
  "result_size_hint": null | <int>,                   // e.g. number of search results returned, or response byte length for WebFetch
  "selected_url": null | "<URL chosen for follow-up fetch, if applicable>",
  "fallback_used": null | "<short kebab-case reason if this was a fallback path>",
  "iteration": null | <int>                            // state.json.current_iteration if inside revision_loop, else null
}
```

All fields are required to be present (use `null` where not applicable). Unknown values pass through as `null` — do not invent.

### Which agents emit Tier 2

- **Researchers** (statutory, case-law, doctrinal) — every MCP call (Legal Data Hunter, CourtListener), every WebSearch, every WebFetch.
- **currency-checker** — every MCP/web call used to verify source currency.
- **citation-auditor** — every WebFetch call used to verify citations against canonical sources.

Reviewers (logic/clarity/style/counterargument/research-sufficiency/client-readiness) and orchestration agents (revision-mediator, source-pack-builder, memo-writer when it stays inside the work_dir, fact-assumption-analyst) do not make external tool calls. They do not emit Tier 2.

If memo-writer or another agent makes an unexpected WebFetch for citation lookup, it MAY emit Tier 2 — same schema, same best-effort discipline.

### How to emit

Agents that inherit `Bash` — append via `Bash`:

```bash
mkdir -p "$WORK_DIR/logs"
printf '{"ts":"%s","tool":"%s","category":"%s","query":"%s","topic_key":"%s","result":"%s","latency_ms":%d,"result_size_hint":%s,"selected_url":%s,"fallback_used":%s,"iteration":%s}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "<tool>" "<category>" "<query summary>" "<topic_key>" "<result>" <latency_ms> \
  "<size or null>" "<\"URL\" or null>" "<\"reason\" or null>" "<int or null>" \
  >> "$WORK_DIR/logs/<your-name>-tools.jsonl"
```

Agents with restricted toolset (no Bash) — use the same cumulative `Write` pattern documented for Tier 1: maintain an in-memory list of JSONL strings, `Write` the full content on each emission.

Atomicity is NOT required (single JSONL line writes are effectively atomic on POSIX append; on Windows the append boundary is usually safe at this granularity, and a torn line gets discarded by the extractor's JSON parser).

### Topic-key heuristics

`topic_key` is the join field the extractor uses to group reformulation attempts. Compute it deterministically:

- **Statute searches:** `<jurisdiction>-<instrument-shortname>-<article>`, e.g. `eu-aiact-art-14`, `us-cfaa`, `cy-data-protection-art-7`.
- **Case-law searches:** `<jurisdiction>-<court>-<topic-keyword>`, e.g. `eu-cjeu-schrems`, `us-scotus-citizens-united`.
- **Doctrinal searches:** `<topic-keyword-bigram>`, e.g. `dpa-clickwrap`, `joint-controllership`.
- **General WebSearch:** bucket by leading 3-4 keywords lowercased and hyphenated, e.g. `ai-act-art-14`, `gdpr-art-6-paragraph-1f`.

Approximate keys are fine. The extractor uses `topic_key` only for cross-task grouping and tolerates noise.

### Failure mode

Best-effort, same as Tier 1. If a Tier-2 write fails (path unwritable, disk error, malformed args, etc.) — swallow the error and continue. Do NOT retry. Do NOT escalate. Do NOT block the agent's actual work.

### What NOT to log in Tier 2

- The full argument blob of an MCP call (some MCPs accept large JSON; summarize in ≤120 chars).
- The full response body (only `result_size_hint` int, never the bytes).
- PII or user-query text in `query` or `topic_key` (summarize the search intent, not the user's words).
- Stack traces or error dumps (use `result: "error"` and let `events.jsonl`'s orchestrator-level events carry the diagnostic detail).

### Why this is separate from Tier 1

- **Machine-readable.** Tier 2 is structured for deterministic downstream parsing; Tier 1 is prose for humans.
- **Append-only with no rewrite cost.** Bash `>>` is O(1) per line; Tier 1's cumulative-write pattern (for restricted-toolset agents) is O(N) per line.
- **Different audience.** Tier 1 = the user watching a long-running block. Tier 2 = automated tooling that may want per-call telemetry without re-parsing prose.
- **Different lifetime.** Tier 1 is debug-only and discarded after task completion. Tier 2 lives in the task work_dir for the lifetime of that task.

A single tool call MAY produce one Tier-1 line AND one Tier-2 line — they are independent and serve different consumers.
