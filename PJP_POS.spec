# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# ------------------------------------------------------------------
# รวมไฟล์และโฟลเดอร์ที่โปรแกรมต้องใช้
# ------------------------------------------------------------------
datas = [
    ('fonts', 'fonts'),
    ('receipts', 'receipts'),
    ('stockApp', 'stockApp'),
    ('stock.db', '.'),
    ('stock_data.xlsx', '.'),
    ('_excel_path.txt', '.'),
    ('print_receipt.txt', '.'),
    ('NotoSansThai-Regular.ttf', '.'),
]

# ------------------------------------------------------------------
# สร้าง .exe จาก main.py ที่อยู่ในโฟลเดอร์ stockApp/
# ------------------------------------------------------------------
a = Analysis(
    ['stockApp/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'reportlab',
        'escpos',
        'escpos.printer',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ------------------------------------------------------------------
# ตั้งค่า EXE
# ------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PJP_POS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='C:/Panjapan/pjp.ico'
)

# ------------------------------------------------------------------
# รวมไฟล์ทั้งหมดลงในโฟลเดอร์ dist/PJP_POS
# ------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='PJP_POS'
)
('stockApp/libzbar-64.dll', '.'),
