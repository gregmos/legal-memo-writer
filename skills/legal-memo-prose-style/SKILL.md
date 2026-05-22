---
name: legal-memo-prose-style
description: Prose-writing playbook for the legal-memo-writer pipeline — tone (formal, dispassionate), four-beat Risk subsection pattern (description → quote → analysis → verdict), definitions format, anti-AI-tells, reviewer-conflict priorities. Use when writing legal memo, legal opinion, contract review, regulatory analysis, compliance check. Does not handle docx layout (see legal-memo-docx-render for that).
---

# House style for legal-memo-writer

Plain-English playbook for consistent style across the legal-memo-writer pipeline. Read by the main session, memo-writer and revision-mediator. Reviewers (logic, clarity, style, citations) do NOT read this skill directly — relevant principles are baked into their system prompts to preserve isolation.

The visual side of the docx output is governed by `skills/legal-memo-docx-render/SKILL.md` and `skills/legal-memo-docx-render/scripts/md_to_docx.py`. The rhetorical side (this skill) tells the writer *how the prose reads*. Both come from the same canonical source: the Cowork org-level `legal-memo-style 11.skill` archive. If that source changes, sync both.

## About the user

- **Role**: in-house legal counsel
- **Company**: <set this in the skill before first run — your company name and registration jurisdiction>
- **Primary jurisdictions in priority order**: Cyprus, EU, US, Switzerland, Hong Kong
- **Working language**: English only. All memos, instructions, and prompts are English regardless of the language the user types the query in. If the query is in another language, restate it in English at the top of the memo's Context block and proceed in English.

## Tone — formal, precise, dispassionate

- The author states conclusions as **facts derived from analysis**, not as personal opinions. Direct statements outrank hedged speculation.
- No softening phrases ("it seems", "it could potentially", "we believe", "possibly"). When the law gives a clear answer, state it.
- Hedge only when there is **genuine** legal uncertainty (conflicting authority, untested provision, missing fact). In that case, name the uncertainty and what would resolve it.
- No promotional or emotive vocabulary ("groundbreaking", "robust", "navigate", "tapestry"). Plain analytical prose.
- No filler openers ("In today's world…", "In an era of…", "Today more than ever…").

## Sentence structure — short, declarative, one idea per sentence

- Short declarative sentences predominate. Each sentence carries one idea. Complex thoughts split into multiple sentences rather than packed into one with cascading subordinate clauses.
- Active voice where natural. Passive voice is acceptable when the actor is irrelevant (regulator-facing sentences often need passive).
- Avoid em dashes (use commas or parentheses).
- Inline citations follow `[Source name, year, section]` and sit at the end of the sentence whose claim they support, not at the end of the paragraph.

### Hard limits (apply to every sentence the writer authors)

- **No sentence longer than 40 words.** Count words in the sentence the writer composed; verbatim quoted source text is excluded from the count.
- **No sentence chaining more than 2 independent ideas** via additive connectives — `and that …, and that …`, `; …; …`, `while …, and …`, `: … but …`, or parallel relative clauses each carrying its own verb and object. Two ideas is the cap; three or more must be split.
- **Exempt:** verbatim source quotations rendered inside `> blockquote` paragraphs (those are the source's words, not the writer's). Headers, titles, and bullet items are not full sentences and are not subject to this cap.
- **Enforcement:** both `style-reviewer` and `clarity-reviewer` treat violations of either limit as `blocking_issues[]`, not `nice_to_have[]`. The writer applies the cap during composition AND in a per-section self-check before moving to the next section. Failing this rule produces a blocking revision and another iteration.

## Paragraph structure — short, single-idea, easy to skim

- Each paragraph carries one developed idea and ends there. Linked but distinct ideas split into separate paragraphs rather than packed into one.
- The "wall of text" look — multiple sub-arguments, multiple citations, multiple operational conclusions stacked inside one paragraph — defeats the legal-memo readability standard, even when every individual sentence is within the sentence cap.
- Each analytical-subsection beat (description / analysis / risk line) may contain multiple short paragraphs; each paragraph still carries one idea.

### Hard limits (apply to every paragraph the writer authors)

- **No paragraph longer than 3 sentences.** Count sentences by full-stop / question-mark / exclamation-mark terminators. Inline citations in `[Source, year, §]` form are not sentence terminators.
- **No paragraph longer than 100 words.** Count words the writer composed; verbatim quoted source text inside `> blockquote` paragraphs is excluded from the count.
- **Exempt:** `> blockquote` source quotations (the whole quote paragraph), bullet items (governed by their own ≤2 sentences / ≤40 words cap), numbered list items, headings, titles, table cells. The cap applies to writer-authored body paragraphs only.
- **Enforcement:** `style-reviewer`, `clarity-reviewer`, AND `client-readiness-reviewer` treat violations of either limit as `blocking_issues[]`. The writer applies the cap during composition AND in a per-section self-check before moving to the next section. Failing this rule produces a blocking revision and another iteration.

