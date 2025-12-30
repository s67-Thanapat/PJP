import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView, QDateEdit, QDialog
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QDate, QLocale

from db import list_sales_by_date, get_sale_items, list_all_sales
from receipt import print_receipt
LAST_PATH_FILE = "last_path.json"



# ==========================================================
# 🔥 Popup ใบเสร็จแบบเดียวกับ PDF
# ==========================================================
class ReceiptDialog(QDialog):
    def __init__(self, items, meta, parent=None):
        super().__init__(parent)

        self.items = items
        self.meta = meta
        self.parent = parent

        self.setWindowTitle("ใบเสร็จรับเงิน")
        self.setFixedWidth(480)
        self.setMinimumHeight(600)  # ป้องกันเล็กเกิน

        # ================================
        #  เลย์เอาต์ใหญ่สุด (แนวตั้ง)
        # ================================
        main = QVBoxLayout()
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(10)

        # ================================
        #  Scroll Area
        # ================================
        from PySide6.QtWidgets import QScrollArea, QWidget
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setAlignment(Qt.AlignTop)

        # ================================
        #      เนื้อหาใบเสร็จ
        # ================================
        lbl_shop = QLabel(meta["shop_name"])
        lbl_shop.setFont(QFont("Segoe UI", 18, QFont.Bold))
        lbl_shop.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(lbl_shop)

        lbl_addr = QLabel(meta["shop_addr"])
        lbl_addr.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(lbl_addr)

        lbl_tax = QLabel(f"เลขประจำตัวผู้เสียภาษี: {meta['tax_id']}")
        lbl_tax.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(lbl_tax)

        content_layout.addWidget(QLabel(""))

        content_layout.addWidget(QLabel(f"วันที่: {meta['dt']}"))
        content_layout.addWidget(QLabel(f"เลขที่ใบเสร็จ: {meta['receipt_no']}"))
        content_layout.addWidget(QLabel("--------------------------------------------------"))

        for it in items:
            line = QLabel(f"{it['name']}\n   x{it['qty']}   {it['price']:.2f} = {it['total']:.2f} บาท")
            line.setStyleSheet("font-size:15px;")
            content_layout.addWidget(line)

        content_layout.addWidget(QLabel("--------------------------------------------------"))

        def right(text):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignRight)
            lbl.setStyleSheet("font-size:16px;")
            return lbl

        content_layout.addWidget(right(f"รวมเป็นเงิน: {meta['subtotal']:.2f} บาท"))
        content_layout.addWidget(right(f"รับเงิน: {meta['cash']:.2f} บาท"))
        content_layout.addWidget(right(f"เงินทอน: {meta['change']:.2f} บาท"))

        content.setLayout(content_layout)
        scroll.setWidget(content)
        main.addWidget(scroll)

        # ================================
        #     ปุ่มลอยด้านล่าง (ไม่เลื่อน)
        # ================================
        btn_row = QHBoxLayout()
        btn_row.setSpacing(20)

        btn_print = QPushButton("🖨 พิมพ์ใบเสร็จ")
        btn_print.setStyleSheet("""
            QPushButton {
                background:#2196F3;color:white;
                padding:10px;font-size:16px;border-radius:10px;
            }
        """)
        btn_print.clicked.connect(self.print_receipt)
        btn_row.addWidget(btn_print)

        btn_ok = QPushButton("ปิด")
        btn_ok.setStyleSheet("""
            QPushButton {
                background:#4CAF50;color:white;
                padding:10px;font-size:16px;border-radius:10px;
            }
        """)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        main.addLayout(btn_row)

        self.setLayout(main)

    def print_receipt(self):
        try:
            print_receipt(self.items, self.meta)
            QMessageBox.information(self, "สำเร็จ", "พิมพ์ใบเสร็จสำเร็จ!")
        except Exception as e:
            QMessageBox.warning(self, "ผิดพลาด", f"ไม่สามารถพิมพ์ใบเสร็จได้:\n{e}")



# ==========================================================
#                      RecordTab
# ==========================================================
class RecordTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.LAST_PATH_FILE = "last_record_path.json"
        self.build_ui()
        self.load_today()

    def build_ui(self):
        layout = QVBoxLayout()

        lbl_title = QLabel("📜 ประวัติการขาย")
        lbl_title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        layout.addWidget(lbl_title)

        # ---------------- ช่องเลือกวันที่ ----------------
        search_row = QHBoxLayout()

        self.date_picker = QDateEdit()
        self.date_picker.setCalendarPopup(True)

        # ภาษาไทย + เดือนไทย + ใช้เลขอารบิก (default)
        thai_locale = QLocale(QLocale.Thai, QLocale.Thailand)
        self.date_picker.setLocale(thai_locale)

        calendar = self.date_picker.calendarWidget()
        calendar.setLocale(thai_locale)
        from PySide6.QtGui import QTextCharFormat, QColor

