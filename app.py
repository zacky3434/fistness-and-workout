import base64
import json
import os
import re
import secrets
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import requests as http_requests
except ImportError:
    http_requests = None

from db import get_connection, init_db

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "static" / "models"
PRODUCTS_IMG_DIR = BASE_DIR / "static" / "uploads" / "products"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
PRODUCTS_IMG_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("KINETIX_SECRET_KEY", "kinetix-3d-secret-key-2026")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

OAUTH_CFG = {
    "google": {"client_id": os.environ.get("GOOGLE_CLIENT_ID", "").strip(), "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()},
    "facebook": {"client_id": os.environ.get("FACEBOOK_CLIENT_ID", "").strip(), "client_secret": os.environ.get("FACEBOOK_CLIENT_SECRET", "").strip()},
    "apple": {"client_id": os.environ.get("APPLE_CLIENT_ID", "").strip(), "client_secret": os.environ.get("APPLE_CLIENT_SECRET", "").strip()},
}

init_db()
MUSCLE_GROUPS = ["chest", "back", "shoulders", "arms", "core", "legs"]
ALLOWED_IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")


def now_label():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def is_oauth_live(provider):
    cfg = OAUTH_CFG.get(provider, {})
    return bool(http_requests and cfg.get("client_id") and cfg.get("client_secret"))


def get_current_user_row():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    if not user:
        session.clear()
        return None
    return dict(user)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not get_current_user_row():
            if request.path.startswith("/api/"):
                return jsonify({"error": "Silakan login terlebih dahulu."}), 401
            return redirect(url_for("welcome_page"))
        return f(*args, **kwargs)
    return wrapper


def developer_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user_row()
        if not user:
            return jsonify({"error": "Silakan login terlebih dahulu."}), 401
        if user.get("role") != "developer":
            return jsonify({"error": "Akses khusus role Developer."}), 403
        return f(*args, **kwargs)
    return wrapper


def push_notification(conn, user_id, title, body, icon="bell", tone="toska"):
    conn.execute("""
        INSERT INTO notifications (user_id, title, body, icon, tone, is_read, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    """, (user_id, title, body, icon, tone, now_label()))


def notify_developers(conn, title, body, icon="bell", tone="ocean"):
    for dev in conn.execute("SELECT id FROM users WHERE role = 'developer'").fetchall():
        push_notification(conn, dev["id"], title, body, icon, tone)


def notify_all_users(conn, title, body, icon="sparkles", tone="toska"):
    for u in conn.execute("SELECT id FROM users WHERE role != 'developer'").fetchall():
        push_notification(conn, u["id"], title, body, icon, tone)


def compute_streak(workout_dates):
    if not workout_dates:
        return 0
    date_set = set(workout_dates)
    today = datetime.now().date()
    cursor = today if today.strftime("%Y-%m-%d") in date_set else today - timedelta(days=1)
    streak = 0
    while cursor.strftime("%Y-%m-%d") in date_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def find_or_create_social_user(provider, email, display_name):
    email = email.strip().lower()
    display_name = (display_name or f"{provider.capitalize()} Athlete").strip()
    conn = get_connection()
    cur = conn.cursor()
    existing = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        uid = existing["id"]
        conn.close()
        return uid

    base_user = re.sub(r"[^a-z0-9_]", "", email.split("@")[0].lower()) or f"{provider}_user"
    username = base_user
    suffix = 1
    while cur.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
        username = f"{base_user}_{suffix}"
        suffix += 1

    cur.execute("""
        INSERT INTO users (username, email, password_hash, role, onboarding_done, name, created_at)
        VALUES (?, ?, ?, 'user', 0, ?, ?)
    """, (username, email, generate_password_hash(secrets.token_hex(16)), display_name, now_label()))
    uid = cur.lastrowid
    cur.execute("INSERT OR IGNORE INTO daily_logs (user_id, date) VALUES (?, ?)", (uid, get_today_str()))
    cur.execute("INSERT OR IGNORE INTO weight_logs (user_id, date, weight_kg, note) VALUES (?, ?, 70.0, ?)", (uid, get_today_str(), f"Login {provider.capitalize()}"))
    push_notification(conn, uid, "Akun Berhasil Dibuat", f"Selamat datang {display_name}! Ikuti panduan interaktif untuk mengenal fitur.", "sparkles", "toska")
    notify_developers(conn, "User Baru Bergabung", f"{display_name} (@{username}) bergabung via {provider.capitalize()}.", "user-plus", "ocean")
    conn.commit()
    conn.close()
    return uid


# ===================== AUTH & WELCOME =====================

@app.route("/welcome")
def welcome_page():
    conn = get_connection()
    rows = conn.execute("SELECT name, username, goal FROM users ORDER BY id DESC LIMIT 6").fetchall()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return render_template("welcome.html", joined_users=[dict(r) for r in rows], total_users=total_users)


@app.route("/auth")
def auth_page():
    if request.args.get("relogin") == "1":
        session.clear()
        return render_template("auth.html")
    if get_current_user_row():
        return redirect(url_for("index"))
    return render_template("auth.html")


@app.route("/api/auth/providers", methods=["GET"])
def api_auth_providers():
    return jsonify({p: is_oauth_live(p) for p in ("google", "facebook", "apple")})


@app.route("/auth/oauth/<provider>")
def oauth_start(provider):
    provider = provider.lower()
    if provider not in ("google", "facebook", "apple") or not is_oauth_live(provider):
        return redirect(url_for("auth_page"))
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    cb = url_for("oauth_callback", provider=provider, _external=True)
    cid = OAUTH_CFG[provider]["client_id"]
    if provider == "google":
        return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({"client_id": cid, "redirect_uri": cb, "response_type": "code", "scope": "openid email profile", "state": state, "prompt": "select_account"}))
    if provider == "facebook":
        return redirect("https://www.facebook.com/v19.0/dialog/oauth?" + urlencode({"client_id": cid, "redirect_uri": cb, "response_type": "code", "scope": "email,public_profile", "state": state}))
    return redirect("https://appleid.apple.com/auth/authorize?" + urlencode({"client_id": cid, "redirect_uri": cb, "response_type": "code id_token", "response_mode": "form_post", "scope": "name email", "state": state}))


