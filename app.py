import os
import json
import hmac
import hashlib
import time
import html
from datetime import datetime
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID", "").strip()
ALLOWED_TELEGRAM_IDS = {
    x.strip()
    for x in os.getenv("ALLOWED_TELEGRAM_IDS", "").split(",")
    if x.strip()
}

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Tbilisi").strip() or "Asia/Tbilisi"

DEPARTMENT_MANAGERS = {
    "FK": (
        "@golayxx8",
        "@Anhtaytay",
        "@kenvinxx8",
        "@zata433",
        "@MAKUNXX86764",
        "@adidasxx8",
    ),
    "CSKH": (
        "@lilyxx8123",
        "@yuxi6676",
        "@doraabcvip",
        "@hihinhungdangkhocccc",
        "@riverdayroi",
    ),
    "XNK": (
        "@jiangabcvip",
        "@asongbakjang",
        "@cucdangneee",
        "@baothanhthien1302",
        "@laurenxx8",
    ),
}

SHIFTS = {
    "MORNING": {"name": "☀️ CA SÁNG", "time": "08:00 - 18:00"},
    "MIDDLE": {"name": "🌤 CA TRUNG", "time": "16:00 - 02:00"},
    "NIGHT": {"name": "🌙 CA ĐÊM", "time": "22:00 - 08:00"},
}

VALID_ACTIONS = {
    "CHECK_IN": ("VÀO CA", "🟢"),
    "CHECK_OUT": ("RA CA", "🔴"),
}

VALID_DEPARTMENTS = {"XNK", "FK", "CSKH"}

# Chặn click liên tục trên cùng 1 tiến trình Render
_recent_submit = {}


def validate_telegram_init_data(init_data: str, max_age_seconds: int = 3600):
    if not BOT_TOKEN or not init_data:
        return None, "Thiếu cấu hình BOT_TOKEN hoặc dữ liệu Telegram."

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None, "Không có chữ ký Telegram."

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(pairs.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return None, "Dữ liệu Telegram không hợp lệ."

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        return None, "auth_date không hợp lệ."

    if not auth_date or abs(time.time() - auth_date) > max_age_seconds:
        return None, "Phiên Telegram đã hết hạn. Hãy đóng và mở lại ứng dụng."

    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        return None, "Không đọc được tài khoản Telegram."

    if not user.get("id"):
        return None, "Không tìm thấy Telegram ID."

    return user, None


def safe(value):
    return html.escape(str(value), quote=False)


def send_report(user, action_code, department, shift_code, ultra_id, ultra_password):
    action, action_icon = VALID_ACTIONS[action_code]
    shift = SHIFTS[shift_code]

    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    sender_name = (first_name + " " + last_name).strip() or "Không có tên"
    username = user.get("username")
    sender_username = f"@{username}" if username else "None"

    managers = " ".join(DEPARTMENT_MANAGERS.get(department, ())) or "Không xác định"

    try:
        tz = ZoneInfo(APP_TIMEZONE)
    except Exception:
        tz = ZoneInfo("UTC")

    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    message = f"""<b>📢 ĐIỂM DANH BỘ PHẬN ONLINE XX8 </b>

{action_icon} <b>Trạng thái: {safe(action)}</b>

🏢 <b>Bộ phận:</b> {safe(department)}

🕐 <b>Ca làm việc:</b> {safe(shift["name"])}
⏰ <b>Khung giờ:</b> {safe(shift["time"])}

<b>👤 Nhân viên:</b>
- Tên: {safe(sender_name)}
- Username: {safe(sender_username)}

<b>💻 ULTRA:</b>

Your ID: {safe(ultra_id)}
Password: {safe(ultra_password)}

<b>⏰ Thời gian gửi:</b> {safe(now)}

<b>👨‍💼 Quản lý:</b>
{safe(managers)}"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": MANAGER_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "Telegram gửi thất bại."))


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/submit")
def submit():
    data = request.get_json(silent=True) or {}

    user, error = validate_telegram_init_data(str(data.get("initData", "")))
    if error:
        return jsonify(ok=False, message=error), 401

    telegram_id = str(user["id"])
    if not ALLOWED_TELEGRAM_IDS:
        return jsonify(
            ok=False,
            message="Hệ thống chưa cấu hình danh sách nhân viên được phép dùng."
        ), 503

    if telegram_id not in ALLOWED_TELEGRAM_IDS:
        return jsonify(
            ok=False,
            message="Tài khoản Telegram này chưa được cấp quyền."
        ), 403

    action_code = str(data.get("action", "")).strip()
    department = str(data.get("department", "")).strip().upper()
    shift_code = str(data.get("shift", "")).strip()
    ultra_id = str(data.get("ultra_id", "")).strip()
    ultra_password = str(data.get("ultra_password", "")).strip()

    if action_code not in VALID_ACTIONS:
        return jsonify(ok=False, message="Vui lòng chọn VÀO CA hoặc RA CA."), 400
    if department not in VALID_DEPARTMENTS:
        return jsonify(ok=False, message="Vui lòng chọn bộ phận."), 400
    if shift_code not in SHIFTS:
        return jsonify(ok=False, message="Vui lòng chọn ca làm việc."), 400
    if not ultra_id:
        return jsonify(ok=False, message="Vui lòng nhập Your ID."), 400
    if not ultra_password:
        return jsonify(ok=False, message="Vui lòng nhập Password."), 400
    if len(ultra_id) > 100 or len(ultra_password) > 200:
        return jsonify(ok=False, message="Thông tin ULTRA quá dài."), 400

    # Không lưu ID/Password vào database hoặc log.
    now_ts = time.time()
    last_ts = _recent_submit.get(telegram_id, 0)
    if now_ts - last_ts < 4:
        return jsonify(ok=False, message="Bạn vừa gửi rồi. Vui lòng chờ vài giây."), 429

    _recent_submit[telegram_id] = now_ts

    try:
        send_report(
            user,
            action_code,
            department,
            shift_code,
            ultra_id,
            ultra_password,
        )
    except Exception:
        app.logger.exception("Không gửi được Telegram")
        return jsonify(
            ok=False,
            message="Không gửi được đến nhóm quản lý. Vui lòng thử lại."
        ), 502

    action, _ = VALID_ACTIONS[action_code]
    shift = SHIFTS[shift_code]
    return jsonify(
        ok=True,
        message="ĐIỂM DANH THÀNH CÔNG",
        action=action,
        department=department,
        shift_name=shift["name"],
        shift_time=shift["time"],
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