## Document structure (target — applies to every template unless the template explicitly says otherwise)

Standard order of top-level sections in the markdown draft (which `md_to_docx.py` renders into docx). The canonical per-template structure lives in `templates/<template_id>.md`; this list is the cross-template baseline.

1. **Title** — bold paragraph at top, format `[Subject]: [Analytical framing]`. The subject is the concrete thing under analysis (counterparty name, regulation, product feature). The framing names what the memo evaluates (legal risks / regulatory exposure / compliance position). No date/jurisdiction front-matter inside the title line itself — those live in a small header block below.
2. **Header block** — date (YYYY-MM-DD), jurisdictions, one-line query restatement, template name. Plain body paragraphs, no table. Unnumbered.
3. **Context paragraphs** — 1-2 paragraphs explaining: who is considering what, for what purpose, what this memo analyzes, and what's *out* of scope. Unnumbered body paragraphs that sit between the Header block and the first `## N.` heading. (For `classical-memo`: Context paragraphs stay UNNUMBERED above `## 1. Executive Summary` — they do not merge into the Exec Summary section. For `executive-brief`: the Context paragraph IS the TL;DR, replacing a separate Executive Summary.)
4. **Executive Summary** (classical-memo only — `## 1.`) — **bullets ONLY, 3-5 of them, no prose paragraphs.** Each bullet is one concrete conclusion tied to a specific analytical subsection number below, ≤ 2 sentences and ≤ 40 words, ending with `Risk: <level>.`. Stand-alone readable. Mixing prose paragraphs into this section is a structural defect.
5. **Background / Definitions** (`## 2.` in classical-memo) — key terms and concepts needed to understand the analysis. Defined inline as `Term — definition.` (em dash separator) or `Term - definition.` — each term as its own short paragraph. No bold, no italic on the term itself. Use this section when the audience may not know domain-specific vocabulary; skip the whole section (heading and all) for a counsel-to-counsel memo. If skipped, the next section (Facts) takes the next available number.
6. **Facts, assumptions and limitations** (`## 3.` in classical-memo when Background is present; `## 2.` if Background is skipped) — **required for classical-memo.** Brief, three short sub-blocks as body paragraphs (no sub-headings): facts the user provided; material assumptions tied to specific subsections; limitations that affect confidence. Anchors the analysis to the user's actual facts. Does NOT belong inside Executive Summary or inside the Context paragraphs. For `executive-brief`, Facts are folded into the Context paragraph (no separate section).
7. **Analysis sections** — each risk/issue gets its own numbered subsection following the **Risk subsection pattern** below. Top-level numbering starts at `## 4.` for classical-memo when both Background and Facts are present (or `## 3.` if Background was skipped); for `executive-brief` analytical subsections start at `## 1.`. Sub-numbering for sub-issues: `4.1.`, `4.2.`. Section headings are bold and descriptive (the section title is a noun phrase, not a question).
8. **General conclusion / Recommendations** — not a generic summary. A structured list of specific conditions, required actions, or open risks, each tied to a specific subsection above. Format: `[Risk or topic label]: [specific action or condition]`. Where a recommendation matrix is useful (conservative / balanced / aggressive options), include it here.
9. **Sources** — numbered list with full bibliographic info: title, identifier (CELEX, ECLI, docket number), URL, retrieval date.

The IRAC discipline (Issue, Rule, Application, Conclusion) is **the writer's internal thinking tool**, not the visible surface. Each risk subsection still rests on IRAC underneath, but on the page the reader sees the **Risk subsection pattern** below.

### Heading discipline

1. **Noun phrases only.** Every heading (H1 title, H2 numbered section, H3 subsection) is a noun phrase: `## 4. Data minimisation obligations` not `## 4. Does data minimisation apply?` and not `## 4. Consider the data minimisation risk`. Questions and imperatives as headings read as undergraduate-paper rhetoric and are blocking style defects.
2. **Hierarchy nesting.** Allowed sequence: H1 (title only, once) → H2 (numbered sections `## 1.`, `## 2.`, …) → H3 (sub-issues within an Analysis section `### 4.1.`, `### 4.2.`). No H4 in analytical or surface sections — if a sub-issue needs further breakdown, use paragraph structure within the H3 subsection rather than introducing H4. No heading-level skips (H2 directly to H4 is a blocking defect; H3 must always sit under an H2).

