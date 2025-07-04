# Clash of Clans Base Finding Automation

DIY automation that watches the screen, reads the three loot numbers (gold, elixir, dark elixir), and either taps **Next** with a servo‑mounted stylus or pops a desktop alert when a rich base appears.

---

## Demos
### 1 **Setup — sliding phone in** 


https://github.com/user-attachments/assets/353c7e85-fbc4-4e8c-89f0-936644e1f766


### 2 **Side by side mobile device and host computer screen recording** 


https://github.com/user-attachments/assets/7a5b18ce-e3dc-4005-af5f-772bad1cc751


### 3 **Skipping low‑loot bases**


https://github.com/user-attachments/assets/3926f5ad-9a82-4e02-8d5b-34e7e415f2f4


### 4 **Visual and sound Alert on good base** 


https://github.com/user-attachments/assets/1e4dc8d2-c486-4162-891c-cd84605c54db


## Hardware

| Part                       | Notes                                              |
| -------------------------- | -------------------------------------------------- |
| **ESP32‑CAM (AI‑Thinker)** | Captures 800 × 600 grayscale, crops on‑board.      |
| **9 g micro‑servo**        | Holds a conductive stylus to tap Next.               |
| **3‑D‑printed mount**      | Designed in Fusion and 3D printed. https://a360.co/4l9JzhV                |
| **Conductive stylus tip**  | Designed in Fusion and 3D printed. https://a360.co/44xi4aY               |

---

## Features

* **Sub‑second decision loop** (460 kbaud UART, \~0.6 s frame‑to‑frame).
* **Adaptive OCR fallback** — reliable even on noisy bases.
* **Servo glide** — smooth 40° press & return.
* **Desktop alerts** (macOS `osascript`) with full loot breakdown.
* **Frame logger** — every sample JPEG saved to `captures/` for tuning.

---


## Tuning

* **Thresholds** in `script.py` — change loot limits, adaptive `C`, dilation.
* **Crop limits** — in `Coc.ino` to fit different screens and mounts.

