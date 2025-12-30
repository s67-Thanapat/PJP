from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGridLayout, QMessageBox, QApplication
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt


class PaymentWindow(QWidget):
    def __init__(self, subtotal, callback_confirm):
        super().__init__()
        self.subtotal = subtotal
        self.callback_confirm = callback_confirm
        self.cash_text = ""

        self.build_ui()

    def build_ui(self):
        self.setWindowTitle("รับเงินจากลูกค้า")
        self.showFullScreen()

        # =============================
        # Responsive Scale (แบบจอใหญ่ = ใหญ่ขึ้น)
        # =============================
        screen = QApplication.primaryScreen().geometry()
        H = screen.height()

        base_height = 900        # baseline ของดีไซน์เดิม
        scale = H / base_height

        if scale < 0.75:         # ไม่เล็กเกินไป
            scale = 0.75

        def fs(px):  # font scale
            return int(px * scale)

        def hs(px):  # height scale
            return int(px * scale)

        # =============================
        # Layout หลัก
        # =============================
        main = QVBoxLayout()
        main.setContentsMargins(fs(40), fs(20), fs(40), fs(20))
        main.setSpacing(fs(18))

        # =============================
        # ยอดรวมสินค้า
        # =============================
        lb_total = QLabel(f"ยอดรวมสินค้า: {self.subtotal:,.2f} บาท")
        lb_total.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lb_total.setStyleSheet(f"""
            font-size: {fs(55)}px;
            font-weight: 800;
            color: #333333;
        """)
        main.addWidget(lb_total)

        # =============================
        # ช่องใส่ยอดเงิน
        # =============================
        self.input = QLineEdit()
        self.input.setPlaceholderText("กรุณาใส่ยอดเงิน…")
        self.input.setAlignment(Qt.AlignRight)
        self.input.setReadOnly(True)

        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: white;
                border: {fs(3)}px solid #ccc;
                border-radius: {fs(25)}px;
                padding-right: {fs(25)}px;
                font-size: {fs(50)}px;
                font-weight: 700;           /* ⭐ ทำให้ตัวเลขเป็นตัวหนา */
                min-height: {fs(110)}px;
            }}
            QLineEdit::placeholder {{
                color: #bfbfbf;
                font-size: {fs(42)}px;
            }}
        """)


        main.addWidget(self.input)

        # =============================
        # ปุ่มแบงค์
        # =============================
        bank_row = QHBoxLayout()
        bank_row.setSpacing(fs(18))

        bank_buttons = [
            (1000, "#9e9e9e"),
            (500,  "#7b1fa2"),
            (100,  "#d32f2f"),
            (50,   "#1976d2"),
            (20,   "#4caf50")
        ]

        for value, color in bank_buttons:
            btn = QPushButton(str(value))
            btn.setFont(QFont("Segoe UI", fs(28), QFont.Bold))
            btn.setFixedHeight(hs(70))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{color};
                    color:white;
                    border-radius:{fs(18)}px;
                }}
            """)
            btn.clicked.connect(lambda _, v=value: self.add_cash(v))
            bank_row.addWidget(btn)

        main.addLayout(bank_row)

        # =============================
        # ปุ่มชำระพอดี
        # =============================
        btn_exact = QPushButton("ชำระพอดี")
        btn_exact.setFont(QFont("Segoe UI", fs(32), QFont.Bold))
        btn_exact.setFixedHeight(hs(75))
        btn_exact.setStyleSheet(f"""
            QPushButton {{
                background:#43A047;
                color:white;
                border-radius:{fs(18)}px;
            }}
        """)
        btn_exact.clicked.connect(self.pay_exact)
        main.addWidget(btn_exact)

        # =============================
        # Keypad
        # =============================
        grid = QGridLayout()
        grid.setSpacing(fs(18))

        keys = [
            ["7", "8", "9"],
            ["4", "5", "6"],
            ["1", "2", "3"],
            ["0", ".", None]
        ]

        for r in range(4):
            for c in range(3):

                key = keys[r][c]

                if r == 3 and c == 2:
                    # ปุ่มลบ + ลบทั้งหมด
                    drow = QHBoxLayout()
                    drow.setSpacing(fs(18))

                    btn_del = QPushButton("ลบทีละตัว")
                    btn_del.setFont(QFont("Segoe UI", fs(28), QFont.Bold))
                    btn_del.setFixedHeight(hs(75))
                    btn_del.setStyleSheet(f"""
                        QPushButton {{
                            background:#FFA000;
                            color:white;
                            border-radius:{fs(18)}px;
                        }}
                    """)
                    btn_del.clicked.connect(self.backspace)

                    btn_clear = QPushButton("ลบทั้งหมด")
                    btn_clear.setFont(QFont("Segoe UI", fs(28), QFont.Bold))
                    btn_clear.setFixedHeight(hs(75))
                    btn_clear.setStyleSheet(f"""
                        QPushButton {{
                            background:#D32F2F;
                            color:white;
                            border-radius:{fs(18)}px;
                        }}
                    """)
                    btn_clear.clicked.connect(self.clear_all)

                    drow.addWidget(btn_del)
                    drow.addWidget(btn_clear)
                    grid.addLayout(drow, r, c)
                    continue

                # ปุ่มตัวเลข
                btn = QPushButton(key)
                btn.setFont(QFont("Segoe UI", fs(40), QFont.Bold))
                btn.setFixedHeight(hs(75))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #ffffff;
                        color: #333;
                        border: {fs(3)}px solid #d9d9d9;
                        border-radius: {fs(22)}px;
                        font-size: {fs(40)}px;
                    }}
                    QPushButton:pressed {{
                        background: #f2f2f2;
                    }}
                """)
                btn.clicked.connect(lambda _, k=key: self.press_key(k))
                grid.addWidget(btn, r, c)

        main.addLayout(grid)

        # =============================
        # ปุ่มล่าง
        # =============================
        bottom = QHBoxLayout()
        bottom.setSpacing(fs(18))

        btn_cancel = QPushButton("ยกเลิก")
        btn_cancel.setFont(QFont("Segoe UI", fs(32), QFont.Bold))
        btn_cancel.setFixedHeight(hs(80))
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background:#E53935;
                color:white;
                border-radius:{fs(20)}px;
            }}
        """)
        btn_cancel.clicked.connect(self.close)

        btn_confirm = QPushButton("ยืนยันชำระเงิน")
        btn_confirm.setFont(QFont("Segoe UI", fs(32), QFont.Bold))
        btn_confirm.setFixedHeight(hs(80))
        btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background:#1E88E5;
                color:white;
                border-radius:{fs(20)}px;
            }}
        """)
        btn_confirm.clicked.connect(self.confirm_payment)

        bottom.addWidget(btn_cancel, 1)
        bottom.addWidget(btn_confirm, 2)

        main.addLayout(bottom)
        self.setLayout(main)

    # ============================== LOGIC ==============================
    def press_key(self, key):
        self.cash_text += key
        self.input.setText(self.cash_text)

    def backspace(self):
        self.cash_text = self.cash_text[:-1]
        self.input.setText(self.cash_text)

    def clear_all(self):
        self.cash_text = ""
        self.input.setText("")

    def add_cash(self, value):
        try:
            now = float(self.cash_text or 0)
        except:
            now = 0
        now += value
        self.cash_text = f"{now:.2f}"
        self.input.setText(self.cash_text)

    def pay_exact(self):
        self.cash_text = f"{self.subtotal:.2f}"
        self.input.setText(self.cash_text)

    def confirm_payment(self):
        if not self.cash_text:
            QMessageBox.warning(self, "แจ้งเตือน", "กรุณากรอกจำนวนเงิน")
            return

        try:
            cash = float(self.cash_text)
        except:
            QMessageBox.warning(self, "ผิดพลาด", "จำนวนเงินไม่ถูกต้อง")
            return

        if cash < self.subtotal:
            QMessageBox.warning(self, "ผิดพลาด", "จำนวนเงินไม่พอ")
            return

        change = cash - self.subtotal
        self.callback_confirm(cash, change)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
