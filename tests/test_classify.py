"""Kiểm tra nhanh bộ phân loại bằng luật: python tests/test_classify.py"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from classify import classify  # noqa: E402

cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
CASES = [
    ("Khởi công Nhà máy sản xuất nội y cao cấp gần 400 tỷ tại Huế", "Huế", "Khởi công"),
    ("Đường Quảng Ngãi 'rót' hơn 4.700 tỷ vào loạt nhà máy ở Gia Lai", "Gia Lai", "Khác"),
    ("Quảng Trị khởi công khu công nghiệp 450 ha", "Quảng Trị", "Khởi công"),
    ("Gia Lai chấp thuận chủ trương đầu tư nhà máy sản xuất bao bì 90 tỷ đồng", "Gia Lai", "Chấp thuận chủ trương đầu tư"),
    ("Hà Tĩnh: Hơn 16 tỷ USD vốn FDI đầu tư vào Khu kinh tế Vũng Áng", None, None),
    ("Công ty TNHH ABC Việt Nam đề xuất dự án Nhà máy linh kiện điện tử 50 triệu USD tại KCN Hòa Khánh", "Đà Nẵng", "Đề xuất / Nghiên cứu đầu tư"),
    ("Trao chứng nhận đăng ký đầu tư Nhà máy sợi XYZ tại KKT Nhơn Hội, tỉnh Gia Lai", "Bình Định", "Cấp GCN đăng ký đầu tư"),
    ("Tập đoàn Hòa Phát khởi công Nhà máy thép tại Dung Quất", "Quảng Ngãi", "Khởi công"),
    ("Khởi công nhà máy may 300 tỷ tại KCN Hòa Hiệp, Đắk Lắk", "Phú Yên", "Khởi công"),
    ("Khởi công nhà máy chế biến gỗ tại KCN Tây Bắc Đồng Hới, tỉnh Quảng Trị", "Quảng Bình", "Khởi công"),
    ("Đà Nẵng trao chủ trương đầu tư dự án Nhà máy điện tử tại KCN Điện Nam - Điện Ngọc", "Quảng Nam", "Chấp thuận chủ trương đầu tư"),
    ("Giá vàng hôm nay tại Đà Nẵng tăng mạnh", None, None),
    ("Đà Nẵng chấp thuận thí điểm hai dự án nhà ở thương mại, tổng vốn hơn 7.300 tỷ đồng", None, None),
    ("Huế đề xuất bổ sung hơn 58 tỷ đồng trả lương nhân viên y tế", None, None),
    ("Huế đề xuất đầu tư 110 tỷ đồng xử lý 71 \"điểm đen\" trên Quốc lộ 49", None, None),
    ("Người dân Gia Lai đón tin vui: Chính thức khởi công đoạn cao tốc hơn 27.500 tỷ đồng", None, None),
    ("Dự án đường băng hơn 3.200 tỷ đồng tại sân bay Phù Cát sắp xong", None, None),
    ("Phê duyệt chủ trương đầu tư khu đô thị mới 2.000 tỷ đồng tại Quảng Ngãi", None, None),
    ("Hà Tĩnh chấp thuận chủ trương đầu tư trung tâm logistics 39.600 tỷ đồng", None, None),
    ("Đà Nẵng sẽ đấu thầu chọn nhà đầu tư Dự án Nhà máy nước Kiểm Lâm 456 tỷ đồng", None, None),
    ("Carlsberg rót thêm 65 triệu USD vào nhà máy bia lớn nhất châu Á tại Huế", "Huế", "Điều chỉnh / Mở rộng / Tăng vốn"),
    ("Cấp chứng nhận đầu tư dự án công nghiệp hơn 2.373 tỷ đồng tại Khu công nghiệp Bắc Thạch Hà", "Hà Tĩnh", "Cấp GCN đăng ký đầu tư"),
]
fails = 0
for title, prov, status in CASES:
    out = classify([dict(title=title, summary="", link="https://x/" + title, source="t", origin="bing", published=None)], cfg)
    got = (out[0]["province"], out[0]["status"]) if out else (None, None)
    ok = got == (prov, status)
    fails += not ok
    extra = f"| {out[0]['project']} | {out[0]['investor']} | {out[0]['capital']}" if out else ""
    print("OK  " if ok else "FAIL", title[:60], "->", got, extra)
sys.exit(1 if fails else 0)
