# memoforge docx-render

Methodology and instructions for converting a finalized legal memo markdown to docx. The actual conversion is executed by `scripts/md_to_docx.py` — this SKILL.md tells the model how and when to invoke it, what arguments to pass, and how to interpret failures.

The visual spec below is ported from the user's Cowork org-level `legal-memo-style` skill (canonical reference: `legal-memo-style 11.skill` archive). The two specs must stay in sync; if the user updates their Cowork skill, mirror the change here and in `md_to_docx.py`.

## When to invoke

After the revision loop and client-readiness gate reach an exit condition (`approved`, `accepted_early`, `forced_exit`, or `manual_review_required`). The main session reads the path to the final draft from `state.json.current_draft_path` and runs the script.

## How to invoke

The docx is written **directly into the working directory** (`state.json.work_dir`, which is also the user's output folder). There is no `final/` subdirectory and no separate "staging → copy" step — input markdown, output docx, and `state.json` all live in the same single working directory.

```bash
# $WORK_DIR is the resolved working-directory path from state.json.work_dir.
# The main session sets it in Phase 1 (or /continue resolves it on resume) — there is no
# ${CLAUDE_PLUGIN_DATA}/work/ staging since v0.0.29. The Python lookup below reads work_dir
# from state.json defensively (state.json itself lives in the working directory).
WORK_DIR=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["work_dir"])' "$WORK_DIR/state.json" 2>/dev/null || echo "$WORK_DIR")
python3 "${CLAUDE_PLUGIN_ROOT}/lib/docx-render/scripts/md_to_docx.py" \
  --input "$WORK_DIR/drafts/v<N>.md" \
  --output "$WORK_DIR/memo-<slug>.docx" \
  --template-id <selected_template_id> \
  --final-status <final_status> \
  --state "$WORK_DIR/state.json" \
  --language en
```

In the `memo` skill Phase 11 the orchestrator already has `$WORK_DIR` resolved from Phase 1 — pass it directly instead of re-resolving here.

Arguments:
- `--input` (required): path to the final markdown draft.
- `--output` (required): target docx path. Parent directory is created automatically.
- `--template-id` (optional, default `classical-memo`): reserved for future per-template styling overrides. Both templates currently share one visual spec.
- `--final-status` (optional): if it is any non-approved status (`forced_exit_...`, `accepted_early_...`, `manual_review_required_...`), the script inserts the yellow warning banner at the top.
- `--state` (optional): path to `state.json` — used to read `remaining_blocking_issues`, client-readiness blockers, or the last revision summary for the warning banner.
- `--language` (optional, default `en`, only choice currently is `en`): reserved for future locale-specific typography rules. The plugin is English-only as of 0.0.35; the flag exists to keep the CLI stable.

`state.json.language` is fixed to `"en"`. Always pass `--language en`.

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
| `- bullet` / `* bullet` / `+ bullet` | List Bullet style, Arial 12pt regular. **Paragraph overrides on top of the style** (identical to numbered lists): `<w:ind w:left="720"/>` (720 DXA = 1.27 cm = 0.5"), `<w:tabs><w:tab w:val="clear" w:pos="360"/></w:tabs>`, `<w:contextualSpacing w:val="0"/>`, justified. Marker sits at ~360 DXA (= left − inherited hanging=360 from numbering.xml), wrapped text starts at 720 DXA — deeper than the body first-line indent so bullets are visually distinct from body paragraphs. `contextualSpacing="0"` disables the "Don't add space between paragraphs of the same style" behaviour baked into Word's built-in ListBullet style, so the 6pt after-spacing applies between items. |
| `1. numbered` | List Number style, Arial 12pt regular. **Same paragraph overrides as bullets**: `<w:ind w:left="720"/>`, tab clear at 360, `<w:contextualSpacing w:val="0"/>`, justified. The number (`1.`, `2.`, …) sits at ~360 DXA, wrapped text at 720 DXA — visually consistent with bullet lists. |
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

If the script fails, the main session runs the always-deliver fallback chain documented in `skills/memo/SKILL.md` Phase 11 and `skills/memo/references/always-deliver.md` Phase 11 row. Summary (the canonical version is the SKILL.md / always-deliver.md text; this section is operational restatement only):

1. **python-docx missing** (`ImportError`): script exits with code 2 + actionable message. Main session prints the error verbatim, then advances to step 2.
2. **Parse error or unexpected exception**: main session attempts `pandoc "<input>" -o "<output>"` as best-effort. Pandoc is NOT guaranteed in Cowork or Claude Code environments.
3. **Pandoc also missing/fails — markdown delivery fallback** (per `always-deliver.md` Phase 11 row, the canonical contract): main session
   - Resolves the source draft deterministically (the no-polish path skips `v<N>-client-ready.md` creation): (1) `drafts/v<N>-client-ready.md` if it exists for the highest N, else (2) `state.json.current_draft_path`, else (3) the highest-N file under `drafts/v*.md`.
   - `cp "<resolved source>" "<work_dir>/memo-<slug>.md"`.
   - Updates `state.json.final_docx_path` to the absolute path of the `.md` file (extension `.md` instead of `.docx` — the schema field name is preserved for stability).
   - Pushes the banner `"docx export failed — markdown file delivered. Convert manually with pandoc or save-as docx."` into `state.json.fallback_banners[]` (dedupe).
   - Calls `Read` on the new `.md` so Cowork inserts an artifact card.
   - Sets `current_phase = done`.
4. Never report "exported successfully" without an actual file written. Never reach `current_phase = done` with `final_docx_path = null` — `scripts/validate_state.py` enforces `is_file()` on `final_docx_path` at `done`.

## Limitations and out-of-scope items

The current visual spec implements `legal-memo-style 11.skill` literally for layout. It does **not** address:

- **Per-template visual variation.** Both plan templates (`classical-memo`, `executive-brief`) currently render with the same visual spec. (Legacy templates `risk-assessment`, `regulatory-analysis`, `cross-jurisdictional` may still appear in archived task state for tasks created before v0.0.45; `md_to_docx.py` falls back to the classical-memo visual spec for any unknown template_id, so legacy exports still render correctly.)
- **TOC, cover page, headers/footers, page numbers.** Explicitly omitted by the source spec.
- **Hyperlinked citations / cross-references.** Inline citations remain plain text.
- **Cross-platform font fallback.** If Arial is unavailable on the rendering machine, Word substitutes.

## What is now addressed (as of 0.0.34)

Writing-style alignment with the source `legal-memo-style 11.skill` was previously listed as out-of-scope here. As of 0.0.34, the writing surface (rhetorical structure, four-beat Risk subsection pattern, definitions format, tone discipline) is implemented across `lib/prose-style.md`, `agents/memo-writer.md`, all five `templates/*.md`, and `agents/style-reviewer.md`. The docx renderer in `scripts/md_to_docx.py` already handled the layout side; the rhetorical side now matches. If the source `.skill` archive evolves further, sync both layers.

## Reference

The canonical visual spec is the user's Cowork org-level skill `legal-memo-style 11.skill` (provided via download). If that spec evolves, sync changes here and in `scripts/md_to_docx.py`.
