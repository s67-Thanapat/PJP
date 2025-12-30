import ctypes
import os
import json
from PySide6.QtGui import QColor, QPen
from functools import partial
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView,
    QPushButton, QHBoxLayout, QHeaderView, QStyledItemDelegate, QComboBox,
    QMessageBox, QInputDialog, QDialog
)
from PySide6.QtCore import Qt

from PySide6.QtGui import QFont

from db import add_product, get_product, add_category, get_categories

TEMP_FILE = "import_pending.json"
from PySide6.QtWidgets import QStyledItemDelegate

def force_focus(widget):
    QTimer.singleShot(120, widget.setFocus)

class ComboPlaceholderDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = index.data()
        combo = option.widget

        # ถ้าเป็น placeholder (แถวแรก)
        if index.row() == 0 and combo.property("isPlaceholder"):
            option.palette.setColor(option.palette.Text, QColor("#999999"))

        super().paint(painter, option, index)

class BarcodeDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignCenter)

        # บังคับภาษาอังกฤษ
        try:
            parent_widget = index.model().parent().parent()
            parent_widget.force_english_keyboard()
        except:
            pass
        return editor

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.DisplayRole) or "")

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        model.setData(index, text, Qt.EditRole)

        

class CenterNumberDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignCenter)
        editor.setFrame(False)
        return editor

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.DisplayRole) or "")

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        model.setData(index, text, Qt.EditRole)

        


# ===========================================================
# 🔥 Inline Editor Delegate (กัน focus หลุด + กรอบแดง)
# ===========================================================
class NameColumnDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignCenter)
        editor.setFrame(False)

        # เคลียร์ error flag เมื่อพิมพ์
        
        return editor

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.DisplayRole) or "")

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        model.setData(index, text, Qt.EditRole)

        if text:
            model.setData(index, None, Qt.UserRole)

        

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.data(Qt.UserRole) == "error":
            painter.save()
            pen = QPen(Qt.red, 2)
            painter.setPen(pen)
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
            painter.restore()


class SafeHeader(QHeaderView):
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()


