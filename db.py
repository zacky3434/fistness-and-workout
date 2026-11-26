import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from werkzeug.security import generate_password_hash

# Ubah menjadi "kinetix_fit.db" jika Anda me-rename file database Anda
DB_PATH = Path(__file__).resolve().parent / "kinetix_fit_v2.db"

DEFAULT_PRODUCT_META = {
    "CalciPro Max Hydration 500ml": (
        "https://images.unsplash.com/photo-1622543925917-763c34d1a86e?auto=format&fit=crop&w=600&q=80",
        35000, 142, 4.9
    ),
    "OsteoFit Calcium + Collagen": (
        "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?auto=format&fit=crop&w=600&q=80",
        45000, 98, 4.8
    ),
    "HydroIon Electrolyte Toska": (
        "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?auto=format&fit=crop&w=600&q=80",
        28000, 215, 4.9
    ),
    "PureWhey Isolate Vanilla": (
        "https://images.unsplash.com/photo-1593095948071-474c5cc2989d?auto=format&fit=crop&w=600&q=80",
        220000, 84, 5.0
    ),
    "NitroCharge Pre-Workout": (
        "https://images.unsplash.com/photo-1579722821273-0f6c7d44362f?auto=format&fit=crop&w=600&q=80",
        175000, 67, 4.7
    ),
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            onboarding_done INTEGER NOT NULL DEFAULT 0,
            name TEXT NOT NULL DEFAULT 'Athlete',
            weight_kg REAL NOT NULL DEFAULT 70.0,
            height_cm REAL NOT NULL DEFAULT 173.0,
            age INTEGER NOT NULL DEFAULT 23,
            gender TEXT NOT NULL DEFAULT 'male',
            activity_level REAL NOT NULL DEFAULT 1.55,
            goal TEXT NOT NULL DEFAULT 'bulk',
            daily_water_target INTEGER NOT NULL DEFAULT 2500,
            daily_cal_target INTEGER NOT NULL DEFAULT 650,
            created_at TEXT NOT NULL
        )
    """)

    user_cols = [r["name"] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
    if "role" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "onboarding_done" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN onboarding_done INTEGER NOT NULL DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            exercise_name TEXT NOT NULL,
            muscle_group TEXT NOT NULL,
            sets INTEGER NOT NULL,
            reps INTEGER NOT NULL,
            weight_kg REAL NOT NULL DEFAULT 0,
            calories INTEGER NOT NULL DEFAULT 0,
            volume REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            water_ml INTEGER NOT NULL DEFAULT 0,
            steps INTEGER NOT NULL DEFAULT 0,
            calories_in INTEGER NOT NULL DEFAULT 0,
            protein_g INTEGER NOT NULL DEFAULT 0,
            carbs_g INTEGER NOT NULL DEFAULT 0,
            fat_g INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weight_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            weight_kg REAL NOT NULL,
            body_fat REAL DEFAULT NULL,
            note TEXT DEFAULT '',
            UNIQUE(user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Minuman Kalsium',
            price INTEGER NOT NULL DEFAULT 25000,
            original_price INTEGER NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 20,
            volume_ml INTEGER NOT NULL DEFAULT 500,
            benefit TEXT NOT NULL DEFAULT '',
            badge TEXT NOT NULL DEFAULT 'Best Seller',
            image_url TEXT NOT NULL DEFAULT '',
            sold_count INTEGER NOT NULL DEFAULT 0,
            rating REAL NOT NULL DEFAULT 4.8,
            created_at TEXT NOT NULL
        )
    """)

    prod_cols = [r["name"] for r in cur.execute("PRAGMA table_info(products)").fetchall()]
    if "original_price" not in prod_cols:
        cur.execute("ALTER TABLE products ADD COLUMN original_price INTEGER NOT NULL DEFAULT 0")
    if "image_url" not in prod_cols:
        cur.execute("ALTER TABLE products ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
    if "sold_count" not in prod_cols:
        cur.execute("ALTER TABLE products ADD COLUMN sold_count INTEGER NOT NULL DEFAULT 0")
    if "rating" not in prod_cols:
        cur.execute("ALTER TABLE products ADD COLUMN rating REAL NOT NULL DEFAULT 4.8")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT NOT NULL DEFAULT '',
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1,
            total_price INTEGER NOT NULL DEFAULT 0,
            discount_amount INTEGER NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'QRIS',
            shipping_method TEXT NOT NULL DEFAULT 'Reguler',
            shipping_address TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Diproses',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    ord_cols = [r["name"] for r in cur.execute("PRAGMA table_info(orders)").fetchall()]
    if "order_code" not in ord_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN order_code TEXT NOT NULL DEFAULT ''")
    if "discount_amount" not in ord_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN discount_amount INTEGER NOT NULL DEFAULT 0")
    if "payment_method" not in ord_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'QRIS'")
    if "shipping_method" not in ord_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN shipping_method TEXT NOT NULL DEFAULT 'Reguler'")
    if "shipping_address" not in ord_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN shipping_address TEXT NOT NULL DEFAULT ''")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL DEFAULT 5,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender_role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            icon TEXT NOT NULL DEFAULT 'bell',
            tone TEXT NOT NULL DEFAULT 'toska',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Seed akun User demo
    cur.execute("SELECT COUNT(*) FROM users WHERE username = 'athlete'")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO users (
                username, email, password_hash, role, onboarding_done, name, weight_kg, height_cm,
                age, gender, activity_level, goal, daily_water_target, daily_cal_target, created_at
            )
            VALUES (?, ?, ?, 'user', 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "athlete", "athlete@kinetix.id", generate_password_hash("password123"),
            "Athlete Pro", 70.0, 173.0, 23, "male", 1.55, "bulk", 2500, 650, now_iso
        ))
        demo_uid = cur.lastrowid

        today = datetime.now()
        sample_workouts = [
            (0, "Incline Dumbbell Press", "chest", 4, 10, 24.0, 145),
            (0, "Cable Tricep Pushdown", "arms", 3, 12, 20.0, 85),
            (1, "Barbell Back Squat", "legs", 4, 8, 80.0, 220),
            (1, "Weighted Plank Hold", "core", 3, 60, 10.0, 90),
            (2, "Lat Pulldown Wide", "back", 4, 10, 55.0, 160),
            (3, "Overhead Shoulder Press", "shoulders", 4, 10, 35.0, 150),
        ]
        for days_ago, name, muscle, sets, reps, weight, cal in sample_workouts:
            d_str = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            vol = round(sets * reps * (weight if weight > 0 else 1.0), 1)
            cur.execute("""
                INSERT INTO workouts (user_id, date, exercise_name, muscle_group, sets, reps, weight_kg, calories, volume, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (demo_uid, d_str, name, muscle, sets, reps, weight, cal, vol, now_iso))

        cur.execute("""
            INSERT INTO daily_logs (user_id, date, water_ml, steps, calories_in, protein_g, carbs_g, fat_g)
            VALUES (?, ?, 1250, 5400, 1650, 115, 190, 48)
        """, (demo_uid, today.strftime("%Y-%m-%d")))

        cur.execute("""
            INSERT INTO notifications (user_id, title, body, icon, tone, is_read, created_at)
            VALUES (?, 'Selamat Datang di KINETIX 3D!', 'Cek Marketplace di tab Toko untuk minuman kalsium tulang & suplemen olahraga, pakai voucher FIT10!', 'sparkles', 'toska', 0, ?)
        """, (demo_uid, now_iso))

    # Seed akun Developer
    cur.execute("SELECT COUNT(*) FROM users WHERE username = 'developer'")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO users (
                username, email, password_hash, role, onboarding_done, name, weight_kg, height_cm,
                age, gender, activity_level, goal, daily_water_target, daily_cal_target, created_at
            )
            VALUES (?, ?, ?, 'developer', 1, ?, 72.0, 175.0, 24, 'male', 1.55, 'maintain', 2500, 650, ?)
        """, (
            "developer", "dev@kinetix.id", generate_password_hash("dev12345"),
            "Zacky Developer", now_iso
        ))
        dev_uid = cur.lastrowid
        cur.execute("""
            INSERT INTO notifications (user_id, title, body, icon, tone, is_read, created_at)
            VALUES (?, 'Seller Center & Dev Studio Aktif', 'Kelola produk marketplace, update status pengiriman pesanan, dan balas chat CS dari tab Dev.', 'shield', 'ocean', 0, ?)
        """, (dev_uid, now_iso))

    # Seed Katalog Marketplace Minuman Kalsium & Suplemen
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        seed_products = [
            ("CalciPro Max Hydration 500ml", "Minuman Kalsium", 28000, 45, 500, "Tinggi Kalsium 600mg + Vitamin D3 & Magnesium untuk kekuatan tulang saat angkat beban.", "Top Kalsium"),
            ("OsteoFit Calcium + Collagen", "Minuman Kalsium", 35000, 30, 350, "Menjaga kepadatan tulang, elastisitas sendi lutut/bahu, dan pemulihan pasca latihan.", "Bone & Joint"),
            ("HydroIon Electrolyte Toska", "Minuman Isotonik", 22000, 60, 500, "Mengganti cairan & elektrolit tubuh yang hilang saat HIIT maupun kardio intensif.", "Zero Sugar"),
            ("PureWhey Isolate Vanilla", "Suplemen Protein", 185000, 20, 300, "27g Protein murni per sajian + BCAA untuk pertumbuhan massa otot tanpa lemak.", "High Protein"),
            ("NitroCharge Pre-Workout", "Energy Drink", 145000, 25, 250, "Meningkatkan fokus, stamina, dan tenaga ledak 20 menit sebelum sesi workout.", "Energy Boost"),
        ]
        for p_name, cat, price, stock, vol_ml, benefit, badge in seed_products:
            img, orig_p, sold, rat = DEFAULT_PRODUCT_META[p_name]
            cur.execute("""
                INSERT INTO products (name, category, price, original_price, stock, volume_ml, benefit, badge, image_url, sold_count, rating, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (p_name, cat, price, orig_p, stock, vol_ml, benefit, badge, img, sold, rat, now_iso))
    else:
        # Lengkapi foto, harga coret, terjual & rating untuk produk lama yang belum terisi
        for p_name, (img, orig_p, sold, rat) in DEFAULT_PRODUCT_META.items():
            cur.execute("""
                UPDATE products
                SET image_url = CASE WHEN image_url = '' THEN ? ELSE image_url END,
                    original_price = CASE WHEN original_price = 0 THEN ? ELSE original_price END,
                    sold_count = CASE WHEN sold_count = 0 THEN ? ELSE sold_count END,
                    rating = CASE WHEN rating = 4.8 THEN ? ELSE rating END
                WHERE name = ?
            """, (img, orig_p, sold, rat, p_name))

    # Seed 1 ulasan awal jika masih kosong
    cur.execute("SELECT COUNT(*) FROM product_reviews")
    if cur.fetchone()[0] == 0:
        first_u = cur.execute("SELECT id FROM users WHERE role = 'user' LIMIT 1").fetchone()
        first_p = cur.execute("SELECT id FROM products ORDER BY id ASC LIMIT 1").fetchone()
        if first_u and first_p:
            cur.execute("""
                INSERT INTO product_reviews (product_id, user_id, rating, comment, created_at)
                VALUES (?, ?, 5, 'Rasanya segar, cepat pulihkan tenaga setelah sesi leg day dan tidak bikin eneg!', ?)
            """, (first_p["id"], first_u["id"], now_iso))

    conn.commit()
    conn.close()