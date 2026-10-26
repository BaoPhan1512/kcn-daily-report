"""Thu thập tin bài về dự án mới từ Google News, Bing News và trang web các BQL KCN/KKT."""
import base64
import email.utils
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
TIMEOUT = 25


def _get(url):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 503):
                time.sleep(5 * (attempt + 1))
                continue
            return None
        except requests.RequestException:
            time.sleep(3)
    return None


def _parse_date(s):
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _clean_html(s):
    return BeautifulSoup(s or "", "html.parser").get_text(" ", strip=True)


def _parse_rss(xml_bytes, origin):
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src = it.find("source")
        source_name = src.text.strip() if src is not None and src.text else ""
        if origin == "google" and source_name and title.endswith(" - " + source_name):
            title = title[: -len(" - " + source_name)]
        items.append({
            "title": title,
            "link": link,
            "summary": _clean_html(it.findtext("description"))[:600],
            "published": _parse_date(it.findtext("pubDate")),
            "source": source_name or urllib.parse.urlparse(link).netloc,
            "origin": origin,
        })
    return items


def google_news(query, lookback_hours):
    days = max(1, round(lookback_hours / 24))
    q = urllib.parse.quote(f"{query} when:{days}d")
    r = _get(f"https://news.google.com/rss/search?q={q}&hl=vi&gl=VN&ceid=VN:vi")
    return _parse_rss(r.content, "google") if r else []


def _unwrap_bing(link):
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    return qs.get("url", [link])[0]


def bing_news(query):
    q = urllib.parse.quote(query)
    r = _get(f"https://www.bing.com/news/search?q={q}&format=rss&setlang=vi-VN&cc=VN&qft=sortbydate%3d%221%22")
    items = _parse_rss(r.content, "bing") if r else []
    for it in items:
        it["link"] = _unwrap_bing(it["link"])
        it["source"] = urllib.parse.urlparse(it["link"]).netloc
    return items


def resolve_google_link(link):
    """Đổi link news.google.com/rss/articles/... sang link bài báo gốc (nếu được)."""
    if "news.google.com" not in link:
        return link
    try:
        art_id = urllib.parse.urlparse(link).path.rsplit("/", 1)[-1]
        # Kiểu cũ: link gốc nằm thẳng trong id base64
        raw = base64.urlsafe_b64decode(art_id + "=" * (-len(art_id) % 4))
        m = re.search(rb"https?://[\x21-\x7e]+", raw)
        if m and b"AU_yqL" not in raw[:8]:
            return m.group(0).decode("utf-8", "ignore")
        # Kiểu mới: gọi batchexecute với chữ ký lấy từ trang bài
        page = _get(f"https://news.google.com/rss/articles/{art_id}")
        if not page:
            return link
        div = BeautifulSoup(page.text, "html.parser").select_one("c-wiz > div[jscontroller]")
        if not div or not div.get("data-n-a-sg"):
            return link
        payload = [
            "Fbv4je",
            f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{art_id}",{div["data-n-a-ts"]},"{div["data-n-a-sg"]}"]',
        ]
        r = requests.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data=f"f.req={urllib.parse.quote(json.dumps([[payload]]))}",
            timeout=TIMEOUT,
        )
        data = json.loads(r.text.split("\n\n", 1)[1])[:-2]
        return json.loads(data[0][2])[1]
    except Exception:
        return link


KEYWORD_RE = re.compile(
    r"nhà máy|dự án|khởi công|động thổ|chủ trương đầu tư|chứng nhận đăng ký đầu tư|fdi|nhà đầu tư|khánh thành",
    re.I,
)


def site_pages(sites):
    """Quét trang tin của BQL KCN/KKT: lấy các link có tiêu đề chứa từ khóa đầu tư."""
    items = []
    for s in sites:
        r = _get(s["url"])
        if not r:
            print(f"  [!] Không tải được {s['url']}")
            continue
        soup = BeautifulSoup(r.content, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True) or a.get("title", "")
            if len(text) < 25 or not KEYWORD_RE.search(text):
                continue
            href = urllib.parse.urljoin(s["url"], a["href"])
            if href in seen:
                continue
            seen.add(href)
            items.append({
                "title": text[:250],
                "link": href,
                "summary": "",
                "published": None,
                "source": s["name"],
                "origin": "site",
                "province_hint": s.get("province"),
            })
    return items


def collect_all(cfg, sites):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=cfg["lookback_hours"])
    raw = []
    for p in cfg["provinces"]:
        for kw in cfg["search_keywords"]:
            query = f"({p['query']}) {kw}"
            g = google_news(query, cfg["lookback_hours"])
            b = bing_news(f"{p['name']} {kw}")
            raw += g + b
            time.sleep(1)
        print(f"  {p['name']}: tổng tích lũy {len(raw)} tin")
    raw = [x for x in raw if x["published"] is None or x["published"] >= cutoff]
    raw += site_pages(sites)
    print(f"  Trang BQL: tổng {len(raw)} tin")
    return raw
