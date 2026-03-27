import io
import re
from typing import List


def markdown_to_pdf_bytes(markdown_text: str, title: str = "Result") -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer
    except Exception:
        return markdown_text.encode("utf-8")

    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleKo",
        parent=styles["Title"],
        fontName="HYSMyeongJo-Medium",
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#0B2A4A"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "SectionKo",
        parent=styles["Heading3"],
        fontName="HYSMyeongJo-Medium",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0F4C81"),
        spaceBefore=6,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyKo",
        parent=styles["BodyText"],
        fontName="HYSMyeongJo-Medium",
        fontSize=10,
        leading=14,
        textColor=colors.black,
        spaceAfter=3,
    )

    story: List = [Paragraph(_esc(title), title_style), HRFlowable(width="100%", color=colors.HexColor("#D5DEEA")), Spacer(1, 8)]
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        if line == "---":
            story.append(HRFlowable(width="100%", color=colors.HexColor("#D5DEEA")))
            story.append(Spacer(1, 6))
            continue
        if line.startswith("#"):
            txt = re.sub(r"^#+\s*", "", line)
            story.append(Paragraph(_esc(txt), section_style))
            continue
        if line.startswith("[") and "]" in line:
            k, v = line.split("]", 1)
            header = k + "]"
            story.append(Paragraph(_esc(f"<b>{header}</b> {v.strip()}"), body_style))
            continue
        if line.startswith("- "):
            story.append(Paragraph(_esc(f"• {line[2:]}"), body_style))
            continue
        story.append(Paragraph(_esc(line), body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

