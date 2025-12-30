import datetime
import os
import ctypes
from db import get_product, update_stock, save_sale, get_alias

from PySide6.QtWidgets import QHeaderView
from payment_window import PaymentWindow

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QInputDialog, QAbstractItemView, QApplication,
    QStyledItemDelegate
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QLocale, QTimer, QEvent

from db import get_product, update_stock, save_sale
from receipt import print_receipt


# ===========================================================
#   🔥 Inline Editor Delegate
# ===========================================================
class CleanDoubleClickDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setAlignment(Qt.AlignCenter)
        editor.setStyleSheet("""
            QLineEdit {
                border: none;
                background: white;
                padding: 0;
                margin: 0;
            }
        """)
        return editor

    def setEditorData(self, editor, index):
        editor.setText(str(index.data(Qt.DisplayRole)))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


# ===========================================================
#                       SellTab
# ===========================================================
class SellTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.cart = {}

        # เริ่มต้นปริ้น = ปิด
        self.enable_print = False
        

        self.build_ui()

        # ให้ทุกปุ่มโฟกัสกลับช่องบาร์โค้ดเสมอ
        self.installEventFilter(self)

        # เปิดแอพแล้วให้โฟกัสช่องบาร์โค้ดทันที
        QTimer.singleShot(10, self.focus_barcode_box)

    # ----------------------------------------------------------
    def force_english_keyboard(self):
        try:
            layout = ctypes.windll.user32.LoadKeyboardLayoutW("00000409", 1)
            ctypes.windll.user32.ActivateKeyboardLayout(layout, 0)
        except Exception:
            pass

    def convert_thai_keyboard_barcode(self, text):
        mapping = {
            "ๅ": "1", "/": "2",
            "-": "3", "–": "3", "—": "3",
            "ภ": "4", "ถ": "5",
            "ุ": "6", "ึ": "7",
            "ค": "8", "ต": "9",
            "จ": "0",

            "+": "1", "๑": "2", "๒": "3", "๓": "4", "๔": "5",
            "ู": "6", "฿": "7", "๕": "8", "๖": "9", "๗": "0",
        }

        out = ""
        for ch in text:
            out += mapping.get(ch, ch)
        return out

        
    def convert_thai_digits(self, text):
        thai_digits = "๐๑๒๓๔๕๖๗๘๙"
        arabic_digits = "0123456789"
        return text.translate(str.maketrans(thai_digits, arabic_digits))

    def focus_barcode_box(self):
        try:
            self.code_sell.setFocus()
            self.force_english_keyboard()
        except:
            pass

    # ===========================================================
    # UI
    # ===========================================================
    def build_ui(self):
        layout = QVBoxLayout()

        lbl_title = QLabel("💰 ขายสินค้า (POS Mode)")
        lbl_title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        layout.addWidget(lbl_title)

        # -------------------------------
        # แถวบน
        # -------------------------------
        top = QHBoxLayout()

        self.code_sell = QLineEdit()
        self.code_sell.setPlaceholderText("สแกนหรือกรอกบาร์โค้ดสินค้า...")
        self.code_sell.returnPressed.connect(self.add_to_cart)

        btn_add = QPushButton("➕ เพิ่มเข้าตะกร้า")
        btn_add.clicked.connect(self.add_to_cart)

        top.addWidget(self.code_sell)
        top.addWidget(btn_add)
        layout.addLayout(top)

        # -------------------------------
        # ตารางสินค้า
        # -------------------------------
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(6)
        self.cart_table.setHorizontalHeaderLabels(
            ["ID", "บาร์โค้ด", "ชื่อสินค้า", "ราคา", "จำนวน", "จัดการ"]
        )

        self.cart_table.verticalHeader().setVisible(False)
        

        self.cart_table.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.SelectedClicked
        )

        self.cart_table.setItemDelegate(CleanDoubleClickDelegate(self.cart_table))

        for i in range(5):
            self.cart_table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)

        header = self.cart_table.horizontalHeader()
        # ---- กำหนดความกว้างแต่ละคอลัมน์ ----
        self.cart_table.setColumnWidth(0, 80)    # ID
        self.cart_table.setColumnWidth(1, 240)   # บาร์โค้ด
        # ชื่อสินค้าให้ยืด
        
        self.cart_table.setColumnWidth(3, 160)    # ราคา
        self.cart_table.setColumnWidth(4, 160)    # จำนวน
        self.cart_table.setColumnWidth(5, 240)   # ปุ่มจัดการ (เพิ่ม/ลด/ลบ)

        # ป้องกันไม่ให้คอลัมน์อื่นยืดตาม
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        

       

        layout.addWidget(self.cart_table)

                # -------------------------------
        # ปุ่มล่าง
        # -------------------------------
        bottom = QHBoxLayout()

        btn_clear = QPushButton("🗑️ ล้างตะกร้า")
        btn_clear.clicked.connect(self.clear_cart)

        # ปุ่มปริ้นใบเสร็จ toggle
        self.btn_toggle_print = QPushButton("🖨️ ปริ้นใบเสร็จ: ปิด")
        self.btn_toggle_print.setStyleSheet("background:#B71C1C;color:white;font-size:16px;")
        self.btn_toggle_print.setFixedHeight(40)
        self.btn_toggle_print.clicked.connect(self.toggle_print)

        # ⭐ ปุ่มเปิด/ปิดหน้าจอลูกค้า (ค่าเริ่มต้น = ปิด)
        self.btn_toggle_display = QPushButton("🖥️ หน้าจอลูกค้า: ปิด")
        self.btn_toggle_display.setStyleSheet("background:#B71C1C;color:white;font-size:16px;")
        self.btn_toggle_display.setFixedHeight(40)
        self.btn_toggle_display.clicked.connect(self.toggle_display_window)

        btn_confirm = QPushButton("✅ ชำระเงินทั้งหมด")
        btn_confirm.clicked.connect(self.confirm_sale)

        # ====== ซ้ายสุด ======
        bottom.addWidget(self.btn_toggle_print)
        bottom.addWidget(self.btn_toggle_display)

        # ====== ช่องว่างกลาง ======
        bottom.addStretch()

        # ====== ขวาสุด ======
        bottom.addWidget(btn_clear)
        bottom.addWidget(btn_confirm)

        layout.addLayout(bottom)


        # -------------------------------
        self.result_label = QLabel("รวมทั้งหมด: 0.00 บาท")
        self.result_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.result_label)

        self.setLayout(layout)

    # ===========================================================
    # เปิด/ปิดหน้าจอลูกค้า
    # ===========================================================
    def toggle_display_window(self):
        win = self.app.display_win

        # สถานะเริ่มต้น ถ้ายังไม่มี
        if not hasattr(self, "display_on"):
            self.display_on = False

        # ------------------------------
        # 🔴 ปิดจอ
        # ------------------------------
        if self.display_on:
            win.enabled = False

            try:
                win.check_timer.stop()
            except:
                pass

            # ⭐ ใส่ดีเลย์ก่อนซ่อน (สำคัญ)
            QTimer.singleShot(150, win.hide)
            # ⭐⭐ ปลดล็อกเมาส์เมื่อปิดจอ ⭐⭐
            win.unlock_mouse()

            self.btn_toggle_display.setText("🖥️ หน้าจอลูกค้า: ปิด")
            self.btn_toggle_display.setStyleSheet(
                "background:#B71C1C;color:white;font-size:16px;"
            )

            self.display_on = False

        # ------------------------------
        # 🟢 เปิดจอ
        # ------------------------------
        else:
            win.enabled = True

            # ⭐ ดีเลย์ก่อนเปิด เพื่อให้ Windows apply ได้
            def _open_display():
                try:
                    # รีเซ็ตไปจอรองทุกครั้ง
                    win.init_display()
                except:
                    pass

                try:
                    win.check_timer.start(1000)
                except:
                    pass

                win.show()
                win.raise_()
                win.activateWindow()
            

            QTimer.singleShot(200, _open_display)

            self.btn_toggle_display.setText("🖥️ หน้าจอลูกค้า: เปิด")
            self.btn_toggle_display.setStyleSheet(
                "background:#4CAF50;color:white;font-size:16px;"
            )

            self.display_on = True

        # กลับโฟกัสช่องบาร์โค้ดเสมอ
        QTimer.singleShot(100, self.focus_barcode_box)


    # ===========================================================
    # ตะกร้า
    # ===========================================================
    def add_to_cart(self):
        self.force_english_keyboard()  # ⭐ บังคับอังกฤษทุกครั้ง

        # ดึงค่าจากช่องยิงบาร์โค้ด
        raw = self.code_sell.text().strip()

        # 1) แปลงเลขไทย (๐๑๒...) เป็นเลขอารบิกปกติ
        code = self.convert_thai_digits(raw)

        # 2) แปลงคีย์ภาษาไทยที่กดผิด เช่น ๅ ภ ถ ค ต จ ฯลฯ → เป็นตัวเลขจริง
        code = self.convert_thai_keyboard_barcode(code)

        if not code:
            self.code_sell.clear()
            self.focus_barcode_box()
            return

        # ---------------------------------------
        # ⭐ เช็คว่าเป็น alias → แปลงเป็นรหัสจริง
        # ---------------------------------------
        real = get_alias(code)
        if real:
            code = real   # ใช้รหัสจริงเสมอ

        # ---------------------------------------
        # โหลดสินค้าจากฐานข้อมูล
        # ---------------------------------------
        product = get_product(code)
        if not product:
            QMessageBox.warning(
                self,
                "ไม่พบสินค้า",
                f"❌ ไม่พบสินค้า\nบาร์โค้ด: {code}"
            )
            self.code_sell.clear()
            self.focus_barcode_box()
            return

        # ---------------------------------------
        # เพิ่มเข้าตะกร้าด้วย real barcode เท่านั้น
        # ---------------------------------------
        real_code = product[0]  # barcode จริงจากฐานข้อมูล

        if real_code in self.cart:
            self.cart[real_code]["qty"] += 1
        else:
            self.cart[real_code] = {
                "name": product[1],
                "price": float(product[2]),
                "qty": 1
            }

        self.refresh_cart()
        self.code_sell.clear()
        self.focus_barcode_box()


    # ===========================================================
    # ปุ่มในแถวสินค้า
    # ===========================================================
    def create_control_buttons(self, code):
        # ⭐ container เต็ม cell (สำคัญมาก)
        container = QWidget()
        container.setStyleSheet("background: transparent;")

        # ⭐ outer คือ layout ตัวใหม่ ที่เราต้องสร้างขึ้นเอง
        outer = QHBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- จัดตำแหน่งปุ่ม ---
        # ตัวเลือก: Qt.AlignLeft / Qt.AlignCenter / Qt.AlignRight
        outer.setAlignment(Qt.AlignCenter)

        # ===== ปุ่มเพิ่ม =====
        btn_plus = QPushButton("เพิ่ม")
        btn_plus.setFixedSize(70, 38)
        btn_plus.setStyleSheet("background:#28a745;color:white;border-radius:8px;font-size:16px;")
        btn_plus.clicked.connect(lambda: self.adjust_qty(code, +1))

        # ===== ปุ่มลด =====
        btn_minus = QPushButton("ลด")
        btn_minus.setFixedSize(70, 38)
        btn_minus.setStyleSheet("background:#ff9800;color:white;border-radius:8px;font-size:16px;")
        btn_minus.clicked.connect(lambda: self.adjust_qty(code, -1))

        # ===== ปุ่มลบ =====
        btn_del = QPushButton("ลบ")
        btn_del.setFixedSize(70, 38)
        btn_del.setStyleSheet("background:#dc3545;color:white;border-radius:8px;font-size:16px;")
        btn_del.clicked.connect(lambda: self.delete_item(code))

        # ===== เพิ่มปุ่มเข้า outer =====
        outer.addWidget(btn_plus)
        outer.addSpacing(6)
        outer.addWidget(btn_minus)
        outer.addSpacing(6)
        outer.addWidget(btn_del)

        return container


    def adjust_qty(self, code, diff):
        if code not in self.cart:
            return

        self.cart[code]["qty"] += diff
        if self.cart[code]["qty"] < 1:
            self.cart[code]["qty"] = 1

        self.refresh_cart()
        QTimer.singleShot(50, self.focus_barcode_box)

    def delete_item(self, code):
        if code in self.cart:
            del self.cart[code]
        self.refresh_cart()
        QTimer.singleShot(50, self.focus_barcode_box)

    # ===========================================================
    # Refresh ตาราง
    # ===========================================================
    def refresh_cart(self):
        items = list(self.cart.items())[::-1]  # เรียงใหม่ล่าสุดขึ้นบน

        self.cart_table.setRowCount(len(items))
        total = 0

        for r, (code, item) in enumerate(items):
            row_id = r + 1
            values = [row_id, code, item["name"], f"{item['price']:.2f}", item["qty"]]


            for c in range(5):  # ID, barcode, name, price, qty
                cell = QTableWidgetItem(str(values[c]))
                cell.setTextAlignment(Qt.AlignCenter)
                self.cart_table.setItem(r, c, cell)


            self.cart_table.setCellWidget(r, 5, self.create_control_buttons(code))

            self.cart_table.setRowHeight(r, 50)

            total += item["price"] * item["qty"]

        self.result_label.setText(f"รวมทั้งหมด: {total:.2f} บาท")

        try:
            self.app.display_win.update_display(self.cart)
        except:
            pass

    # ===========================================================
    # ล้างตะกร้า
    # ===========================================================
    def clear_cart(self):
        self.cart.clear()
        self.cart_table.setRowCount(0)
        self.result_label.setText("รวมทั้งหมด: 0.00 บาท")
        QTimer.singleShot(50, self.focus_barcode_box)

    # ===========================================================
    # ยืนยันขาย
    # ===========================================================
    def confirm_sale(self):
        if not self.cart:
            QMessageBox.warning(self, "แจ้งเตือน", "ยังไม่มีสินค้า")
            QTimer.singleShot(50, self.focus_barcode_box)
            return

        subtotal = sum(item["price"] * item["qty"] for item in self.cart.values())

        self.paywin = PaymentWindow(subtotal, self.on_payment_confirm)
        self.paywin.show()
        self.paywin.raise_()
        self.paywin.activateWindow()

    # ===========================================================
    # เมื่อยืนยันเงินทอน
    # ===========================================================
    def on_payment_confirm(self, cash, change):

        subtotal = sum(item["price"] * item["qty"] for item in self.cart.values())

        items = [{
            "name": it["name"],
            "qty": it["qty"],
            "price": float(it["price"]),
            "total": float(it["price"] * it["qty"])
        } for it in self.cart.values()]

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        receipt_no = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        meta = {
            "shop_name": self.app.SHOP_NAME,
            "shop_addr": self.app.SHOP_ADDR,
            "tax_id": self.app.SHOP_TAXID,
            "cashier": self.app.CASHIER_NAME,
            "receipt_no": receipt_no,
            "dt": now,
            "subtotal": subtotal,
            "cash": cash,
            "change": change
        }

        self.app.last_receipt = (items, meta)

        for code, item in self.cart.items():
            update_stock(code, item["qty"])

        save_sale(receipt_no, subtotal, cash, change, items)

        try:
            self.app.display_win.update_change(float(change))
        except:
            pass

        QMessageBox.information(
            self,
            "ขายสำเร็จ",
            f"✔ ยอดรวม {subtotal:.2f}\nรับเงิน {cash:.2f}\nเงินทอน {change:.2f}"
        )

        if self.enable_print:
            print_receipt(items, meta)

        self.cart.clear()
        self.refresh_cart()
        self.result_label.setText("รวมทั้งหมด: 0.00 บาท")

        # รีเซ็ตหน้าจอลูกค้า
        try:
            self.app.display_win.update_display({})
        except:
            pass

        QTimer.singleShot(150, self.focus_barcode_box)

    # ===========================================================
    # กดปุ่มใดๆ ให้กลับไปที่ช่องบาร์โค้ด
    # ===========================================================
    def eventFilter(self, obj, event):

        # ⭐ เมื่อช่องบาร์โค้ดถูกโฟกัส → บังคับภาษาอังกฤษ
        if obj == self.code_sell and event.type() == QEvent.FocusIn:
            self.force_english_keyboard()

        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            QTimer.singleShot(50, self.focus_barcode_box)
            
        # ⭐⭐ ฟีเจอร์ใหม่ — กด ENTER ตรงไหนก็ได้ → กลับไปช่องบาร์โค้ด
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                QTimer.singleShot(50, self.focus_barcode_box)
                return True   # ดักไม่ให้ส่ง event ต่อ

        return super().eventFilter(obj, event)


    # ===========================================================
    # toggle ปริ้นใบเสร็จ
    # ===========================================================
    def toggle_print(self):
        self.enable_print = not self.enable_print

        if self.enable_print:
            self.btn_toggle_print.setText("🖨️ ปริ้นใบเสร็จ: เปิด")
            self.btn_toggle_print.setStyleSheet("background:#4CAF50;color:white;font-size:16px;")
        else:
            self.btn_toggle_print.setText("🖨️ ปริ้นใบเสร็จ: ปิด")
            self.btn_toggle_print.setStyleSheet("background:#B71C1C;color:white;font-size:16px;")

        self.app.enable_print = self.enable_print

        QTimer.singleShot(50, self.focus_barcode_box)

    def refresh(self):
        pass
