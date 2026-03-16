"""
PDF generator for Simurgh AI proposal export.

Produces a polished multi-page PDF matching the app's visual design:

    Page 1  — Cover: project name, task description, persona badge,
               confidence score, export timestamp
    Page 2+ — Executive Summary + Architecture sections from PRD
    Next    — Reasoning & Trade-offs (persona's own words)
    Next    — Debate Summary (if debate turns exist)
    Last    — Metadata: approval status, Jira/Confluence links

Uses reportlab Platypus for layout with custom styles matching the
amber/violet/sky persona colour scheme from the frontend.
"""

import re
import io
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
    KeepTogether,
)
from reportlab.platypus.flowables import Flowable

from app.models.proposal import Proposal, ProposalVariation, AgentPersona

# ── Persona colour palette (matches frontend PERSONA config) ──────────────────
PERSONA_COLORS = {
    AgentPersona.LEGACY_KEEPER: {
        "name": "Legacy Keeper",
        "accent": colors.HexColor("#b45309"),
        "bg": colors.HexColor("#fffbeb"),
        "border": colors.HexColor("#fcd34d"),
        "description": "Stability · Proven patterns · Risk mitigation",
    },
    AgentPersona.INNOVATOR: {
        "name": "Innovator",
        "accent": colors.HexColor("#7c3aed"),
        "bg": colors.HexColor("#f5f3ff"),
        "border": colors.HexColor("#c4b5fd"),
        "description": "Modern arch · Scalability · Future-proof",
    },
    AgentPersona.MEDIATOR: {
        "name": "Mediator",
        "accent": colors.HexColor("#0369a1"),
        "bg": colors.HexColor("#f0f9ff"),
        "border": colors.HexColor("#7dd3fc"),
        "description": "Balanced trade-offs · Pragmatic · Team-focused",
    },
    AgentPersona.BASELINE: {
        "name": "Baseline",
        "accent": colors.HexColor("#64748b"),
        "bg": colors.HexColor("#f8fafc"),
        "border": colors.HexColor("#cbd5e1"),
        "description": "Single-agent baseline proposal",
    },
}

SIMURGH_CYAN = colors.HexColor("#0891b2")
SLATE_900 = colors.HexColor("#0f172a")
SLATE_700 = colors.HexColor("#334155")
SLATE_500 = colors.HexColor("#64748b")
SLATE_200 = colors.HexColor("#e2e8f0")
SLATE_50 = colors.HexColor("#f8fafc")
WHITE = colors.white


# ── Custom Flowable: coloured confidence bar ──────────────────────────────────


class ConfidenceBar(Flowable):
    """Horizontal progress bar showing AI confidence score."""

    def __init__(self, score: int, color: colors.Color, width: float = 120 * mm):
        super().__init__()
        self.score = score
        self.color = color
        self.bar_width = width
        self.height = 6
        self.width = width

    def draw(self):
        # Background track
        self.canv.setFillColor(SLATE_200)
        self.canv.roundRect(0, 0, self.bar_width, self.height, 3, fill=1, stroke=0)
        # Fill
        fill_w = self.bar_width * (self.score / 100)
        if fill_w > 0:
            self.canv.setFillColor(self.color)
            self.canv.roundRect(0, 0, fill_w, self.height, 3, fill=1, stroke=0)


# ── Markdown → reportlab paragraph converter ─────────────────────────────────


