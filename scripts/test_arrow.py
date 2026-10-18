#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiem tra dong 'arrow' trong danh sach + trang thai italic cua run cong thuc."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from compile_docx import latex_to_unicode, _MATH_SPAN_RE, _add_math_run

LINE = (r"\- Hàng 1: Dịch vòng sang trái 1 byte: "
        r"$\$[s\_{1,0}, s\_{1,1}, s\_{1,2}, s\_{1,3}] \\rightarrow "
        r"[s\_{1,1}, s\_{1,2}, s\_{1,3}, s\_{1,0}]\$$.")

print("RAW  :", repr(LINE))
for m in _MATH_SPAN_RE.finditer(LINE):
    print("SPAN :", repr(m.group(0)))
    print("OUT  :", repr(latex_to_unicode(m.group(0).replace("\\$", "$"))))

# So sanh voi ban khong co backslash kep
print()
print("1 backslash :", repr(latex_to_unicode(r"$[a] \rightarrow [b]$")))
print("2 backslash :", repr(latex_to_unicode(r"$[a] \\rightarrow [b]$")))

# Kiem tra run co italic khong
print()
import docx
d = docx.Document()
p = d.add_paragraph()
r = _add_math_run(p, r"$[a] \rightarrow [b]$", 12.0)
print("run text    :", repr(r.text))
print("italic      :", r.italic)
print("font        :", r.font.name)