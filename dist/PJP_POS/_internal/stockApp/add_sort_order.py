import sqlite3

conn = sqlite3.connect("stock.db")
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE products ADD COLUMN sort_order INTEGER DEFAULT 0;")
    print("เพิ่มคอลัมน์ sort_order สำเร็จ!")
except Exception as e:
    print("Error:", e)

conn.commit()
conn.close()
