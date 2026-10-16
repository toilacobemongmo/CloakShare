"""
scripts/compile_docx.py

Biên dịch tệp báo cáo chuyên khảo CloakShare từ Markdown (CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx.md)
thành tài liệu Microsoft Word chuyên nghiệp (.docx) đạt chuẩn học thuật:
- Khổ giấy A4, lề chuẩn luận văn: Trái 30mm, Phải 20mm, Trên 20mm, Dưới 20mm.
- Typography: Times New Roman, cỡ chữ 12pt, dãn dòng 1.25x, căn đều 2 bên (Justified).
- Tiêu đề (Headings) phân cấp chuẩn: Chương (H1), Mục lớn (H2), Tiểu mục (H3, H4).
- 17 Hình vẽ học thuật chèn trực tiếp từ file PNG (figures/), căn giữa kèm caption chuẩn.
- Bảng biểu (Tables): Border thanh mảnh, header nền xanh navy chữ trắng đậm, dòng xen kẽ zebra shading.
- Khối mã nguồn (Code blocks): Khung viền viền xám nhạt, font Consolas 9pt, giữ nguyên thụt đầu dòng.
- Định lý / Bất biến (Theorems / Callouts): Khung highlight thanh lịch.
"""

import os
import re
import shutil
import sys
from pathlib import Path
import docx
from docx.shared import Inches, Pt, Mm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
MD_PATH = ROOT_DIR / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx.md"
DOCX_OUT = ROOT_DIR / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang.docx"
# Bản "v2" là tên tệp người dùng mở để xem; luôn ghi đồng bộ cùng DOCX_OUT.
DOCX_OUT_V2 = ROOT_DIR / "CloakShare_Bao_Cao_Chuyen_Khao_400_Trang_v2.docx"


# ==============================================================================
# XML HELPERS FOR ADVANCED WORD FORMATTING
# ==============================================================================

