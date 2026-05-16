---
name: legal-memo-style
description: Convert a legal memo markdown draft to a properly formatted docx. Use when finalizing a legal-memo-writer task — typically called from skills/memo export phase via Bash. Handles heading hierarchy, source citations, and non-approved-status warning banners.
---

# legal-memo-style

Methodology and instructions for converting a finalized legal memo markdown to docx. The actual conversion is executed by `scripts/md_to_docx.py` — this SKILL.md tells the model how and when to invoke it, what arguments to pass, and how to interpret failures.

## When to invoke

After the revision loop and client-readiness gate reach an exit condition (`approved`, `forced_exit`, or `manual_review_required`). The main session reads the path to `drafts/vN.md` from `state.json` and runs the script.

## How to invoke

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/legal-memo-style/scripts/md_to_docx.py" \
  --input "${CLAUDE_PLUGIN_DATA}/work/<task_id>/drafts/v<N>.md" \
  --output "${CLAUDE_PLUGIN_DATA}/work/<task_id>/final/memo-<slug>.docx" \
  --template-id <selected_template_id> \
  --final-status <final_status> \
  --state "${CLAUDE_PLUGIN_DATA}/work/<task_id>/state.json"
```

Arguments:
- `--input` (required): path to the final markdown draft.
- `--output` (required): target docx path. Parent directory is created automatically.
- `--template-id` (optional, default `classical-memo`): for template-specific styling overrides (v0.0.1: no-op — all templates share one style).
- `--final-status` (optional): if it is any non-approved status (`forced_exit...` or `manual_review_required...`), the script inserts the yellow warning banner at the top.
- `--state` (optional): path to state.json — used to read `remaining_blocking_issues`, client-readiness blockers, or the last revision summary for the warning banner.

Anti-pattern enforcement (em-dashes, AI vocabulary, vague attributions) is the job of `style-reviewer` during the revision loop, not the export step. No `--house-style` arg.

## What the script does

Reads markdown, parses heading hierarchy, generates a docx with:
- Heading 1 (H1) → docx Heading 1 style (memo title).
- Heading 2 (H2) → Heading 2 (numbered sections like "1. Executive Summary").
- Heading 3 (H3) → Heading 3 (sub-sections like "4.1. Issue 1").
- Heading 4 (H4) → Heading 4 (IRAC labels: bold inline).
- Bullets and numbered lists → docx native lists.
- Inline citations `[Source name, year, section]` → preserved as text (no hyperlink yet in v0.0.1).
- Final "Sources" section → numbered list with hanging indent.
- Forced exit or manual-review status → yellow callout box at top of document with title "REVIEWER NOTES NOT FULLY RESOLVED" or "MANUAL REVIEW REQUIRED" + bulleted list of remaining blocking issues.

Default styling (override per template_id later):
- Font: Calibri 11pt body, 14pt H1, 12pt H2-H3, 11pt H4 bold.
- Margins: 2.5cm all sides.
- Line spacing: 1.15.
- Black text, no color emphasis except the warning banner.

## Fallback behavior

If the script fails:
1. **python-docx missing** (`ImportError` from script): the script exits with code 2 and prints an actionable message to install with `pip install python-docx`. Main session should print this error verbatim to the user, then try the pandoc fallback. Do NOT silently swallow the docx export step.
2. **Parse error or unexpected exception**: main session attempts `pandoc <input> -o <output>` as best-effort. Pandoc is NOT guaranteed in Cowork or Claude Code environments — expect failure if missing.
3. **Pandoc also missing/fails**: surface the markdown path to the user with an explicit message: "docx export failed (python-docx + pandoc both unavailable). Markdown saved at `<path>`. Install python-docx and re-run, or convert via Microsoft Word's Open Markdown / a third-party tool."
4. Never report "exported successfully" without an actual docx file written.

## Limitations (v0.0.1)

- All 5 templates use the same docx style. Template-specific styling (different fonts, margins, heading numbering schemes) is deferred to a later version.
- No table of contents auto-generation.
- No automatic hyperlinking of inline citations (manual cross-references only).
- No cross-platform docx font fallback — if Calibri is missing on the rendering machine, Word substitutes.
