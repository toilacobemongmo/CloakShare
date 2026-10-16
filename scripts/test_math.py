#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm thử latex_to_unicode với các công thức thực tế trong báo cáo."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "scripts")
from compile_docx import latex_to_unicode as L

TESTS = [
    # (desc, input, expected_substring hoặc None)
    ("display hoan toan (Pandoc escape)", r'\$\$P(M \= m | C \= c) \= P(M \= m) \quad \forall m \in \mathcal{M}, \forall c \in \mathcal{C} \text{ sao cho } P(C \= c) \> 0\$\$', None),
    ("xtime / bithack", r'$$\text{xtime}(b) \= (b \ll 1) \oplus ((b \& 0x80) \;?\; 0x1B : 0x00)$$', None),
    ("da thuc GF(2^8)", r'$$b(x) \= b_7 x^7 + b_6 x^6 + b_5 x^5 + b_4 x^4 + b_3 x^3 + b_2 x^2 + b_1 x + b_0 \quad (b_i \in \{0, 1\})$$', None),
    ("sum + oplus", r'$$\sum_{i=0}^7 (a_i \oplus b_i) x^i$$', None),
    ("text + quote + parallel", r'$$\text{ChallengeMessage} \= \text{"CloakShare Retrieve Auth: "} \parallel \text{tx\_id} \parallel \text{Timestamp}$$', None),
    ("exp + frac + sqrt", r'$$L_n[1/3, c] \= \exp\left( (c + o(1)) (\ln n)^{1/3} (\ln \ln n)^{2/3} \right) \quad \text{v\\u1edbi } c \= \sqrt[3]{\frac{64}{9}} \approx 1.923$$', None),
    ("inline math", r'$P(K \= k) \= 1 / |\mathcal{K}|$', None),
    ("bmatrix", r'$$\begin{bmatrix} s_0 \\ s_1 \end{bmatrix} \= \begin{bmatrix} 1 & 0 \\ 1 & 1 \end{bmatrix} \begin{bmatrix} y_0 \\ y_1 \end{bmatrix}$$', None),
    ("inline mathcal", r'$\mathcal{K}$', None),
    ("mod p", r'$$y^2 \= x^3 \+ 7 \pmod p$$', None),
    ("ecrecover", r'$$\text{Address} \= \text{Keccak-256}(\text{ecrecover}(\text{Hash}, v, r, s))\[-20:\]$$', None),
    ("OAEP em", r'$EM \= 0x00 \parallel 0x02 \parallel PS \parallel 0x00 \parallel M$', None),
    ("pmod neu", r'$y \= x^{-1} \pmod{m(x)}$', None),
    ("no latex (plain)", 'thông điệp bản rõ', None),
]

print("=" * 80)
fails = 0
for desc, src, exp in TESTS:
    out = L(src)
    bad = []
    if "$" in out:
        bad.append("con $")
    if "\\" in out:
        bad.append("con backslash")
    if "{" in out or "}" in out:
        bad.append("con ngoac cuộn")
    if "\\=" in src and "\\=" in out:
        bad.append("con \\=")
    if "\\text" in out or "\\mathcal" in out or "\\oplus" in out:
        bad.append("con lenh latex")
    status = "OK " if not bad else "FAIL"
    if bad:
        fails += 1
    print(f"[{status}] {desc}")
    print(f"      IN : {src}")
    print(f"      OUT: {out}")
    if bad:
        print(f"      LOI: {', '.join(bad)}")

print("=" * 80)
print(f"Ket qua: {len(TESTS) - fails}/{len(TESTS)} dat")