def set_cell_background(cell, hex_color: str):
    """Thiết lập màu nền cho ô trong bảng."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    """Thiết lập padding lề trong ô (đơn vị dxa, 20 dxa = 1 pt)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def set_table_borders(table, color="CBD5E1", sz="4", val="single"):
    """Đặt viền thanh mảnh chuyên nghiệp cho toàn bảng."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideV w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)


def mark_row_as_header(row):
    """Lặp lại hàng tiêu đề khi bảng nhảy trang và không bị ngắt giữa hàng."""
    trPr = row._tr.get_or_add_trPr()
    trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
    trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))


def mark_row_cant_split(row):
    """Chống ngắt hàng dữ liệu giữa 2 trang."""
    trPr = row._tr.get_or_add_trPr()
    trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))


def add_page_number_to_footer(footer):
    """Chèn số trang tự động vào giữa Footer."""
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run("Trang ")
    run.font.name = "Times New Roman"
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(148, 163, 184)
    
    # XML Field for Page
    fld1 = parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr="PAGE"/>')
    p._p.append(fld1)
    
    run2 = p.add_run(" / ")
    run2.font.name = "Times New Roman"
    run2.font.size = Pt(9.5)
    run2.font.color.rgb = RGBColor(148, 163, 184)
    
    # XML Field for Numpages
    fld2 = parse_xml(f'<w:fldSimple {nsdecls("w")} w:instr="NUMPAGES"/>')
    p._p.append(fld2)


# ==============================================================================
# MARKDOWN ESCAPE UNESCAPER
# ==============================================================================

# Ký tự mà CommonMark cho phép escape bằng dấu chéo ngược "\"
_MD_ESCAPABLE = set("\\`*_{}[]()#+-.!|><~^{}\"'&$")

_MD_ESCAPE_RE = re.compile(r"\\([" + re.escape("".join(sorted(_MD_ESCAPABLE))) + r"])")

# Escape "phi chuẩn" do Pandoc sinh khi xuất sang AsciiMath: \= \> \< \+ \/
# (không thuộc tập escapable của CommonMark nên unescape_md bỏ sót)
_PANDOC_EXTRA_ESCAPE_RE = re.compile(r"\\([=<>+/\^\-])")


def unescape_md(text: str) -> str:
    r"""
    Gỡ dấu chéo ngược escape của Markdown theo đúng chuẩn CommonMark.

    File .md nguồn được sinh từ Word/Pandoc nên chứa rất nhiều ký tự bị escape
    thừa (vd: `\_`, `\#`, `\-`, `\[1\]`). Nếu không gỡ, các ký tự này sẽ bị in
    thẳng ra văn bản Word và trông rất "lỗi". Hàm này chỉ gỡ backslash khi
    ký tự đứng sau nó là ký tự markdown-escapable, nên không đụng tới backslash
    trong mã nguồn / đường dẫn Windows (ví dụ `C:\Users\...`).

    Lưu ý: áp dụng SAU khi đã tách token `**bold**` / `*italic*` / `` `code` ``,
    và KHÔNG áp dụng cho nội dung code block.
    """
    if not text or "\\" not in text:
        return text
    # Lặp tối đa 2 lần để xử lý trường hợp escape lồng nhau (\\- -> \- -> -)
    out = text
    for _ in range(2):
        new = _MD_ESCAPE_RE.sub(r"\1", out)
        new = _PANDOC_EXTRA_ESCAPE_RE.sub(r"\1", new)
        if new == out:
            break
        out = new
    return out


# ==============================================================================
# EMOJI STRIPPER
# ==============================================================================

# Các vùng code được giữ nguyên emoji (không áp dụng strip)
_EMOJI_RES = [
    re.compile(r"[\U0001F1E6-\U0001F1FF]{2}"),          # cờ (2 ký tự)
    re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\uFE0E-\uFE0F]"),
]

# Các emoji có thể thay bằng nhãn văn bản có nghĩa (giữ tính minh họa)
_EMOJI_TEXT_MAP = {
    "📌": "GHI CHÚ:",
    "✅": "[OK]",
    "❌": "[LỖI]",
    "⚠": "[CẢNH BÁO]",
    "🔒": "[KHOÁ]",
    "🔑": "[KHÓA]",
    "🛡": "[BẢO VỆ]",
    "🔒": "[KHOÁ]",
    "🔐": "[KHOÁ]",
    "🔓": "[ĐÃ MỞ]",
    "💾": "[LƯU]",
    "📊": "[BIỂU ĐỒ]",
    "📈": "[TĂNG]",
    "📉": "[GIẢM]",
    "🚀": "[TĂNG TRƯỞNG]",
    "⚡": "[NHANH]",
    "🔥": "[NỔI BẬT]",
    "✨": "",
    "🎉": "",
    "🟢": "[●]",
    "🔴": "[●]",
    "📍": "",
    "🔗": "[LIÊN KẾT]",
    "🌐": "[MẠNG]",
    "📱": "[MOBILE]",
    "💬": "[CHAT]",
    "📦": "[GÓI]",
    "📎": "[TỆP]",
    "📥": "[NHẬN]",
    "📤": "[GỬI]",
    "🗑": "[XÓA]",
    "🔍": "[TÌM]",
    "👤": "[NGƯỜI DÙNG]",
    "🏠": "[TRANG CHỦ]",
    "🔄": "[ĐỔI MỚI]",
    "➡": "->",
    "➕": "+",
    "⛓": "",
    "🦎": "",
    "💰": "[ETH]",
    "📌": "GHI CHÚ:",
    "🎯": "",
    "🔔": "",
    "📌": "GHI CHÚ:",
    "📘": "",
    "📗": "",
    "📙": "",
    "📚": "",
    "🧠": "",
    "🛡": "[BẢO VỆ]",
    "🔐": "[KHOÁ]",
    "📩": "",
    "📨": "",
    "🧩": "",
    "🪄": "",
}


def strip_emoji(text: str) -> str:
    r"""Loại bỏ / thay thế emoji trong văn bản đầu ra Word."""
    if not text or not any(0x1F000 <= ord(c) or 0x2600 <= ord(c) <= 0x27BF or 0x2B00 <= ord(c) for c in text):
        # tránh xử lý nặng khi không có emoji
        has_emoji = False
        for c in text:
            if (0x1F000 <= ord(c) <= 0x1FAFF) or (0x2600 <= ord(c) <= 0x27BF) or (0x2B00 <= ord(c) <= 0x2BFF) or (0x2300 <= ord(c) <= 0x23FF):
                has_emoji = True
                break
        if not has_emoji:
            return text
    for emoji, repl in _EMOJI_TEXT_MAP.items():
        if emoji in text:
            text = text.replace(emoji, repl)
    # Xóa còn lại
    for rx in _EMOJI_RES:
        text = rx.sub("", text)
    # Dọn khoảng trắng thừa sau khi gỡ
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text


def _looks_like_windows_path(text: str) -> bool:
    r"""Phát hiện chuỗi kiểu đường dẫn Windows dạng C:\Users\foo để giữ backslash."""
    return bool(re.search(r"[A-Za-z]:\\", text)) and "\\" in text


# ==============================================================================
# LATEX / ASCIIMATH -> UNICODE TEXT
# ==============================================================================

# Lệnh LaTeX mà thân lệnh đã là ký tự Unicode (vd \oplus -> ⊕, \le -> ≤)
_LATEX_SYMBOLS = {
    "oplus": "⊕", "otimes": "⊗", "ominus": "⊖", "odot": "⊙",
    "cdot": "⋅", "times": "×", "div": "÷", "pm": "±", "mp": "∓",
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥",
    "ne": "≠", "neq": "≠", "equiv": "≡", "approx": "≈", "sim": "∼",
    "propto": "∝", "cong": "≅", "ll": "≪", "gg": "≫",
    "in": "∈", "notin": "∉", "ni": "∋", "subset": "⊂", "supset": "⊃",
    "subseteq": "⊆", "supseteq": "⊇", "cup": "∪", "cap": "∩",
    "forall": "∀", "exists": "∃", "neg": "¬", "lnot": "¬",
    "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨",
    "rightarrow": "→", "to": "→", "leftarrow": "←", "Rightarrow": "⇒",
    "Leftarrow": "⇐", "leftrightarrow": "↔", "mapsto": "↦",
    "infty": "∞", "partial": "∂", "nabla": "∇", "emptyset": "∅",
    "varnothing": "∅", "perp": "⊥", "parallel": "∥", "mid": "∣",
    "degree": "°", "prime": "′", "angle": "∠",
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "varepsilon": "ϵ", "zeta": "ζ", "eta": "η",
    "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π",
    "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "varphi": "ϕ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ",
    "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    "ell": "ℓ", "hbar": "ℏ", "Re": "ℜ", "Im": "ℑ",
    "sum": "∑", "prod": "∏", "int": "∫", "binom": "C",
    "gcd": "gcd", "mod": "mod", "bmod": "mod", "pmod": "mod",
    "ldots": "…", "dots": "…", "cdots": "⋯",
    "quad": " ", "qquad": "  ", "thinspace": " ", "space": " ",
    "ahir": " ", "displaystyle": "", "textstyle": "",
}

# Từ viết tắt trong \text{...} giữ nguyên khi dịch (đề phòng gỡ \text)
_KEEP_WORDS = {"AES", "RSA", "GF", "SHA", "EIP", "PKCS", "MGF", "HMAC", "XOR", "FIPS"}

_LATEX_CMD_RE = re.compile(r"\\([A-Za-z]+|.)")
_ENV_RE = re.compile(r"\\(begin|end)\{([A-Za-z*]+)\}?")


def _latex_command_to_unicode(name: str) -> str:
    """Đổi một lệnh LaTeX sang ký tự Unicode (hoặc chuỗi tương đương)."""
    if name in _LATEX_SYMBOLS:
        return _LATEX_SYMBOLS[name]
    if name == "text" or name == "mathrm" or name == "operatorname":
        return "\u0000TEXT\u0000"   # giữ nội dung, bỏ \\text{...}
    if name == "mathcal":
        return "\u0000ITAL\u0000"   # \\mathcal{M} -> M in nghiêng
    if name == "mathbb":
        return "\u0000DOUBLE\u0000"  # \\mathbb{F} -> F
    if name == "bar":
        return "\u0000BAR\u0000"    # \\bar{x} -> x̄
    if name == "sqrt":
        return "\u0000SQRT\u0000"
    if name == "frac":
        return "\u0000FRAC\u0000"
    if name == "left" or name == "right":
        return ""                   # \\left( \\right) -> chỉ giữ dấu ngoặc
    if name in (";", "!", ","):
        return " "
    if len(name) == 1 and not name.isalpha():
        # escape ký tự đặc biệt: \\=, \\+, \\& ... -> ký tự thường
        return name
    # lệnh lạ (vd \\bmod của AsciiMath) -> giữ tên chữ thường
    return name if name.isascii() and name.isalpha() else ""


def _extract_brace_group(s: str, i: int):
    """Trích nhóm { ... } bắt đầu tại s[i] (đã bỏ qua khoảng trắng)."""
    if i < len(s) and s[i] == "{":
        depth, j = 0, i
        while j < len(s):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return s[i + 1:j], j + 1
            j += 1
    return "", i


def latex_to_unicode(tex: str) -> str:
    r"""
    Dịch chuỗi LaTeX/AsciiMath (Pandoc) thành văn bản Unicode dễ đọc.

    Bỏ dấu $$ / $, chuyển \= ... \> (dấu escape Pandoc) về ký tự thường,
    \oplus -> ⊕, \mathcal{M} -> M, \text{...} -> nội dung, \frac{a}{b} -> a/b,
    \sqrt[3]{x} -> ∛(x), \begin{bmatrix} -> ma trận nhiều dòng.
    """
    if not tex:
        return tex
    s = tex

    # Chuẩn hoá backslash kép trước lệnh LaTeX: trong Markdown nguồn, "\\quad",
    # "\\forall", "\\in", "\\mathcal" bị escape dư một lớp (do Pandoc/Markdown),
    # khiến phần sau bị hiểu nhầm là "ngắt dòng ma trận" (\\  -> ROW) và in ra chữ trơ
    # "quad", "forall", "in", "mathcal". Gộp "\\<chữ cái>" về "\<chữ cái>".
    # Lưu ý: chỉ gộp khi \\ đứng ngay trước một chữ cái (tên lệnh); dấu ngắt dòng
    # thật trong ma trận (\\ theo sau là khoảng trắng / & / } / hết chuỗi) KHÔNG bị đụng.
    s = re.sub(r"\\\\(?=[A-Za-z])", lambda _m: "\\", s)

    # Bỏ lớp ngoặc nhọn thừa (Pandoc hay escape \{ \} thành ngoặc nhọn trơ)
    s = re.sub(r"\\[{}]", "", s)

    # Gỡ escape AsciiMath kiểu Pandoc: \= \> \< \+ \- \# \_ \& ... -> ký tự thường
    s = re.sub(r"\\([=<>+\-*/#&|~^`\"'!?,;:().])", r"\1", s)

    # Bỏ dấu $ (kể cả \$ đã escape)
    s = s.replace("\\$", "")
    s = re.sub(r"\$+", "", s)

    # Xử lý environment (bmatrix) trước để giữ cấu trúc dòng
    def env_repl(m):
        kind, name = m.group(1), m.group(2)
        if kind == "begin":
            return "\u0000MTX\u0000" if name in ("bmatrix", "matrix", "pmatrix", "vmatrix") else ""
        return "\u0001MTX\u0001"
    s = _ENV_RE.sub(env_repl, s)

    # Xử lý \\ (ngắt dòng trong ma trận) và & (phân cột)
    s = s.replace("\\\\", "\u0001ROW\u0001")
    s = s.replace("&", "\u0001COL\u0001")

    # Xử lý \bar{x} -> x̄ (ký tự combining, làm sau nên xử lý trước các lệnh khác)
    BAR_MAP = {"a": "ā", "e": "ē", "i": "ī", "o": "ō", "u": "ū", "x": "x̄"}
    def bar_repl(m):
        inner = m.group(1)
        return BAR_MAP.get(inner, inner + "\u0304")
    s = re.sub(r"\\bar\{([^{}]*)\}", bar_repl, s)

    # Xử lý \sqrt[3]{x} -> ∛(x)
    s = re.sub(r"\\sqrt\[([0-9]+)\]\{([^{}]*)\}",
               lambda m: {"2": "√", "3": "∛"}.get(m.group(1), f"^(1/{m.group(1)})") + f"({m.group(2)})",
               s)
    # Xử lý \sqrt{x} -> √(x)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", s)
    # Xử lý \frac{a}{b} -> a/b
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", s)

    # Xử lý \text{...} / \mathrm{...} -> giữ nguyên nội dung
    s = re.sub(r"\\(?:text|mathrm|operatorname|textnormal|mathbf|mathit|textbf|textit)\{([^{}]*)\}", r"\1", s)
    # \mathcal{M} -> M (nội dung giữ nguyên, chữ hoa thường đã là ký tự Unicode)
    s = re.sub(r"\\(?:mathcal|mathbb|mathfrak|mathscr|bm|boldsymbol|mathsf|mathtt)\{([^{}]*)\}", r"\1", s)
    # \left \right -> bỏ, giữ dấu ngoặc.
    # CHỈ bỏ khi theo sau là 1 trong các delimiter thật của \left \right
    # ( ( ) [ ] { } | . / < > ). Nếu không giới hạn, regex sẽ "ăn trúng" phần
    # đầu của các lệnh khác như \rightarrow, \leftarrow, \leftrightarrow -> \rightarrow
    # biến thành chữ trơ "arrow".
    s = re.sub(r"\\(?:left|right)\s*(?=[()[\]{}|./<>])", "", s)

    # Các lệnh còn lại
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            m = _LATEX_CMD_RE.match(s, i)
            if m:
                name = m.group(1)
                repl = _latex_command_to_unicode(name)
                # Nếu lệnh lạ có nhóm { ... } ngay sau thì lấy nội dung nhóm
                if name in _LATEX_SYMBOLS or repl in ("", "\u0000TEXT\u0000", "\u0000ITAL\u0000",
                                                      "\u0000DOUBLE\u0000", "\u0000BAR\u0000"):
                    if repl in ("", "\u0000TEXT\u0000", "\u0000ITAL\u0000", "\u0000DOUBLE\u0000", "\u0000BAR\u0000"):
                        out.append(repl if repl else "")
                    else:
                        out.append(repl)
                else:
                    out.append(repl)
                i = m.end()
                continue
        out.append(ch)
        i += 1

    res = "".join(out)

    # Gỡ marker
    res = res.replace("\u0000TEXT\u0000", "")
    res = res.replace("\u0000ITAL\u0000", "")
    res = res.replace("\u0000DOUBLE\u0000", "")
    res = res.replace("\u0000BAR\u0000", "")
    res = res.replace("\u0000SQRT\u0000", "√")
    res = res.replace("\u0000MTX\u0000", "[")
    res = res.replace("\u0001MTX\u0001", "]")
    # Gộp nhiều ROW liên tiếp (\\ \\ sinh ra chuỗi marker đôi) thành 1 ngắt dòng "; "
    res = re.sub(r"(?:\u0001ROW\u0001)+", "; ", res)
    res = res.replace("\u0001COL\u0001", ", ")

    # Gỡ ngoặc nhọn thừa
    res = res.replace("{", "").replace("}", "")

    # Chỉ số _i hoặc ^i -> giữ i (bỏ ký tự gạch dưới/caret Pandoc còn sót)
    res = re.sub(r"[_^]\{([^}]*)\}", r"\1", res)
    res = re.sub(r"[_^]([A-Za-z0-9])", r"\1", res)

    # Dọn khoảng trắng
    res = re.sub(r"[ \t]{2,}", " ", res)
    res = re.sub(r"\s+([,.;:)])", r"\1", res)
    res = re.sub(r"([(])\s+", r"\1", res)
    res = re.sub(r"\s+([)])", r"\1", res)
    return res.strip()


# ==============================================================================
# INLINE FORMATTING PARSER (Markdown bold, italic, code)
# ==============================================================================

# Khớp công thức: $$...$$ (hiển thị) hoặc $...$ (nội tuyến), chấp nhận cả \$ đã escape
_MATH_SPAN_RE = re.compile(r'(\\?\$\$.+?\\?\$\$|\\?\$[^$\n]+?\\?\$)', re.DOTALL)


def _add_plain_run(paragraph, text: str, base_font: str, base_size: float, base_color=None):
    r = paragraph.add_run(text)
    r.font.name = base_font
    r.font.size = Pt(base_size)
    if base_color:
        r.font.color.rgb = base_color
    return r


def _add_math_run(paragraph, tex: str, base_size: float, base_color=None):
    """Thêm một công thức toán học đã dịch sang Unicode, font toán học, chữ nghiêng."""
    clean = tex.replace("\\$", "$")
    if clean.startswith("$$") and clean.endswith("$$"):
        clean = clean[2:-2]
    elif clean.startswith("$") and clean.endswith("$"):
        clean = clean[1:-1]
    plain = latex_to_unicode(clean)
    if not plain:
        return None
    r = paragraph.add_run(plain)
    r.font.name = "Cambria Math"
    r.font.size = Pt(base_size)
    # Người dùng yêu cầu KHÔNG in nghiêng phần công thức (chỉ giữ font Cambria Math).
    r.italic = False
    if base_color:
        r.font.color.rgb = base_color
    return r


def add_formatted_runs(paragraph, text: str, base_font="Times New Roman", base_size=12.0, base_color=None):
    """
    Phân tích các thẻ markdown inline: **bold**, *italic*, `code` và công thức $...$.
    Công thức LaTeX/AsciiMath được dịch sang Unicode trước khi in ra Word.
    """
    if not text:
        return
    text = strip_emoji(text)

    # Tách các đoạn công thức ra trước (để không đụng tới escape markdown bên trong)
    segments = []
    pos = 0
    for m in _MATH_SPAN_RE.finditer(text):
        if m.start() > pos:
            segments.append(("text", text[pos:m.start()]))
        segments.append(("math", m.group(0)))
        pos = m.end()
    if pos < len(text):
        segments.append(("text", text[pos:]))

    for kind, seg in segments:
        if kind == "math":
            _add_math_run(paragraph, seg, base_size, base_color)
        else:
            _add_markdown_runs(paragraph, seg, base_font, base_size, base_color)


def _add_markdown_runs(paragraph, text: str, base_font: str, base_size: float, base_color=None):
    """Xử lý **bold**, *italic*, `code` cho một đoạn văn bản thuần."""
    if not text:
        return
    if not _looks_like_windows_path(text):
        text = unescape_md(text)

    # Regex tách các token inline
    # Nhóm 1: `code`
    # Nhóm 2: ***bold italic***
    # Nhóm 3: **bold**
    # Nhóm 4: *italic*
    token_pattern = re.compile(
        r'(`[^`]+`)'
        r'|(\*\*\*[^*]+\*\*\*)'
        r'|(\*\*[^*]+\*\*)'
        r'|(\*[^*]+\*)'
    )

    pos = 0
    for match in token_pattern.finditer(text):
        start, end = match.span()
        if start > pos:
            # Đoạn text thông thường
            plain = text[pos:start]
            _add_plain_run(paragraph, plain, base_font, base_size, base_color)

        tok = match.group(0)
        if tok.startswith('`') and tok.endswith('`'):
            # Inline code
            code_text = tok[1:-1]
            r = paragraph.add_run(code_text)
            r.font.name = "Consolas"
            r.font.size = Pt(base_size * 0.9)
            r.font.color.rgb = RGBColor(30, 41, 59)
            # Thêm highlight xám nhạt
            rPr = r._r.get_or_add_rPr()
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F1F5F9"/>')
            rPr.append(shd)
        elif tok.startswith('***') and tok.endswith('***'):
            # Bold & Italic
            content = tok[3:-3]
            r = paragraph.add_run(content)
            r.font.name = base_font
            r.font.size = Pt(base_size)
            r.bold = True
            r.italic = True
            if base_color:
                r.font.color.rgb = base_color
        elif tok.startswith('**') and tok.endswith('**'):
            # Bold
            content = tok[2:-2]
            r = paragraph.add_run(content)
            r.font.name = base_font
            r.font.size = Pt(base_size)
            r.bold = True
            if base_color:
                r.font.color.rgb = base_color
        elif tok.startswith('*') and tok.endswith('*'):
            # Italic
            content = tok[1:-1]
            r = paragraph.add_run(content)
            r.font.name = base_font
            r.font.size = Pt(base_size)
            r.italic = True
            if base_color:
                r.font.color.rgb = base_color

        pos = end

    if pos < len(text):
        plain = text[pos:]
        _add_plain_run(paragraph, plain, base_font, base_size, base_color)


# ==============================================================================
# MAIN COMPILER CLASS
# ==============================================================================

class MonographCompiler:
    def __init__(self, md_path: Path, out_path: Path):
        self.md_path = md_path
        self.out_path = out_path
        self.doc = docx.Document()
        self._setup_page()

    def _setup_page(self):
        """Thiết lập chuẩn trang A4 và lề học thuật."""
        section = self.doc.sections[0]
        section.page_width = Mm(210)
        section.page_height = Mm(297)
        section.top_margin = Mm(20)
        section.bottom_margin = Mm(20)
        section.left_margin = Mm(30)   # 3cm lề trái đóng gáy
        section.right_margin = Mm(20)

        # Header
        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("Báo Cáo Chuyên Khảo: Hệ Sinh Thái Trao Đổi Tệp Tin Lai Ghép CloakShare")
        hrun.font.name = "Times New Roman"
        hrun.font.size = Pt(8.5)
        hrun.font.italic = True
        hrun.font.color.rgb = RGBColor(148, 163, 184)

        # Footer
        add_page_number_to_footer(section.footer)

        # Normal style
        style = self.doc.styles['Normal']
        font = style.font
        font.name = 'Times New Roman'
        font.size = Pt(12)
        font.color.rgb = RGBColor(15, 23, 42)

    def compile(self):
        print(f"[*] Đọc tệp nguồn: {self.md_path}")
        with open(self.md_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        print(f"[*] Tổng số dòng: {total_lines}")

        i = 0
        table_count = 0
        image_count = 0
        code_block_count = 0

        while i < total_lines:
            line = lines[i]
            s_line = line.strip()

            # 1. Bỏ qua dòng trống
            if not s_line:
                i += 1
                continue

            # 2. Xử lý Khối Mã Nguồn (Code Blocks)
            if s_line.startswith("```"):
                lang = s_line[3:].strip()
                code_lines = []
                i += 1
                while i < total_lines and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i].rstrip("\r\n"))
                    i += 1
                i += 1  # Bỏ qua dòng đóng ```
                self._render_code_block(code_lines, lang)
                code_block_count += 1
                continue

            # 3. Xử lý công thức hiển thị $$...$$
            math_line = s_line.replace("\\$", "$").strip()
            if math_line.startswith("$$") and math_line.endswith("$$") and len(math_line) > 4:
                self._render_formula(math_line)
                i += 1
                continue

            # 4. Xử lý Bảng Biểu Markdown (Tables)
            if s_line.startswith("|") and "|" in s_line[1:]:
                table_lines = []
                while i < total_lines and lines[i].strip().startswith("|") and "|" in lines[i].strip()[1:]:
                    table_lines.append(lines[i].strip())
                    i += 1
                self._render_table(table_lines)
                table_count += 1
                continue

            # 5. Xử lý Hình Ảnh (![Caption](path))
            img_match = re.match(r'^!\[(.*?)\]\((.*?)\)', s_line)
            if img_match:
                caption = img_match.group(1).strip()
                img_path_rel = img_match.group(2).strip()
                self._render_image(img_path_rel, caption)
                image_count += 1
                i += 1
                continue

            # 6. Xử lý Tiêu Đề Chương & Phân Mục (Headings)
            if self._is_heading_or_special(s_line):
                self._render_heading(s_line)
                i += 1
                continue

            # 7. Xử lý Khối Blockquote / Invariant / Theorem (> ...)
            if s_line.startswith(">"):
                quote_lines = []
                while i < total_lines and lines[i].strip().startswith(">"):
                    quote_lines.append(lines[i].strip()[1:].strip())
                    i += 1
                self._render_callout("\n".join(quote_lines))
                continue

            # 8. Xử lý Danh Sách (Bullet / Numbered lists)
            list_match = re.match(r'^(\*|-|\d+\.)\s+(.*)', s_line)
            if list_match:
                prefix = list_match.group(1)
                content = list_match.group(2)
                self._render_list_item(prefix, content)
                i += 1
                continue

            # 9. Xử lý Đường Kẻ Ngang (Divider: --- hoặc ***)
            if re.match(r'^(-{3,}|\*{3,}|_{3,})$', s_line):
                # Subtle spacing
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(6)
                i += 1
                continue

            # 10. Đoạn văn thông thường (Normal Paragraph)
            self._render_paragraph(s_line)
            i += 1

        print(f"[v] Đã xử lý xong:")
        print(f"    - Bảng biểu đã chèn: {table_count}")
        print(f"    - Hình vẽ đã chèn: {image_count}")
        print(f"    - Khối mã nguồn: {code_block_count}")
        print(f"[*] Đang lưu tài liệu DOCX ra: {self.out_path} ...")
        self.doc.save(str(self.out_path))
        size_bytes = os.path.getsize(self.out_path)
        print(f"[v] Đã lưu thành công! Dung lượng tệp: {size_bytes:,} bytes ({size_bytes / (1024*1024):.2f} MB)")

    # --------------------------------------------------------------------------
    # RENDERERS
    # --------------------------------------------------------------------------

    def _is_heading_or_special(self, text: str) -> bool:
        clean = text.replace("**", "").strip()
        # Dòng chỉ chứa công thức $$...$$ không phải tiêu đề
        if clean.replace("\\$", "$").startswith("$$") and clean.replace("\\$", "$").endswith("$$"):
            return False
        if text.startswith("#"):
            return True
        if re.match(r'^CHƯƠNG\s+([0-9]+|TK|CK-[0-9]+)\s*:', clean, re.IGNORECASE):
            return True
        if re.match(r'^[0-9]+\.[0-9]+(\.[0-9]+)?(\.[0-9]+)?\s+', clean):
            return True
        specials = [
            "LỜI CAM ĐOAN", "LỜI CẢM ƠN", "TÓM TẮT",
            "DANH MỤC CÁC TỪ VIẾT TẮT VÀ THUẬT NGỮ",
            "DANH MỤC CÁC HÌNH VẼ VÀ BIỂU ĐỒ",
            "DANH MỤC CÁC BẢNG BIỂU",
            "BÁO CÁO BÀI TẬP LỚN",
            "HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG",
            "KHOA AN TOÀN THÔNG TIN",
            "HÀ NỘI 2026", "HÀ NỘI – 2026",
        ]
        for s in specials:
            if clean.upper() == s or clean.upper().startswith(s):
                return True
        return False

    def _render_heading(self, text: str):
        level = 1
        clean = text
        if text.startswith("#"):
            hashes = len(text) - len(text.lstrip("#"))
            level = min(hashes, 4)
            clean = text.lstrip("#").strip()
        else:
            clean_t = text.replace("**", "").strip()
            if re.match(r'^CHƯƠNG\s+', clean_t, re.IGNORECASE) or clean_t in [
                "LỜI CAM ĐOAN", "LỜI CẢM ƠN", "TÓM TẮT",
                "DANH MỤC CÁC TỪ VIẾT TẮT VÀ THUẬT NGỮ",
                "DANH MỤC CÁC HÌNH VẼ VÀ BIỂU ĐỒ",
                "DANH MỤC CÁC BẢNG BIỂU",
                "BÁO CÁO BÀI TẬP LỚN",
            ]:
                level = 1
            elif re.match(r'^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\s+', clean_t):
                level = 4
            elif re.match(r'^[0-9]+\.[0-9]+\.[0-9]+\s+', clean_t):
                level = 3
            elif re.match(r'^[0-9]+\.[0-9]+\s+', clean_t):
                level = 2
            else:
                level = 1

        p = self.doc.add_paragraph()
        p.paragraph_format.keep_with_next = True

        if level == 1:
            # Ngắt trang trước mỗi Chương mới (trừ phần bìa)
            clean_upper = clean.replace("**", "").strip().upper()
            if "CHƯƠNG" in clean_upper or clean_upper in ["LỜI CAM ĐOAN", "TÓM TẮT", "DANH MỤC CÁC TỪ VIẾT TẮT VÀ THUẬT NGỮ"]:
                p.paragraph_format.page_break_before = True
            p.paragraph_format.space_before = Pt(16)
            p.paragraph_format.space_after = Pt(10)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            add_formatted_runs(p, clean, base_size=15.0, base_color=RGBColor(15, 23, 42))
            for r in p.runs:
                r.bold = True
        elif level == 2:
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            add_formatted_runs(p, clean, base_size=13.5, base_color=RGBColor(30, 58, 138))
            for r in p.runs:
                r.bold = True
        elif level == 3:
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(4)
            add_formatted_runs(p, clean, base_size=12.5, base_color=RGBColor(51, 65, 85))
            for r in p.runs:
                r.bold = True
        else:
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(2)
            add_formatted_runs(p, clean, base_size=12.0, base_color=RGBColor(71, 85, 105))
            for r in p.runs:
                r.bold = True

    def _render_formula(self, tex: str):
        """
        Khối công thức hiển thị: canh giữa, nền xám nhạt, font Cambria Math, chữ nghiêng.
        Toàn bộ LaTeX được dịch sang Unicode nên Word không còn ký hiệu $$ hay \\oplus.
        """
        plain = latex_to_unicode(tex.replace("\\$", "$").strip().strip("$"))
        if not plain:
            return

        table = self.doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Mm(160)
        set_cell_background(cell, "F8FAFC")
        set_cell_margins(cell, top=90, bottom=90, left=140, right=140)

        tcPr = cell._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'<w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'<w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'</w:tcBorders>'
        ))

        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.line_spacing = 1.2
        cp.paragraph_format.space_after = Pt(0)
        r = cp.add_run(plain)
        r.font.name = "Cambria Math"
        r.font.size = Pt(12.0)
        r.italic = True
        r.font.color.rgb = RGBColor(15, 23, 42)

        sp = self.doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(2)
        sp.paragraph_format.space_after = Pt(4)

    def _render_paragraph(self, text: str):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.25
        p.paragraph_format.space_after = Pt(4)

        # Xử lý caption hình hoặc bảng dạng **Hình X.** hoặc **Bảng X:**
        clean = text.replace("**", "").strip()
        if re.match(r'^(Hình\s+[0-9]+[\.:]|Bảng\s+[0-9]+[\.:])', clean):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(8)
            add_formatted_runs(p, text, base_size=10.5, base_color=RGBColor(51, 65, 85))
            return

        add_formatted_runs(p, text, base_size=12.0)

    def _render_list_item(self, prefix: str, content: str):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.25
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.first_line_indent = Inches(-0.15)

        bullet_symbol = "• " if prefix in ["*", "-"] else f"{prefix} "
        r_bullet = p.add_run(bullet_symbol)
        r_bullet.bold = True
        r_bullet.font.name = "Times New Roman"
        r_bullet.font.size = Pt(11)
        r_bullet.font.color.rgb = RGBColor(30, 58, 138)

        add_formatted_runs(p, content, base_size=12.0)

    def _render_callout(self, text: str):
        """Khung ghi chú / Định lý / Bất biến với viền bên trái."""
        table = self.doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Mm(160)

        set_cell_background(cell, "F8FAFC")
        set_cell_margins(cell, top=100, bottom=100, left=140, right=140)

        # Đặt viền trái dày màu xanh navy (#1e3a8a), các viền khác không có
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:left w:val="single" w:sz="24" w:space="0" w:color="1E3A8A"/>'
            f'<w:top w:val="none"/>'
            f'<w:bottom w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(borders)

        cp = cell.paragraphs[0]
        cp.paragraph_format.line_spacing = 1.2
        cp.paragraph_format.space_after = Pt(0)
        add_formatted_runs(cp, text, base_size=11.0, base_color=RGBColor(30, 41, 59))
        
        # Spacer
        sp = self.doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(2)
        sp.paragraph_format.space_after = Pt(4)

    def _render_code_block(self, lines: list[str], lang: str):
        r"""
        Khung code block chuyên nghiệp: nền xám nhạt, viền mảnh, font Consolas.

        Mỗi dòng code được tách thành MỘT đoạn (paragraph) riêng bên trong ô
        bảng 1x1. Cách này giữ được thụt đầu dòng bằng khoảng trắng, tránh tình
        trạng Word hiển thị ký tự "\n" thô khi toàn khối được gộp vào một run.
        """
        table = self.doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Mm(160)

        set_cell_background(cell, "F1F5F9")
        set_cell_margins(cell, top=80, bottom=80, left=120, right=120)

        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'<w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'<w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(borders)

        # Nhãn ngôn ngữ (nếu có) ở góc trên khối code
        if lang:
            lp = cell.paragraphs[0]
            lp.paragraph_format.line_spacing = 1.0
            lp.paragraph_format.space_before = Pt(0)
            lp.paragraph_format.space_after = Pt(2)
            lr = lp.add_run(lang.upper())
            lr.font.name = "Consolas"
            lr.font.size = Pt(7.5)
            lr.font.bold = True
            lr.font.color.rgb = RGBColor(100, 116, 139)
            first_p = cell.add_paragraph()
        else:
            first_p = cell.paragraphs[0]

        # Mỗi dòng code = 1 paragraph để giữ đúng thụt đầu dòng
        for idx, code_line in enumerate(lines):
            cp = first_p if idx == 0 else cell.add_paragraph()
            cp.paragraph_format.line_spacing = 1.05
            cp.paragraph_format.space_before = Pt(0)
            cp.paragraph_format.space_after = Pt(0)
            # expandtabs để tab hiển thị đúng thành khoảng trắng cố định
            run = cp.add_run(code_line.expandtabs(4))
            run.font.name = "Consolas"
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(15, 23, 42)

        # Spacer
        sp = self.doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(2)
        sp.paragraph_format.space_after = Pt(4)

    def _render_image(self, rel_path: str, caption: str):
        """Chèn hình ảnh trực tiếp từ file PNG kèm căn giữa và caption tương ứng."""
        full_path = ROOT_DIR / rel_path
        if not full_path.exists():
            print(f"    [!] Cảnh báo: Không tìm thấy hình ảnh tại: {full_path}")
            return

        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True

        is_cover_logo = "logo" in rel_path.lower() or "ptit" in rel_path.lower()

        try:
            from PIL import Image
            with Image.open(full_path) as im:
                w, h = im.size
                ratio = h / w

            if is_cover_logo:
                img_width = Mm(52)
            elif ratio > 1.3:
                # Ảnh dọc (smartphone screenshot) căn 70mm để chiều cao ~150mm vừa trang
                img_width = Mm(70)
            else:
                # Đồ họa ngang chuẩn 150mm
                img_width = Mm(150)

            p.add_run().add_picture(str(full_path), width=img_width)
        except Exception as ex:
            print(f"    [!] Lỗi khi chèn ảnh {full_path}: {ex}")

        # Caption (Không in caption cho huy hiệu logo trang bìa)
        if caption and not is_cover_logo:
            cp = self.doc.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cp.paragraph_format.space_before = Pt(2)
            cp.paragraph_format.space_after = Pt(10)
            c_run = cp.add_run(caption)
            c_run.font.name = "Times New Roman"
            c_run.font.size = Pt(10.0)
            c_run.font.italic = True
            c_run.font.color.rgb = RGBColor(71, 85, 105)

    def _render_table(self, table_lines: list[str]):
        """Dựng bảng biểu học thuật từ markdown table.

        Bảng 1 ô duy nhất (1×n hoặc n×1, thường là khối "📌 GHI CHÚ / BẤT BIẾN")
        được render như một khung callout: emoji → nhãn văn bản, **bold** được
        phân tích, bỏ dấu markdown escape. Tránh lộ 📌 / ** thô trong tài liệu.
        """
        parsed_rows = []
        for line in table_lines:
            # Loại bỏ cột rỗng do dấu | ở đầu và cuối
            parts = [c.strip() for c in line.split("|")]
            if len(parts) >= 2 and parts[0] == "":
                parts = parts[1:]
            if len(parts) >= 1 and parts[-1] == "":
                parts = parts[:-1]
            if not parts:
                continue
            # Bỏ qua dòng phân cách header (chứa ---)
            if all(re.match(r'^:?-+:?$', p) for p in parts):
                continue
            parsed_rows.append(parts)

        if not parsed_rows:
            return

        # Phát hiện bảng callout: bảng 1-ô HOẶC ô đầu tiên bắt đầu bằng 📌
        # (một số bảng chứa ký tự "|" trong công thức nên bị tách thành nhiều cột)
        first_cell = parsed_rows[0][0] if parsed_rows[0] else ""
        is_callout = (
            all(len(row) == 1 for row in parsed_rows)
            or first_cell.lstrip().startswith("\U0001F4CC")
        )
        if is_callout and len(parsed_rows) >= 1:
            # Gom toàn bộ nội dung các ô thành một khối văn bản (nối bằng <br>)
            body_text = "<br>".join(
                " ".join(row[0].split()) for row in parsed_rows if row
            )
            # Chuyển thẻ <br> thành xuống dòng bằng cách gắn mỗi dòng thành 1 đoạn
            lines = [seg.strip() for seg in body_text.split("<br>") if seg.strip()]
            if lines:
                # Áp dụng chuẩn hóa escape + emoji trên từng dòng
                cleaned = [strip_emoji(unescape_md(seg)) for seg in lines]
                self._render_callout("\n".join(cleaned))
            return

        num_cols = max(len(row) for row in parsed_rows)
        num_rows = len(parsed_rows)

        table = self.doc.add_table(rows=num_rows, cols=num_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(table, color="CBD5E1", sz="4")

        # Phân bổ đều chiều rộng các cột (tổng 160mm)
        col_width = Mm(160.0 / num_cols)
        for col in table.columns:
            for cell in col.cells:
                cell.width = col_width

        for r_idx, row_data in enumerate(parsed_rows):
            row = table.rows[r_idx]
            is_header = (r_idx == 0)

            if is_header:
                mark_row_as_header(row)
            else:
                mark_row_cant_split(row)

            # Màu nền xen kẽ (Zebra)
            bg_color = "1E3A8A" if is_header else ("F8FAFC" if r_idx % 2 == 1 else "FFFFFF")

            for c_idx in range(num_cols):
                cell = row.cells[c_idx]
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                set_cell_background(cell, bg_color)
                set_cell_margins(cell, top=70, bottom=70, left=90, right=90)

                raw_val = row_data[c_idx] if c_idx < len(row_data) else ""
                val = unescape_md(raw_val)
                p = cell.paragraphs[0]
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)

                if is_header:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r = p.add_run(val)
                    r.font.name = "Times New Roman"
                    r.font.size = Pt(10.0)
                    r.bold = True
                    r.font.color.rgb = RGBColor(255, 255, 255)
                else:
                    # Kiểm tra xem ô có phải là số / code ngắn không
                    if len(val) <= 6 and (val.isdigit() or val.replace(".", "").isdigit()):
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    else:
                        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    add_formatted_runs(p, val, base_size=10.0, base_color=RGBColor(30, 41, 59))

        # Spacer sau bảng
        sp = self.doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(2)
        sp.paragraph_format.space_after = Pt(6)


if __name__ == "__main__":
    compiler = MonographCompiler(MD_PATH, DOCX_OUT)
    compiler.compile()
    # Ghi đồng bộ sang tên _v2 để tránh người dùng mở phải bản cũ chưa sửa công thức.
    print(f"[OK] Đã ghi: {DOCX_OUT.name}")
    try:
        shutil.copyfile(DOCX_OUT, DOCX_OUT_V2)
        print(f"[OK] Đã ghi: {DOCX_OUT_V2.name}")
    except PermissionError:
        print(
            f"[!] KHÔNG ghi được '{DOCX_OUT_V2.name}' — tệp đang MỞ trong Word.\n"
            f"    Hãy ĐÓNG Word rồi chạy lại:  python scripts/compile_docx.py\n"
            f"    (Bản gốc '{DOCX_OUT.name}' đã được cập nhật đầy đủ công thức.)"
        )