`style-reviewer` enforces both rules as blocking issues.

## Risk subsection pattern (applies to every analytical subsection)

Each numbered analytical subsection follows this four-beat pattern. Keep the beats in order; do not interleave.

1. **Description of the issue** — what the problem is. 1-3 short paragraphs. State the legal question concretely (what right, what obligation, what exposure). Identify the applicable rule by name and citation.
2. **Direct quote from the source** — verbatim text of the controlling provision (statute, regulation, contract clause, judgment passage). Markdown blockquote (`> …`); rendered italic, 11pt, left-indented in docx. Quote stays in the **original language of the source** when the source is non-English (an authoritative non-English regulation, a contract drafted in a non-English language, a non-English-language judgment); otherwise English. Introduce the quote with the precise locator in English: "Article 5(1)(c) GDPR provides:", "Section 13.2 of the master agreement states:", "CJEU in Case C-311/18, para. 96, holds:". Quotes ≤ 30 words where possible; trim with `…` and preserve sense.
3. **Analysis of implications** — 2-4 short paragraphs translating the quoted text into operational consequences. What does this mean for the user's facts, given the assumptions in the Context block? Cite case law and doctrinal commentary inline. If a case or commentary modifies the plain text of the rule, say so explicitly.
4. **Risk assessment line** — a new body paragraph that starts with the verdict as a complete short sentence: `Risk: high.` / `Risk: medium.` / `Risk: low.` / `Risk: undetermined.` (the last one used when the risk cannot be assessed because of missing facts or open law, followed by what would resolve it).

   After the verdict sentence, continue the same paragraph with justification (1-2 sentences linking the verdict to the analysis above) and specific recommendations (what the user should do or refrain from, and any conditions for the recommendation to hold). Recommendations are concrete: a contract amendment, a DPIA trigger, a process control, an escalation path, a deadline.

The four beats are mandatory for every analytical subsection. The reviewers (style-reviewer in particular) check that each subsection contains all four. Skipping the source quote because "the rule is well known" is not acceptable — the quote anchors the analysis to verbatim text.

### Recommendation concreteness (Beat 4)

Every Risk-line recommendation MUST name three elements. A recommendation missing any of the three is a blocking issue (enforced by `style-reviewer`, `clarity-reviewer`, and `client-readiness-reviewer`):

1. **Action verb** — a specific operational step (`amend the DPA to add …`, `run a DPIA before launch`, `add a process control that …`, `escalate to the supervisory authority`, `block launch`, `obtain consent`, `update the privacy notice to disclose …`). Generic verbs alone (`consider`, `ensure`, `review`, `evaluate`, `assess`, `monitor`, `be aware of`, `keep in mind`) DO NOT count as action verbs — they may appear only as connectors followed by a concrete action.
2. **Condition or trigger** — when the action applies (`before launch`, `by [YYYY-MM-DD]`, `within 30 days of [event]`, `if [observable condition X] occurs`, `when [threshold Y] is crossed`, `prior to onboarding the next vendor of this type`).
3. **Owner or accountable function** — who or what function executes (`Legal`, `Privacy`, `Product`, `the controller`, `the vendor counterparty`, `the supervisory authority`, `the DPO`). When the owner is the company by default and unambiguous from context, a generic actor name is acceptable; when the responsibility could fall to multiple functions, the recommendation MUST disambiguate.

Example PASS: "Risk: medium. Adopt a documented LIA (Action: prepare and retain a written LIA covering necessity and balancing) before launch (Condition: pre-launch) — Legal and Privacy co-own (Owner). Confirm vendor due diligence as part of it."

Example FAIL: "Risk: medium. Consider documenting an LIA." (No action verb beyond `consider`, no condition, no owner — three blocking deficiencies in one sentence.)

### Counter-argument framing

The counter-argument is part of the Risk subsection, not an afterthought.

