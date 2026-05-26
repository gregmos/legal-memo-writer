# Template: research-summary-only

**Status: VESTIGIAL.** No skill path leads to this template any more. The Phase 7.5 heartbeat gate that fed it (the "Research summary only" option) was removed in v0.0.43 along with Phase 8 Branch A. The file remains on disk for backward compatibility with any external tooling that scans the templates directory and for legacy state.json export. Do NOT manually invoke this template — the supported set is `classical-memo` (Full mode) and `executive-brief` (Brief mode) as of v0.0.45.

The content below is preserved as documentation of how the template was structured. The `md_to_docx.py` script still recognises `final_status == "fallback_research_summary_delivered"` on legacy state files so older completed tasks still export correctly.

**Original use (deprecated):** the user picked "Research summary only" at the Phase 7.5 heartbeat gate. The pipeline had NOT run revision-loop (Phase 9) or client-readiness (Phase 10); legal conclusions are deliberately NOT validated. The deliverable reports research findings, identifies open issues, and stops short of recommendations.

This template was **never** chosen by the Phase 3 classifier. It was set by Phase 8 ONLY when `state.json.heartbeat_choice == "research_summary_only"`.

## Required sections (in this order)

1. **Title** — bold, format `<Subject>: Research summary (no legal conclusions)`. The parenthetical is mandatory so the reader cannot misread the document as an opinion.
2. **Header block** — date (YYYY-MM-DD), jurisdictions, one-line query restatement, template name (`research-summary-only`), and the line `Status: research findings only — analysis not validated through the revision loop`.
3. **Banner block** *(injected by Phase 11 export, do not add manually)* — the documented always-deliver banner: "Research summary mode — full IRAC analysis not performed per user choice. The memo reports findings only; legal conclusions are not validated through the revision loop."
4. **Context** — 1 short body paragraph: who asked, what was asked, what was researched, what was deliberately NOT done.
5. **Scope of research** — bulleted list:
   - Researchers dispatched (statutory / case-law / doctrinal, per `state.json.config.researcher_set`).
   - Source pack location (`research/source-pack.md`).
   - Currency check outcome (or `not run` if Phase 6 was skipped).
6. **Findings by issue** — one numbered subsection per planned issue from `plan.md`. Each subsection contains:
   1. **Issue statement** — 1 sentence restating the planned question.
   2. **Sources found** — bulleted list of primary acts / cases / regulatory guidance discovered, each with full citation and (where available) a URL to the canonical portal. NO paraphrase of legal effect.
   3. **Verbatim source quote(s)** — markdown blockquote, source's original language, ≤ 60 words combined per issue. At least one quote per issue if any source was found.
   4. **Open questions** — bulleted list of variables that would need to be resolved before a conclusion could be reached (facts, conflicting authority, currency uncertainty, missing sub-jurisdiction).
   5. **NO "Risk assessment" line.** NO recommendation. The reader is being told what was *found*, not what to *do*.
7. **What was NOT done** — explicit short list:
   - Revision loop (5-reviewer or 3-reviewer JSON cycle) — skipped per user choice.
   - Client-readiness review — skipped.
   - Counter-argument stress test — skipped.
   - Citation audit — skipped (citations are listed as found, not as validated).
8. **Next steps the user can take** — 3-5 bullets, framed as actions the user (not the pipeline) should take:
   - "Run /memoforge:memo again in Full mode for IRAC analysis of issue <N>."
   - "Provide answers to the open questions listed under issue <N>." etc.
9. **Sources** — numbered list with full bibliographic info (same format as `executive-brief`). Reuse `research/source-pack.md` content here.

## Tone

Descriptive, not advisory. Use phrases like "the act provides…", "the court held…", "the regulator's guidance states…". AVOID "you should…", "we recommend…", "the risk is…". When in doubt, quote the source and stop.

## Length guidance

No hard cap. Typical length 1500-3500 words depending on the number of issues and source density. Do NOT pad with analysis — when you run out of *found* sources for an issue, mark it `Sources: none located in this research pass` and move on.

## Rules

- Every factual claim about a source MUST have either a verbatim quote or a citation pointing back to `research/*.md`. No claims sourced from the writer's prior knowledge.
- Every "open question" bullet MUST identify what kind of variable is missing (fact, authority, currency, jurisdiction).
- DO NOT include a "Risk" subsection in any issue — that field belongs to validated memos, not summaries.
- DO NOT include a "Recommendation" section above the "Next steps the user can take" list — the absence is intentional.
- The banner block above the Context section is injected by Phase 11 export — the writer MUST NOT type it manually. Leave a placeholder `<!-- BANNER: injected at export --> ` line if you need to mark its position.
- See `lib/prose-style.md` for citation format, definition format, anti-patterns. Tone overrides above take precedence over house-style "deliverability" guidance because this document is *not* a deliverable opinion.

## What goes in the warning banner

The banner is mandatory for this template (set by `state.json.fallback_banners[]` at Phase 7.5 when `heartbeat_choice = research_summary_only`). It is rendered as a yellow callout at the top of the docx by `md_to_docx.py`. The text is fixed by `always-deliver.md`:

> Research summary mode — full IRAC analysis not performed per user choice. The memo reports findings only; legal conclusions are not validated through the revision loop.
