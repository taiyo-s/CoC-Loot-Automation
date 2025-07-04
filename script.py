"""
PC-side listener for ESP32-CAM loot OCR.

Starts a serial session, requests frames, OCRs the three numbers
(gold, elixir, dark elixir) and optionally taps “next base”.
"""

import serial
import base64
import cv2
import numpy as np
import pytesseract
import subprocess
import time
from pathlib import Path
from datetime import datetime

# ---- Configuration ----
SERIAL_PORT = "..........."   # change to serial port
BAUD_RATE   = 460800

GOLD_LOOT_THRESHOLD        = 800_000 # change to preferred amount
ELIXIR_LOOT_THRESHOLD      = 800_000 # change to preferred amount
DARK_ELIXIR_LOOT_THRESHOLD = 10_000 # change to preferred amount
SKIP_PAUSE_SEC             = 5

START_MARK = "-----START-IMAGE-----"
END_MARK   = "-----END-IMAGE-----"
READY_MARK = "READY"
CAPTURE_SAVE_DIR = Path("captures")

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=10)


# ---------------------------------------------------------------------------

def notify_mac(title: str, message: str) -> None:
    subprocess.run([
        "osascript",
        "-e",
        f'display notification "{message}" with title "{title}" sound name "Ping"'
    ])


# ---------------------------------------------------------------------------

def flush_rx() -> None:
    """Drain anything sitting in the serial RX buffer."""
    while ser.in_waiting:
        ser.readline()


def wait_for_ready() -> None:
    """Block until ESP32 prints READY."""
    while True:
        raw = ser.readline()
        if raw and raw.decode(errors="ignore").strip() == READY_MARK:
            return


def read_one_image_b64() -> str:
    """Read exactly one Base-64 frame from serial and return its payload."""
    in_img, payload = False, []
    while True:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode(errors="ignore").strip()

        if line == START_MARK:
            in_img, payload = True, []
            continue
        if line == END_MARK:
            return "".join(payload)
        if in_img:
            payload.append(line)


def decode_base64_to_image(b64: str) -> np.ndarray:
    data = base64.b64decode(b64)
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

def parse_loot(text: str):
    """Extract gold, elixir and dark-elixir values from OCR’d multiline text."""
    gold = elixir = dark = 0
    # Keep non-empty lines only, preserving order
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    if len(lines) >= 3:
        try:
            gold   = int(''.join(filter(str.isdigit, lines[0])))
            elixir = int(''.join(filter(str.isdigit, lines[1])))
            dark   = int(''.join(filter(str.isdigit, lines[2])))
        except ValueError:
            print("[WARN] loot parse failed; non-numeric lines:", lines[:3])
    else:
        print(f"[WARN] loot parse failed; expected ≥3 lines, got {len(lines)}: {lines}")

    return gold, elixir, dark


# ---------------------------------------------------------------------------

def ocr(img: np.ndarray) -> tuple[int, int, int]:
    """
    Rotate the cropped screenshot, split into three equal horizontal bands,
    OCR each band with digits-only whitelist, and return integers.
    """
    CAPTURE_SAVE_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  
    cv2.imwrite(str(CAPTURE_SAVE_DIR / f"{ts}.jpg"), clean)
    img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img

    blur = cv2.GaussianBlur(gray, (3, 3), 0)

    _, thresh = cv2.threshold(blur, 200, 255, cv2.THRESH_BINARY_INV)

    # Upscale **and** keep the result
    thresh = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    
    # Remove tiny white dots (“pepper” noise)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    clean  = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    # ---- save original frame ----------------------------------
    CAPTURE_SAVE_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  
    cv2.imwrite(str(CAPTURE_SAVE_DIR / f"{ts}.jpg"), clean)

    ocr_text = pytesseract.image_to_string(
        clean,
        config="--psm 6 "
            "-c tessedit_char_whitelist=0123456789 "
            "-c preserve_interword_spaces=0"
    )

    return parse_loot(ocr_text)  # gold, elixir, dark


# ---------------------------------------------------------------------------

def main() -> None:
    input("Press <Enter> to start Clash-of-Clans loot detection …")
    print("Started listener …  (Ctrl-C to stop)")
    time.sleep(1) # let board finish booting
    flush_rx()

    while True:
        try:
            # ---- capture ---------------------------------------------------
            flush_rx()
            ser.reset_output_buffer()
            ser.write(b"CAPTURE\n")
            print("Requested Capture")

            b64_img = read_one_image_b64()
            wait_for_ready()

            img = decode_base64_to_image(b64_img)
            gold, elixir, dark = ocr(img)

            print(f"Gold {gold:,}  Elixir {elixir:,}  Dark {dark:,}")

            # ---- decision --------------------------------------------------
            if (gold >= GOLD_LOOT_THRESHOLD and
                elixir >= ELIXIR_LOOT_THRESHOLD and
                dark >= DARK_ELIXIR_LOOT_THRESHOLD):

                notify_mac("💰 GOOD BASE FOUND!",
                           f"Gold: {gold:,}  Elixir: {elixir:,}  Dark: {dark:,}")
                input("Good base!  Review on phone, then press <Enter> …")

            elif (gold == 0 and elixir == 0 and dark == 0):
                print("Waiting for base …")
                flush_rx()
                ser.reset_output_buffer()
                time.sleep(SKIP_PAUSE_SEC)
            else:
                print("Skipping base …")
                flush_rx()
                ser.reset_output_buffer()
                ser.write(b"SKIP\n")
                wait_for_ready()
                time.sleep(SKIP_PAUSE_SEC)

        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print("Error:", e)
            time.sleep(7)


if __name__ == "__main__":
    main()
