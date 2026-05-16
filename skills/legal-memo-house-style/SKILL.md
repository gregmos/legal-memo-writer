---
name: legal-memo-house-style
description: In-house legal memo style for the legal-memo-writer pipeline. Use when writing legal memo, правовая справка, legal opinion, юридический analysis, contract review, regulatory analysis, compliance check.
---

# House style for legal-memo-writer

Plain-English playbook for consistent style across the legal-memo-writer pipeline. Read by the main session, memo-writer and revision-mediator. Reviewers (logic, clarity, style, citations) do NOT read this skill directly — relevant principles are baked into their system prompts to preserve isolation.

## About the user

- **Role**: in-house legal counsel
- **Company**: <set this in the skill before first run — your company name and registration jurisdiction>
- **Primary jurisdictions in priority order**: Cyprus, EU, US, Switzerland, Hong Kong
- **Working languages**: English (default), Russian (when query is in Russian)

## Memorandum conventions

- Always include Executive Summary as section 1
- Material factual assumptions must be stated early when they affect conclusions
- Cite primary sources first, doctrine second
- Date format: YYYY-MM-DD
- Source citations: full title + URL + retrieval date
- Inline citation format: `[Source name, year, section]`
- IRAC structure (Issue, Rule, Application, Conclusion) for each issue
- Direct quotes ≤15 words; otherwise paraphrase
- One direct quote per source per memorandum maximum
- For client-ready recommendations, prefer a practical matrix where useful: conservative approach / balanced approach / aggressive approach / required actions / optional actions / open risks

## Reviewer priorities (used by revision-mediator)

When reviewers conflict:
1. **Logic ≈ Citations > Style > Clarity**

   Legal correctness and source-grounding outweigh readability. Counterarguments are treated as a legal-risk input: when they identify a real overstatement or hidden assumption, resolve them with the same priority as Logic. If forced to choose between precise-and-complex versus understandable-and-imprecise, choose precise.

## Exit thresholds

- `max_iterations`: 3
- Approval requires **all five** reviewers (logic, clarity, style, citations, counterarguments) to have zero `blocking_issues`, followed by a client-readiness review
- On forced exit (after iteration 3) or `manual_review_required`, the final docx includes a yellow box at the top: "REVIEWER NOTES NOT FULLY RESOLVED" or "MANUAL REVIEW REQUIRED" + a brief list of remaining issues

## Confidentiality

- Do not name specific company clients, specific amounts, or specific internal artifacts in the memo unless explicitly stated in the query
- When in doubt, use generic phrasing: "the company", "the product feature", "the data subject"

## Anti-patterns

- Avoid em dashes (use commas or parentheses)
- Avoid AI-tells: "delve into", "it is important to note", "furthermore", "navigate the landscape", "in today's world", "tapestry", "robust", "leverage" (as verb)
- Avoid Russian filler openers: "В современном мире...", "В наше время..."
- Avoid vague attributions: "some scholars argue...", "it is generally accepted..."
- Avoid decorative Latin without legal necessity (`mutatis mutandis`, `inter alia`, `prima facie` only when they add substance)
- Avoid promotional language ("groundbreaking", "comprehensive analysis")
- Avoid hedging when the law is clear; hedge only where there is genuine legal uncertainty

## Output format conventions

- Heading hierarchy: H1 (memo title), H2 (numbered sections like "1. Executive Summary"), H3 (sub-sections like "4.1. Issue 1"), H4 (IRAC labels in Russian: **Применимое право (Rule)**)
- Lists: bullet for parallel enumerations; numbered for sequential or prioritized items
- Source citations grouped at the end in a numbered list with full bibliographic info
- For forced-exit or manual-review memos, the yellow warning box is rendered as a callout block in docx (background color `#FFF3CD`, border `#FFE69C`)
