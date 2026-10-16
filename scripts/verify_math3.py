#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hien thi van ban thuc (raw text) cua khoi cong thuc dau tien de doi chieu."""
import re
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DOCX = ROOT / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx"

with zipfile.ZipFile(DOCX) as z:
    xml = z.read("word/document.xml").decode("utf-8")

texts = [re.sub(r"<[^>]+>", "", t) for t in
         re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.DOTALL)]

targets = [
    "forall", "quad", "oplus", "mathcal", "text", "bmatrix",
    "sqrt", "frac", "equiv", "pmod",
]

print("=== CAC DOAN CHUA LENH LATEX CON SOT (raw) ===")
n = 0
for t in texts:
    if any(k in t for k in targets) and "\\mathcal" in t:
        n += 1
        print(f"  [{n}] {t[:160]}")
        if n >= 5:
            break

print()
print("=== CHIET XUAT TU XML: tim \\\\mathcal, \\\\text, \\\\oplus ===")
raw = xml
for pat in ["\\mathcal", "\\text{", "\\oplus", "\\forall", "\\quad"]:
    cnt = raw.count(pat)
    print(f"  {pat!r}: {cnt}")

# Hien 1 doan co \mathcal
idx = raw.find("\\mathcal")
if idx >= 0:
    print("\n--- Doan XML chua \\mathcal ---")
    print(raw[idx - 200: idx + 200])