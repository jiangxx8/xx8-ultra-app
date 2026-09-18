XX8 UNIFIED - MINI APP + QUẢN LÝ TELEGRAM ID

/                 Mini App Telegram
/admin/login      Đăng nhập quản lý
/admin            Quản lý Telegram ID
/health           Kiểm tra server

Render Environment Variables:
BOT_TOKEN=...
MANAGER_CHAT_ID=...
WEB_ADMIN_USERNAME=admin
WEB_ADMIN_PASSWORD=đổi_mật_khẩu_mạnh
WEB_SECRET_KEY=chuỗi_ngẫu_nhiên_dài
APP_TIMEZONE=Asia/Tbilisi

Bản này KHÔNG dùng ALLOWED_TELEGRAM_IDS nữa.
Mini App đọc quyền trực tiếp từ users.db.
Nếu quản lý TẮT ID -> Mini App từ chối ngay.
Nếu đổi bộ phận -> Mini App chỉ hiện ca của bộ phận mới.

LƯU Ý RENDER FREE:
SQLite nằm trên filesystem của service. Thay đổi admin có thể mất khi service bị redeploy/recreate.
Để dùng lâu dài: dùng persistent disk hoặc chuyển database sang PostgreSQL.
