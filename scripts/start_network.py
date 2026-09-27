"""
scripts/start_network.py

Khởi chạy hệ thống CloakShare hỗ trợ đa thiết bị (PC, Laptop, Mobile)
qua mạng LAN Wi-Fi nội bộ hoặc mạng riêng ảo Tailscale.
"""

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

# Đảm bảo UTF-8 stream trên Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_tailscale_ip() -> str | None:
    try:
        out = subprocess.check_output(
            ["tailscale", "ip", "-4"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        if out:
            return out
    except Exception:
        pass
    return None


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    print("=" * 65)
    print("      CLOAKSHARE - MULTI-DEVICE LAUNCHER (LAN / TAILSCALE)     ")
    print("=" * 65)

    local_ip = get_local_ip()
    tailscale_ip = get_tailscale_ip()

    print("\n[+] THONG TIN KET NOI HE THONG:")
    if tailscale_ip:
        print(f"  * Tailscale VPN IP : {tailscale_ip}")
        print(f"    -> Web UI (Mobile / Remote): http://{tailscale_ip}:8501")
        print(f"    -> Broker API              : http://{tailscale_ip}:8000")
    else:
        print("  * Tailscale        : Khong phat hien (hoac chua bat).")

    print(f"  * Wi-Fi LAN IP     : {local_ip}")
    print(f"    -> Web UI (Cung Wi-Fi)     : http://{local_ip}:8501")
    print(f"    -> Broker API              : http://{local_ip}:8000")
    print(f"  * Localhost        : http://127.0.0.1:8501\n")

    # 1. Khoi dong Broker neu chua chay
    if not is_port_in_use(8000):
        print("[*] Dang khoi dong RAM Broker tren port 8000 (0.0.0.0)...")
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "broker.main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=str(ROOT_DIR),
        )
        time.sleep(2)
    else:
        print("[v] Broker da dang chay tren port 8000.")

    # 2. Khoi dong Streamlit neu chua chay
    if not is_port_in_use(8501):
        print("[*] Dang khoi dong Streamlit Web UI tren port 8501 (0.0.0.0)...")
        subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "ui/app.py", "--server.address", "0.0.0.0", "--server.port", "8501"],
            cwd=str(ROOT_DIR),
        )
        time.sleep(2)
    else:
        print("[v] Web UI da dang chay tren port 8501.")

    print("\n" + "=" * 65)
    print(">> HUONG DAN KET NOI CHO DIEN THOAI & MAY KHAC:")
    print("1. Tren dien thoai (chung Wi-Fi hoac Tailscale):")
    if tailscale_ip:
        print(f"   Mo trinh duyet go: http://{tailscale_ip}:8501")
    else:
        print(f"   Mo trinh duyet go: http://{local_ip}:8501")
    print("2. Quet ma QR co san trong muc 'Ket Noi Da Thiet Bi' tren UI")
    print("3. Chon tai khoan (Vi du: PC chon Alice, Dien thoai chon Bob/Mobile)")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