1. **Mandatory inline contrary authority for medium / undetermined verdicts.** When the Risk line verdict is `medium` or `undetermined`, the justification sentence(s) MUST name the contrary authority or the strongest counter-argument explicitly and explain in one sentence why the analysis still stands. A bare "Risk: medium. The case is fact-dependent." is insufficient. The reviewer (`counterargument-reviewer`) blocks medium/undetermined verdicts that do not surface contrary authority inline.
2. **Trigger conditions on the Risk line.** Where the Analysis beat discusses a counter-argument and concludes it does not prevail on the current facts, the Risk line MUST state the explicit factual or legal triggers that would activate the counter-argument and escalate the risk. Example: "Risk: medium. Conclusion holds only while suggestions remain agent-facing and do not drive entitlement, billing, complaint, or account outcomes; if any of those four conditions changes, re-run under Article 22(2)/(3) framing." Implicit "we should monitor" without naming triggers is a blocking gap.
3. **Material Assumption ↔ Open Question mapping.** Every entry in the Conclusion's "Material assumptions" subsection MUST either be linked to a specific entry in the "Open questions" subsection that would resolve it (with an explicit "if this question is answered as X, re-evaluate subsection N" note) OR be explicitly marked "immaterial — does not affect any conclusion in this memo". `logic-reviewer` blocks the draft when this mapping is incomplete.

## Cross-section consistency

A memo's Executive Summary, Analysis Risk lines, Recommendation matrix, and Conclusion section MUST present a single coherent view of each issue. Drift between them is a blocking defect.

1. **Risk-score sync.** For each analytical subsection, the risk score MUST be identical in three places: the Exec Summary bullet for that subsection, the subsection's Risk-line verdict, and the Conclusion item for that subsection. If the writer revises the verdict in one place during drafting, all three must change together.
2. **Subsection cross-references — format.** Each Exec Summary bullet ends with `(§ N)` or `(see § N.M)` pointing at the analytical subsection it summarises. Each Conclusion item starts with `§ N.M:` (or `§ N:`) prefix referring back to the originating subsection. The `§` symbol is preferred; literal `Section` or `Sec.` are also acceptable as long as the format is consistent across the memo.
3. **Bijection between Analysis and Exec Summary / Conclusion.** Every analytical subsection MUST appear as a bullet in `## 1. Executive Summary` AND as an item in the Conclusion. No orphan Analysis subsections (Analysis-only with no Exec Summary surface or Conclusion action). No phantom Exec Summary bullets or Conclusion items that do not map back to an Analysis subsection. The Recommendation matrix, when present, must label each column or row with the subsection number it addresses.
4. **Recommendation-matrix reconciliation.** If a matrix presents an "Aggressive" / high-residual-risk option that conflicts with the Risk-line verdict (e.g., Risk-line says "blocker — do not launch", but the matrix offers a "launch anyway, accept high risk" row), the matrix cell MUST be explicitly labelled as `consequence of ignoring the recommended path, not a viable option`. A matrix that presents the high-risk option as a peer alternative when the Risk line forbids it is a blocking defect.

Enforcement: `logic-reviewer` checks risk-score sync and bijection (content layer). `style-reviewer` checks the `(§ N)` cross-reference format (format layer). Both treat violations as blocking.

## Definitions format

When a term needs introduction, render as its own short paragraph in the Background section (or, if introduced where first relevant, at the start of the section that uses it):

```
Term — short, operational definition that lets the reader follow the rest of the memo.
```

Or with hyphen separator (`Term - definition.`) when em dash is unavailable. The term sits at the start of the paragraph, not bolded, not italicised. No bullet list of definitions — each definition is a body paragraph.

Standard abbreviations (SaaS, AI, API, GDPR, DPIA, NIS2, EDPB, ECJ, CJEU) are used as-is. When a non-English term carries legal significance untranslated (e.g. a civil-law concept whose English approximation distorts the meaning), keep the original term and gloss it parenthetically in English on first use.

## Quotes — formatting and language

- Direct quotes are markdown blockquotes (`> …`), rendered in docx as italic 11pt, left-indented. Each `>` line produces one docx paragraph.
- Quotes stay in the original language of the source document. If the source is non-English (a non-English regulation, contract, or judgment), keep the quote in its original language and add an English gloss in a body paragraph beneath if the audience needs it — never paraphrase inside the blockquote itself.
- Each source is quoted **at most once** in the memo. Pick the load-bearing passage. If two passages from the same source matter, choose the one closest to the operative right or duty and paraphrase the other.
- Direct quotes ≤ 30 words by default. Trim with `…` when needed.

## Conclusion / Recommendations

The Conclusion section is **not** a recap of what was analyzed. It is a structured list of operational outputs:

- One bullet or short numbered item per risk subsection above. Format `Topic / risk label: specific action or condition.`
- Where the company has more than one defensible path, present a small matrix: conservative approach / balanced approach / aggressive approach, each with the trade-off.
- Material assumptions that drove the analysis are listed here too, with a note "if this assumption changes, re-evaluate" tied to the affected subsection.
- Open risks (unresolved facts, untested law) live in a separate "Open questions" sub-list within Conclusion or as a final small section.

## Memorandum conventions (legacy — preserved for compatibility)

