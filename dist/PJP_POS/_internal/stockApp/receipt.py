# receipt.py
import os, datetime, platform
from decimal import Decimal
from pathlib import Path

# --- ESC/POS (optional) ---
ESC_POS_AVAILABLE = False
try:
    from escpos.printer import Win32Raw, Usb
    ESC_POS_AVAILABLE = True
except Exception:
    ESC_POS_AVAILABLE = False

# --- PDF ---
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# เตรียมโฟลเดอร์เก็บใบเสร็จ
RECEIPT_DIR = Path("receipts")
RECEIPT_DIR.mkdir(exist_ok=True)

# ฟอนต์ไทย
def _register_thai_font():
    fonts_dir = Path("fonts")
    candidates = ["NotoSansThai-Regular.ttf", "THSarabunNew.ttf", "Sarabun-Regular.ttf"]
    for f in candidates:
        p = fonts_dir / f
        if p.exists():
            try:
                pdfmetrics.registerFont(TTFont("THAI", str(p)))
                return "THAI"
            except:
                pass
    return "Helvetica"

FONT_NAME = _register_thai_font()

# -------------------------------------------------------
# ESC/POS Print
# -------------------------------------------------------
def _print_escpos(items, meta, printer_name=None, usb_ids=None):
    if not ESC_POS_AVAILABLE:
        raise RuntimeError("ESC/POS not available")

    p = None
    if platform.system().lower().startswith("win") and printer_name:
        p = Win32Raw(printer_name)
    elif usb_ids:
        p = Usb(usb_ids[0], usb_ids[1], 0x81, 0x03)
    else:
        raise RuntimeError("No ESC/POS printer")

    p.set(align='center', width=2, height=2, text_type='B')
    p.text(meta['shop_name'] + "\n")

    p.set(align='center', width=1, height=1)
    if meta.get('shop_addr'):
        p.text(meta['shop_addr'] + "\n")
    if meta.get('tax_id'):
        p.text(f"เลขประจำตัวผู้เสียภาษี: {meta['tax_id']}\n")

    p.text("-" * 32 + "\n")
    p.text(f"{meta['dt']}  #{meta['receipt_no']}\n")
    p.text(f"แคชเชียร์: {meta.get('cashier','')}\n")
    p.text("-" * 32 + "\n")

    for it in items:
        p.set(align='left')
        p.text(it['name'][:22] + "\n")
        p.set(align='right')
        p.text(f"{it['qty']} x {it['price']:.2f} = {it['total']:.2f}\n")

    p.text("-" * 32 + "\n")
    p.set(align='right')
    p.text(f"ยอดรวม: {meta['subtotal']:.2f}\n")
    p.text(f"รับเงิน: {meta.get('cash',0):.2f}\n")
    p.text(f"เงินทอน: {meta.get('change',0):.2f}\n")

    p.text("-" * 32 + "\n")
    p.set(align='center')
    p.text("ขอบคุณที่อุดหนุนน้า\n\n")
    p.cut()


# -------------------------------------------------------
# CREATE PDF 57mm (Short Receipt)
# -------------------------------------------------------
def _make_pdf(items, meta):
    width = 57 * mm
    line_h = 3.8 * mm

    header = [
        "ร้านปัญจภัณฑ์",
        "101/2 หมู่8 ต.กระดังงา อ.บางคนที",
        "จ.สมุทรสงคราม 75120",
        f"เลขประจำตัวผู้เสียภาษี: {meta.get('tax_id','')}",
        "-" * 26,
        f"{meta['dt']}   #{meta['receipt_no']}",
        f"แคชเชียร์: {meta.get('cashier','')}",
        "-" * 26,
    ]

    lines = len(header) + len(items)*3 + 5
    height = lines * line_h + 6 * mm

    filename = RECEIPT_DIR / f"receipt_{meta['receipt_no']}.pdf"
    c = canvas.Canvas(str(filename), pagesize=(width, height))

    y = height - 4 * mm
    MARGIN = 6 * mm
    ITEM_INDENT = MARGIN + 1 * mm

    def draw_center(text, size=9):
        nonlocal y
        c.setFont(FONT_NAME, size)
        c.drawCentredString(width/2, y, text)
        y -= line_h

    def draw_right(text, size=9):
        nonlocal y
        c.setFont(FONT_NAME, size)
        c.drawRightString(width - MARGIN, y, text)
        y -= line_h

    # Header
    for h in header:
        draw_center(h)

    # Items
    for it in items:
        c.setFont(FONT_NAME, 9)
        c.drawString(ITEM_INDENT, y, it['name'])
        y -= line_h

        c.drawString(ITEM_INDENT, y, f"{it['qty']} x {it['price']:.2f} = {it['total']:.2f}")
        y -= line_h

        y -= 1.0 * mm

    draw_center("-" * 26)

    draw_right(f"ยอดรวม: {meta['subtotal']:.2f}")
    draw_right(f"รับเงิน: {meta.get('cash',0):.2f}")
    draw_right(f"เงินทอน: {meta.get('change',0):.2f}")

    draw_center("-" * 26)
    draw_center("ขอบคุณที่อุดหนุนน้า")

    c.showPage()
    c.save()
    return str(filename)


# -------------------------------------------------------
# MAIN PRINT FUNCTION
# -------------------------------------------------------
def print_receipt(items, meta, printer_name="Label Printer", usb_ids=None):
    """
    พยายาม ESC/POS ก่อน
    ถ้าไม่ได้ → สร้าง PDF แล้วสั่งปริ้นด้วย os.startfile()
    """
    # 1) ESC/POS
    if ESC_POS_AVAILABLE:
        try:
            _print_escpos(items, meta, printer_name, usb_ids)
            return None
        except Exception as e:
            print("ESC/POS error:", e)

    # 2) PDF fallback
    pdf_path = _make_pdf(items, meta)

    # แสดง popup เฉย ๆ ไม่ต้องเปิด PDF
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.information(
        None,
        "บันทึกใบเสร็จสำเร็จ",
        f"ไม่พบเครื่องปริ้น จึงบันทึกใบเสร็จเป็น PDF แทน\n\n{pdf_path}"
    )

