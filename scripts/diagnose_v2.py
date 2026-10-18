#!/usr/bin/env python3
"""
Chẩn đoán các ký tự chưa sạch trong tệp DOCX đầu ra (v2).

Mục đích: chỉ ra CHÍNH XÁC ký tự rác (emoji, **bold**, backslash, ###) đang
nằm ở vùng nào trong cấu trúc tài liệu (đoạn văn thường / ô header bảng /
ô dữ liệu bảng / ô code-block 1x1), từ đó khoanh vùng hàm render còn thiếu
bước làm sạch.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

BASE = Path(__file__).resolve().parent.parent
F_DOCX = BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx"
F_MD = BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx.md"
F_FIX = BASE / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang_Fixed.docx"

PAT = [("PIN", "\U0001F4CC"), ("STAR2", "**"), ("HASH3", "###"), ("BS", "\\")]

# ----------------------------------------------------------------------------
# 1) Nguồn Markdown: tổng số và số ngoài code-block
# ----------------------------------------------------------------------------
md = F_MD.read_text(encoding="utf-8")
md_nocode = re.sub(r"```.*?```", "", md, flags=re.S)
print("=== NGUON MD ===")
for name, ch in PAT:
    print(f"  {name:<6} {ch!r:<8} toan bo={md.count(ch):>6}   ngoai-code-block={md_nocode.count(ch):>6}")

# ----------------------------------------------------------------------------
# 2) DOCX v2: phân bố theo vùng cấu trúc
# ----------------------------------------------------------------------------
ZONES = ["body_para", "table_data", "table_header", "table_code(1x1)"]


def scan(path, label):
    d = docx.Document(str(path))
    zones = {z: {} for z in ZONES}
    samples = {z: [] for z in ZONES}

    def bump(zone, text):
        for name, ch in PAT:
            zones[zone][name] = zones[zone].get(name, 0) + text.count(ch)
        if text.count("**") > 0 and len(samples[zone] + [s for s in samples[zone]]) < 6:
            samples[zone].append(f"STAR2: {text[:150]}")
        elif text.count("\\") > 3 and len(samples[zone]) < 6:
            samples[zone].append(f"BS: {text[:150]}")

    for child in d.element.body.iterchildren():
        if child.tag == qn("w:p"):
            bump("body_para", Paragraph(child, d).text)
        elif child.tag == qn("w:tbl"):
            tbl = Table(child, d)
            is_code = len(tbl.columns) == 1
            for ri, row in enumerate(tbl.rows):
                if is_code:
                    zone = "table_code(1x1)"
                elif ri == 0:
                    zone = "table_header"
                else:
                    zone = "table_data"
                seen = set()
                for c in row.cells:
                    if id(c._tc) in seen:
                        continue
                    seen.add(id(c._tc))
                    for p in c.paragraphs:
                        bump(zone, p.text)

    print(f"\n=== DOCX {label} ===")
    print(f"  {'ZONE':<18}{'PIN':>7}{'STAR2':>8}{'HASH3':>7}{'BS':>7}")
    for z in ZONES:
        r = zones[z]
        print(f"  {z:<18}{r.get('PIN',0):>7}{r.get('STAR2',0):>8}{r.get('HASH3',0):>7}{r.get('BS',0):>7}")
    for z in ZONES:
        for s in samples[z]:
            print(f"    [{z}] {s}")

    return zones


v2 = scan(F_DOCX, "v2 (moi bien dich)")
try:
    fx = scan(F_FIX, "FIXED (ban cua ban)")
except Exception as ex:
    print(f"  (bo qua FIXED: {ex})")
