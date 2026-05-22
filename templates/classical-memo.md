# Template: classical-memo

**Use when:** deep, multi-issue legal analysis where the reader needs full coverage, comprehensive context, and an audit trail of reasoning. Default for complex regulatory, transactional, or cross-disciplinary questions.

All templates in this plugin share one rhetorical surface — the four-beat Risk subsection pattern from `skills/legal-memo-prose-style/SKILL.md`. `classical-memo` is the longest form and the closest to the canonical legal memorandum shape. The four-beat pattern (description → verbatim source quote → analysis → risk assessment line) is mandatory inside every numbered analytical subsection.

## Required sections (in this order)

1. **Title** — bold, format `<Subject>: <Analytical framing>`. No date or jurisdictions inside the title itself.
2. **Header block** — date (YYYY-MM-DD), jurisdictions, one-line query restatement, template name. Each as its own body paragraph (not a table).
3. **Context** — 1-2 body paragraphs: who is considering what, for what purpose, what this memo analyzes, what is out of scope.
4. **Executive Summary** (`## 1.`) — **bullets ONLY, 3-5 of them, no prose paragraphs.** Each bullet is one concrete conclusion tied to a specific analytical subsection number below, **≤ 2 sentences and ≤ 40 words**, ending with `Risk: <high|medium|low|undetermined>.`. Stand-alone readable. Do NOT mix facts, context, or analytical prose into this section — facts live in `## 3. Facts, assumptions and limitations`; context lives in the unnumbered paragraphs above `## 1.`.
5. **Background and definitions** — domain-specific terms needed to follow the analysis. Each definition as its own short body paragraph in the format `Term — short operational definition.` Skip the section entirely if the audience does not need orientation.
6. **Facts, assumptions and limitations** — facts provided by the user; material assumptions from intake that affect conclusions; limitations that affect confidence. Brief.
7. **Numbered analytical subsections** — one per legal question / risk area. Hierarchical numbering (`1.`, `2.`, `2.1.`, `2.2.`, `3.`). Section headings are bold descriptive noun phrases, not questions. Each numbered analytical subsection follows the four-beat pattern:
   1. **Description** — what the issue is, the controlling provision named and cited.
   2. **Verbatim source quote** — markdown blockquote (`> …`), source's original language, ≤ 30 words.
   3. **Analysis** — 2-4 short paragraphs translating the quoted text into operational consequences for the user's facts, with inline case-law / doctrinal citations.
   4. **Risk assessment line** — new body paragraph beginning with `Risk: high.` / `Risk: medium.` / `Risk: low.` / `Risk: undetermined.`, followed by one-sentence justification and a specific concrete recommendation.
8. **General conclusion and recommendations** — structured list, one item per analytical subsection above, format `<subsection-number / risk label>: <specific action or condition>`. Include conservative / balanced / aggressive options where useful. Material assumptions and open questions listed here as sub-lists.
9. **Sources** — numbered list with full bibliographic info (title, identifier, URL, retrieval date).

## Tone

Formal, analytical, precise. Short declarative sentences. No hedging when the law is clear. English regardless of the query language.

## Length guidance

3000-6000 words typical. Don't pad; a straightforward subsection can be 200-300 words while still containing all four beats (quote + 1-2 sentences each for description, analysis, and risk line).

## Rules

- The four-beat Risk subsection pattern is mandatory in every numbered analytical subsection. Skipping the verbatim source quote because "the rule is well known" is a blocking issue at style review.
- **Executive Summary discipline (blocking at review):** `## 1. Executive Summary` contains **only** 3-5 bullets. No prose paragraphs in this section — neither before, between, nor after the bullets. Each bullet is one short conclusion + `Risk:` line, ≤ 2 sentences and ≤ 40 words. Facts and assumptions belong in `## 3. Facts, assumptions and limitations`; framing/scope belongs in the unnumbered Context paragraphs above `## 1.`.
- **Facts section required (blocking at review):** `## 3. Facts, assumptions and limitations` is required for classical-memo. Skipping it (or merging facts into Executive Summary, Context, or Background) is a structural defect.
- IRAC discipline (Issue, Rule, Application, Conclusion) is the writer's internal logic — **do not surface IRAC labels as visible sub-headings**. The reader sees the four beats, not "Rule" / "Application".
- Each source quoted at most once across the whole memo.
- Inline citation format: `[Source name, year, section]`.
- **Sentence-length cap (hard, blocking at review):** no sentence over 40 words; no sentence chaining more than 2 independent ideas (via `and that …, and that …`, semicolon chains, `while …, and …`, or parallel relative clauses). Verbatim source quotes inside `> blockquote` paragraphs are exempt. See `skills/legal-memo-prose-style/SKILL.md` §Sentence structure Hard limits.
- **Paragraph-length cap (hard, blocking at review):** no paragraph over 3 sentences or 100 words. Each paragraph carries one developed idea; multi-argument "wall of text" paragraphs are a structural defect even when their sentences are within the sentence cap. Verbatim source quotes (`> blockquote`), bullet items, numbered list items, headings, and table cells are exempt. See `skills/legal-memo-prose-style/SKILL.md` §Paragraph structure Hard limits.
- **Cross-section consistency (hard, blocking at review):** risk scores match in three places per subsection (Exec Summary bullet, Analysis Risk line, Conclusion item — no drift). Each Exec Summary bullet ends with `(§ N)` referring to its analytical subsection; each Conclusion item starts with `§ N.M:` prefix. Every analytical subsection has BOTH an Exec Summary bullet AND a Conclusion item (no orphans). Recommendation matrix columns/rows are labelled with subsection numbers. See `skills/legal-memo-prose-style/SKILL.md` §Cross-section consistency.
- **Recommendation concreteness (hard, blocking at review):** every Risk-line recommendation names an action verb (specific operational step), a condition or trigger, and an owner. Generic verbs alone (`consider`, `ensure`, `review`, `evaluate`, `assess`, `monitor`) do not count. See `skills/legal-memo-prose-style/SKILL.md` §Recommendation concreteness (Beat 4).
- **Counter-argument framing (hard, blocking at review):** every `Risk: medium` / `Risk: undetermined` verdict names the contrary authority inline and explains why analysis stands; counter-arguments resolved as "does not prevail" carry explicit trigger conditions in the Risk line; Material Assumptions are mapped 1:1 to Open Questions (or labelled immaterial). See `skills/legal-memo-prose-style/SKILL.md` §Counter-argument framing.
- **Heading discipline (hard, blocking at review):** all headings (H1/H2/H3) are noun phrases — not questions, not imperatives. Hierarchy H1 → H2 → H3 only; no H4; no skip jumps. See `skills/legal-memo-prose-style/SKILL.md` §Heading discipline.
- See `skills/legal-memo-prose-style/SKILL.md` for tone, sentence structure, anti-patterns, definition format.

## What goes in the warning banner (forced exit / manual review)

If `final_status` is `forced_exit_...` or `manual_review_required_...`, a yellow callout box at the top with the remaining blocking issues from `state.json.remaining_blocking_issues` or the client-readiness review.
