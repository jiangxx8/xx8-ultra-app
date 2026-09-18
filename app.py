import os
import json
import hmac
import hashlib
import html
import sqlite3
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo

import requests
from flask import (
    Flask, flash, jsonify, redirect, render_template,
    request, session, url_for
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("USERS_DB_PATH", str(BASE_DIR / "users.db")))

app = Flask(__name__)
app.secret_key = os.getenv("WEB_SECRET_KEY", "CHANGE-ME-PLEASE")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID", "").strip()
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Tbilisi").strip() or "Asia/Tbilisi"
ADMIN_USERNAME = os.getenv("WEB_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD", "admin123")

ID_TYPES = ["ID Telegram công việc", "ID Telegram cá nhân"]
DEPARTMENTS = ["CSKH", "FK", "XNK", "Chưa phân loại"]
VALID_DEPARTMENTS = {"CSKH", "FK", "XNK"}

MANAGERS = {
    "XNK": "@jiangabcvip @asongbakjang @cucdangneee @baothanhthien1302 @laurenxx8",
    "FK": "@golayxx8 @Anhtaytay @kenvinxx8 @zata433 @MAKUNXX86764 @adidasxx8",
    "CSKH": "@lilyxx8123 @yuxi6676 @doraabcvip @hihinhungdangkhocccc @riverdayroi",
}

SHIFTS = {
    "XNK_08_18": ("☀️ CA SÁNG", "08:00 - 18:00", "XNK"),
    "XNK_13_23": ("🌤️ CA TRUNG", "13:00 - 23:00", "XNK"),
    "XNK_22_08": ("🌙 CA ĐÊM", "22:00 - 08:00", "XNK"),
    "FK_08_18": ("☀️ CA SÁNG", "08:00 - 18:00", "FK"),
    "FK_12_22": ("🌤️ CA TRUNG", "12:00 - 22:00", "FK"),
    "FK_22_08": ("🌙 CA ĐÊM", "22:00 - 08:00", "FK"),
    "CSKH_11_21": ("🔵 CA 1", "11:00 - 21:00", "CSKH"),
    "CSKH_08_18": ("☀️ CA SÁNG", "08:00 - 18:00", "CSKH"),
    "CSKH_16_02": ("🌆 CA TRUNG", "16:00 - 02:00", "CSKH"),
    "CSKH_22_08": ("🌙 CA ĐÊM", "22:00 - 08:00", "CSKH"),
}

ACTIONS = {
    "CHECK_IN": ("VÀO CA", "🟢"),
    "CHECK_OUT": ("RA CA", "🔴"),
}

recent_submit = {}


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                telegram_id INTEGER NOT NULL,
                id_type TEXT NOT NULL,
                department TEXT NOT NULL DEFAULT 'Chưa phân loại',
                enabled INTEGER NOT NULL DEFAULT 1,
                note TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (telegram_id, id_type)
            )
        """)
        conn.commit()


def get_employee(telegram_id):
    """Return (employee dict, error message)."""
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT id, name, telegram_id, id_type, department, enabled, note
                FROM users
                WHERE telegram_id = ? AND enabled = 1
                ORDER BY id ASC
            """, (int(telegram_id),)).fetchall()
    except Exception:
        return None, "Không đọc được danh sách nhân viên."

    if not rows:
        return None, "Telegram ID này chưa được cấp quyền hoặc đã bị tắt."

    departments = {r["department"] for r in rows if r["department"] in VALID_DEPARTMENTS}
    if len(departments) == 0:
        return None, "Telegram ID này chưa được phân bộ phận."
    if len(departments) > 1:
        return None, "Telegram ID đang bị gán nhiều bộ phận. Hãy báo quản lý."

    department = next(iter(departments))
    # Prefer a row in the resolved department.
    row = next((r for r in rows if r["department"] == department), rows[0])
    return {
        "name": row["name"],
        "telegram_id": row["telegram_id"],
        "department": department,
        "id_type": row["id_type"],
    }, None


