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
    item.strip()
    for item in os.getenv(
        "ALLOWED_TELEGRAM_IDS",
        ""
    ).split(",")
    if item.strip()
}

APP_TIMEZONE = (
    os.getenv(
        "APP_TIMEZONE",
        "Asia/Tbilisi"
    ).strip()
    or
    "Asia/Tbilisi"
)


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


SHIFTS = {

    "XNK_08_18":
    (
        "☀️ CA SÁNG",
        "08:00 - 18:00",
        "XNK"
    ),

    "XNK_13_23":
    (
        "🌤️ CA TRUNG",
        "13:00 - 23:00",
        "XNK"
    ),

    "XNK_22_08":
    (
        "🌙 CA ĐÊM",
        "22:00 - 08:00",
        "XNK"
    ),


    "FK_08_18":
    (
        "☀️ CA SÁNG",
        "08:00 - 18:00",
        "FK"
    ),

    "FK_12_22":
    (
        "🌤️ CA TRUNG",
        "12:00 - 22:00",
        "FK"
    ),

    "FK_22_08":
    (
        "🌙 CA ĐÊM",
        "22:00 - 08:00",
        "FK"
    ),


    "CSKH_11_21":
    (
        "🔵 CA 1",
        "11:00 - 21:00",
        "CSKH"
    ),

    "CSKH_08_18":
    (
        "☀️ CA SÁNG",
        "08:00 - 18:00",
        "CSKH"
    ),

    "CSKH_16_02":
    (
        "🌆 CA TRUNG",
        "16:00 - 02:00",
        "CSKH"
    ),

    "CSKH_22_08":
    (
        "🌙 CA ĐÊM",
        "22:00 - 08:00",
        "CSKH"
    )

}


ACTIONS = {

    "CHECK_IN":
    (
        "VÀO CA",
        "🟢"
    ),

    "CHECK_OUT":
    (
        "RA CA",
        "🔴"
    )

}


recent_submit = {}


