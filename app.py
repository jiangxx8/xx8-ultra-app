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

from flask import (
    Flask,
    jsonify,
    render_template,
    request
)


app = Flask(__name__)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
).strip()


MANAGER_CHAT_ID = os.getenv(
    "MANAGER_CHAT_ID",
    ""
).strip()


ALLOWED_TELEGRAM_IDS = {

    x.strip()

    for x in os.getenv(
        "ALLOWED_TELEGRAM_IDS",
        ""
    ).split(",")

    if x.strip()

}


APP_TIMEZONE = os.getenv(
    "APP_TIMEZONE",
    "Asia/Tbilisi"
).strip()


# =========================================================
# QUẢN LÝ THEO BỘ PHẬN
# =========================================================

MANAGERS = {

    "XNK":
        "@jiangabcvip "
        "@asongbakjang "
        "@cucdangneee "
        "@baothanhthien1302 "
        "@laurenxx8",

    "FK":
        "@golayxx8 "
        "@Anhtaytay "
        "@kenvinxx8 "
        "@zata433 "
        "@MAKUNXX86764 "
        "@adidasxx8",

    "CSKH":
        "@lilyxx8123 "
        "@yuxi6676 "
        "@doraabcvip "
        "@hihinhungdangkhocccc "
        "@riverdayroi"
}


# =========================================================
# VÀO CA / RA CA
# =========================================================

ACTIONS = {

    "CHECK_IN": {
        "name": "VÀO CA",
        "icon": "🟢"
    },

    "CHECK_OUT": {
        "name": "RA CA",
        "icon": "🔴"
    }

}


# =========================================================
# CA LÀM VIỆC
# =========================================================

SHIFTS = {

    # =====================
    # XNK
    # =====================

    "XNK_08_18": {
        "department": "XNK",
        "name": "☀️ CA SÁNG",
        "time": "08:00 - 18:00"
    },

    "XNK_13_23": {
        "department": "XNK",
        "name": "🌤️ CA TRUNG",
        "time": "13:00 - 23:00"
    },

    "XNK_22_08": {
        "department": "XNK",
        "name": "🌙 CA ĐÊM",
        "time": "22:00 - 08:00"
    },


    # =====================
    # FK
    # =====================

    "FK_08_18": {
        "department": "FK",
        "name": "☀️ CA SÁNG",
        "time": "08:00 - 18:00"
    },

    "FK_12_22": {
        "department": "FK",
        "name": "🌤️ CA TRUNG",
        "time": "12:00 - 22:00"
    },

    "FK_22_08": {
        "department": "FK",
        "name": "🌙 CA ĐÊM",
        "time": "22:00 - 08:00"
    },


    # =====================
    # CSKH
    # =====================

    "CSKH_11_21": {
        "department": "CSKH",
        "name": "🔵 CA 1",
        "time": "11:00 - 21:00"
    },

    "CSKH_08_18": {
        "department": "CSKH",
        "name": "☀️ CA SÁNG",
        "time": "08:00 - 18:00"
    },

    "CSKH_16_02": {
        "department": "CSKH",
        "name": "🌆 CA TRUNG",
        "time": "16:00 - 02:00"
    },

    "CSKH_22_08": {
        "department": "CSKH",
        "name": "🌙 CA ĐÊM",
        "time": "22:00 - 08:00"
    }

}


# chống bấm liên tục
recent_submit = {}


# =========================================================
# XÁC MINH TELEGRAM MINI APP
# =========================================================

