from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QTableWidget, QTableWidgetItem, QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtCore import QCoreApplication
import ctypes
from ctypes import wintypes


class DisplayWindow(QWidget):
    def __init__(self):
        super().__init__()

        # เริ่มต้นปิด
        self.enabled = False
        self.current_geo = None

        # UI อย่างเดียว ห้ามเปิดหน้าจอ/ย้ายจอใน init
        self.build_ui()

        # Timer ไว้ใช้เฉพาะตอนเปิดเท่านั้น
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.verify_screen_status)
        # ❌ ห้าม start timer ที่นี่
        # self.check_timer.start(1000)
        # ปล่อยให้ toggle_display_window() เรียกเอง

    

   

    # ======================================================
    #  เลือกจอรอง (เรียกเฉพาะตอนเปิดเท่านั้น)
    # ======================================================
    def init_display(self):
        if not self.enabled:
            return

        screens = QApplication.screens()
        primary = QApplication.primaryScreen()

        print("ตรวจจอจำนวน =", len(screens))

        # ไม่มีจอรอง
        if len(screens) < 2:
            print("⚠ ไม่มีจอรอง → ไม่เปิด DisplayWindow")
            return

        # หา secondary
        target = None
        for s in screens:
            if s != primary:
                target = s
                break

        if target is None:
            target = primary

        geo = target.geometry()
        print("📺 DisplayWindow → ใช้จอ:", geo)

        # ตั้งค่า Window
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        # ⭐⭐ ป้องกัน DisplayWindow แย่งโฟกัส ⭐⭐
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus)

        # ย้ายไปยังจอรอง
        self.setGeometry(geo)

        # ป้องกัน Windows ดึงหน้าจอกลับ
        for delay in [10, 60, 200]:
            QTimer.singleShot(delay, lambda g=geo: self.move(g.left(), g.top()))

        self.current_geo = geo

        # เปิดหลังย้ายจอ
        for delay in [100, 300]:
            QTimer.singleShot(delay, self.showFullScreen)
        



    # ======================================================
    #  ตรวจจอเฉพาะตอน enabled = True
    # ======================================================
    def verify_screen_status(self):
        if not self.enabled:
            return  # สำคัญมาก!!
        # ⭐ ตรวจว่า main ปิดไปหรือยัง
        if hasattr(self, "main_window") and not self.main_window.isVisible():
            print("⚠ MainWindow ถูกปิด → ปิด DisplayWindow")
            self.force_close()
            return

        screens = QApplication.screens()
        primary = QApplication.primaryScreen()

        # หา secondary
        secondary = None
        for s in screens:
            if s != primary:
                secondary = s
                break

        # จอรองหาย → ไม่อะไรทั้งนั้น แค่ไม่แสดง
        if secondary is None:
            print("⚠ จอรองหาย → ซ่อนจอ Display")
            self.hide()
            return

        # จอรองกลับมา → ย้ายกลับไป
        if self.current_geo != secondary.geometry():
            print("🎉 จอรองกลับมาแล้ว → ย้ายกลับไปจอรอง")
            self.init_display()


    # ======================================================
    #  UI หลัก
    # ======================================================
    def build_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #f3e9d7;
                color: #b48b43;
                font-family: 'Segoe UI';
            }
            QLabel {
                color: #b48b43;
            }
            QHeaderView::section {
                background-color: #e7d7bd;
                color: #7d623c;
                font-weight: bold;
                font-size: 26px;
            }
            QTableWidget {
                background-color: #fffcf5;
                gridline-color: #d8c7a8;
                border: 1px solid #d8c7a8;
                font-size: 28px;
            }
        """)

        layout = QVBoxLayout()

        self.lbl_shop = QLabel("🏺 ร้านปัญจภัณฑ์ PJP")
        self.lbl_shop.setFont(QFont("Segoe UI", 42, QFont.Bold))
        self.lbl_shop.setAlignment(Qt.AlignCenter)

        from PySide6.QtWidgets import QAbstractItemView, QHeaderView

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "สินค้า", "จำนวน", "ราคา"])

        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        
        header = self.table.horizontalHeader()

        self.table.setColumnWidth(0, 80)   # ID
        self.table.setColumnWidth(1, 500)  # สินค้า (ยืด)
        self.table.setColumnWidth(2, 200)  # จำนวน
        self.table.setColumnWidth(3, 200)  # ราคา

        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)

       

        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.lbl_footer = QLabel("รวมทั้งหมด: 0.00 บาท")
        self.lbl_footer.setAlignment(Qt.AlignCenter)
        self.lbl_footer.setStyleSheet("""
            QLabel {
                background-color: #d6b27c;
                color: white;
                font-size: 80px;
                font-weight: bold;
                padding: 25px 20px;
                border-top: 4px solid #b18c5a;
            }
        """)

        layout.addWidget(self.lbl_shop)
        layout.addWidget(self.table)
        layout.addWidget(self.lbl_footer)

        self.setLayout(layout)

    # ======================================================
    #  Update display
    # ======================================================
    def update_display(self, cart):
        items = list(cart.items())[::-1]
        self.table.setRowCount(len(items))
        total = 0

        for r, (code, item) in enumerate(items):
            row_id = r + 1

            id_cell = QTableWidgetItem(str(row_id))
            id_cell.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 0, id_cell)

            name = QTableWidgetItem(item["name"])
            name.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 1, name)

            qty = QTableWidgetItem(str(item["qty"]))
            qty.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 2, qty)

            price_value = item["price"] * item["qty"]
            price = QTableWidgetItem(f"{price_value:.2f}")
            price.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 3, price)


            total += price_value

        self.update_total(total)
        self.table.scrollToTop()

    def update_total(self, total):
        self.lbl_footer.setStyleSheet("""
            QLabel {
                background-color: #d6b27c;
                color: white;
                font-size: 80px;
                font-weight: bold;
                padding: 25px 20px;
                border-top: 4px solid #b18c5a;
            }
        """)
        self.lbl_footer.setText(f"รวมทั้งหมด: {total:.2f} บาท")

    def update_change(self, change):
        self.lbl_footer.setStyleSheet("""
            QLabel {
                background-color: #0d8d2d;
                color: white;
                font-size: 90px;
                font-weight: bold;
                padding: 25px 20px;
                border-top: 6px solid #0a6e24;
            }
        """)
        self.lbl_footer.setText(f"เงินทอน: {change:.2f} บาท")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
            
    def attach_main(self, main_window):
        """เชื่อมกับหน้าหลัก"""
        self.main_window = main_window

    def force_close(self):
        try:
            self.enabled = False
            self.check_timer.stop()
        except:
            pass
        # ⭐⭐ ปลดล็อกเมาส์ก่อนปิด ⭐⭐
        self.unlock_mouse()
        self.close()




    def unlock_mouse(self):
        """ปลดล็อกเมาส์ให้ไปได้ทุกจอ"""
        ctypes.windll.user32.ClipCursor(None)
