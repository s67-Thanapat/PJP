import sqlite3
import os
import pandas as pd
import json
import datetime
import re
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

DB_FILE = "stock.db"

# ===========================================================
# 🔥 สร้างตาราง + ตรวจสอบคอลัมน์
# ===========================================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    # ---------- ตารางประวัติสินค้า ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT,
            name TEXT,
            qty_added INTEGER,
            cost REAL,
            price REAL,
            timestamp TEXT
        )
    """)


    # ---------- ตารางสินค้า ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            barcode TEXT PRIMARY KEY,
            name TEXT,
            price REAL,
            cost REAL,
            qty INTEGER,
            main_category TEXT,
            sub_category TEXT
        )
    """)

    # ตรวจสอบคอลัมน์
    cur.execute("PRAGMA table_info(products)")
    cols = [c[1] for c in cur.fetchall()]

    if "main_category" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN main_category TEXT")
    if "sub_category" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN sub_category TEXT")
    # ✨ เพิ่ม created_at ถ้ายังไม่มี
    if "created_at" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN created_at TEXT DEFAULT ''")


    # ---------- ตารางหมวดหลัก ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY
        )
    """)

    # ---------- ตารางหมวดย่อย (ใหม่) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sub_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_category TEXT,
            name TEXT,
            UNIQUE(parent_category, name)
        )
    """)



    # ---------- ตารางบาร์โค้ดเทียบเท่า ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS barcode_alias (
            real_code TEXT,
            alias_code TEXT PRIMARY KEY
        )
    """)

    # ---------- ตารางการขาย ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_no TEXT,
            subtotal REAL,
            cash REAL,
            change REAL,
            items TEXT,
            datetime TEXT
        )
    """)

    conn = sqlite3.connect("stock.db")
    c = conn.cursor()

    # ⭐ สร้าง alias_map ถ้ายังไม่มี
    c.execute("""
        CREATE TABLE IF NOT EXISTS alias_map (
            real TEXT NOT NULL,
            alias TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()
    conn.close()

def normalize_header(name: str):
    """
    แปลงชื่อหัวตารางให้เป็นรูปแบบกลาง เช่น
    - ตัดช่องว่าง
    - lower()
    - ตัดคำพิเศษ
    - เหลือเฉพาะตัวอักษร a-z0-9
    """
    if not isinstance(name, str):
        return ""

    name = name.strip().lower()
    name = re.sub(r"[\s\-_]+", "", name)       # ลบ space, - , _
    name = re.sub(r"[^a-z0-9ก-๙]", "", name)   # เหลือเฉพาะตัวอักษรสำคัญ
    return name


# ===========================================================
# 🔥 ฟังก์ชันจัดการหมวดหมู่
# ===========================================================
def add_category(name):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()


def get_categories():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]



# ===========================================================
# 🔥 เพิ่มสินค้า
# ===========================================================
def add_product(barcode, name, price, cost, qty, main_cat="", sub_cat=""):
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ใช้คำสั่ง SQL แบบเดิมของคุณ (ON CONFLICT DO UPDATE) ซึ่งดีอยู่แล้ว
        cur.execute("""
            INSERT INTO products (
                barcode, name, price, cost, qty,
                main_category, sub_category, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(barcode) DO UPDATE SET
                name = excluded.name,
                price = excluded.price,
                cost = excluded.cost,
                qty = products.qty + excluded.qty,
                main_category = excluded.main_category,
                sub_category = excluded.sub_category,
                created_at = CASE
                    WHEN products.created_at IS NULL
                         OR products.created_at = ''
                    THEN excluded.created_at
                    ELSE products.created_at
                END
        """, (barcode, name, price, cost, qty, main_cat, sub_cat, now))

        conn.commit()
        conn.close()
        
        return True  # ✅ เพิ่มบรรทัดนี้: บอกโปรแกรมว่า "บันทึกสำเร็จ"

    except Exception as e:
        print(f"Error adding product: {e}")
        try:
            conn.close()
        except:
            pass
        return False # ❌ ถ้ามี Error จริงๆ ให้ส่ง False กลับไป




# ===========================================================
# 🔍 ดึงสินค้า
# ===========================================================
def get_product(barcode):
    from db import get_alias

    real = get_alias(barcode)
    if real:
        barcode = real

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            barcode,
            name,
            price,
            cost,
            qty,
            main_category,
            sub_category,
            created_at
        FROM products
        WHERE barcode=?
    """, (barcode,))

    row = cur.fetchone()
    conn.close()
    return row


# ===========================================================
# 🔥 อัปเดตข้อมูลสินค้า
# ===========================================================
def update_product_info(barcode, name, price, cost, main_cat=None, sub_cat=None):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if main_cat is None and sub_cat is None:
        cur.execute("""
            UPDATE products
            SET name=?, price=?, cost=?
            WHERE barcode=?
        """, (name, price, cost, barcode))
    else:
        cur.execute("""
            UPDATE products
            SET name=?, price=?, cost=?, main_category=?, sub_category=?
            WHERE barcode=?
        """, (name, price, cost, main_cat, sub_cat, barcode))

    conn.commit()
    conn.close()



# ===========================================================
# 🔥 อัปเดตสต็อก
# ===========================================================
def update_stock(barcode, qty, absolute=False):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if absolute:
        cur.execute("UPDATE products SET qty=? WHERE barcode=?", (qty, barcode))
    else:
        cur.execute("UPDATE products SET qty = qty - ? WHERE barcode=?", (qty, barcode))

    conn.commit()
    conn.close()



# ===========================================================
# 📋 ดึงสินค้าทั้งหมด
# ===========================================================
def list_products():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            barcode,
            name,
            price,
            cost,
            qty,
            main_category,
            sub_category,
            created_at
        FROM products
    """)
    rows = cur.fetchall()
    conn.close()
    return rows




# ===========================================================
# 🔥 เพิ่มหมวดย่อย (ใหม่)
# ===========================================================
def add_subcategory(main, sub):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO sub_categories (parent_category, name)
        VALUES (?, ?)
    """, (main, sub))
    conn.commit()
    conn.close()