@app.route("/auth/oauth/<provider>/callback", methods=["GET", "POST"])
def oauth_callback(provider):
    provider = provider.lower()
    if not is_oauth_live(provider):
        return redirect(url_for("auth_page"))
    req_data = request.form if request.method == "POST" else request.args
    if not req_data.get("state") or req_data.get("state") != session.pop("oauth_state", None):
        return redirect(url_for("auth_page", err="Sesi OAuth tidak valid."))
    cb = url_for("oauth_callback", provider=provider, _external=True)
    cid, csec = OAUTH_CFG[provider]["client_id"], OAUTH_CFG[provider]["client_secret"]
    email, name = None, None
    try:
        if provider == "google":
            tok = http_requests.post("https://oauth2.googleapis.com/token", data={"code": req_data.get("code"), "client_id": cid, "client_secret": csec, "redirect_uri": cb, "grant_type": "authorization_code"}, timeout=10).json()
            info = http_requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {tok.get('access_token', '')}"}, timeout=10).json()
            email, name = info.get("email"), info.get("name") or "Google Athlete"
        elif provider == "facebook":
            tok = http_requests.get("https://graph.facebook.com/v19.0/oauth/access_token", params={"client_id": cid, "client_secret": csec, "redirect_uri": cb, "code": req_data.get("code")}, timeout=10).json()
            info = http_requests.get("https://graph.facebook.com/me", params={"fields": "id,name,email", "access_token": tok.get("access_token", "")}, timeout=10).json()
            email, name = info.get("email") or f"fb_{info.get('id', 'u')}@facebook.kinetix.id", info.get("name") or "Facebook Athlete"
        elif provider == "apple":
            parts = req_data.get("id_token", "").split(".")
            if len(parts) >= 2:
                payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)).decode("utf-8"))
                email = payload.get("email") or f"{payload.get('sub', 'apple')}@privaterelay.appleid.com"
            name = "Apple Athlete"
    except Exception:
        return redirect(url_for("auth_page", err=f"Gagal terhubung ke {provider.capitalize()}."))
    if not email:
        return redirect(url_for("auth_page", err="Email tidak tersedia."))
    session["user_id"] = find_or_create_social_user(provider, email, name)
    return redirect(url_for("index"))


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json(force=True)
    username = str(data.get("username", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    name = str(data.get("name", "")).strip()
    password = str(data.get("password", ""))
    if not username or not email or not name or len(password) < 6:
        return jsonify({"error": "Semua kolom wajib diisi dan password minimal 6 karakter."}), 400

    conn = get_connection()
    cur = conn.cursor()
    if cur.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email)).fetchone():
        conn.close()
        return jsonify({"error": "Username atau email sudah terdaftar."}), 409

    cur.execute("""
        INSERT INTO users (username, email, password_hash, role, onboarding_done, name, created_at)
        VALUES (?, ?, ?, 'user', 0, ?, ?)
    """, (username, email, generate_password_hash(password), name, now_label()))
    uid = cur.lastrowid
    cur.execute("INSERT OR IGNORE INTO daily_logs (user_id, date) VALUES (?, ?)", (uid, get_today_str()))
    cur.execute("INSERT OR IGNORE INTO weight_logs (user_id, date, weight_kg, note) VALUES (?, ?, 70.0, 'Berat awal')", (uid, get_today_str()))
    push_notification(conn, uid, "Selamat Datang!", f"Halo {name}, ikuti panduan interaktif untuk mengenal seluruh fitur KINETIX 3D.", "sparkles", "toska")
    notify_developers(conn, "User Baru Terdaftar", f"{name} (@{username}) baru saja membuat akun.", "user-plus", "ocean")
    conn.commit()
    conn.close()
    session["user_id"] = uid
    return jsonify({"status": "registered"}), 201


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    identifier = str(data.get("identifier", "")).strip().lower()
    password = str(data.get("password", ""))
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier)).fetchone()
    conn.close()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Username/email atau password salah."}), 401
    session["user_id"] = user["id"]
    return jsonify({"status": "ok", "name": user["name"], "role": user["role"]})


@app.route("/api/auth/social", methods=["POST"])
def api_social_login():
    data = request.get_json(force=True)
    provider = str(data.get("provider", "google")).strip().lower()
    if provider not in ("google", "facebook", "apple"):
        return jsonify({"error": "Provider tidak didukung."}), 400
    email = str(data.get("email", "")).strip().lower() or f"{provider}_athlete@kinetix.id"
    name = str(data.get("name", "")).strip() or f"{provider.capitalize()} Athlete"
    if "@" not in email:
        return jsonify({"error": "Format email tidak valid."}), 400
    session["user_id"] = find_or_create_social_user(provider, email, name)
    return jsonify({"status": "ok"})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"status": "logged_out"})


# ===================== DASHBOARD & CORE API =====================

