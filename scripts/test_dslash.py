#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm thử backslash kép (\\quad, \\mathcal...) trong công thức nguồn."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from compile_docx import latex_to_unicode

CASES = [
    # Dòng EXACT từ file MD nguồn (thực tế repr đã thấy \\quad, \\mathcal)
    (r"$$P(M \= m | C \= c) \= P(M \= m) \\quad \\forall m \\in \\mathcal{M}, "
     r"\\forall c \\in \\mathcal{C} \\text{ sao cho } P(C \= c) \> 0$$",
     "P(M = m | C = c) = P(M = m) ∀ m ∈ M, ∀ c ∈ C sao cho P(C = c) > 0"),
    (r"$$C \= c | M \= m) \= P(C \= c) \\quad \\forall m \\in \\mathcal{M}, c \\in \\mathcal{C}$$",
     "C = c | M = m) = P(C = c) ∀ m ∈ M, c ∈ C"),
    (r"$P(K \= k) \= 1 / |\\mathcal{K}|$", "P(K = k) = 1 / |K|"),
    (r"\\mathcal{K} và \\mathcal{C}", "K và C"),
    # Ngắt dòng ma trận THẬT phải giữ nguyên (không bị gộp)
    (r"$$\begin{bmatrix} a \\\\ b \end{bmatrix}$$", "[ a; b ]"),
]

fails = 0
for i, (src, expected) in enumerate(CASES, 1):
    out = latex_to_unicode(src)
    ok = out == expected
    if not ok:
        fails += 1
    tag = "OK " if ok else "FAIL"
    print(f"[{tag}] case {i}")
    print(f"      IN : {src}")
    print(f"      OUT: {out}")
    if not ok:
        print(f"      EXP: {expected}")

# Quét: chắc chắn không còn chuỗi con kiểu "mathcal", "quad", "forall", "in " sót
BAD = ["mathcal", "\\quad", "\\forall", "\\in ", "\\text{"]
print()
allout = " || ".join(latex_to_unicode(s) for s, _ in CASES)
for b in BAD:
    if b in allout:
        print(f"  [LEAK] {b!r} còn trong output")
        fails += 1

print(f"\nKet qua: {len(CASES)} cases, {fails} loi")
sys.exit(1 if fails else 0)