def validate_telegram_init_data(init_data, max_age_seconds=3600):
    if not BOT_TOKEN or not init_data:
        return None, "Thiếu BOT_TOKEN hoặc dữ liệu Telegram."

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None, "Không có chữ ký Telegram."

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
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


def esc(value):
    return html.escape(str(value), quote=False)


def send_to_manager(user, employee, action_code, shift_code, ultra_id, ultra_password):
    action_name, action_icon = ACTIONS[action_code]
    shift_name, shift_time, department = SHIFTS[shift_code]

    username = f"@{user['username']}" if user.get("username") else "None"
    display_name = employee.get("name") or "Không có tên"
    try:
        tz = ZoneInfo(APP_TIMEZONE)
    except Exception:
        tz = ZoneInfo("UTC")
    sent_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    message = f"""<b>📢 ĐIỂM DANH BỘ PHẬN ONLINE XX8</b>

{action_icon} <b>Trạng thái: {esc(action_name)}</b>

🏢 <b>Bộ phận:</b> {esc(department)}

🕐 <b>Ca làm việc:</b> {esc(shift_name)}
⏰ <b>Khung giờ:</b> {esc(shift_time)}

<b>👤 Nhân viên:</b>
- Tên: {esc(display_name)}
- Username: {esc(username)}
- Telegram ID: <code>{esc(user['id'])}</code>

<b>💻 ULTRA:</b>
Your ID: {esc(ultra_id)}
Password: {esc(ultra_password)}

<b>⏰ Thời gian gửi:</b> {esc(sent_time)}

<b>👨‍💼 Quản lý:</b>
{esc(MANAGERS.get(department, ''))}"""

    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": MANAGER_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=12,
    )
    r.raise_for_status()
    payload = r.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "Telegram gửi thất bại."))


# ---------------- Mini App ----------------
@app.get("/")
def miniapp():
    return render_template("miniapp.html")


@app.get("/health")
def health():
    return {"ok": True, "db": DB_PATH.exists()}


@app.post("/api/profile")
def api_profile():
    data = request.get_json(silent=True) or {}
    user, error = validate_telegram_init_data(str(data.get("initData", "")))
    if error:
        return jsonify(ok=False, message=error), 401
    employee, error = get_employee(user["id"])
    if error:
        return jsonify(ok=False, message=error), 403
    return jsonify(
        ok=True,
        employee_name=employee["name"],
        department=employee["department"],
        telegram_id=user["id"],
        username=user.get("username"),
    )


@app.post("/submit")
def submit():
    data = request.get_json(silent=True) or {}
    user, error = validate_telegram_init_data(str(data.get("initData", "")))
    if error:
        return jsonify(ok=False, message=error), 401

    employee, error = get_employee(user["id"])
    if error:
        return jsonify(ok=False, message=error), 403

    action_code = str(data.get("action", "")).strip()
    shift_code = str(data.get("shift", "")).strip()
    ultra_id = str(data.get("ultra_id", "")).strip()
    ultra_password = str(data.get("ultra_password", "")).strip()

    if action_code not in ACTIONS:
        return jsonify(ok=False, message="Vui lòng chọn VÀO CA hoặc RA CA."), 400
    if shift_code not in SHIFTS:
        return jsonify(ok=False, message="Ca làm việc không hợp lệ."), 400
    if SHIFTS[shift_code][2] != employee["department"]:
        return jsonify(ok=False, message="Ca không thuộc bộ phận của bạn."), 400
    if not ultra_id or not ultra_password:
        return jsonify(ok=False, message="Thiếu Your ID hoặc Password."), 400
    if len(ultra_id) > 100 or len(ultra_password) > 200:
        return jsonify(ok=False, message="Thông tin ULTRA quá dài."), 400

    now = time.time()
    if now - recent_submit.get(str(user["id"]), 0) < 4:
        return jsonify(ok=False, message="Bạn vừa gửi rồi. Vui lòng chờ vài giây."), 429
    recent_submit[str(user["id"])] = now

    try:
        send_to_manager(user, employee, action_code, shift_code, ultra_id, ultra_password)
    except Exception:
        app.logger.exception("Không gửi được Telegram")
        return jsonify(ok=False, message="Không gửi được đến nhóm quản lý."), 502

    return jsonify(ok=True, message="ĐIỂM DANH THÀNH CÔNG")


