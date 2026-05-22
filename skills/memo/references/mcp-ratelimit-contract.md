# MCP rate-limit fallback contract

Researcher subagents (`statutory-researcher`, `case-law-researcher`, `doctrinal-researcher`) make heavy MCP calls — primarily to Legal Data Hunter (LDH) and CourtListener. Both services enforce per-account quotas. A typical Full-mode run with three parallel researchers across multiple issues can exhaust these quotas mid-flight, especially on jurisdictions with citation graphs (CJEU, US federal).

This document defines the **mandatory fallback** when an MCP quota is reached. It applies to all researchers and is referenced from each researcher agent file.

## Detection — when this fallback applies

Trigger the fallback **only** when an MCP tool call returns an error containing one or more of these signals:

- HTTP `429 Too Many Requests`
- explicit "rate limit", "rate-limited", "throttle", "throttled", "quota exceeded", "too many requests" phrasing
- documented per-minute / per-hour exhaustion responses from LDH or CourtListener

**Do NOT** treat as a rate limit:
- a single transient timeout (retry once with a few-second pause first)
- a 4xx error other than 429 (malformed input, authentication, not-found — these are bugs, not quotas)
- an empty result set ("no documents matched" is a legitimate finding, not throttling)

If unsure, prefer one retry with backoff before assuming rate-limit. If the second call returns the same quota-like signal, fall back.

## Fallback procedure

Once a rate limit is confirmed:

1. **Stop calling that MCP service for the rest of the run.** Retrying within the same minute compounds the throttle and burns tool calls. Treat the service as unavailable for the remainder of this research session.

2. **Switch to the WebSearch + WebFetch path already documented in your `## WebSearch discovery boundaries` section.** That path is:
   - Use `WebSearch` to find the **canonical identifier or URL** (CELEX number, eur-lex / ecfr.gov / govinfo / official-court-site URL, EDPB document number, etc.).
   - Use `WebFetch` on that canonical URL to retrieve the authoritative text.
   - The citation still points to the canonical URL, **not** the WebSearch result page.

3. **Mark each fallback-sourced item explicitly** in your output `research/<your-output>.md`. Append the tag `[rate-limited fallback]` next to the tier marker on the source's bullet. Example:
   ```
   - Tier-1 [rate-limited fallback]: Regulation (EU) 2024/1689 (EU AI Act), Art. 14(4) — fetched from eur-lex.europa.eu via WebFetch after LDH quota was reached at issue 3.
   ```
   This makes the fallback transparent for the `citation-auditor` and the user.

4. **Record in the `## Methodology` section of your output file.** One short paragraph: which MCP service hit its limit, approximately at which point in your run (e.g. "at issue 3 of 7"), and how many items in the file were retrieved via the fallback path.

5. **Append a structured event to `events.jsonl`** so the orchestrator can detect the fallback for the docx banner. You inherit `Bash`:
   ```bash
   printf '{"ts":"%sZ","event":"mcp_ratelimit_fallback","agent":"<your-name>","service":"<ldh|courtlistener>","items_fallback":<count>}\n' \
     "$(date -u +%Y-%m-%dT%H:%M:%S)" >> "<work_dir>/events.jsonl"
   ```

6. **Also log the fallback step in your per-agent log** (per `logging-contract.md`):
   ```
   <ISO ts> step=ratelimit-fallback detail=<service> quota hit at issue <N>; switching to WebSearch+WebFetch for remaining items
   ```

## Hard floor — when even the fallback is not enough

If WebSearch is also unavailable, or if `WebFetch` of a canonical URL fails (network, paywall, geo-block), do NOT silently drop the citation. Instead:

- Record the source in `## Considered but excluded` with reason "MCP rate-limited AND WebFetch failed for canonical URL — manual fetch required".
- Continue with the remaining issues so the run completes; the sufficiency-reviewer will flag the gap.
- Do NOT cite a WebSearch result snippet as a source. The discovery-vs-citation distinction stays absolute.

## Citation policy stays unchanged

The rate-limit fallback changes **discovery** (how you find sources) and **service routing** (which tool retrieves the text). It does **not** weaken the citation policy:

- Citations still list the canonical issuing-body URL.
- WebSearch snippets, blog posts, summaries, vendor pages, LinkedIn — **never** cited.
- The `citation-auditor` audits fallback-sourced items the same way as MCP-sourced items: against the canonical URL.

The only externally visible difference of a fallback item vs. a normally-sourced item is the `[rate-limited fallback]` tag in the analyzed `.md` file and the matching event in `events.jsonl`. Both feed the docx export banner.
