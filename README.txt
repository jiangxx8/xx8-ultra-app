XX8 MINI APP ĐƠN GIẢN

Mục đích:
- Nhân viên mở "Ứng dụng" ngay trong bot Telegram.
- Nhập ULTRA ID.
- Bấm XÁC NHẬN GỬI.
- Server xác minh tài khoản Telegram.
- Chỉ Telegram ID được cấp quyền mới dùng được.
- ULTRA ID được gửi thẳng đến nhóm quản lý.

CẤU HÌNH BẮT BUỘC TRÊN HOSTING:
1) BOT_TOKEN
   Token bot Telegram của bạn. KHÔNG đặt token trong index.html.

2) MANAGER_CHAT_ID
   Chat ID của nhóm quản lý, ví dụ: -1001234567890

3) ALLOWED_TELEGRAM_IDS
   Danh sách Telegram ID của nhân viên, ngăn cách bằng dấu phẩy.
   Ví dụ: 111111111,222222222,333333333

CHẠY THỬ:
pip install -r requirements.txt
set BOT_TOKEN=...
set MANAGER_CHAT_ID=...
set ALLOWED_TELEGRAM_IDS=...
python app.py

Sau khi deploy:
- Bạn phải có URL HTTPS, ví dụ https://xx8-ultra.example.com
- Mở @BotFather
- /setmenubutton
- Chọn bot
- Đặt tên nút: MỞ ỨNG DỤNG
- Điền URL HTTPS của web

Lưu ý:
- File này chỉ nhận ULTRA ID, KHÔNG nhận mật khẩu.
- Người dùng mở URL ngoài Telegram sẽ không gửi được.
- Server kiểm tra chữ ký Telegram trước khi chấp nhận dữ liệu.
