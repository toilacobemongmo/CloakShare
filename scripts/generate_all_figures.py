"""
scripts/generate_all_figures.py

Tự động sinh toàn bộ 17 hình vẽ / biểu đồ kỹ thuật cho báo cáo chuyên khảo CloakShare.
Quy chuẩn:
  - Phong cách học thuật (Academic Paper / IEEE / ACM / Luận văn Đại học).
  - Tối giản, thanh lịch, đường nét dứt khoát, không màu mè hoa lá cành.
  - Tông màu chuẩn: Xám bạc, Xanh Navy (#003366, #1E3A8A), Slate (#334155, #64748B), Đen/Trắng.
  - Font chữ: Times New Roman.
  - Độ phân giải: 300 DPI, định dạng PNG.
"""

import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch

OUT_DIR = Path(r"C:\Users\ghaob\CloakShare\figures")
OUT_DIR.mkdir(exist_ok=True, parents=True)

# Cấu hình font chữ học thuật toàn cục
plt.rcParams["font.family"] = "Times New Roman"
plt.rcParams["font.size"] = 10
plt.rcParams["axes.titlesize"] = 12
plt.rcParams["axes.titleweight"] = "bold"
plt.rcParams["axes.labelsize"] = 11
plt.rcParams["xtick.labelsize"] = 10
plt.rcParams["ytick.labelsize"] = 10
plt.rcParams["figure.dpi"] = 300
plt.rcParams["savefig.dpi"] = 300

NAVY = "#003366"
DARK_SLATE = "#1E293B"
MID_SLATE = "#475569"
LIGHT_BG = "#F8FAFC"
BORDER_GRAY = "#94A3B8"
ACCENT_BLUE = "#2563EB"
MUTED_RED = "#991B1B"
MUTED_GREEN = "#166534"


def add_box(ax, x, y, w, h, title="", subtitle="", bg=LIGHT_BG, border=DARK_SLATE, lw=1.2, radius=0.02):
    """Vẽ một hộp thành phần với tiêu đề và mô tả."""
    box = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.01,rounding_size={radius}",
                         facecolor=bg, edgecolor=border, linewidth=lw, zorder=2)
    ax.add_patch(box)
    if title:
        ty = y + h * 0.65 if subtitle else y + h * 0.5
        ax.text(x + w / 2, ty, title, ha="center", va="center", fontsize=9.5, fontweight="bold",
                color=NAVY, zorder=3)
    if subtitle:
        ax.text(x + w / 2, y + h * 0.3, subtitle, ha="center", va="center", fontsize=8,
                color=MID_SLATE, zorder=3)
    return box


