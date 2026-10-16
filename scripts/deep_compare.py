#!/usr/bin/env python3
"""Đào sâu điểm khác biệt: bảng biểu, ký tự escape markdown, cấu trúc bảng."""
import sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import docx

BASE = Path(__file__).resolve().parent.parent
F_FIXED = BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang_Fixed.docx"
F_MINE = BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx"
F_MD = BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx.md"

# ---- 1. Dem bang trong markdown nguon ----
lines = F_MD.read_text(encoding="utf-8").splitlines()
md_tables = 0
i = 0
while i < len(lines):
    s = lines[i].strip()
    if s.startswith("|") and "|" in s[1:]:
        md_tables += 1
        while i < len(lines) and lines[i].strip().startswith("|"):
            i += 1
        continue
    i += 1
print(f"[MARKDOWN] So bang trong file .md : {md_tables}")

# ---- 2. Kiem tra escape con lai trong DOCX ----
print()
ESCAPES = ["\\-", "\\#", "\\*", "\\_", "\\.", "\\]", "\\[", "\\{", "\\}", "\\\\"]
for label, f in [("FIXED", F_FIXED), ("MINE", F_MINE)]:
    d = docx.Document(str(f))
    alltext = "\n".join(p.text for p in d.paragraphs)
    for t in d.tables:
        for r in t.rows:
            for c in r.cells:
                alltext += "\n" + c.text
    print(f"--- {label} ({f.name}) ---")
    for e in ESCAPES:
        cnt = alltext.count(e)
        if cnt:
            print(f"   escape {e!r:<8} x{cnt}")
    # vi du
    for e in ["\\-", "\\#", "\\."]:
        for m in re.finditer(re.escape(e), alltext):
            s = max(0, m.start() - 40)
            print(f"      ...{alltext[s:m.start()+25]}...".replace("\n", " | "))
            break
    print()

# ---- 3. So sanh bang: kich thuoc tung bang ----
print("=" * 70)
print("SO SANH KICH THUOC TUNG BANG (rows x cols)")
print("=" * 70)
d_fixed = docx.Document(str(F_FIXED))
d_mine = docx.Document(str(F_MINE))
sf = [(len(t.rows), len(t.columns)) for t in d_fixed.tables]
sm = [(len(t.rows), len(t.columns)) for t in d_mine.tables]
print(f"FIXED: {len(sf)} bang, tong o = {sum(r*c for r,c in sf):,}")
print(f"MINE : {len(sm)} bang, tong o = {sum(r*c for r,c in sm):,}")
print()
print("Bang co trong FIXED nhung khong co (theo kich thuoc, top 20):")
from collections import Counter
cf, cm = Counter(sf), Counter(sm)
missing = cf - cm
for k, v in list(missing.items())[:20]:
    print(f"   {k[0]}x{k[1]}  x{v}")
print()
print("Bang co trong MINE nhung khong co (top 20):")
for k, v in list((cm - cf).items())[:20]:
    print(f"   {k[0]}x{k[1]}  x{v}")

# ---- 4. Tim cac bang rat lon / bat thuong ----
print()
print("Bang > 30 hang trong FIXED (top 10):")
big_f = sorted(range(len(sf)), key=lambda x: -sf[x][0])[:10]
for idx in big_f:
    t = d_fixed.tables[idx]
    print(f"   tbl#{idx}: {sf[idx][0]}x{sf[idx][1]}  | dong 0: "
          f"{[c.text[:22] for c in t.rows[0].cells][:6]}")
print()
print("Bang > 30 hang trong MINE (top 10):")
big_m = sorted(range(len(sm)), key=lambda x: -sm[x][0])[:10]
for idx in big_m:
    t = d_mine.tables[idx]
    print(f"   tbl#{idx}: {sm[idx][0]}x{sm[idx][1]}  | dong 0: "
          f"{[c.text[:22] for c in t.rows[0].cells][:6]}")