@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/dashboard", methods=["GET"])
@login_required
def api_dashboard():
    uid = session["user_id"]
    conn = get_connection()
    cur = conn.cursor()
    today_str = get_today_str()

    user_row = cur.execute("""
        SELECT id, username, email, role, onboarding_done, name, weight_kg, height_cm, age, gender,
               activity_level, goal, daily_water_target, daily_cal_target
        FROM users WHERE id = ?
    """, (uid,)).fetchone()
    if not user_row:
        conn.close()
        session.clear()
        return jsonify({"error": "Akun tidak ditemukan."}), 401
    profile = dict(user_row)

    daily_row = cur.execute("SELECT * FROM daily_logs WHERE user_id = ? AND date = ?", (uid, today_str)).fetchone()
    if not daily_row:
        cur.execute("INSERT INTO daily_logs (user_id, date) VALUES (?, ?)", (uid, today_str))
        conn.commit()
        daily_row = cur.execute("SELECT * FROM daily_logs WHERE user_id = ? AND date = ?", (uid, today_str)).fetchone()
    daily = dict(daily_row)

    workouts = [dict(r) for r in cur.execute("SELECT * FROM workouts WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 120", (uid,)).fetchall()]
    all_stats = cur.execute("SELECT COUNT(*) AS cnt, COALESCE(SUM(volume), 0) AS total_vol FROM workouts WHERE user_id = ?", (uid,)).fetchone()
    all_dates = [r["date"] for r in cur.execute("SELECT DISTINCT date FROM workouts WHERE user_id = ?", (uid,)).fetchall()]
    streak = compute_streak(all_dates)
    lifetime_volume = round(float(all_stats["total_vol"]), 1)

    today_burned = sum(w["calories"] for w in workouts if w["date"] == today_str)
    today_volume = sum(w["volume"] for w in workouts if w["date"] == today_str)
    today_sets = sum(w["sets"] for w in workouts if w["date"] == today_str)

    labels, cal_series, vol_series = [], [], []
    today_dt = datetime.now()
    for i in range(6, -1, -1):
        d = today_dt - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        labels.append(d.strftime("%a"))
        day_items = [w for w in workouts if w["date"] == d_str]
        cal_series.append(sum(x["calories"] for x in day_items))
        vol_series.append(round(sum(x["volume"] for x in day_items), 1))

    heatmap_28d = []
    for i in range(27, -1, -1):
        d = today_dt - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        day_items = [w for w in workouts if w["date"] == d_str]
        d_sets = sum(x["sets"] for x in day_items)
        d_vol = round(sum(x["volume"] for x in day_items), 1)
        level = 0 if d_sets == 0 else (1 if d_sets <= 5 else (2 if d_sets <= 10 else 3))
        heatmap_28d.append({"date": d_str, "sets": d_sets, "volume": d_vol, "level": level})

    muscle_distribution = {m: 0 for m in MUSCLE_GROUPS}
    muscle_fatigue = {m: 0 for m in MUSCLE_GROUPS}
    for w in workouts:
        m = w["muscle_group"]
        if m not in MUSCLE_GROUPS:
            continue
        muscle_distribution[m] += w["sets"]
        try:
            days_diff = (today_dt.date() - datetime.strptime(w["date"], "%Y-%m-%d").date()).days
        except ValueError:
            days_diff = 7
        if days_diff == 0:
            muscle_fatigue[m] = min(100, muscle_fatigue[m] + w["sets"] * 18)
        elif days_diff == 1:
            muscle_fatigue[m] = min(100, muscle_fatigue[m] + w["sets"] * 11)
        elif days_diff == 2:
            muscle_fatigue[m] = min(100, muscle_fatigue[m] + w["sets"] * 5)

    prs = [dict(r) for r in cur.execute("""
        SELECT exercise_name, muscle_group, MAX(weight_kg) AS max_weight, MAX(volume) AS max_volume
        FROM workouts WHERE user_id = ? GROUP BY exercise_name ORDER BY max_weight DESC LIMIT 6
    """, (uid,)).fetchall()]

    weight_logs = [dict(r) for r in cur.execute("SELECT id, date, weight_kg, body_fat, note FROM weight_logs WHERE user_id = ? ORDER BY date ASC LIMIT 30", (uid,)).fetchall()]
    notif_rows = [dict(r) for r in cur.execute("SELECT id, title, body, icon, tone, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 25", (uid,)).fetchall()]
    unread_count = sum(1 for n in notif_rows if n["is_read"] == 0)

    badges = [
        {"id": "first", "title": "First Rep", "desc": "Catat sesi pertama", "unlocked": all_stats["cnt"] >= 1, "icon": "zap"},
        {"id": "streak3", "title": "Iron Streak", "desc": "Latihan 3+ hari beruntun", "unlocked": streak >= 3, "icon": "flame"},
        {"id": "ton5", "title": "5 Ton Club", "desc": "Total volume ≥ 5.000 kg", "unlocked": lifetime_volume >= 5000, "icon": "trophy"},
        {"id": "hydro", "title": "Hydro Pro", "desc": "Capai target air harian", "unlocked": daily["water_ml"] >= profile["daily_water_target"], "icon": "droplets"},
        {"id": "balanced", "title": "Full Anatomy", "desc": "Latih semua 6 otot", "unlocked": all(v > 0 for v in muscle_distribution.values()), "icon": "shield-check"},
    ]

    custom_glb = MODELS_DIR / f"user_{uid}.glb"
    default_glb = MODELS_DIR / "athlete.glb"
    glb_url = f"/static/models/user_{uid}.glb?v={int(custom_glb.stat().st_mtime)}" if custom_glb.exists() else (f"/static/models/athlete.glb?v={int(default_glb.stat().st_mtime)}" if default_glb.exists() else None)

    conn.close()
    return jsonify({
        "profile": profile, "daily": daily, "glb_url": glb_url,
        "notifications": notif_rows, "unread_count": unread_count,
        "summary": {"today_burned": today_burned, "today_volume": round(today_volume, 1), "today_sets": today_sets, "streak": streak, "lifetime_volume": lifetime_volume, "total_sessions": len(all_dates)},
        "charts": {"labels": labels, "calories": cal_series, "volume": vol_series, "muscle_distribution": muscle_distribution},
        "heatmap_28d": heatmap_28d, "muscle_fatigue": muscle_fatigue,
        "workouts": workouts, "prs": prs, "weight_logs": weight_logs, "badges": badges
    })


@app.route("/api/notifications/read", methods=["POST"])
@login_required
def mark_notifications_read():
    conn = get_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (session["user_id"],))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/onboarding/complete", methods=["POST"])
@login_required
def complete_onboarding():
    conn = get_connection()
    conn.execute("UPDATE users SET onboarding_done = 1 WHERE id = ?", (session["user_id"],))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/workouts", methods=["POST"])
