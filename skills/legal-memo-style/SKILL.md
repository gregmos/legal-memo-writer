---
name: legal-memo-style
description: Convert a legal memo markdown draft to a properly formatted docx that matches the in-house legal-memo visual style. Use when finalizing a legal-memo-writer task — typically called from skills/memo export phase via Bash.
---

# legal-memo-style

Methodology and instructions for converting a finalized legal memo markdown to docx. The actual conversion is executed by `scripts/md_to_docx.py` — this SKILL.md tells the model how and when to invoke it, what arguments to pass, and how to interpret failures.

The visual spec below is ported from the user's Cowork org-level `legal-memo-style` skill (canonical reference: `legal-memo-style 11.skill` archive). The two specs must stay in sync; if the user updates their Cowork skill, mirror the change here and in `md_to_docx.py`.

## When to invoke

After the revision loop and client-readiness gate reach an exit condition (`approved`, `accepted_early`, `forced_exit`, or `manual_review_required`). The main session reads the path to the final draft from `state.json.current_draft_path` and runs the script.

## How to invoke

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/legal-memo-style/scripts/md_to_docx.py" \
  --input "${CLAUDE_PLUGIN_DATA}/work/<task_id>/drafts/v<N>.md" \
  --output "${CLAUDE_PLUGIN_DATA}/work/<task_id>/final/memo-<slug>.docx" \
  --template-id <selected_template_id> \
  --final-status <final_status> \
  --state "${CLAUDE_PLUGIN_DATA}/work/<task_id>/state.json" \
  --language <ru|en>
```

Arguments:
- `--input` (required): path to the final markdown draft.
- `--output` (required): target docx path. Parent directory is created automatically.
- `--template-id` (optional, default `classical-memo`): reserved for future per-template styling overrides. All five templates currently share one visual spec.
- `--final-status` (optional): if it is any non-approved status (`forced_exit_...`, `accepted_early_...`, `manual_review_required_...`), the script inserts the yellow warning banner at the top.
- `--state` (optional): path to `state.json` — used to read `remaining_blocking_issues`, client-readiness blockers, or the last revision summary for the warning banner.
- `--language` (optional, default `en`, choices `en` / `ru`): controls locale typography. On `ru`, straight double quotes around words are converted to «...», en-dash between words is converted to em-dash. Conservative: skips inside code fences, blockquotes, tables, and headings.

Read the language from `state.json.language` (set in Phase 1 by auto-detection). The model should substitute the resolved value into the command before running.

## Document formatting spec

Authoritative visual rules. The script implements these; this section documents what's implemented and why.

### Page setup

- **Margins**: 1 inch (2.54 cm) on all four sides.
- **Orientation**: portrait (default).
- **Page size**: US Letter / A4 — inherited from the rendering environment (Word substitutes appropriately).

### Typography defaults

- **Font family**: `Arial`. Applied to every run via explicit `font.name` plus `w:rFonts` XML for Cyrillic fallback (without this Cyrillic text can render in Calibri/Times on some Word builds).
- **Body size**: 12pt.
- **Quote size**: 11pt (only used for blockquotes).
- **Line spacing**: single (1.0).
- **Paragraph spacing**: 0pt before, 6pt after. Applied uniformly.
- **Alignment**: justified.

### Paragraph types — markdown → docx mapping

| Markdown input | Docx rendering |
|---|---|
| `# Title` (H1) | Arial 12pt **bold**, no indent, justified. Plain bold paragraph — **not** Word's `Heading 1` style. |
| `## Section` (H2) | Same as H1. Numbering ("1.", "2.") is part of the markdown text, no auto-numbering. |
| `### Subsection` (H3) | Same as H2. |
| `#### Sub-subsection` (H4) | Same as H2. |
| Regular text paragraph | Arial 12pt regular, justified, first-line indent 1.11 cm (630 DXA). |
| `> blockquote line` | Arial 11pt *italic*, justified, left indent 1.59 cm (900 DXA), no first-line indent. One docx paragraph per `>` line. |
| `- bullet` / `* bullet` / `+ bullet` | List Bullet style, Arial 12pt regular. |
| `1. numbered` | List Number style, Arial 12pt regular. |
| `\| col \| col \|` table | Table Grid style, cells use Arial 12pt; first row bold. |
| `---` horizontal rule | Blank paragraph (visual break). |

