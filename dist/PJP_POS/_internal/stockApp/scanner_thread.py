import os
import sys
import cv2
import ctypes
import time
import winsound
from PySide6.QtCore import QThread, Signal

# ----------------------------------------------------------
#  พยายามโหลด pyzbar แบบปลอดภัย
# ----------------------------------------------------------
def _dummy_decode(*args, **kwargs):
    return []

try:
    from pyzbar.pyzbar import decode as _real_decode
    decode = _real_decode
    print("✔ pyzbar โหลดสำเร็จ")
except Exception as e:
    print("⚠ pyzbar โหลดไม่ได้ → ปิดฟีเจอร์อ่านกล้อง:", e)
    decode = _dummy_decode


class BarcodeScannerThread(QThread):
    code_detected = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.last_scan_time = 0

    def run(self):
        # ถ้า decode เป็น dummy → ไม่เปิดกล้อง
        if decode is _dummy_decode:
            print("⚠ ไม่มี pyzbar → ไม่เปิดกล้อง")
            return

        self.running = True

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if not cap.isOpened():
            print("❌ Cannot open camera")
            return

        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue

            barcodes = decode(frame)
            now = time.time()

            for b in barcodes:
                code = b.data.decode("utf-8")

                if now - self.last_scan_time < 1:
                    continue

                self.last_scan_time = now
                self.code_detected.emit(code)
                winsound.Beep(2000, 80)

            time.sleep(1)

        cap.release()

    def stop(self):
        self.running = False
        self.wait()
