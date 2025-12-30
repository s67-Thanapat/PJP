import sqlite3
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import Signal
from db import get_barcode_alias_map
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPropertyAnimation, QRect
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QSizePolicy
from PySide6 import QtGui
from PySide6.QtCore import QLocale
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView,
    QPushButton, QHBoxLayout, QHeaderView, QStyledItemDelegate, QComboBox,
    QMessageBox, QInputDialog, QFileDialog, QDialog,
    QPlainTextEdit,QMainWindow          # ⭐ เพิ่มบรรทัดนี้
)
from PySide6.QtCore import Qt


from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QTimer, QEvent

from db import (
    update_product_info,
    update_stock,
    get_categories,
    import_from_excel,
    export_to_excel,
)

DB_FILE = "stock.db"
LAST_STOCK_PATH = "last_stock_path.json"


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        # ❗❗ บล็อก scroll wheel ไม่ให้เปลี่ยนค่า
        event.ignore()

# ===========================================================
# ⭐ ฟังก์ชันแปลงตัวคีย์ไทยที่ยิงจากบาร์โค้ด → ตัวเลขจริง
# ===========================================================
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


# ===========================================================
# ⭐ ฟังก์ชันแปลงเลขไทย → อารบิก
# ===========================================================
def convert_thai_digits(text):
    thai_digits = "๐๑๒๓๔๕๖๗๘๙"
    arabic_digits = "0123456789"
    return text.translate(str.maketrans(thai_digits, arabic_digits))

# ============================================================
# 🔥 Delegates สำหรับ inline editor
# ============================================================
class LeftAlignEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        editor.setStyleSheet("padding-left: 6px; font-size:16px;")
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect.adjusted(0, 0, 0, 0)  # ขยายเต็ม ไม่มีหด
        editor.setGeometry(rect)