@login_required
def add_workout():
    uid = session["user_id"]
    data = request.get_json(force=True)
    exercise_name = str(data.get("exercise_name", "")).strip()
    muscle_group = str(data.get("muscle_group", "chest")).strip().lower()
    sets = max(1, int(data.get("sets", 3)))
    reps = max(1, int(data.get("reps", 10)))
    weight_kg = max(0.0, float(data.get("weight_kg", 0)))
    date_str = str(data.get("date") or get_today_str())
    if not exercise_name:
        return jsonify({"error": "Nama latihan wajib diisi."}), 400
    if muscle_group not in MUSCLE_GROUPS:
        muscle_group = "chest"

    volume = round(sets * reps * (weight_kg if weight_kg > 0 else 1.0), 1)
    calories = int(data.get("calories") or round(sets * reps * 0.45 + (weight_kg * sets * 0.35) + 25))

    conn = get_connection()
    prev_max = conn.execute("SELECT MAX(weight_kg) FROM workouts WHERE user_id = ? AND LOWER(exercise_name) = LOWER(?)", (uid, exercise_name)).fetchone()[0]
    conn.execute("""
        INSERT INTO workouts (user_id, date, exercise_name, muscle_group, sets, reps, weight_kg, calories, volume, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (uid, date_str, exercise_name, muscle_group, sets, reps, weight_kg, calories, volume, now_label()))

    if prev_max is not None and weight_kg > float(prev_max):
        push_notification(conn, uid, "Personal Record Baru!", f"Rekor baru {exercise_name}: {weight_kg} kg!", "trophy", "amber")
    else:
        push_notification(conn, uid, "Latihan Tercatat", f"{exercise_name} ({sets}×{reps} @ {weight_kg}kg) • Volume {volume} kg.", "dumbbell", "toska")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 201


@app.route("/api/workouts/<int:workout_id>", methods=["DELETE"])
@login_required
def delete_workout(workout_id):
    uid = session["user_id"]
    conn = get_connection()
    conn.execute("DELETE FROM workouts WHERE id = ? AND user_id = ?", (workout_id, uid))
    push_notification(conn, uid, "Riwayat Dihapus", "Satu entri riwayat latihan telah dihapus.", "trash-2", "rose")
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


@app.route("/api/daily", methods=["POST"])
@login_required
def update_daily():
    uid = session["user_id"]
    data = request.get_json(force=True)
    today_str = get_today_str()
    conn = get_connection()
    cur = conn.cursor()

    row = cur.execute("SELECT * FROM daily_logs WHERE user_id = ? AND date = ?", (uid, today_str)).fetchone()
    if not row:
        cur.execute("INSERT INTO daily_logs (user_id, date) VALUES (?, ?)", (uid, today_str))
        conn.commit()
        row = cur.execute("SELECT * FROM daily_logs WHERE user_id = ? AND date = ?", (uid, today_str)).fetchone()
    current = dict(row)
    target_water = cur.execute("SELECT daily_water_target FROM users WHERE id = ?", (uid,)).fetchone()[0]

    water_ml = max(0, current["water_ml"] + int(data["add_water"])) if "add_water" in data else max(0, int(data.get("water_ml", current["water_ml"])))
    steps = max(0, current["steps"] + int(data["add_steps"])) if "add_steps" in data else max(0, int(data.get("steps", current["steps"])))
    calories_in = max(0, int(data.get("calories_in", current["calories_in"])))
    protein_g = max(0, int(data.get("protein_g", current["protein_g"])))
    carbs_g = max(0, int(data.get("carbs_g", current["carbs_g"])))
    fat_g = max(0, int(data.get("fat_g", current["fat_g"])))

    cur.execute("""
        UPDATE daily_logs SET water_ml = ?, steps = ?, calories_in = ?, protein_g = ?, carbs_g = ?, fat_g = ?
        WHERE user_id = ? AND date = ?
    """, (water_ml, steps, calories_in, protein_g, carbs_g, fat_g, uid, today_str))

    if "add_water" in data and current["water_ml"] < target_water <= water_ml:
        push_notification(conn, uid, "Target Hidrasi Tercapai!", f"Asupan air hari ini sudah mencapai {water_ml} ml.", "droplets", "toska")
    elif "calories_in" in data:
        push_notification(conn, uid, "Nutrisi Diperbarui", f"Asupan hari ini: {calories_in} kcal (P:{protein_g}g K:{carbs_g}g L:{fat_g}g).", "utensils", "ocean")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/weights", methods=["POST"])
@login_required
def add_weight_log():
    uid = session["user_id"]
    data = request.get_json(force=True)
    date_str = str(data.get("date") or get_today_str())
    weight_kg = float(data.get("weight_kg", 0))
    bf = data.get("body_fat")
    bf_val = float(bf) if bf not in (None, "", "null") else None
    note = str(data.get("note", "")).strip()[:80]
    if weight_kg <= 20 or weight_kg > 300:
        return jsonify({"error": "Berat badan harus antara 20–300 kg."}), 400

    conn = get_connection()
    conn.execute("""
        INSERT INTO weight_logs (user_id, date, weight_kg, body_fat, note)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET weight_kg = excluded.weight_kg, body_fat = excluded.body_fat, note = excluded.note
    """, (uid, date_str, weight_kg, bf_val, note))
    conn.execute("UPDATE users SET weight_kg = ? WHERE id = ?", (weight_kg, uid))
    push_notification(conn, uid, "Check-In Berat Badan", f"Berat tercatat {weight_kg} kg pada {date_str}.", "scale", "toska")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 201


@app.route("/api/profile", methods=["POST"])
@login_required
def update_profile():
    uid = session["user_id"]
    data = request.get_json(force=True)
    conn = get_connection()
    conn.execute("""
        UPDATE users SET name = ?, weight_kg = ?, height_cm = ?, age = ?, gender = ?,
                         activity_level = ?, goal = ?, daily_water_target = ?, daily_cal_target = ?
        WHERE id = ?
    """, (
        str(data.get("name", "Athlete Pro")).strip() or "Athlete Pro",
        float(data.get("weight_kg", 70)), float(data.get("height_cm", 173)), int(data.get("age", 23)),
        str(data.get("gender", "male")), float(data.get("activity_level", 1.55)), str(data.get("goal", "maintain")),
        int(data.get("daily_water_target", 2500)), int(data.get("daily_cal_target", 650)), uid
    ))
    push_notification(conn, uid, "Profil & TDEE Diperbarui", "Target kalori dan makronutrisi Anda telah disesuaikan.", "user-check", "ocean")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ===================== MARKETPLACE API =====================

@app.route("/api/store/products", methods=["GET"])
@login_required
def api_store_products():
    uid = session["user_id"]
    conn = get_connection()
    products = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()]
    my_orders = [dict(r) for r in conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 30", (uid,)).fetchall()]
    conn.close()
    return jsonify({"products": products, "my_orders": my_orders})


@app.route("/api/store/products/<int:pid>/reviews", methods=["GET", "POST"])
@login_required
def api_product_reviews(pid):
    uid = session["user_id"]
    conn = get_connection()
    if request.method == "POST":
        data = request.get_json(force=True)
        rating = max(1, min(5, int(data.get("rating", 5))))
        comment = str(data.get("comment", "")).strip()[:280]
        if not comment:
            conn.close()
            return jsonify({"error": "Tulis ulasan Anda terlebih dahulu."}), 400
        conn.execute("""
            INSERT INTO product_reviews (product_id, user_id, rating, comment, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (pid, uid, rating, comment, now_label()))
        avg_row = conn.execute("SELECT ROUND(AVG(rating), 1) AS avg_r FROM product_reviews WHERE product_id = ?", (pid,)).fetchone()
        if avg_row and avg_row["avg_r"]:
            conn.execute("UPDATE products SET rating = ? WHERE id = ?", (avg_row["avg_r"], pid))
        conn.commit()

    rows = [dict(r) for r in conn.execute("""
        SELECT r.id, r.rating, r.comment, r.created_at, u.name AS reviewer_name
        FROM product_reviews r JOIN users u ON u.id = r.user_id
        WHERE r.product_id = ? ORDER BY r.id DESC LIMIT 20
    """, (pid,)).fetchall()]
    conn.close()
    return jsonify({"reviews": rows})


@app.route("/api/store/checkout", methods=["POST"])
@login_required
def api_store_checkout():
    uid = session["user_id"]
    data = request.get_json(force=True)
    items = data.get("items") or []
    voucher = str(data.get("voucher", "")).strip().upper()
    payment_method = str(data.get("payment_method", "QRIS")).strip()[:30]
    shipping_method = str(data.get("shipping_method", "Reguler")).strip()[:30]
    shipping_address = str(data.get("shipping_address", "")).strip()[:160] or "Ambil di KINETIX Gym"

    if not items:
        return jsonify({"error": "Keranjang masih kosong."}), 400

    conn = get_connection()
    cur = conn.cursor()
    user = cur.execute("SELECT name, username FROM users WHERE id = ?", (uid,)).fetchone()

    resolved = []
    subtotal = 0
    for it in items:
        pid = int(it.get("product_id", 0))
        qty = max(1, int(it.get("qty", 1)))
        prod = cur.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if not prod:
            conn.close()
            return jsonify({"error": "Salah satu produk tidak ditemukan."}), 404
        if prod["stock"] < qty:
            conn.close()
            return jsonify({"error": f"Stok {prod['name']} hanya tersisa {prod['stock']}."}), 400
        resolved.append((dict(prod), qty))
        subtotal += prod["price"] * qty

    shipping_fee = 15000 if shipping_method == "Express" else (8000 if shipping_method == "Reguler" else 0)
    discount = 0
    if voucher == "FIT10":
        discount = round(subtotal * 0.10)
    elif voucher == "KALSIUM10" and subtotal >= 30000:
        discount = 10000

    order_code = f"KNX-{datetime.now().strftime('%m%d')}-{secrets.token_hex(2).upper()}"
    hydration_added = 0
    item_summaries = []

    for idx, (prod, qty) in enumerate(resolved):
        line_total = prod["price"] * qty
        line_disc = discount if idx == 0 else 0
        line_ship = shipping_fee if idx == 0 else 0
        final_line = max(0, line_total - line_disc + line_ship)

        cur.execute("UPDATE products SET stock = stock - ?, sold_count = sold_count + ? WHERE id = ?", (qty, qty, prod["id"]))
        cur.execute("""
            INSERT INTO orders (order_code, user_id, product_id, product_name, qty, total_price, discount_amount, payment_method, shipping_method, shipping_address, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Diproses', ?)
        """, (order_code, uid, prod["id"], prod["name"], qty, final_line, line_disc, payment_method, shipping_method, shipping_address, now_label()))

        item_summaries.append(f"{qty}× {prod['name']}")
        if "minuman" in prod["category"].lower() or "energy" in prod["category"].lower():
            hydration_added += prod["volume_ml"] * qty

    if hydration_added > 0:
        today_str = get_today_str()
        cur.execute("INSERT OR IGNORE INTO daily_logs (user_id, date) VALUES (?, ?)", (uid, today_str))
        cur.execute("UPDATE daily_logs SET water_ml = water_ml + ? WHERE user_id = ? AND date = ?", (hydration_added, uid, today_str))

    grand_total = max(0, subtotal - discount + shipping_fee)
    extra_h = f" (+{hydration_added}ml hidrasi otomatis)" if hydration_added else ""
    push_notification(conn, uid, f"Pesanan {order_code} Berhasil!", f"{', '.join(item_summaries)} • Rp {grand_total:,} via {payment_method}{extra_h}.", "shopping-bag", "toska")
    notify_developers(conn, f"Order Marketplace {order_code}", f"{user['name']} membeli {', '.join(item_summaries)} (Rp {grand_total:,} • {shipping_method}).", "shopping-cart", "amber")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "order_code": order_code, "grand_total": grand_total, "hydration_added": hydration_added}), 201