# ---------------- Admin ----------------
def admin_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_index"))
        flash("Sai tài khoản hoặc mật khẩu.", "error")
    return render_template("admin_login.html")


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@admin_login_required
def admin_index():
    q = request.args.get("q", "").strip()
    department = request.args.get("department", "").strip()
    id_type = request.args.get("id_type", "").strip()
    status = request.args.get("status", "").strip()

    sql = "SELECT * FROM users WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR CAST(telegram_id AS TEXT) LIKE ? OR note LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])
    if department in DEPARTMENTS:
        sql += " AND department = ?"
        params.append(department)
    if id_type in ID_TYPES:
        sql += " AND id_type = ?"
        params.append(id_type)
    if status in {"0", "1"}:
        sql += " AND enabled = ?"
        params.append(int(status))
    sql += " ORDER BY CASE department WHEN 'CSKH' THEN 1 WHEN 'FK' THEN 2 WHEN 'XNK' THEN 3 ELSE 4 END, name, id_type"

    with get_db() as conn:
        users = conn.execute(sql, params).fetchall()
        stats = {
            "total": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "enabled": conn.execute("SELECT COUNT(*) FROM users WHERE enabled=1").fetchone()[0],
            "cskh": conn.execute("SELECT COUNT(*) FROM users WHERE department='CSKH'").fetchone()[0],
            "fk": conn.execute("SELECT COUNT(*) FROM users WHERE department='FK'").fetchone()[0],
            "xnk": conn.execute("SELECT COUNT(*) FROM users WHERE department='XNK'").fetchone()[0],
            "unclassified": conn.execute("SELECT COUNT(*) FROM users WHERE department='Chưa phân loại'").fetchone()[0],
        }

    return render_template(
        "admin_index.html", users=users, stats=stats, q=q,
        department=department, id_type=id_type, status=status,
        departments=DEPARTMENTS, id_types=ID_TYPES,
    )


def validate_admin_form():
    name = request.form.get("name", "").strip()
    tid = request.form.get("telegram_id", "").strip()
    id_type = request.form.get("id_type", "").strip()
    department = request.form.get("department", "").strip()
    note = request.form.get("note", "").strip()
    enabled = 1 if request.form.get("enabled") == "1" else 0
    if not name:
        return None, "Vui lòng nhập tên."
    if not tid.lstrip("-").isdigit():
        return None, "Telegram ID phải là số."
    if id_type not in ID_TYPES:
        return None, "Loại ID không hợp lệ."
    if department not in DEPARTMENTS:
        return None, "Bộ phận không hợp lệ."
    return {
        "name": name, "telegram_id": int(tid), "id_type": id_type,
        "department": department, "enabled": enabled, "note": note,
    }, None


def sync_department(conn, telegram_id, department):
    conn.execute("UPDATE users SET department=? WHERE telegram_id=?", (department, telegram_id))


