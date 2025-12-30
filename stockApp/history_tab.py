import sqlite3
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QPushButton
)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtCore import QDate
from PySide6.QtGui import QTextCharFormat
from PySide6 import QtGui
from PySide6.QtGui import QPixmap, QPainter, QPolygon, QColor
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCalendarWidget

from PySide6.QtWidgets import QDateEdit
from PySide6.QtCore import QLocale
from datetime import datetime
from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
            QPushButton, QHeaderView, QMessageBox, QComboBox
        )
from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter


DB_FILE = "stock.db"

thai_months = {
    "01": "มกราคม",
    "02": "กุมภาพันธ์",
    "03": "มีนาคม",
    "04": "เมษายน",
    "05": "พฤษภาคม",
    "06": "มิถุนายน",
    "07": "กรกฎาคม",
    "08": "สิงหาคม",
    "09": "กันยายน",
    "10": "ตุลาคม",
    "11": "พฤศจิกายน",
    "12": "ธันวาคม",
}

def make_arrow(direction="down", size=12, color=QColor(30, 30, 30)):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)

        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(color)

        w = size
        h = size

        if direction == "down":      # ▼
            poly = QPolygon([
                QPoint(w*0.25, h*0.35),
                QPoint(w*0.75, h*0.35),
                QPoint(w*0.50, h*0.70),
            ])

        elif direction == "up":     # ▲
            poly = QPolygon([
                QPoint(w*0.25, h*0.65),
                QPoint(w*0.75, h*0.65),
                QPoint(w*0.50, h*0.30),
            ])

        p.drawPolygon(poly)
        p.end()
        return pix

class CustomComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.arrow_up = "arrow_up.png"     # ▲
        self.arrow_down = "arrow_down.png" # ▼
        self.popup_open = False
        self.update_arrow(False)  # ตอนเริ่ม = ปิด → ให้แสดง ▲

    def update_arrow(self, opened):
        # ❗ ตอนปิดให้เป็น ▲ และตอนเปิดให้เป็น ▼
        current_arrow = self.arrow_down if opened else self.arrow_up

        css = f"""
        QComboBox {{
            background-color: #eeeeee;
            border: 2px solid #bbbbbb;
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 14px;
            color: #333333;
        }}

        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 28px;
            border-left: 1px solid #cccccc;
            background-color: #d3d3d3;
        }}

        QComboBox::down-arrow {{
            image: url({current_arrow});
            width: 14px;
            height: 14px;
            margin-right: 7px;
        }}
        """
        self.setStyleSheet(css)

    def showPopup(self):
        super().showPopup()
        self.popup_open = True
        self.update_arrow(True)   # เปิด → ▼

    def hidePopup(self):
        super().hidePopup()
        self.popup_open = False
        self.update_arrow(False)  # ปิด → ▲


def create_windows_arrow(size=12, color=QColor("black")):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)

        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(color)

        w = size
        poly = QPolygon([
            QPoint(w*0.25, w*0.35),
            QPoint(w*0.75, w*0.35),
            QPoint(w*0.50, w*0.70),
        ])
        p.drawPolygon(poly)
        p.end()
        return pix


class PopupCalendar(QDialog):
    def __init__(self, parent=None, default_date=None):
        super().__init__(parent)

        self.setWindowFlags(Qt.Popup)
        self.setFixedSize(320, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.cal = QCalendarWidget()

        # ❗ ตัดเลขสัปดาห์ออก
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)

        # ไทย + อาราบิก
        thai_locale = QLocale(QLocale.Thai, QLocale.Thailand)
        self.cal.setLocale(thai_locale)

        # ✅ ไฮไลต์ "วันนี้"
        today = QDate.currentDate()
        fmt = QtGui.QTextCharFormat()
        fmt.setBackground(QColor("#4CAF50"))   # สีเขียว
        fmt.setForeground(QColor("white"))
        fmt.setFontWeight(QFont.Bold)
        self.cal.setDateTextFormat(today, fmt)

        layout.addWidget(self.cal)

        if default_date:
            self.cal.setSelectedDate(default_date)

        self.cal.clicked.connect(self.accept)

        
    def selected_date(self):
            return self.cal.selectedDate()



class ThaiArabicCalendarDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = index.data()

        if text:
            thai_digits = "๐๑๒๓๔๕๖๗๘๙"
            arabic_digits = "0123456789"
            text = text.translate(str.maketrans(thai_digits, arabic_digits))

        painter.save()
        QStyledItemDelegate.paint(self, painter, option, index)
        painter.drawText(option.rect, Qt.AlignCenter, text)
        painter.restore()




class ArabicCalendarDelegate(QStyledItemDelegate):
    """บังคับ QCalendarWidget ให้แสดงตัวเลขอาราบิกแทนเลขไทย"""
    def paint(self, painter, option, index):
        text = index.data()
        if text:
            # แปลงเลขไทย → อาราบิก
            thai_digits = "๐๑๒๓๔๕๖๗๘๙"
            arabic_digits = "0123456789"
            trans = str.maketrans(thai_digits, arabic_digits)
            text = str(text).translate(trans)

        painter.save()
        QStyledItemDelegate.paint(self, painter, option, index)

        painter.drawText(option.rect, Qt.AlignCenter, text)
        painter.restore()


class ProductHistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        self._skip_edit = False
                # --- สำหรับสแกน + Enter behavior ---
        self.enter_count = 0
        self.scan_buffer = ""
        self.scan_timer = QTimer()
        self.scan_timer.setInterval(100)
        self.scan_timer.timeout.connect(self.finish_scan)


        self.category_rows = {}
        self.sub_rows = {}
        self.category_collapsed = {}
        self.sub_collapsed = {}

        self.build_ui()
        self.ensure_created_at_column()
        self.load_data()

    def on_double_click(self, row, col):
        self._skip_edit = True   # บอกว่าห้าม on_cell_edit ทำงาน
        self.show_item_history(row, col)


    # ------------------------------------------------------------
    def ensure_created_at_column(self):
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(products)")
        cols = [c[1] for c in cur.fetchall()]

        if "created_at" not in cols:
            cur.execute("ALTER TABLE products ADD COLUMN created_at TEXT DEFAULT ''")
            conn.commit()

        conn.close()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_data()      # โหลดข้อมูลทุกครั้งที่เปิดแท็บ

    def refresh_now(self):
        self.load_data()

    # ------------------------------------------------------------
    def show_item_history(self, row, col):
        item_role = self.table.item(row, 0).data(Qt.UserRole)
        if item_role != "item":
            return

        barcode = self.table.item(row, 5).text()
        name = self.table.item(row, 1).text()

        # --- ดึงข้อมูลประวัติทั้งหมด ---
        conn = sqlite3.connect("stock.db")
        cur = conn.cursor()
        cur.execute("""
            SELECT id, qty_added, timestamp
            FROM product_history
            WHERE barcode = ?
            ORDER BY timestamp DESC
        """, (barcode,))
        all_history = cur.fetchall()
        conn.close()
        

        # ถ้าไม่มีประวัติเลย แสดงกล่องข้อความแล้วจบ
        if not all_history:
            QMessageBox.information(
                self, "ประวัติสินค้า",
                f"ไม่พบประวัติการเพิ่มสินค้า\n\n{name}\nบาร์โค้ด: {barcode}"
            )
            return

        # --- สร้างปีทั้งหมดที่มีในประวัติ ---
        years = sorted(list({ts[:4] for (_, _, ts) in all_history}), reverse=True)

        # =========== WINDOW ===========
        dialog = QDialog(self)
        dialog.setWindowTitle("ประวัติสินค้า")
        dialog.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        dialog.setMinimumSize(750, 550)

        layout = QVBoxLayout(dialog)

        # Header
        header = QLabel(f"📦 ประวัติ: {name}\nบาร์โค้ด: {barcode}")
        header.setStyleSheet("font-size:16px; font-weight:bold; margin-bottom:8px;")
        layout.addWidget(header)

        # ====== YEAR SELECTOR ======
        year_select = CustomComboBox()

        year_select.addItems(years)
        year_select.setFixedWidth(150)

        # สร้างไฟล์ไอคอน ▼/▲
        make_arrow("down").save("arrow_down.png")
        make_arrow("up").save("arrow_up.png")


        year_select.setStyleSheet("""
            QComboBox {
                background-color: #eeeeee;
                border: 2px solid #bbbbbb;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 14px;
                color: #333333;
            }

            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #cccccc;
                background-color: #d3d3d3;
            }

            /* ▼ ตอนปิด */
            QComboBox::down-arrow {
                image: url(arrow_up.png);
                width: 14px;
                height: 14px;
                margin-right: 7px;
            }

            /* ▲ ตอนเปิด dropdown */
            QComboBox::down-arrow:on {
                image: url(arrow_up.png);
            }
        """)
        

        layout.addWidget(year_select)

        # ====== TABLE ======
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["ลำดับ", "จำนวน", "เวลา", "จัดการ"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)

        headerView = table.horizontalHeader()
        headerView.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        headerView.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        headerView.setSectionResizeMode(2, QHeaderView.Stretch)
        headerView.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        layout.addWidget(table)

        # =============== INTERNAL STATE ===============
        month_collapsed = {}  # "2025-11": True/False


        # =============== FUNCTION: RENDER TABLE ===============
        def render_for_year(selected_year):
            nonlocal month_collapsed

            # filter เฉพาะปี
            history = [(hid, qty, ts) for (hid, qty, ts) in all_history if ts.startswith(selected_year)]

            # จัดกลุ่มตามเดือน
            grouped = {}
            for hid, qty, ts in history:
                month_key = ts[:7]  # YYYY-MM
                grouped.setdefault(month_key, []).append((hid, qty, ts))

            # sort เดือนมาก→น้อย
            grouped = dict(sorted(grouped.items(), reverse=True))

            # reset
            table.clearContents()
            table.setRowCount(0)
            month_collapsed = {m: False for m in grouped.keys()}

            row_index = 0

            for month_key, items in grouped.items():
                # month_key = YYYY-MM
                month_name = f"{thai_months[month_key[5:7]]} {month_key[:4]}"

                # ====== HEADER MONTH ======
                table.insertRow(row_index)
                head = QTableWidgetItem(f"▾  {month_name}")
                head.setData(Qt.UserRole, ("month", month_key))
                head.setData(Qt.UserRole + 1, month_name)   # เก็บชื่อเดือนจริง

                head.setBackground(QColor("#d0d0d0"))
                head.setForeground(QColor("black"))
                head.setFont(QFont("Segoe UI", 12, QFont.Bold))
                head.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                table.setSpan(row_index, 0, 1, 4)
                table.setItem(row_index, 0, head)
                table.setRowHeight(row_index, 40)
                row_index += 1

                # ====== ROWS FOR THIS MONTH ======
                for i, (hid, qty, ts) in enumerate(items, start=1):
                    table.insertRow(row_index)

                    # ลำดับ
                    c0 = QTableWidgetItem(str(i))
                    c0.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row_index, 0, c0)

                    # จำนวน
                    c1 = QTableWidgetItem(str(qty))
                    c1.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row_index, 1, c1)

                    # เวลา
                    c2 = QTableWidgetItem(ts)
                    c2.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row_index, 2, c2)

                    # ปุ่มลบ
                    btn = QPushButton("ลบ")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color:#d9534f;
                            color:white;
                            border-radius:6px;
                            padding:5px 10px;
                        }
                        QPushButton:hover { background-color:#c9302c; }
                    """)

                    def make_delete(hid):
                        def delete():
                            if QMessageBox.question(dialog, "ยืนยัน", "ลบประวัติ?",
                                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                                conn = sqlite3.connect("stock.db")
                                c = conn.cursor()
                                c.execute("DELETE FROM product_history WHERE id=?", (hid,))
                                conn.commit()
                                conn.close()
                                dialog.close()
                                self.show_item_history(row, col)
                        return delete

                    btn.clicked.connect(make_delete(hid))
                    table.setCellWidget(row_index, 3, btn)

                    table.setRowHeight(row_index, 45)
                    row_index += 1

        # ====== CLICK TO COLLAPSE ======
        def on_click(r, c):
            item = table.item(r, 0)
            if not item:
                return

            data = item.data(Qt.UserRole)
            if not data:
                return

            typ, month_key = data

            if typ == "month":
                collapsed = month_collapsed.get(month_key, False)
                month_collapsed[month_key] = not collapsed

                # toggle icon + ใช้ชื่อเดือนจาก UserRole+1
                month_name = item.data(Qt.UserRole + 1)
                icon = "▸" if not collapsed else "▾"
                item.setText(f"{icon}  {month_name}")

                # hide/show rows ใต้เดือนนี้
                rr = r + 1
                while rr < table.rowCount():
                    it = table.item(rr, 0)
                    it_data = it.data(Qt.UserRole) if it else None
                    if it_data and it_data[0] == "month":
                        break
                    table.setRowHidden(rr, not collapsed)
                    rr += 1

        table.cellClicked.connect(on_click)

        # ===== render first time =====
        year_select.currentTextChanged.connect(lambda y: render_for_year(y))
        render_for_year(years[0])

        # ===== OK BUTTON =====
        ok = QPushButton("OK")
        ok.setStyleSheet("""
            QPushButton {
                background-color:#28a745;
                color:white;
                font-size:16px;
                padding:8px 25px;
                border-radius:8px;
            }
        """)
        ok.clicked.connect(dialog.accept)
        layout.addWidget(ok, alignment=Qt.AlignCenter)

        dialog.exec()


    def on_cell_edit(self, row, col):
        # แก้ได้เฉพาะคอลัมน์ "เพิ่มเมื่อ"
        if col != 6:
            return

        # ต้องเป็นแถวสินค้าเท่านั้น
        role = self.table.item(row, 0).data(Qt.UserRole)
        if role != "item":
            return

        # ถ้าเป็น double-click → ให้ไปเปิดประวัติอย่างเดียว
        if self.table.state() == QAbstractItemView.EditingState:
            return

        barcode = self.table.item(row, 5).text()
        old_value = self.table.item(row, 6).text().strip()

        # ===== เตรียมค่า default date =====
        try:
            dt = datetime.strptime(old_value, "%Y-%m-%d %H:%M:%S")
            default_date = dt.date()
        except:
            default_date = datetime.now().date()

        # ===== เปิด Popup Calendar =====
        popup = PopupCalendar(self, default_date)

        cell_rect = self.table.visualItemRect(self.table.item(row, col))
        pos = self.table.viewport().mapToGlobal(cell_rect.bottomLeft())
        popup.move(pos)

        if not popup.exec():
            return

        # ===== ได้วันที่ใหม่จากปฏิทิน =====
        new_qdate = popup.selected_date()
        new_date = new_qdate.toString("yyyy-MM-dd")
        now_time = datetime.now().strftime("%H:%M:%S")
        final_dt = f"{new_date} {now_time}"

        # ===== อ่าน Qty ปัจจุบันของสินค้า =====
        try:
            current_qty = int(self.table.item(row, 4).text())
        except:
            current_qty = 0

        # ===== อัปเดต products.created_at =====
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            UPDATE products 
            SET created_at=? 
            WHERE barcode=?
        """, (final_dt, barcode))

        # ===== เพิ่มประวัติใหม่ product_history =====
        cur.execute("""
            INSERT INTO product_history (barcode, qty_added, timestamp)
            VALUES (?, ?, ?)
        """, (barcode, current_qty, final_dt))

        conn.commit()
        conn.close()

        # ===== อัปเดตในตาราง =====
        item = QTableWidgetItem(final_dt)
        item.setTextAlignment(Qt.AlignCenter)
        item.setData(Qt.UserRole, "item")
        self.table.setItem(row, col, item)
        # ⭐⭐ รีไฮไลต์ใหม่หลังแก้ข้อมูล ⭐⭐
        self.apply_low_stock_highlight()


    


    # ------------------------------------------------------------
    def build_ui(self):
        layout = QVBoxLayout()

        title = QLabel("📜 ประวัติสินค้า")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        layout.addWidget(title)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 ค้นหาสินค้า / หมวด / บาร์โค้ด ...")
        self.search_box.setFixedHeight(40)

        self.search_box.installEventFilter(self)   # ✅ เพิ่มบรรทัดนี้
        self.search_box.textChanged.connect(self.apply_filter)

        layout.addWidget(self.search_box)


        # ตาราง
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ลำดับ", "ชื่อสินค้า", "ราคา", "ราคาทุน",
            "จำนวน", "บาร์โค้ด", "เพิ่มเมื่อ"
        ])
        self.table.verticalHeader().setVisible(False)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        

        self.table.setSelectionMode(QAbstractItemView.NoSelection)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)

        header.resizeSection(0, 80)
        header.resizeSection(2, 110)
        header.resizeSection(3, 110)
        header.resizeSection(4, 110)
        header.resizeSection(5, 150)

        # ปุ่มเปิด/ปิดไฮไลต์สินค้าใกล้หมด
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_lowstock = QPushButton("ปิดไฮไลต์สินค้าใกล้หมด")
        self.btn_lowstock.setFixedHeight(32)
        self.btn_lowstock.setStyleSheet("""
            QPushButton {
                background-color: #ffcccc;
                border: 1px solid #d88;
                color: #b00000;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ffb3b3;
            }
            QPushButton:checked {
                background-color: #ff9999;
                color: white;
            }
        """)
        self.btn_lowstock.setCheckable(True)
        self.btn_lowstock.toggled.connect(self.toggle_low_stock_highlight)

        btn_row.addWidget(self.btn_lowstock)
        layout.addLayout(btn_row)

        layout.addWidget(self.table)
        self.setLayout(layout)

        self.table.cellClicked.connect(self.on_click)
        self.table.cellDoubleClicked.connect(self.show_item_history)
        self.table.cellClicked.connect(self.on_cell_edit)



    # ------------------------------------------------------------
    def toggle_low_stock_highlight(self, state):
        if state:
            self.btn_lowstock.setText("🔦 เปิดไฮไลต์สินค้าใกล้หมด")
        else:
            self.btn_lowstock.setText(" ปิดไฮไลต์สินค้าใกล้หมด")

        self.apply_low_stock_highlight()

    def apply_low_stock_highlight(self):
        highlight_on = self.btn_lowstock.isChecked()

        # สีใหม่ตามที่ต้องการ
        COLOR_CATEGORY = QColor("#ffe08a")    # เหลืองเข้ม = หมวดหลัก
        COLOR_SUB = QColor("#fff2b3")         # เหลืองกลาง = หมวดย่อย
        COLOR_ITEM = QColor("#ffe5e5")        # แดงอ่อน = item ใกล้หมด

        # ---------------------------------------------------
        # STEP 1: reset คืนค่าเดิมทั้งหมดก่อน
        # ---------------------------------------------------
        for r in range(self.table.rowCount()):
            item0 = self.table.item(r, 0)
            if not item0:
                continue

            role = item0.data(Qt.UserRole)

            if role == "header":
                base_color = QColor("#d5d5d5")
            elif role == "sub":
                base_color = QColor("#e5e5e5")
            else:
                base_color = QColor("#ffffff")

            for c in range(self.table.columnCount()):
                cell = self.table.item(r, c)
                if cell:
                    cell.setBackground(base_color)

        if not highlight_on:
            return

        # ---------------------------------------------------
        # STEP 2: ไฮไล item (qty < 10)
        # ---------------------------------------------------
        low_rows = []
        for r in range(self.table.rowCount()):
            it0 = self.table.item(r, 0)
            if it0 and it0.data(Qt.UserRole) == "item":
                try:
                    qty = int(self.table.item(r, 4).text())
                except:
                    qty = 0

                if qty < 10:
                    low_rows.append(r)
                    for c in range(self.table.columnCount()):
                        cell = self.table.item(r, c)
                        if cell:
                            cell.setBackground(COLOR_ITEM)

        # ---------------------------------------------------
        # STEP 3: ไฮไลหมวดย่อยที่ถูกย่อ + มี item ใกล้หมด
        # ---------------------------------------------------
        sub_should_highlight = set()

        for r in low_rows:
            sr = r - 1
            while sr >= 0:
                it = self.table.item(sr, 0)
                role = it.data(Qt.UserRole)
                if role == "sub":
                    main = it.data(Qt.UserRole + 1)
                    sub = self.table.item(sr, 1).text()
                    key = (main, sub)

                    if self.sub_collapsed.get(key, True):
                        sub_should_highlight.add(sr)
                    break
                if role == "header":
                    break
                sr -= 1

        for sr in sub_should_highlight:
            for c in range(self.table.columnCount()):
                cell = self.table.item(sr, c)
                if cell:
                    cell.setBackground(COLOR_SUB)

        # ---------------------------------------------------
        # STEP 4: ไฮไลหมวดหลักที่ถูกย่อ + มี item ใกล้หมด
        # ---------------------------------------------------
        cat_should_highlight = set()

        for r in low_rows:
            cr = r - 1
            while cr >= 0:
                it = self.table.item(cr, 0)
                role = it.data(Qt.UserRole)
                if role == "header":
                    category = self.table.item(cr, 1).text()
                    if self.category_collapsed.get(category, True):
                        cat_should_highlight.add(cr)
                    break
                cr -= 1

        for cr in cat_should_highlight:
            for c in range(self.table.columnCount()):
                cell = self.table.item(cr, c)
                if cell:
                    cell.setBackground(COLOR_CATEGORY)



    # ------------------------------------------------------------
    def load_data(self):
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        # 👉 ดึงเวลาล่าสุดจาก product_history
        cur.execute("""
            SELECT 
                p.barcode, 
                p.name, 
                p.price, 
                p.cost, 
                p.qty, 
                p.main_category, 
                p.sub_category,

                IFNULL((
                    SELECT MAX(timestamp) 
                    FROM product_history h
                    WHERE h.barcode = p.barcode
                ), '') AS last_added

            FROM products p
            ORDER BY p.main_category, p.sub_category, last_added DESC
        """)

        rows = cur.fetchall()
        conn.close()

        self.all_products = []
        for bc, name, price, cost, qty, main_cat, sub_cat, last_added in rows:
            if not main_cat:
                main_cat = "ไม่มีหมวดหมู่"
            if not sub_cat:
                sub_cat = "ไม่มีหมวดย่อย"

            self.all_products.append({
                "barcode": bc,
                "name": name,
                "price": price,
                "cost": cost,
                "qty": qty,
                "category": main_cat.strip(),
                "sub_category": sub_cat.strip(),
                "created_at": last_added
            })

        self.render_table(self.all_products)

    # ------------------------------------------------------------
    def render_table(self, products):
        self.table.clearContents()
        self.table.setRowCount(0)

        self.category_rows.clear()
        self.sub_rows.clear()
        self.category_collapsed.clear()
        self.sub_collapsed.clear()

        tree = {}
        for p in products:
            main = p["category"]
            sub = p["sub_category"]
            tree.setdefault(main, {}).setdefault(sub, []).append(p)

        for main_cat, sub_map in sorted(tree.items()):
            self.add_main_header(main_cat)

            for sub_cat, plist in sorted(sub_map.items()):
                self.add_sub_header(main_cat, sub_cat)

                for idx, p in enumerate(plist, start=1):
                    self.add_product_row(p, idx)

        # hide ทั้งหมดก่อน
        for r in range(self.table.rowCount()):
            item0 = self.table.item(r, 0)
            if item0.data(Qt.UserRole) == "header":
                self.table.setRowHidden(r, False)
            else:
                self.table.setRowHidden(r, True)
        self.apply_low_stock_highlight()

    # ------------------------------------------------------------
    def add_main_header(self, category):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # ▸ / ▾ อยู่คอลัมน์ 0
        icon = QTableWidgetItem("▸")
        icon.setFont(QFont("Segoe UI", 20, QFont.Bold))
        icon.setTextAlignment(Qt.AlignCenter)
        icon.setBackground(QColor("#d5d5d5"))
        icon.setFlags(Qt.ItemIsEnabled)
        icon.setData(Qt.UserRole, "header")
        self.table.setItem(row, 0, icon)

        # ชื่อหมวดอยู่คอลัมน์ 1
        name_item = QTableWidgetItem(category)
        name_item.setFont(QFont("Segoe UI", 14, QFont.Bold))
        name_item.setBackground(QColor("#d5d5d5"))
        name_item.setFlags(Qt.ItemIsEnabled)
        name_item.setData(Qt.UserRole, "header")
        self.table.setItem(row, 1, name_item)

        # คอลัมน์อื่นให้เป็น dummy
        for c in range(2, 7):
            dummy = QTableWidgetItem("")
            dummy.setBackground(QColor("#d5d5d5"))
            dummy.setFlags(Qt.ItemIsEnabled)
            dummy.setData(Qt.UserRole, "header")
            self.table.setItem(row, c, dummy)

        self.category_rows[category] = row
        self.category_collapsed[category] = True
        self.table.setRowHeight(row, 45)

    # ------------------------------------------------------------
    def add_sub_header(self, main, sub):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # ▸ อยู่คอลัมน์ 0 (ชิดขวา)
        icon = QTableWidgetItem("▸")
        icon.setFont(QFont("Segoe UI", 18, QFont.Bold))
        icon.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        icon.setBackground(QColor("#e5e5e5"))
        icon.setFlags(Qt.ItemIsEnabled)
        icon.setData(Qt.UserRole, "sub")
        icon.setData(Qt.UserRole + 1, main)
        self.table.setItem(row, 0, icon)

        # ชื่อหมวดย่อยในคอลัมน์ 1
        name_item = QTableWidgetItem(sub)
        name_item.setFont(QFont("Segoe UI", 12, QFont.Bold))
        name_item.setBackground(QColor("#e5e5e5"))
        name_item.setFlags(Qt.ItemIsEnabled)
        name_item.setData(Qt.UserRole, "sub")
        self.table.setItem(row, 1, name_item)

        # dummy columns
        for c in range(2, 7):
            dummy = QTableWidgetItem("")
            dummy.setBackground(QColor("#e5e5e5"))
            dummy.setFlags(Qt.ItemIsEnabled)
            dummy.setData(Qt.UserRole, "sub")
            self.table.setItem(row, c, dummy)

        self.sub_rows[(main, sub)] = row
        self.sub_collapsed[(main, sub)] = True
        self.table.setRowHeight(row, 38)

    # ------------------------------------------------------------
    def add_product_row(self, p, order):
        row = self.table.rowCount()
        self.table.insertRow(row)

        def cell(val, align=Qt.AlignCenter):
            it = QTableWidgetItem(str(val))
            it.setData(Qt.UserRole, "item")
            it.setTextAlignment(align)
            return it

        self.table.setItem(row, 0, cell(order))  # ลำดับ
        self.table.setItem(row, 1, cell(p["name"], Qt.AlignLeft | Qt.AlignVCenter))
        self.table.setItem(row, 2, cell(p["price"]))
        self.table.setItem(row, 3, cell(p["cost"]))
        self.table.setItem(row, 4, cell(p["qty"]))
        self.table.setItem(row, 5, cell(p["barcode"]))
        self.table.setItem(row, 6, cell(p["created_at"]))

        self.table.setRowHeight(row, 42)

    # ------------------------------------------------------------
    def on_click(self, row, col):
        item = self.table.item(row, 0)
        if not item:
            return
        role = item.data(Qt.UserRole)

        # ============ หมวดหลัก ============
        if role == "header":
            category = self.table.item(row, 1).text()
            collapsed = self.category_collapsed.get(category, True)
            new_state = not collapsed
            self.category_collapsed[category] = new_state

            item.setText("▸" if new_state else "▾")

            r = row + 1
            while r < self.table.rowCount():
                it = self.table.item(r, 0)
                if it.data(Qt.UserRole) == "header":
                    break
                if it.data(Qt.UserRole) == "sub":
                    self.table.setRowHidden(r, new_state)
                else:
                    self.table.setRowHidden(r, True)
                r += 1

            # ⭐ เพิ่มบรรทัดนี้
            self.apply_low_stock_highlight()

            return

        # ============ หมวดย่อย ============
        if role == "sub":
            main = item.data(Qt.UserRole + 1)
            sub = self.table.item(row, 1).text()
            key = (main, sub)

            collapsed = self.sub_collapsed.get(key, True)
            new_state = not collapsed
            self.sub_collapsed[key] = new_state

            item.setText("▸" if new_state else "▾")

            r = row + 1
            while r < self.table.rowCount():
                it = self.table.item(r, 0)
                if it.data(Qt.UserRole) in ("header", "sub"):
                    break
                self.table.setRowHidden(r, new_state)
                r += 1

            # ⭐ เพิ่มบรรทัดนี้
            self.apply_low_stock_highlight()

            return


    # ------------------------------------------------------------
    def get_main_of_sub(self, row):
        r = row - 1
        while r >= 0:
            it = self.table.item(r, 0)
            if it.data(Qt.UserRole) == "header":
                return it.text()[2:].strip()
            r -= 1
        return None

    # ------------------------------------------------------------
    def apply_filter(self):
        t = self.search_box.text().strip().lower()

        if not t:
            self.render_table(self.all_products)
            return

        results = []
        for p in self.all_products:
            if (
                t in p["name"].lower()
                or t in p["barcode"].lower()
                or t in p["category"].lower()
                or t in p["sub_category"].lower()
                or t in str(p["created_at"]).lower()
            ):
                results.append(p)

        self.render_table(results)


    def highlight_main(self, row):
        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it:
                it.setBackground(QColor("#fff4c2"))   # สีเหลืองอ่อน

    def highlight_sub(self, row):
        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it:
                it.setBackground(QColor("#ffe9d2"))   # สีส้มอ่อน

    def clear_highlight_row(self, row):
        role = self.table.item(row, 0).data(Qt.UserRole)
        color = {
            "header": "#d5d5d5",
            "sub": "#e5e5e5",
            "item": "#ffffff"
        }[role]

        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it:
                it.setBackground(QColor(color))


    def eventFilter(self, obj, event):

        if obj == self.search_box and event.type() == QEvent.KeyPress:

            key = event.key()

            if key not in (Qt.Key_Return, Qt.Key_Enter):
                return False

            # ===== Enter ครั้งที่ 2 = ล้าง =====
            if self.enter_count == 1:
                self.enter_count = 0
                self.search_box.clear()
                self.apply_filter()
                return True

            # ===== Enter ครั้งที่ 1 = ค้นหา =====
            raw = self.search_box.text().strip()

            if not raw:
                self.enter_count = 0
                return True

            # แปลงเลขไทย + คีย์บอร์ดไทย
            code = convert_thai_barcode(raw)
            code = convert_thai_digits(code)

            self.search_box.blockSignals(True)
            self.search_box.setText(code)
            self.search_box.blockSignals(False)

            self.apply_filter()

            self.enter_count = 1
            return True

        return super().eventFilter(obj, event)


    def finish_scan(self):
        self.scan_timer.stop()
        if not self.scan_buffer:
            return

        raw = self.scan_buffer.strip()
        self.scan_buffer = ""

        code = convert_thai_barcode(raw)
        code = convert_thai_digits(code)

        self.search_box.setText(code)
        self.apply_filter()


def convert_thai_digits(text):
    thai_digits = "๐๑๒๓๔๕๖๗๘๙"
    arabic_digits = "0123456789"
    return text.translate(str.maketrans(thai_digits, arabic_digits))


def convert_thai_barcode(text):
    # แป้นพิมพ์ไทยที่สแกนเนอร์ชอบส่งมา
    thai_keys = "๑๒๓๔๕๖๗๘๙๐"
    eng_keys  = "1234567890"
    return text.translate(str.maketrans(thai_keys, eng_keys))

def convert_thai_barcode(text):
    mapping = {
        "ๅ": "1", "/": "2", "-": "3", "ภ": "4", "ถ": "5",
        "ุ": "6", "ึ": "7", "ค": "8", "ต": "9", "จ": "0",

        "+": "1", "๑": "2", "๒": "3", "๓": "4", "๔": "5",
        "ู": "6", "฿": "7", "๕": "8", "๖": "9", "๗": "0",
    }

    out = ""
    for ch in text:
        out += mapping.get(ch, ch)
    return out
