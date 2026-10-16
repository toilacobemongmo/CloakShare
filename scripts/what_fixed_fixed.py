#!/usr/bin/env python3
"""Dò chính xác bạn đã sửa gì trong bản _Fixed.docx so với bản gốc của tôi."""
import sys, re, zipfile
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import docx

BASE = Path(__file__).resolve().parent.parent
F_MINE = BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx"
F_FIX = BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang_Fixed.docx"
F_GIF = BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx.md"


def grab(path):
    d = docx.Document(str(path))
    lines = [p.text for p in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            for c in r.cells:
                lines.append(c.text)
    return lines


def count(pat, lines):
    rx = re.compile(pat)
    return sum(len(rx.findall(l)) for l in lines)


mine = grab(F_MINE)
fix = grab(F_FIX)

checks = {
    r"\\-": r"\\-  (escape thang gach)",
    r"\\#": r"\\#  (escape thang #)",
    r"\\\.": r"\\.  (escape cham ket thuc)",
    r"\\\[\d+\\\]": r"\[n\]  (escape ngoac vuong tham chieu)",
    r"\\_": r"\\_  (escape gach duoi)",
    r"\\\*": r"\\*  (escape sao)",
    r"\\": r"Tat ca backslash \\  (nao chua)",
    r"📌": r"Emoji 📌 con lai",
    r"###": r"###  (dau # heading)",
    r"!\[.*?\]\(": r"Anh markdown con lai ![](  )",
    r"```": r"Fence code ``` con lai",
    r"\*\*": r"The **bold** khong giai ma",
}

print(f"{'Muc can kiem tra':<34}{'BAN GOC':>10}{'BAN FIXED':>12}   GHI CHU")
print("-" * 76)
for pat, label in checks.items():
    a, b = count(pat, mine), count(pat, fix)
    note = "  <= ban Fixed da sua sach" if a > 0 and b == 0 else (
           "  <= ban Fixed van con" if b > 0 else "")
    print(f"{label:<34}{a:>10}{b:>12}{note}")

# Tim vi du cu the trong ban Fixed
print()
print("=" * 70)
print("VI DU CON LAI TRONG BAN FIXED (neu co):")
print("=" * 70)
shown = 0
for l in fix:
    for pat, lab in [(r"\\[-#._\[\]\*]", "escape \\x"),
                     (r"📌", "emoji 📌"),
                     (r"!\[.*?\]\(", "anh markdown"),
                     (r"```", "fence ```")]:
        m = re.search(pat, l)
        if m and shown < 10:
            s = max(0, m.start() - 50)
            print(f"  [{lab}] ...{l[s:m.end()+60]}...".replace("\n", " | "))
            shown += 1
if shown == 0:
    print("  Khong tim thay — ban Fixed da sach het.")

# Do dai / thong ke van ban
print()
print("=" * 70)
tb = sum(len(c.text) for t in docx.Document(str(F_FIX)).tables for r in t.rows for c in r.cells)
tg = sum(len(c.text) for t in docx.Document(str(F_MINE)).tables for r in t.rows for c in r.cells)
print(f"Ky tu trong bang: GOC={tg:,}  FIXED={tb:,}  (+{tb-tg:,})  -> FIXED day hon vi code block bang mau 1x1 duoc tach/tao bo sung")
print()

# Anh
for lbl, f in [("GOC", F_MINE), ("FIXED", F_FIX)]:
    with zipfile.ZipFile(f) as z:
        media = [n for n in z.namelist() if n.startswith("word/media/")]
    print(f"{lbl}: {len(media)} anh nhung")

# Kiem tra hinh 18 / logo / mobile
for lbl, f in [("GOC", F_MINE), ("FIXED", F_FIX)]:
    d = docx.Document(str(f))
    txt = "\n".join(p.text for p in d.paragraphs)
    has18 = "Hình 18" in txt
    print(f"{lbl}: co 'Hình 18' (mobile): {has18}")

# Mo ta anh
print()
print("Mo ta anh trong ban FIXED:")
with zipfile.ZipFile(F_FIX) as z:
    rels = z.read("word/_rels/document.xml.rels").decode("utf-8", "replace")
    imgs = re.findall(r'Type="[^"]*image"[^>]*Target="media/([^"]+)"', rels)
    print("   ", imgs)
print("Mo ta anh trong ban GOC:")
with zipfile.ZipFile(F_MINE) as z:
    rels = z.read("word/_rels/document.xml.rels").decode("utf-8", "replace")
    imgs = re.findall(r'Type="[^"]*image"[^>]*Target="media/([^"]+)"', rels)
    print("   ", len(imgs), "anh (dai dien hinh_01..hinh_17, ptit_logo, mobile_verified)")