# ===================== CHATBOT & LIVE CS =====================

def generate_bot_reply(conn, uid, text):
    msg = text.lower()
    user = dict(conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())
    daily = conn.execute("SELECT * FROM daily_logs WHERE user_id = ? AND date = ?", (uid, get_today_str())).fetchone()
    products = [dict(r) for r in conn.execute("SELECT name, category, price, stock, benefit FROM products WHERE stock > 0 ORDER BY sold_count DESC").fetchall()]

    h_m = user["height_cm"] / 100.0
    bmi = round(user["weight_kg"] / (h_m * h_m), 1)
    bmr = 10 * user["weight_kg"] + 6.25 * user["height_cm"] - 5 * user["age"] + (5 if user["gender"] == "male" else -161)
    tdee = round(bmr * user["activity_level"])
    target_cal = tdee - 400 if user["goal"] == "cut" else (tdee + 350 if user["goal"] == "bulk" else tdee)
    protein = round(user["weight_kg"] * 2.0)

    if any(k in msg for k in ("cs", "customer", "admin", "manusia", "komplain", "bantuan")):
        notify_developers(conn, "Permintaan Bantuan CS", f"{user['name']} (@{user['username']}): \"{text[:70]}\"", "headphones", "rose")
        return "Pesan Anda sudah diteruskan ke Tim Customer Service kami. Aktifkan tab 'Live CS' di atas agar balasan CS langsung masuk ke sini."

    if any(k in msg for k in ("kalsium", "minuman", "toko", "beli", "harga", "suplemen", "whey", "tulang", "promo", "voucher")):
        if not products:
            return "Saat ini stok minuman & suplemen di Marketplace sedang habis. Cek lagi sebentar lagi ya!"
        calcium = [p for p in products if "kalsium" in p["category"].lower() or "calci" in p["name"].lower() or "osteo" in p["name"].lower()]
        picks = calcium if calcium else products[:3]
        lines = [f"• {p['name']} — Rp {p['price']:,} (Stok: {p['stock']})" for p in picks[:3]]
        return "Rekomendasi terlaris di Marketplace KINETIX:\n" + "\n".join(lines) + "\n\nTips hemat: Gunakan voucher FIT10 (diskon 10%) atau KALSIUM10 (potongan Rp 10.000) saat checkout di tab Toko!"

    if any(k in msg for k in ("otot", "latihan", "workout", "split", "program", "jadwal", "lelah")):
        recent = conn.execute("SELECT muscle_group, date, sets FROM workouts WHERE user_id = ? ORDER BY date DESC LIMIT 20", (uid,)).fetchall()
        fat = {m: 0 for m in MUSCLE_GROUPS}
        today_d = datetime.now().date()
        for w in recent:
            if w["muscle_group"] not in fat:
                continue
            try:
                diff = (today_d - datetime.strptime(w["date"], "%Y-%m-%d").date()).days
            except ValueError:
                diff = 5
            if diff == 0:
                fat[w["muscle_group"]] += w["sets"] * 18
            elif diff == 1:
                fat[w["muscle_group"]] += w["sets"] * 11
        fresh = [m.capitalize() for m, v in fat.items() if v < 30]
        tired = [m.capitalize() for m, v in fat.items() if v >= 60]
        fresh_txt = ", ".join(fresh) if fresh else "Semua otot baru dilatih (ambil hari istirahat/kardio ringan)"
        tired_txt = f" Otot butuh pemulihan: {', '.join(tired)}." if tired else ""
        return f"Berdasarkan Heatmap 3D hari ini, otot paling siap dilatih (Fresh): {fresh_txt}.{tired_txt} Buka tab Split untuk template gerakan cepat."

    if any(k in msg for k in ("kalori", "tdee", "bmi", "diet", "protein", "bulking", "cutting", "nutrisi")):
        return f"Biometrik {user['name']}: BMI {bmi}, TDEE {tdee} kcal/hari. Untuk target {user['goal'].upper()}, target asupan sekitar {target_cal} kcal dan protein ±{protein}g/hari."

    if any(k in msg for k in ("air", "minum", "hidrasi")):
        cur_w = daily["water_ml"] if daily else 0
        sisa = max(0, user["daily_water_target"] - cur_w)
        return f"Hidrasi hari ini: {cur_w} ml / {user['daily_water_target']} ml (kurang {sisa} ml). Beli minuman kalsium di tab Toko juga otomatis menambah hidrasi!"

    return f"Halo {user['name']}! Coba tanyakan:\n1) 'Rekomendasi minuman kalsium & voucher'\n2) 'Otot apa yang siap dilatih hari ini?'\n3) 'Berapa target kalori & protein saya?'\n4) 'Hubungi CS'"