def validate_telegram_init_data(
    init_data,
    max_age_seconds=3600
):

    if not BOT_TOKEN:

        return None, (
            "Server chưa cấu hình BOT_TOKEN."
        )


    if not init_data:

        return None, (
            "Không nhận được dữ liệu Telegram."
        )


    pairs = dict(
        parse_qsl(
            init_data,
            keep_blank_values=True
        )
    )


    received_hash = pairs.pop(
        "hash",
        None
    )


    if not received_hash:

        return None, (
            "Không có chữ ký Telegram."
        )


    data_check_string = "\n".join(

        f"{key}={value}"

        for key, value
        in sorted(
            pairs.items()
        )

    )


    secret_key = hmac.new(

        b"WebAppData",

        BOT_TOKEN.encode(
            "utf-8"
        ),

        hashlib.sha256

    ).digest()


    calculated_hash = hmac.new(

        secret_key,

        data_check_string.encode(
            "utf-8"
        ),

        hashlib.sha256

    ).hexdigest()


    if not hmac.compare_digest(
        calculated_hash,
        received_hash
    ):

        return None, (
            "Dữ liệu Telegram không hợp lệ."
        )


    try:

        auth_date = int(
            pairs.get(
                "auth_date",
                "0"
            )
        )

    except ValueError:

        return None, (
            "auth_date không hợp lệ."
        )


    if not auth_date:

        return None, (
            "Không tìm thấy auth_date."
        )


    if abs(
        time.time()
        -
        auth_date
    ) > max_age_seconds:

        return None, (
            "Phiên Telegram đã hết hạn. "
            "Hãy đóng và mở lại ứng dụng."
        )


    try:

        user = json.loads(
            pairs.get(
                "user",
                "{}"
            )
        )

    except json.JSONDecodeError:

        return None, (
            "Không đọc được tài khoản Telegram."
        )


    if not user.get("id"):

        return None, (
            "Không tìm thấy Telegram ID."
        )


    return user, None


# =========================================================
# ESCAPE HTML
# =========================================================

def safe(value):

    return html.escape(
        str(value),
        quote=False
    )


# =========================================================
# GỬI TELEGRAM
# =========================================================