def _md_to_paragraphs(
    markdown_text: str,
    body_style: ParagraphStyle,
    h2_style: ParagraphStyle,
    h3_style: ParagraphStyle,
    bullet_style: ParagraphStyle,
    accent: colors.Color = colors.HexColor("#0891b2"),
) -> list:
    """
    Convert a subset of Markdown to reportlab Paragraph objects.

    Handles: # headings, **bold**, *italic*, - bullet lists, blank lines.
    Mermaid code blocks are stripped (not renderable in PDF).
    """
    elements = []

    # Strip mermaid blocks entirely
    text = re.sub(
        r"```mermaid[\s\S]*?```",
        "[Architecture diagram — see Confluence export]",
        markdown_text,
    )
    # Mark code blocks with a special delimiter for later processing
    text = re.sub(
        r"```[\w]*\n([\s\S]*?)```",
        lambda m: "\n[CODE_BLOCK]\n" + m.group(1).rstrip() + "\n[/CODE_BLOCK]\n",
        text,
    )

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Heading 2
        if line.startswith("## "):
            content = line[3:].strip()
            elements.append(Spacer(1, 4 * mm))
            elements.append(Paragraph(_inline_md(content), h2_style))
            elements.append(
                HRFlowable(
                    width="100%", thickness=0.5, color=SLATE_200, spaceAfter=2 * mm
                )
            )

        # Heading 3
        elif line.startswith("### "):
            content = line[4:].strip()
            elements.append(Spacer(1, 2 * mm))
            elements.append(Paragraph(_inline_md(content), h3_style))

        # Heading 4+ (#### etc) -> treat as bold body text
        elif line.startswith("#### ") or line.startswith("##### "):
            content = re.sub(r"^#{4,6}\s+", "", line).strip()
            elements.append(Spacer(1, 1 * mm))
            elements.append(Paragraph(f"<b>{_inline_md(content)}</b>", body_style))

        # Heading 1 (treat as h2 inside body)
        elif line.startswith("# "):
            content = line[2:].strip()
            elements.append(Spacer(1, 4 * mm))
            elements.append(Paragraph(_inline_md(content), h2_style))
            elements.append(
                HRFlowable(
                    width="100%", thickness=0.5, color=SLATE_200, spaceAfter=2 * mm
                )
            )

        # Bullet list item
        elif line.startswith("- ") or line.startswith("* "):
            content = line[2:].strip()
            elements.append(Paragraph(f"• {_inline_md(content)}", bullet_style))

        # Numbered list
        elif re.match(r"^\d+\.\s", line):
            content = re.sub(r"^\d+\.\s", "", line).strip()
            elements.append(Paragraph(f"• {_inline_md(content)}", bullet_style))

        # Code block start
        elif line.strip() == "[CODE_BLOCK]":
            # Collect lines until [/CODE_BLOCK]
            code_lines = []
            i += 1
            while i < len(lines) and lines[i].rstrip() != "[/CODE_BLOCK]":
                code_lines.append(lines[i])
                i += 1
            if code_lines:
                # Do NOT apply _inline_md inside code blocks — it produces nested
                # <font> tags that break reportlab's XML parser since the whole
                # block is already wrapped in <font name="Courier">.
                def _escape_code(line: str) -> str:
                    return (
                        line.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace(" ", "&nbsp;")
                    )

                code_text = "<br/>".join(
                    _escape_code(code_line) for code_line in code_lines
                )
                code_para = Paragraph(
                    f'<font name="Courier" size="8">{code_text}</font>',
                    ParagraphStyle(
                        "Code",
                        fontName="Courier",
                        fontSize=8,
                        textColor=colors.HexColor("#1e293b"),
                        backColor=colors.HexColor("#f1f5f9"),
                        leading=12,
                        leftIndent=4 * mm,
                        rightIndent=4 * mm,
                        spaceBefore=2 * mm,
                        spaceAfter=2 * mm,
                        borderPad=3,
                    ),
                )
                elements.append(code_para)
            i += 1
            continue

        # Markdown table
        elif line.startswith("|") and "|" in line[1:]:
            # Collect all consecutive table lines
            table_lines = [line]
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith("|"):
                table_lines.append(lines[j].strip())
                j += 1
            i = j - 1

            # Parse rows, skip separator lines (---|---)
            rows = []
            for tl in table_lines:
                if re.match(r"^[\|\s\-:]+$", tl):
                    continue
                cells = [c.strip() for c in tl.split("|") if c.strip()]
                if cells:
                    rows.append(cells)

            if len(rows) >= 1:
                # Normalise column count
                max_cols = max(len(r) for r in rows)
                for r in rows:
                    while len(r) < max_cols:
                        r.append("")

                col_w = (170 * mm) / max_cols
                col_widths = [col_w] * max_cols

                para_rows = []
                for ri, row in enumerate(rows):
                    style = ParagraphStyle(
                        "TH" if ri == 0 else "TD",
                        fontName="Helvetica-Bold" if ri == 0 else "Helvetica",
                        fontSize=8,
                        leading=11,
                        textColor=WHITE if ri == 0 else SLATE_700,
                    )
                    para_rows.append([Paragraph(_inline_md(c), style) for c in row])

                tbl = Table(para_rows, colWidths=col_widths, repeatRows=1)
                tbl_style = [
                    ("BACKGROUND", (0, 0), (-1, 0), accent),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SLATE_50]),
                    ("GRID", (0, 0), (-1, -1), 0.25, SLATE_200),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
                tbl.setStyle(TableStyle(tbl_style))
                elements.append(Spacer(1, 2 * mm))
                elements.append(tbl)
                elements.append(Spacer(1, 2 * mm))

        # Blank line
        elif not line.strip():
            elements.append(Spacer(1, 2 * mm))

        # Normal paragraph
        else:
            elements.append(Paragraph(_inline_md(line), body_style))

        i += 1

    return elements