def get_subcategories(main):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT name FROM sub_categories
        WHERE parent_category=?
        ORDER BY name
    """, (main,))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]




# ===========================================================
# 💾 บันทึกการขาย
# ===========================================================
def save_sale(receipt_no, subtotal, cash, change, items):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO sales (receipt_no, subtotal, cash, change, items, datetime)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        receipt_no,
        subtotal,
        cash,
        change,
        json.dumps(items, ensure_ascii=False),
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()



# ===========================================================
# 🔄 Barcode alias
# ===========================================================
def add_alias(real_code, alias_code):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO barcode_alias(real_code, alias_code)
        VALUES (?, ?)
    """, (real_code, alias_code))
    conn.commit()
    conn.close()


def delete_alias(alias_code):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # ลบจากจริง: barcode_alias
    cur.execute("DELETE FROM barcode_alias WHERE alias_code=?", (alias_code,))

    # ลบสินค้าใน stock ที่บันทึกด้วย alias นี้
    cur.execute("DELETE FROM products WHERE barcode=?", (alias_code,))

    conn.commit()
    conn.close()





def get_all_alias():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT real_code, alias_code FROM barcode_alias")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_alias(code):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT real_code FROM barcode_alias WHERE alias_code=?", (code,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None



# ===========================================================
# 📤 Export Excel
# ===========================================================
def export_to_excel(filepath):
    data = list_products()

    # 1️⃣ ใช้ชื่อ column ตรงกับ DB ก่อน
    df = pd.DataFrame(data, columns=[
        "barcode",
        "name",
        "price",
        "cost",
        "qty",
        "main_category",
        "sub_category",
        "created_at"
    ])

    # 2️⃣ rename เป็นชื่อสวยสำหรับ Excel
    df.rename(columns={
        "barcode": "Barcode",
        "name": "Name",
        "price": "Price",
        "cost": "Cost",
        "qty": "Qty",
        "main_category": "MainCategory",
        "sub_category": "SubCategory",
        "created_at": "CreatedAt"
    }, inplace=True)

    df.to_excel(filepath, index=False)




# ===========================================================
# 📥 Import Excel
# ===========================================================
def import_from_excel(file_path):
    import pandas as pd
    import sqlite3
    import re
    import datetime

    df = pd.read_excel(file_path, dtype=str)

    # =======================================================
    # normalize header
    # =======================================================
    def norm(x):
        if not isinstance(x, str):
            return ""
        x = x.strip().lower()
        x = re.sub(r"[\s\-_]+", "", x)
        x = re.sub(r"[^a-z0-9ก-๙]", "", x)
        return x

    HEADER_MAP = {
        "barcode": "barcode",
        "บาร์โค้ด": "barcode",
        "productbarcode": "barcode",
        "รหัสสินค้า": "barcode",

        "name": "name",
        "ชื่อสินค้า": "name",

        "price": "price",
        "ราคาขาย": "price",

        "cost": "cost",
        "ราคาทุน": "cost",

        "qty": "qty",
        "จำนวน": "qty",
        "จำนวนคงเหลือ": "qty",

        "category": "category",
        "หมวดหลัก": "category",

        "subcategory": "sub_category",
        "sub_category": "sub_category",
        "หมวดย่อย": "sub_category",

        # เวลา
        "createdat": "created_at",
        "datetime": "created_at",
        "timestamp": "created_at",
        "วันที่": "created_at",
        "เวลา": "created_at",
    }

    new_cols = {}
    for col in df.columns:
        key = norm(col)
        if key in HEADER_MAP:
            new_cols[col] = HEADER_MAP[key]

    df.rename(columns=new_cols, inplace=True)

    if "sub_category" not in df.columns:
        df["sub_category"] = ""

    required = ["barcode", "name", "price", "cost", "qty", "category", "sub_category"]
    for r in required:
        if r not in df.columns:
            raise Exception(f"Column '{r}' not found in imported file")

    conn = sqlite3.connect("stock.db")
    cur = conn.cursor()

    # =======================================================
    # โหลดข้อมูลเดิม
    # =======================================================
    cur.execute("SELECT barcode, name FROM products")
    rows = cur.fetchall()
    existing_barcodes = {r[0].strip() for r in rows}
    existing_names = {r[1].strip() for r in rows}

    skipped_rows = []

    # =======================================================
    # loop import
    # =======================================================
    for idx, row in df.iterrows():
        bc = str(row["barcode"]).strip()
        name = str(row["name"]).strip()
        price = float(row["price"])
        cost = float(row["cost"])
        qty = int(row["qty"])

        cat = str(row["category"]).strip() if pd.notna(row["category"]) else "ไม่มีหมวดหมู่"
        sub = str(row["sub_category"]).strip() if pd.notna(row["sub_category"]) else ""

        raw_time = row.get("created_at", None)

        # ✅ ถ้าไม่มีเวลา → ใส่ NULL (ไม่ใส่เวลา)
        if raw_time is None or pd.isna(raw_time) or str(raw_time).strip() == "":
            created_at = None
        else:
            try:
                created_at = pd.to_datetime(raw_time).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                created_at = None


        # กันซ้ำ
        if bc in existing_barcodes or name in existing_names:
            skipped_rows.append((idx + 2, bc, name))
            continue

        # insert product
        cur.execute("""
            INSERT INTO products
            (barcode, name, price, cost, qty, main_category, sub_category, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (bc, name, price, cost, qty, cat, sub, created_at))

        # insert history
        cur.execute("""
            INSERT INTO product_history
            (barcode, name, qty_added, cost, price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (bc, name, qty, cost, price, created_at))

        # หมวด
        cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
        if sub:
            cur.execute("""
                INSERT OR IGNORE INTO sub_categories (parent_category, name)
                VALUES (?, ?)
            """, (cat, sub))

        existing_barcodes.add(bc)
        existing_names.add(name)

    conn.commit()
    conn.close()

    if skipped_rows:
        msg = "รายการต่อไปนี้ไม่ถูกเพิ่มเพราะซ้ำ:\n\n"
        for r in skipped_rows:
            msg += f"- แถว {r[0]} | Barcode: {r[1]} | Name: {r[2]}\n"
        raise Exception(msg)


def create_history_table():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT,
            qty_added INTEGER,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()



def get_barcode_alias_map():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT real_code, alias_code FROM barcode_alias")
    rows = cur.fetchall()
    conn.close()

    alias_map = {}
    for real, alias in rows:
        alias_map[alias] = real

    return alias_map

# ===========================================================
# 📅 รายการขายตามวันที่
# ===========================================================
def list_sales_by_date(date_str):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, receipt_no, subtotal, cash, change, datetime
        FROM sales
        WHERE datetime LIKE ?
        ORDER BY datetime DESC
    """, (f"{date_str}%",))

    rows = cur.fetchall()
    conn.close()
    return rows


# ===========================================================
# 📦 ดึงรายการสินค้าในใบเสร็จ
# ===========================================================
def get_sale_items(receipt_no):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT items FROM sales WHERE receipt_no=?", (receipt_no,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return []

    try:
        return json.loads(row[0])
    except:
        return []


# ===========================================================
# 📄 รายการขายทั้งหมด
# ===========================================================
def list_all_sales():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, receipt_no, subtotal, cash, change, datetime
        FROM sales
        ORDER BY datetime DESC
    """)

    rows = cur.fetchall()
    conn.close()
    return rows
def get_all_product_names():
    import sqlite3
    conn = sqlite3.connect("stock.db")
    cur = conn.cursor()

    cur.execute("SELECT name FROM products")
    rows = cur.fetchall()

    conn.close()

    return [r[0] for r in rows]

def add_history(barcode, name, qty_added, cost, price, timestamp=None):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO product_history
        (barcode, name, qty_added, cost, price, timestamp)
        VALUES (
            ?, ?, ?, ?, ?,
            COALESCE(?, datetime('now','localtime'))
        )
    """, (barcode, name, qty_added, cost, price, timestamp))

    conn.commit()
    conn.close()




def get_history_by_barcode(barcode):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT timestamp, qty_added, cost, price, name
        FROM product_history
        WHERE barcode = ?
        ORDER BY timestamp DESC
    """, (barcode,))

    rows = cur.fetchall()
    conn.close()
    return rows

