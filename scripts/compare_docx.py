#!/usr/bin/env python3
"""So sánh chi tiết hai bản DOCX: bản bạn gửi (Fixed) và bản tôi tạo."""
import sys, re, zipfile, hashlib
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import docx
from docx.shared import Pt

BASE = Path(__file__).resolve().parent.parent
FILES = {
    "FIXED (ban ban gui)": BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang_Fixed.docx",
    "MINE (ban toi tao)": BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx",
}


def analyse(label, path: Path):
    print("=" * 78)
    print(f"{label}  ->  {path.name}")
    print("=" * 78)
    d = docx.Document(str(path))

    paras = d.paragraphs
    tables = d.tables
    print(f"Dung luong tep      : {path.stat().st_size:,} bytes")
    print(f"So doan (paragraphs): {len(paras)}")
    print(f"So bang (tables)    : {len(tables)}")
    print(f"So section          : {len(d.sections)}")

    # styles
    used = {}
    for p in paras:
        used[p.style.name] = used.get(p.style.name, 0) + 1
    print("Phan bo style       :", dict(sorted(used.items(), key=lambda x: -x[1])[:10]))

    # fonts used in runs
    fonts = {}
    sizes = {}
    for p in paras:
        for r in p.runs:
            if r.font.name:
                fonts[r.font.name] = fonts.get(r.font.name, 0) + 1
            if r.font.size:
                sizes[r.font.size.pt] = sizes.get(r.font.size.pt, 0) + 1
    print("Fonts (top)         :", dict(sorted(fonts.items(), key=lambda x: -x[1])[:6]))
    print("Sizes (top)         :", dict(sorted(sizes.items(), key=lambda x: -x[1])[:8]))

    # images
    with zipfile.ZipFile(path) as z:
        media = sorted(n for n in z.namelist() if n.startswith("word/media/"))
    print(f"Anh nhung           : {len(media)}")
    for m in media[:25]:
        print("     ", m)

    # section geometry
    for i, s in enumerate(d.sections):
        print(f"Section {i}: page {s.page_width.mm:.0f}x{s.page_height.mm:.0f}mm  "
              f"margins L{s.left_margin.mm:.0f} R{s.right_margin.mm:.0f} "
              f"T{s.top_margin.mm:.0f} B{s.bottom_margin.mm:.0f}")

    # text stats
    text = "\n".join(p.text for p in paras)
    words = len(text.split())
    print(f"So tu (ke ca bang)  : {words:,}")

    # table cell chars
    cell_chars = sum(len(c.text) for t in tables for r in t.rows for c in r.cells)
    print(f"Ky tu trong bang    : {cell_chars:,}")

    # headings outline
    heads = [p.text.strip() for p in paras
             if p.style.name.startswith("Heading") and p.text.strip()]
    print(f"So muc tieu de     : {len(heads)}")
    for h in heads[:8]:
        print("      ", h[:90])

    # figure captions
    figs = re.findall(r"Hình\s*\d+[\.:]", text)
    tabs = re.findall(r"Bảng\s*\d+[\.:]", text)
    print(f"Chuong/hinh tham chieu 'Hinh N': {len(figs)}")
    print(f"Chuong/bang tham chieu 'Bang N': {len(tabs)}")
    print()
    return {
        "paras": len(paras), "tables": len(tables), "media": len(media),
        "words": words, "cell": cell_chars, "text": text,
    }


def diff_text(a: str, b: str):
    print("=" * 78)
    print("SO SANH VAN BAN")
    print("=" * 78)
    # rough: which paragraph texts unique to each
    from collections import Counter
    ca = Counter(l.strip() for l in a.splitlines() if len(l.strip()) > 60)
    cb = Counter(l.strip() for l in b.splitlines() if len(l.strip()) > 60)
    only_fixed = [l for l in ca if l not in cb]
    only_mine = [l for l in cb if l not in ca]
    print(f"Doan (>60 ky tu) CHI co trong FIXED : {len(only_fixed)}")
    for l in only_fixed[:15]:
        print("   [F]", l[:150])
    print()
    print(f"Doan (>60 ky tu) CHI co trong MINE  : {len(only_mine)}")
    for l in only_mine[:15]:
        print("   [M]", l[:150])


stats = {}
for label, p in FILES.items():
    if p.exists():
        stats[label] = analyse(label, p)
    else:
        print("KHONG TON TAI:", p)

if len(stats) == 2:
    keys = list(stats)
    print("=" * 78)
    print("BANG TONG HOP")
    print("=" * 78)
    metrics = ["paras", "tables", "media", "words", "cell"]
    print(f"{'Metric':<10}{keys[0]:>18}{keys[1]:>18}")
    for m in metrics:
        print(f"{m:<10}{stats[keys[0]][m]:>18,}{stats[keys[1]][m]:>18,}")
    diff_text(stats[keys[0]]["text"], stats[keys[1]]["text"])