#!/usr/bin/env python3
"""
md_to_docx.py — convert a legal memo markdown draft to a docx.

Used by legal-memo-writer plugin at the export phase. Invoked from the main
session via Bash. Reads markdown, applies a single legal-memo style across
heading hierarchy, lists, and citations; optionally prepends a yellow warning
banner for forced-exit or manual-review memos.

Limitations (v0.0.1):
- All templates share one docx style; per-template variation is deferred.
- No TOC auto-generation, no hyperlinked citations.
- Requires python-docx (`pip install python-docx`).
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    sys.stderr.write(
        "ERROR: python-docx is not installed. Install with `pip install python-docx`.\n"
        "Fallback: try `pandoc <input> -o <output>` or surface the markdown path.\n"
    )
    sys.exit(2)


FONT_NAME = "Calibri"
FONT_SIZE_BODY = 11
FONT_SIZE_H1 = 14
FONT_SIZE_H2 = 12
FONT_SIZE_H3 = 12
FONT_SIZE_H4 = 11
MARGIN_CM = 2.5
LINE_SPACING = 1.15

WARNING_BG = "FFF3CD"
WARNING_BORDER = "FFE69C"


def set_cell_background(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def set_cell_border(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "8")
        b.set(qn("w:color"), hex_color)
        tc_borders.append(b)
    tc_pr.append(tc_borders)


def apply_page_setup(doc):
    for section in doc.sections:
        section.top_margin = Cm(MARGIN_CM)
        section.bottom_margin = Cm(MARGIN_CM)
        section.left_margin = Cm(MARGIN_CM)
        section.right_margin = Cm(MARGIN_CM)


def configure_default_style(doc):
    style = doc.styles["Normal"]
    font = style.font
    font.name = FONT_NAME
    font.size = Pt(FONT_SIZE_BODY)
    pf = style.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = LINE_SPACING

    for name, size in (
        ("Heading 1", FONT_SIZE_H1),
        ("Heading 2", FONT_SIZE_H2),
        ("Heading 3", FONT_SIZE_H3),
        ("Heading 4", FONT_SIZE_H4),
    ):
        if name in doc.styles:
            s = doc.styles[name]
            s.font.name = FONT_NAME
            s.font.size = Pt(size)
            s.font.color.rgb = RGBColor(0x00, 0x00, 0x00)


def add_warning_banner(doc, final_status, remaining_issues):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cell = table.cell(0, 0)
    set_cell_background(cell, WARNING_BG)
    set_cell_border(cell, WARNING_BORDER)

    title_p = cell.paragraphs[0]
    title = "MANUAL REVIEW REQUIRED"
    if final_status and final_status.startswith("forced_exit"):
        title = "REVIEWER NOTES NOT FULLY RESOLVED"
    title_run = title_p.add_run(title)
    title_run.bold = True
    title_run.font.size = Pt(FONT_SIZE_BODY)

    subtitle_p = cell.add_paragraph()
    subtitle_p.add_run(
        "Manual check recommended before relying on this memorandum. "
        f"Final status: {final_status}."
    )

    if remaining_issues:
        cell.add_paragraph("Remaining blocking issues:").runs[0].bold = True
        for issue in remaining_issues:
            p = cell.add_paragraph(style="List Bullet")
            p.add_run(issue)

    doc.add_paragraph()


def summarize_issue(issue):
    if isinstance(issue, str):
        return issue
    if not isinstance(issue, dict):
        return str(issue)
    section = issue.get("section")
    text = issue.get("issue") or issue.get("gap") or issue.get("why_blocking") or issue.get("suggestion")
    if section and text:
        return f"{section}: {text}"
    return text or json.dumps(issue, ensure_ascii=False)


def extract_remaining_issues(state_path):
    if not state_path or not Path(state_path).exists():
        return []
    try:
        state = json.loads(Path(state_path).read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return []

    explicit_issues = state.get("remaining_blocking_issues")
    if isinstance(explicit_issues, list) and explicit_issues:
        return [summarize_issue(issue) for issue in explicit_issues[:10]]

    client_readiness = state.get("client_readiness")
    if isinstance(client_readiness, dict):
        client_issues = client_readiness.get("blocking_issues")
        if isinstance(client_issues, list) and client_issues:
            return [summarize_issue(issue) for issue in client_issues[:10]]

    iterations = state.get("iterations", [])
    if not iterations:
        return []
    last = iterations[-1]
    blocking_count = sum(
        r.get("blocking_count", 0)
        for r in last.get("reviews", {}).values()
        if isinstance(r, dict)
    )
    if blocking_count == 0:
        return []
    summary = []
    for reviewer, data in last.get("reviews", {}).items():
        if isinstance(data, dict) and data.get("blocking_count", 0) > 0:
            summary.append(f"{reviewer}: {data['blocking_count']} blocking issue(s)")
    return summary


HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
BULLET_RE = re.compile(r"^[-*+]\s+(.*)$")
NUMBERED_RE = re.compile(r"^\d+\.\s+(.*)$")
HORIZONTAL_RULE_RE = re.compile(r"^-{3,}\s*$")
TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")


def split_table_row(line):
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def is_table_separator(line):
    if not TABLE_LINE_RE.match(line):
        return False
    cells = split_table_row(line)
    if not cells:
        return False
    return all(re.match(r"^:?-{3,}:?$", cell.replace(" ", "")) for cell in cells)


def add_markdown_table(doc, rows):
    if not rows:
        return
    col_count = max(len(row) for row in rows)
    table = doc.add_table(rows=0, cols=col_count)
    try:
        table.style = "Table Grid"
    except KeyError:
        pass

    for row_index, row_cells in enumerate(rows):
        cells = table.add_row().cells
        for col_index in range(col_count):
            cell_text = row_cells[col_index] if col_index < len(row_cells) else ""
            paragraph = cells[col_index].paragraphs[0]
            render_inline(paragraph, cell_text)
            if row_index == 0:
                for run in paragraph.runs:
                    run.bold = True

    doc.add_paragraph()


def render_markdown(doc, md_text):
    paragraphs = []
    lines = md_text.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()

        if not line.strip():
            paragraphs.append(("blank", None))
            index += 1
            continue

        if (
            TABLE_LINE_RE.match(line)
            and index + 1 < len(lines)
            and is_table_separator(lines[index + 1])
        ):
            table_rows = [split_table_row(line)]
            index += 2
            while index < len(lines) and TABLE_LINE_RE.match(lines[index].rstrip()):
                table_rows.append(split_table_row(lines[index].rstrip()))
                index += 1
            paragraphs.append(("table", table_rows))
            continue

        if HORIZONTAL_RULE_RE.match(line):
            paragraphs.append(("hrule", None))
            index += 1
            continue

        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            paragraphs.append((f"h{level}", text))
            index += 1
            continue

        m = BULLET_RE.match(line)
        if m:
            paragraphs.append(("bullet", m.group(1).strip()))
            index += 1
            continue

        m = NUMBERED_RE.match(line)
        if m:
            paragraphs.append(("numbered", m.group(1).strip()))
            index += 1
            continue

        paragraphs.append(("text", line))
        index += 1

    for kind, content in paragraphs:
        if kind == "blank":
            continue
        if kind == "hrule":
            doc.add_paragraph().add_run("").add_break()
            continue
        if kind == "table":
            add_markdown_table(doc, content)
            continue
        if kind.startswith("h"):
            level = int(kind[1:])
            heading = doc.add_heading(level=level)
            run = heading.add_run(content)
            run.bold = True
            continue
        if kind == "bullet":
            p = doc.add_paragraph(style="List Bullet")
            render_inline(p, content)
            continue
        if kind == "numbered":
            p = doc.add_paragraph(style="List Number")
            render_inline(p, content)
            continue
        if kind == "text":
            p = doc.add_paragraph()
            render_inline(p, content)


BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
CODE_RE = re.compile(r"`([^`]+)`")


def render_inline(paragraph, text):
    cursor = 0
    while cursor < len(text):
        match = None
        kind = None
        for k, regex in (
            ("bold", BOLD_RE),
            ("italic", ITALIC_RE),
            ("code", CODE_RE),
        ):
            m = regex.search(text, cursor)
            if m and (match is None or m.start() < match.start()):
                match = m
                kind = k
        if match is None:
            paragraph.add_run(text[cursor:])
            break
        if match.start() > cursor:
            paragraph.add_run(text[cursor:match.start()])
        run = paragraph.add_run(match.group(1))
        if kind == "bold":
            run.bold = True
        elif kind == "italic":
            run.italic = True
        elif kind == "code":
            run.font.name = "Consolas"
        cursor = match.end()


def main():
    parser = argparse.ArgumentParser(description="Convert legal memo markdown to docx.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--template-id", default="classical-memo")
    parser.add_argument("--final-status", default=None)
    parser.add_argument("--state", default=None)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        sys.stderr.write(f"ERROR: input markdown not found: {input_path}\n")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    md_text = input_path.read_text(encoding="utf-8")

    doc = Document()
    apply_page_setup(doc)
    configure_default_style(doc)

    if args.final_status and not args.final_status.startswith("approved"):
        remaining = extract_remaining_issues(args.state)
        add_warning_banner(doc, args.final_status, remaining)

    render_markdown(doc, md_text)

    doc.save(str(output_path))
    sys.stdout.write(f"OK: wrote {output_path}\n")


if __name__ == "__main__":
    main()