def _inline_md(text: str) -> str:
    """Convert inline markdown (**bold**, *italic*, `code`) to reportlab XML."""
    # Escape XML chars first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r'<font name="Courier">\1</font>', text)
    return text


# ── Page template callbacks ───────────────────────────────────────────────────


def _make_page_callbacks(project_name: str, persona_name: str, accent: colors.Color):
    """Return onFirstPage and onLaterPages callbacks for header/footer."""

    def _header_footer(canvas, doc, is_first: bool):
        canvas.saveState()
        w, h = A4

        if not is_first:
            # Header bar
            canvas.setFillColor(SLATE_50)
            canvas.rect(0, h - 14 * mm, w, 14 * mm, fill=1, stroke=0)
            canvas.setFillColor(accent)
            canvas.rect(0, h - 14 * mm, 3, 14 * mm, fill=1, stroke=0)

            canvas.setFont("Helvetica-Bold", 8)
            canvas.setFillColor(SLATE_700)
            canvas.drawString(15 * mm, h - 9 * mm, project_name[:60])

            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(SLATE_500)
            canvas.drawRightString(
                w - 15 * mm, h - 9 * mm, f"{persona_name} · Simurgh AI"
            )

        # Footer
        canvas.setFillColor(SLATE_200)
        canvas.rect(0, 0, w, 10 * mm, fill=1, stroke=0)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(SLATE_500)
        canvas.drawString(15 * mm, 3.5 * mm, "Generated by Simurgh AI — Confidential")
        canvas.drawRightString(w - 15 * mm, 3.5 * mm, f"Page {doc.page}")

        canvas.restoreState()

    def on_first_page(canvas, doc):
        _header_footer(canvas, doc, is_first=True)

    def on_later_pages(canvas, doc):
        _header_footer(canvas, doc, is_first=False)

    return on_first_page, on_later_pages


# ── Main generator ────────────────────────────────────────────────────────────


