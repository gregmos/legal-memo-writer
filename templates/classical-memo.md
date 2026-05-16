# Template: classical-memo

**Use when:** deep, multi-issue legal analysis where the reader needs full IRAC treatment, comprehensive context, and an audit trail of reasoning. Default for complex regulatory, transactional, or cross-disciplinary questions.

## Required sections (in this order)

1. **Header** — title, date, jurisdictions, query (1-2 sentences), template name.
2. **Executive Summary** — 3-5 bullets or a short paragraph with main conclusions. Stand-alone readable.
3. **Facts, assumptions and limitations** — facts provided by the user; material assumptions from intake; limitations that affect confidence.
4. **Issues** — numbered list, taken from `plan.md`.
5. **Analysis** — one sub-section per issue, IRAC inside:
   - **Применимое право (Rule)** — statutes, regulations, with inline citations.
   - **Применение к фактам (Application)** — analysis, case law, doctrinal commentary.
   - **Вывод по Issue N (Conclusion)** — focused answer to the issue.
6. **General conclusion and recommendations** — synthesized takeaways across all issues. Include conservative / balanced / aggressive options where useful.
7. **Risks and open questions** — uncertainty surface, manual-check recommendations.
8. **Sources** — numbered list with title, identifier, URL, retrieval date.

## Tone

Formal, analytical, precise. Russian or English depending on query.

## Length guidance

3000-6000 words typical. Don't pad; if an issue is straightforward, its IRAC can be 200-300 words.

## What goes in the warning banner (forced exit / manual review)

If `final_status` is `forced_exit_...` or `manual_review_required_...`, a yellow callout box at the top with the remaining blocking issues from `state.json.remaining_blocking_issues` or the client-readiness review.
