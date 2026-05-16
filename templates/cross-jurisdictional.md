# Template: cross-jurisdictional

**Use when:** the question requires comparing how multiple jurisdictions treat the same legal issue — e.g. cross-border data transfers, multi-country product launches, comparative employment law. Default when `plan.md` lists 2+ jurisdictions with substantive differences.

## Required sections (in this order)

1. **Header** — title, date, **jurisdictions compared** (full list), query, template name.
2. **Executive Summary** — 3-5 bullets:
   - Areas of convergence (where jurisdictions agree).
   - Key divergences.
   - Strictest jurisdiction overall (top-line).
   - Recommended approach for multi-jurisdictional operation.
3. **Facts, assumptions and methodology** — user-provided facts, assumptions adopted from intake, what was compared, what was excluded (e.g. "We compared substantive requirements; procedural/enforcement aspects were not analyzed").
4. **Comparative matrix** — a markdown table with:
   - Rows: legal sub-issues from `plan.md`.
   - Columns: jurisdictions.
   - Cells: short factual statement of each jurisdiction's position + citation marker (e.g. `[CY-1]`).
   
   Example:
   ```
   | Sub-issue                           | Cyprus            | EU (GDPR)         | Switzerland     |
   |-------------------------------------|-------------------|-------------------|-----------------|
   | Lawful basis for biometric processing | Art. 9(2)(a) GDPR via CY DPL [CY-1] | Art. 9(2)(a) GDPR [EU-1] | Art. 31 FADP [CH-1] |
   ```
5. **Detailed analysis by jurisdiction** — one H2 sub-section per jurisdiction:
   - Applicable instruments (statutes, regulations).
   - Key obligations.
   - Notable case law (if any).
   - Recent regulatory guidance (if any).
6. **Areas of convergence** — where the jurisdictions agree substantively.
7. **Key divergences** — where they differ, with severity (administrative-only / substantive-different / completely-incompatible).
8. **Recommended approach for multi-jurisdictional operation** — practical guidance: which jurisdiction to default to, where to localize, which conflicts cannot be resolved without operational segmentation.
9. **Risks and open questions** — uncertainty surface.
10. **Sources** — numbered list grouped by jurisdiction (e.g. `## Cyprus sources`, `## EU sources`, etc.).

## Tone

Analytical, comparative. The matrix is a key visual deliverable — invest in making it clean and readable.

## Length guidance

3500-7500 words. Matrix + per-jurisdiction detail + comparative synthesis.

## Rules

- The comparative matrix is mandatory, even if narrow (2 jurisdictions, 3 sub-issues).
- Citation markers in the matrix (e.g. `[CY-1]`) refer to numbered entries in the Sources section.
- Don't sugar-coat divergences. If two jurisdictions are incompatible, say so explicitly; that informs the operational recommendation.
- When recommending a default jurisdiction for multi-country operation, justify the choice (strictest standard wins by default; deviation only with explicit business rationale).

## What goes in the warning banner (forced exit / manual review)

Same yellow callout for any non-approved final status.
