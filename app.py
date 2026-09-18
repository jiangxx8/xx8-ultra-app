import os
import json
import hmac
import hashlib
import time
from urllib.parse import parse_qsl

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

def validate_telegram_init_data(init_data: str, max_age_seconds: int = 3600):
    if not BOT_TOKEN or not init_data:
        return None, "Thiếu cấu hình BOT_TOKEN hoặc Telegram initData."

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None, "Không có chữ ký Telegram."

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(pairs.items())
    )

    # Telegram: secret_key = HMAC_SHA256(key="WebAppData", data=bot_token)
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
        return None, "Phiên Telegram đã hết hạn. Hãy mở lại ứng dụng."

    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        return None, "Không đọc được tài khoản Telegram."

    if not user.get("id"):
        return None, "Không tìm thấy Telegram ID."

    return user, None


def send_to_manager(user: dict, ultra_id: str):
    if not BOT_TOKEN or not MANAGER_CHAT_ID:
        raise RuntimeError("Chưa cấu hình BOT_TOKEN hoặc MANAGER_CHAT_ID.")

    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    full_name = (first_name + " " + last_name).strip() or "Không có tên"
    username = user.get("username")
    telegram_id = str(user.get("id"))

    username_line = f"\n🔗 Username: @{username}" if username else ""

    message = (
        "✅ <b>NHÂN VIÊN GỬI ULTRA</b>\n\n"
        f"👤 Nhân viên: <b>{html_escape(full_name)}</b>"
        f"{username_line}\n"
        f"🆔 Telegram ID: <code>{html_escape(telegram_id)}</code>\n"
        f"💻 ULTRA ID: <code>{html_escape(ultra_id)}</code>"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": MANAGER_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "Telegram gửi thất bại."))


def html_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/submit")
def submit_ultra():
    data = request.get_json(silent=True) or {}
    init_data = str(data.get("initData", ""))
    ultra_id = str(data.get("ultra_id", "")).strip()

    if not ultra_id:
        return jsonify(ok=False, message="Vui lòng nhập ULTRA ID."), 400

    if len(ultra_id) > 100:
        return jsonify(ok=False, message="ULTRA ID quá dài."), 400

    user, error = validate_telegram_init_data(init_data)
    if error:
        return jsonify(ok=False, message=error), 401

    telegram_id = str(user["id"])

    # Bắt buộc cấu hình danh sách nhân viên được phép dùng.
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

    try:
        send_to_manager(user, ultra_id)
    except Exception:
        app.logger.exception("Không gửi được Telegram")
        return jsonify(
            ok=False,
            message="Không gửi được đến nhóm quản lý. Vui lòng báo quản lý."
        ), 502

    return jsonify(ok=True, message="Đã gửi ULTRA đến nhóm quản lý.")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
