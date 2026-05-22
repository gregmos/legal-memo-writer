# Template: executive-brief

**Use when:** a fast, high-level answer is needed for a non-lawyer business stakeholder. Short, dense, no abstract. Default for simple compliance questions or product-team requests.

All templates in this plugin share one rhetorical surface — the four-beat Risk subsection pattern from `skills/legal-memo-prose-style/SKILL.md`. In `executive-brief` the pattern is **compressed**: each beat is one-to-two sentences and the brief covers a maximum of 2-3 risks. The verbatim source quote is still required (a brief without a quote is just an opinion).

## Required sections (in this order)

1. **Title** — bold, format `<Subject>: <Analytical framing>`. No date or jurisdictions inside the title.
2. **Header block** — date (YYYY-MM-DD), jurisdictions, one-line query restatement, template name.
3. **Context** — 1 short body paragraph: who is considering what, for what purpose. No abstract or TL;DR separately — the context IS the TL;DR for a brief.
4. **Key assumptions** — only if material; ≤ 3 bullets. Skip entirely if assumptions do not affect the answer.
5. **Numbered analytical subsections** — 2-3 maximum. Combine related risks into one subsection rather than splitting them. Each subsection follows the four-beat pattern, compressed:
   1. **Description** — 1 sentence naming the issue and the controlling provision.
   2. **Verbatim source quote** — markdown blockquote (`> …`), source's original language, ≤ 25 words.
   3. **Analysis** — 1-2 sentences linking the quote to the user's facts.
   4. **Risk assessment line** — one paragraph: `Risk: high.` / `Risk: medium.` / `Risk: low.`, one-sentence justification, one-sentence concrete recommendation.
6. **Recommendation** — 3-5 bullets total: one line per subsection above linking risk to action, plus any cross-cutting recommendation (e.g. "Run a DPIA before launch").
7. **Sources** — numbered list with full bibliographic info.

## Tone

Direct, plain English. Avoid legalese unless necessary. The reader is a business decision-maker, not a lawyer. Short declarative sentences. No hedging when the law is clear.

## Length guidance

500-1200 words total **including footnotes and Sources** — hard cap in Brief mode (the only mode that produces `executive-brief`). Target 800-1000 words. If genuine analysis cannot fit defensibly under the cap, add the `length_overflow_recommendation: true` YAML front-matter and let the mediator route to a Full-mode rerun.

## Rules

- The four-beat pattern is compressed but **all four beats are present** — including the verbatim source quote. A brief without quotes loses the audit trail and gets blocked at style review.
- Plain language: if a legal term is unavoidable, define it on first use in one phrase (inline, not in a separate Background section — there is no Background section in `executive-brief`).
- Maximum 3 numbered analytical subsections. If `plan.md` lists more legal questions, fold the secondary ones into the Recommendation bullets as one-liners or escalate the template.
- Use prose paragraphs for the four beats, bullets only for Recommendation and Key assumptions.
- **Sentence-length cap (hard, blocking at review):** no sentence over 40 words; no sentence chaining more than 2 independent ideas (via `and that …, and that …`, semicolon chains, `while …, and …`, or parallel relative clauses). Verbatim source quotes inside `> blockquote` paragraphs are exempt. See `skills/legal-memo-prose-style/SKILL.md` §Sentence structure Hard limits.
- **Paragraph-length cap (hard, blocking at review):** no paragraph over 3 sentences or 100 words. Executive-brief paragraphs are already compressed (1-2 sentences per beat) so this cap rarely binds, but it is enforced uniformly across templates. Verbatim source quotes (`> blockquote`), bullet items, numbered list items, headings, and table cells are exempt. See `skills/legal-memo-prose-style/SKILL.md` §Paragraph structure Hard limits.
- **Cross-section consistency (hard, blocking at review):** executive-brief has no separate Exec Summary section (Context paragraph IS the TL;DR), so the bullet-to-subsection check does not apply. However, each item in the §Recommendation bullets MUST start with `§ N.M:` (or `§ N:`) prefix referring back to its analytical subsection, and risk scores must match between each analytical subsection's Risk line and its Recommendation bullet. See `skills/legal-memo-prose-style/SKILL.md` §Cross-section consistency.
- **Recommendation concreteness (hard, blocking at review):** every Risk-line recommendation AND every Recommendation bullet names an action verb (specific operational step), a condition or trigger, and an owner. Generic verbs alone (`consider`, `ensure`, `review`, `evaluate`, `assess`, `monitor`) do not count. See `skills/legal-memo-prose-style/SKILL.md` §Recommendation concreteness (Beat 4).
- **Counter-argument framing (hard, blocking at review):** every `Risk: medium` / `Risk: undetermined` verdict names the contrary authority inline (compressed to one sentence in executive-brief) and explains why analysis stands; counter-arguments resolved as "does not prevail" carry explicit trigger conditions in the Risk line. Material Assumptions (when present in Key Assumptions section) are mapped to whatever would change them. See `skills/legal-memo-prose-style/SKILL.md` §Counter-argument framing.
- **Heading discipline (hard, blocking at review):** all headings are noun phrases — not questions, not imperatives. Hierarchy H1 → H2 only (executive-brief rarely needs H3); no H4; no skip jumps. See `skills/legal-memo-prose-style/SKILL.md` §Heading discipline.
- See `skills/legal-memo-prose-style/SKILL.md` for tone, anti-patterns, definition format.

## What goes in the warning banner (forced exit / manual review)

Same yellow callout pattern at the top of the docx for any non-approved final status.
