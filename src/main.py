"""KCN Daily Report.

  python src/main.py collect   # 21:00 giờ VN: thu thập, phân loại, xuất PDF cho ngày hôm sau
  python src/main.py send      # 06:15 giờ VN: gửi PDF của ngày hôm nay qua Telegram
  python src/main.py chatid    # in ID nhóm Telegram (cần TELEGRAM_BOT_TOKEN)
  python src/main.py demo      # tạo PDF mẫu từ data/sample.json (không cần mạng)
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(__file__))
from classify import classify, norm, strip_accents  # noqa: E402
from report import build_pdf  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VN = timezone(timedelta(hours=7))
SEEN_PATH = os.path.join(ROOT, "data", "seen.json")
SEEN_DAYS = 45


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def pdf_path(date_str):
    return os.path.join(ROOT, "reports", f"BaoCao_DuAnMoi_{date_str}.pdf")


def seen_key(it):
    # Có cả tình trạng: dự án cũ chuyển sang giai đoạn mới (vd. từ chủ trương sang khởi công) sẽ được báo lại
    return f"{it['province']}|{strip_accents(norm(it['project']))[:60]}|{it['status']}"


def cmd_collect():
    from collect import collect_all, resolve_google_link

    cfg = load_json(os.path.join(ROOT, "config.json"), None)
    sites = load_json(os.path.join(ROOT, "sites.json"), {}).get("sites", [])
    now = datetime.now(VN)
    report_date = (now + timedelta(hours=6)).strftime("%Y-%m-%d")  # chạy 21h -> báo cáo cho sáng mai

    print("Thu thập tin...")
    raw = collect_all(cfg, sites)
    print(f"Tổng {len(raw)} tin thô. Phân loại...")
    items = classify(raw, cfg)

    seen = load_json(SEEN_PATH, {})
    cutoff = (now - timedelta(days=SEEN_DAYS)).strftime("%Y-%m-%d")
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    known_sites = {k.split("|", 2)[1] for k in seen if k.startswith("site|")}

    fresh = []
    for it in items:
        if seen_key(it) in seen or f"link|{it['link']}" in seen:
            continue
        # Lần đầu quét một trang BQL: chỉ ghi nhớ, không báo (tránh dồn hàng trăm tin cũ)
        if it["origin"] == "site" and it["source"] not in known_sites:
            seen[f"link|{it['link']}"] = report_date
            continue
        fresh.append(it)
    for s in sites:
        seen[f"site|{s['name']}|"] = report_date

    fresh = fresh[: cfg["max_items_in_report"]]
    for it in fresh:
        it["link"] = resolve_google_link(it["link"])
        seen[seen_key(it)] = report_date
        seen[f"link|{it['link']}"] = report_date
    save_json(SEEN_PATH, seen)
    # Chạy lại trong cùng buổi tối thì cộng dồn, không ghi đè báo cáo đã có
    data_path = os.path.join(ROOT, "data", f"{report_date}.json")
    fresh = load_json(data_path, []) + fresh
    save_json(data_path, fresh)

    build_pdf(fresh, cfg, pdf_path(report_date), report_date, bool(os.environ.get("GEMINI_API_KEY")))
    print(f"Đã tạo {pdf_path(report_date)} với {len(fresh)} dự án.")


def tg(method, **kw):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", timeout=60, **kw)
    if not r.ok:
        raise SystemExit(f"Telegram lỗi {r.status_code}: {r.text[:300]}")


def cmd_send():
    chat = os.environ["TELEGRAM_CHAT_ID"]
    date_str = datetime.now(VN).strftime("%Y-%m-%d")
    path = pdf_path(date_str)
    if not os.path.exists(path):
        # Chạy thử bằng tay trước 0h: báo cáo mới nhất mang ngày mai
        newer = sorted(f[15:25] for f in os.listdir(os.path.join(ROOT, "reports"))
                       if f.startswith("BaoCao_DuAnMoi_") and f[15:25] > date_str)
        if newer:
            date_str, path = newer[-1], pdf_path(newer[-1])
    if not os.path.exists(path):
        tg("sendMessage", data={"chat_id": chat, "text": f"⚠️ Chưa có báo cáo ngày {date_str} (lượt thu thập 21h có thể bị lỗi). Kiểm tra tab Actions trên GitHub."})
        return
    items = load_json(os.path.join(ROOT, "data", f"{date_str}.json"), [])
    by_status = Counter(i["status"] for i in items)
    by_prov = Counter(i["province"] for i in items)
    lines = [f"📊 Báo cáo dự án mới KCN – {datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')}",
             f"Tổng: {len(items)} dự án/tin mới"]
    if items:
        lines.append("• " + " · ".join(f"{k}: {v}" for k, v in by_status.most_common()))
        lines.append("• Nhiều nhất: " + ", ".join(f"{k} ({v})" for k, v in by_prov.most_common(4)))
    with open(path, "rb") as f:
        tg("sendDocument", data={"chat_id": chat, "caption": "\n".join(lines)[:1000]},
           files={"document": (os.path.basename(path), f, "application/pdf")})
    print("Đã gửi Telegram.")


def cmd_chatid():
    """In ra ID các nhóm/người đã nhắn cho bot gần đây (dùng để điền TELEGRAM_CHAT_ID)."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
    if not r.get("ok"):
        raise SystemExit(f"Token sai hoặc lỗi Telegram: {r}")
    chats = {}
    for u in r["result"]:
        for key in ("message", "channel_post", "my_chat_member", "edited_message"):
            c = u.get(key, {}).get("chat")
            if c:
                chats[c["id"]] = c
    if not chats:
        print("Chưa thấy tin nhắn nào. Hãy gõ /start@<tên_bot> trong nhóm rồi chạy lại.")
    for cid, c in chats.items():
        print(f"ID: {cid}  |  loại: {c.get('type')}  |  tên: {c.get('title') or c.get('first_name')}  |  @{c.get('username', '')}")


def cmd_demo():
    cfg = load_json(os.path.join(ROOT, "config.json"), None)
    items = load_json(os.path.join(ROOT, "data", "sample.json"), [])
    out = os.path.join(ROOT, "reports", "BaoCao_MAU.pdf")
    build_pdf(items, cfg, out, datetime.now(VN).strftime("%Y-%m-%d"), False)
    print(out)


if __name__ == "__main__":
    {"collect": cmd_collect, "send": cmd_send, "demo": cmd_demo, "chatid": cmd_chatid}[sys.argv[1] if len(sys.argv) > 1 else "collect"]()
