"""KCN Daily Report.

  python src/main.py collect   # 21:00 giờ VN: thu thập, phân loại, xuất PDF cho ngày hôm sau
  python src/main.py send      # 06:15 giờ VN: gửi PDF của ngày hôm nay qua Telegram
  python src/main.py chatid    # in ID nhóm Telegram (cần TELEGRAM_BOT_TOKEN)
  python src/main.py demo      # tạo PDF mẫu từ data/sample.json (không cần mạng)
"""
import json
import os
import sys
import time
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


REPORT_PREFIX = "Daily Report_New Project_"


def pdf_path(date_str):
    return os.path.join(ROOT, "reports", f"{REPORT_PREFIX}{date_str}.pdf")


def seen_key(it):
    # Có cả tình trạng: dự án cũ chuyển sang giai đoạn mới (vd. từ chủ trương sang khởi công) sẽ được báo lại
    return f"{it['province']}|{strip_accents(norm(it['project']))[:60]}|{it['status']}"


# Lịch của GitHub có thể trễ hoặc bỏ lượt, nên mỗi việc được lên lịch nhiều lần; file đánh dấu
# giúp chỉ lượt đầu tiên thực sự chạy. Chạy bằng tay (Run workflow) thì luôn chạy.
SCHEDULED = os.environ.get("GITHUB_EVENT_NAME") == "schedule"


def marker(kind, date_str):
    return os.path.join(ROOT, "data", kind, f"{date_str}.txt")


def write_marker(kind, date_str):
    path = marker(kind, date_str)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(datetime.now(VN).isoformat())


def cmd_collect():
    from collect import collect_all, resolve_google_link

    cfg = load_json(os.path.join(ROOT, "config.json"), None)
    sites = load_json(os.path.join(ROOT, "sites.json"), {}).get("sites", [])
    now = datetime.now(VN)
    report_date = (now + timedelta(hours=6)).strftime("%Y-%m-%d")  # chạy 21h -> báo cáo cho sáng mai
    if SCHEDULED and os.path.exists(marker("collected", report_date)):
        print(f"Báo cáo {report_date} đã được tạo ở lượt trước, bỏ qua.")
        return

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
    write_marker("collected", report_date)
    print(f"Đã tạo {pdf_path(report_date)} với {len(fresh)} dự án.")


def tg(method, **kw):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", timeout=60, **kw)
    if not r.ok:
        raise SystemExit(f"Telegram lỗi {r.status_code}: {r.text[:300]}")


SEND_AT = (6, 15)        # giờ gửi (giờ VN)
LAST_TRY = (7, 15)       # sau giờ này mà vẫn chưa có báo cáo thì báo lỗi vào nhóm


def cmd_send():
    chat = os.environ["TELEGRAM_CHAT_ID"]
    now = datetime.now(VN)
    date_str = now.strftime("%Y-%m-%d")
    if SCHEDULED:
        if os.path.exists(marker("sent", date_str)):
            print(f"Báo cáo {date_str} đã gửi ở lượt trước, bỏ qua.")
            return
        send_at = now.replace(hour=SEND_AT[0], minute=SEND_AT[1], second=0, microsecond=0)
        if now < send_at:
            wait = (send_at - now).total_seconds()
            print(f"Lượt chạy sớm, chờ {wait / 60:.0f} phút đến {SEND_AT[0]:02d}:{SEND_AT[1]:02d}...")
            time.sleep(wait)
    path = pdf_path(date_str)
    if not os.path.exists(path):
        # Chạy thử bằng tay trước 0h: báo cáo mới nhất mang ngày mai
        n = len(REPORT_PREFIX)
        newer = sorted(f[n:n + 10] for f in os.listdir(os.path.join(ROOT, "reports"))
                       if f.startswith(REPORT_PREFIX) and f[n:n + 4].isdigit() and f[n:n + 10] > date_str)
        if newer:
            date_str, path = newer[-1], pdf_path(newer[-1])
    if not os.path.exists(path):
        if SCHEDULED and (datetime.now(VN).hour, datetime.now(VN).minute) < LAST_TRY:
            print("Chưa có báo cáo, để lượt dự phòng sau thử lại.")
            return
        tg("sendMessage", data={"chat_id": chat, "text": f"⚠️ Chưa có báo cáo ngày {date_str} (lượt thu thập 21h có thể bị lỗi). Kiểm tra tab Actions trên GitHub."})
        write_marker("sent", date_str)
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
    write_marker("sent", date_str)
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


def cmd_check():
    """Kiểm tra các Secrets: Telegram token, chat id, Gemini key (không in giá trị key)."""
    ok = True
    token, chat, gkey = (os.environ.get(k, "").strip() for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GEMINI_API_KEY"))
    if not token:
        ok = False
        print("❌ Thiếu TELEGRAM_BOT_TOKEN")
    else:
        me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=30).json()
        print(f"✅ Token Telegram đúng, bot @{me['result']['username']}" if me.get("ok") else f"❌ Token Telegram sai: {me.get('description')}")
        ok &= bool(me.get("ok"))
        if not chat:
            ok = False
            print("❌ Thiếu TELEGRAM_CHAT_ID")
        else:
            c = requests.get(f"https://api.telegram.org/bot{token}/getChat", params={"chat_id": chat}, timeout=30).json()
            print(f"✅ Chat id đúng: {c['result'].get('title') or c['result'].get('first_name')}" if c.get("ok") else f"❌ Chat id sai: {c.get('description')}")
            ok &= bool(c.get("ok"))
    if not gkey:
        print("⚠️ Chưa có GEMINI_API_KEY (bot vẫn chạy bằng luật từ khóa)")
    else:
        cfg = load_json(os.path.join(ROOT, "config.json"), {})
        from classify import gemini_call, gemini_models
        models = gemini_models(gkey, cfg.get("gemini_model", "gemini-2.5-flash"))
        print(f"   Thử lần lượt: {', '.join(models)}")
        try:
            used, _ = gemini_call(gkey, models, {"contents": [{"parts": [{"text": "Trả lời đúng một từ: OK"}]}]}, timeout=240)
            print(f"✅ Gemini key hoạt động (model {used})")
        except RuntimeError as e:
            msg = str(e)
            if any(f"HTTP {c}" in msg for c in (400, 401, 403)):
                ok = False
                print(f"❌ Gemini key sai hoặc chưa được bật: {msg}")
            else:
                print(f"⚠️ Key hợp lệ nhưng Gemini đang quá tải, bot sẽ tự thử lại khi chạy: {msg}")
    if not ok:
        raise SystemExit(1)


def cmd_demo():
    cfg = load_json(os.path.join(ROOT, "config.json"), None)
    items = load_json(os.path.join(ROOT, "data", "sample.json"), [])
    out = os.path.join(ROOT, "reports", f"{REPORT_PREFIX}SAMPLE.pdf")
    build_pdf(items, cfg, out, datetime.now(VN).strftime("%Y-%m-%d"), False)
    print(out)


if __name__ == "__main__":
    {"collect": cmd_collect, "send": cmd_send, "demo": cmd_demo, "chatid": cmd_chatid, "check": cmd_check}[sys.argv[1] if len(sys.argv) > 1 else "collect"]()