@app.route("/api/chat", methods=["GET", "POST"])
@login_required
def api_chat():
    uid = session["user_id"]
    conn = get_connection()
    if request.method == "GET":
        rows = [dict(r) for r in conn.execute("SELECT id, sender_role, message, created_at FROM support_messages WHERE user_id = ? ORDER BY id ASC LIMIT 60", (uid,)).fetchall()]
        conn.close()
        return jsonify({"messages": rows})

    data = request.get_json(force=True)
    text = str(data.get("message", "")).strip()
    mode = str(data.get("mode", "bot")).strip().lower()
    if not text:
        conn.close()
        return jsonify({"error": "Pesan tidak boleh kosong."}), 400

    user = conn.execute("SELECT name, username FROM users WHERE id = ?", (uid,)).fetchone()
    conn.execute("INSERT INTO support_messages (user_id, sender_role, message, created_at) VALUES (?, 'user', ?, ?)", (uid, text, now_label()))

    if mode == "cs":
        notify_developers(conn, "Pesan CS Baru", f"{user['name']} (@{user['username']}): {text[:80]}", "message-circle", "amber")
    else:
        reply = generate_bot_reply(conn, uid, text)
        conn.execute("INSERT INTO support_messages (user_id, sender_role, message, created_at) VALUES (?, 'bot', ?, ?)", (uid, reply, now_label()))

    conn.commit()
    rows = [dict(r) for r in conn.execute("SELECT id, sender_role, message, created_at FROM support_messages WHERE user_id = ? ORDER BY id ASC LIMIT 60", (uid,)).fetchall()]
    conn.close()
    return jsonify({"messages": rows}), 201


# ===================== ROLE DEVELOPER / SELLER CENTER API =====================

@app.route("/api/dev/overview", methods=["GET"])
@developer_required
def api_dev_overview():
    conn = get_connection()
    users = [dict(r) for r in conn.execute("""
        SELECT u.id, u.username, u.email, u.role, u.name, u.weight_kg, u.height_cm, u.goal, u.created_at,
               (SELECT COUNT(*) FROM workouts w WHERE w.user_id = u.id) AS workout_count,
               (SELECT COALESCE(SUM(volume), 0) FROM workouts w WHERE w.user_id = u.id) AS total_volume,
               (SELECT COALESCE(SUM(total_price), 0) FROM orders o WHERE o.user_id = u.id) AS total_spent
        FROM users u ORDER BY u.id DESC
    """).fetchall()]
    products = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()]
    orders = [dict(r) for r in conn.execute("""
        SELECT o.*, u.name AS buyer_name, u.username AS buyer_username
        FROM orders o JOIN users u ON u.id = o.user_id
        ORDER BY o.id DESC LIMIT 50
    """).fetchall()]
    threads = [dict(r) for r in conn.execute("""
        SELECT u.id AS user_id, u.name, u.username,
               (SELECT message FROM support_messages m WHERE m.user_id = u.id ORDER BY m.id DESC LIMIT 1) AS last_message,
               (SELECT created_at FROM support_messages m WHERE m.user_id = u.id ORDER BY m.id DESC LIMIT 1) AS last_time
        FROM users u
        WHERE EXISTS (SELECT 1 FROM support_messages m WHERE m.user_id = u.id)
        ORDER BY last_time DESC
    """).fetchall()]
    total_revenue = sum(o["total_price"] for o in orders)
    conn.close()
    return jsonify({
        "stats": {"total_users": len(users), "total_products": len(products), "total_orders": len(orders), "total_revenue": total_revenue},
        "users": users, "products": products, "orders": orders, "threads": threads
    })