### Inline formatting

- `**bold**` → bold run inside the paragraph.
- `*italic*` → italic run.
- `` `code` `` → Consolas-font run (kept distinct so legal text containing code-like tokens stays recognisable).

Inline formatting layers on top of paragraph-type defaults: a blockquote line that contains `**foo**` produces an italic-by-default paragraph with `foo` rendered bold+italic.

### Why these choices

- **Arial 12pt** — readability for legal documents on screen and print. Matches the in-house Cowork visual identity.
- **Plain bold paragraphs instead of Word Heading styles** — section numbers ("1.", "1.1.") are hand-written in markdown; using Word's auto-numbering would drift on edit and conflict with our hand-maintained numbering.
- **6pt after-paragraph spacing** — visual breathing room without ragged whitespace.
- **First-line indent for body** — standard legal-document convention.
- **Left-indent (not first-line) for blockquotes** — pull-quote convention: the entire paragraph shifts right, marking it visually as cited material.
- **No headers, no footers, no page numbers** — explicit in the source spec ("Keep it clean").

## Warning banner (non-approved memos)

When `--final-status` indicates a non-approved exit, the script inserts a yellow callout box at the top of the document **before** the memo content:

| Final status prefix | Banner title |
|---|---|
| `forced_exit_...` | REVIEWER NOTES NOT FULLY RESOLVED |
| `accepted_early_...` | USER ACCEPTED EARLY — REMAINING ISSUES |
| `manual_review_required_...` | MANUAL REVIEW REQUIRED |
| any other non-approved | MANUAL REVIEW REQUIRED |

Banner content:
1. Title (Arial 12pt bold).
2. Subtitle: "Manual check recommended before relying on this memorandum. Final status: ...".
3. Bulleted list of remaining blocking issues from `state.json.remaining_blocking_issues`, falling back to `state.json.client_readiness.blocking_issues`, falling back to the per-reviewer counts in the last iteration.

Banner uses the same Arial 12pt; only the background (light yellow `FFF3CD`) and border (`FFE69C`) mark it visually.

## Fallback behavior

If the script fails:

1. **python-docx missing** (`ImportError`): exits with code 2 and prints an actionable message to install with `pip install python-docx`. Main session should print this error verbatim to the user, then try the pandoc fallback. Do NOT silently swallow the docx export step.
2. **Parse error or unexpected exception**: main session attempts `pandoc <input> -o <output>` as best-effort. Pandoc is NOT guaranteed in Cowork or Claude Code environments — expect failure if missing.
3. **Pandoc also missing/fails**: surface the markdown path to the user with an explicit message: "docx export failed (python-docx + pandoc both unavailable). Markdown saved at `<path>`. Install python-docx and re-run, or convert via Microsoft Word's Open Markdown / a third-party tool."
4. Never report "exported successfully" without an actual docx file written.

## Limitations and out-of-scope items

The current visual spec implements `legal-memo-style 11.skill` literally for layout. It does **not** address:

- **Writing style alignment.** The user's source skill also specifies a rhetorical structure (numbered "1.", "1.1." sections; opening "[Subject]: [Framing]" title pattern; per-issue pattern of description → italic source quote → analysis → "Риск высокий/средний/низкий" line; definitions as `Term - definition`). Our memo-writer agent and reviewers currently produce IRAC-structured drafts. The docx will render the IRAC structure with this visual spec; aligning the rhetorical pattern to the source skill is a separate, invasive change (touches `skills/legal-memo-house-style/SKILL.md`, `agents/memo-writer.md`, reviewer prompts).
- **Per-template visual variation.** All five plan templates (`classical-memo`, `executive-brief`, `risk-assessment`, `regulatory-analysis`, `cross-jurisdictional`) currently render with the same visual spec.
- **TOC, cover page, headers/footers, page numbers.** Explicitly omitted by the source spec.
- **Hyperlinked citations / cross-references.** Inline citations remain plain text.
- **Cross-platform font fallback.** If Arial is unavailable on the rendering machine, Word substitutes.

## Reference

The canonical visual spec is the user's Cowork org-level skill `legal-memo-style 11.skill` (provided via download). If that spec evolves, sync changes here and in `scripts/md_to_docx.py`.