class ScrollMessageWindow(QMainWindow):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 550)

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # หัวข้อ
        header = QLabel(text.split("\n")[0])
        header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(header)

        # เนื้อหายาว
        detail = "\n".join(text.split("\n")[1:])

        text_area = QPlainTextEdit()
        text_area.setReadOnly(True)
        text_area.setPlainText(detail)
        text_area.setStyleSheet("font-family: Consolas; font-size: 12px;")
        layout.addWidget(text_area)

        # ปุ่มปิด
        btn_close = QPushButton("ปิด")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                font-size: 16px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: #218838;
            }
        """)
        btn_close.clicked.connect(self.on_close_clicked)


        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn_close)
        layout.addLayout(row)

        self.setCentralWidget(widget)

    def on_close_clicked(self):
        parent = self.parent()

        # 1) เซฟ StockTab
        if hasattr(parent, "save_if_dirty"):
            parent.save_if_dirty()

        # 2) รีเฟรช StockTab
        if hasattr(parent, "refresh"):
            QTimer.singleShot(50, parent.refresh)

        # 3) ปิด popup
        self.close()



class CenterEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setAlignment(Qt.AlignCenter)
        editor.setStyleSheet("font-size:16px;")
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect.adjusted(0, 0, 0, 0)  # ขยายเต็ม ไม่มีหด
        editor.setGeometry(rect)

# ---------------------------------------------------------
# 🔥  Block editor เฉพาะหัวหมวด
# ---------------------------------------------------------
class HeaderBlockDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        item = index.model().item(index.row(), 0)
        # ถ้าเป็นหัวหมวด → return None = ห้ามแก้ไข
        if item and item.data(Qt.UserRole) == "header":
            return None
        return super().createEditor(parent, option, index)

class NoEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return None  # ⛔ ห้ามเข้าโหมดแก้ไข

# ------------------------------------------------------------
# 🔥 Delegate เฉพาะคอลัมน์ "ชื่อสินค้า" + AutoComplete
# ------------------------------------------------------------
class NameEditDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        editor.setStyleSheet("""
            font-size:16px;
            padding-left: 8px;
            padding-right: 8px;
        """)


        # ⭐ Auto-Complete ชื่อสินค้า ดึงจาก DB
        from db import get_all_product_names
        names = get_all_product_names()

        from PySide6.QtWidgets import QCompleter
        completer = QCompleter(names)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        editor.setCompleter(completer)

        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

class StockTableWidget(QTableWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        # ปิด selection ของ Qt (กัน highlight ดำ)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)

        self.dragging = False
        self.src_row = None
        self._press_pos = None

        # ⭐ Long-press timer สำหรับเริ่มลากแถว
        self.longpress_timer = QTimer()
        self.longpress_timer.setSingleShot(True)
        self.longpress_timer.timeout.connect(self._start_longpress_drag)
        self._press_row = None

        # ⭐ Highlight settings
        self.drag_highlight_color = QtGui.QColor("#cce9ff")
        self.drag_original_colors = {}  # เก็บสีเดิมไว้ restore

        # ⭐ เก็บ animation ไว้ใน object
        self._row_anim = None

    



    def _start_longpress_drag(self):
        self.longpress_timer.stop()

        if self._press_row is None:
            return

        item = self.item(self._press_row, 0)
        if not item or item.data(Qt.UserRole) == "header":
            return

        # ⭐ ปลดซ่อนหมวดก่อนเริ่มลาก (กัน Qt crash)
        cat = self.owner.get_category_of_row(self._press_row)
        if cat:
            self.owner.expand_category(cat)
            QApplication.processEvents()   # ⭐ บังคับเรนเดอร์ใหม่ก่อน drag

        self.dragging = True
        self.src_row = self._press_row

        # ⭐ ไฮไลต์แถวที่ลาก
        self.highlight_row(self.src_row)

    def mousePressEvent(self, event):
        self._press_time = event.timestamp()

        self.longpress_timer.stop()
        pos = event.position().toPoint()
        row = self.rowAt(pos.y())

        print(f"[StockTable] PRESS row={row}")

        self.dragging = False
        self.src_row = None
        self._press_row = row
        self._press_pos = pos

        # ⭐ เริ่มจับค้าง (400ms)
        if row >= 0:
            self.longpress_timer.start(400)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        row = self.rowAt(pos.y())

        if not self.dragging:
            super().mouseMoveEvent(event)
            return

        if row < 0:
            return

        # ❌ ห้าม selectRow() เพราะ Qt จะทำ highlight แบบ persistent
        self._hover_row = row


    def mouseReleaseEvent(self, event):
        print(f"[StockTable] RELEASE dragging={self.dragging} src_row={self.src_row}")

        self.longpress_timer.stop()
        press_duration = event.timestamp() - (self._press_time or 0)

        # ⭐ คลิกเร็ว < 200ms → เปิด editor
        if not self.dragging and press_duration < 200:
            row = self.rowAt(event.position().toPoint().y())
            col = self.columnAt(event.position().toPoint().x())

            # ห้ามแก้ header/sub_header
            item0 = self.item(row, 0)
            if item0 and item0.data(Qt.UserRole) not in ("header", "sub_header"):
                self.editItem(self.item(row, col))


        # ============================
        # กรณีไม่ได้เข้าสู่โหมดลากจริง
        # (คลิกธรรมดา / คลิกแล้วปล่อยเร็ว)
        # ============================
        if not self.dragging:
            self._press_row = None
            super().mouseReleaseEvent(event)
            return

        # ============================
        # กรณีกำลังลากอยู่ (มี long-press แล้ว)
        # ============================
        if self.src_row is not None:
            dst = getattr(self, "_hover_row", None)

            if dst is not None and dst != self.src_row:
                # กรณีลากไปลงแถวใหม่
                self.clear_highlight(self.src_row)
                self.animate_row_move(self.src_row, dst)

                # ⭐ หลังย้ายเสร็จ บังคับแถวปลายทางเป็นสีขาว
                QTimer.singleShot(10, lambda r=dst: self.force_white_row(r))

            else:
                # กรณีกดค้างแต่ไม่ย้ายแถว → ให้แถวเดิมเป็นสีขาว
                self.clear_highlight(self.src_row)
                self.force_white_row(self.src_row)

        try:
            self.releaseMouse()
        except:
            pass

        self.dragging = False
        self.src_row = None
        self._hover_row = None

        super().mouseReleaseEvent(event)
        self.clear_all_highlights()
        self.clearSelection()
        self.setCurrentItem(None)


       


    def force_white_row(self, row):
        """บังคับให้ทั้งแถวเป็นพื้นขาว ตัวหนังสือดำ (ยกเว้นหัวหมวด)"""
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if not item:
                continue

            role = item.data(Qt.UserRole)
            if role in ("header", "sub_header"):
                continue

            # ⭐ บังคับสีขาว-ดำ แบบ hard reset
            item.setBackground(QtGui.QColor("#ffffff"))
            item.setForeground(QtGui.QColor("#000000"))




    def animate_row_move(self, src, dst):

        table = self

        # ⭐ ทำให้แถว src เป็นสีฟ้า highlight จริง
        self.highlight_row(src)
        QApplication.processEvents()

        # -----------------------------
        #  จับภาพแถวต้นทางทั้งแถว (สีฟ้าจริง)
        # -----------------------------
        src_index = table.model().index(src, 0)
        row_rect = table.visualRect(src_index)

        row_rect.setX(0)
        row_rect.setWidth(table.viewport().width())

        row_pixmap = table.viewport().grab(row_rect)

        # ⭐ ไม่ต้อง fillRect — ใช้สี highlight จริง
        # (ลบ painter.fillRect ออก)

        # overlay
        overlay = QLabel(table.viewport())
        overlay.setPixmap(row_pixmap)
        overlay.setGeometry(row_rect)
        overlay.show()

        # -----------------------------
        #  ปลายทาง
        # -----------------------------
        dst_index = table.model().index(dst, 0)
        dst_rect = table.visualRect(dst_index)
        dst_rect.setX(0)
        dst_rect.setWidth(table.viewport().width())

        anim = QPropertyAnimation(overlay, b"geometry", self)
        anim.setDuration(250)
        anim.setStartValue(row_rect)
        anim.setEndValue(dst_rect)
        anim.setEasingCurve(QEasingCurve.InOutCubic)

        # -----------------------------
        #  เสร็จ → ย้ายแถวจริง
        # -----------------------------
        def finish_anim():
            overlay.deleteLater()
            self.owner.move_product_row(src, dst)

            # ============================
            # ⭐ FIX: แถวดำหลังลาก ⭐
            # ============================
            self.clear_all_highlights()
            self.clearSelection()
            self.setCurrentItem(None)
            QApplication.processEvents()

            self._row_anim = None



        anim.finished.connect(finish_anim)
        anim.start()
        self._row_anim = anim




    def highlight_row(self, row):
        """ทาสี highlight แถวที่ลาก"""
        self.drag_original_colors[row] = {}

        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                self.drag_original_colors[row][col] = item.background().color()
                item.setBackground(self.drag_highlight_color)

    def clear_highlight(self, row):
        """คืนสีเดิมเมื่อปล่อยเมาส์"""
        if row not in self.drag_original_colors:
            return

        for col, old_color in self.drag_original_colors[row].items():
            item = self.item(row, col)
            if item:
                item.setBackground(old_color)

        del self.drag_original_colors[row]

    def clear_all_highlights(self):
        for r in list(self.drag_original_colors.keys()):
            self.clear_highlight(r)



# ============================================================
#                           StockTab
# ============================================================
class StockTab(QWidget):
    saved = Signal()
    def __init__(self):
        super().__init__()
        self.qty_header_toggled = False

        self.enter_count = 0
        self._last_main_category = None
        self._last_sub_category = None


    
        # สำหรับ scan barcode ที่ช่องค้นหา
        self.scan_buffer = ""
        self.scan_timer = QTimer()
        self.scan_timer.setInterval(100)
        self.scan_timer.timeout.connect(self.finish_scan)

        # state ภายใน
        self.all_products = []
        self.categories = []
        self.category_rows = {}       # cat -> row index (ของ header)
        self.category_collapsed = {}  # cat -> bool
        self.editing = False
        self.dirty = False            # มีข้อมูลที่ยังไม่เซฟ ?
        self.sub_category_rows = {}       # ⭐ แถวของหมวดย่อย
        self.sub_category_collapsed = {}  # ⭐ สถานะย่อ/ขยายของหมวดย่อย


        self.build_ui()
        self.alias_map = get_barcode_alias_map()
        self.ensure_sub_category_table()


        self.load_data()

    def highlight_low_stock_row(self, row, qty):
        if self.qty_header_toggled and qty < 10:
            bg = QtGui.QColor("#ffe5e5")  # แดงอ่อน
        else:
            bg = QtGui.QColor("#ffffff")  # พื้นขาว

        # สีทุกคอลัมน์ของสินค้า
        for c in range(self.table.columnCount()):
            item = self.table.item(row, c)
            if item and item.data(Qt.UserRole) not in ("header", "sub_header"):
                item.setBackground(bg)

    def on_header_clicked(self, index):
        if index == 4:  # คอลัมน์จำนวน
            # toggle
            self.qty_header_toggled = not self.qty_header_toggled

            new_text = "จำนวนคงเหลือ" if self.qty_header_toggled else "จำนวน"
            self.table.horizontalHeaderItem(4).setText(new_text)

            # ⭐ เมื่อเปลี่ยนโหมด ต้องไล่ re-highlight ทั้งตารางใหม่
            for r in range(self.table.rowCount()):
                item0 = self.table.item(r, 0)
                if not item0 or item0.data(Qt.UserRole) in ("header", "sub_header"):
                    continue

                # เอาค่า qty จาก column 4
                try:
                    qty = int(self.table.item(r, 4).text())
                except:
                    continue

                # ทำ highlight
                self.highlight_low_stock_row(r, qty)


    def expand_category(self, category):
        if category not in self.category_rows:
            return

        header_row = self.category_rows[category]

        self.category_collapsed[category] = False
        header_item = self.table.item(header_row, 0)
        if header_item:
            header_item.setText(f"▾  {category}")

        r = header_row + 1
        while r < self.table.rowCount():
            item = self.table.item(r, 0)
            if item and item.data(Qt.UserRole) == "header":
                break
            self.table.setRowHidden(r, False)
            r += 1
            
        # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------
    def build_ui(self):
        layout = QVBoxLayout()

        title = QLabel("📦 สต็อกสินค้า (แยกหมวดหมู่)")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        layout.addWidget(title)

        # ช่องค้นหา
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 ค้นหาสินค้า / หมวด / บาร์โค้ด ...")
        self.search_box.setFixedHeight(40)
        self.search_box.setStyleSheet("font-size:16px; padding-left:10px;")
        self.search_box.textChanged.connect(self.apply_filter)
        self.search_box.installEventFilter(self)
        layout.addWidget(self.search_box)

        # ตาราง
        self.table = StockTableWidget(self)
        self.table.setStyleSheet("""
            QTableWidget::item:selected {
                background: #ffffff;     /* ขาว */
                color: black;
            }
        """)


        self.table.setObjectName("stockTable")

        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ลำดับ", "ชื่อสินค้า", "ราคา", "ราคาทุน", "จำนวนคงเหลือ",
            "บาร์โค้ด", "หมวดหลัก", "หมวดย่อย", "จัดการ"
        ])

        self.table.verticalHeader().setVisible(False)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        header = self.table.horizontalHeader()
        header.sectionClicked.connect(self.on_header_clicked)

        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 60)   # ← ปรับได้ เช่น 40 / 50 / 60

        header.setSectionResizeMode(1, QHeaderView.Stretch)            # ชื่อสินค้า
        header.resizeSection(2, 120)  # ราคา
        header.resizeSection(3, 120)  # ราคาทุน
        header.resizeSection(4, 120)  # จำนวน
        header.resizeSection(5, 160)  # บาร์โค้ด
        header.resizeSection(6, 200)  # หมวดหลัก
        header.resizeSection(7, 200)  # หมวดย่อย
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)   # ปุ่มลบ


        

        # signals
        self.table.cellClicked.connect(self.handle_click)
        self.table.cellDoubleClicked.connect(self.handle_double_click)
        self.table.itemChanged.connect(self.mark_dirty)

        # ตั้ง Delegate ให้ช่องตัวเลขอยู่ตรงกลางเวลาตอน edit
        # Delegates
        name_delegate = NameEditDelegate(self.table)
        self.table.setItemDelegateForColumn(1, name_delegate)  # ชื่อสินค้า → ชิดซ้ายตอน edit

        center_delegate = CenterEditDelegate(self.table)
        self.table.setItemDelegateForColumn(2, center_delegate)  # ราคา
        self.table.setItemDelegateForColumn(3, center_delegate)  # ราคาทุน
        self.table.setItemDelegateForColumn(4, center_delegate)  # จำนวน
        self.table.setItemDelegateForColumn(5, center_delegate)  # บาร์โค้ด
        
        noedit = NoEditDelegate(self.table)
        self.table.setItemDelegateForColumn(0, noedit)


        # ===== ปุ่มใต้ search แต่เหนือหัวตาราง =====
        top_btn_row = QHBoxLayout()
        top_btn_row.setAlignment(Qt.AlignRight)   # ⭐ ชิดขวา
        top_btn_row.setSpacing(8)

        btn_manage_cat = QPushButton("📁 จัดการหมวดหมู่")
        btn_manage_cat.setFixedHeight(35)
        btn_manage_cat.clicked.connect(self.manage_categories)

        btn_calc_price = QPushButton("💰 คำนวณราคา")
        btn_calc_price.setFixedHeight(35)
        btn_calc_price.clicked.connect(self.show_calc_price_popup)

        btn_import = QPushButton("⬇️ Import Excel")
        btn_import.setFixedHeight(35)
        btn_import.clicked.connect(self.import_excel)

        btn_export = QPushButton("⬆️ Export Excel")
        btn_export.setFixedHeight(35)
        btn_export.clicked.connect(self.export_excel)

        top_btn_row.addWidget(btn_manage_cat)
        top_btn_row.addWidget(btn_calc_price)
        top_btn_row.addWidget(btn_import)
        top_btn_row.addWidget(btn_export)

        layout.addLayout(top_btn_row)   # ⭐ วางไว้ใต้ search box

        layout.addWidget(self.table)
        # ===== ปุ่มล้างข้อมูล + ปุ่มบันทึกทั้งหมด (ล่างสุด) =====
        bottom_btn_row = QHBoxLayout()
        bottom_btn_row.addStretch()              # ⭐ ดันปุ่มไปชิดขวา

        # ปุ่มล้างข้อมูล
        btn_clear = QPushButton("🧹 ล้างข้อมูล")
        btn_clear.setFixedHeight(45)
        btn_clear.setStyleSheet("""
            QPushButton {
                background:#6c757d;
                color:white;
                padding:6px 14px;
                border-radius:6px;
                font-size:16px;
            }
            QPushButton:hover {
                background:#5a6268;
            }
        """)
        btn_clear.clicked.connect(self.clear_all_products)   # ⭐ เรียกฟังก์ชันลบทั้งหมด
        bottom_btn_row.addWidget(btn_clear)

        # ปุ่มบันทึกทั้งหมด
        btn_save_all = QPushButton("💾 บันทึกทั้งหมด")
        btn_save_all.setFixedHeight(45)
        btn_save_all.setStyleSheet("""
            QPushButton {
                background:#28a745;
                color:white;
                padding:6px 14px;
                border-radius:6px;
                font-size:16px;
            }
            QPushButton:hover {
                background:#1e7e34;
            }
        """)
        btn_save_all.clicked.connect(self.save_all_products)
        bottom_btn_row.addWidget(btn_save_all)

        layout.addLayout(bottom_btn_row)


        # ===== Apply Layout =====
        self.setLayout(layout)

        

    def mark_dirty(self, item):
        if not item:
            return

        # ข้ามหัวหมวด
        role_item = self.table.item(item.row(), 0)
        if role_item and role_item.data(Qt.UserRole) in ("header", "sub_header"):
            return

        self.dirty = True


    def clear_all_products(self):
        # -----------------------------
        # Custom QMessageBox
        # -----------------------------
        msg = QMessageBox(self)
        msg.setWindowTitle("ยืนยันการลบทั้งหมด")
        msg.setText("ต้องการลบข้อมูลสินค้าทั้งหมดจริงหรือไม่?\n(ไม่สามารถกู้คืนได้)")
        msg.setIcon(QMessageBox.Question)

        # ปุ่ม No = สีเขียว = ยืนยันลบ (AcceptRole)
        no_btn  = msg.addButton("ลบทั้งหมด", QMessageBox.AcceptRole)

        # ปุ่ม Yes = สีเทา = ยกเลิก (RejectRole)
        yes_btn = msg.addButton("ยกเลิก", QMessageBox.RejectRole)

        # Styling
        yes_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                padding: 6px 20px;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #5a6268;
            }
        """)

        no_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                padding: 6px 20px;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #218838;
            }
        """)

        msg.exec()

        # -----------------------------
        # ตรวจว่ากดปุ่มยืนยันหรือไม่
        # -----------------------------
        if msg.clickedButton() != no_btn:
            return  # กด "ยกเลิก" หรือปิดหน้าต่าง → ไม่ลบ

        # -----------------------------
        # ดำเนินการลบข้อมูลจริง
        # -----------------------------
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("DELETE FROM products")
        conn.commit()
        conn.close()

        # ล้างข้อมูลใน memory
        self.all_products = []

        # เคลียร์หน้าตาราง
        self.render_table([])

        QMessageBox.information(self, "สำเร็จ", "ลบข้อมูลทั้งหมดเรียบร้อยแล้ว!")



        # ---------------------------------------------------------
    # โหลดข้อมูล
    # ---------------------------------------------------------
    def load_data(self):
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        cur.execute("""
            SELECT barcode, name, price, cost, qty, main_category, sub_category, sort_order
            FROM products
        """)

        rows = cur.fetchall()
        conn.close()

        self.all_products = []
        for bc, name, price, cost, qty, main_cat, sub_cat, sort_order in rows:

            # ⭐ ถ้า main_cat ไม่มี → ตั้งเป็น "ไม่มีหมวดหมู่"
            if not main_cat or main_cat.strip() == "":
                main_cat = "ไม่มีหมวดหมู่"

            self.all_products.append({
                "barcode": bc,
                "name": name,
                "price": price,
                "cost": cost,
                "qty": qty,
                "category": main_cat,

                "sub_category": sub_cat if sub_cat else "",
                "sort_order": sort_order if sort_order is not None else 999999
            })



        self.categories = get_categories()
        if "ไม่มีหมวดหมู่" not in self.categories:
            self.categories.insert(0, "ไม่มีหมวดหมู่")

        if not self.categories:
            self.categories = sorted({p["category"] for p in self.all_products})

        self.render_table(self.all_products)
        self.dirty = False


        # ---------------------------------------------------------
    # รีเฟรช combobox เฉพาะคอลัมน์หมวดหมู่ หลังแก้หมวดเสร็จ
    # ---------------------------------------------------------
    def reload_categories_in_table(self):
        cats = get_categories()
        self.categories = cats  # sync ไว้ใช้ตอนสร้าง combo ใหม่

        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 6)  # ✅ หมวดหลักอยู่คอลัมน์ 6
            if isinstance(w, QComboBox):
                current = w.currentText()

                w.blockSignals(True)
                w.clear()
                w.addItems(cats)
                w.addItem("➕ เพิ่มหมวดหมู่")
                if current in cats:
                    w.setCurrentText(current)
                w.blockSignals(False)


        # ---------------------------------------------------------
    # วาดตารางแบบหมวด + แถวสินค้า (ไม่มี span)
    # ---------------------------------------------------------
    def render_table(self, products):
        self.table.blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(0)

        self.category_rows.clear()
        self.sub_category_rows.clear()
        self.category_collapsed.clear()
        self.sub_category_collapsed.clear()

        tree = {}
        for p in products:
            main = p["category"]
            sub = p["sub_category"] or "ไม่มีหมวดย่อย"
            tree.setdefault(main, {}).setdefault(sub, []).append(p)

        for main_cat, sub_map in sorted(tree.items()):
            self.add_category_header(main_cat)
            for sub_cat, plist in sorted(sub_map.items()):
                self.add_sub_category_header(main_cat, sub_cat)
                idx = 1
                for p in sorted(plist, key=lambda x: x["sort_order"]):
                    self.add_product_row(p, idx)
                    idx += 1

        # ⭐ ซ่อนแถวสินค้าเริ่มต้น
        # ⭐ พับทุกหมวดหลักตอนเริ่มต้น
        for r in range(self.table.rowCount()):
            role = self.table.item(r, 0).data(Qt.UserRole)

            if role == "header":
                # หัวหมวดหลัก → แสดง แต่เปลี่ยนเป็น icon พับ (▸)
                item0 = self.table.item(r, 0)
                if item0:
                    item0.setText("▸")
                self.table.setRowHidden(r, False)
                continue

            if role == "sub_header":
                # หัวหมวดย่อย → ซ่อน
                self.table.setRowHidden(r, True)
                continue

            # สินค้า → ซ่อนทั้งหมด
            self.table.setRowHidden(r, True)


        self.table.blockSignals(False)


    def create_main_category_box(self, row):
        combo = NoWheelComboBox()

        combo.setEditable(False)

        # ⭐ ตั้งค่าเริ่มต้นในกรณี popup ยังไม่เคยเปิด
        combo._old_value = combo.currentText()

        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setFocusPolicy(Qt.StrongFocus)

        # ===== ใส่รายการ =====
        cats = self.categories[:] if self.categories else []
        combo.addItems(cats)
        combo.addItem("➕ เพิ่มหมวดหมู่")

        # ===== ค่าเดิมจากตาราง =====
        item_cat = self.table.item(row, 6)
        current = item_cat.text() if item_cat else ""
        if current:
            combo.setCurrentText(current)

        barcode = self.table.item(row, 5).text()

        # ===== จำค่าเดิมเมื่อ popup เปิด =====
        orig_popup = combo.showPopup
        def patched_show():
            combo._old_value = combo.currentText()
            orig_popup()
        combo.showPopup = patched_show

        # ===== เมื่อเลือกค่า =====
        def on_change(value):
            real_combo = self.table.cellWidget(row, 6)

            # -----------------------------
            # 1) เพิ่มหมวดหมู่ใหม่
            # -----------------------------
            if value == "➕ เพิ่มหมวดหมู่":
                new_cat, ok = QInputDialog.getText(
                    self,
                    "เพิ่มหมวดหมู่ใหม่",
                    "ชื่อหมวดหมู่:"
                )

                # ❗ ยกเลิก → rollback
                if not ok or not new_cat.strip():
                    real_combo.blockSignals(True)
                    real_combo.setCurrentText(combo._old_value)
                    real_combo.blockSignals(False)
                    return

                new_cat = new_cat.strip()
                # เพิ่มหมวดใน DB
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (new_cat,))
                cur.execute("UPDATE products SET main_category=?, sub_category='' WHERE barcode=?",
                            (new_cat, barcode))
                conn.commit()
                conn.close()

                # sync memory
                self.categories = get_categories()
                for p in self.all_products:
                    if p["barcode"] == barcode:
                        p["category"] = new_cat
                        p["sub_category"] = ""
                        break

                # ⭐⭐ จุดสำคัญ — รีเฉพาะหมวดหลักนี้
                self.refresh_category_combobox_in_main(new_cat)

                # ⭐⭐ เซฟทันที — กันบัคที่ combobox ไม่รีอื่น ๆ
                self.save_all_products(suppress_popup=True)

                self.dirty = True
                return


            # -----------------------------
            # 2) เลือกหมวดปกติ
            # -----------------------------
            if not value:
                return

            # update category
            self.handle_category_change(value, barcode)

        combo.currentTextChanged.connect(on_change)
        return combo



    def create_sub_category_box(self, row):
        combo = NoWheelComboBox()

        combo.setEditable(False)

        # ⭐ ตั้งค่าเดิม (กัน _old_value หาย)
        combo._old_value = combo.currentText()

        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setFocusPolicy(Qt.StrongFocus)

        # ===== โหลดหมวดหลัก =====
        item_main = self.table.item(row, 6)
        main_cat = item_main.text() if item_main else ""

        subs = self.get_sub_categories_for(main_cat)
        if "ไม่มีหมวดย่อย" not in subs:
            subs.insert(0, "ไม่มีหมวดย่อย")

        combo.addItems(subs)
        combo.addItem("➕ เพิ่มหมวดย่อย")

        # ===== ค่าเดิม =====
        item_sub = self.table.item(row, 7)
        current_sub = item_sub.text() if item_sub else "ไม่มีหมวดย่อย"
        combo.setCurrentText(current_sub)

        barcode = self.table.item(row, 5).text()

        # ===== จำค่าเดิมเมื่อ popup เปิด =====
        orig_popup = combo.showPopup

        def patched_show():
            combo._old_value = combo.currentText()   # ⭐ เซฟค่าเดิมก่อนเลือกใหม่
            orig_popup()

        combo.showPopup = patched_show

        # ===== เมื่อเลือกค่า =====
        def on_change(sub):
            real_combo = self.table.cellWidget(row, 7)

            # -----------------------------
            # 1) เพิ่มหมวดย่อยใหม่
            # -----------------------------
            if sub == "➕ เพิ่มหมวดย่อย":

                # ❗ ห้ามเพิ่มถ้าไม่มีหมวดหลัก
                if main_cat == "ไม่มีหมวดหมู่":
                    QMessageBox.warning(
                        self,
                        "ผิดพลาด",
                        "กรุณาเลือกหมวดหลักก่อนเพิ่มหมวดย่อย"
                    )
                    real_combo.blockSignals(True)
                    real_combo.setCurrentText(combo._old_value)
                    real_combo.blockSignals(False)
                    return

                new_sub, ok = QInputDialog.getText(
                    self,
                    "เพิ่มหมวดย่อย",
                    f"ชื่อหมวดย่อยใหม่ใน '{main_cat}':"
                )

                # ❗ กดยกเลิก → rollback
                if not ok or not new_sub.strip():
                    real_combo.blockSignals(True)
                    real_combo.setCurrentText(combo._old_value)
                    real_combo.blockSignals(False)
                    return

                new_sub = new_sub.strip()

                # บันทึก DB
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR IGNORE INTO sub_categories(parent_category, name)
                    VALUES (?,?)
                """, (main_cat, new_sub))
                cur.execute("UPDATE products SET sub_category=? WHERE barcode=?",
                            (new_sub, barcode))
                conn.commit()
                conn.close()

                # sync memory
                for p in self.all_products:
                    if p["barcode"] == barcode:
                        p["sub_category"] = new_sub
                        break

                # reload combobox
                # reload combobox
                new_list = self.get_sub_categories_for(main_cat)
                if "ไม่มีหมวดย่อย" not in new_list:
                    new_list.insert(0, "ไม่มีหมวดย่อย")

                real_combo.blockSignals(True)
                real_combo.clear()
                real_combo.addItems(new_list)
                real_combo.addItem("➕ เพิ่มหมวดย่อย")
                real_combo.setCurrentText(new_sub)
                real_combo.blockSignals(False)

                # ⭐⭐ รีเฉพาะหมวดหลักที่กำลังแก้
                self.refresh_category_combobox_in_main(main_cat)

                # ⭐⭐ เซฟทันที
                self.save_all_products(suppress_popup=True)

                self.dirty = True
                return


            # -----------------------------
            # 2) เลือกปกติ
            # -----------------------------
            db_sub = "" if sub == "ไม่มีหมวดย่อย" else sub

            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("UPDATE products SET sub_category=? WHERE barcode=?", (db_sub, barcode))
            conn.commit()
            conn.close()

            for p in self.all_products:
                if p["barcode"] == barcode:
                    p["sub_category"] = db_sub
                    break

            self.dirty = True

        combo.currentTextChanged.connect(on_change)
        return combo
   
 




    def clear_table_focus(self):
        self.table.clearSelection()
        self.table.setCurrentItem(None)
        self.close_all_editors()

        # ป้องกัน Qt auto-focus cell แรก
        self.table.setFocusPolicy(Qt.NoFocus)
        QTimer.singleShot(30, lambda: self.table.setFocusPolicy(Qt.StrongFocus))

    # ---------------------------------------------------------
    # แถวหัวหมวด
    # ---------------------------------------------------------
    def add_category_header(self, category):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # คอลัมน์ 0 = ไอคอนย่อ/ขยาย
        icon_item = QTableWidgetItem("▾")
        icon_item.setFont(QFont("Segoe UI", 20, QFont.Bold))
        icon_item.setTextAlignment(Qt.AlignCenter)  # ⭐ อยู่กลางช่อง
        icon_item.setBackground(QtGui.QColor("#d0d0d0"))
        icon_item.setFlags(Qt.ItemIsEnabled)
        icon_item.setData(Qt.UserRole, "header")
        self.table.setItem(row, 0, icon_item)
        self.force_pure_item(row, 0)      # ⭐ ลบ widget ให้สะอาดจริง 

        # คอลัมน์ 1 = ชื่อหมวด
        name_item = QTableWidgetItem(category)
        name_item.setFont(QFont("Segoe UI", 14, QFont.Bold))
        name_item.setBackground(QtGui.QColor("#d0d0d0"))
        name_item.setFlags(Qt.ItemIsEnabled)
        name_item.setData(Qt.UserRole, "header")
        self.table.setItem(row, 1, name_item)

        # คอลัมน์อื่น dummy
        for c in range(2, self.table.columnCount()):
            dummy = QTableWidgetItem("")
            dummy.setBackground(QtGui.QColor("#d0d0d0"))
            dummy.setFlags(Qt.ItemIsEnabled)
            dummy.setData(Qt.UserRole, "header")
            dummy.setForeground(QtGui.QColor("#d0d0d0"))
            self.table.setItem(row, c, dummy)

        self.table.setRowHeight(row, 40)
        self.category_rows[category] = row
        self.category_collapsed[category] = True



    def add_sub_category_header(self, main_cat, sub_cat):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # คอลัมน์ 0 = ไอคอน
        icon_item = QTableWidgetItem("▸")
        icon_item.setFont(QFont("Segoe UI", 18, QFont.Bold))
        icon_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)  # ⭐ ชิดขวา
        icon_item.setBackground(QtGui.QColor("#e8e8e8"))
        icon_item.setFlags(Qt.ItemIsEnabled)
        icon_item.setData(Qt.UserRole, "sub_header")
        icon_item.setData(Qt.UserRole + 1, main_cat)
        self.table.setItem(row, 0, icon_item)
        self.force_pure_item(row, 0)      # ⭐ ลบ widget ให้สะอาดจริง


        # คอลัมน์ 1 = ชื่อหมวดย่อย
        name_item = QTableWidgetItem(sub_cat)
        name_item.setFont(QFont("Segoe UI", 12, QFont.Bold))
        name_item.setBackground(QtGui.QColor("#e8e8e8"))
        name_item.setFlags(Qt.ItemIsEnabled)
        name_item.setData(Qt.UserRole, "sub_header")
        self.table.setItem(row, 1, name_item)

        # คอลัมน์อื่น dummy
        for c in range(2, self.table.columnCount()):
            dummy = QTableWidgetItem("")
            dummy.setBackground(QtGui.QColor("#e8e8e8"))
            dummy.setFlags(Qt.ItemIsEnabled)
            dummy.setData(Qt.UserRole, "sub_header")
            dummy.setForeground(QtGui.QColor("#e8e8e8"))
            self.table.setItem(row, c, dummy)

        self.table.setRowHeight(row, 35)
        self.sub_category_rows[(main_cat, sub_cat)] = row
        self.sub_category_collapsed[(main_cat, sub_cat)] = True

        # ---------------------------------------------------------
    # แถวสินค้า
    # ---------------------------------------------------------
    def add_product_row(self, p, index_in_sub):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # คอลัมน์ลำดับ (เฉพาะหมวดย่อย)
        item_order = QTableWidgetItem(str(index_in_sub))
        item_order.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 0, item_order)

        # ชื่อสินค้า
        item_name = QTableWidgetItem(p["name"])
        item_name.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setItem(row, 1, item_name)

        # ราคา
        item_price = QTableWidgetItem(str(p["price"]))
        item_price.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 2, item_price)

        # ราคาทุน
        item_cost = QTableWidgetItem(str(p["cost"]))
        item_cost.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 3, item_cost)

        # จำนวน
        item_qty = QTableWidgetItem(str(p["qty"]))
        item_qty.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 4, item_qty)

        # barcode (แก้ปัญหาทศนิยมด้วย)
        item_bc = QTableWidgetItem(str(p["barcode"]).split(".")[0])
        item_bc.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 5, item_bc)

        # หมวด
        self.table.setItem(row, 6, QTableWidgetItem(p["category"]))
        self.table.setItem(row, 7, QTableWidgetItem(p["sub_category"] or "ไม่มีหมวดย่อย"))

        # Combobox หมวดหลัก
        combo_cat = self.create_main_category_box(row)
        self.table.setCellWidget(row, 6, combo_cat)

        # Combobox หมวดย่อย
        combo_sub = self.create_sub_category_box(row)
        self.table.setCellWidget(row, 7, combo_sub)

        # ปุ่มลบ
        btn = self.create_delete_button(p["barcode"])
        self.table.setCellWidget(row, 8, btn)

        # ✅ เพิ่มเมื่อ (created_at)
        created_at = p.get("created_at") or ""
        item_time = QTableWidgetItem(created_at)
        item_time.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 9, item_time)

        self.table.setRowHeight(row, 45)

        qty = p["qty"]
        self.highlight_low_stock_row(row, qty)





           # ---------------------------------------------------------
    # เปลี่ยนหมวดจาก combobox → อัปเดต + ปิด editor + รีเฟรช
    # ---------------------------------------------------------
    def handle_category_change(self, value, barcode):
        combo = self.sender()

        # 🔹 กรณีเลือก "เพิ่มหมวดหมู่"
        if value == "➕ เพิ่มหมวดหมู่":
            new_cat, ok = QInputDialog.getText(self, "เพิ่มหมวดหมู่ใหม่", "ชื่อหมวดหมู่:")
            if not ok or not new_cat.strip():
                # ยกเลิก → กลับไปหมวดเดิม
                old_cat = None
                for p in self.all_products:
                    if p["barcode"] == barcode:
                        old_cat = p["category"]
                        break
                combo.blockSignals(True)
                if old_cat:
                    combo.setCurrentText(old_cat)
                else:
                    combo.setCurrentIndex(0)
                combo.blockSignals(False)
                return

            new_cat = new_cat.strip()

            # เพิ่มหมวดใน DB
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (new_cat,))
            # อัปเดตสินค้าตัวนี้ให้ใช้หมวดใหม่ และเคลียร์หมวดย่อย
            cur.execute("UPDATE products SET main_category=?, sub_category='' WHERE barcode=?",
                        (new_cat, barcode))
            conn.commit()
            conn.close()

            # sync memory
            self.categories = get_categories()
            for p in self.all_products:
                if p["barcode"] == barcode:
                    p["category"] = new_cat
                    p["sub_category"] = ""
                    break

            # วาดตารางใหม่เพื่อให้ combobox ทั้งหมดอัปเดต
            self.render_table(self.all_products)
            self.dirty = True
            return

        # 🔹 กรณีเลือกหมวดปกติ
        if not value:
            return

        self.close_all_editors()

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("UPDATE products SET main_category=? WHERE barcode=?", (value, barcode))
        conn.commit()
        conn.close()

        for p in self.all_products:
            if p["barcode"] == barcode:
                p["category"] = value
                break

        self.render_table(self.all_products)
        self.dirty = True


    # ---------------------------------------------------------
    # คลิกหัวหมวดเพื่อพับ/ขยาย
    # ---------------------------------------------------------
    def handle_click(self, row, col):

        # ถ้ากำลังลากอยู่ ไม่ต้องทำอะไร
        if self.table.dragging:
            return

        item0 = self.table.item(row, 0)
        if not item0:
            return

        role = item0.data(Qt.UserRole)

        # =======================================================
        # 1) คลิกหัวหมวดหลัก
        # =======================================================
        if role == "header":
            cat = self.table.item(row, 1).text()

            collapsed = self.category_collapsed.get(cat, True)
            new_state = not collapsed
            self.category_collapsed[cat] = new_state

            # เปลี่ยนไอคอน
            item0.setText("▸" if new_state else "▾")
            item0.setTextAlignment(Qt.AlignCenter)

            # ซ่อน / แสดง แถวลูก
            for r in range(row + 1, self.table.rowCount()):
                it = self.table.item(r, 0)
                r_role = it.data(Qt.UserRole)
                if r_role == "header":
                    break
                if r_role == "sub_header":
                    self.table.setRowHidden(r, new_state)   # ย่อ/ขยายเฉพาะหัวหมวดย่อย
                else:
                    self.table.setRowHidden(r, True)        # สินค้าให้ซ่อนอยู่เสมอ
            return

        # =======================================================
        # 2) คลิกหัวหมวดย่อย
        # =======================================================
        if role == "sub_header":
            sub = self.table.item(row, 1).text()
            main = item0.data(Qt.UserRole + 1)
            key = (main, sub)

            collapsed = self.sub_category_collapsed.get(key, True)
            new_state = not collapsed
            self.sub_category_collapsed[key] = new_state

            # เปลี่ยนไอคอน
            item0.setText("▸" if new_state else "▾")
            item0.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            # ซ่อน / แสดงสินค้าใต้หมวดย่อยนี้
            for r in range(row + 1, self.table.rowCount()):
                it = self.table.item(r, 0)
                r_role = it.data(Qt.UserRole)
                if r_role in ("header", "sub_header"):
                    break
                self.table.setRowHidden(r, new_state)
            return

        # =======================================================
        # 3) cell widget เช่น ปุ่มลบ / combobox
        # =======================================================
        widget = self.table.cellWidget(row, col)
        if widget:
            widget.setFocus()
            return

        # 🔥 ไม่มีคำสั่ง editItem ที่นี่แล้ว
        # ถ้าจะเข้าโหมดแก้ไข ให้ใช้ double-click


    # ---------------------------------------------------------
    # อัปเดตสินค้าเมื่อแก้ไขเซลล์
    # ---------------------------------------------------------
    def handle_double_click(self, row, col):
        item0 = self.table.item(row, 0)
        if not item0:
            return

        # หัวหมวดไม่แก้ไข
        if item0.data(Qt.UserRole) == "header":
            return

        # 🔥 Double click คอลัมน์ราคา
        if col == 1:
            self.table.editItem(self.table.item(row, col))
            return


        # ช่องอื่น
        if col not in (5, 6, 7):   # เพิ่ม 7 เพราะคุณเพิ่มหมวดย่อย + ปุ่มลบ
            self.table.editItem(self.table.item(row, col))

        self.table.clearSelection()
        self.table.setCurrentItem(None)

    def update_product(self, item):
        if self.editing:
            return

        row = item.row()
        item0 = self.table.item(row, 0)
        if not item0:
            return

        if item0.data(Qt.UserRole) in ("header", "sub_header"):
            return

        try:
            bc    = self.table.item(row, 5).text().strip()
            name  = self.table.item(row, 1).text().strip()
            price = float(self.table.item(row, 2).text())
            cost  = float(self.table.item(row, 3).text())
            qty   = int(self.table.item(row, 4).text())
        except Exception:
            return

        self.editing = True
        self.table.blockSignals(True)

        update_product_info(bc, name, price, cost, None)
        update_stock(bc, qty, absolute=True)
        # ⭐ บันทึกประวัติสินค้า
        try:
            old_qty = None
            for p in self.all_products:
                if p["barcode"] == bc:
                    old_qty = p["qty"]
                    break
            
            if old_qty is not None:
                qty_added = qty - old_qty
                if qty_added != 0:
                    from db import add_history
                    add_history(bc, qty_added)
        except:
            pass


        # mark dirty
        self.dirty = True

        # sync all_products memory
        for p in self.all_products:
            if p["barcode"] == bc:
                p["name"] = name
                p["price"] = price
                p["cost"] = cost
                p["qty"] = qty
                break

        self.table.blockSignals(False)
        self.editing = False



    # ---------------------------------------------------------
    def delete_product(self, barcode):

        # -----------------------------
        # Popup ยืนยันก่อนลบสินค้า
        # -----------------------------
        msg = QMessageBox(self)
        msg.setWindowTitle("ยืนยันการลบสินค้า")
        msg.setText(f"ต้องการลบสินค้านี้จริงหรือไม่?\nบาร์โค้ด: {barcode}")
        msg.setIcon(QMessageBox.Warning)

        # ปุ่มเขียว = ลบ
        ok_btn = msg.addButton("ลบ", QMessageBox.AcceptRole)

        # ปุ่มเทา = ยกเลิก
        cancel_btn = msg.addButton("ยกเลิก", QMessageBox.RejectRole)

        # ปุ่มเทา
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                padding: 6px 18px;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #5a6268;
            }
        """)

        # ปุ่มเขียว
        ok_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                padding: 6px 18px;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #218838;
            }
        """)

        msg.exec()

        # ถ้าผู้ใช้ไม่กดปุ่มลบ → ยกเลิก
        if msg.clickedButton() != ok_btn:
            return

        # -----------------------------
        # 1) ลบใน DB
        # -----------------------------
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE barcode=?", (barcode,))
        conn.commit()
        conn.close()

        # -----------------------------
        # 2) ลบจาก all_products  (แก้ bug จาก == เป็น !=)
        # -----------------------------
        self.all_products = [p for p in self.all_products if p["barcode"] != barcode]

        # -----------------------------
        # 3) หา row ก่อนลบ
        # -----------------------------
        delete_row = None
        for r in range(self.table.rowCount()):
            cell = self.table.item(r, 5)
            if cell and cell.text() == barcode:
                delete_row = r
                break

        if delete_row is None:
            return

        # เก็บหมวดหลัก + ย่อย
        main = self.get_category_of_row(delete_row)
        sub = self.get_sub_category_of_row(delete_row)

        # -----------------------------
        # 4) ลบ row ออกจากตาราง
        # -----------------------------
        self.table.removeRow(delete_row)

        # -----------------------------
        # 5) เรียงลำดับภายใน sub
        # -----------------------------
        if main and sub:
            self.recalc_sub_order(main, sub)

        # -----------------------------
        # 6) เรียง sort_order ใหม่
        # -----------------------------
        if main:
            self.recalculate_sort_order(main)

        self.dirty = True

    def refresh_category_combobox_in_main(self, main_cat):
        """
        รีเฟรชเฉพาะ combobox ของหมวดหลัก main_cat เท่านั้น
        """

        for row in range(self.table.rowCount()):
            row_main = self.get_category_of_row(row)

            if row_main == main_cat:

                # ------- รีเฟรช main category combo -------
                combo_main = self.table.cellWidget(row, 6)
                if isinstance(combo_main, QComboBox):
                    current = combo_main.currentText()
                    combo_main.blockSignals(True)
                    combo_main.clear()

                    # โหลดหมวดหลักใหม่จาก self.categories
                    combo_main.addItems(self.categories)
                    combo_main.addItem("➕ เพิ่มหมวดหมู่")

                    combo_main.setCurrentText(current)
                    combo_main.blockSignals(False)

                # ------- รีเฟรช sub category combo -------
                combo_sub = self.table.cellWidget(row, 7)
                if isinstance(combo_sub, QComboBox):
                    current_sub = combo_sub.currentText()
                    combo_sub.blockSignals(True)
                    combo_sub.clear()

                    # โหลดหมวดย่อยจากฟังก์ชันจริงของคุณ
                    subs = self.get_sub_categories_for(main_cat)

                    # เพิ่ม "ไม่มีหมวดย่อย"
                    if "ไม่มีหมวดย่อย" not in subs:
                        subs.insert(0, "ไม่มีหมวดย่อย")

                    for s in subs:
                        combo_sub.addItem(s)

                    combo_sub.addItem("➕ เพิ่มหมวดย่อย")
                    combo_sub.setCurrentText(current_sub)

                    combo_sub.blockSignals(False)


    def create_delete_button(self, barcode):
        btn = QPushButton("ลบ")
        btn.setStyleSheet("""
            QPushButton {
                background:#dc3545;
                color:white;
                padding:4px 10px;
                border-radius:6px;
            }
            QPushButton:hover {
                background:#b52a3a;
            }
        """)
        btn.clicked.connect(lambda _, bc=barcode: self.delete_product(bc))
        return btn


    # ---------------------------------------------------------
    # ค้นหา
    # ---------------------------------------------------------
    def apply_filter(self):
        t = self.search_box.text().strip().lower()

        if not t:
            self.render_table(self.all_products)
            return

        result = []

        for p in self.all_products:
            bc = p["barcode"].lower()

            if t in p["name"].lower():
                result.append(p)
                continue

            if t in bc:
                result.append(p)
                continue

            if t in p["category"].lower():
                result.append(p)
                continue

            # ⭐ หมวดย่อย
            if "sub_category" in p and t in p["sub_category"].lower():
                result.append(p)
                continue

            if t in self.alias_map:
                base = self.alias_map[t]
                if base == p["barcode"]:
                    result.append(p)
                    continue

        self.render_table(result)

    def show_scrollable_message(self, title, text):
        win = ScrollMessageWindow(title, text, self)
        win.show()



    # ---------------------------------------------------------
    # Barcode Scan → search_box
    # ---------------------------------------------------------
    def eventFilter(self, obj, event):

        # ============================================================
        # 1) ฟิลเตอร์ของช่องค้นหา (ของเดิม)
        # ============================================================
        if obj == self.search_box and event.type() == QEvent.KeyPress:

            key = event.key()
            if key not in (Qt.Key_Return, Qt.Key_Enter):
                return False

            if self.enter_count == 1:
                self.enter_count = 0
                self.search_box.clear()
                self.apply_filter()
                return True

            raw_code = self.search_box.text().strip()

            if not raw_code:
                self.enter_count = 0
                return True

            code = convert_thai_barcode(raw_code)

            self.search_box.clear()
            self.search_box.setText(code)
            self.apply_filter()

            self.enter_count = 1
            return True

        # ============================================================
        # 2) ComboBox: หมวดหลัก
        # ============================================================
        if isinstance(obj, QComboBox) and obj.property("type") == "main_cat":

            if event.type() == QEvent.Show:
                self._last_main_category = obj.currentText()

            if event.type() == QEvent.Hide:
                txt = obj.currentText()

                # true valid = ชื่อหมวดจริงเท่านั้น
                valid = txt in self.categories

                if not valid:
                    obj.blockSignals(True)
                    obj.setCurrentText(self._last_main_category)
                    obj.blockSignals(False)

            return False

        # ============================================================
        # 3) ComboBox: หมวดย่อย
        # ============================================================
        if isinstance(obj, QComboBox) and obj.property("type") == "sub_cat":

            if event.type() == QEvent.Show:
                self._last_sub_category = obj.currentText()

            if event.type() == QEvent.Hide:
                txt = obj.currentText()

                # rollback กรณียกเลิก/ค่าเพี้ยน
                if txt == "" or txt == "➕ เพิ่มหมวดย่อย":
                    obj.blockSignals(True)
                    obj.setCurrentText(self._last_sub_category)
                    obj.blockSignals(False)

            return False

        return False


    def finish_scan(self):
        self.scan_timer.stop()
        if not self.scan_buffer:
            return

        raw = self.scan_buffer.strip()
        self.scan_buffer = ""

        # ⭐ แปลง (เลขไทย + คีย์ไทย) → ตัวเลขจริง
        code = self.convert_thai_digits(raw)
        code = self.convert_thai_keyboard_barcode(code)   # ← อันนี้ใช้ mapping ที่ SellTab ใช้

        # ใส่ลงช่องค้นหา + ค้นหา
        self.search_box.setText(code)
        self.apply_filter()

    # ---------------------------------------------------------
    # บันทึกทั้งหมด (ปุ่ม)
    # ---------------------------------------------------------
    def save_all_products(self, suppress_popup=False, skip_history=False):
        from db import add_history

        # ================================
        # 1) เก็บ qty เดิมของทุกสินค้า
        # ================================
        old_qty_map = {p["barcode"]: p["qty"] for p in self.all_products}

        # ================================
        # 2) บันทึกสินค้าในตารางลง DB
        # ================================
        for r in range(self.table.rowCount()):
            item0 = self.table.item(r, 0)
            if not item0 or item0.data(Qt.UserRole) in ("header", "sub_header"):
                continue

            try:
                bc    = self.table.item(r, 5).text().strip()
                name  = self.table.item(r, 1).text().strip()
                price = float(self.table.item(r, 2).text())
                cost  = float(self.table.item(r, 3).text())
                qty   = int(self.table.item(r, 4).text())
            except Exception:
                continue

            # update สินค้า
            update_product_info(bc, name, price, cost, None)
            update_stock(bc, qty, absolute=True)

            # ================================
            # 3) บันทึก history (ถ้าไม่ skip)
            # ================================
            if skip_history:
                continue   # ⭐ สำคัญมาก

            old_qty = old_qty_map.get(bc)
            if old_qty is not None:
                qty_added = qty - old_qty
                if qty_added != 0:
                    add_history(bc, qty_added)

        # ================================
        # 4) รีโหลด & แจ้งผล
        # ================================
        self.dirty = False
        self.load_data()

        if not suppress_popup:
            QMessageBox.information(self, "สำเร็จ", "บันทึกข้อมูลทั้งหมดเรียบร้อย!")

        try:
            self.parent().history_tab.refresh_now()
        except:
            pass



    def manage_categories(self):
        # ================================
        # 1) เลือกว่าจะจัดการอะไร?
        # ================================
        mode, ok = QInputDialog.getItem(
            self,
            "จัดการหมวดหมู่",
            "เลือกประเภทการจัดการ:",
            [
                "🗂 จัดการหมวดหลัก",
                "🗂 จัดการหมวดย่อย"
            ],
            editable=False
        )
        if not ok:
            return

        # ----------------------------------------
        # 2) โหมดจัดการหมวดหลัก (ใช้ของเดิม)
        # ----------------------------------------
        if mode == "🗂 จัดการหมวดหลัก":
            return self.manage_main_categories()

        # ----------------------------------------
        # 3) โหมดจัดการหมวดย่อย
        # ----------------------------------------
        if mode == "🗂 จัดการหมวดย่อย":
            return self.manage_sub_categories()

            # ---------------------------------------------------------
        # จัดการหมวดหมู่ (ใช้ logic ใกล้เคียงของเดิม)
        # ---------------------------------------------------------

    def manage_main_categories(self):
        categories = get_categories()

        # =======================================================
        # ⭐ กรณีไม่มีหมวดเลย → ให้เพิ่มหมวดแรกได้ทันที
        # =======================================================
        if not categories:
            new_cat, ok = QInputDialog.getText(
                self,
                "เพิ่มหมวดหมู่แรก",
                "ยังไม่มีหมวดหมู่\nกรุณากรอกชื่อหมวดหมู่เเรก"
            )
            if ok and new_cat.strip():
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute(
                    "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                    (new_cat.strip(),)
                )
                conn.commit()
                conn.close()

                self.load_data()
                self.reload_categories_in_table()
                self.dirty = True
            return

        # =======================================================
        # ⭐ มีหมวดแล้ว → แสดงเมนูจัดการหมวด
        # =======================================================
        action, ok = QInputDialog.getItem(
            self,
            "จัดการหมวดหมู่",
            "เลือกการทำงาน:",
            [
                "➕ เพิ่มหมวดหมู่ใหม่",
                "✏ เปลี่ยนชื่อหมวดหมู่",
                "🔁 ย้ายสินค้าทั้งหมวดไปหมวดใหม่",
                "🗑 ลบหมวดหมู่"
            ],
            editable=False
        )
        if not ok:
            return

        # =======================================================
        # ➕ เพิ่มหมวดหมู่ใหม่
        # =======================================================
        if action == "➕ เพิ่มหมวดหมู่ใหม่":
            new_cat, ok2 = QInputDialog.getText(self, "เพิ่มหมวด", "ชื่อหมวด:")
            if ok2 and new_cat.strip():
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute(
                    "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                    (new_cat.strip(),)
                )
                conn.commit()
                conn.close()

                self.load_data()
                self.reload_categories_in_table()
                self.dirty = True
            return

        # =======================================================
        # ✏ เปลี่ยนชื่อหมวดหมู่
        # =======================================================
        if action == "✏ เปลี่ยนชื่อหมวดหมู่":
            old, ok2 = QInputDialog.getItem(
                self,
                "เลือกหมวด",
                "หมวดเดิม:",
                categories,
                editable=False
            )
            if not ok2:
                return

            new_name, ok3 = QInputDialog.getText(self, "แก้ชื่อหมวด", "ชื่อใหม่:")
            if ok3 and new_name.strip():
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute("UPDATE categories SET name=? WHERE name=?", (new_name, old))
                cur.execute("UPDATE products SET main_category=? WHERE main_category=?", (new_name, old))
                conn.commit()
                conn.close()

                self.load_data()
                self.reload_categories_in_table()
                self.dirty = True
            return

        # =======================================================
        # 🔁 ย้ายสินค้าทั้งหมวดไปหมวดใหม่
        # =======================================================
        if action == "🔁 ย้ายสินค้าทั้งหมวดไปหมวดใหม่":
            from_cat, ok2 = QInputDialog.getItem(
                self,
                "เลือกหมวดเดิม",
                "ย้ายออกจาก:",
                categories,
                editable=False
            )
            if not ok2:
                return

            to_cat, ok3 = QInputDialog.getItem(
                self,
                "เลือกหมวดใหม่",
                "ย้ายไป:",
                categories,
                editable=False
            )
            if not ok3 or to_cat == from_cat:
                return

            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute(
                "UPDATE products SET main_category=? WHERE main_category=?",
                (to_cat, from_cat)
            )
            conn.commit()
            conn.close()

            self.load_data()
            self.reload_categories_in_table()
            self.dirty = True
            return

        # =======================================================
        # 🗑 ลบหมวดหมู่
        # =======================================================
        if action == "🗑 ลบหมวดหมู่":
            cat, ok2 = QInputDialog.getItem(
                self,
                "ลบหมวด",
                "เลือกหมวด:",
                categories,
                editable=False
            )
            if not ok2:
                return

            confirm = QMessageBox.question(
                self,
                "ยืนยันลบ",
                f"ต้องการลบหมวด '{cat}' จริงหรือไม่?\nสินค้าจะถูกตั้งเป็น 'ไม่มีหมวดหมู่'",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute("DELETE FROM categories WHERE name=?", (cat,))
                cur.execute("UPDATE products SET main_category='ไม่มีหมวดหมู่' WHERE main_category=?", (cat,))
                conn.commit()
                conn.close()

                self.load_data()
                self.reload_categories_in_table()
                self.dirty = True
            return




    def manage_sub_categories(self):
        # 1) เลือกหมวดหลักก่อน
        main_cat_list = get_categories()
        if not main_cat_list:
            QMessageBox.information(self, "แจ้งเตือน", "ยังไม่มีหมวดหลัก")
            return

        parent, ok = QInputDialog.getItem(
            self,
            "เลือกหมวดหลัก",
            "เลือกหมวดหลักที่ต้องการจัดการหมวดย่อย:",
            main_cat_list,
            editable=False
        )
        if not ok:
            return

        # 2) โหลดหมวดย่อย
        subs = self.get_sub_categories_for(parent)
        if not subs:
            subs = []

        subs_display = subs[:] if subs else []
        subs_display.insert(0, "➕ เพิ่มหมวดย่อยใหม่")

        action, ok2 = QInputDialog.getItem(
            self,
            f"จัดการหมวดย่อย ({parent})",
            "เลือกการทำงาน:",
            [
                "➕ เพิ่มหมวดย่อยใหม่",
                "✏ เปลี่ยนชื่อหมวดย่อย",
                "🗑 ลบหมวดย่อย"
            ],
            editable=False
        )
        if not ok2:
            return

        # -------------------------
        # เพิ่มหมวดย่อย
        # -------------------------
        if action == "➕ เพิ่มหมวดย่อยใหม่":
            new_sub, ok3 = QInputDialog.getText(
                self, "เพิ่มหมวดย่อย", f"ชื่อหมวดย่อยใหม่ใน '{parent}':"
            )
            if ok3 and new_sub.strip():
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute("INSERT OR IGNORE INTO sub_categories(parent_category, name) VALUES (?,?)",
                            (parent, new_sub.strip()))
                conn.commit()
                conn.close()

                self.load_data()
                QMessageBox.information(self, "สำเร็จ", "เพิ่มหมวดย่อยสำเร็จ!")
            return

        # -------------------------
        # เปลี่ยนชื่อหมวดย่อย
        # -------------------------
        if action == "✏ เปลี่ยนชื่อหมวดย่อย":
            if not subs:
                QMessageBox.information(self, "แจ้งเตือน", "หมวดนี้ยังไม่มีหมวดย่อย")
                return

            old_sub, ok3 = QInputDialog.getItem(
                self,
                "เลือกหมวดย่อย",
                "หมวดย่อยเดิม:",
                subs,
                editable=False
            )
            if not ok3:
                return

            new_sub, ok4 = QInputDialog.getText(
                self,
                "เปลี่ยนชื่อหมวดย่อย",
                "ชื่อใหม่:"
            )
            if ok4 and new_sub.strip():
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute("""
                    UPDATE sub_categories
                    SET name=?
                    WHERE parent_category=? AND name=?
                """, (new_sub.strip(), parent, old_sub))
                cur.execute("""
                    UPDATE products SET sub_category=?
                    WHERE main_category=? AND sub_category=?
                """, (new_sub.strip(), parent, old_sub))
                conn.commit()
                conn.close()

                self.load_data()
                QMessageBox.information(self, "สำเร็จ", "แก้ไขชื่อสำเร็จ!")
            return

        # -------------------------
        # ลบหมวดย่อย
        # -------------------------
        if action == "🗑 ลบหมวดย่อย":
            if not subs:
                QMessageBox.information(self, "แจ้งเตือน", "ยังไม่มีหมวดย่อย")
                return

            sub, ok3 = QInputDialog.getItem(
                self,
                "ลบหมวดย่อย",
                "เลือกหมวดย่อย:",
                subs,
                editable=False
            )
            if not ok3:
                return

            confirm = QMessageBox.question(
                self,
                "ยืนยัน",
                f"ต้องการลบ '{sub}' หรือไม่?\nสินค้าจะถูกตั้งเป็น 'ไม่มีหมวดย่อย'",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return

            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("DELETE FROM sub_categories WHERE parent_category=? AND name=?", (parent, sub))
            cur.execute("UPDATE products SET sub_category='' WHERE main_category=? AND sub_category=?",
                        (parent, sub))
            conn.commit()
            conn.close()

            self.load_data()
            QMessageBox.information(self, "สำเร็จ", "ลบหมวดย่อยสำเร็จ!")


    # ---------------------------------------------------------
    # Import / Export Excel
    # ---------------------------------------------------------
    def import_excel(self):
        last_path = self.get_last_stock_path()

        file, _ = QFileDialog.getOpenFileName(
            self,
            "เลือกไฟล์ Excel",
            last_path,
            "Excel Files (*.xlsx *.xls)"
        )
        if not file:
            return

        self.save_last_stock_path(file)

        try:
            import_from_excel(file)       # ⭐ โหลดเข้า DB

            self.load_data()              # ⭐ โหลด DB → ตารางอีกครั้ง
            self.render_table(self.all_products)  # ⭐ บังคับวาดใหม่

            self.save_all_products(suppress_popup=True)   # ไม่ให้โชว์ popup ของ save
      
            self.refresh()                # ⭐⭐ รีเฟรชหน้าอีกครั้งให้ combobox / alias / table updated

            QMessageBox.information(self, "สำเร็จ", "นำเข้าข้อมูลสำเร็จ!")

        except Exception as e:
            self.show_scrollable_message("ผิดพลาด", str(e))



    def get_table_products(self):
        products = []

        for r in range(self.table.rowCount()):
            item0 = self.table.item(r, 0)

            # ข้ามหัวหมวด / หัวหมวดย่อย
            if not item0 or item0.data(Qt.UserRole) in ("header", "sub_header"):
                continue

            try:
                name     = self.table.item(r, 1).text()
                price    = float(self.table.item(r, 2).text())
                cost     = float(self.table.item(r, 3).text())
                qty      = int(self.table.item(r, 4).text())
                barcode  = self.table.item(r, 5).text()
                main_cat = self.table.item(r, 6).text()
                sub_cat  = self.table.item(r, 7).text()
            except Exception:
                continue

            products.append({
                "barcode": barcode,
                "name": name,
                "price": price,
                "cost": cost,
                "qty": qty,
                "category": main_cat,
                "sub_category": sub_cat,
            })

        return products




    def export_excel(self):
        self.save_all_products()   # <-- บังคับบันทึกลง DB ก่อน
        last_path = self.get_last_stock_path()

        default_name = f"{last_path}/stock_export.xlsx" if last_path else "stock_export.xlsx"

        file, _ = QFileDialog.getSaveFileName(
            self,
            "บันทึกไฟล์ Excel",
            default_name,
            "Excel Files (*.xlsx)"
        )
        if not file:
            return

        # บันทึก path ล่าสุด
        self.save_last_stock_path(file)

        try:
            import pandas as pd

            products = self.get_table_products()
            if not products:
                QMessageBox.information(self, "แจ้งเตือน", "ยังไม่มีข้อมูลในตารางให้ส่งออก")
                return

            # สร้าง DataFrame + ตั้งหัวตารางเป็นภาษาไทย
            df = pd.DataFrame(products)
            df = df[["barcode", "name", "price", "cost", "qty", "category", "sub_category"]]
            df.columns = [
                "บาร์โค้ด",
                "ชื่อสินค้า",
                "ราคาขาย",
                "ราคาทุน",
                "จำนวนคงเหลือ",
                "หมวดหลัก",
                "หมวดย่อย"
            ]

            # ใช้ XlsxWriter เพื่อจัดรูปแบบ
            with pd.ExcelWriter(file, engine="xlsxwriter") as writer:
                sheet_name = "Stock"
                df.to_excel(writer, sheet_name=sheet_name, index=False)

                workbook  = writer.book
                worksheet = writer.sheets[sheet_name]

                # ---------- สร้างรูปแบบ ----------
                header_fmt = workbook.add_format({
                    "bold": True,
                    "font_size": 12,
                    "font_name": "Sarabun",
                    "align": "center",
                    "valign": "vcenter",
                    "bg_color": "#4CAF50",   # เขียว
                    "font_color": "white",
                    "border": 1,
                })

                text_fmt = workbook.add_format({
                    "font_name": "Sarabun",
                    "font_size": 11,
                    "valign": "vcenter",
                    "border": 1,
                })

                num_fmt = workbook.add_format({
                    "font_name": "Sarabun",
                    "font_size": 11,
                    "valign": "vcenter",
                    "border": 1,
                    "num_format": "#,##0.00",
                })

                int_fmt = workbook.add_format({
                    "font_name": "Sarabun",
                    "font_size": 11,
                    "valign": "vcenter",
                    "border": 1,
                    "num_format": "#,##0",
                })

                zebra_fmt = workbook.add_format({
                    "bg_color": "#F5F5F5",
                })

                # ---------- เขียนหัวตารางใหม่ด้วย header_fmt ----------
                for col, name in enumerate(df.columns):
                    worksheet.write(0, col, name, header_fmt)

                # ---------- ตั้งความกว้างคอลัมน์ + format ----------
                for col_idx, col_name in enumerate(df.columns):
                    series = df[col_name].astype(str)
                    max_len = max([len(col_name)] + [len(s) for s in series])
                    width = max_len + 2

                    if col_name in ("ราคาขาย", "ราคาทุน"):
                        worksheet.set_column(col_idx, col_idx, width, num_fmt)
                    elif col_name == "จำนวนคงเหลือ":
                        worksheet.set_column(col_idx, col_idx, width, int_fmt)
                    else:
                        worksheet.set_column(col_idx, col_idx, width, text_fmt)

                # ---------- แถวสลับสี (zebra) ----------
                last_row = len(df)
                last_col = len(df.columns) - 1
                worksheet.conditional_format(
                    1, 0, last_row, last_col,
                    {
                        "type": "formula",
                        "criteria": "=MOD(ROW(),2)=0",
                        "format": zebra_fmt
                    }
                )

                # ---------- Freeze header + AutoFilter ----------
                worksheet.freeze_panes(1, 0)
                worksheet.autofilter(0, 0, last_row, last_col)

            QMessageBox.information(self, "สำเร็จ", "ส่งออกข้อมูลสำเร็จ! (จัดรูปแบบแล้ว)")

        except Exception as e:
            QMessageBox.warning(self, "ผิดพลาด", str(e))


    # ---------------------------------------------------------
    # 🔥 ใช้กับ Auto-save จาก Main (ไม่ popup, ไม่ reload)
    # ---------------------------------------------------------
    def save_if_dirty(self):
        if not self.dirty:
            return

        for r in range(self.table.rowCount()):
            item0 = self.table.item(r, 0)
            if not item0 or item0.data(Qt.UserRole) in ("header", "sub_header"):
                continue

            try:
                bc    = self.table.item(r, 5).text().strip()
                name  = self.table.item(r, 1).text().strip()
                price = float(self.table.item(r, 2).text())
                cost  = float(self.table.item(r, 3).text())
                qty   = int(self.table.item(r, 4).text())
            except Exception:
                continue

            update_product_info(bc, name, price, cost)

            update_stock(bc, qty, absolute=True)

        self.dirty = False
        self.saved.emit()   # ⭐ แจ้งว่าเซฟเสร็จแล้ว


    def close_all_editors(self):
        # ปิด item editor ทั้งหมด
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item:
                    self.table.closePersistentEditor(item)

        # ปิด editor ของ cellWidget เช่น QComboBox ด้วย
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                widget = self.table.cellWidget(r, c)
                if widget:
                    widget.clearFocus()
                    widget.setDisabled(True)
                    widget.setDisabled(False)


    # ---------------------------------------------------------
    # จำตำแหน่งไฟล์ล่าสุด (โฟลเดอร์ Import/Export)
    # ---------------------------------------------------------
    def get_last_stock_path(self):
        import os, json
        if not os.path.exists(LAST_STOCK_PATH):
            return ""
        try:
            with open(LAST_STOCK_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("path", "")
        except:
            return ""

    def save_last_stock_path(self, filepath):
        import json, os
        folder = os.path.dirname(filepath)
        with open(LAST_STOCK_PATH, "w", encoding="utf-8") as f:
            json.dump({"path": folder}, f, ensure_ascii=False, indent=2)



    # ---------------------------------------------------------
    # hook จาก Main เวลาอยากให้รีเฟรช
    # ---------------------------------------------------------
    def refresh(self):
        self.load_data()
        self.alias_map = get_barcode_alias_map()

    def refresh_now(self):
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(20, self.refresh)

    # ---------------------------------------------------------
    # หา category ของแถวใดแถวหนึ่ง (เดินย้อนขึ้นไปหา header)
    # ---------------------------------------------------------
    def get_category_of_row(self, row):
        r = row
        while r >= 0:
            item0 = self.table.item(r, 0)
            if item0 and item0.data(Qt.UserRole) == "header":
                # ชื่อหมวดอยู่คอลัมน์ 1 แล้ว
                name_item = self.table.item(r, 1)
                return name_item.text().strip() if name_item else None
            r -= 1
        return None

    
    def get_sub_category_of_row(self, row):
        r = row
        while r >= 0:
            item = self.table.item(r, 0)
            if item and item.data(Qt.UserRole) == "sub_header":
                # ชื่อหมวดย่อยถูกเก็บในคอลัมน์ 1
                name_item = self.table.item(r, 1)
                return name_item.text().strip() if name_item else None
            r -= 1
        return None



    # ---------------------------------------------------------
    # หลังลากเรียง → คำนวณ sort_order ใหม่ในหมวดนั้น
    # ---------------------------------------------------------
    def recalculate_sort_order(self, category):
        print(f"[StockTab] recalculate_sort_order category={category}")
        header_row = self.category_rows.get(category)
        print(f"[StockTab] header_row for '{category}' = {header_row}")
        if header_row is None:
            print("[StockTab] recalculate_sort_order: header_row is None → return")
            return

        barcodes_in_order = []

        r = header_row + 1
        while r < self.table.rowCount():
            item = self.table.item(r, 0)
            if item and item.data(Qt.UserRole) == "header":
                break

            bc_item = self.table.item(r, 4)
            if bc_item:
                barcodes_in_order.append(bc_item.text())

            r += 1

        print(f"[StockTab] barcodes_in_order = {barcodes_in_order}")

        # อัปเดต sort_order ลง DB
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        for idx, bc in enumerate(barcodes_in_order):
            print(f"[StockTab] UPDATE sort_order={idx} for barcode={bc}")
            cur.execute("UPDATE products SET sort_order=? WHERE barcode=?", (idx, bc))
        conn.commit()
        conn.close()

        # sync all_products ในหน่วยความจำ
        for p in self.all_products:
            if p["category"] == category and p["barcode"] in barcodes_in_order:
                p["sort_order"] = barcodes_in_order.index(p["barcode"])

        # ถือว่าเป็นการแก้ไข → dirty
        self.dirty = True
        print(f"[StockTab] recalculate_sort_order DONE for category={category}")

    # ---------------------------------------------------------
    # ย้ายแถวเองแบบ custom (เพราะ InternalMove ทำตารางพัง)
    # ---------------------------------------------------------
    def move_product_row(self, src, dst):
        print(f"[StockTab] move_product_row START src={src} dst={dst}")

        # --- BLOCK 1: กันลากข้ามหมวด ---
        cat_src = self.get_category_of_row(src)
        cat_dst = self.get_category_of_row(dst)
        if cat_src != cat_dst:
            print("❌ BLOCK: cannot move across categories")
            return

        # --- BLOCK 2: กันลากใส่หัวหมวด ---
        item_dst = self.table.item(dst, 0)
        if item_dst and item_dst.data(Qt.UserRole) in ("header", "sub_header"):
            print("❌ BLOCK: cannot drop on header")
            return

        # ---------------------------
        #  BACKUP DATA จาก src row
        # ---------------------------
        row_data = []
        barcode = None

        for col in range(self.table.columnCount()):
            widget = self.table.cellWidget(src, col)
            if widget:
                row_data.append(("WIDGET", widget))
                continue

            item = self.table.item(src, col)
            if item:

                # ⭐⭐⭐ FIX: BLOCK — ห้าม clone header / sub_header ⭐⭐⭐
                if item.data(Qt.UserRole) in ("header", "sub_header"):
                    row_data.append(("ITEM", QTableWidgetItem("")))
                    continue

                clone = QTableWidgetItem(item.text())
                clone.setBackground(item.background())
                clone.setTextAlignment(item.textAlignment())
                clone.setFont(item.font())
                clone.setData(Qt.UserRole, item.data(Qt.UserRole))
                clone.setFlags(item.flags())
                row_data.append(("ITEM", clone))

                if col == 5:
                    barcode = item.text()
            else:
                row_data.append(None)

        # --- DELETE SRC ROW ---
        self.table.removeRow(src)

        # --- INSERT NEW ROW ---
        self.table.insertRow(dst)

        # ---------------------------
        #  RESTORE DATA TO NEW ROW
        # ---------------------------
        for col in range(self.table.columnCount()):
            typ, data = (None, None)
            if row_data[col]:
                typ, data = row_data[col]

            if typ == "WIDGET":
                old_widget = data

                # combobox
                if isinstance(old_widget, QComboBox):
                    new = QComboBox()
                    for i in range(old_widget.count()):
                        new.addItem(old_widget.itemText(i))
                    new.setCurrentIndex(old_widget.currentIndex())

                    if col == 6:
                        new.currentTextChanged.connect(
                            lambda v, bc=barcode: self.handle_category_change(v, bc)
                        )
                    if col == 7:
                        new.currentTextChanged.connect(
                            lambda v, bc=barcode: self.handle_sub_category_change(v, bc)
                        )

                    self.table.setCellWidget(dst, col, new)

                else:
                    # ปุ่มลบ
                    btn = self.create_delete_button(barcode)
                    self.table.setCellWidget(dst, col, btn)

            elif typ == "ITEM":
                old_item = data

                # ⭐⭐⭐ FIX: BLOCK — ห้าม restore header / sub_header ⭐⭐⭐
                if old_item.data(Qt.UserRole) in ("header", "sub_header"):
                    new_item = QTableWidgetItem("")
                    self.table.setItem(dst, col, new_item)
                    continue

                new_item = QTableWidgetItem(old_item.text())
                new_item.setFont(old_item.font())
                new_item.setTextAlignment(old_item.textAlignment())

                # ⭐ ใช้สีเดิมของ item ต้นฉบับ (ไม่ให้ Qt สุ่มเป็นสีดำ)
                new_item.setBackground(QtGui.QColor("#ffffff"))
                new_item.setForeground(QtGui.QColor("#000000"))


                new_item.setData(Qt.UserRole, old_item.data(Qt.UserRole))
                self.table.setItem(dst, col, new_item)


            else:
                self.table.setItem(dst, col, QTableWidgetItem(""))

        self.table.setRowHeight(dst, 45)

        print(f"[StockTab] move_product_row DONE src={src} → dst={dst}")

        # -------------------------------------------------------
        #  FIX ลำดับใหม่ตาม sub-category
        # -------------------------------------------------------
        new_sub = self.get_sub_category_of_row(dst)
        if new_sub:
            self.recalc_sub_order(cat_dst, new_sub)

        # -------------------------------------------------------
        #  FIX sort_order ทุกสินค้าภายในหมวดใหญ่
        # -------------------------------------------------------
        self.recalculate_sort_order(cat_dst)

        # -------------------------------------------------------
        #  FIX sub-order อีกครั้ง
        # -------------------------------------------------------
        cat = self.get_category_of_row(dst)
        sub = self.get_sub_category_of_row(dst)
        if sub:
            self.recalc_sub_order(cat, sub)


    def force_pure_item(self, row, col):
        """
        ลบ widget ออกจาก cell ให้หมดจริง ๆ 
        และบังคับให้ cell ใช้ QTableWidgetItem แบบธรรมดาเท่านั้น
        """

        # 1) ถ้ามี widget → ลบทิ้ง
        w = self.table.cellWidget(row, col)
        if w:
            w.setParent(None)
            self.table.removeCellWidget(row, col)

        # 2) บังคับสร้าง QTableWidgetItem ใหม่ทับของเดิม
        old_item = self.table.item(row, col)
        new_item = QTableWidgetItem("" if old_item is None else old_item.text())

        if old_item:
            new_item.setFont(old_item.font())
            new_item.setBackground(old_item.background())
            new_item.setForeground(old_item.foreground())
            new_item.setTextAlignment(old_item.textAlignment())
            new_item.setData(Qt.UserRole, old_item.data(Qt.UserRole))

        self.table.setItem(row, col, new_item)




    def recalc_sub_order(self, main, sub):
        key = (main, sub)
        header_row = self.sub_category_rows.get(key)
        if header_row is None:
            return

        index = 1
        r = header_row + 1

        while r < self.table.rowCount():
            it = self.table.item(r, 0)

            # เจอหัวหมวดหรือหัวหมวดย่อย → จบ
            if it and it.data(Qt.UserRole) in ("header", "sub_header"):
                break

            # ⭐ อัปเดตเลขลำดับเฉพาะสินค้า
            if it:
                it.setText(str(index))
                index += 1

            r += 1


    def get_sub_categories_for(self, category):
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sub_categories WHERE parent_category=?", (category,))
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows] if rows else []


    def handle_sub_category_change(self, sub, barcode):
        combo = self.sender()

        # 🔹 1) เลือก "➕ เพิ่มหมวดย่อย"
        if sub == "➕ เพิ่มหมวดย่อย":
            # หา main category ของสินค้าตัวนี้
            main_cat = None
            for p in self.all_products:
                if p["barcode"] == barcode:
                    main_cat = p["category"]
                    break

            if not main_cat:
                # ไม่มีหมวดหลัก → ยกเลิก
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)
                return

            new_sub, ok = QInputDialog.getText(
                self,
                "เพิ่มหมวดย่อย",
                f"ชื่อหมวดย่อยใหม่ในหมวด '{main_cat}':"
            )
            if not ok or not new_sub.strip():
                # ยกเลิก → กลับค่าเดิม
                old_sub = None
                for p in self.all_products:
                    if p["barcode"] == barcode:
                        old_sub = p["sub_category"] or "ไม่มีหมวดย่อย"
                        break
                combo.blockSignals(True)
                if old_sub:
                    combo.setCurrentText(old_sub)
                else:
                    combo.setCurrentIndex(0)
                combo.blockSignals(False)
                return

            new_sub = new_sub.strip()

            # บันทึกหมวดย่อยใหม่ในตาราง sub_categories + อัปเดตสินค้า
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO sub_categories (parent_category, name) VALUES (?, ?)",
                (main_cat, new_sub)
            )
            cur.execute("UPDATE products SET sub_category=? WHERE barcode=?", (new_sub, barcode))
            conn.commit()
            conn.close()

            # sync memory
            for p in self.all_products:
                if p["barcode"] == barcode:
                    p["sub_category"] = new_sub
                    break

            # reload รายการหมวดย่อยใน combobox ตัวนี้
            subs = self.get_sub_categories_for(main_cat)

            combo.blockSignals(True)
            combo.clear()
            if "ไม่มีหมวดย่อย" not in subs:
                combo.addItem("ไม่มีหมวดย่อย")
            for s in subs:
                combo.addItem(s)
            combo.addItem("➕ เพิ่มหมวดย่อย")
            combo.setCurrentText(new_sub)
            combo.blockSignals(False)

            self.dirty = True
            return

        # 🔹 2) เลือก "ไม่มีหมวดย่อย" → เซฟเป็นค่าว่างใน DB
        if sub == "ไม่มีหมวดย่อย":
            db_sub = ""
        else:
            db_sub = sub

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("UPDATE products SET sub_category=? WHERE barcode=?", (db_sub, barcode))
        conn.commit()
        conn.close()

        # sync memory
        for p in self.all_products:
            if p["barcode"] == barcode:
                p["sub_category"] = db_sub
                break

        self.dirty = True

    def ensure_sub_category_table(self):
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        # ตารางหมวดย่อย
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sub_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_category TEXT,
                name TEXT
            )
        """)

        # เพิ่มคอลัมน์ sub_category ให้ products ถ้ายังไม่มี
        cur.execute("PRAGMA table_info(products)")
        cols = [r[1] for r in cur.fetchall()]
        if "sub_category" not in cols:
            cur.execute("ALTER TABLE products ADD COLUMN sub_category TEXT DEFAULT ''")

        conn.commit()
        conn.close()


    def show_calc_price_popup(self):
        # ------------------------
        # 1) เลือกหมวดหลัก
        # ------------------------
        main_list = get_categories()
        if not main_list:
            QMessageBox.warning(self, "แจ้งเตือน", "ยังไม่มีหมวดหลัก")
            return

        main_cat, ok = QInputDialog.getItem(
            self, "เลือกหมวดหลัก", "หมวดหลัก:", main_list, editable=False
        )
        if not ok:
            return

        # ------------------------
        # 2) เลือกหมวดย่อย
        # ------------------------
        subs = self.get_sub_categories_for(main_cat)
        if "ไม่มีหมวดย่อย" not in subs:
            subs.insert(0, "ไม่มีหมวดย่อย")

        if not subs:
            QMessageBox.warning(self, "แจ้งเตือน", "หมวดนี้ยังไม่มีหมวดย่อย")
            return

        sub_cat, ok2 = QInputDialog.getItem(
            self, "เลือกหมวดย่อย", f"หมวดย่อยใน '{main_cat}' :", subs, editable=False
        )
        if not ok2:
            return

        # ------------------------
        # 3) ใส่จำนวนกำไร (บาท)
        # ------------------------
        profit_txt, ok3 = QInputDialog.getText(
            self,
            "เพิ่มกำไร",
            "เพิ่มกำไรจากราคาทุน (บาท):"
        )
        if not ok3 or not profit_txt.strip():
            return

        try:
            profit = float(profit_txt)
        except:
            QMessageBox.warning(self, "ผิดพลาด", "กรุณาใส่จำนวนเงินให้ถูกต้อง")
            return

        # ------------------------
        # 4) อัปเดตราคาสินค้าทั้งหมวดย่อย
        # ------------------------
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        db_sub = "" if sub_cat == "ไม่มีหมวดย่อย" else sub_cat

        # ดึง p ทั้งหมวดย่อย
        cur.execute("""
            SELECT barcode, cost FROM products
            WHERE main_category=? AND (sub_category=? OR (?='' AND sub_category=''))
        """, (main_cat, db_sub, db_sub))

        items = cur.fetchall()

        for bc, cost in items:
            new_price = float(cost) + profit
            cur.execute("UPDATE products SET price=? WHERE barcode=?", (new_price, bc))

            # sync memory
            for p in self.all_products:
                if p["barcode"] == bc:
                    p["price"] = new_price
                    break

        conn.commit()
        conn.close()

        # ------------------------
        # 5) รีเฟรชเฉพาะหมวดย่อย
        # ------------------------
        self.render_table(self.all_products)

        # ขยายเฉพาะหมวด + หมวดย่อยที่แก้
        if main_cat in self.category_rows:
            self.expand_category(main_cat)

        key = (main_cat, sub_cat)
        if key in self.sub_category_rows:
            self.sub_category_collapsed[key] = False
            header_row = self.sub_category_rows[key]

            item0 = self.table.item(header_row, 0)
            if item0:
                item0.setText("▾")

            # แสดงสินค้าในหมวดย่อย
            r = header_row + 1
            while r < self.table.rowCount():
                it = self.table.item(r, 0)
                if it.data(Qt.UserRole) in ("header", "sub_header"):
                    break
                self.table.setRowHidden(r, False)
                r += 1

        QMessageBox.information(
            self, "สำเร็จ",
            f"อัปเดตราคาในหมวดย่อย '{sub_cat}' เรียบร้อย!"
        )