- Material factual assumptions must be stated early (in Context block) when they affect conclusions
- Cite primary sources first, doctrine second
- Date format: YYYY-MM-DD
- Source citations: full title + URL + retrieval date
- Inline citation format: `[Source name, year, section]`
- One direct quote per source per memorandum maximum (see Quotes section above)
- For client-ready recommendations, prefer a practical matrix where useful: conservative approach / balanced approach / aggressive approach / required actions / optional actions / open risks
- Heading hierarchy: H1 (memo title), H2 (numbered sections like "1. <Section title>"), H3 (sub-sections like "2.1. <Subsection title>"), H4 reserved for rare cases where a subsection has its own sub-issues (e.g. multi-jurisdiction risk comparison inside one subsection)

## Reviewer priorities (used by revision-mediator)

When reviewers conflict:
1. **Logic ≈ Citations ≈ Counterarguments > Style > Clarity**

   Legal correctness, source-grounding, and resilience to adversarial attack all count at the same priority tier (the "legal-substance" tier). Counterargument blockers — whether `overconfidence`, `contrary_authority`, `missing_fact`, `weak_application`, or `understated_risk` — are resolved at the same priority as Logic and Citations findings. Style and Clarity are the "form" tier and yield to substance: if forced to choose between precise-and-complex versus understandable-and-imprecise, choose precise.

   Conflicts within the substance tier (e.g. counterargument wants softer phrasing, citations wants the original strong claim because the source supports it): preserve the strong claim and add the caveat counterargument requested. The mediator should never drop a substance-tier finding in favour of another substance-tier finding — both go into the consolidated instructions with a Resolution note.

## Exit thresholds (per mode — see `skills/memo/references/modes.md`)

Reviewer set and iteration cap are **mode-dependent**, not fixed. The canonical mapping lives in `modes.md`; this section restates it so reviewers / mediator do not block a Quick-mode task on `clarity` / `style` absence.

- **Quick** — `max_iterations: 1`; approval requires zero `blocking_issues` in **3 reviewers** (logic, citations, counterarguments); no client-readiness polish pass.
- **Standard** — `max_iterations: 3`; approval requires zero `blocking_issues` in **all 5 reviewers** (logic, clarity, style, citations, counterarguments); followed by 1 client-readiness polish pass when `needs_final_polish`.
- **Deep** — `max_iterations: 3`; approval requires zero `blocking_issues` in **all 5 reviewers**; followed by up to 2 client-readiness polish passes.
- On forced exit (after the mode's iteration cap) or `manual_review_required`, the final docx includes a yellow box at the top: "REVIEWER NOTES NOT FULLY RESOLVED" or "MANUAL REVIEW REQUIRED" + a brief list of remaining issues.

## Confidentiality

- Do not name specific company clients, specific amounts, or specific internal artifacts in the memo unless explicitly stated in the query
- When in doubt, use generic phrasing: "the company", "the product feature", "the data subject"

## Anti-patterns

- Avoid em dashes inside body text (use commas, parentheses, or the dedicated definition-format em dash). The `Term — definition.` em dash IS allowed; an em dash thrown into a body sentence as a stylistic break is NOT.
- Avoid AI-tells: "delve into", "it is important to note", "furthermore", "navigate the landscape", "in today's world", "tapestry", "robust", "leverage" (as verb), "in an era of"
- Avoid filler openers at the start of paragraphs ("In today's world…", "In an era of…", "Today more than ever…").
- Avoid vague attributions: "some scholars argue...", "it is generally accepted..."
- Avoid decorative Latin without legal necessity (`mutatis mutandis`, `inter alia`, `prima facie` only when they add substance)
- Avoid promotional language ("groundbreaking", "comprehensive analysis")
- Avoid hedging when the law is clear; hedge only where there is genuine legal uncertainty
- Avoid skipping the source quote in an analytical subsection — every numbered analytical subsection needs the verbatim quote (see Risk subsection pattern)
- Avoid surfacing IRAC labels (Rule / Application / Conclusion) as visible sub-headings inside an analytical subsection. IRAC is the underlying logic; the visible surface uses the four-beat Risk subsection pattern instead.

## Output format conventions

- Lists: bullet for parallel enumerations; numbered for sequential or prioritized items
- Source citations grouped at the end in a numbered list with full bibliographic info
- For forced-exit or manual-review memos, the yellow warning box is rendered as a callout block in docx (background color `#FFF3CD`, border `#FFE69C`)
- For docx layout details (font, sizes, indents, spacing), see `skills/legal-memo-docx-render/SKILL.md` and `skills/legal-memo-docx-render/scripts/md_to_docx.py`