@app.route("/api/dev/products", methods=["POST"])
@developer_required
def api_dev_add_product():
    # Mendukung multipart FormData (dengan upload file foto) maupun JSON
    if request.content_type and "multipart/form-data" in request.content_type:
        form = request.form
        name = str(form.get("name", "")).strip()
        category = str(form.get("category", "Minuman Kalsium")).strip()
        price = max(1000, int(form.get("price", 25000)))
        original_price = max(0, int(form.get("original_price", 0) or 0))
        stock = max(0, int(form.get("stock", 20)))
        volume_ml = max(0, int(form.get("volume_ml", 500) or 0))
        benefit = str(form.get("benefit", "")).strip() or "Mendukung performa olahraga & kesehatan tulang."
        badge = str(form.get("badge", "Promo")).strip() or "Promo"
        image_url = str(form.get("image_url", "")).strip()

        img_file = request.files.get("image_file")
        if img_file and img_file.filename:
            ext = Path(img_file.filename).suffix.lower()
            if ext in ALLOWED_IMG_EXT:
                safe_name = f"prod_{secrets.token_hex(6)}{ext}"
                img_file.save(PRODUCTS_IMG_DIR / safe_name)
                image_url = f"/static/uploads/products/{safe_name}"
    else:
        data = request.get_json(force=True)
        name = str(data.get("name", "")).strip()
        category = str(data.get("category", "Minuman Kalsium")).strip()
        price = max(1000, int(data.get("price", 25000)))
        original_price = max(0, int(data.get("original_price", 0) or 0))
        stock = max(0, int(data.get("stock", 20)))
        volume_ml = max(0, int(data.get("volume_ml", 500) or 0))
        benefit = str(data.get("benefit", "")).strip() or "Mendukung performa olahraga & kesehatan tulang."
        badge = str(data.get("badge", "Baru")).strip() or "Baru"
        image_url = str(data.get("image_url", "")).strip()

    if not name:
        return jsonify({"error": "Nama produk wajib diisi."}), 400

    conn = get_connection()
    conn.execute("""
        INSERT INTO products (name, category, price, original_price, stock, volume_ml, benefit, badge, image_url, sold_count, rating, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 5.0, ?)
    """, (name, category, price, original_price, stock, volume_ml, benefit, badge, image_url, now_label()))
    notify_all_users(conn, "Produk Baru di Marketplace!", f"{name} ({category}) kini hadir dengan harga Rp {price:,}!", "shopping-bag", "toska")
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201


@app.route("/api/dev/products/<int:pid>", methods=["PATCH", "DELETE"])
@developer_required
def api_dev_manage_product(pid):
    conn = get_connection()
    if request.method == "DELETE":
        conn.execute("DELETE FROM products WHERE id = ?", (pid,))
    else:
        data = request.get_json(force=True)
        delta = int(data.get("stock_delta", 0))
        conn.execute("UPDATE products SET stock = MAX(0, stock + ?) WHERE id = ?", (delta, pid))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/dev/orders/<int:oid>", methods=["PATCH"])
@developer_required
def api_dev_update_order(oid):
    data = request.get_json(force=True)
    status = str(data.get("status", "Diproses")).strip()
    if status not in ("Diproses", "Dikemas", "Dikirim", "Selesai"):
        return jsonify({"error": "Status tidak valid."}), 400

    conn = get_connection()
    order = conn.execute("SELECT user_id, order_code, product_name FROM orders WHERE id = ?", (oid,)).fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Pesanan tidak ditemukan."}), 404

    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, oid))
    code_lbl = order["order_code"] or f"#{oid}"
    push_notification(conn, order["user_id"], f"Status Pesanan {code_lbl}: {status}", f"Pesanan {order['product_name']} Anda sekarang berstatus '{status}'.", "truck", "ocean")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/dev/chat/<int:target_uid>", methods=["GET", "POST"])
@developer_required
def api_dev_chat(target_uid):
    conn = get_connection()
    if request.method == "GET":
        rows = [dict(r) for r in conn.execute("SELECT id, sender_role, message, created_at FROM support_messages WHERE user_id = ? ORDER BY id ASC", (target_uid,)).fetchall()]
        conn.close()
        return jsonify({"messages": rows})

    data = request.get_json(force=True)
    text = str(data.get("message", "")).strip()
    if not text:
        conn.close()
        return jsonify({"error": "Balasan tidak boleh kosong."}), 400
    conn.execute("INSERT INTO support_messages (user_id, sender_role, message, created_at) VALUES (?, 'developer', ?, ?)", (target_uid, text, now_label()))
    push_notification(conn, target_uid, "Balasan dari Customer Service", text[:90], "headphones", "ocean")
    conn.commit()
    rows = [dict(r) for r in conn.execute("SELECT id, sender_role, message, created_at FROM support_messages WHERE user_id = ? ORDER BY id ASC", (target_uid,)).fetchall()]
    conn.close()
    return jsonify({"messages": rows}), 201


# ===================== MODEL 3D .GLB & EXPORT EXCEL =====================

@app.route("/api/models/upload", methods=["POST"])
@login_required
def upload_glb_model():
    uid = session["user_id"]
    if "model" not in request.files:
        return jsonify({"error": "File tidak ditemukan."}), 400
    f = request.files["model"]
    if not f.filename or not f.filename.lower().endswith(".glb"):
        return jsonify({"error": "Format wajib .glb (binary glTF)."}), 400
    dest = MODELS_DIR / f"user_{uid}.glb"
    f.save(dest)
    conn = get_connection()
    push_notification(conn, uid, "Model 3D .GLB Diperbarui", "Model 3D realistis berhasil dimuat ke Anatomy Lab.", "box", "toska")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "glb_url": f"/static/models/user_{uid}.glb?v={int(dest.stat().st_mtime)}"})