def send_telegram_report(
    user,
    action_code,
    department,
    shift_code,
    ultra_id,
    ultra_password
):

    action = ACTIONS[
        action_code
    ]


    shift = SHIFTS[
        shift_code
    ]


    first_name = user.get(
        "first_name",
        ""
    )


    last_name = user.get(
        "last_name",
        ""
    )


    full_name = (
        first_name
        +
        " "
        +
        last_name
    ).strip()


    if not full_name:

        full_name = (
            "Không có tên"
        )


    username = user.get(
        "username"
    )


    if username:

        username_text = (
            "@"
            +
            username
        )

    else:

        username_text = (
            "None"
        )


    managers = MANAGERS.get(
        department,
        ""
    )


    try:

        timezone = ZoneInfo(
            APP_TIMEZONE
        )

    except Exception:

        timezone = ZoneInfo(
            "UTC"
        )


    now = datetime.now(
        timezone
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    message = f"""
<b>📢 ĐIỂM DANH BỘ PHẬN ONLINE XX8</b>

{action["icon"]} <b>Trạng thái: {safe(action["name"])}</b>

🏢 <b>Bộ phận:</b> {safe(department)}

🕐 <b>Ca làm việc:</b> {safe(shift["name"])}
⏰ <b>Khung giờ:</b> {safe(shift["time"])}

<b>👤 Nhân viên:</b>
- Tên: {safe(full_name)}
- Username: {safe(username_text)}

<b>💻 ULTRA:</b>

Your ID: {safe(ultra_id)}
Password: {safe(ultra_password)}

<b>⏰ Thời gian gửi:</b> {safe(now)}

<b>👨‍💼 Quản lý:</b>
{safe(managers)}
""".strip()


    telegram_url = (

        "https://api.telegram.org/bot"
        +
        BOT_TOKEN
        +
        "/sendMessage"

    )


    response = requests.post(

        telegram_url,

        json={

            "chat_id":
                MANAGER_CHAT_ID,

            "text":
                message,

            "parse_mode":
                "HTML",

            "disable_web_page_preview":
                True

        },

        timeout=12

    )


    response.raise_for_status()


    result = response.json()


    if not result.get(
        "ok"
    ):

        raise RuntimeError(
            result.get(
                "description",
                "Telegram gửi thất bại."
            )
        )


# =========================================================
# WEBSITE
# =========================================================

@app.get("/")
def index():

    return render_template(
        "index.html"
    )


@app.get("/health")
def health():

    return {
        "ok": True
    }


# =========================================================
# API SUBMIT
# =========================================================

@app.post("/submit")
def submit():

    data = (
        request.get_json(
            silent=True
        )
        or
        {}
    )


    # =====================
    # TELEGRAM AUTH
    # =====================

    user, error = (
        validate_telegram_init_data(

            str(
                data.get(
                    "initData",
                    ""
                )
            )

        )
    )


    if error:

        return jsonify(

            ok=False,
            message=error

        ), 401


    telegram_id = str(
        user["id"]
    )


    # =====================
    # CHECK QUYỀN
    # =====================

    if not ALLOWED_TELEGRAM_IDS:

        return jsonify(

            ok=False,

            message=(
                "Hệ thống chưa cấu hình "
                "danh sách nhân viên."
            )

        ), 503


    if telegram_id not in (
        ALLOWED_TELEGRAM_IDS
    ):

        return jsonify(

            ok=False,

            message=(
                "Tài khoản Telegram này "
                "chưa được cấp quyền."
            )

        ), 403


    # =====================
    # LẤY DATA
    # =====================

    action_code = str(
        data.get(
            "action",
            ""
        )
    ).strip()


    department = str(
        data.get(
            "department",
            ""
        )
    ).strip().upper()


    shift_code = str(
        data.get(
            "shift",
            ""
        )
    ).strip()


    ultra_id = str(
        data.get(
            "ultra_id",
            ""
        )
    ).strip()


    ultra_password = str(
        data.get(
            "ultra_password",
            ""
        )
    ).strip()


    # =====================
    # CHECK ACTION
    # =====================

    if action_code not in ACTIONS:

        return jsonify(

            ok=False,

            message=(
                "Vui lòng chọn "
                "VÀO CA hoặc RA CA."
            )

        ), 400


    # =====================
    # CHECK DEPARTMENT
    # =====================

    if department not in MANAGERS:

        return jsonify(

            ok=False,
            message="Bộ phận không hợp lệ."

        ), 400


    # =====================
    # CHECK SHIFT
    # =====================

    if shift_code not in SHIFTS:

        return jsonify(

            ok=False,
            message="Ca làm việc không hợp lệ."

        ), 400


    shift = SHIFTS[
        shift_code
    ]


    if (
        shift["department"]
        !=
        department
    ):

        return jsonify(

            ok=False,

            message=(
                "Ca làm việc không thuộc "
                "bộ phận đã chọn."
            )

        ), 400


    # =====================
    # CHECK ULTRA
    # =====================

    if not ultra_id:

        return jsonify(

            ok=False,

            message=(
                "Không tìm thấy Your ID."
            )

        ), 400


    if not ultra_password:

        return jsonify(

            ok=False,

            message=(
                "Không tìm thấy Password."
            )

        ), 400


    if len(ultra_id) > 100:

        return jsonify(

            ok=False,
            message="Your ID quá dài."

        ), 400


    if len(ultra_password) > 200:

        return jsonify(

            ok=False,
            message="Password quá dài."

        ), 400


    # =====================
    # CHỐNG CLICK LIÊN TỤC
    # =====================

    current_time = (
        time.time()
    )


    previous_time = (
        recent_submit.get(
            telegram_id,
            0
        )
    )


    if (
        current_time
        -
        previous_time
        <
        4
    ):

        return jsonify(

            ok=False,

            message=(
                "Bạn vừa gửi rồi. "
                "Vui lòng chờ vài giây."
            )

        ), 429


    recent_submit[
        telegram_id
    ] = current_time


    # =====================
    # SEND TELEGRAM
    # =====================

    try:

        send_telegram_report(

            user=user,

            action_code=
                action_code,

            department=
                department,

            shift_code=
                shift_code,

            ultra_id=
                ultra_id,

            ultra_password=
                ultra_password

        )


    except Exception:

        app.logger.exception(
            "Không gửi được Telegram"
        )


        return jsonify(

            ok=False,

            message=(
                "Không gửi được đến "
                "nhóm quản lý."
            )

        ), 502


    # =====================
    # SUCCESS
    # =====================

    return jsonify(

        ok=True,

        message=(
            "ĐIỂM DANH THÀNH CÔNG"
        ),

        action=
            ACTIONS[
                action_code
            ]["name"],

        department=
            department,

        shift=
            shift["time"]

    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "8080"
        )
    )


    app.run(

        host="0.0.0.0",

        port=port

    )
