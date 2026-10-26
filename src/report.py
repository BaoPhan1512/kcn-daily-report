"""Xuất báo cáo PDF tiếng Việt."""
import os
import urllib.parse
from collections import Counter
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
pdfmetrics.registerFont(TTFont("DV", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DV-B", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV", boldItalic="DV-B")

NAVY = colors.HexColor("#1F3A5F")
LIGHT = colors.HexColor("#F2F5F9")
GRID = colors.HexColor("#C9D3E0")
BAND = colors.HexColor("#DCE6F2")
STATUS_COLORS = {
    "Đề xuất / Nghiên cứu đầu tư": "#DB2777",
    "Chấp thuận chủ trương đầu tư": "#2563EB",
    "Cấp GCN đăng ký đầu tư": "#7C3AED",
    "Điều chỉnh / Mở rộng / Tăng vốn": "#0D9488",
    "Khởi công": "#EA580C",
    "Khánh thành / Đi vào hoạt động": "#16A34A",
    "Khác": "#9CA3AF",
}
STATUS_FLOW = list(STATUS_COLORS)

S_TITLE = ParagraphStyle("t", fontName="DV-B", fontSize=17, textColor=NAVY, leading=21)
S_SUB = ParagraphStyle("s", fontName="DV", fontSize=9.5, textColor=colors.HexColor("#4B5563"), leading=13)
S_H2 = ParagraphStyle("h2", fontName="DV-B", fontSize=12, textColor=NAVY, leading=15, spaceBefore=8, spaceAfter=4)
S_CELL = ParagraphStyle("c", fontName="DV", fontSize=8.2, leading=10.5)
S_CELL_B = ParagraphStyle("cb", parent=S_CELL, fontName="DV-B")
S_HEAD = ParagraphStyle("hd", fontName="DV-B", fontSize=8.5, leading=11, textColor=colors.white)
S_CENTER = ParagraphStyle("cc", parent=S_CELL, alignment=TA_CENTER)
S_BAND = ParagraphStyle("b", fontName="DV-B", fontSize=9.5, leading=12, textColor=NAVY)
S_NOTE = ParagraphStyle("n", fontName="DV", fontSize=7.5, leading=10, textColor=colors.HexColor("#6B7280"))


def P(text, style=S_CELL):
    return Paragraph(escape(text or ""), style)


def _status_cell(status):
    c = STATUS_COLORS.get(status, "#9CA3AF")
    dot = "○" if status == "Khác" else "●"  # "Khác" dùng chấm rỗng để khác hẳn các tình trạng có màu
    return Paragraph(f'<font color="{c}"><b>{dot}</b></font> {escape(status)}', S_CELL)


def _link_cell(url, source):
    host = urllib.parse.urlparse(url).netloc.replace("www.", "")
    label = source if host.startswith("news.google") else host
    return Paragraph(f'<link href="{escape(url)}"><font color="#2563EB"><u>{escape(label or "Mở link")}</u></font></link>', S_CELL)


def _summary_table(items, cfg):
    by_prov = Counter(i["province"] for i in items)
    by_status = Counter(i["status"] for i in items)
    head = [Paragraph("Tỉnh (cũ)", S_HEAD)] + [Paragraph(s, S_HEAD) for s in STATUS_FLOW] + [Paragraph("Tổng", S_HEAD)]
    rows = [head]
    for p in cfg["provinces"]:
        name = p["name"]
        cnt = Counter(i["status"] for i in items if i["province"] == name)
        rows.append([P(name, S_CELL_B)] + [P(str(cnt.get(s, "")) or "", S_CENTER) for s in STATUS_FLOW]
                    + [P(str(by_prov.get(name, 0)), S_CENTER)])
    rows.append([P("Tổng", S_CELL_B)] + [P(str(by_status.get(s, 0)), S_CENTER) for s in STATUS_FLOW]
                + [P(str(len(items)), S_CENTER)])
    t = Table(rows, colWidths=[34 * mm] + [30 * mm] * len(STATUS_FLOW) + [16 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _detail_table(items, cfg):
    """Một bảng duy nhất, mỗi tỉnh là một dải tiêu đề, tiêu đề cột lặp lại ở mỗi trang."""
    head = ["STT", "Tên dự án", "Tình trạng", "Tỉnh (cũ)", "Chủ đầu tư", "Nguồn"]
    rows = [[Paragraph(h, S_HEAD) for h in head]]
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    n = 0
    for p in cfg["provinces"]:
        grp = [i for i in items if i["province"] == p["name"]]
        if not grp:
            continue
        r = len(rows)
        rows.append([Paragraph(f"{escape(p['name'])} <font color='#6B7280'>({len(grp)})</font>", S_BAND)] + [""] * 5)
        style += [("SPAN", (0, r), (-1, r)), ("BACKGROUND", (0, r), (-1, r), BAND)]
        for k, it in enumerate(grp):
            n += 1
            name = escape(it["project"])
            if it.get("capital"):
                name += f'<br/><font color="#6B7280" size="7.5">Vốn: {escape(it["capital"])}</font>'
            prov = it["province"]
            if it.get("province_new") and it["province_new"] != prov:
                prov += f"\n(nay: {it['province_new']})"
            if k % 2:
                style.append(("BACKGROUND", (0, len(rows)), (-1, len(rows)), LIGHT))
            rows.append([
                P(str(n), S_CENTER),
                Paragraph(name, S_CELL_B),
                _status_cell(it["status"]),
                P(prov),
                P(it["investor"] or "—"),
                _link_cell(it["link"], it["source"]),
            ])
    widths = [12 * mm, 88 * mm, 44 * mm, 28 * mm, 59 * mm, 39 * mm]
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


def build_pdf(items, cfg, path, report_date, ai_used):
    doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"Báo cáo dự án mới KCN miền Trung {report_date}", author="KCN Daily Bot")
    story = [
        Paragraph("BÁO CÁO DỰ ÁN ĐẦU TƯ MỚI – KCN/KKT MIỀN TRUNG &amp; TÂY NGUYÊN", S_TITLE),
        Paragraph(f"Ngày {report_date} · Tin thu thập trong khoảng {cfg['lookback_hours']} giờ trước 21:00 tối hôm trước · "
                  f"{len(items)} dự án/tin mới · Phân loại: {'AI (Gemini) + luật' if ai_used else 'luật từ khóa'}", S_SUB),
        Spacer(1, 6),
        Paragraph("Tổng hợp theo tỉnh và tình trạng", S_H2),
        _summary_table(items, cfg),
    ]
    order = {p["name"]: k for k, p in enumerate(cfg["provinces"])}
    items = sorted(items, key=lambda i: (order.get(i["province"], 99), STATUS_FLOW.index(i["status"])
                                         if i["status"] in STATUS_FLOW else 99))
    if not items:
        story += [Spacer(1, 10), Paragraph("Không ghi nhận dự án mới nào trong 24 giờ qua.", S_SUB)]
    else:
        story += [Paragraph("Danh sách dự án", S_H2), _detail_table(items, cfg)]
    story += [Spacer(1, 10), Paragraph(
        "Ghi chú: Tỉnh ghi theo địa giới cũ (trước 1/7/2025); “nay” là tỉnh/thành sau sáp nhập. Tình trạng và chủ đầu tư được trích "
        "tự động từ tiêu đề/tóm tắt bài báo nên có thể chưa chính xác, hãy mở link nguồn để kiểm tra. Nguồn: Google News, Bing News, "
        "trang tin các Ban quản lý KCN/KKT.", S_NOTE)]

    def on_page(canvas, d):
        canvas.saveState()
        canvas.setFont("DV", 7.5)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawRightString(d.pagesize[0] - 12 * mm, 7 * mm, f"Trang {d.page}")
        canvas.drawString(12 * mm, 7 * mm, f"KCN Daily Report · {report_date}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
