# KCN Daily Report – Bot báo cáo dự án đầu tư mới tại KCN/KKT

Bot miễn phí, chạy tự động trên GitHub Actions:

| Giờ Việt Nam | Việc làm |
|---|---|
| **21:00** | Tìm tin mới trên Google News, Bing News và trang tin các Ban quản lý KCN/KKT của 11 tỉnh (cũ): Hà Tĩnh, Quảng Bình, Quảng Trị, Huế, Đà Nẵng, Quảng Nam, Quảng Ngãi, Bình Định, Phú Yên, Kon Tum, Gia Lai. Lọc, phân loại, bỏ trùng, xuất PDF. |
| **06:15** | Gửi file PDF kèm tóm tắt vào Telegram. |

Mỗi dòng trong báo cáo có: **Tên dự án · Tình trạng · Tỉnh (cũ, kèm tỉnh mới) · Chủ đầu tư · 1 link nguồn** (và vốn đầu tư nếu có).
Tình trạng gồm: Đề xuất / Nghiên cứu đầu tư → Chấp thuận chủ trương đầu tư → Cấp GCN đăng ký đầu tư → Điều chỉnh / Mở rộng / Tăng vốn → Khởi công → Khánh thành / Đi vào hoạt động.

Bot chỉ giữ dự án **sản xuất công nghiệp** và hạ tầng KCN/CCN. Tin về nhà ở, khu đô thị, tái định cư, thương mại, du lịch, giao thông (quốc lộ, cao tốc, sân bay, cảng), logistics, đầu tư công, y tế, giáo dục, lương, nhà máy nước, xử lý rác... bị loại. Danh sách từ khóa lọc nằm trong mục `industry_filter` của `config.json`.

Bot nhớ các dự án đã báo trong 45 ngày nên không lặp lại; một dự án chuyển sang giai đoạn mới (vd. từ chủ trương sang khởi công) sẽ được báo lại.

## Chi phí: 0 đồng

- GitHub Actions: repo **Private** được 2.000 phút miễn phí/tháng, bot dùng khoảng 400–600 phút. Repo Public thì không giới hạn.
- Telegram Bot: miễn phí.
- Gemini API (không bắt buộc): gói miễn phí của Google AI Studio, đủ cho vài trăm tin/ngày. Không có key thì bot vẫn chạy bằng bộ luật từ khóa, chỉ kém chính xác hơn ở tên dự án và chủ đầu tư.

## Cài đặt (khoảng 15 phút)

1. **Tạo repo** trên GitHub (vd. `kcn-daily-report`; Public thì Actions miễn phí không giới hạn, nhưng báo cáo PDF trong `reports/` ai cũng xem được) và đưa toàn bộ thư mục này lên.
2. **Tạo bot Telegram**: mở Telegram, chat với `@BotFather`, gõ `/newbot`, đặt tên. BotFather trả về *token*.
3. **Lấy chat id**: nhắn một tin bất kỳ cho bot vừa tạo (hoặc thêm bot vào nhóm và nhắn trong nhóm), rồi mở trình duyệt:
   `https://api.telegram.org/bot<TOKEN>/getUpdates` và tìm `"chat":{"id": ...}`. Nhóm có id âm, ví dụ `-100123...`.
4. *(Khuyến nghị)* **Lấy Gemini API key** miễn phí tại https://aistudio.google.com/apikey.
5. Trong repo: **Settings → Secrets and variables → Actions → New repository secret**, tạo:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `GEMINI_API_KEY` (nếu có)
6. **Settings → Actions → General → Workflow permissions**: chọn *Read and write permissions* (để bot lưu báo cáo vào repo).
7. Chạy thử: tab **Actions → "Thu thap tin 21h" → Run workflow**. Xong thì chạy **"Gui bao cao 6h15" → Run workflow**, PDF sẽ về Telegram.

Từ đó bot tự chạy mỗi ngày. Mọi báo cáo cũ lưu trong thư mục `reports/`.

## Tùy chỉnh

- `config.json`: bộ lọc ngành (`industry_filter`), tỉnh, tên KCN/KKT/huyện để nhận diện tỉnh cũ, từ khóa tìm kiếm, từ khóa loại trừ, số giờ quét lùi.
- `sites.json`: trang tin của các BQL KCN/KKT. Hãy kiểm tra lại URL (bot tự bỏ qua link chết, xem log trong tab Actions).
- Kiểm tra bộ phân loại: `python tests/test_classify.py`. Tạo PDF mẫu không cần mạng: `python src/main.py demo`.

## Giới hạn cần biết

- **Facebook, LinkedIn**: không có cách lấy tin miễn phí và hợp lệ (đăng nhập, chặn bot, điều khoản cấm thu thập). Phần lớn tin trên các fanpage BQL/UBND cũng được báo chí đăng lại nên vẫn được Google News bắt được.
- Các trang thông tin dự án trả phí (vd. BCI, Vietnam Construction, …) cần tài khoản nên không đưa vào.
- GitHub có thể chạy lịch trễ 5–20 phút lúc cao điểm; báo cáo vẫn về trước khoảng 06:35.
- Repo không có hoạt động 60 ngày thì GitHub tắt lịch chạy; bot tự commit báo cáo mỗi ngày nên không bị ảnh hưởng.
- Sau sáp nhập tỉnh (1/7/2025), báo chí dùng tên tỉnh mới. Bot xác định tỉnh cũ qua tên KCN/KKT/huyện; tin chỉ ghi chung "tỉnh Gia Lai" mà không nói địa danh cụ thể sẽ được xếp vào Gia Lai (cũ).
