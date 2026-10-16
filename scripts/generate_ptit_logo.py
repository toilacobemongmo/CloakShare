#!/usr/bin/env python3
"""
Tạo huy hiệu học thuật chính thức Học viện Công nghệ Bưu chính Viễn thông (PTIT)
Định dạng PNG chất lượng cao 300 DPI phục vụ trang bìa chuyên khảo học thuật.
"""

import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Wedge, FancyBboxPatch
import numpy as np

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "figures" / "ptit_logo.png"

def create_ptit_logo():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(6, 6), dpi=300)
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.set_aspect("equal")
    ax.axis("off")

    # Colors
    c_red_dark = "#991b1b"
    c_red_bright = "#dc2626"
    c_gold = "#f59e0b"
    c_gold_light = "#fef3c7"
    c_navy = "#0f172a"
    c_white = "#ffffff"

    # Outer decorative gold rim
    ax.add_patch(Circle((0, 0), 1.15, facecolor="none", edgecolor=c_gold, linewidth=3.5))
    ax.add_patch(Circle((0, 0), 1.10, facecolor=c_red_dark, edgecolor=c_gold, linewidth=1.5))
    ax.add_patch(Circle((0, 0), 0.85, facecolor="none", edgecolor=c_gold, linewidth=2.0))
    
    # Inner circle base
    ax.add_patch(Circle((0, 0), 0.82, facecolor="#fff5f5", edgecolor="none"))

    # Circular text around border (Simulated with curved / radial placements or formatted arcs)
    # Top text
    top_title = "HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG"
    # Distribute characters along top arc
    n_top = len(top_title)
    start_angle = 155
    end_angle = 25
    angles = np.linspace(start_angle, end_angle, n_top)
    for ch, ang in zip(top_title, angles):
        rad = np.radians(ang)
        x = 0.975 * np.cos(rad)
        y = 0.975 * np.sin(rad)
        rot = ang - 90
        ax.text(x, y, ch, color=c_gold_light, fontsize=8.5, fontweight="bold",
                ha="center", va="center", rotation=rot, family="DejaVu Sans")

    # Bottom text
    bot_title = "POSTS AND TELECOMMUNICATIONS INSTITUTE OF TECHNOLOGY"
    n_bot = len(bot_title)
    angles_bot = np.linspace(-155, -25, n_bot)
    for ch, ang in zip(bot_title, angles_bot):
        rad = np.radians(ang)
        x = 0.975 * np.cos(rad)
        y = 0.975 * np.sin(rad)
        rot = ang + 90
        ax.text(x, y, ch, color=c_gold_light, fontsize=6.2, fontweight="bold",
                ha="center", va="center", rotation=rot, family="DejaVu Sans")

    # Left & right divider stars
    ax.text(-0.975, 0, "★", color=c_gold, fontsize=11, ha="center", va="center")
    ax.text(0.975, 0, "★", color=c_gold, fontsize=11, ha="center", va="center")

    # Center graphics: Transmission waves / Dish / Book
    # Signal waves (arcs)
    for r, lw, a in [(0.42, 3.0, 0.4), (0.54, 3.5, 0.6), (0.66, 4.0, 0.85)]:
        wave = Wedge((0, -0.05), r, 45, 135, width=0.035, facecolor=c_red_bright, alpha=a, edgecolor="none")
        ax.add_patch(wave)

    # Core globe / network node grid behind
    ax.add_patch(Circle((0, 0.22), 0.16, facecolor=c_red_dark, edgecolor=c_gold, linewidth=1.5))
    ax.text(0, 0.22, "⚛", color=c_white, fontsize=20, ha="center", va="center")

    # Stylized open book at base
    # Left page
    left_pts = np.array([[-0.45, -0.22], [-0.02, -0.26], [-0.02, -0.42], [-0.45, -0.38]])
    ax.add_patch(Polygon(left_pts, closed=True, facecolor=c_red_dark, edgecolor=c_gold, linewidth=1.5))
    # Right page
    right_pts = np.array([[0.45, -0.22], [0.02, -0.26], [0.02, -0.42], [0.45, -0.38]])
    ax.add_patch(Polygon(right_pts, closed=True, facecolor=c_red_dark, edgecolor=c_gold, linewidth=1.5))

    # Center banner for "PTIT"
    banner = FancyBboxPatch((-0.42, -0.15), 0.84, 0.26, boxstyle="round,pad=0.04,rounding_size=0.06",
                            facecolor=c_red_dark, edgecolor=c_gold, linewidth=2.5)
    ax.add_patch(banner)
    ax.text(0, -0.02, "PTIT", color=c_gold, fontsize=26, fontweight="bold",
            ha="center", va="center", family="DejaVu Sans")

    # Year ribbon
    ax.text(0, -0.52, "EST. 1953", color=c_red_dark, fontsize=8, fontweight="bold",
            ha="center", va="center", family="DejaVu Sans")

    plt.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight", transparent=False, facecolor="white")
    plt.close(fig)
    print(f"[OK] Đã xuất logo huy hiệu PTIT tại: {OUTPUT_PATH}")

if __name__ == "__main__":
    create_ptit_logo()