def save_all_products(self, suppress_popup=False):
    from db import add_history  # ← ใช้อันนี้!!

    # เก็บ qty เดิมของทุกสินค้า
    old_qty_map = {p["barcode"]: p["qty"] for p in self.all_products}

    for r in range(self.table.rowCount()):
        item0 = self.table.item(r, 0)
        if not item0 or item0.data(Qt.UserRole) in ("header", "sub_header"):
            continue

        try:
            bc    = self.table.item(r, 5).text().strip()
            name  = self.table.item(r, 1).text().strip()
            price = float(self.table.item(r, 2).text())
            cost  = float(self.table.item(r, 3).text())
            qty   = int(self.table.item(r, 4).text())
        except Exception:
            continue

        # update base product info
        update_product_info(bc, name, price, cost)

        update_stock(bc, qty, absolute=True)

        # ===== บันทึกประวัติ =====
        old_qty = old_qty_map.get(bc, None)

        if old_qty is not None:
            qty_added = qty - old_qty
            if qty_added != 0:
                add_history(bc, name, qty_added, cost, price)

    self.dirty = False
    self.load_data()

    if not suppress_popup:
        QMessageBox.information(self, "สำเร็จ", "บันทึกข้อมูลทั้งหมดเรียบร้อย!")

    # refresh history tab ถ้ามี
    try:
        self.parent().history_tab.refresh_now()
    except:
        pass
