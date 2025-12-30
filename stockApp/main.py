import sys
from db import init_db
init_db()
from PySide6.QtGui import QScreen
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtGui import QCursor


import ctypes
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QHBoxLayout, QVBoxLayout, QPushButton, QLabel
)
from PySide6.QtCore import Qt, QTimer

from display_window import DisplayWindow
from db import init_db

from sale import SellTab
from import_tab import ImportTab
from stock_tab import StockTab
from record_tab import RecordTab
from history_tab import ProductHistoryTab



APP_STYLE = """
QWidget {
    background-color: #f5f5f5;
    font-family: 'Segoe UI';
    font-size: 16px;
    color: #333333;
}

QTabWidget::pane { border: none; }

QTabBar::tab {
    background: #e0e0e0;
    color: #888;
    padding: 10px 25px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #4CAF50;
    color: white;
    font-weight: bold;
}

QPushButton {
    background-color: #4CAF50;
    color: white;
    font-weight: bold;
    padding: 10px 18px;
    border-radius: 10px;
}

QPushButton:hover { background-color: #45a049; }

QLineEdit {
    background: white;
    padding: 8px;
    border: 1px solid #ccc;
    border-radius: 6px;
}




QHeaderView::section {
    background-color: #4CAF50;
    color: white;
    padding: 6px;
    font-weight: bold;
}


QTableWidget {
    background: white;
    border: 1px solid #ddd;
    gridline-color: #ddd;
}

QTableWidget::item { padding: 6px; }
"""
import sqlite3

def migrate_db():
    """อัปเดตฐานข้อมูลเก่าให้อัตโนมัติ (กัน error no such column)"""
    conn = sqlite3.connect("stock.db")
    c = conn.cursor()

    # อ่านคอลัมน์ปัจจุบันของตาราง products
    c.execute("PRAGMA table_info(products)")
    cols = [col[1] for col in c.fetchall()]

    # เพิ่ม sort_order ถ้ายังไม่มี
    if "sort_order" not in cols:
        print("⚙ เพิ่มคอลัมน์ sort_order ในฐานข้อมูล...")
        c.execute("ALTER TABLE products ADD COLUMN sort_order INTEGER DEFAULT 0;")
        conn.commit()
        print("✔ เพิ่มเรียบร้อย")

    conn.close()


class StockApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # 🔥 เรียกก่อนทุกอย่าง เพื่อแก้ฐานข้อมูลเก่าทันที
        migrate_db()
        
        


        # -------- จอลูกค้า (ปิดไว้) --------
        self.display_win = DisplayWindow()
        self.display_win.attach_main(self)
        self.display_win.enabled = False
        self.display_win.hide()
        try:
            self.display_win.check_timer.stop()
        except:
            pass

        # -------- ข้อมูลร้าน --------
        self.SHOP_NAME = "ร้านปัญจภัณฑ์"
        self.SHOP_ADDR = "101/2 หมู่8, สมุทรสงคราม"
        self.SHOP_TAXID = "0123456789012"
        self.CASHIER_NAME = "ADMIN"

        init_db()
        self.init_ui()

    def clamp_mouse_position(self):
        # ใช้ geometry ของจอหลัก
        screen = QGuiApplication.primaryScreen()
        geo = screen.geometry()

        pos = QCursor.pos()
        x, y = pos.x(), pos.y()

        left = geo.left()
        right = geo.right()

        new_x = x
        if x < left:
            new_x = left
        if x > right:
            new_x = right

        # ถ้าต้องแก้ไข → ขยับเมาส์กลับเข้าในกรอบ
        if new_x != x:
            QCursor.setPos(new_x, y)

    # =======================================================
    def init_ui(self):
        self.setWindowTitle("โปรแกรมจัดการสต็อกสินค้า PJP")
        self.resize(1400, 900)
        
        self.tabs = QTabWidget()
        self.tabs.tabBarClicked.connect(self.on_tab_clicked)

        # -------- โหลดแต่ละ Tab --------
        self.sell_tab = SellTab(self)
        self.import_tab = ImportTab(self)
        self.stock_tab = StockTab()
        self.record_tab = RecordTab(self)
        self.stock_tab.saved.connect(
            lambda: QTimer.singleShot(50, self.import_tab.refresh)
        )


        # -------- เพิ่มลงใน Tab Widget --------
        self.tabs.addTab(self.sell_tab, "ขายสินค้า")
        self.tabs.addTab(self.import_tab, "เพิ่มสินค้าเข้า")
        self.tabs.addTab(self.stock_tab, "ดูสต็อกทั้งหมด")
        
        self.history_tab = ProductHistoryTab()
        self.tabs.addTab(self.history_tab, "ประวัติสินค้า")
        self.tabs.addTab(self.record_tab, "ประวัติการขาย")
        self.last_tab = self.sell_tab

        # ====== AutoSave Toggle (มุมซ้ายบนแบบ Word) ======
        self.autosave_enabled = True   # เริ่มต้นเปิด AutoSave


        self.btn_autosave = QPushButton("AutoSave: ON")
        self.btn_autosave.setCheckable(True)
        self.btn_autosave.setChecked(True)
        self.btn_autosave.setFixedHeight(40)   # ⭐ บังคับให้ปุ่มสูงพอจนเห็นมุมมน
        self.btn_autosave.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: white;
                padding: 6px 20px;
                border-radius: 16px;
                border: none;           /* ⭐ สำคัญมาก */
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: #2ecc71;
                color: white;
            }
        """)

        self.btn_autosave.clicked.connect(self.toggle_autosave)
        

        # -------- เวลาแบบด้านขวา --------
        self.time_label = QLabel()
        self.time_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #444;
            padding-right: 12px;
        """)
        

        container = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ================================
        #  แถวบนสุด AutoSave + ระบบ POS + เวลา
        # ================================
        top_widget = QWidget()
        top_widget.setStyleSheet("""
            background-color: #e9e9e9;
            border-radius: 6px;
        """)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(12, 8, 12, 8)
        top_bar.setSpacing(10)

        # ปุ่ม AutoSave (ซ้าย)
        top_bar.addWidget(self.btn_autosave)

        # spacer ซ้าย → ดัน label ไปกลาง
        top_bar.addStretch()

        # ⭐ เพิ่มข้อความตรงกลาง
        center_label = QLabel("POS-PjP")
        center_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #555;
        """)
        top_bar.addWidget(center_label)

        # spacer ขวา → ดันเวลาไปชิดขวา
        top_bar.addStretch()

        # เวลา (ขวา)
        top_bar.addWidget(self.time_label)

        top_widget.setLayout(top_bar)
        main_layout.addWidget(top_widget)


        # ================================
        #  แถวที่สอง: TabBar เต็มแถว
        # ================================
        tab_container = QWidget()
        tab_layout = QHBoxLayout()
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        tab_layout.addWidget(self.tabs)   # TAB จะเต็มทั้งแถว

        tab_container.setLayout(tab_layout)
        main_layout.addWidget(tab_container)

        # ตั้ง layout หลัก
        container.setLayout(main_layout)
        self.setCentralWidget(container)



        # เวลา real-time
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_datetime)
        self.time_timer.start(1000)
        self.update_datetime()

        # -------- AutoSave timer (ทุก 10 วินาที) --------
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave_tick)
        self.autosave_timer.start(10000)   # 10000 ms = 10 วิ

        # -------- เมื่อสลับ Tab --------
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # -------- หน้าแรก --------
        QTimer.singleShot(300, lambda: (
            self.tabs.setCurrentIndex(0),
            self.sell_tab.focus_barcode_box()
        ))
        # ===== Mouse Clamp =====
        self.mouse_clamp_timer = QTimer(self)
        self.mouse_clamp_timer.timeout.connect(self.clamp_mouse_position)
        self.mouse_clamp_timer.start(10)   # เช็คทุก 10ms


    # =======================================================
    #   AutoSave toggle
    # =======================================================
    def toggle_autosave(self):
        self.autosave_enabled = self.btn_autosave.isChecked()
        if self.autosave_enabled:
            self.btn_autosave.setText("AutoSave: ON")
        else:
            self.btn_autosave.setText("AutoSave: OFF")

    def autosave_tick(self):
        """ถูกเรียกทุก 10 วิ ถ้า AutoSave เปิดอยู่จะเซฟสต็อกให้เอง"""
        if not self.autosave_enabled:
            return
        try:
            if hasattr(self.stock_tab, "dirty") and self.stock_tab.dirty:
                self.stock_tab.save_if_dirty()
                print("AutoSaved stock (timer)")
        except Exception as e:
            print("AutoSave error:", e)

    
    def on_tab_clicked(self, index):
        # ให้สลับหน้าได้ปกติ ไม่มี popup ไม่มีบล็อค
        pass


    # =======================================================
    def on_tab_changed(self, index):

        old_tab = self.last_tab
        new_tab = self.tabs.widget(index)

        # === ถ้าออกจาก ImportTab ===
        if isinstance(old_tab, ImportTab):

            try:
                old_tab.fill_empty_barcodes_with_nan()
                old_tab.save_pending_rows()
            except Exception as e:
                print("Error filling nan:", e)

        # ✅✅✅ เพิ่มตรงนี้: ถ้าออกจาก StockTab ให้ AutoSave ทันที
        if isinstance(old_tab, StockTab):
            if self.autosave_enabled:
                try:
                    if hasattr(old_tab, "dirty") and old_tab.dirty:
                        print("🔁 AutoSave because leave StockTab")
                        old_tab.save_if_dirty()
                except Exception as e:
                    print("AutoSave error:", e)


        # === ตั้งค่าโฟกัส / รีเฟรช ของแท็บอื่น ===
        if new_tab is self.stock_tab:
            QTimer.singleShot(20, new_tab.refresh)

        if new_tab is self.sell_tab:
            QTimer.singleShot(80, new_tab.focus_barcode_box)

        if new_tab is self.import_tab:
            QTimer.singleShot(80, new_tab.focus_barcode_box)

        self.last_tab = new_tab




    # =======================================================
    # closeEvent → พฤติกรรมแบบ Word
    #   - ถ้า AutoSave ON → เซฟแล้วปิดเลย (ไม่ popup)
    #   - ถ้า AutoSave OFF → ถ้า dirty ให้ถาม บันทึก/ไม่บันทึก/ยกเลิก
    # =======================================================
    def closeEvent(self, event):
        # เช็คว่ามีข้อมูลยังไม่เซฟหรือไม่
        dirty = getattr(self.stock_tab, "dirty", False)

        # ============================================================
        # CASE 1: AutoSave เปิดอยู่ → ไม่ต้องถามเซฟข้อมูล
        #        แต่ต้องถามผู้ใช้ว่า "ต้องการปิดโปรแกรมไหม?"
        # ============================================================
        if self.autosave_enabled:
            msg = QMessageBox(self)
            msg.setWindowTitle("ต้องการปิดโปรแกรม?")
            msg.setText("คุณต้องการที่จะปิดโปรแกรมใช่ไหม?")
            msg.setIcon(QMessageBox.Question)

            yes_btn = msg.addButton("ใช่", QMessageBox.AcceptRole)
            no_btn = msg.addButton("ไม่", QMessageBox.RejectRole)

            # default = yes
            msg.setDefaultButton(yes_btn)
            msg.setEscapeButton(no_btn)

            yes_btn.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    font-size: 15px;
                    padding: 8px 22px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1f9452;
                }
            """)

            no_btn.setStyleSheet("""
                QPushButton {
                    background-color: #555;
                    color: white;
                    font-size: 15px;
                    padding: 8px 22px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #444;
                }
            """)

            msg.exec()

            if msg.clickedButton() == yes_btn:
                # เซฟอัตโนมัติ (ถ้า dirty)
                try:
                    if hasattr(self.stock_tab, "save_if_dirty"):
                        self.stock_tab.save_if_dirty()
                except:
                    pass

                event.accept()
                return

            else:
                event.ignore()
                return

        # ============================================================
        # CASE 2: AutoSave ปิด BUT ไม่มี dirty → Popup แบบ ESC
        # ============================================================
        if not dirty:
            msg = QMessageBox(self)
            msg.setWindowTitle("ต้องการปิดโปรแกรม?")
            msg.setText("คุณต้องการที่จะปิดโปรแกรมใช่ไหม?")
            msg.setIcon(QMessageBox.Question)

            yes_btn = msg.addButton("ใช่", QMessageBox.AcceptRole)
            no_btn = msg.addButton("ไม่", QMessageBox.RejectRole)

            msg.setDefaultButton(yes_btn)
            msg.setEscapeButton(no_btn)

            yes_btn.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    font-size: 15px;
                    padding: 8px 22px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1f9452;
                }
            """)

            no_btn.setStyleSheet("""
                QPushButton {
                    background-color: #555;
                    color: white;
                    font-size: 15px;
                    padding: 8px 22px;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #444;
                }
            """)

            msg.exec()

            if msg.clickedButton() == yes_btn:
                event.accept()
            else:
                event.ignore()
            return

        # ============================================================
        # CASE 3: AutoSave ปิด + dirty = True → popup บันทึก/ไม่บันทึก/ยกเลิก
        # ============================================================
        msg = QMessageBox(self)
        msg.setWindowTitle("มีข้อมูลยังไม่ได้บันทึก")
        msg.setText("คุณยังไม่ได้บันทึกการเปลี่ยนแปลงของสินค้า\nต้องการบันทึกก่อนปิดหรือไม่?")
        msg.setIcon(QMessageBox.Warning)

        save_btn = msg.addButton("บันทึก", QMessageBox.AcceptRole)
        dont_btn = msg.addButton("ไม่บันทึก", QMessageBox.DestructiveRole)
        cancel_btn = msg.addButton("ยกเลิก", QMessageBox.RejectRole)

        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 15px;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #229954; }
        """)

        dont_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                font-size: 15px;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2f2f2f; }
        """)

        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #5a5a5a;
                color: white;
                font-size: 15px;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #4d4d4d; }
        """)

        msg.exec()

        if msg.clickedButton() == save_btn:
            try:
                self.stock_tab.save_if_dirty()
            except:
                pass
            event.accept()
            return

        if msg.clickedButton() == dont_btn:
            event.accept()
            return

        if msg.clickedButton() == cancel_btn:
            event.ignore()
            return


    # =======================================================
    def update_datetime(self):
        from datetime import datetime
        now = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        self.time_label.setText(now)

    # =======================================================
    def toggle_f11(self):
        screen = QGuiApplication.primaryScreen()
        geo = screen.geometry()   # ⭐ เต็มจอจริง 100%

        if self.isFullScreen():
            self.showNormal()
            self.setGeometry(geo)
            self.showMaximized()
        else:
            self.setGeometry(geo)
            self.showFullScreen()


            



    # =======================================================
    def keyPressEvent(self, event):
        # ============================
        # F11 → Toggle FullScreen
        # ============================
        if event.key() == Qt.Key_F11:
            self.toggle_f11()
            return

        # ============================
        # ESC → ปิดโปรแกรม (ไปให้ closeEvent จัดการ popup)
        # ============================
        if event.key() == Qt.Key_Escape:
            self.close()
            return

        # ส่ง event อื่น ๆ ให้ parent จัดการต่อ
        super().keyPressEvent(event)




if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)

    win = StockApp()
    win.show()
    QTimer.singleShot(10, lambda: (
    win.setGeometry(QGuiApplication.primaryScreen().geometry()),
    win.showFullScreen()
    ))


    sys.exit(app.exec())