# ===========================================================
#                     ImportTab
# ===========================================================
class ImportTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app

        self.scan_buffer = ""
        self.category_list = get_categories()

        # ระบบหมวดหลัก–หมวดย่อย (Auto)
        self.auto_main_mode = False
        self.auto_sub_mode = False
        self.locked_main_category = None
        self.locked_sub_category = None

        # โหมด Auto category แบบเก่า (ยังเผื่อไว้)
        self.auto_category_mode = False
        self.locked_category = None

        self.build_ui()

        self.installEventFilter(self)
        QTimer.singleShot(200, self.focus_barcode_box)

        # โหลดแถวค้างไว้
        self.load_pending_rows()

    def safe_focus_barcode(self):
        """รอให้ editor ถูกปิดก่อน แล้วค่อย focus ช่องบาร์โค้ด"""
        QTimer.singleShot(50, lambda: self.input_barcode.setFocus())


    # ----------------------------------------------------------
    # เติมข้อมูลจาก stock เดิมอัตโนมัติ (ถ้ามีใน DB)
    # ----------------------------------------------------------
    def auto_fill_product(self, row):
        code_item = self.add_table.item(row, 1)
        if not code_item:
            return

        code = code_item.text().strip()
        if not code:
            return

        product = get_product(code)
        if not product:
            return

        # DB คืนค่า 7 ช่อง
        barcode, name, price, cost, qty, main_cat, sub_cat = product


        if name and not self.add_table.item(row, 2).text().strip():
            self.add_table.item(row, 2).setText(name)

        if price and not self.add_table.item(row, 3).text().strip():
            self.add_table.item(row, 3).setText(str(price))

        if cost and not self.add_table.item(row, 4).text().strip():
            self.add_table.item(row, 4).setText(str(cost))

        combo_main = self.add_table.cellWidget(row, 6)
        if main_cat:
            combo_main.setCurrentText(main_cat)

        # ----------------------------------------------------------
    # Refresh จาก StockTab (เมื่อสต็อกเซฟ)
    # ----------------------------------------------------------
    def refresh(self):
        """รีเฟรชข้อมูลหมวดหมู่ / combobox / แถวค้าง"""
        try:
            self.reload_category_list()
        except:
            pass

        try:
            self.refresh_all_category_combobox()
        except:
            pass

        try:
            self.load_pending_rows()
        except:
            pass

        force_focus(self.input_barcode)




    def mark_combo_error(self, combo):
        combo.setStyleSheet("""
            QComboBox {
                border: 2px solid red;
                border-radius: 6px;
                padding-left: 6px;
                background: white;
            }
        """)


    def clear_combo_error(self, combo):
        combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding-left: 6px;
                background: white;
            }
        """)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_import_tab()

    # ----------------------------------------------------------
    def update_category_header_style(self):
        # ใช้กับโหมด auto_category_mode แบบเก่า (หมวดเดียว)
        if self.auto_category_mode:
            # column 6 (index) = หมวดหลัก → header ลำดับที่ 7
            self.add_table.setStyleSheet("""
                QTableWidget#addTable QHeaderView::section {
                    background-color: #0091ff;
                    color: white;
                    font-weight: bold;
                }
                QTableWidget#addTable QHeaderView::section:nth-child(7) {
                    background-color: #00c8ff;
                    color: white;
                    font-weight: bold;
                }
            """)
        else:
            self.add_table.setStyleSheet("""
                QTableWidget#addTable QHeaderView::section {
                    background-color: #28a745;
                    color: white;
                    font-weight: bold;
                }
            """)

    # ----------------------------------------------------------
    # ตั้ง focus ไปช่องบาร์โค้ด
    # ----------------------------------------------------------
    def focus_barcode_box(self):
        try:
            self.input_barcode.setFocus()
        except:
            pass

    # ================================
    # แปลงคีย์ไทย → ตัวเลข
    # ================================
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

    # ================================
    # แปลงเลขไทย → อารบิก
    # ================================
    def convert_thai_digits(self, text):
        thai_digits = "๐๑๒๓๔๕๖๗๘๙"
        arabic_digits = "0123456789"
        return text.translate(str.maketrans(thai_digits, arabic_digits))
    
    
    def force_english_keyboard(self):
        try:
            layout = ctypes.windll.user32.LoadKeyboardLayoutW("00000409", 1)
            ctypes.windll.user32.ActivateKeyboardLayout(layout, 0)
        except Exception as e:
            print("Keyboard switch failed:", e)

    # ----------------------------------------------------------
    # UI หลัก
    # ----------------------------------------------------------
    def build_ui(self):
        layout = QVBoxLayout()

        lbl = QLabel("➕ เพิ่มสินค้าเข้าสต็อก (หลายรายการ)")
        lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        layout.addWidget(lbl)

        # ---------- แถวบน ----------
        top_row = QHBoxLayout()

        self.input_barcode = QLineEdit()
        self.input_barcode.setPlaceholderText("สแกนหรือกรอกบาร์โค้ดสินค้า...")
        self.input_barcode.setFixedHeight(40)
        self.input_barcode.returnPressed.connect(self.add_from_input)

        self.btn_add_input = QPushButton("➕ เพิ่มเข้าตาราง")
        self.btn_add_input.clicked.connect(self.add_row)

        top_row.addWidget(self.input_barcode)
        top_row.addWidget(self.btn_add_input)
        layout.addLayout(top_row)

        # ---------- ตาราง ----------
        self.add_table = QTableWidget()
        self.add_table.setObjectName("addTable")
        
        self.add_table.setColumnCount(9)
        self.add_table.setHorizontalHeaderLabels(
            ["ID", "บาร์โค้ด", "ชื่อสินค้า", "ราคา", "ราคาทุน",
             "จำนวน", "หมวดหลัก", "หมวดย่อย", "จัดการ"]
        )

        header = self.add_table.horizontalHeader()
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        header.setSectionResizeMode(7, QHeaderView.Fixed)


        # === FIXED columns ===
        fixed_columns = {
            0: 60,    # ID
            1: 200,   # Barcode
            3: 120,   # Price
            4: 120,   # Cost
            5: 120,   # Qty
            6: 200,   # Main category
            7: 200,   # Sub category
            8: 240,   # Controls
        }

        for col, width in fixed_columns.items():
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.add_table.setColumnWidth(col, width)

        # === ONLY column that stretches ===
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # ชื่อสินค้า


        # ⭐⭐⭐ ปิด vertical header หลังจาก setup header เสร็จ ⭐⭐⭐
        self.add_table.verticalHeader().setVisible(False)


        # แก้ไขได้ด้วย single-click เหมือนเดิม
        self.add_table.setEditTriggers(QAbstractItemView.SelectedClicked)
        self.add_table.setItemDelegateForColumn(1, BarcodeDelegate(self.add_table))


        # delegate barcode
        self.add_table.setItemDelegateForColumn(1, BarcodeDelegate(self.add_table))

        # ชื่อสินค้า
        self.add_table.setItemDelegateForColumn(2, NameColumnDelegate(self.add_table))

        # คอลัมน์ตัวเลข
        num_delegate = CenterNumberDelegate(self.add_table)
        self.add_table.setItemDelegateForColumn(3, num_delegate)
        self.add_table.setItemDelegateForColumn(4, num_delegate)
        self.add_table.setItemDelegateForColumn(5, num_delegate)



        # event cell
        self.add_table.cellClicked.connect(self.handle_cell_click)
        self.add_table.cellDoubleClicked.connect(self.handle_cell_double_click)

        # header click → โหมด Auto หมวดหลัก/หมวดย่อย
        
        
        header.sectionClicked.connect(self.handle_header_click)

        layout.addWidget(self.add_table)

        # ---------- ปุ่มล่าง ----------
        btns = QHBoxLayout()
        btns.setAlignment(Qt.AlignLeft)

        btn_alias = QPushButton("⚙ ตั้งค่าบาร์โค้ดเทียบเท่า")
        btn_alias.clicked.connect(self.open_alias_popup)
        btns.addWidget(btn_alias)

        btns.addStretch()
        btn_clear = QPushButton("🗑️ ลบทั้งหมด")
        btn_clear.clicked.connect(self.clear_all)
        btns.addWidget(btn_clear)

        btn_save = QPushButton("💾 บันทึกสินค้าทั้งหมด")
        btn_save.clicked.connect(self.save_all_products)
        btns.addWidget(btn_save)

        layout.addLayout(btns)
        self.setLayout(layout)

    def refresh_import_tab(self):
        
        # โหลดหมวดหลักใหม่
        self.reload_category_list()

        # รีเฟรช combobox ทุกแถว
        self.refresh_all_category_combobox()

        # โหลด pending rows ใหม่ (เผื่อมีการแก้ไฟล์)
        self.load_pending_rows()

        # ตั้ง focus ใหม่
        QTimer.singleShot(100, self.focus_barcode_box)



    # ----------------------------------------------------------
    # Header click → Auto หมวดหลัก/หมวดย่อย
    # ----------------------------------------------------------
    def handle_header_click(self, column):

        # column 6 = หมวดหลัก
        if column == 6:
            self.auto_main_mode = not self.auto_main_mode
            header = self.add_table.horizontalHeaderItem(6)


            if self.auto_main_mode:
                header.setText("หมวดหลักAuto")
                if self.add_table.rowCount() > 0:
                    first = self.add_table.cellWidget(0, 6)
                    main = first.currentText() if first else ""
                    if not main:
                        QMessageBox.warning(self, "ผิดพลาด", "กรุณาเลือกหมวดหลักในแถวแรกก่อน")
                        self.auto_main_mode = False
                        header.setText("หมวดหลัก")
                        return
                    self.locked_main_category = main
                    self.apply_locked_main()
            else:
                header.setText("หมวดหลัก")
                self.locked_main_category = None
                self.highlight_auto_rows()

            return

        # column 7 = หมวดย่อย
        if column == 7:
            self.auto_sub_mode = not self.auto_sub_mode
            header = self.add_table.horizontalHeaderItem(7)

            if self.auto_sub_mode:
                header.setText("หมวดย่อยAuto")
                if self.add_table.rowCount() > 0:
                    first = self.add_table.cellWidget(0, 7)
                    sub = first.currentText() if first else ""
                    if not sub or sub == "เลือกหมวดหลักก่อน":
                        QMessageBox.warning(self, "ผิดพลาด", "กรุณาเลือกหมวดย่อยในแถวแรกก่อน")
                        self.auto_sub_mode = False
                        header.setText("หมวดย่อย")
                        return
                    self.locked_sub_category = sub
                    self.apply_locked_sub()
            else:
                header.setText("หมวดย่อย")
                self.locked_sub_category = None
                self.highlight_auto_rows()
            return
        self.highlight_auto_rows()

    def apply_locked_main(self):
        if not self.locked_main_category:
            return
        for r in range(self.add_table.rowCount()):
            combo = self.add_table.cellWidget(r, 6)
            if combo:
                combo.setCurrentText(self.locked_main_category)
        self.highlight_auto_rows()

    def apply_locked_sub(self):
        if not self.locked_sub_category:
            return
        for r in range(self.add_table.rowCount()):
            combo = self.add_table.cellWidget(r, 7)
            if combo:
                combo.setCurrentText(self.locked_sub_category)
        self.highlight_auto_rows()

    def highlight_auto_rows(self):
        rows = self.add_table.rowCount()

        for r in range(rows):
            for c in (6, 7):
                widget = self.add_table.cellWidget(r, c)

                widget.setStyleSheet("""
                    QComboBox {
                        border: 1px solid #cccccc;
                        border-radius: 6px;
                        padding: 4px;
                        background: white;
                    }
                """)

                if widget.property("isPlaceholder") and widget.currentIndex() == 0:
                    widget.setProperty("isPlaceholder", True)
                else:
                    widget.setProperty("isPlaceholder", False)

                                

        # Auto main
        if self.auto_main_mode and self.locked_main_category:
            for r in range(rows):
                main = self.add_table.cellWidget(r, 6).currentText()
                if main == self.locked_main_category:
                    self.add_table.cellWidget(r, 6).setStyleSheet("""
                        QComboBox {
                            border: 3px solid #0099ff;
                            border-radius: 6px;
                            padding: 4px;
                        }
                    """)

        # Auto sub
        if self.auto_sub_mode and self.locked_sub_category:
            for r in range(rows):
                sub = self.add_table.cellWidget(r, 7).currentText()
                if sub == self.locked_sub_category:
                    self.add_table.cellWidget(r, 7).setStyleSheet("""
                        QComboBox {
                            border: 3px solid #0099ff;
                            border-radius: 6px;
                            padding: 4px;
                        }
                    """)

        
            

    def fill_empty_barcodes_with_nan(self):
        rows = self.add_table.rowCount()
        for r in range(rows):
            item = self.add_table.item(r, 1)  # คอลัมน์บาร์โค้ด
            if not item or item.text().strip() == "":
                if not item:
                    item = QTableWidgetItem("ไม่มีบาร์โค้ด")
                    self.add_table.setItem(r, 1, item)
                else:
                    item.setText("ไม่มีบาร์โค้ด")



    # ----------------------------------------------------------
    # จัดการคลิกเซลล์
    # ----------------------------------------------------------
    def handle_cell_click(self, row, col):
        # ❗ บล็อกการคลิกหมวดย่อย ถ้ายังไม่ได้เลือกหมวดหลัก
        if col == 7:  # หมวดย่อย
            main = self.add_table.cellWidget(row, 6).currentText().strip()
            if not main or main == "เลือกหมวดหลัก":
                QMessageBox.warning(self, "ผิดพลาด", "เลือกหมวดหลักก่อน")
                return
        # ============================
        # ⭐ บังคับภาษาอังกฤษเมื่อคลิกช่องบาร์โค้ด
        # ============================
        if col == 1:   # column barcode
            try:
                self.force_english_keyboard()
            except:
                pass
        item = self.add_table.item(row, col)
        # ห้ามแก้ไขหมวดหลัก/หมวดย่อย (ใช้ combobox)
        if col in (6, 7):
            return

        if item:
            self.add_table.editItem(item)

        # ถ้าคลิกที่ "บาร์โค้ด" → auto fill ถ้ามีใน stock
        if col == 1:
            QTimer.singleShot(10, lambda: self.auto_fill_product(row))

    def handle_cell_double_click(self, row, col):
        if col in (6, 7):
            return
        item = self.add_table.item(row, col)
        if item:
            self.add_table.editItem(item)

    # สำหรับโหมด Auto แบบเก่า (หมวดเดียว)
    def apply_locked_category(self):
        if not self.locked_category:
            return
        for r in range(self.add_table.rowCount()):
            combo = self.add_table.cellWidget(r, 6)
            if combo:
                combo.setCurrentText(self.locked_category)

    # ----------------------------------------------------------
    # ปุ่มจัดการจำนวน
    # ----------------------------------------------------------
    def create_control_buttons(self, row):
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        btn_plus = QPushButton("เพิ่ม")
        btn_plus.setStyleSheet("background:#28a745;color:white;border-radius:8px;")
        btn_plus.clicked.connect(lambda r=row: self.adjust_qty(r, +1))

        btn_minus = QPushButton("ลด")
        btn_minus.setStyleSheet("background:#ff9800;color:white;border-radius:8px;")
        btn_minus.clicked.connect(lambda r=row: self.adjust_qty(r, -1))

        btn_del = QPushButton("ลบ")
        btn_del.setStyleSheet("background:#dc3545;color:white;border-radius:8px;")
        btn_del.setProperty("row", row)
        btn_del.clicked.connect(self.delete_row_dynamic)

        layout.addWidget(btn_plus)
        layout.addWidget(btn_minus)
        layout.addWidget(btn_del)

        widget.setLayout(layout)
        return widget

    # หลังลบ row แล้วให้ reindex ID
    def renumber_ids(self):
        for r in range(self.add_table.rowCount()):
            item = self.add_table.item(r, 0)
            if not item:
                item = QTableWidgetItem()
                self.add_table.setItem(r, 0, item)
            item.setText(str(r + 1))
            item.setFlags(Qt.ItemIsEnabled)
            item.setTextAlignment(Qt.AlignCenter)

    def delete_row_dynamic(self):
        btn = self.sender()
        row = btn.property("row")

        if row is None:
            return

        if 0 <= row < self.add_table.rowCount():
            self.add_table.removeRow(row)

        # update row index ให้ปุ่มลบ + ID
        self.refresh_delete_button_rows()
        self.renumber_ids()

        self.save_pending_rows()
        force_focus(self.input_barcode)


    def refresh_delete_button_rows(self):
        for r in range(self.add_table.rowCount()):
            widget = self.add_table.cellWidget(r, 8)  # ปุ่มอยู่ col 8
            if widget:
                layout = widget.layout()
                btn_del = layout.itemAt(2).widget()
                btn_del.setProperty("row", r)

    # ----------------------------------------------------------
    # Combobox หมวดย่อย / หมวดหลัก
    # ----------------------------------------------------------
    def create_sub_category_box(self, row):
        combo = QComboBox()
        combo.setFixedHeight(48)
        combo.setEditable(False)

        # ⭐ Placeholder (แสดงเฉพาะบนกล่อง)
        combo.setPlaceholderText("เลือกหมวดย่อย")

        # ⭐ สไตล์ให้ placeholder สีเทาจาง
        combo.setStyleSheet("""
            QComboBox {
                color: #aaaaaa;
                padding-left: 6px;
            }
            QComboBox:enabled {
                color: #000000;
            }
            QComboBox::placeholder {
                color: #aaaaaa;
            }
        """)

        # ⭐ dropdown จะถูกเติมภายหลัง เมื่อเลือกหมวดหลัก
        combo.addItem("➕ เพิ่มหมวดย่อย")  # index 0
        # แต่เรา **ไม่** ตั้ง currentIndex → ให้เป็น -1 แทน

        combo.setCurrentIndex(-1)   # ⭐ แสดง placeholder

        combo.currentIndexChanged.connect(
            lambda: self.handle_sub_category_select(combo, row)
        )

        return combo


    def create_main_category_box(self, row):
        combo = QComboBox()
        combo.setFixedHeight(48)
        combo.setEditable(False)

        # ⭐ Placeholder ตอนแสดงผล
        combo.setPlaceholderText("เลือกหมวดหมู่")
        combo.setCurrentText("")

        # ⭐ สไตล์ placeholder สีเทา
        combo.setStyleSheet("""
            QComboBox {
                color: #000000;
                padding-left: 6px;
            }
            QComboBox::placeholder {
                color: #aaaaaa;
            }
        """)

        # ⭐ เพิ่มตัวเลือก "ไม่มีหมวดหมู่" เป็นค่าเก็บจริง
        combo.addItem("ไม่มีหมวดหมู่")

        # ⭐ เพิ่มหมวดหลักทั้งหมด
        for cat in self.category_list:
            combo.addItem(cat)

        # ⭐ ปุ่มเพิ่มหมวด
        combo.addItem("➕ เพิ่มหมวดหลัก")

        combo.currentIndexChanged.connect(
            lambda: self.handle_main_category_select(combo, row)
        )

        return combo



    def handle_main_category_select(self, combo_main, row):
        main = combo_main.currentText().strip()
        combo_sub = self.add_table.cellWidget(row, 7)

        # ---------------------------------------------------------
        # (1) เพิ่มหมวดหลักใหม่
        # ---------------------------------------------------------
        if main == "➕ เพิ่มหมวดหลัก":
            new_cat, ok = QInputDialog.getText(self, "เพิ่มหมวดหลัก", "ชื่อหมวดหลัก:")
            new_cat = new_cat.strip()

            if ok and new_cat:
                # ⭐⭐ ตรวจสอบชื่อซ้ำ ⭐⭐
                if new_cat in self.category_list:
                    QMessageBox.warning(self, "ซ้ำกัน", f"หมวดหลัก '{new_cat}' มีอยู่แล้ว")
                    self.mark_combo_error(combo_main)
                    combo_main.blockSignals(True)
                    combo_main.setCurrentIndex(-1)
                    combo_main.blockSignals(False)
                    return

                # ผ่าน → เพิ่มลงฐานข้อมูล
                add_category(new_cat)
                self.category_list.append(new_cat)

                combo_main.blockSignals(True)
                combo_main.insertItem(combo_main.count() - 1, new_cat)
                combo_main.setCurrentText(new_cat)
                combo_main.blockSignals(False)

                self.clear_combo_error(combo_main)

            else:
                combo_main.setCurrentIndex(-1)
            return

        # -------------------------------------
        # ถ้าเลือกหมวดจริง → เอากรอบแดงออก
        # -------------------------------------
        self.clear_combo_error(combo_main)

        # โหลดหมวดย่อย
        from db import get_subcategories
        subs = get_subcategories(main)

        combo_sub.blockSignals(True)
        combo_sub.clear()

        if subs:
            combo_sub.addItems(subs)

        combo_sub.addItem("➕ เพิ่มหมวดย่อย")
        combo_sub.setCurrentIndex(-1)
        combo_sub.blockSignals(False)

        self.highlight_auto_rows()
        # ⭐ หลังเลือกหมวดหลัก ให้โฟกัสกลับบาร์โค้ด
        try:
            force_focus(self.input_barcode)
        except:
            pass
        force_focus(self.input_barcode)
        QTimer.singleShot(200, lambda: force_focus(self.input_barcode))






    def handle_sub_category_select(self, combo_sub, row):
        text = combo_sub.currentText().strip()
        main_combo = self.add_table.cellWidget(row, 6)
        main = main_combo.currentText().strip()

        # ------------------------------------------
        # (1) กรณีเพิ่มหมวดย่อยใหม่
        # ------------------------------------------
        if text == "➕ เพิ่มหมวดย่อย":

            # ❗ ถ้าหมวดหลักยังไม่เลือก หรือเป็น "ไม่มีหมวดหมู่" → ห้ามเพิ่ม
            if (not main or 
                main in ["เลือกหมวดหลัก", "ไม่มีหมวดหมู่"]):

                QMessageBox.warning(
                    self, "ผิดพลาด",
                    "ไม่สามารถเพิ่มหมวดย่อยได้\nเพราะหมวดหลักเป็น 'ไม่มีหมวดหมู่'"
                )

                combo_sub.blockSignals(True)
                combo_sub.setCurrentIndex(-1)
                combo_sub.blockSignals(False)

                # ❗ ไม่ mark error เพราะไม่ได้ถือว่าเป็นความผิดของผู้ใช้
                return

            # -------------------------------------
            # เพิ่มหมวดย่อยใหม่ (ปกติ)
            # -------------------------------------
            new_sub, ok = QInputDialog.getText(
                self, f"เพิ่มหมวดย่อย ({main})", "ชื่อหมวดย่อย:"
            )
            new_sub = new_sub.strip()

            if ok and new_sub:
                from db import get_subcategories, add_subcategory
                subs = get_subcategories(main)

                # ⭐⭐ เช็คชื่อซ้ำ ⭐⭐
                if new_sub in subs:
                    QMessageBox.warning(
                        self, "ซ้ำกัน",
                        f"หมวดย่อย '{new_sub}' ในหมวด '{main}' มีอยู่แล้ว"
                    )

                    combo_sub.blockSignals(True)
                    combo_sub.setCurrentIndex(-1)
                    combo_sub.blockSignals(False)
                    return

                # ⭐ เพิ่มลง DB
                add_subcategory(main, new_sub)

                combo_sub.blockSignals(True)
                combo_sub.insertItem(combo_sub.count() - 1, new_sub)
                combo_sub.setCurrentText(new_sub)
                combo_sub.blockSignals(False)

            else:
                combo_sub.setCurrentIndex(-1)

            return

        # -------------------------------------
        # ถ้าเลือกหมวดย่อยจริง → เอากรอบแดงออก
        # -------------------------------------
        self.clear_combo_error(combo_sub)

        self.highlight_auto_rows()

        # ⭐ ส่งโฟกัสกลับช่องบาร์โค้ด
        try:
            force_focus(self.input_barcode)
        except:
            pass

        QTimer.singleShot(200, lambda: force_focus(self.input_barcode))



    # ----------------------------------------------------------
    # รีเฟรช combobox ทุกแถว เมื่อเพิ่มหมวดใหม่
    # ----------------------------------------------------------
    def refresh_all_category_combobox(self):
        self.reload_category_list()

        for r in range(self.add_table.rowCount()):
            combo = self.add_table.cellWidget(r, 6)
            if isinstance(combo, QComboBox):
                cur = combo.currentText()

                combo.blockSignals(True)
                combo.clear()

                # ⭐ Placeholder
                combo.addItem("เลือกหมวดหลัก")
                combo.model().item(0).setEnabled(False)

                # ⭐ ตั้ง placeholder property + สี
                combo.setProperty("isPlaceholder", True)
                

                # ใส่หมวดจริง
                for cat in self.category_list:
                    combo.addItem(cat)

                # ปุ่มเพิ่มหมวด
                combo.addItem("➕ เพิ่มหมวดหลัก")

                # restore selection
                if cur and cur in self.category_list:
                    combo.setCurrentText(cur)
                    combo.setProperty("isPlaceholder", False)
                    
                else:
                    combo.setCurrentIndex(0)

                # เพราะ QComboBox ไม่ได้เป็น editable — ใช้ setStyleSheet แทน
                combo.setStyleSheet("""
                    QComboBox {
                        padding-left: 6px;
                        text-align: center;
                    }
                    QComboBox QAbstractItemView {
                        text-align: center;
                    }
                """)

                combo.blockSignals(False)


    def reload_category_list(self):
        from db import get_categories
        self.category_list = get_categories()

    # ----------------------------------------------------------
    # เพิ่มแถวใหม่
    # ----------------------------------------------------------
    def add_row(self):
        row = self.add_table.rowCount()
        self.add_table.insertRow(row)

        # ID
        id_item = QTableWidgetItem(str(row + 1))
        id_item.setFlags(Qt.ItemIsEnabled)
        id_item.setTextAlignment(Qt.AlignCenter)
        self.add_table.setItem(row, 0, id_item)

        # barcode, name, price, cost, qty
        for c in range(1, 6):
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignCenter)
            self.add_table.setItem(row, c, item)

        # --- สร้าง combobox หมวดหลักก่อน ---
        combo_main = self.create_main_category_box(row)
        self.add_table.setCellWidget(row, 6, combo_main)

        # --- สร้าง combobox หมวดย่อย ---
        combo_sub = self.create_sub_category_box(row)
        self.add_table.setCellWidget(row, 7, combo_sub)

        # -------------------------------------------------------
        # ⭐ Apply Auto หมวดหลัก หลัง combo ถูกสร้างแล้ว
        # -------------------------------------------------------
        if self.auto_main_mode and self.locked_main_category:
            combo_main.setCurrentText(self.locked_main_category)

        # ⭐ Apply Auto หมวดย่อย หลัง combo ถูกสร้างแล้ว
        if self.auto_sub_mode and self.locked_sub_category:
            combo_sub.setCurrentText(self.locked_sub_category)

        # ปุ่มควบคุม
        self.add_table.setCellWidget(row, 8, self.create_control_buttons(row))

        self.add_table.setRowHeight(row, 60)
        self.highlight_auto_rows()

        force_focus(self.input_barcode)


    # ----------------------------------------------------------
    def delete_row(self, row):
        if row < self.add_table.rowCount():
            self.add_table.removeRow(row)
        self.renumber_ids()
        self.save_pending_rows()
        force_focus(self.input_barcode)


    def clear_all(self):
        self.add_table.setRowCount(0)
        self.save_pending_rows()
        force_focus(self.input_barcode)


    # ----------------------------------------------------------
    # จำนวน
    # ----------------------------------------------------------
    def adjust_qty(self, row, diff):
        item = self.add_table.item(row, 5)  # col 5 = จำนวน
        qty = int(item.text() or "0") + diff
        qty = max(1, qty)
        item.setText(str(qty))
        self.save_pending_rows()
        # ⭐ Force Focus
        force_focus(self.input_barcode)


    # ----------------------------------------------------------
    # สแกนบาร์โค้ด / กด Enter
    # ----------------------------------------------------------
    def add_from_input(self):
        raw = self.input_barcode.text().strip()
        if not raw:
            return

        code = self.convert_thai_digits(raw)
        code = self.convert_thai_keyboard_barcode(code)

        self.input_barcode.clear()
        self.add_row_by_scan(code)

    def add_row_by_scan(self, code):
        QTimer.singleShot(10, lambda: self._add_row_by_scan(code))

    def _add_row_by_scan(self, code):
        code = self.convert_thai_digits(code)
        code = self.convert_thai_keyboard_barcode(code)

        from db import get_alias
        real = get_alias(code)
        if real:
            code = real

        rows = self.add_table.rowCount()

        # ซ้ำ → เพิ่มจำนวน
        for r in range(rows):
            bc_item = self.add_table.item(r, 1)
            if bc_item and bc_item.text() == code:
                qty_item = self.add_table.item(r, 5)
                qty_item.setText(str(int(qty_item.text() or "0") + 1))
                self.save_pending_rows()
                force_focus(self.input_barcode)

                return

        # ไม่ซ้ำ → สร้างแถวใหม่
        self.add_row()
        row = self.add_table.rowCount() - 1

        self.add_table.item(row, 1).setText(code)

        product = get_product(code)
        if product:

            # ตรงกับโครงสร้าง DB จริง
            barcode_db, name, price, cost, qty, main_cat, sub_cat = product

            self.add_table.item(row, 2).setText(str(name or ""))
            self.add_table.item(row, 3).setText(str(price or 0))
            self.add_table.item(row, 4).setText(str(cost or 0))
            self.add_table.item(row, 5).setText("1")

            combo_main = self.add_table.cellWidget(row, 6)
            combo_sub = self.add_table.cellWidget(row, 7)

            if main_cat:
                combo_main.setCurrentText(main_cat)
            if sub_cat:
                combo_sub.setCurrentText(sub_cat)

        else:
            self.add_table.item(row, 2).setText("")
            self.add_table.item(row, 3).setText("0")
            self.add_table.item(row, 4).setText("0")
            self.add_table.item(row, 5).setText("1")

        self.save_pending_rows()
        force_focus(self.input_barcode)



    # ----------------------------------------------------------
    # validate ก่อนเซฟ (ถ้าอยากใช้)
    # ----------------------------------------------------------
    def validate_rows_before_save(self):
        rows = self.add_table.rowCount()

        for r in range(rows):
            name_item = self.add_table.item(r, 2)  # col 2 = ชื่อสินค้า
            name = name_item.text().strip() if name_item else ""

            if not name:
                name_item.setData(Qt.UserRole, "error")
                self.add_table.setCurrentCell(r, 2)
                self.add_table.editItem(name_item)

                QMessageBox.warning(self, "ข้อมูลไม่ครบ",
                                    f"แถวที่ {r+1}: โปรดใส่ชื่อสินค้า")
                return False
            else:
                name_item.setData(Qt.UserRole, None)

        return True

    # ----------------------------------------------------------
    # บันทึกลงฐานข้อมูล + ล้าง pending
    # ----------------------------------------------------------
    def save_all_products(self):
        rows = self.add_table.rowCount()
        saved = 0

        for r in range(rows):
            code_item = self.add_table.item(r, 1)
            if not code_item:
                continue
            code = code_item.text().strip()

            name_item = self.add_table.item(r, 2)
            name = name_item.text().strip() if name_item else ""

            # validate ชื่อ
            if not name:
                if name_item:
                    name_item.setData(Qt.UserRole, "error")
                QMessageBox.warning(
                    self, "ข้อมูลไม่ครบ",
                    f"แถวที่ {r+1} โปรดใส่ชื่อสินค้า"
                )
                self.add_table.setCurrentCell(r, 2)
                if name_item:
                    self.add_table.editItem(name_item)
                return

            if name_item:
                name_item.setData(Qt.UserRole, None)

            price = float(self.add_table.item(r, 3).text() or 0)
            cost  = float(self.add_table.item(r, 4).text() or 0)
            qty   = int(self.add_table.item(r, 5).text() or 0)

            combo_main = self.add_table.cellWidget(r, 6)
            combo_sub  = self.add_table.cellWidget(r, 7)

            # ----- หมวดหลัก -----
            if combo_main:
                main_text = (combo_main.currentText() or "").strip()
                main_index = combo_main.currentIndex()
            else:
                main_text = ""
                main_index = -1

            main_cat = (
                main_text
                if main_text and not main_text.startswith(("เลือก", "กรุณา", "➕")) and main_index != -1
                else "ไม่มีหมวดหมู่"
            )

            # ----- หมวดย่อย -----
            if combo_sub:
                sub_text = (combo_sub.currentText() or "").strip()
                sub_index = combo_sub.currentIndex()
            else:
                sub_text = ""
                sub_index = -1

            sub_cat = (
                sub_text
                if sub_text and not sub_text.startswith(("เลือก", "กรุณา", "➕")) and sub_index != -1
                else "ไม่มีหมวดย่อย"
            )

            # --------- เซฟลง DB ---------
            add_product(code, name, price, cost, qty, main_cat, sub_cat)

            from db import add_history
            add_history(code, name, qty, cost, price)

            saved += 1

        # ====== หลังจากบันทึกครบทุกแถว ======
        QMessageBox.information(self, "สำเร็จ", f"เพิ่มสินค้าแล้ว {saved} รายการ")

        self.add_table.setRowCount(0)
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)

        try:
            self.app.history_tab.refresh_now()
        except:
            pass

        force_focus(self.input_barcode)


    

    # ----------------------------------------------------------
    # Auto-save: เก็บแถวค้างไว้ในไฟล์
    # ----------------------------------------------------------
    def save_pending_rows(self):
        rows = []

        for r in range(self.add_table.rowCount()):
            bc = self.add_table.item(r, 1).text().strip()   # barcode
            name = self.add_table.item(r, 2).text().strip()  # name
            qty = self.add_table.item(r, 5).text().strip()   # qty

            if not (bc or name or qty or 
                    self.add_table.cellWidget(r, 6).currentText() or 
                    self.add_table.cellWidget(r, 7).currentText()):
                continue


            row_data = {
                "barcode": bc,
                "name": name,
                "price": self.add_table.item(r, 3).text(),
                "cost": self.add_table.item(r, 4).text(),
                "qty": qty,
                "main": self.add_table.cellWidget(r, 6).currentText(),
                "sub": self.add_table.cellWidget(r, 7).currentText()
            }
            rows.append(row_data)

        with open(TEMP_FILE, "w", encoding="utf8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    # ----------------------------------------------------------
    # โหลดแถวค้างจากไฟล์
    # ----------------------------------------------------------
    def load_pending_rows(self):
        if not os.path.exists(TEMP_FILE):
            return

        try:
            data = json.load(open(TEMP_FILE, "r", encoding="utf8"))
        except:
            return

        # ⭐ รวมข้อมูลตาม barcode (ตัวสุดท้ายชนะ)
        merged = {}
        for item in data:
            bc = item.get("barcode", "")

            # ⭐ เก็บแถวว่างไว้ด้วย (ไม่ข้าม)
            if bc:
                key = bc
            else:
                key = f"empty_{len(merged)}"

            merged[key] = item

        # ⭐ รวมกับข้อมูลล่าสุดจากสต็อก
        merged = self.merge_with_stock(merged)

        self.add_table.setRowCount(0)

        from db import get_subcategories

        for bc, item in merged.items():
            self.add_row()
            row = self.add_table.rowCount() - 1

            # ---------- เติมคอลัมน์พื้นฐาน ----------
            self.add_table.item(row, 1).setText(item.get("barcode", ""))
            self.add_table.item(row, 2).setText(item.get("name", ""))
            self.add_table.item(row, 3).setText(str(item.get("price", 0) or 0))
            self.add_table.item(row, 4).setText(str(item.get("cost", 0) or 0))
            self.add_table.item(row, 5).setText(str(item.get("qty", 1) or 1))

            main = (item.get("main", "") or "").strip()
            sub  = (item.get("sub", "") or "").strip()

            combo_main = self.add_table.cellWidget(row, 6)
            combo_sub  = self.add_table.cellWidget(row, 7)

            # ---------- หมวดหลัก ----------
            combo_main.blockSignals(True)

            # ถ้า main เป็น "ไม่มีหมวดหมู่" หรือค่าว่าง → ให้แสดง placeholder "เลือกหมวดหมู่"
            if (not main) or (main == "ไม่มีหมวดหมู่"):
                combo_main.setCurrentIndex(-1)   # ⭐ ให้ placeholder ทำงาน
            else:
                if main in self.category_list:
                    combo_main.setCurrentText(main)
                else:
                    # ถ้าเจอหมวดเก่าที่ไม่มีใน list แล้ว → แทรกเข้าไป
                    combo_main.insertItem(combo_main.count() - 1, main)
                    combo_main.setCurrentText(main)

            combo_main.blockSignals(False)

            # ---------- หมวดย่อย ----------
            # ถ้าไม่มีหมวดหลักจริง ๆ หรือเป็น "ไม่มีหมวดหมู่" → ไม่มีหมวดย่อย
            effective_main = "" if (not main or main == "ไม่มีหมวดหมู่") else main
            subs = get_subcategories(effective_main) if effective_main else []

            combo_sub.blockSignals(True)
            combo_sub.clear()
            combo_sub.addItems(subs)
            combo_sub.addItem("➕ เพิ่มหมวดย่อย")

            # ถ้า sub เป็น "ไม่มีหมวดย่อย" หรือว่าง → ไม่เลือกอะไร (placeholder)
            if (not sub) or (sub == "ไม่มีหมวดย่อย"):
                combo_sub.setCurrentIndex(-1)
            else:
                if sub in subs:
                    combo_sub.setCurrentText(sub)
                else:
                    # ถ้ามีหมวดย่อยที่ไม่อยู่ใน DB แล้ว → แทรกไว้ด้านบน
                    combo_sub.insertItem(0, sub)
                    combo_sub.setCurrentText(sub)

            combo_sub.blockSignals(False)

        self.renumber_ids()


    def merge_with_stock(self, merged_rows):
        """
        merged_rows = dict ที่รวมแถวจาก pending แล้ว (key = barcode)
        คืนค่า dict ใหม่ โดยดึงข้อมูลจาก stock เฉพาะกรณีที่ไม่มีใน pending
        """

        new_data = {}

        for bc, row in merged_rows.items():

            # ⭐ ถ้าเป็นแถวว่าง → ไม่ merge กับ stock
            if not bc or str(bc).startswith("empty_"):
                # เติมค่า default สำหรับหมวด
                main_val = row.get("main", "").strip()
                sub_val = row.get("sub", "").strip()

                if not main_val:
                    main_val = "ไม่มีหมวดหมู่"
                if not sub_val:
                    sub_val = "ไม่มีหมวดย่อย"

                row["main"] = main_val
                row["sub"] = sub_val
                new_data[bc] = row
                continue

            # ดึงสินค้าในสต็อก
            product = get_product(bc)

            # ====================================================
            # ⭐ ดึงค่าที่ผู้ใช้เลือกไว้ก่อน (pending rows)
            # ====================================================
            pending_main = (row.get("main", "") or "").strip()
            pending_sub = (row.get("sub", "") or "").strip()

            # ถ้าไม่มี → ใส่ default
            if not pending_main or pending_main in ["เลือกหมวดหลัก", ""]:
                pending_main = "ไม่มีหมวดหมู่"

            if not pending_sub or pending_sub in ["เลือกหมวดย่อย", ""]:
                pending_sub = "ไม่มีหมวดย่อย"

            # ====================================================
            # ⭐ ถ้ามีใน stock → ใช้ข้อมูลสินค้า แต่ **ไม่ทับหมวด**
            # ====================================================
            if product:
                _, name, price, cost, qty, main_cat, sub_cat = product

                new_data[bc] = {
                    "barcode": bc,
                    "name": name,
                    "price": price,
                    "cost": cost,
                    "qty": row.get("qty", "1"),

                    # ⭐ ใช้ค่าที่ pending เลือกไว้ ไม่ใช้ค่าจาก stock
                    "main": pending_main,
                    "sub": pending_sub
                }

            # ====================================================
            # ⭐ ถ้าไม่มีใน stock → ใช้ข้อมูลเดิมจาก pending
            # ====================================================
            else:
                new_data[bc] = {
                    "barcode": bc,
                    "name": row.get("name", ""),
                    "price": row.get("price", 0),
                    "cost": row.get("cost", 0),
                    "qty": row.get("qty", "1"),
                    "main": pending_main,
                    "sub": pending_sub
                }

        return new_data

    # ----------------------------------------------------------
    # ตั้งค่า Alias popup
    # ----------------------------------------------------------
    def open_alias_popup(self):
        self.alias_window = AliasSettingWindow(self)
        self.alias_window.exec()
        force_focus(self.input_barcode)


    # ----------------------------------------------------------
    # Scanner event (ยิงบาร์โค้ดช่วงที่ focus ไม่อยู่ที่ input)
    # ----------------------------------------------------------
    def eventFilter(self, obj, event):
        # ------------------------------
        # 1) ถ้า focus อยู่ใน editor → ห้ามดัก key เด็ดขาด
        # ------------------------------
        from PySide6.QtWidgets import QLineEdit
        if isinstance(self.focusWidget(), QLineEdit):
            return False
        
        # ===============================
        # ⭐ Enter ที่ไหนก็ได้บนหน้า → กลับไปช่องบาร์โค้ด
        # ===============================
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # อย่าทำตอนพิมพ์ใน combobox
            if not isinstance(self.focusWidget(), QComboBox):
                QTimer.singleShot(10, lambda: self.input_barcode.setFocus())
            return False


        # ------------------------------
        # 2) ดักเฉพาะกรณี scanner ยิง "ตอนที่ไม่ได้ focus ช่อง input"
        # ------------------------------
        if event.type() == QEvent.KeyPress:

            fw = self.focusWidget()

            # ถ้าอยู่ใน widget ที่ใช้พิมพ์ → ไม่ดัก
            if isinstance(fw, (QLineEdit, QComboBox)):
                return False

            text = event.text()

            if text and text.isprintable():
                self.scan_buffer += text
                return True  # block scan char
            
            # scanner กด Enter
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                raw_code = self.scan_buffer.strip()
                self.scan_buffer = ""

                if len(raw_code) >= 6:
                    code = self.convert_thai_digits(raw_code)
                    code = self.convert_thai_keyboard_barcode(code)
                    self.add_row_by_scan(code)

                return True

        return super().eventFilter(obj, event)


# ----------------------------------------------------------
# Popup ตั้งค่า Alias
# ----------------------------------------------------------
class AliasSettingWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_tab = parent

        self.setWindowTitle("ตั้งค่าบาร์โค้ดเทียบเท่า")
        self.resize(500, 500)

        layout = QVBoxLayout()

        lbl = QLabel(
            "กำหนดบาร์โค้ดหลายแบบให้เป็นสินค้าเดียวกัน\nเช่น: 8858832701280 = 8858832701464"
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.real = QLineEdit()
        self.real.setPlaceholderText("บาร์โค้ดจริง (หลัก)")
        layout.addWidget(self.real)

        self.alias = QLineEdit()
        self.alias.setPlaceholderText("บาร์โค้ดเทียบเท่า (รอง)")
        layout.addWidget(self.alias)

        btn_add = QPushButton("➕ เพิ่มเทียบเท่า")
        btn_add.clicked.connect(self.add_alias_pair)
        layout.addWidget(btn_add)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["บาร์โค้ดจริง", "บาร์โค้ดเทียบเท่า", "จัดการ"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 150)
        self.table.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.load_alias_table()

    def add_alias_pair(self):
        real = (self.real.text() or "").strip()
        alias = (self.alias.text() or "").strip()

        if not real or not alias:
            QMessageBox.warning(self, "ผิดพลาด", "กรุณากรอกให้ครบทั้ง 2 ช่อง")
            return

        if not real.isdigit() or not alias.isdigit():
            QMessageBox.warning(self, "ผิดพลาด", "บาร์โค้ดต้องเป็นตัวเลขเท่านั้น")
            return

        if real == alias:
            QMessageBox.warning(self, "ผิดพลาด", "สองบาร์โค้ดต้องไม่เหมือนกัน")
            return

        from db import add_alias
        add_alias(real, alias)

        QMessageBox.information(self, "สำเร็จ", f"เพิ่ม {alias} เทียบเท่า {real}")

        self.real.clear()
        self.alias.clear()

        self.load_alias_table()

    def add_alias_row(self, real, alias):
        row = self.table.rowCount()
        self.table.insertRow(row)

        item_real = QTableWidgetItem(real)
        item_real.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 0, item_real)

        item_alias = QTableWidgetItem(alias)
        item_alias.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 1, item_alias)

        btn_delete = QPushButton("ลบ")
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                border-radius: 10px;
                padding: 8px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
        """)
        btn_delete.setFixedWidth(110)
        btn_delete.setFixedHeight(36)
        btn_delete.clicked.connect(lambda: self.delete_alias(alias))

        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(wrapper)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        lay.addWidget(btn_delete)

        self.table.setCellWidget(row, 2, wrapper)

    def delete_alias(self, alias_code):
        from db import delete_alias
        delete_alias(alias_code)

        QMessageBox.information(self, "ลบแล้ว", f"ลบ {alias_code} สำเร็จ")

        # ⭐ โหลดตารางใหม่หลังลบ
        self.load_alias_table()


    def load_alias_table(self):
        from db import get_all_alias
        data = get_all_alias()

        self.table.setRowCount(0)

        for real, alias in data:
            self.add_alias_row(real, alias)