# ------------- ไฮไลต์วันปัจจุบันด้วย QCalendar Format -------------
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#E3F2FD"))     # พื้นหลังฟ้าอ่อน
        fmt.setForeground(QColor("black"))       # ตัวอักษรดำ
        fmt.setFontWeight(QFont.Bold)            # ตัวหนา
        fmt.setUnderlineStyle(QTextCharFormat.SingleUnderline)  # เส้นใต้บางๆ

        calendar.setDateTextFormat(QDate.currentDate(), fmt)

        # ---------------- ไฮไลต์วันปัจจุบัน (ทำแบบ manual) ----------------
        def highlight_today():
            cal = self.date_picker.calendarWidget()
            view = cal.findChild(QWidget, "qt_calendar_calendarview")
            if view:
                # loop หา cell วันทั้งหมด
                for child in view.findChildren(QWidget):
                    if hasattr(child, "date"):  # cell ที่มี property date()
                        d = child.date()
                        if d == QDate.currentDate():
                            child.setStyleSheet("""
                                background-color: #E3F2FD;
                                border: 2px solid #2196F3;
                                border-radius: 4px;
                                color: black;
                                font-weight: bold;
                            """)

        # เรียกเมื่อเปิด calendar
        calendar.clicked.connect(lambda _: highlight_today())
        calendar.showEvent = lambda e: (highlight_today(), QWidget.showEvent(calendar, e))


        # แสดงแบบไทย
        self.date_picker.setDisplayFormat("d MMMM yyyy")

        # -------------------- stylesheet ปฏิทิน --------------------
        calendar.setStyleSheet("""
            /* ซ่อนวันนอกเดือน */
            QCalendarWidget QAbstractItemView:item[qt_calendar_state="OtherMonth"] {
                color: transparent;
                background: transparent;
            }

            /* เสาร์สีแดง */
            QCalendarWidget QAbstractItemView:item:nth-child(7) {
                color: red;
            }

            /* อาทิตย์สีแดง */
            QCalendarWidget QAbstractItemView:item:nth-child(1) {
                color: red;
            }

            /* วันที่เลือก */
            QCalendarWidget QAbstractItemView:item:selected {
                background-color: #FF5722;
                color: white;
            }

            /* ไฮไลต์วันปัจจุบันแบบแท้จริง */
            QCalendarWidget QWidget#qt_calendar_calendarview::item:today {
                background-color: #E3F2FD;
                border: 1px solid #2196F3;
                border-radius: 4px;
                color: black;
                font-weight: bold;
            }
        """)


        self.date_picker.setDate(QDate.currentDate())
        self.date_picker.dateChanged.connect(self.load_by_date)

        btn_all = QPushButton("📄 ทั้งหมด")
        btn_all.clicked.connect(self.load_all)

        # ---------------- ช่องเลือกวันที่ + ปุ่มต่างๆ ----------------
        search_row = QHBoxLayout()

        # ---------------- ปุ่ม ทั้งหมด (ปรับให้เล็กลง) ----------------
        btn_all = QPushButton("📄 ทั้งหมด")
        btn_all.setFixedHeight(36)
        btn_all.setStyleSheet("""
            QPushButton {
                background:#4CAF50;
                color:white;
                padding:6px 12px;
                font-size:14px;
                border-radius:8px;
            }
        """)
        btn_all.clicked.connect(self.load_all)

        # ---------------- ปุ่ม Import Excel ----------------
        btn_import = QPushButton("⬇ Import Excel")
        btn_import.setFixedHeight(36)
        btn_import.setStyleSheet("""
            QPushButton {
                background:#4CAF50;
                color:white;
                padding:6px 12px;
                font-size:14px;
                border-radius:8px;
            }
        """)
        btn_import.clicked.connect(self.import_excel)

        # ---------------- ปุ่ม Export Excel ----------------
        btn_export = QPushButton("⬆ Export Excel")
        btn_export.setFixedHeight(36)
        btn_export.setStyleSheet("""
            QPushButton {
                background:#4CAF50;
                color:white;
                padding:6px 12px;
                font-size:14px;
                border-radius:8px;
            }
        """)
        btn_export.clicked.connect(self.export_excel)

        

        # ใส่เข้ารูปแบบใหม่
        search_row.addWidget(self.date_picker)
        search_row.addWidget(btn_all)
        search_row.addWidget(btn_import)
        search_row.addWidget(btn_export)
        

        layout.addLayout(search_row)
        

        # ---------------- ตาราง ----------------
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "วันที่", "เลขที่ใบเสร็จ", "ยอดรวม", "รับเงิน", "เงินทอน"
        ])

        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        for i in range(6):
            self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.table.cellDoubleClicked.connect(self.show_items_popup)

        layout.addWidget(self.table)
        self.setLayout(layout)

    def load_today(self):
        today = QDate.currentDate()
        self.date_picker.setDate(today)
        self.load_by_date()

    def load_by_date(self):
        date_str = self.date_picker.date().toString("yyyy-MM-dd")
        data = list_sales_by_date(date_str)
        self.load_table(data)

    def load_all(self):
        data = list_all_sales()
        self.load_table(data)

    def load_table(self, data):
        self.table.setRowCount(len(data))

        for r, row in enumerate(data):
            reordered = [
                row[0],
                row[5],
                row[1],
                row[2],
                row[3],
                row[4],
            ]

            for c, val in enumerate(reordered):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, item)

    def show_items_popup(self, row, col):
        receipt_no = self.table.item(row, 2).text()
        items = get_sale_items(receipt_no)

        if not items:
            QMessageBox.information(self, "ไม่มีข้อมูล", "ไม่พบสินค้าของใบเสร็จนี้")
            return

        meta = {
            "shop_name": self.app.SHOP_NAME,
            "shop_addr": self.app.SHOP_ADDR,
            "tax_id": self.app.SHOP_TAXID,
            "cashier": self.app.CASHIER_NAME,
            "receipt_no": receipt_no,
            "dt": self.table.item(row, 1).text(),
            "subtotal": float(self.table.item(row, 3).text()),
            "cash": float(self.table.item(row, 4).text()),
            "change": float(self.table.item(row, 5).text()),
        }

        win = ReceiptDialog(items, meta, parent=self)
        win.exec()
        
    def refresh(self):
        # โหลดข้อมูลใหม่ตามวันที่ที่เลือก
        self.load_by_date()

        # ==========================================================
    #   ฟังก์ชัน Export Excel
    # ==========================================================
    def export_excel(self):
        from PySide6.QtWidgets import QFileDialog
        import pandas as pd

        last_path = self.get_last_path()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "บันทึกไฟล์ Excel",
            f"{last_path}/sales.xlsx",
            "Excel Files (*.xlsx)"
        )

        if not path:
            return

        # ⭐⭐ เซฟก่อนส่งออก
        self.save_all_sales()

        # บันทึก path
        self.save_last_path(path)

        # ดึงข้อมูลจากตาราง
        rows = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                row.append(self.table.item(r, c).text())
            rows.append(row)

        df = pd.DataFrame(rows, columns=[
            "ID", "วันที่", "เลขที่ใบเสร็จ", "ยอดรวม", "รับเงิน", "เงินทอน"
        ])

        df.to_excel(path, index=False)
        QMessageBox.information(self, "สำเร็จ", "บันทึกไฟล์ Excel แล้ว!")



    # ==========================================================
    #   ฟังก์ชัน Import Excel
    # ==========================================================
    def import_excel(self):
        from PySide6.QtWidgets import QFileDialog
        import pandas as pd

        last_path = self.get_last_path()

        path, _ = QFileDialog.getOpenFileName(
            self,
            "เปิดไฟล์ Excel",
            last_path,
            "Excel Files (*.xlsx *.xls)"
        )

        if not path:
            return

        # บันทึก path ล่าสุด
        self.save_last_path(path)

        try:
            df = pd.read_excel(path)

            self.table.setRowCount(0)
            self.table.setRowCount(len(df))

            for r in range(len(df)):
                for c in range(6):
                    item = QTableWidgetItem(str(df.iat[r, c]))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(r, c, item)

            # ⭐⭐ เซฟอัตโนมัติ
            self.save_all_sales()

            # ⭐⭐ รีเฟรชหน้า
            self.refresh()

            QMessageBox.information(self, "นำเข้าข้อมูล", "นำเข้าจาก Excel สำเร็จ!")

        except Exception as e:
            QMessageBox.warning(self, "ผิดพลาด", f"ไม่สามารถนำเข้าไฟล์ได้:\n{e}")


    def get_last_path(self):
        import os, json
        if not os.path.exists(self.LAST_PATH_FILE):
            return ""  # ถ้าไม่มีไฟล์ ให้ default = โฟลเดอร์โปรเจค

        try:
            with open(self.LAST_PATH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("path", "")
        except:
            return ""

    def save_last_path(self, path):
        import json
        from pathlib import Path

        folder = str(Path(path).parent)  # เก็บเฉพาะโฟลเดอร์
        with open(self.LAST_PATH_FILE, "w", encoding="utf-8") as f:
            json.dump({"path": folder}, f, ensure_ascii=False, indent=2)

    def save_all_sales(self):
        import sqlite3
        conn = sqlite3.connect("stock.db")
        cur = conn.cursor()

        # ลบของเดิมทั้งหมด (เพื่อ sync Excel → DB)
        cur.execute("DELETE FROM sales")

        for r in range(self.table.rowCount()):
            sale_id     = self.table.item(r, 0).text()
            dt          = self.table.item(r, 1).text()
            receipt_no  = self.table.item(r, 2).text()
            subtotal    = float(self.table.item(r, 3).text())
            cash        = float(self.table.item(r, 4).text())
            change      = float(self.table.item(r, 5).text())

            cur.execute("""
                INSERT INTO sales(id, datetime, receipt_no, subtotal, cash, change)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sale_id, dt, receipt_no, subtotal, cash, change))

        conn.commit()
        conn.close()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()        # ⭐ โหลดข้อมูลใหม่ทุกครั้งที่เข้าหน้านี้