def generate_proposal_pdf(
    proposal: Proposal,
    variation: ProposalVariation,
    project_name: str,
    debate_summary: Optional[str] = None,
) -> bytes:
    """
    Generate a polished PDF for a proposal variation.

    Args:
        proposal:       The Proposal object
        variation:      The selected ProposalVariation
        project_name:   Name of the parent project (for header/cover)
        debate_summary: Optional short summary of the debate (1-3 sentences)

    Returns:
        bytes: Raw PDF bytes to stream to the client
    """
    buf = io.BytesIO()
    persona_cfg = PERSONA_COLORS.get(
        variation.agent_persona, PERSONA_COLORS[AgentPersona.BASELINE]
    )
    accent = persona_cfg["accent"]
    persona_name = persona_cfg["name"]
    persona_desc = persona_cfg["description"]

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=f"Architecture Proposal — {persona_name}",
        author="Simurgh AI",
        subject=proposal.task_description[:100],
    )

    # ── Styles ────────────────────────────────────────────────────────────────
    getSampleStyleSheet()

    cover_title = ParagraphStyle(
        "CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=SLATE_900,
        leading=34,
        spaceAfter=4 * mm,
    )

    cover_sub = ParagraphStyle(
        "CoverSub",
        fontName="Helvetica",
        fontSize=13,
        textColor=SLATE_700,
        leading=18,
        spaceAfter=6 * mm,
    )

    ParagraphStyle(
        "CoverMeta", fontName="Helvetica", fontSize=9, textColor=SLATE_500, leading=14
    )

    section_h2 = ParagraphStyle(
        "SectionH2",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=SLATE_900,
        leading=18,
        spaceBefore=2 * mm,
    )

    section_h3 = ParagraphStyle(
        "SectionH3",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=SLATE_700,
        leading=15,
        spaceBefore=1 * mm,
    )

    body = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=10,
        textColor=SLATE_700,
        leading=15,
        spaceAfter=1.5 * mm,
    )

    bullet = ParagraphStyle(
        "Bullet",
        fontName="Helvetica",
        fontSize=10,
        textColor=SLATE_700,
        leading=14,
        leftIndent=5 * mm,
        spaceAfter=1 * mm,
    )

    ParagraphStyle(
        "Caption", fontName="Helvetica", fontSize=8, textColor=SLATE_500, leading=12
    )

    ParagraphStyle(
        "Label", fontName="Helvetica-Bold", fontSize=8, textColor=accent, leading=10
    )

    on_first, on_later = _make_page_callbacks(project_name, persona_name, accent)
    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ══════════════════════════════════════════════════════════════════════════
    w, h = A4
    page_w = w - 40 * mm  # usable width
    export_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    approval = proposal.approval_status.value.replace("_", " ").title()

    # ── Large accent header block ─────────────────────────────────────────────
    # Draw a full-width coloured block at the top via a custom canvas callback
    class CoverHeaderBlock(Flowable):
        """Full-width coloured cover header drawn on the canvas."""

        def __init__(
            self,
            accent_color,
            bg_color,
            border_color,
            persona_name,
            persona_desc,
            page_width,
        ):
            super().__init__()
            self.accent_color = accent_color
            self.bg_color = bg_color
            self.border_color = border_color
            self.persona_name = persona_name
            self.persona_desc = persona_desc
            self.width = page_width
            self.height = 28 * mm

        def draw(self):
            c = self.canv
            w, block_h = self.width, self.height
            # Background
            c.setFillColor(self.bg_color)
            c.roundRect(0, 0, w, block_h, 6, fill=1, stroke=0)
            # Left accent stripe
            c.setFillColor(self.accent_color)
            c.roundRect(0, 0, 5, block_h, 3, fill=1, stroke=0)
            c.rect(2, 0, 5, block_h, fill=1, stroke=0)
            # Border
            c.setStrokeColor(self.border_color)
            c.setLineWidth(1)
            c.roundRect(0, 0, w, block_h, 6, fill=0, stroke=1)
            # Persona name
            c.setFont("Helvetica-Bold", 13)
            c.setFillColor(self.accent_color)
            c.drawString(12 * mm, block_h - 10 * mm, self.persona_name.upper())
            # Description
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.HexColor("#64748b"))
            c.drawString(12 * mm, block_h - 18 * mm, self.persona_desc)
            # Simurgh AI badge top-right
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(colors.HexColor("#0891b2"))
            c.drawRightString(w - 4 * mm, block_h - 10 * mm, "Simurgh AI")
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.HexColor("#94a3b8"))
            c.drawRightString(
                w - 4 * mm, block_h - 18 * mm, "Architecture Intelligence Platform"
            )

    story.append(
        CoverHeaderBlock(
            accent,
            persona_cfg["bg"],
            persona_cfg["border"],
            persona_name,
            persona_desc,
            page_w,
        )
    )
    story.append(Spacer(1, 10 * mm))

    # ── Title ─────────────────────────────────────────────────────────────────
    story.append(Paragraph("Architecture Proposal", cover_title))
    story.append(Spacer(1, 3 * mm))

    # Task description
    task_display = (
        proposal.task_description[:300] + "…"
        if len(proposal.task_description) > 300
        else proposal.task_description
    )
    story.append(Paragraph(task_display, cover_sub))
    story.append(Spacer(1, 6 * mm))

    story.append(
        HRFlowable(width="100%", thickness=1.5, color=accent, spaceAfter=4 * mm)
    )

    # ── Confidence score ──────────────────────────────────────────────────────
    conf_row_data = [
        [
            Paragraph(
                f'<font color="{SLATE_500.hexval()}">Confidence Score</font>',
                ParagraphStyle("CL", fontName="Helvetica", fontSize=9, leading=12),
            ),
            Paragraph(
                f'<font color="{accent.hexval()}" name="Helvetica-Bold"><b>{variation.confidence_score}%</b></font>',
                ParagraphStyle(
                    "CV",
                    fontName="Helvetica-Bold",
                    fontSize=14,
                    textColor=accent,
                    leading=16,
                    alignment=TA_RIGHT,
                ),
            ),
        ]
    ]
    conf_row = Table(conf_row_data, colWidths=[page_w * 0.5, page_w * 0.5])
    conf_row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(conf_row)
    story.append(Spacer(1, 2 * mm))
    story.append(ConfidenceBar(variation.confidence_score, accent, page_w))
    story.append(Spacer(1, 8 * mm))

    # ── Meta table ────────────────────────────────────────────────────────────
    meta_data = [
        ["Project", project_name[:60]],
        ["Approval Status", approval],
        ["Exported", export_time],
    ]
    if proposal.jira_epic_key:
        meta_data.append(["Jira Epic", proposal.jira_epic_key])

    meta_table = Table(meta_data, colWidths=[38 * mm, page_w - 38 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), SLATE_500),
                ("TEXTCOLOR", (1, 0), (1, -1), SLATE_700),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, SLATE_200),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, SLATE_50]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # PRD CONTENT
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Architecture Specification", section_h2))
    story.append(
        HRFlowable(width="100%", thickness=1.5, color=accent, spaceAfter=4 * mm)
    )

    prd_elements = _md_to_paragraphs(
        variation.structured_prd, body, section_h2, section_h3, bullet, accent
    )
    story.extend(prd_elements)

    # ══════════════════════════════════════════════════════════════════════════
    # REASONING & TRADE-OFFS
    # ══════════════════════════════════════════════════════════════════════════
    if variation.reasoning or variation.trade_offs:
        story.append(PageBreak())
        story.append(Paragraph(f"{persona_name} — Reasoning & Trade-offs", section_h2))
        story.append(
            HRFlowable(width="100%", thickness=1.5, color=accent, spaceAfter=4 * mm)
        )

        if variation.reasoning:
            story.append(Paragraph("Reasoning", section_h3))
            story.append(Spacer(1, 1 * mm))
            for para in variation.reasoning.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(_inline_md(para.strip()), body))
            story.append(Spacer(1, 4 * mm))

        if variation.trade_offs:
            story.append(Paragraph("Trade-offs", section_h3))
            story.append(Spacer(1, 1 * mm))
            for para in variation.trade_offs.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(_inline_md(para.strip()), body))

    # ══════════════════════════════════════════════════════════════════════════
    # DEBATE SUMMARY (optional)
    # ══════════════════════════════════════════════════════════════════════════
    if debate_summary:
        story.append(Spacer(1, 6 * mm))
        story.append(
            KeepTogether(
                [
                    Paragraph("Council Debate Summary", section_h3),
                    HRFlowable(
                        width="100%", thickness=0.5, color=SLATE_200, spaceAfter=2 * mm
                    ),
                    Paragraph(_inline_md(debate_summary), body),
                ]
            )
        )

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER METADATA PAGE
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("Document Information", section_h2))
    story.append(
        HRFlowable(width="100%", thickness=1.5, color=SLATE_200, spaceAfter=4 * mm)
    )

    key_style = ParagraphStyle(
        "FKey", fontName="Helvetica-Bold", fontSize=9, textColor=SLATE_500, leading=13
    )
    val_style = ParagraphStyle(
        "FVal", fontName="Helvetica", fontSize=9, textColor=SLATE_700, leading=13
    )

    def _frow(k: str, v: str) -> list:
        return [Paragraph(k, key_style), Paragraph(v, val_style)]

    footer_data = [
        _frow("Generated by", "Simurgh AI"),
        _frow("Persona", f"{persona_name} — {persona_desc}"),
        _frow("Confidence", f"{variation.confidence_score}%"),
        _frow("Task", proposal.task_description),
        _frow("Proposal ID", str(proposal.id)),
        _frow("Approval Status", approval),
        _frow("Export Date", export_time),
    ]
    if proposal.jira_epic_key:
        footer_data.append(
            _frow(
                "Jira Epic",
                f"{proposal.jira_epic_key} — {proposal.jira_epic_url or ''}",
            )
        )
    if proposal.confluence_page_url:
        footer_data.append(_frow("Confluence", proposal.confluence_page_url))

    footer_table = Table(footer_data, colWidths=[45 * mm, page_w - 45 * mm])
    footer_table.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, SLATE_200),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, SLATE_50]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(footer_table)

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=on_first, onLaterPages=on_later)
    return buf.getvalue()
