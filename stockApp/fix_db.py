import sqlite3

DB_FILE = "stock.db"

def fix_subcategories():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    print("🔧 ลบตาราง sub_categories เดิม...")
    cur.execute("DROP TABLE IF EXISTS sub_categories")

    print("🔧 สร้างตารางใหม่แบบ UNIQUE สำหรับกันซ้ำ...")
    cur.execute("""
        CREATE TABLE sub_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_category TEXT,
            name TEXT,
            UNIQUE(parent_category, name)
        )
    """)

    print("🧹 VACUUM เพื่อล้างข้อมูลเก่า...")
    cur.execute("VACUUM")

    conn.commit()
    conn.close()

    print("🎉 แก้หมวดย่อยซ้ำสำเร็จ! พร้อมใช้งานแล้ว")

if __name__ == "__main__":
    fix_subcategories()
