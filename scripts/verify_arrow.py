#!/usr/bin/env python3
"""Kiểm tra nhanh: ghi đè _v2.docx + đếm mũi tên '→' và leak 'arrow' trong DOCX."""
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path("CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx")
V2 = Path("CloakShare_Bao_Cao_Chuyen_Khao_400_Trang_v2.docx")

try:
    shutil.copyfile(BASE, V2)
    print("[OK] da ghi de _v2.docx")
except PermissionError:
    print("[!] _v2.docx dang mo trong Word - chua ghi de duoc")

with zipfile.ZipFile(BASE) as z:
    x = z.read("word/document.xml").decode("utf-8")

print("muiten '->' (U+2192):", x.count("\u2192"))
print("muiten '<-' (U+2190):", x.count("\u2190"))
print("muiten '<->' (U+2194):", x.count("\u2194"))
print("leak 'arrow':", x.count("arrow"))
print("leak 'rightarrow':", x.count("rightarrow"))
print("Cambria Math:", x.count("Cambria Math"))