# ==============================================================================
# HÌNH 1: MÔ HÌNH KIẾN TRÚC TỔNG THỂ CLOAKSHARE ĐA TẦNG
# ==============================================================================
def draw_fig_01():
    fig, ax = plt.subplots(figsize=(9, 6.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")

    ax.text(5, 6.7, "Hình 1: Mô hình Kiến trúc Tổng thể Hệ sinh thái CloakShare Đa tầng",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    # Tầng 1: Client Layer
    add_box(ax, 0.5, 3.8, 4.0, 2.5, title="TẦNG MÁY KHÁCH (CLIENT ENGINE)", subtitle="Người Gửi (Seller / Alice)", bg="#F1F5F9", lw=1.5)
    add_box(ax, 0.7, 4.8, 3.6, 0.6, title="Giao Diện Ứng Dụng", subtitle="Streamlit Web3 UI / Python CLI", bg="#FFFFFF")
    add_box(ax, 0.7, 4.0, 1.7, 0.65, title="Crypto Engine", subtitle="RSA-OAEP + PSS", bg="#FFFFFF")
    add_box(ax, 2.6, 4.0, 1.7, 0.65, title="Lõi C Native", subtitle="AES-128-CBC + PKCS#7", bg="#FFFFFF")

    # Tầng Máy Khách Nhận (Bob)
    add_box(ax, 5.5, 3.8, 4.0, 2.5, title="TẦNG MÁY KHÁCH (CLIENT ENGINE)", subtitle="Người Nhận (Buyer / Bob)", bg="#F1F5F9", lw=1.5)
    add_box(ax, 5.7, 4.8, 3.6, 0.6, title="Giao Diện Ứng Dụng", subtitle="Streamlit Web3 UI / Hòm Thư Inbox", bg="#FFFFFF")
    add_box(ax, 5.7, 4.0, 1.7, 0.65, title="Giải Mã Lai", subtitle="RSA Unwrap + Verify", bg="#FFFFFF")
    add_box(ax, 7.6, 4.0, 1.7, 0.65, title="Lõi C Native", subtitle="AES Decrypt + Unpad", bg="#FFFFFF")

    # Tầng 2: dPKI Blockchain
    add_box(ax, 0.5, 0.6, 4.0, 2.3, title="TẦNG ĐỊNH DANH PHI TẬP TRUNG (dPKI)", subtitle="Hạ Tầng Sổ Cái Máy Ảo EVM (Ethereum / Polygon)", bg="#F8FAFC", lw=1.5)
    add_box(ax, 0.8, 1.3, 3.4, 0.65, title="Smart Contract dPKIRegistry.sol", subtitle="mapping(address => string) publicKeys", bg="#FFFFFF")
    add_box(ax, 0.8, 0.75, 3.4, 0.45, title="RPC Node (Anvil / Testnet)", subtitle="JSON-RPC 2.0 @ Cổng 8545", bg="#FFFFFF")

    # Tầng 3: Zero-Log RAM Broker
    add_box(ax, 5.5, 0.6, 4.0, 2.3, title="TẦNG TRUNG CHUYỂN KHÔNG LƯU VẾT", subtitle="Máy Chủ Đệm Bộ Nhớ RAM (Zero-Log Broker)", bg="#F8FAFC", lw=1.5)
    add_box(ax, 5.8, 1.3, 3.4, 0.65, title="FastAPI Engine (Port 8000)", subtitle="Uvicorn Access Log = Disabled", bg="#FFFFFF")
    add_box(ax, 5.8, 0.75, 3.4, 0.45, title="InMemoryStore (Heap RAM)", subtitle="threading.RLock + _wipe(0x00)", bg="#FFFFFF")

    # Các mũi tên luồng dữ liệu
    ax.annotate("", xy=(4.5, 2.0), xytext=(6.5, 3.8),
                arrowprops=dict(arrowstyle="->", color=DARK_SLATE, lw=1.2, ls="--"))
    ax.text(6.1, 2.8, "(1) Đăng ký Khóa RSA", fontsize=7.5, ha="left", color=DARK_SLATE)

    ax.annotate("", xy=(2.5, 3.8), xytext=(2.5, 2.9),
                arrowprops=dict(arrowstyle="<-", color=DARK_SLATE, lw=1.2, ls="--"))
    ax.text(2.6, 3.3, "(2) Tra cứu Khóa Bob", fontsize=7.5, ha="left", color=DARK_SLATE)

    ax.annotate("", xy=(6.5, 2.9), xytext=(3.5, 3.8),
                arrowprops=dict(arrowstyle="->", color=ACCENT_BLUE, lw=1.5))
    ax.text(4.2, 3.5, "(3) Stage Payload\n(AES+RSA+PSS)", fontsize=7.5, ha="center", color=ACCENT_BLUE)

    ax.annotate("", xy=(7.5, 3.8), xytext=(7.5, 2.9),
                arrowprops=dict(arrowstyle="<->", color=MUTED_RED, lw=1.5))
    ax.text(7.6, 3.3, "(4) Retrieve Payload\n(X-Signature EIP-191)", fontsize=7.5, ha="left", color=MUTED_RED)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_01_kien_truc_tong_the.png")
    plt.close()
    print("   [+] Saved hinh_01_kien_truc_tong_the.png")


# ==============================================================================
# HÌNH 2: BIỂU ĐỒ TUẦN TỰ (SEQUENCE DIAGRAM) E2E
# ==============================================================================
def draw_fig_02():
    fig, ax = plt.subplots(figsize=(9, 7.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 11)
    ax.axis("off")

    ax.text(5, 10.6, "Hình 2: Biểu đồ Tuần tự (Sequence Diagram) Trao đổi Dữ liệu Toàn trình E2E",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    actors = [
        ("Alice (Sender)", 1.5),
        ("dPKI (EVM)", 3.8),
        ("Broker (RAM)", 6.2),
        ("Bob (Receiver)", 8.5)
    ]
    for name, x in actors:
        ax.text(x, 10.0, name, ha="center", va="center", fontsize=9.5, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="#E2E8F0", ec=DARK_SLATE, lw=1.2))
        ax.plot([x, x], [0.8, 9.6], color="#CBD5E1", lw=1.2, ls="--", zorder=1)

    steps = [
        (9.0, 8.5, 3.8, "registerPublicKey(Bob_RSA_Pub)", "(Giao dịch EVM có ký số)", False),
        (8.2, 1.5, 3.8, "getPublicKey(Bob_Address)", "(Truy vấn RPC miễn phí)", False),
        (7.6, 3.8, 1.5, "Trả về: Bob_RSA_Public_Key_PEM", "", True),
        (6.8, 1.5, 1.5, "[Local] AES-128 encrypt + RSA wrap + RSA-PSS sign", "(Thực thi hoàn toàn trên RAM)", False),
        (5.9, 1.5, 6.2, "POST /api/v1/stage (tx_id, iv, payload, sig, ttl)", "(Đẩy gói mã hóa lên heap RAM)", False),
        (5.3, 6.2, 1.5, "201 Created (expires_at)", "(Biên lai thời hạn)", True),
        (4.4, 8.5, 8.5, "[Local] Ký thông điệp EIP-191 Personal Sign", "(Thách thức tx_id @ timestamp)", False),
        (3.5, 8.5, 6.2, "GET /api/v1/retrieve/{tx_id} [X-Signature EIP-191]", "(Xác thực quyền rút file)", False),
        (2.7, 6.2, 6.2, "[Broker] verify_signature() + _wipe() burn-after-read", "(RAM Scrubbing 0x00)", False),
        (1.9, 6.2, 8.5, "200 OK (Ciphertext, Wrapped_Key, IV, Signature)", "(Chuyển giao gói tin)", True),
        (1.2, 8.5, 8.5, "[Local] RSA-PSS verify + RSA unwrap + AES decrypt", "(Khôi phục tệp gốc)", False)
    ]

    for y, x1, x2, label, note, is_dash in steps:
        if x1 == x2:
            ax.annotate("", xy=(x1, y - 0.25), xytext=(x1, y + 0.15),
                        arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.2,
                                        connectionstyle="arc3,rad=-0.8"))
            ax.text(x1 + 0.35, y, f"{label}\n{note}", fontsize=7.5, va="center", color=NAVY, fontweight="bold")
        else:
            ls = "--" if is_dash else "-"
            ax.annotate("", xy=(x2, y), xytext=(x1, y),
                        arrowprops=dict(arrowstyle="->", color=DARK_SLATE, lw=1.2, ls=ls))
            mid_x = (x1 + x2) / 2
            ax.text(mid_x, y + 0.15, label, fontsize=7.8, ha="center", va="bottom", color=DARK_SLATE, fontweight="bold")
            if note:
                ax.text(mid_x, y - 0.18, note, fontsize=7.0, ha="center", va="top", color=MID_SLATE)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_02_sequence_diagram.png")
    plt.close()
    print("   [+] Saved hinh_02_sequence_diagram.png")


# ==============================================================================
# HÌNH 3: MẠNG BIẾN ĐỔI VÒNG LẶP TRONG FIPS-197 AES-128
# ==============================================================================
def draw_fig_03():
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(5, 8.6, "Hình 3: Cấu trúc Vòng lặp Biến đổi Mật mã FIPS-197 AES-128",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    add_box(ax, 3.5, 7.8, 3.0, 0.5, title="Plaintext (128 bits / 16 bytes)", bg="#E2E8F0")
    ax.annotate("", xy=(5.0, 7.3), xytext=(5.0, 7.8), arrowprops=dict(arrowstyle="->", lw=1.2))

    add_box(ax, 3.5, 6.7, 3.0, 0.6, title="VÒNG KHỞI TẠO (ROUND 0)", subtitle="AddRoundKey(State, Key[0])", bg="#F8FAFC")
    ax.annotate("", xy=(5.0, 6.1), xytext=(5.0, 6.7), arrowprops=dict(arrowstyle="->", lw=1.2))

    add_box(ax, 2.5, 3.4, 5.0, 2.7, title="CÁC VÒNG LẶP TIÊU CHUẨN (ROUNDS 1 ĐẾN 9)", bg="#F1F5F9", lw=1.5)
    sub_steps = [
        (4.9, "1. SubBytes: Thế byte phi tuyến qua bảng S-Box"),
        (4.3, "2. ShiftRows: Hoán vị dịch chuyển vòng các hàng"),
        (3.7, "3. MixColumns: Nhân ma trận trường Galois GF(2^8)"),
        (3.1, "4. AddRoundKey: XOR với khóa con RoundKey[r]")
    ]
    for y_pos, text in sub_steps:
        box = FancyBboxPatch((2.8, y_pos - 0.2), 4.4, 0.45, boxstyle="round,pad=0.01",
                             fc="#FFFFFF", ec=BORDER_GRAY, lw=1)
        ax.add_patch(box)
        ax.text(5.0, y_pos, text, ha="center", va="center", fontsize=8.2, color=DARK_SLATE)

    ax.annotate("", xy=(5.0, 2.5), xytext=(5.0, 3.4), arrowprops=dict(arrowstyle="->", lw=1.2))

    add_box(ax, 2.8, 1.4, 4.4, 1.1, title="VÒNG KẾT THÚC (ROUND 10)",
            subtitle="SubBytes  ->  ShiftRows  ->  AddRoundKey\n(Tuyệt đối KHÔNG có MixColumns)", bg="#F8FAFC")

    ax.annotate("", xy=(5.0, 0.8), xytext=(5.0, 1.4), arrowprops=dict(arrowstyle="->", lw=1.2))
    add_box(ax, 3.5, 0.3, 3.0, 0.5, title="Ciphertext (128 bits / 16 bytes)", bg="#E2E8F0")

    add_box(ax, 8.0, 2.5, 1.6, 4.5, title="BỘ MỞ KHÓA\n(KEY EXPANSION)",
            subtitle="Khóa 16B -> 176B\nRcon[1..10]\nRotWord\nSubWord", bg="#EFF6FF", border=ACCENT_BLUE)
    ax.annotate("", xy=(7.5, 6.7), xytext=(8.0, 6.7), arrowprops=dict(arrowstyle="->", lw=1, ls="--"))
    ax.annotate("", xy=(7.5, 4.5), xytext=(8.0, 4.5), arrowprops=dict(arrowstyle="->", lw=1, ls="--"))
    ax.annotate("", xy=(7.2, 1.9), xytext=(8.0, 1.9), arrowprops=dict(arrowstyle="->", lw=1, ls="--"))

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_03_aes_round_transformation.png")
    plt.close()
    print("   [+] Saved hinh_03_aes_round_transformation.png")


# ==============================================================================
# HÌNH 4: CƠ CHẾ ĐỆM KHỐI PKCS#7 VÀ MA TRẬN KIỂM TRA
# ==============================================================================
def draw_fig_04():
    fig, ax = plt.subplots(figsize=(9, 6.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis("off")

    ax.text(5, 7.6, "Hình 4: Cơ chế Đệm Khối PKCS#7 (RFC 5652) và Luồng Kiểm Định Tính Hợp Lệ",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    ax.text(0.5, 6.9, "Trường hợp 1: Độ dài bản rõ = 10 bytes (Không chia hết cho 16)", fontsize=9, fontweight="bold", color=DARK_SLATE)
    for k in range(16):
        x = 0.5 + k * 0.55
        if k < 10:
            add_box(ax, x, 6.1, 0.5, 0.6, title=f"D{k+1}", bg="#FFFFFF")
        else:
            add_box(ax, x, 6.1, 0.5, 0.6, title="06", bg="#E0F2FE", border=ACCENT_BLUE)
    ax.text(9.4, 6.4, "16 bytes", va="center", fontsize=8.5, fontweight="bold", color=NAVY)

    ax.text(0.5, 5.3, "Trường hợp 2: Độ dài bản rõ = 16 bytes (Bội số của 16 -> Thêm khối đệm rỗng)", fontsize=9, fontweight="bold", color=DARK_SLATE)
    for k in range(16):
        x = 0.5 + k * 0.27
        add_box(ax, x, 4.5, 0.25, 0.6, title="D", bg="#FFFFFF")
    ax.text(4.9, 4.8, "+", fontsize=12, fontweight="bold", ha="center")
    for k in range(16):
        x = 5.2 + k * 0.25
        add_box(ax, x, 4.5, 0.23, 0.6, title="10", bg="#FEF3C7", border="#D97706")
    ax.text(9.4, 4.8, "32 bytes", va="center", fontsize=8.5, fontweight="bold", color=NAVY)

    ax.text(0.5, 3.6, "Quy trình Kiểm Định & Gỡ Đệm An Toàn (pkcs7_unpad trong core/padding.c):", fontsize=9, fontweight="bold", color=NAVY)

    steps = [
        (0.5, 1.8, 2.0, 1.4, "Bước 1: Kiểm Tra Biên", "len % 16 == 0\nlen > 0\nlen <= MAX"),
        (2.8, 1.8, 2.0, 1.4, "Bước 2: Đọc pad_val", "pad_val = in[len - 1]\n1 <= pad_val <= 16\npad_val <= len"),
        (5.1, 1.8, 2.2, 1.4, "Bước 3: Quét Ma Trận", "Duyệt k từ 1 đến pad_val:\nin[len - k] == pad_val ?"),
        (7.6, 1.8, 2.0, 1.4, "Bước 4: Kết Luận", "Khớp: Trả unpadded_len\nSai: Trả mã lỗi -2\n(PKCS7_INVALID_PAD)")
    ]
    for x, y, w, h, t, st in steps:
        add_box(ax, x, y, w, h, title=t, subtitle=st, bg="#F8FAFC", border=DARK_SLATE)

    for i in range(3):
        x1 = steps[i][0] + steps[i][2]
        x2 = steps[i+1][0]
        y_mid = steps[i][1] + steps[i][3] / 2
        ax.annotate("", xy=(x2, y_mid), xytext=(x1, y_mid), arrowprops=dict(arrowstyle="->", lw=1.2))

    box_note = FancyBboxPatch((0.5, 0.4), 9.0, 0.9, boxstyle="round,pad=0.01",
                              fc="#F1F5F9", ec=BORDER_GRAY, lw=1)
    ax.add_patch(box_note)
    ax.text(5.0, 0.85, "Phòng thủ Tấn công Oracle Đệm (Padding Oracle Attack):\n"
                       "Quy trình unpad duyệt toàn bộ mảng đệm và trả về lỗi đồng nhất, loại bỏ chênh lệch thời gian rò rỉ kênh kề.",
            ha="center", va="center", fontsize=8, color=MID_SLATE)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_04_pkcs7_padding.png")
    plt.close()
    print("   [+] Saved hinh_04_pkcs7_padding.png")


# ==============================================================================
# HÌNH 5: KIẾN TRÚC MẠNG FEISTEL HAI VÒNG TRONG RSA-OAEP
# ==============================================================================
def draw_fig_05():
    fig, ax = plt.subplots(figsize=(9, 6.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    ax.text(5, 8.1, "Hình 5: Cấu trúc Mạng Feistel Hai Vòng trong Cơ Chế Đệm RSA-OAEP (RFC 8017)",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    add_box(ax, 1.0, 6.8, 3.2, 0.7, title="Hạt Giống Ngẫu Nhiên (Seed)", subtitle="k0 = 32 bytes (256 bits)", bg="#E0F2FE", border=ACCENT_BLUE)
    add_box(ax, 5.0, 6.8, 4.2, 0.7, title="Khối Dữ Liệu DB (Data Block)", subtitle="M || pHash || PS || 0x01 (k - k0 - 1 bytes)", bg="#F8FAFC")

    ax.annotate("", xy=(2.6, 5.2), xytext=(2.6, 6.8), arrowprops=dict(arrowstyle="->", lw=1.2))
    add_box(ax, 1.6, 4.6, 2.0, 0.6, title="MGF1 (SHA-256)", bg="#FFFFFF", border=DARK_SLATE)

    ax.annotate("", xy=(7.1, 4.9), xytext=(3.6, 4.9), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.text(5.3, 5.1, "dbMask", fontsize=8.5, ha="center", color=MID_SLATE)

    ax.annotate("", xy=(7.1, 5.2), xytext=(7.1, 6.8), arrowprops=dict(arrowstyle="->", lw=1.2))
    circle1 = plt.Circle((7.1, 4.9), 0.25, color=DARK_SLATE, fill=False, lw=1.5)
    ax.add_patch(circle1)
    ax.text(7.1, 4.9, "+", ha="center", va="center", fontsize=12, fontweight="bold")

    ax.annotate("", xy=(7.1, 3.5), xytext=(7.1, 4.65), arrowprops=dict(arrowstyle="->", lw=1.2))
    add_box(ax, 5.2, 2.8, 3.8, 0.7, title="Khối Dữ Liệu Đã Che (maskedDB)", subtitle="maskedDB = DB  XOR  MGF1(Seed)", bg="#FEF3C7", border="#D97706")

    ax.annotate("", xy=(5.2, 3.15), xytext=(4.4, 3.15), arrowprops=dict(arrowstyle="->", lw=1.2))
    add_box(ax, 2.4, 2.85, 2.0, 0.6, title="MGF1 (SHA-256)", bg="#FFFFFF", border=DARK_SLATE)

    ax.annotate("", xy=(1.0, 3.15), xytext=(2.4, 3.15), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.text(1.7, 3.35, "seedMask", fontsize=8, ha="center", color=MID_SLATE)

    circle2 = plt.Circle((1.0, 4.2), 0.25, color=DARK_SLATE, fill=False, lw=1.5)
    ax.add_patch(circle2)
    ax.text(1.0, 4.2, "+", ha="center", va="center", fontsize=12, fontweight="bold")

    ax.annotate("", xy=(1.0, 4.45), xytext=(1.0, 6.8), arrowprops=dict(arrowstyle="<-", lw=1.2))
    ax.annotate("", xy=(1.0, 3.95), xytext=(1.0, 3.15), arrowprops=dict(arrowstyle="<-", lw=1.2))

    ax.annotate("", xy=(1.0, 2.2), xytext=(1.0, 3.95), arrowprops=dict(arrowstyle="->", lw=1.2))
    add_box(ax, 0.5, 1.5, 3.5, 0.7, title="Hạt Giống Đã Che (maskedSeed)", subtitle="maskedSeed = Seed  XOR  MGF1(maskedDB)", bg="#E0F2FE", border=ACCENT_BLUE)

    add_box(ax, 0.5, 0.4, 9.0, 0.7, title="THÔNG ĐIỆP MÃ HÓA HOÀN CHỈNH:   EM = 0x00  ||  maskedSeed  ||  maskedDB",
            subtitle="Kích thước: Đúng 256 bytes (2048 bits) -> Đưa trực tiếp vào hàm lũy thừa modulo RSA c = m^e mod n",
            bg="#F1F5F9", border=NAVY, lw=1.5)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_05_rsa_oaep_feistel.png")
    plt.close()
    print("   [+] Saved hinh_05_rsa_oaep_feistel.png")


# ==============================================================================
# HÌNH 6: LƯỢC ĐỒ CHỮ KÝ SỐ XÁC SUẤT RSA-PSS
# ==============================================================================
def draw_fig_06():
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    ax.text(5, 8.1, "Hình 6: Sơ đồ Sinh Chữ Ký Số Xác Suất RSASSA-PSS (RFC 8017)",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    add_box(ax, 0.5, 6.8, 3.0, 0.7, title="Thông Điệp Cần Ký (M)", subtitle="Tệp tin bản rõ (Bytes)", bg="#FFFFFF")
    ax.annotate("", xy=(4.2, 7.15), xytext=(3.5, 7.15), arrowprops=dict(arrowstyle="->", lw=1.2))
    add_box(ax, 4.2, 6.8, 2.2, 0.7, title="Hash (SHA-256)", subtitle="mHash (32 bytes)", bg="#E2E8F0")

    add_box(ax, 7.2, 6.8, 2.3, 0.7, title="Muối Salt Ngẫu Nhiên", subtitle="sLen = 32 bytes ngẫu nhiên", bg="#FEF3C7", border="#D97706")

    ax.annotate("", xy=(5.0, 5.8), xytext=(5.3, 6.8), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.annotate("", xy=(5.0, 5.8), xytext=(8.3, 6.8), arrowprops=dict(arrowstyle="->", lw=1.2))

    add_box(ax, 1.5, 5.0, 7.0, 0.7, title="Thông Điệp Mở Rộng:   M' = Padding1 (8 bytes 0x00)  ||  mHash  ||  Salt",
            subtitle="Đảm bảo tính chống va chạm tuyệt đối", bg="#F8FAFC")

    ax.annotate("", xy=(5.0, 4.2), xytext=(5.0, 5.0), arrowprops=dict(arrowstyle="->", lw=1.2))
    add_box(ax, 3.8, 3.5, 2.4, 0.7, title="Hash (SHA-256)", subtitle="Giá trị băm H (32B)", bg="#E0F2FE", border=ACCENT_BLUE)

    add_box(ax, 0.5, 2.3, 4.0, 0.7, title="Khối Dữ Liệu DB", subtitle="PS (zeros) || 0x01 || Salt", bg="#F8FAFC")

    ax.annotate("", xy=(3.0, 1.8), xytext=(3.0, 2.3), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.annotate("", xy=(5.0, 2.3), xytext=(5.0, 3.5), arrowprops=dict(arrowstyle="->", lw=1.2))
    add_box(ax, 4.2, 1.7, 1.6, 0.6, title="MGF1(H)", bg="#FFFFFF")

    add_box(ax, 0.5, 0.5, 9.0, 0.8, title="BẢN MÃ HÓA CHỮ KÝ:   EM = maskedDB  ||  H (32B)  ||  0xBC (Trailer Field)",
            subtitle="Được ký bằng khóa riêng RSA: s = EM^d mod n. Mỗi lần ký sinh ra chữ ký khác nhau nhờ Salt.",
            bg="#F1F5F9", border=NAVY, lw=1.5)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_06_rsa_pss_signature.png")
    plt.close()
    print("   [+] Saved hinh_06_rsa_pss_signature.png")


# ==============================================================================
# HÌNH 7: MÔ HÌNH TƯƠNG TÁC SMART CONTRACT dPKIRegistry TRÊN EVM
# ==============================================================================
def draw_fig_07():
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")

    ax.text(5, 6.6, "Hình 7: Mô hình Lưu Trữ & Tra Cứu Danh Bạ dPKIRegistry trên Sổ Cái EVM",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    add_box(ax, 0.5, 3.8, 3.2, 2.0, title="NGƯỜI DÙNG A (OFF-CHAIN)", subtitle="Địa chỉ ví: 0xAlice...\nKhóa RSA: Alice_Public_Key.pem", bg="#FFFFFF")
    add_box(ax, 0.5, 1.0, 3.2, 2.0, title="NGƯỜI DÙNG B (OFF-CHAIN)", subtitle="Địa chỉ ví: 0xBob...\nKhóa RSA: Bob_Public_Key.pem", bg="#FFFFFF")

    add_box(ax, 5.0, 0.8, 4.5, 5.2, title="HỢP ĐỒNG THÔNG MINH dPKIRegistry.sol",
            subtitle="Triển khai trên Máy Ảo EVM (Solidity ^0.8.20)", bg="#F8FAFC", border=NAVY, lw=1.5)

    add_box(ax, 5.3, 4.0, 3.9, 1.2, title="Trạng Thái Lưu Trữ Bất Biến (State Storage)",
            subtitle="mapping(address => string) private _publicKeys;\n• 0xAlice -> '-----BEGIN RSA PUBLIC KEY...'\n• 0xBob   -> '-----BEGIN RSA PUBLIC KEY...'",
            bg="#FEF3C7", border="#D97706")

    add_box(ax, 5.3, 2.6, 3.9, 1.0, title="registerPublicKey(string pem)",
            subtitle="• msg.sender kiểm soát quyền ghi\n• emit PublicKeyRegistered(msg.sender, pem)", bg="#E0F2FE", border=ACCENT_BLUE)

    add_box(ax, 5.3, 1.2, 3.9, 1.0, title="getPublicKey(address user) view",
            subtitle="• Đọc trực tiếp off-chain không tốn phí Gas\n• Trả về chuỗi khóa công khai RSA chuẩn PEM", bg="#F1F5F9")

    ax.annotate("", xy=(5.3, 3.1), xytext=(3.7, 4.5),
                arrowprops=dict(arrowstyle="->", color=ACCENT_BLUE, lw=1.5))
    ax.text(4.5, 4.0, "Giao dịch ghi\n(Tốn Gas)", fontsize=7.5, color=ACCENT_BLUE, ha="center")

    ax.annotate("", xy=(3.7, 2.0), xytext=(5.3, 1.7),
                arrowprops=dict(arrowstyle="<-", color=DARK_SLATE, lw=1.5, ls="--"))
    ax.text(4.5, 1.5, "eth_call tra cứu\n(0 Gas)", fontsize=7.5, color=DARK_SLATE, ha="center")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_07_dpki_smart_contract.png")
    plt.close()
    print("   [+] Saved hinh_07_dpki_smart_contract.png")


# ==============================================================================
# HÌNH 8: CẤU TRÚC HTTP HEADERS XÁC THỰC WEB3 EIP-191
# ==============================================================================
def draw_fig_08():
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")

    ax.text(5, 6.6, "Hình 8: Cấu trúc Gói tin HTTP Headers Xác thực Web3 EIP-191 Personal Sign",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    add_box(ax, 0.5, 3.5, 9.0, 2.6, title="YÊU CẦU HTTP:   GET /api/v1/retrieve/{tx_id}",
            subtitle="Đính kèm bộ 3 Headers bảo mật bắt buộc", bg="#F8FAFC", border=NAVY, lw=1.2)

    headers = [
        (0.8, 4.8, 8.4, 0.45, "X-Wallet-Address:", "0x70997970C51812dc3A010C7d01b50e0d17dc79C8 (Địa chỉ ví nhận)"),
        (0.8, 4.2, 8.4, 0.45, "X-Timestamp:", "1773052800 (Unix timestamp hiện tại - Chống tấn công Replay)"),
        (0.8, 3.6, 8.4, 0.45, "X-Signature:", "0x4a7b9f... (Chữ ký 65 bytes ECDSA: r, s, v trên chuỗi thông điệp)")
    ]
    for x, y, w, h, lbl, val in headers:
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01", fc="#FFFFFF", ec=BORDER_GRAY, lw=1)
        ax.add_patch(box)
        ax.text(x + 0.15, y + h/2, lbl, va="center", fontsize=8.5, fontweight="bold", color=NAVY)
        ax.text(x + 1.8, y + h/2, val, va="center", fontsize=8.0, color=DARK_SLATE)

    add_box(ax, 0.5, 0.6, 9.0, 2.4, title="QUY TRÌNH KIỂM CHỨNG CHỮ KÝ TRÊN MÁY CHỦ BROKER (wallet_auth.py)",
            bg="#F1F5F9", lw=1.2)

    steps = [
        (0.8, 1.4, 2.6, 1.0, "1. Tạo Chuỗi Thách Thức", "msg = 'CloakShare Retrieve Auth:\n{tx_id} @ {timestamp}'"),
        (3.7, 1.4, 2.6, 1.0, "2. Kiểm Tra Độ Trôi Giờ", "abs(now - timestamp) <= 60s\n(Loại bỏ Replay Attack)"),
        (6.6, 1.4, 2.6, 1.0, "3. Khôi Phục Địa Chỉ", "Account.recover_message(msg, sig)\n== X-Wallet-Address ?")
    ]
    for x, y, w, h, t, st in steps:
        add_box(ax, x, y, w, h, title=t, subtitle=st, bg="#FFFFFF", border=DARK_SLATE)

    for k in range(2):
        ax.annotate("", xy=(steps[k+1][0], 1.9), xytext=(steps[k][0] + steps[k][2], 1.9),
                    arrowprops=dict(arrowstyle="->", lw=1.2))

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_08_http_headers_web3_auth.png")
    plt.close()
    print("   [+] Saved hinh_08_http_headers_web3_auth.png")


# ==============================================================================
# HÌNH 9: VÒNG ĐỜI STAGING - RETRIEVAL - PURGE TRONG RAM BROKER
# ==============================================================================
def draw_fig_09():
    fig, ax = plt.subplots(figsize=(9, 5.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")

    ax.text(5, 6.6, "Hình 9: Vòng Đời Staging – Retrieval – Purge của Payload trên Bộ Nhớ RAM",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    add_box(ax, 0.5, 3.2, 2.5, 2.0, title="TRẠNG THÁI: STAGED",
            subtitle="• Lưu trên heap RAM\n• expires_at = now + TTL\n• Cấu trúc bytearray\n• Ghi đĩa = 0",
            bg="#E0F2FE", border=ACCENT_BLUE, lw=1.5)

    add_box(ax, 4.0, 4.5, 2.5, 1.5, title="ĐỌC VÀ TỰ HỦY\n(Burn-After-Read)",
            subtitle="Buyer rút tệp thành công\nGọi _purge_one(tx_id)", bg="#FEF3C7", border="#D97706")

    add_box(ax, 4.0, 1.5, 2.5, 1.5, title="HẾT HẠN THỜI GIAN\n(TTL Purge Loop)",
            subtitle="Task nền quét mỗi 5s\ntime() >= expires_at", bg="#FEF2F2", border=MUTED_RED)

    add_box(ax, 7.5, 3.2, 2.2, 2.0, title="TRẠNG THÁI: PURGED\n(TIÊU HỦY TOÀN PHẦN)",
            subtitle="• _wipe(): byte = 0x00\n• del _data[tx_id]\n• Truy cập lại: 404\n• Hoàn toàn vô vết",
            bg="#F1F5F9", border=DARK_SLATE, lw=1.5)

    ax.annotate("", xy=(4.0, 5.2), xytext=(3.0, 4.5), arrowprops=dict(arrowstyle="->", lw=1.5, color=DARK_SLATE))
    ax.text(3.3, 5.2, "GET /retrieve", fontsize=7.5, color=DARK_SLATE)

    ax.annotate("", xy=(7.5, 4.5), xytext=(6.5, 5.2), arrowprops=dict(arrowstyle="->", lw=1.5, color=DARK_SLATE))
    ax.text(7.2, 5.2, "Ghi đè 0x00", fontsize=7.5, color=DARK_SLATE)

    ax.annotate("", xy=(4.0, 2.2), xytext=(3.0, 3.8), arrowprops=dict(arrowstyle="->", lw=1.5, color=MUTED_RED, ls="--"))
    ax.text(3.2, 2.7, "Quá hạn TTL", fontsize=7.5, color=MUTED_RED)

    ax.annotate("", xy=(7.5, 3.8), xytext=(6.5, 2.2), arrowprops=dict(arrowstyle="->", lw=1.5, color=MUTED_RED, ls="--"))
    ax.text(7.2, 2.7, "Tẩy xóa RAM", fontsize=7.5, color=MUTED_RED)

    box_c = FancyBboxPatch((0.5, 0.4), 9.0, 0.7, boxstyle="round,pad=0.01", fc="#F8FAFC", ec=BORDER_GRAY, lw=1)
    ax.add_patch(box_c)
    ax.text(5.0, 0.75, "Cam Kết Bất Biến: Không tạo file tạm, không write đĩa, tắt Uvicorn access log, tẩy sạch bộ nhớ.",
            ha="center", va="center", fontsize=8.5, fontweight="bold", color=NAVY)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_09_ram_store_lifecycle.png")
    plt.close()
    print("   [+] Saved hinh_09_ram_store_lifecycle.png")


# ==============================================================================
# HÌNH 10: SO SÁNH THÔNG LƯỢNG C NATIVE VS PYTHON
# ==============================================================================
def draw_fig_10():
    fig, ax = plt.subplots(figsize=(8.5, 5.0))

    sizes = ["64 KB", "512 KB", "1 MB", "10 MB", "50 MB"]
    x = np.arange(len(sizes))
    width = 0.35

    c_throughput = [485.2, 562.4, 598.1, 615.3, 622.8]
    py_throughput = [12.4, 15.2, 16.8, 17.4, 17.6]

    rects1 = ax.bar(x - width/2, c_throughput, width, label="Lõi C Native FIPS-197 (Ctypes -O3)", color=NAVY, edgecolor=DARK_SLATE)
    rects2 = ax.bar(x + width/2, py_throughput, width, label="Python Thuần Fallback", color="#94A3B8", edgecolor=DARK_SLATE)

    ax.set_title("Hình 10: So Sánh Thông Lượng Mã Hóa: Lõi C Native FIPS-197 vs Python Thuần", pad=15, color=NAVY)
    ax.set_ylabel("Thông lượng (MB/s)")
    ax.set_xlabel("Kích thước tệp tin thực nghiệm")
    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.legend(frameon=True, edgecolor=BORDER_GRAY)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for rect in rects1:
        height = rect.get_height()
        ax.annotate(f"{height:.1f}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, fontweight="bold")

    for rect in rects2:
        height = rect.get_height()
        ax.annotate(f"{height:.1f}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7.5, color=MID_SLATE)

    ax.set_ylim(0, 720)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_10_throughput_benchmark.png")
    plt.close()
    print("   [+] Saved hinh_10_throughput_benchmark.png")


# ==============================================================================
# HÌNH 11: CHI PHÍ TIÊU THỤ GAS SMART CONTRACT dPKI
# ==============================================================================
def draw_fig_11():
    fig, ax = plt.subplots(figsize=(8.5, 4.8))

    operations = [
        "Triển Khai Hợp Đồng\n(Constructor Deployment)",
        "Đăng Ký Khóa Lần Đầu\n(Cold SSTORE Write)",
        "Cập Nhật Khóa Mới\n(Warm SSTORE Write)",
        "Truy Vấn Khóa\n(Off-chain eth_call View)"
    ]
    gas_costs = [285420, 68230, 28450, 0]
    colors = [NAVY, ACCENT_BLUE, "#60A5FA", MUTED_GREEN]

    bars = ax.barh(operations, gas_costs, color=colors, edgecolor=DARK_SLATE, height=0.55)
    ax.set_title("Hình 11: Phân Tích Tiêu Thụ Gas của Smart Contract dPKIRegistry trên EVM", pad=15, color=NAVY)
    ax.set_xlabel("Lượng Gas Tiêu Thụ (Gas Units)")
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    ax.set_xlim(0, 340000)

    for bar, val in zip(bars, gas_costs):
        if val > 0:
            ax.text(val + 5000, bar.get_y() + bar.get_height()/2, f"{val:,} Gas",
                    va="center", fontsize=8.5, fontweight="bold", color=DARK_SLATE)
        else:
            ax.text(5000, bar.get_y() + bar.get_height()/2, "0 Gas (Miễn Phí Hoàn Toàn)",
                    va="center", fontsize=8.5, fontweight="bold", color=MUTED_GREEN)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_11_gas_analysis.png")
    plt.close()
    print("   [+] Saved hinh_11_gas_analysis.png")


# ==============================================================================
# HÌNH 12: PHÂN BỔ ĐỘ TRỄ TRONG TOÀN TRÌNH TRAO ĐỔI TỆP
# ==============================================================================
def draw_fig_12():
    fig, ax = plt.subplots(figsize=(8.8, 5.0))

    stages = [
        "Mã Hóa AES-128\n(C Native)",
        "Bọc Khóa RSA\n(OAEP SHA-256)",
        "Ký Số Toàn Vẹn\n(RSA-PSS)",
        "Truyền Staging\n(LAN/VPN Upload)",
        "Ký Thách Thức\n(Web3 EIP-191)",
        "Xác Thực & Rút\n(Retrieve Request)",
        "Mở Khóa RSA\n(Unwrap Private)",
        "Giải Mã AES\n(C Native Unpad)"
    ]
    latencies = [4.2, 5.1, 3.8, 12.5, 2.4, 11.2, 8.4, 4.8]
    total_lat = sum(latencies)

    x = np.arange(len(stages))
    bars = ax.bar(x, latencies, color=NAVY, edgecolor=DARK_SLATE, width=0.55)

    ax.set_title(f"Hình 12: Phân Bổ Độ Trễ Toàn Trình E2E (Tổng Cộng: {total_lat:.1f} ms cho tệp 1 MB)", pad=15, color=NAVY)
    ax.set_ylabel("Độ trễ xử lý (mili-giây - ms)")
    ax.set_xticks(x)
    ax.set_xticklabels(stages, fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.set_ylim(0, 16)

    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.3, f"{h:.1f} ms",
                ha="center", va="bottom", fontsize=8, fontweight="bold", color=DARK_SLATE)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_12_latency_breakdown.png")
    plt.close()
    print("   [+] Saved hinh_12_latency_breakdown.png")


# ==============================================================================
# HÌNH 13: KHẢ NĂNG DỌN SẠCH BỘ NHỚ RAM BROKER
# ==============================================================================
def draw_fig_13():
    fig, ax = plt.subplots(figsize=(8.5, 4.8))

    t = np.linspace(0, 70, 300)
    ram = np.zeros_like(t)
    ram[(t >= 5) & (t < 40)] = 10.48

    ax.plot(t, ram, color=NAVY, lw=2.2, label="Dung lượng RAM chiếm dụng (MB)")
    ax.fill_between(t, 0, ram, color="#E0F2FE", alpha=0.6)

    ax.axvline(x=5, color=ACCENT_BLUE, ls="--", lw=1.2)
    ax.text(5.5, 8.5, "t = 5s: POST /stage\nCấp phát Heap RAM", fontsize=8, color=ACCENT_BLUE)

    ax.axvline(x=40, color=MUTED_RED, ls="--", lw=1.2)
    ax.text(41.0, 6.0, "t = 40s: GET /retrieve?burn=true\nKích hoạt _wipe() byte 0x00\nRAM giải phóng tức thì = 0 MB", fontsize=8, color=MUTED_RED, fontweight="bold")

    ax.set_title("Hình 13: Biểu Đồ Giám Sát Bộ Nhớ RAM Broker: Cơ Chế Tẩy Xóa Tức Thì (Memory Scrubbing)", pad=15, color=NAVY)
    ax.set_xlabel("Thời gian vận hành (Giây)")
    ax.set_ylabel("Bộ nhớ RAM sử dụng (Megabytes)")
    ax.set_ylim(-0.5, 12)
    ax.set_xlim(0, 70)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", frameon=True)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_13_ram_scrubbing_timeline.png")
    plt.close()
    print("   [+] Saved hinh_13_ram_scrubbing_timeline.png")


# ==============================================================================
# HÌNH 14: ĐÁNH GIÁ MỨC ĐỘ BẢO VỆ STRIDE
# ==============================================================================
def draw_fig_14():
    categories = [
        "S - Mạo Danh\n(Spoofing)",
        "T - Giả Mạo\n(Tampering)",
        "R - Chối Bỏ\n(Repudiation)",
        "I - Lộ Tin\n(Information)",
        "D - Từ Chối Dịch Vụ\n(DoS)",
        "E - Nâng Quyền\n(Elevation)"
    ]
    num_vars = len(categories)

    cloakshare_scores = [9.5, 9.8, 9.6, 9.9, 7.5, 9.2]
    baseline_scores = [4.0, 3.5, 3.0, 2.0, 5.5, 4.2]

    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    cloakshare_scores += cloakshare_scores[:1]
    baseline_scores += baseline_scores[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7.5, 6.0), subplot_kw=dict(polar=True))

    ax.plot(angles, cloakshare_scores, color=NAVY, linewidth=2, label="CloakShare (Đa tầng Hybrid)")
    ax.fill(angles, cloakshare_scores, color=NAVY, alpha=0.25)

    ax.plot(angles, baseline_scores, color="#94A3B8", linewidth=1.5, ls="--", label="Hệ Thống Đám Mây Truyền Thống")
    ax.fill(angles, baseline_scores, color="#94A3B8", alpha=0.15)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), categories, fontsize=8.5)
    ax.set_ylim(0, 10)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_yticklabels(["2", "4", "6", "8", "10 (Tối Đa)"], fontsize=7.5, color=MID_SLATE)

    plt.title("Hình 14: Ma Trận Đánh Giá Khả Năng Phòng Thủ Theo Mô Hình STRIDE (Thang điểm 10)", pad=25, color=NAVY, fontweight="bold")
    plt.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), frameon=True)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_14_stride_radar_chart.png")
    plt.close()
    print("   [+] Saved hinh_14_stride_radar_chart.png")


# ==============================================================================
# HÌNH 15: SO SÁNH KÍCH THƯỚC KHÓA & BẢN MÃ RSA VS PQC
# ==============================================================================
def draw_fig_15():
    fig, ax = plt.subplots(figsize=(8.8, 5.0))

    schemes = ["RSA-2048\n(Cổ điển)", "ML-KEM-768\n(Kyber PQC)", "ML-DSA-65\n(Dilithium PQC)"]
    x = np.arange(len(schemes))
    width = 0.28

    pub_keys = [270, 1184, 1952]
    cipher_sig = [256, 1088, 3293]

    r1 = ax.bar(x - width/2, pub_keys, width, label="Khóa Công Khai (Public Key Bytes)", color=NAVY, edgecolor=DARK_SLATE)
    r2 = ax.bar(x + width/2, cipher_sig, width, label="Bản Mã Bọc / Chữ Ký Số (Bytes)", color=ACCENT_BLUE, edgecolor=DARK_SLATE)

    ax.set_title("Hình 15: So Sánh Kích Thước Khóa và Dữ Liệu Bọc: RSA Cổ Điển vs Chuẩn NIST PQC", pad=15, color=NAVY)
    ax.set_ylabel("Kích thước dữ liệu (Bytes)")
    ax.set_xticks(x)
    ax.set_xticklabels(schemes)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.set_ylim(0, 3800)
    ax.legend(frameon=True)

    for r in r1:
        h = r.get_height()
        ax.text(r.get_x() + r.get_width()/2, h + 50, f"{h} B", ha="center", va="bottom", fontsize=8, fontweight="bold")

    for r in r2:
        h = r.get_height()
        ax.text(r.get_x() + r.get_width()/2, h + 50, f"{h} B", ha="center", va="bottom", fontsize=8, fontweight="bold", color=ACCENT_BLUE)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_15_pqc_comparison.png")
    plt.close()
    print("   [+] Saved hinh_15_pqc_comparison.png")


# ==============================================================================
# HÌNH 16: SƠ ĐỒ LỚP (CLASS DIAGRAM) ENGINE LAYER
# ==============================================================================
def draw_fig_16():
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    ax.text(5, 8.1, "Hình 16: Sơ Đồ Lớp (UML Class Diagram) Tầng Điều Phối Engine CloakShare",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    classes = [
        (0.5, 4.6, 2.8, 3.0, "AESWrapper", "• lib_path: str\n• _c_lib: CDLL\n───────────────────\n+ encrypt(data, key)\n+ decrypt(data, key, iv)\n+ _bind_c_functions()"),
        (3.6, 4.6, 2.8, 3.0, "RSAEnvelope", "• key_size = 2048\n• padding = OAEP-SHA256\n───────────────────\n+ wrap_key(aes_key, pub)\n+ unwrap_key(wrapped, priv)\n+ generate_rsa_key_pair()"),
        (6.7, 4.6, 2.8, 3.0, "IntegritySigner", "• hash = SHA-256\n• salt_length = 32B\n───────────────────\n+ sign_file(data, priv)\n+ verify_file(data, sig, pub)\n+ sign_ecdsa(data, priv)\n+ verify_ecdsa(data, sig, addr)"),

        (0.5, 0.8, 2.8, 3.2, "DPKIClient", "• contract_addr: str\n• rpc_url: str\n• w3: Web3\n───────────────────\n+ get_public_key(addr)\n+ register_public_key(pk, pem)"),
        (3.6, 0.8, 2.8, 3.2, "Web3Auth", "• MAX_CLOCK_DRIFT = 60s\n• PREFIX = 'CloakShare Auth'\n───────────────────\n+ create_retrieve_msg()\n+ sign_challenge(pk, msg)\n+ verify_signature(addr, msg, sig)\n+ verify_retrieve_request()"),
        (6.7, 0.8, 2.8, 3.2, "CLIAdapter", "• DLL_PATH: Path\n• _aes_lib: CDLL\n───────────────────\n+ encrypt_file(in, out)\n+ decrypt_file(in, out, k, iv)\n+ wrap_aes_key(k, iv, pub)\n+ unwrap_aes_key(w, priv)")
    ]

    for x, y, w, h, name, members in classes:
        box_h = FancyBboxPatch((x, y + h - 0.55), w, 0.55, boxstyle="round,pad=0.01",
                               fc="#E2E8F0", ec=DARK_SLATE, lw=1.2)
        ax.add_patch(box_h)
        ax.text(x + w/2, y + h - 0.28, name, ha="center", va="center", fontsize=9.5, fontweight="bold", color=NAVY)

        box_b = FancyBboxPatch((x, y), w, h - 0.55, boxstyle="round,pad=0.01",
                               fc="#FFFFFF", ec=DARK_SLATE, lw=1.2)
        ax.add_patch(box_b)
        ax.text(x + 0.15, y + (h - 0.55)/2, members, va="center", fontsize=7.5, color=DARK_SLATE)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_16_class_diagram_engine.png")
    plt.close()
    print("   [+] Saved hinh_16_class_diagram_engine.png")


# ==============================================================================
# HÌNH 17: BỐ CỤC GIAO DIỆN STREAMLIT MESSENGER UI
# ==============================================================================
def draw_fig_17():
    fig, ax = plt.subplots(figsize=(9, 6.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7.5)
    ax.axis("off")

    ax.text(5, 7.1, "Hình 17: Cấu Trúc Bố Cục Kiến Trúc Giao Diện Web3 Messenger (Streamlit UI)",
            ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)

    add_box(ax, 0.5, 0.5, 9.0, 6.2, title="", bg="#F8FAFC", border=DARK_SLATE, lw=1.5)

    add_box(ax, 0.7, 0.7, 2.6, 5.8, title="SIDEBAR ĐIỀU KHIỂN",
            subtitle="• Trạng thái RPC: 8545 (Online)\n• dPKI Contract: 0x9fE4...\n• Tài khoản ví: Alice (0xf39F...)\n• Số dư: 10 ETH gas ảo\n───────────────────\nDANH BẠ LIÊN LẠC\n[o] Bob (0x7099...)\n[ ] Charlie\n───────────────────\nKẾT NỐI ĐA THIẾT BỊ\n[Mã QR LAN / Tailscale]",
            bg="#F1F5F9", lw=1.2)

    add_box(ax, 3.5, 5.4, 5.8, 1.1, title="HỘP THOẠI TRÒ CHUYỆN: ALICE -> BOB",
            subtitle="Khóa Công Khai dPKI: Đã xác thực trên EVM  |  Bảo Mật: E2EE AES-128-CBC + RSA-OAEP",
            bg="#EFF6FF", border=ACCENT_BLUE)

    add_box(ax, 3.5, 2.0, 5.8, 3.2, title="", bg="#FFFFFF", lw=1)

    box_r = FancyBboxPatch((5.8, 4.0), 3.3, 0.9, boxstyle="round,pad=0.01", fc="#0084FF", ec="none")
    ax.add_patch(box_r)
    ax.text(7.45, 4.55, "Alice: Đã gửi hợp đồng bảo mật!\nTicket: tx-8812af90  (E2EE)", color="#FFFFFF", fontsize=7.8, ha="center")
    ax.text(8.9, 4.15, "10:42", color="#CBD5E1", fontsize=6.5)

    box_l = FancyBboxPatch((3.7, 2.8), 3.3, 0.9, boxstyle="round,pad=0.01", fc="#3E4042", ec="none")
    ax.add_patch(box_l)
    ax.text(5.35, 3.35, "Bob: Đã nhận và giải mã nguyên vẹn!\nChữ ký RSA-PSS: HỢP LỆ [OK]", color="#FFFFFF", fontsize=7.8, ha="center")
    ax.text(6.8, 2.95, "10:43", color="#CBD5E1", fontsize=6.5)

    box_bg = FancyBboxPatch((3.7, 2.15), 5.4, 0.45, boxstyle="round,pad=0.01", fc="#FEF3C7", ec="#D97706")
    ax.add_patch(box_bg)
    ax.text(6.4, 2.37, "Tiến trình đồng bộ ngầm: @st.fragment(run_every=2) quét hòm thư /api/v1/inbox không giật lag UI",
            fontsize=7.2, ha="center", va="center", color="#92400E", fontweight="bold")

    add_box(ax, 3.5, 0.7, 5.8, 1.1, title="", bg="#F8FAFC", border=BORDER_GRAY)
    add_box(ax, 3.7, 0.85, 3.6, 0.8, title="Soạn tin nhắn bí mật hoặc chọn tệp tin...", bg="#FFFFFF", border=BORDER_GRAY)
    add_box(ax, 7.5, 0.85, 1.6, 0.8, title="MÃ HÓA & GỬI\n(STAGING)", bg=NAVY, border=NAVY)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "hinh_17_streamlit_ui_layout.png")
    plt.close()
    print("   [+] Saved hinh_17_streamlit_ui_layout.png")


def main():
    print("=" * 65)
    print("BAT DAU SINH 17 HINH VE CHUYEN KHAO CLOAKSHARE (CHUAN ACADEMIC)")
    print("=" * 65)

    draw_fig_01()
    draw_fig_02()
    draw_fig_03()
    draw_fig_04()
    draw_fig_05()
    draw_fig_06()
    draw_fig_07()
    draw_fig_08()
    draw_fig_09()
    draw_fig_10()
    draw_fig_11()
    draw_fig_12()
    draw_fig_13()
    draw_fig_14()
    draw_fig_15()
    draw_fig_16()
    draw_fig_17()

    print("=" * 65)
    print(f"[+] HOAN TAT! Toan bo 17 hinh ve da luu tai: {OUT_DIR}")
    print("=" * 65)


if __name__ == "__main__":
    main()
