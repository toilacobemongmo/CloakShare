#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Khảo sát toàn bộ công thức toán học trong file .md nguồn (trước khi unescape)."""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MD = Path(__file__).resolve().parent.parent / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx.md"
text = MD.read_text(encoding="utf-8")

# unescape tối thiểu giống compiler
ESC = set("\\`*_{}[]()#+-.!|><~^{}\"'&$")
RE = re.compile(r"\\([" + re.escape("".join(sorted(ESC))) + r"])")
lines = [RE.sub(r"\1", l) for l in text.splitlines()]

display_full = 0
display_indent = 0
display_inline_in_para = 0
span_lines = 0
lens = []
samples = []
for idx, l in enumerate(lines, 1):
    if "$$" not in l:
        continue
    st = l.strip()
    n = st.count("$$")
    if n >= 2 and st.startswith("$$") and st.endswith("$$"):
        if st == l:
            display_full += 1
        else:
            display_indent += 1
        core = st[2:-2]
        lens.append(len(core))
        if len(samples) < 8:
            samples.append((idx, st[:110]))
    elif n >= 1:
        display_inline_in_para += 1

# math có trải nhiều dòng không?
open_state = False
for idx, l in enumerate(lines, 1):
    if l.count("$$") % 2 == 1:
        open_state = not open_state
        if open_state:
            span_lines += 1

inline = 0
for l in lines:
    tmp = re.sub(r"\$\$.*?\$\$", "", l)
    tmp = re.sub(r"`[^`]*`", "", tmp)
    inline += len(re.findall(r"(?<!\$)\$[^$\n]+\$(?!\$)", tmp))

print(f"Tong so dong                     : {len(lines)}")
print(f"Display math ca dong             : {display_full}")
print(f"Display math thut le (list)      : {display_indent}")
print(f"Display math longsot/trongdoan    : {display_inline_in_para}")
print(f"Display math tran dong           : {span_lines}")
print(f"Inline math $...$                : {inline}")
print(f"Do dai median display math       : {sorted(lens)[len(lens)//2] if lens else 0}")
print(f"Do dai max display math          : {max(lens) if lens else 0}")
print("\nVi du:")
for i, s in samples:
    print(f"  {i}: {s}")

# cac lenh latex pho bien
cmds = {}
for l in lines:
    for m in re.finditer(r"\\([A-Za-z]+)", l):
        cmds[m.group(1)] = cmds.get(m.group(1), 0) + 1
print("\nTop latex commands:")
for k, v in sorted(cmds.items(), key=lambda x: -x[1])[:35]:
    print(f"  \\{k:<14} {v}")

envs = {}
for l in lines:
    for m in re.finditer(r"\\(begin|end)\{(\w+\*?)\}", l):
        envs[m.group(2)] = envs.get(m.group(2), 0) + 1
print("\nEnvironments:", envs)