@app.route("/api/export/excel", methods=["GET"])
@login_required
def export_excel():
    uid = session["user_id"]
    conn = get_connection()
    user = dict(conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())
    workouts = [dict(r) for r in conn.execute("SELECT * FROM workouts WHERE user_id = ? ORDER BY date DESC, id DESC", (uid,)).fetchall()]
    daily_logs = [dict(r) for r in conn.execute("SELECT * FROM daily_logs WHERE user_id = ? ORDER BY date DESC", (uid,)).fetchall()]
    weight_logs = [dict(r) for r in conn.execute("SELECT * FROM weight_logs WHERE user_id = ? ORDER BY date DESC", (uid,)).fetchall()]
    conn.close()

    wb = Workbook()
    header_fill = PatternFill("solid", fgColor="0F2933")
    zebra_fill = PatternFill("solid", fgColor="F0FDFA")
    white_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    thin_side = Side(style="thin", color="CBD5E1")
    border_all = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    ws_sum = wb.active
    ws_sum.title = "Ringkasan"
    ws_sum["A1"] = f"LAPORAN PROGRES FITNESS — {user['name'].upper()}"
    ws_sum["A1"].font = Font(name="Calibri", size=15, bold=True, color="0F2933")
    ws_sum["A2"] = f"Diekspor pada: {now_label()}"

    ws_sum["A4"], ws_sum["B4"] = "Metrik", "Nilai"
    for c in ("A4", "B4"):
        ws_sum[c].fill, ws_sum[c].font, ws_sum[c].alignment = header_fill, white_bold, Alignment(horizontal="center")

    h_m = user["height_cm"] / 100.0
    bmi = round(user["weight_kg"] / (h_m * h_m), 1)
    for idx, (lbl, val) in enumerate([
        ("Username", user["username"]), ("Berat Badan (kg)", user["weight_kg"]), ("Tinggi (cm)", user["height_cm"]),
        ("BMI", bmi), ("Target", user["goal"].upper()),
        ("Total Entri Latihan", "=COUNTA('Riwayat Latihan'!B2:B1000)"),
        ("Total Volume (kg)", "=SUM('Riwayat Latihan'!G2:G1000)"),
        ("Total Kalori (kcal)", "=SUM('Riwayat Latihan'!H2:H1000)"),
    ], start=5):
        ws_sum[f"A{idx}"], ws_sum[f"B{idx}"] = lbl, val
        ws_sum[f"A{idx}"].border = ws_sum[f"B{idx}"].border = border_all

    ws_sum["D4"], ws_sum["E4"] = "Kelompok Otot", "Total Set"
    for c in ("D4", "E4"):
        ws_sum[c].fill, ws_sum[c].font, ws_sum[c].alignment = header_fill, white_bold, Alignment(horizontal="center")
    counts = {m: 0 for m in MUSCLE_GROUPS}
    for w in workouts:
        if w["muscle_group"] in counts:
            counts[w["muscle_group"]] += w["sets"]
    for idx, m in enumerate(MUSCLE_GROUPS, start=5):
        ws_sum[f"D{idx}"], ws_sum[f"E{idx}"] = m.capitalize(), counts[m]
        ws_sum[f"D{idx}"].border = ws_sum[f"E{idx}"].border = border_all

    chart = BarChart()
    chart.title = "Distribusi Total Set per Otot"
    chart.add_data(Reference(ws_sum, min_col=5, min_row=4, max_row=4 + len(MUSCLE_GROUPS)), titles_from_data=True)
    chart.set_categories(Reference(ws_sum, min_col=4, min_row=5, max_row=4 + len(MUSCLE_GROUPS)))
    chart.legend = None
    ws_sum.add_chart(chart, "D12")
    for col, w_dim in zip("ABCDE", [28, 18, 4, 18, 14]):
        ws_sum.column_dimensions[col].width = w_dim

    ws_w = wb.create_sheet("Riwayat Latihan")
    ws_w.append(["Tanggal", "Latihan", "Otot", "Set", "Rep", "Beban (kg)", "Volume (kg)", "Kalori"])
    for ci in range(1, 9):
        c = ws_w.cell(row=1, column=ci)
        c.fill, c.font, c.alignment = header_fill, white_bold, Alignment(horizontal="center")
    for ri, w in enumerate(workouts, start=2):
        ws_w.append([w["date"], w["exercise_name"], w["muscle_group"].capitalize(), w["sets"], w["reps"], w["weight_kg"], w["volume"], w["calories"]])
        for ci in range(1, 9):
            cell = ws_w.cell(row=ri, column=ci)
            cell.border = border_all
            if ri % 2 == 1:
                cell.fill = zebra_fill
    ws_w.freeze_panes = "A2"

    ws_d = wb.create_sheet("Log Harian")
    ws_d.append(["Tanggal", "Air (ml)", "Langkah", "Kalori Masuk", "Protein", "Karbo", "Lemak"])
    for ci in range(1, 8):
        c = ws_d.cell(row=1, column=ci)
        c.fill, c.font, c.alignment = header_fill, white_bold, Alignment(horizontal="center")
    for d in daily_logs:
        ws_d.append([d["date"], d["water_ml"], d["steps"], d["calories_in"], d["protein_g"], d["carbs_g"], d["fat_g"]])

    ws_bw = wb.create_sheet("Progres Berat Badan")
    ws_bw.append(["Tanggal", "Berat (kg)", "Body Fat (%)", "Catatan"])
    for ci in range(1, 5):
        c = ws_bw.cell(row=1, column=ci)
        c.fill, c.font, c.alignment = header_fill, white_bold, Alignment(horizontal="center")
    for wl in weight_logs:
        ws_bw.append([wl["date"], wl["weight_kg"], wl["body_fat"], wl["note"]])

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(out, as_attachment=True, download_name=f"KINETIX_3D_{user['username']}_{get_today_str()}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    app.run(debug=True, port=5000)