@app.route("/admin/add", methods=["GET", "POST"])
@admin_login_required
def admin_add():
    if request.method == "POST":
        data, error = validate_admin_form()
        if error:
            flash(error, "error")
        else:
            try:
                with get_db() as conn:
                    existing = conn.execute("SELECT DISTINCT department FROM users WHERE telegram_id=?", (data["telegram_id"],)).fetchall()
                    real = {r[0] for r in existing if r[0] in VALID_DEPARTMENTS}
                    if real and data["department"] not in real:
                        flash(f"Telegram ID này đang thuộc {', '.join(sorted(real))}.", "error")
                        return render_template("admin_form.html", mode="add", user=request.form, departments=DEPARTMENTS, id_types=ID_TYPES)
                    conn.execute("""
                        INSERT INTO users(name,telegram_id,id_type,department,enabled,note)
                        VALUES(?,?,?,?,?,?)
                    """, (data["name"], data["telegram_id"], data["id_type"], data["department"], data["enabled"], data["note"]))
                    if data["department"] in VALID_DEPARTMENTS:
                        sync_department(conn, data["telegram_id"], data["department"])
                    conn.commit()
                flash("Đã thêm Telegram ID. Mini App dùng được ngay.", "success")
                return redirect(url_for("admin_index"))
            except sqlite3.IntegrityError:
                flash("Telegram ID + loại ID này đã tồn tại.", "error")
    return render_template("admin_form.html", mode="add", user=(request.form if request.method == "POST" else None), departments=DEPARTMENTS, id_types=ID_TYPES)


@app.route("/admin/edit/<int:user_id>", methods=["GET", "POST"])
@admin_login_required
def admin_edit(user_id):
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        flash("Không tìm thấy ID.", "error")
        return redirect(url_for("admin_index"))

    if request.method == "POST":
        data, error = validate_admin_form()
        if error:
            flash(error, "error")
        else:
            try:
                with get_db() as conn:
                    conn.execute("""
                        UPDATE users SET name=?,telegram_id=?,id_type=?,department=?,enabled=?,note=? WHERE id=?
                    """, (data["name"], data["telegram_id"], data["id_type"], data["department"], data["enabled"], data["note"], user_id))
                    if data["department"] in VALID_DEPARTMENTS:
                        sync_department(conn, data["telegram_id"], data["department"])
                    conn.commit()
                flash("Đã lưu thay đổi.", "success")
                return redirect(url_for("admin_index"))
            except sqlite3.IntegrityError:
                flash("Telegram ID + loại ID này đã tồn tại.", "error")
        user = request.form
    return render_template("admin_form.html", mode="edit", user=user, departments=DEPARTMENTS, id_types=ID_TYPES)


@app.post("/admin/toggle/<int:user_id>")
@admin_login_required
def admin_toggle(user_id):
    with get_db() as conn:
        conn.execute("UPDATE users SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id=?", (user_id,))
        conn.commit()
    return redirect(request.referrer or url_for("admin_index"))


@app.post("/admin/delete/<int:user_id>")
@admin_login_required
def admin_delete(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
    flash("Đã xóa ID.", "success")
    return redirect(url_for("admin_index"))


@app.post("/admin/bulk")
@admin_login_required
def admin_bulk():
    ids = [int(x) for x in request.form.getlist("ids") if x.isdigit()]
    if not ids:
        flash("Chưa chọn dòng nào.", "error")
        return redirect(request.referrer or url_for("admin_index"))

    action = request.form.get("bulk_action", "")
    placeholders = ",".join("?" for _ in ids)
    with get_db() as conn:
        if action == "enable":
            conn.execute(f"UPDATE users SET enabled=1 WHERE id IN ({placeholders})", ids)
        elif action == "disable":
            conn.execute(f"UPDATE users SET enabled=0 WHERE id IN ({placeholders})", ids)
        elif action == "delete":
            conn.execute(f"DELETE FROM users WHERE id IN ({placeholders})", ids)
        elif action.startswith("department:"):
            dept = action.split(":",1)[1]
            if dept in DEPARTMENTS:
                conn.execute(f"UPDATE users SET department=? WHERE id IN ({placeholders})", [dept] + ids)
        conn.commit()
    flash("Đã cập nhật các dòng đã chọn.", "success")
    return redirect(request.referrer or url_for("admin_index"))


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
