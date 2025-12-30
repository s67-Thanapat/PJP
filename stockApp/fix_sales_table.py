import sqlite3

conn = sqlite3.connect("stock.db")
cur = conn.cursor()

print("📌 Checking sales table...")

cur.execute("PRAGMA table_info(sales);")
cols = cur.fetchall()
col_names = [c[1] for c in cols]

print("Columns now:", col_names)

# ถ้ามี datetime อยู่แล้ว → ไม่ต้องทำอะไร
if "datetime" in col_names:
    print("✔ Column 'datetime' already exists. Nothing to fix.")
    conn.close()
    exit()

# ต้อง migrate จาก date → datetime
print("🔧 Migrating: rename 'date' → 'datetime' ...")

cur.execute("ALTER TABLE sales RENAME TO sales_old;")

cur.execute("""
    CREATE TABLE sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_no TEXT,
        subtotal REAL,
        cash REAL,
        change REAL,
        items TEXT,
        datetime TEXT
    );
""")

# คัดลอกข้อมูลเดิม (ใช้ date → datetime)
cur.execute("""
    INSERT INTO sales (id, receipt_no, subtotal, cash, change, items, datetime)
    SELECT id, receipt_no, subtotal, cash, change, '' AS items, date
    FROM sales_old;
""")

cur.execute("DROP TABLE sales_old;")

conn.commit()
conn.close()

print("✔ Migration completed! Column 'datetime' is now added.")