def validate_telegram_init_data(
    init_data,
    max_age_seconds=3600
):

    if (
        not BOT_TOKEN
        or
        not init_data
    ):

        return (
            None,
            "Thiếu BOT_TOKEN hoặc dữ liệu Telegram."
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

        return (
            None,
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

        return (
            None,
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

        return (
            None,
            "auth_date không hợp lệ."
        )


    if (
        not auth_date
        or
        abs(
            time.time()
            -
            auth_date
        )
        >
        max_age_seconds
    ):

        return (
            None,
            "Phiên Telegram đã hết hạn. Hãy đóng và mở lại ứng dụng."
        )


    try:

        user = json.loads(
            pairs.get(
                "user",
                "{}"
            )
        )

    except json.JSONDecodeError:

        return (
            None,
            "Không đọc được tài khoản Telegram."
        )


    if not user.get("id"):

        return (
            None,
            "Không tìm thấy Telegram ID."
        )


    return (
        user,
        None
    )


def esc(value):

    return html.escape(
        str(value),
        quote=False
    )


def send_to_manager(
    user,
    action_code,
    department,
    shift_code,
    ultra_id,
    ultra_password
):

    action_name, action_icon = (
        ACTIONS[
            action_code
        ]
    )


    shift_name, shift_time, shift_department = (
        SHIFTS[
            shift_code
        ]
    )


    first_name = user.get(
        "first_name",
        ""
    )

    last_name = user.get(
        "last_name",
        ""
    )


    employee_name = (
        first_name
        +
        " "
        +
        last_name
    ).strip()


    if not employee_name:

        employee_name = (
            "Không có tên"
        )


    if user.get(
        "username"
    ):

        username = (
            "@"
            +
            user["username"]
        )

    else:

        username = (
            "None"
        )


    try:

        timezone = ZoneInfo(
            APP_TIMEZONE
        )

    except Exception:

        timezone = ZoneInfo(
            "UTC"
        )


    sent_time = datetime.now(
        timezone
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    manager_list = MANAGERS.get(
        department,
        ""
    )


    message = f"""<b>📢 ĐIỂM DANH BỘ PHẬN ONLINE XX8</b>

{action_icon} <b>Trạng thái: {esc(action_name)}</b>

🏢 <b>Bộ phận:</b> {esc(department)}

🕐 <b>Ca làm việc:</b> {esc(shift_name)}
⏰ <b>Khung giờ:</b> {esc(shift_time)}

<b>👤 Nhân viên:</b>
- Tên: {esc(employee_name)}
- Username: {esc(username)}

<b>💻 ULTRA:</b>

Your ID: {esc(ultra_id)}
Password: {esc(ultra_password)}

<b>⏰ Thời gian gửi:</b> {esc(sent_time)}

<b>👨‍💼 Quản lý:</b>
{esc(manager_list)}"""


    response = requests.post(

        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",

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


    payload = response.json()


    if not payload.get(
        "ok"
    ):

        raise RuntimeError(
            payload.get(
                "description",
                "Telegram gửi thất bại."
            )
        )


@app.get("/")
def home():

    return render_template(
        "index.html"
    )


@app.get("/health")
def health():

    return {
        "ok": True
    }


@app.post("/submit")
def submit():

    data = (
        request.get_json(
            silent=True
        )
        or
        {}
    )


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

        return (
            jsonify(
                ok=False,
                message=error
            ),
            401
        )


    telegram_id = str(
        user["id"]
    )


    if not ALLOWED_TELEGRAM_IDS:

        return (
            jsonify(
                ok=False,
                message="Hệ thống chưa cấu hình danh sách nhân viên."
            ),
            503
        )


    if (
        telegram_id
        not in
        ALLOWED_TELEGRAM_IDS
    ):

        return (
            jsonify(
                ok=False,
                message="Tài khoản Telegram này chưa được cấp quyền."
            ),
            403
        )


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


    if (
        action_code
        not in
        ACTIONS
    ):

        return (
            jsonify(
                ok=False,
                message="Vui lòng chọn VÀO CA hoặc RA CA."
            ),
            400
        )


    if (
        department
        not in
        MANAGERS
    ):

        return (
            jsonify(
                ok=False,
                message="Bộ phận không hợp lệ."
            ),
            400
        )


    if (
        shift_code
        not in
        SHIFTS
    ):

        return (
            jsonify(
                ok=False,
                message="Ca làm việc không hợp lệ."
            ),
            400
        )


    shift_department = (
        SHIFTS[
            shift_code
        ][2]
    )


    if (
        shift_department
        !=
        department
    ):

        return (
            jsonify(
                ok=False,
                message="Ca này không thuộc bộ phận đã chọn."
            ),
            400
        )


    if (
        not ultra_id
        or
        not ultra_password
    ):

        return (
            jsonify(
                ok=False,
                message="Thiếu Your ID hoặc Password."
            ),
            400
        )


    if (
        len(ultra_id)
        >
        100
        or
        len(ultra_password)
        >
        200
    ):

        return (
            jsonify(
                ok=False,
                message="Thông tin ULTRA quá dài."
            ),
            400
        )


    now = time.time()


    previous = recent_submit.get(
        telegram_id,
        0
    )


    if (
        now
        -
        previous
        <
        4
    ):

        return (
            jsonify(
                ok=False,
                message="Bạn vừa gửi rồi. Vui lòng chờ vài giây."
            ),
            429
        )


    recent_submit[
        telegram_id
    ] = now


    try:

        send_to_manager(

            user,

            action_code,

            department,

            shift_code,

            ultra_id,

            ultra_password

        )

    except Exception:

        app.logger.exception(
            "Không gửi được Telegram"
        )


        return (
            jsonify(
                ok=False,
                message="Không gửi được đến nhóm quản lý. Vui lòng thử lại."
            ),
            502
        )


    return jsonify(

        ok=True,

        message=
            "ĐIỂM DANH THÀNH CÔNG"

    )


if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "8080"
        )
    )


    app.run(

        host=
            "0.0.0.0",

        port=
            port

    )
