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

from PySide6.QtCore import QTimer



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
        # 🔒 flag กัน save ตอนโหลดข้อมูล
        self._loading = False

    def safe_focus_barcode(self):
        """รอให้ editor ถูกปิดก่อน แล้วค่อย focus ช่องบาร์โค้ด"""
        QTimer.singleShot(50, lambda: self.input_barcode.setFocus())

    def schedule_save(self):
        # ❌ ห้าม save ระหว่าง load
        if getattr(self, "_loading_pending", False):
            return

        if not hasattr(self, "_save_timer"):
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self.save_pending_rows)

        self._save_timer.start(300)  # debounce 300ms

    # ----------------------------------------------------------
    # เติมข้อมูลจาก stock เดิมอัตโนมัติ (ถ้ามีใน DB)
    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # เติมข้อมูลจาก stock เดิมอัตโนมัติ (ถ้ามีใน DB)
    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # เติมข้อมูลจาก stock เดิมอัตโนมัติ (แก้ไขดึงราคา + ทุน)
    # ----------------------------------------------------------
    def auto_fill_product(self, row):
        # 1. ดึงบาร์โค้ดจากตาราง
        item_code = self.add_table.item(row, 1)
        if not item_code:
            return

        code = item_code.text().strip()
        if not code:
            return

        # 2. ดึงข้อมูลจาก Database
        product = get_product(code)
        
        # --- DEBUG ---
        print(f"🔍 CHECK DB Row {row}: {product}") 

        if not product:
            return

        try:
            # map ข้อมูล (0=barcode, 1=name, 2=price, 3=cost, ...)
            db_name = product[1]
            db_price = product[2]
            db_cost = product[3]
            db_main = product[5]
            db_sub = product[6]
        except Exception as e:
            print(f"❌ Error Mapping Data: {e}")
            return

        # ==========================================
        # 3. ใส่ชื่อ (Column 2) [จัดกึ่งกลาง]
        # ==========================================
        item_name = self.add_table.item(row, 2)
        if item_name is None:
            item_name = QTableWidgetItem()
            item_name.setTextAlignment(Qt.AlignCenter) # จัดกึ่งกลาง
            self.add_table.setItem(row, 2, item_name)
        
        if db_name:
            item_name.setText(str(db_name))
            item_name.setTextAlignment(Qt.AlignCenter) # ย้ำกึ่งกลาง

        # ==========================================
        # 4. ใส่ราคาขาย (Column 3) [จัดกึ่งกลาง]
        # ==========================================
        try:
            val_price = float(db_price) if db_price is not None else 0.0
            str_price = f"{val_price:g}"
            
            new_item_price = QTableWidgetItem(str_price)
            new_item_price.setTextAlignment(Qt.AlignCenter) # จัดกึ่งกลาง
            self.add_table.setItem(row, 3, new_item_price)
            
        except Exception as e:
            print(f"❌ Error Set Price: {e}")

        # ==========================================
        # 5. ใส่ราคาทุน (Column 4) [จัดกึ่งกลาง]
        # ==========================================
        try:
            val_cost = float(db_cost) if db_cost is not None else 0.0
            str_cost = f"{val_cost:g}"

            new_item_cost = QTableWidgetItem(str_cost)
            new_item_cost.setTextAlignment(Qt.AlignCenter) # จัดกึ่งกลาง
            self.add_table.setItem(row, 4, new_item_cost)
            
        except Exception as e:
             print(f"❌ Error Set Cost: {e}")

        # ==========================================
        # 6. ใส่หมวดหมู่ (Dropdown)
        # ==========================================
        combo_main = self.add_table.cellWidget(row, 6)
        if combo_main and db_main:
            combo_main.setCurrentText(str(db_main))
            # ถ้ามีหมวดย่อย ให้หน่วงเวลาตั้งค่านิดนึง
            if db_sub:
                QTimer.singleShot(100, lambda: self._set_sub_cat_delayed(row, str(db_sub)))

    def _set_sub_cat_delayed(self, row, sub_name):
        combo_sub = self.add_table.cellWidget(row, 7)
        if combo_sub:
            combo_sub.setCurrentText(sub_name)


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

        self.schedule_save()

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
        self.schedule_save()

        force_focus(self.input_barcode)


    def clear_all(self):
        # 1. ล้างตารางหน้าจอ
        self.add_table.setRowCount(0)

        # 2. 🔥 ลบไฟล์ Temp ทิ้งทันที (สำคัญ! เพื่อไม่ให้ข้อมูลผีโผล่มาอีก)
        if os.path.exists(TEMP_FILE):
            try:
                os.remove(TEMP_FILE)
            except:
                pass

        # 3. โฟกัสกลับไปช่องบาร์โค้ด
        force_focus(self.input_barcode)


    # ----------------------------------------------------------
    # จำนวน
    # ----------------------------------------------------------
    def adjust_qty(self, row, diff):
        item = self.add_table.item(row, 5)  # col 5 = จำนวน
        qty = int(item.text() or "0") + diff
        qty = max(1, qty)
        item.setText(str(qty))
        self.schedule_save()

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
                self.schedule_save()

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

        self.schedule_save()

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
        row_count = self.add_table.rowCount()
        
        if row_count == 0:
            QMessageBox.warning(self, "แจ้งเตือน", "ไม่มีข้อมูลสินค้าในตาราง")
            return

        # ถามยืนยันก่อนบันทึก
        confirm = QMessageBox.question(
            self, "ยืนยัน", 
            f"ต้องการบันทึกสินค้า {row_count} รายการหรือไม่?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        saved_count = 0
        error_count = 0
        error_messages = []

        # วนลูปทุกแถวในตาราง
        for row in range(row_count):
            try:
                # --- 1. ดึงข้อมูล ---
                item_code = self.add_table.item(row, 1)
                barcode = item_code.text().strip() if item_code else ""

                item_name = self.add_table.item(row, 2)
                name = item_name.text().strip() if item_name else ""

                item_price = self.add_table.item(row, 3)
                price_text = item_price.text().strip() if item_price else "0"
                price = float(price_text) if price_text else 0.0

                item_cost = self.add_table.item(row, 4)
                cost_text = item_cost.text().strip() if item_cost else "0"
                cost = float(cost_text) if cost_text else 0.0

                item_qty = self.add_table.item(row, 5)
                qty_text = item_qty.text().strip() if item_qty else "1"
                qty = int(float(qty_text)) if qty_text else 1

                # ดึงหมวดหมู่
                combo_main = self.add_table.cellWidget(row, 6)
                main_cat = combo_main.currentText()
                if main_cat in ["เลือกหมวดหลัก", "เลือกหมวดหมู่", "➕ เพิ่มหมวดหลัก"]:
                    main_cat = "ไม่มีหมวดหมู่"

                combo_sub = self.add_table.cellWidget(row, 7)
                sub_cat = combo_sub.currentText()
                if sub_cat in ["เลือกหมวดย่อย", "➕ เพิ่มหมวดย่อย"]:
                    sub_cat = "-"

                # --- 2. Validation ---
                if not barcode:
                    error_messages.append(f"แถวที่ {row+1}: ไม่มีบาร์โค้ด")
                    error_count += 1
                    continue
                
                if not name:
                    error_messages.append(f"แถวที่ {row+1}: ไม่มีชื่อสินค้า")
                    error_count += 1
                    continue

                # --- 3. บันทึกลง DB ---
                success = add_product(barcode, name, price, cost, qty, main_cat, sub_cat)
                
                if success:
                    saved_count += 1
                else:
                    error_messages.append(f"แถวที่ {row+1}: บันทึกไม่สำเร็จ (บาร์โค้ดอาจซ้ำ)")
                    error_count += 1

            except Exception as e:
                print(f"Error saving row {row}: {e}")
                error_messages.append(f"แถวที่ {row+1}: Error ({str(e)})")
                error_count += 1

        # --- 4. สรุปผล ---
        if error_count > 0:
            summary = f"บันทึกสำเร็จ: {saved_count}\nไม่สำเร็จ: {error_count}"
            details = "\n".join(error_messages[:5])
            if len(error_messages) > 5: details += "\n..."
            QMessageBox.warning(self, "บันทึกเสร็จสิ้น (มีข้อผิดพลาด)", f"{summary}\n\nรายละเอียด:\n{details}")
        else:
            QMessageBox.information(self, "สำเร็จ", f"บันทึกสินค้า {saved_count} รายการเรียบร้อยแล้ว!")

        # --- 5. เคลียร์ตารางและไฟล์ทิ้ง (ถ้าไม่มี Error) ---
        if saved_count > 0 and error_count == 0:
            self.clear_all()  # เรียกฟังก์ชัน clear_all ที่แก้แล้วด้านบน
        
        # กรณีมี error บางรายการ จะไม่เคลียร์ เพื่อให้ user แก้ไขรายการที่ผิด
    

    # ----------------------------------------------------------
    # Auto-save: เก็บแถวค้างไว้ในไฟล์
    # ----------------------------------------------------------
    def save_pending_rows(self):
        if getattr(self, "_loading_pending", False):
            return

        rows_data = []
        row_count = self.add_table.rowCount()

        for r in range(row_count):
            def text(col):
                item = self.add_table.item(r, col)
                return item.text().strip() if item else ""

            bc   = text(1)
            name = text(2)
            qty  = text(5)

            combo_main = self.add_table.cellWidget(r, 6)
            combo_sub  = self.add_table.cellWidget(r, 7)

            main = combo_main.currentText().strip() if combo_main and combo_main.currentIndex() >= 0 else ""
            sub  = combo_sub.currentText().strip() if combo_sub and combo_sub.currentIndex() >= 0 else ""

            # ข้ามเฉพาะแถวที่ว่าง 100%
            if not any([bc, name, qty, main, sub]):
                continue

            rows_data.append({
                "barcode": bc if bc else "nan",
                "name": name,
                "price": text(3) or "0",
                "cost":  text(4) or "0",
                "qty":   qty or "1",
                "main":  main,
                "sub":   sub
            })

        if not rows_data:
            print("SKIP SAVE (no rows)")
            return

        with open(TEMP_FILE, "w", encoding="utf8") as f:
            json.dump(rows_data, f, ensure_ascii=False, indent=2)

        print("SAVE ROWS:", len(rows_data))


    # ----------------------------------------------------------
    # โหลดแถวค้างจากไฟล์
    # ----------------------------------------------------------
    def load_pending_rows(self):
        self._loading = True     # 🔒 เริ่มโหลด (ห้าม save)

        self._block_save = True  # (ถ้ามีอยู่แล้ว ยิ่งดี)
        if not os.path.exists(TEMP_FILE):
            return

        self._loading_pending = True  # 🔒 lock save

        try:
            with open(TEMP_FILE, "r", encoding="utf8") as f:
                data = json.load(f)
        except:
            self._loading_pending = False
            return

        if not isinstance(data, list):
            self._loading_pending = False
            return

        self.add_table.setRowCount(0)

        from db import get_subcategories

        for item in data:
            self.add_row()
            row = self.add_table.rowCount() - 1

            barcode = item.get("barcode", "")
            if str(barcode).lower() == "nan":
                barcode = ""

            self.add_table.item(row, 1).setText(barcode)
            self.add_table.item(row, 2).setText(item.get("name", ""))
            self.add_table.item(row, 3).setText(str(item.get("price", 0)))
            self.add_table.item(row, 4).setText(str(item.get("cost", 0)))
            self.add_table.item(row, 5).setText(str(item.get("qty", 1)))

            main = (item.get("main") or "").strip()
            sub  = (item.get("sub") or "").strip()

            combo_main = self.add_table.cellWidget(row, 6)
            combo_sub  = self.add_table.cellWidget(row, 7)

            # main
            combo_main.blockSignals(True)
            if main and main in self.category_list:
                combo_main.setCurrentText(main)
            else:
                combo_main.setCurrentIndex(-1)
            combo_main.blockSignals(False)

            # sub
            subs = get_subcategories(main) if main else []
            combo_sub.blockSignals(True)
            combo_sub.clear()
            combo_sub.addItems(subs)
            combo_sub.addItem("➕ เพิ่มหมวดย่อย")

            if sub in subs:
                combo_sub.setCurrentText(sub)
            else:
                combo_sub.setCurrentIndex(-1)
            combo_sub.blockSignals(False)

        self.renumber_ids()
        self._loading_pending = False  # 🔓 unlock



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
    # 🔥 ฟังก์ชันรับค่าจากช่อง Input (แก้ไขใหม่)
    # ----------------------------------------------------------
    def add_from_input(self):
        """รับค่าจากบาร์โค้ด เช็คซ้ำ ถ้าซ้ำบวกจำนวน ถ้าไม่ซ้ำเพิ่มแถว"""
        text = self.input_barcode.text().strip()
        if not text:
            return

        # แปลงแป้นพิมพ์ไทยเป็นอังกฤษ (เผื่อลืมสลับภาษา)
        barcode = self.convert_thai_keyboard_barcode(text)

        # 1. วนลูปเช็คว่ามีบาร์โค้ดนี้ในตารางหรือยัง
        rows = self.add_table.rowCount()
        for r in range(rows):
            item_code = self.add_table.item(r, 1) # คอลัมน์ 1 คือบาร์โค้ด
            if item_code and item_code.text().strip() == barcode:
                # === เจอของเดิม! บวกจำนวนเพิ่ม ===
                item_qty = self.add_table.item(r, 5) # คอลัมน์ 5 คือจำนวน
                current_qty = 0
                try:
                    current_qty = int(item_qty.text())
                except ValueError:
                    current_qty = 0
                
                # บวกเพิ่ม 1 (หรือตามจำนวนที่ต้องการ)
                new_qty = current_qty + 1
                item_qty.setText(str(new_qty))

                # Highlight แถวนั้นให้รู้ว่าอัปเดตแล้ว
                self.add_table.selectRow(r)
                self.add_table.scrollToItem(item_qty)
                
                # เคลียร์ช่องและบันทึก
                self.input_barcode.clear()
                self.schedule_save()
                return  # ⛔ จบฟังก์ชันเลย ไม่ต้องไปสร้างแถวใหม่

        # 2. ถ้าไม่เจอของเดิม ให้เพิ่มแถวใหม่
        self.add_row(barcode_val=barcode)
        self.input_barcode.clear()

    # ----------------------------------------------------------
    # 🔥 ฟังก์ชันเพิ่มแถวใหม่ (รองรับการรับค่าบาร์โค้ดมาเลย)
    # ----------------------------------------------------------
    def add_row(self, barcode_val=""):
        row = self.add_table.rowCount()
        self.add_table.insertRow(row)
        self.add_table.setRowHeight(row, 60) # ความสูงแถว

        # --- 0. ID (ลำดับ) ---
        item_id = QTableWidgetItem(str(row + 1))
        item_id.setFlags(Qt.ItemIsEnabled) # ห้ามแก้
        item_id.setTextAlignment(Qt.AlignCenter)
        self.add_table.setItem(row, 0, item_id)

        # --- 1. Barcode ---
        item_code = QTableWidgetItem(barcode_val)
        item_code.setTextAlignment(Qt.AlignCenter)
        self.add_table.setItem(row, 1, item_code)

        # --- 2. Name (ชื่อสินค้า) ---
        item_name = QTableWidgetItem("")
        self.add_table.setItem(row, 2, item_name)

        # --- 3. Price (ราคาขาย) ---
        item_price = QTableWidgetItem("0")
        item_price.setTextAlignment(Qt.AlignCenter)
        self.add_table.setItem(row, 3, item_price)

        # --- 4. Cost (ทุน) ---
        item_cost = QTableWidgetItem("0")
        item_cost.setTextAlignment(Qt.AlignCenter)
        self.add_table.setItem(row, 4, item_cost)

        # --- 5. Qty (จำนวน) ---
        # เริ่มต้นเป็น 1 เสมอเมื่อเพิ่มแถวใหม่
        item_qty = QTableWidgetItem("1")
        item_qty.setTextAlignment(Qt.AlignCenter)
        self.add_table.setItem(row, 5, item_qty)

        # --- 6. Main Category (Combobox) ---
        combo_main = self.create_main_category_box(row)
        self.add_table.setCellWidget(row, 6, combo_main)

        # --- 7. Sub Category (Combobox) ---
        combo_sub = self.create_sub_category_box(row)
        self.add_table.setCellWidget(row, 7, combo_sub)

        # --- 8. Controls (ปุ่มจัดการ) ---
        btn_widget = self.create_control_buttons(row)
        self.add_table.setCellWidget(row, 8, btn_widget)

        # --- Auto Fill: ถ้ามีในระบบ ให้ดึงชื่อ/ราคา/หมวด มาใส่เลย ---
        if barcode_val:
            self.auto_fill_product(row)

        # --- Auto Category: ถ้าล็อคหมวดไว้ ให้เลือกเลย ---
        if self.auto_main_mode and self.locked_main_category:
            combo_main.setCurrentText(self.locked_main_category)
        
        if self.auto_sub_mode and self.locked_sub_category:
            # ต้องรอให้ Main เลือกเสร็จก่อน Sub ถึงจะมีรายการให้เลือก
            # (Logic นี้อาจต้องปรับตามการทำงานของ Combo คุณ)
             QTimer.singleShot(50, lambda: combo_sub.setCurrentText(self.locked_sub_category))

        # Scroll ไปหาแถวใหม่
        self.add_table.scrollToBottom()
        self.schedule_save()
    
    # ฟังก์ชันช่วยปรับจำนวน (ใช้กับปุ่ม + / - ในตาราง)
    def adjust_qty(self, row, amount):
        item = self.add_table.item(row, 5)
        if not item: return
        try:
            val = int(item.text())
        except:
            val = 0
        
        new_val = val + amount
        if new_val < 1: new_val = 1 # ห้ามต่ำกว่า 1
        
        item.setText(str(new_val))
        self.schedule_save()
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
