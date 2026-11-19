"""Server-side A4 PDF generator for digital certificates with scannable ISO/IEC 18004 QR codes."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import segno
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from .demo import fmt_date, fmt_dt, fmt_rub, mask_full_name

_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_FONTS_REGISTERED = False

PAGE_W, PAGE_H = 595.28, 841.89
MARGIN = 44.0
INK = "#161918"
MUTED = "#525A56"
ACCENT = "#162C22"
TINT = "#EFF2F0"
LINE = "#D5DDD9"
ERR_HEX = "#9E2A2B"


def _ensure_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont("SemestrSans", str(_FONTS_DIR / "Inter-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("SemestrStrong", str(_FONTS_DIR / "Inter-SemiBold.ttf")))
    _FONTS_REGISTERED = True


def _draw_mark(c: Canvas, x: float, top_y: float, size: float = 28.0) -> None:
    """Draw the geometric Semestr mark (forest rounded square + white C + bookmark)."""
    y = PAGE_H - top_y - size
    c.saveState()
    c.setFillColor(colors.HexColor(ACCENT))
    c.roundRect(x, y, size, size, size * 0.24, fill=1, stroke=0)
    # Bookmark tab in upper-right
    c.setFillColor(colors.HexColor("#7FC39B"))
    bx = x + size * 0.66
    by = y + size * 0.62
    bw = size * 0.16
    bh = size * 0.24
    p = c.beginPath()
    p.moveTo(bx, by + bh)
    p.lineTo(bx + bw, by + bh)
    p.lineTo(bx + bw, by)
    p.lineTo(bx + bw * 0.5, by + bh * 0.28)
    p.lineTo(bx, by)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    # Letter C arc
    c.setStrokeColor(colors.white)
    c.setLineWidth(size * 0.115)
    c.setLineCap(1)
    cx = x + size * 0.45
    cy = y + size * 0.47
    r = size * 0.24
    c.arc(cx - r, cy - r, cx + r, cy + r, startAng=48, extent=264)
    c.restoreState()


def _draw_qr(c: Canvas, payload_url: str, x: float, bottom_y: float, box_size: float = 88.0) -> None:
    """Draw vector QR modules directly onto the PDF canvas with a 4-module quiet zone."""
    qr = segno.make(payload_url, error="m", boost_error=False)
    matrix = qr.matrix
    n = len(matrix)
    border = 4
    total = n + 2 * border
    cell = box_size / total

    c.saveState()
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor(LINE))
    c.setLineWidth(0.7)
    c.roundRect(x, bottom_y, box_size, box_size, 6, fill=1, stroke=1)

    c.setFillColor(colors.HexColor(INK))
    for r_idx, row in enumerate(matrix):
        # PDF y grows bottom-up; matrix row 0 is top
        py = bottom_y + box_size - (r_idx + border + 1) * cell
        col = 0
        while col < n:
            if row[col]:
                start = col
                while col < n and row[col]:
                    col += 1
                px = x + (start + border) * cell
                c.rect(px, py, (col - start) * cell + 0.08, cell + 0.08, fill=1, stroke=0)
            else:
                col += 1
    c.linkURL(payload_url, (x, bottom_y, x + box_size, bottom_y + box_size), relative=0)
    c.restoreState()


def _draw_para(
    c: Canvas,
    html_text: str,
    x: float,
    top_y: float,
    width: float,
    font: str = "SemestrSans",
    size: float = 10.2,
    leading: float = 15.0,
    color: str = INK,
) -> float:
    style = ParagraphStyle(
        "docp",
        fontName=font,
        fontSize=size,
        leading=leading,
        textColor=colors.HexColor(color),
    )
    para = Paragraph(html_text, style)
    _, h = para.wrap(width, PAGE_H)
    para.drawOn(c, x, PAGE_H - top_y - h)
    return top_y + h


def render_certificate_pdf(
    *,
    item: dict,
    student,
    student_meta: dict,
    records: list,
    scholar: dict | None,
    dorm: dict | None,
    verify_code: str,
    verify_url: str,
    valid_until: str,
    concept_notice: str,
) -> bytes:
    """Render an official-style A4 demo certificate PDF with embedded QR and privacy metadata."""
    _ensure_fonts()
    buf = BytesIO()
    c = Canvas(buf, pagesize=(PAGE_W, PAGE_H), pageCompression=0)
    c.setTitle(f"{item['title']} · {verify_code} · Семестр")
    c.setAuthor("Цифровой деканат «Семестр» (конкурсный демо-прототип)")
    c.setSubject(f"Электронная справка {verify_code} · {verify_url}")

    content_w = PAGE_W - 2 * MARGIN

    # Outer sheet frame
    c.setFillColor(colors.white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor(LINE))
    c.setLineWidth(0.8)
    c.roundRect(24, 24, PAGE_W - 48, PAGE_H - 48, 10, fill=0, stroke=1)

    # Diagonal watermark
    c.saveState()
    c.translate(PAGE_W / 2, PAGE_H / 2)
    c.rotate(34)
    c.setFont("SemestrStrong", 44)
    c.setFillColor(colors.HexColor("#F1DFDF" if item["revoked"] else "#ECEFEC"))
    wm = "ОТОЗВАНО · ДЕМО" if item["revoked"] else "ОБРАЗЕЦ / ДЕМО"
    c.drawCentredString(0, 0, wm)
    c.restoreState()

    # Header / Letterhead
    top = 52.0
    _draw_mark(c, MARGIN, top, 30.0)
    c.setFont("SemestrStrong", 11.5)
    c.setFillColor(colors.HexColor(INK))
    c.drawString(MARGIN + 38, PAGE_H - top - 13, "Цифровой деканат «Семестр»")
    c.setFont("SemestrSans", 8.8)
    c.setFillColor(colors.HexColor(MUTED))
    c.drawString(MARGIN + 38, PAGE_H - top - 26, "Единый реестр студенческих документов · демонстрационный стенд")

    # Right meta box
    meta_w = 186.0
    meta_x = PAGE_W - MARGIN - meta_w
    c.setFillColor(colors.HexColor("#FDF2F2" if item["revoked"] else TINT))
    c.setStrokeColor(colors.HexColor(ERR_HEX if item["revoked"] else LINE))
    c.roundRect(meta_x, PAGE_H - top - 38, meta_w, 40, 6, fill=1, stroke=1)
    c.setFont("SemestrStrong", 8.2)
    c.setFillColor(colors.HexColor(ERR_HEX if item["revoked"] else ACCENT))
    status_lbl = "СТАТУС: ОТОЗВАНА ИЗ РЕЕСТРА" if item["revoked"] else "СТАТУС: ОБРАЗЕЦ / ДЕМО"
    c.drawString(meta_x + 10, PAGE_H - top - 13, status_lbl)
    c.setFont("SemestrStrong", 9.4)
    c.setFillColor(colors.HexColor(INK))
    c.drawString(meta_x + 10, PAGE_H - top - 25, f"Исх. № {verify_code}")
    c.setFont("SemestrSans", 7.8)
    c.setFillColor(colors.HexColor(MUTED))
    c.drawString(meta_x + 10, PAGE_H - top - 35, f"от {fmt_dt(item['ready_at'])} · до {valid_until}")

    y = top + 54.0
    c.setStrokeColor(colors.HexColor(LINE))
    c.setLineWidth(0.8)
    c.line(MARGIN, PAGE_H - y, PAGE_W - MARGIN, PAGE_H - y)

    # Document Title
    y += 22.0
    y = _draw_para(c, f"<b>{escape(item['title'])}</b>", MARGIN, y, content_w, font="SemestrStrong", size=17.5, leading=22.0)
    y += 12.0

    # Student statement
    stmt = (
        f"Выдана обучающемуся <b>{escape(student['full_name'])}</b> "
        f"({student['course']} курс, очная форма обучения, подразделение «{escape(student['faculty'])}», "
        f"программа «{escape(student['program'])}», учебная группа <b>{escape(student['student_group'])}</b>, "
        f"студенческий билет {escape(student_meta['card_number'])})."
    )
    y = _draw_para(c, stmt, MARGIN, y, content_w, font="SemestrSans", size=10.3, leading=15.5)
    y += 16.0

    cell_style = ParagraphStyle("tc", fontName="SemestrSans", fontSize=8.8, leading=12.2, textColor=colors.HexColor(INK))
    head_style = ParagraphStyle("th", fontName="SemestrStrong", fontSize=8.5, leading=11.5, textColor=colors.HexColor(MUTED))

    if item["kind"] == "grades" and records:
        rows = [[
            Paragraph("Дисциплина", head_style),
            Paragraph("Контроль", head_style),
            Paragraph("ЗЕТ", head_style),
            Paragraph("Рейтинг", head_style),
            Paragraph("Результат", head_style),
        ]]
        for r in records:
            res_lbl = r["result"] or f"Сессия ({fmt_date(r['date'])})"
            rows.append([
                Paragraph(escape(r["title"]), cell_style),
                Paragraph(escape(r["kind"]), cell_style),
                Paragraph(str(r["credits"]), cell_style),
                Paragraph(f"{r['score']} / 100 ({escape(r['ects'])})", cell_style),
                Paragraph(f"<b>{escape(res_lbl)}</b>", cell_style),
            ])
        col_w = [content_w * 0.36, content_w * 0.15, content_w * 0.09, content_w * 0.18, content_w * 0.22]
        tbl = Table(rows, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(TINT)),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]))
        _, th = tbl.wrapOn(c, content_w, PAGE_H)
        tbl.drawOn(c, MARGIN, PAGE_H - y - th)
        y += th + 16.0
    elif item["kind"] == "income" and scholar:
        rows = [[
            Paragraph("Расчётный период", head_style),
            Paragraph("Вид стипендии / выплаты", head_style),
            Paragraph("Сумма", head_style),
            Paragraph("Статус перечисления", head_style),
        ]]
        for period_lbl, kind_lbl, amount_val, paid_lbl in scholar["history"]:
            rows.append([
                Paragraph(escape(period_lbl), cell_style),
                Paragraph(escape(kind_lbl), cell_style),
                Paragraph(f"<b>{escape(fmt_rub(amount_val))}</b>", cell_style),
                Paragraph(escape(f"{paid_lbl} ({scholar['card_mask']})"), cell_style),
            ])
        col_w = [content_w * 0.24, content_w * 0.34, content_w * 0.16, content_w * 0.26]
        tbl = Table(rows, colWidths=col_w)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(TINT)),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]))
        _, th = tbl.wrapOn(c, content_w, PAGE_H)
        tbl.drawOn(c, MARGIN, PAGE_H - y - th)
        y += th + 16.0
    else:
        if item["kind"] == "military":
            pairs = [
                ("Форма справки", "Приложение № 4 (воинский учёт обучающихся очной формы)"),
                ("Приказ о зачислении", student_meta["order_no"]),
                ("Код и направление", student_meta["program_code"]),
                ("Государственная аккредитация", "Действующая очная программа бакалавриата"),
                ("Нормативный срок окончания", f"До {student_meta['study_end']}"),
                ("Военно-учётный стол", "Корпус В, каб. В–102 · предоставляется по месту учёта"),
            ]
        elif item["kind"] == "dorm_cert" and dorm:
            pairs = [
                ("Объект размещения", f"{dorm['building']} ({dorm['address']})"),
                ("Жилое помещение", dorm["room"]),
                ("Договор найма", f"№ {dorm['contract']}"),
                ("Основание проживания", f"Очное обучение, период до {student_meta['study_end']}"),
            ]
        else:
            pairs = [
                ("Форма и основа обучения", f"{student_meta['degree']} · {student_meta['funding'].lower()}"),
                ("Приказ о зачислении", student_meta["order_no"]),
                ("Нормативный срок обучения", f"До {student_meta['study_end']}"),
                ("Назначение справки", item["comment"] or "По месту требования"),
            ]
        rows = [
            [Paragraph(escape(k), head_style), Paragraph(f"<b>{escape(v)}</b>", cell_style)]
            for k, v in pairs
        ]
        tbl = Table(rows, colWidths=[content_w * 0.36, content_w * 0.64])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(TINT)),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ]))
        _, th = tbl.wrapOn(c, content_w, PAGE_H)
        tbl.drawOn(c, MARGIN, PAGE_H - y - th)
        y += th + 16.0

    # Verification Footer pinned cleanly near bottom of A4
    footer_bottom = 52.0
    footer_h = 108.0
    c.setFillColor(colors.HexColor("#F8FAF9"))
    c.setStrokeColor(colors.HexColor(LINE))
    c.setLineWidth(0.8)
    c.roundRect(MARGIN, footer_bottom, content_w, footer_h, 8, fill=1, stroke=1)

    qr_box = 88.0
    qr_x = PAGE_W - MARGIN - qr_box - 10.0
    qr_y = footer_bottom + (footer_h - qr_box) / 2.0
    _draw_qr(c, verify_url, qr_x, qr_y, qr_box)

    left_w = qr_x - MARGIN - 22.0
    ft_top = PAGE_H - (footer_bottom + footer_h) + 12.0
    masked = mask_full_name(student["full_name"])
    ft_top = _draw_para(
        c,
        "<b>Электронная отметка реестра «Семестр»</b>",
        MARGIN + 12,
        ft_top,
        left_w,
        font="SemestrStrong",
        size=9.8,
        leading=13.5,
        color=ACCENT,
    )
    ft_top = _draw_para(
        c,
        f"Код проверки: <b>{escape(verify_code)}</b> · В публичном реестре ФИО маскируется ({escape(masked)}).<br/>"
        f"Ссылка проверки QR: {escape(verify_url)}",
        MARGIN + 12,
        ft_top + 3,
        left_w,
        font="SemestrSans",
        size=8.3,
        leading=12.0,
        color=INK,
    )
    _draw_para(
        c,
        f"{escape(concept_notice)} Настоящей юридической силы бланк не имеет.",
        MARGIN + 12,
        ft_top + 4,
        left_w,
        font="SemestrSans",
        size=7.6,
        leading=10.8,
        color=MUTED,
    )

    c.showPage()
    c.save()
    return buf.getvalue()
