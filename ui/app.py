import io
import os
import socket
import base64
import json
import gzip
from decimal import Decimal
import time
import uuid
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
# Sinh QR offline (không cần Internet) để bạn cùng lớp quét mã dùng thử.
try:
    import qrcode as _qrcode_lib
except Exception:  # pragma: no cover - thiếu thư viện thì vẫn chạy được (fallback API)
    _qrcode_lib = None
# Biểu đồ Plotly cho Dashboard admin (fallback: dùng st.line_chart nếu thiếu).
try:
    import plotly.express as _px
    import plotly.graph_objects as _go
except Exception:  # pragma: no cover
    _px = None
    _go = None
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

from engine.cli_adapter import CLIAdapter
from engine.dpki_client import DPKIClient
from engine.ecies_envelope import ECIESEnvelope
import eth_keys
from engine.signer import IntegritySigner
from engine.wallet_auth import Web3Auth
from engine.wrappers.aes_wrapper import AESWrapper

st.set_page_config(
    page_title="CloakShare | Web3 Secure Messenger",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown('''
<style>
/* PRECISION DARK ARCHITECTURE - evondevKit Design System */
/* Refined glassmorphism: opaque elevation layers + restrained glass budget */

:root {
    /* Color Tokens */
    --bg-canvas: #0B0E14;
    --bg-surface-1: #151A23;
    --bg-surface-2: #1A2030;
    --border-default: rgba(255, 255, 255, 0.08);
    --border-hover: rgba(255, 255, 255, 0.18);
    --text-primary: #F8FAFC;
    --text-secondary: #94A3B8;
    --text-tertiary: #64748B;
    --brand-accent: #6366F1;
    --brand-glow: #A855F7;
    --success: #10B981;
    --warning: #F59E0B;
    --error: #EF4444;
    
    /* Spacing Scale (4px base) */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 32px;
    
    /* Typography */
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', 'Consolas', monospace;
    
    /* Easing & Motion */
    --ease-spring: cubic-bezier(0.16, 1, 0.3, 1);
    --duration-fast: 150ms;
    --duration-base: 250ms;
}

/* Global Resets */
* {
    -webkit-tap-highlight-color: transparent;
}

/* Base App Background */
.stApp {
    background: radial-gradient(circle at 10% 20%, #0B0E14 0%, #1A1F2E 90%);
    color: var(--text-primary);
    font-family: var(--font-sans);
}

/* Streamlit Native Component Overrides */
[data-testid="stAppViewContainer"] {
    background: transparent;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--brand-accent) 0%, var(--brand-glow) 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    transition: all var(--duration-base) var(--ease-spring) !important;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3) !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4) !important;
}

.stButton > button:active {
    transform: scale(0.96) !important;
}

.stButton > button:focus:not(:focus-visible) {
    outline: none !important;
}

.stButton > button:focus-visible {
    outline: 2px solid var(--brand-accent) !important;
    outline-offset: 2px !important;
}

.stButton > button[kind="secondary"] {
    background: var(--bg-surface-2) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-default) !important;
    box-shadow: none !important;
}

.stButton > button[kind="secondary"]:hover {
    border-color: var(--border-hover) !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
}

/* Text Inputs & Forms */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
.stSelectbox select {
    background: var(--bg-surface-1) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    padding: 10px 14px !important;
    font-size: 14px !important;
    transition: border-color var(--duration-base) ease !important;
}

[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
.stSelectbox select:focus {
    border-color: var(--brand-accent) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1) !important;
}

/* Metrics (KPI Cards) */
[data-testid="stMetric"] {
    background: var(--bg-surface-1);
    border: 1px solid var(--border-default);
    border-radius: 12px;
    padding: var(--space-lg);
    background-clip: padding-box;
    transition: all var(--duration-base) var(--ease-spring);
}

[data-testid="stMetric"]:hover {
    transform: translateY(-4px) scale(1.01);
    border-color: var(--border-hover);
    box-shadow:
        0 4px 16px rgba(0, 0, 0, 0.3),
        0 0 0 1px rgba(99, 102, 241, 0.1),
        0 8px 32px rgba(99, 102, 241, 0.15);
}

[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-size: 13px !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}

[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, #60A5FA 0%, #A78BFA 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* Chat Messages - Precision Dark with Spring Animation */
[data-testid="stChatMessage"] {
    border-radius: 16px;
    margin-bottom: var(--space-sm);
    padding: 12px 16px;
    max-width: 80%;
    animation-duration: 400ms;
    animation-timing-function: var(--ease-spring);
    animation-fill-mode: both;
}

[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
    border: none;
    color: white;
    margin-left: auto;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.3);
    animation-name: chatPopRight;
}

[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background: var(--bg-surface-2);
    border: 1px solid var(--border-default);
    color: var(--text-primary);
    margin-right: auto;
    animation-name: chatPopLeft;
}

@keyframes chatPopLeft {
    0% {
        opacity: 0;
        transform: translateX(-20px) scale(0.95);
    }
    100% {
        opacity: 1;
        transform: translateX(0) scale(1);
    }
}

@keyframes chatPopRight {
    0% {
        opacity: 0;
        transform: translateX(20px) scale(0.95);
    }
    100% {
        opacity: 1;
        transform: translateX(0) scale(1);
    }
}

/* Custom Chat Bubbles (legacy class support) */
.chat-bubble-user {
    background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
    color: white;
    padding: 12px 18px;
    border-radius: 16px 16px 4px 16px;
    margin-bottom: 10px;
    max-width: 80%;
    float: right;
    clear: both;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.3);
    animation: chatPopRight 0.4s var(--ease-spring);
}

.chat-bubble-peer {
    background: var(--bg-surface-2);
    border: 1px solid var(--border-default);
    color: var(--text-primary);
    padding: 12px 18px;
    border-radius: 16px 16px 16px 4px;
    margin-bottom: 10px;
    max-width: 80%;
    float: left;
    clear: both;
    animation: chatPopLeft 0.4s var(--ease-spring);
}

/* Chat Container - Opaque Elevation (No Blur) */
.chat-container {
    overflow: hidden;
    padding: var(--space-lg);
    border-radius: 12px;
    background: var(--bg-surface-1);
    border: 1px solid var(--border-default);
    height: 50vh;
    overflow-y: auto;
}

/* Metric Boxes (legacy class support) - Opaque Elevation */
.metric-box {
    background: var(--bg-surface-1);
    border: 1px solid var(--border-default);
    border-radius: 12px;
    padding: var(--space-lg);
    text-align: center;
    background-clip: padding-box;
    transition: all var(--duration-base) var(--ease-spring);
}

.metric-box:hover {
    transform: translateY(-4px) scale(1.01);
    box-shadow:
        0 4px 16px rgba(0, 0, 0, 0.3),
        0 8px 32px rgba(99, 102, 241, 0.15);
    border-color: var(--border-hover);
}

.metric-num {
    font-size: 32px;
    font-weight: 800;
    background: linear-gradient(135deg, #60A5FA, #A78BFA);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.metric-sub {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 5px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}

/* Dashboard Card Headers */
.dash-card-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    padding: 10px 14px 2px 14px;
}

.dash-card-sub {
    font-size: 12px;
    color: var(--text-secondary);
    padding: 0 14px 8px 14px;
}

/* Plotly Chart Containers */
[data-testid="stPlotlyChart"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border-default);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: var(--space-sm);
    background: transparent;
    border-bottom: 1px solid var(--border-default);
}

.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
    border: none !important;
    padding: 12px 20px !important;
    font-weight: 500 !important;
    transition: color var(--duration-fast) ease !important;
}

.stTabs [aria-selected="true"] {
    color: var(--brand-accent) !important;
    border-bottom: 2px solid var(--brand-accent) !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: var(--bg-surface-1) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    font-weight: 500 !important;
}

.streamlit-expanderHeader:hover {
    border-color: var(--border-hover) !important;
}

/* File Uploader */
[data-testid="stFileUploader"] {
    background: var(--bg-surface-1);
    border: 2px dashed var(--border-default);
    border-radius: 12px;
    padding: var(--space-xl);
    transition: border-color var(--duration-base) ease;
}

[data-testid="stFileUploader"]:hover {
    border-color: var(--brand-accent);
}

/* Spinner Color Override */
.stSpinner > div {
    border-top-color: var(--brand-accent) !important;
}

/* Scrollbar Styling */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--bg-surface-1);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: var(--border-hover);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.25);
}

/* Accessibility: Reduced Motion */
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* Mobile Responsive Adjustments */
@media (max-width: 768px) {
    :root {
        --space-lg: 16px;
        --space-xl: 24px;
    }
    
    [data-testid="stMetric"] {
        padding: var(--space-md);
    }
    
    [data-testid="stMetricValue"] {
        font-size: 24px !important;
    }
    
    .metric-num {
        font-size: 28px;
    }
    
    .chat-bubble-user,
    .chat-bubble-peer {
        max-width: 90%;
    }
}
</style>
''', unsafe_allow_html=True)


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_tailscale_ip() -> str | None:
    try:
        import subprocess
        out = subprocess.check_output(["tailscale", "ip", "-4"], text=True, stderr=subprocess.DEVNULL).strip()
        if out:
            return out
    except Exception:
        pass
    return None

LOCAL_IP = get_local_ip()
TAILSCALE_IP = get_tailscale_ip()
DEFAULT_RPC = os.getenv("RPC_URL", "http://127.0.0.1:8545")
DEFAULT_CONTRACT = os.getenv("CONTRACT_ADDRESS", "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512")

if "broker_url" not in st.session_state:
    st.session_state.broker_url = os.getenv("BROKER_URL", "http://127.0.0.1:8000")

_aes = AESWrapper()

# ==========================================
# GIAO DIỆN HIỆN ĐẠI MOBILE-FIRST (DARK THEME)
# ==========================================
st.markdown("""
<style>
    /* Reset & Nền tối hiện đại */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
    }
    
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    
    .stDeployButton, [data-testid="stAppDeployButton"] {
        display: none !important;
    }
    
    [data-testid="stSidebar"] {
        display: none;
    }
    
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 100% !important;
    }

    label[data-testid="stWidgetLabel"] p {
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
    }

    /* Thẻ thông tin tài khoản trên cùng */
    .user-card {
        background: linear-gradient(135deg, #111827 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 14px 18px;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .user-header-title {
        font-size: 1.25rem;
        font-weight: 800;
        color: #38bdf8;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .user-badge-net {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 3px 8px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 600;
        display: inline-block;
    }

    /* Tabs điều hướng */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #111827;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #1f2937;
        margin-bottom: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 14px;
        color: #94a3b8 !important;
        font-size: 0.88rem;
        font-weight: 600;
        border: none !important;
        background: transparent !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.4);
    }

    /* Khung chat và bong bóng tin nhắn */
    .bubble-wrapper-left {
        display: flex;
        justify-content: flex-start;
        margin: 6px 0;
    }
    .bubble-wrapper-right {
        display: flex;
        justify-content: flex-end;
        margin: 6px 0;
    }
    .chat-bubble-left {
        background: #1e293b;
        color: #f8fafc;
        padding: 10px 14px;
        border-radius: 16px 16px 16px 4px;
        max-width: 82%;
        word-break: break-word;
        border: 1px solid #334155;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
    }
    .chat-bubble-right {
        background: linear-gradient(135deg, #1d4ed8, #2563eb);
        color: #ffffff;
        padding: 10px 14px;
        border-radius: 16px 16px 4px 16px;
        max-width: 82%;
        word-break: break-word;
        box-shadow: 0 3px 10px rgba(37, 99, 235, 0.35);
    }
    .bubble-sender {
        font-size: 0.72rem;
        font-weight: 700;
        color: #93c5fd;
        margin-bottom: 3px;
    }
    .bubble-text {
        font-size: 0.95rem;
        line-height: 1.4;
    }
    .bubble-badges {
        display: flex;
        gap: 4px;
        margin-top: 4px;
    }
    .badge-tag {
        font-size: 0.65rem;
        padding: 1px 6px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-ok {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-enc {
        background: rgba(59, 130, 246, 0.2);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.4);
    }
    .chat-time {
        font-size: 0.68rem;
        opacity: 0.7;
        margin-top: 3px;
        text-align: right;
    }

    /* Input & Select & Popover */
    .stTextInput input, .stSelectbox select, [data-baseweb="select"] {
        border-radius: 10px !important;
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border: 1px solid #334155 !important;
    }
    [data-baseweb="select"] * {
        color: #f8fafc !important;
    }

    /* Đổi toàn bộ phong cách button sang dark neon hiện đại, loại bỏ triệt để nút trắng */
    button[data-testid="stPopoverButton"],
    button[data-testid="stBaseButton-secondary"],
    button[data-testid="stBaseButton-primary"],
    button[data-testid="stBaseButton-primaryFormSubmit"],
    .stButton > button {
        background: #1e293b !important;
        color: #38bdf8 !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25) !important;
    }
    button[data-testid="stPopoverButton"] *,
    button[data-testid="stBaseButton-secondary"] * {
        color: #38bdf8 !important;
    }
    button[data-testid="stPopoverButton"]:hover,
    button[data-testid="stBaseButton-secondary"]:hover {
        background: #2563eb !important;
        border-color: #3b82f6 !important;
    }
    button[data-testid="stPopoverButton"]:hover *,
    button[data-testid="stBaseButton-secondary"]:hover * {
        color: #ffffff !important;
    }
    button[data-testid="stBaseButton-primary"],
    button[data-testid="stBaseButton-primaryFormSubmit"],
    .stFormSubmitButton > button {
        background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
        color: #ffffff !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4) !important;
    }
    button[data-testid="stBaseButton-primary"] *,
    button[data-testid="stBaseButton-primaryFormSubmit"] * {
        color: #ffffff !important;
    }

    /* Metric cards */
    .metric-box {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 12px;
        padding: 16px 14px;
        text-align: center;
        background-clip: padding-box;
        transition: border-color 0.2s ease, transform 0.2s ease;
        min-height: 105px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .metric-box:hover {
        border-color: #38bdf8;
    }
    .metric-num {
        font-size: 1.85rem;
        font-weight: 800;
        color: #38bdf8;
        line-height: 1.2;
        margin-bottom: 4px;
    }
    .metric-sub {
        font-size: 0.85rem;
        font-weight: 600;
        color: #94a3b8;
        letter-spacing: 0.02em;
    }
    .stCaption, [data-testid="stCaptionContainer"] p {
        font-size: 0.82rem !important;
        color: #94a3b8 !important;
    }

    /* Chống mờ giao diện khi Streamlit cập nhật */
    [data-stale="true"] {
        opacity: 1 !important;
        filter: none !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ĐĂNG KÝ / ĐĂNG NHẬP (AUTH GATE)
# ==========================================
# Khóa riêng ví KHÔNG còn nằm plaintext trong file. Mỗi tài khoản có
# username + mật khẩu; private key được mã hoá Fernet bằng khóa dẫn xuất
# PBKDF2(mật khẩu) trước khi ghi xuống ~/.cloakshare/accounts.json.
from engine import accounts as accounts_mod


def _logout_and_stop(message: str | None = None) -> None:
    """Xoá toàn bộ dữ liệu phiên nhạy cảm rồi dừng render."""
    for key in ("my_pk", "my_address", "my_priv_pem", "active_user"):
        st.session_state.pop(key, None)
    if message:
        st.error(message)
    st.stop()


st.markdown("""
<style>
.auth-wrap { max-width: 420px; margin: 40px auto 0 auto; }
.auth-title { font-size: 2rem; font-weight: 800; text-align: center; color: #f1f5f9; }
.auth-sub { text-align: center; color: #94a3b8; margin-bottom: 22px; }
.auth-foot { text-align: center; color: #64748b; font-size: 0.82rem; margin-top: 14px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="auth-title">CloakShare</div>'
            '<div class="auth-sub">Đăng nhập để vào phiên làm việc</div>',
            unsafe_allow_html=True)


def _seed_demo_accounts_once() -> None:
    """Tạo các tài khoản demo (thiếu cái nào tạo cái đó), mật khẩu cố định dev.

    Bao gồm tài khoản `admin` (vai trò admin) để đăng nhập xem Dashboard
    giám sát Zero-Log. Các tài khoản đã tồn tại sẽ KHÔNG bị ghi đè.
    """
    existing = {a["username"].lower() for a in accounts_mod.list_accounts()}
    demos = {
        # username: (private_key_hex, password, role)
        "admin": ("0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80", "admin123", "admin"),
        # alice = Anvil #1, bob = Anvil #2 (môi trường thử cục bộ).
        "alice": ("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d", "alice123", "user"),
        "bob": ("0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a", "bob12345", "user"),
    }
    for name, (pk_hex, pwd, role) in demos.items():
        if name.lower() in existing:
            continue
        try:
            addr = to_checksum(Account.from_key(pk_hex).address)
        except Exception:
            continue
        try:
            accounts_mod.register(name, pwd, pk_hex, addr, role=role)
        except Exception:
            pass
    # Tài khoản cũ chưa có trường role -> đồng bộ về 'user' để tránh KeyError.
    try:
        accounts_mod.ensure_roles()
    except Exception:
        pass


def render_auth_gate() -> None:
    """Màn hình đăng nhập / đăng ký. Gọi st.stop() nếu chưa đăng nhập."""
    has_accounts = bool(accounts_mod.list_accounts())
    if not has_accounts:
        _seed_demo_accounts_once()
        has_accounts = bool(accounts_mod.list_accounts())

    left, right = st.columns(2)

    # ---------------- ĐĂNG NHẬP ----------------
    with left:
        st.markdown("### Đăng Nhập")
        with st.form("login_form"):
            login_user = st.text_input("Tên đăng nhập", placeholder="alice",
                                        autocomplete="username")
            login_pwd = st.text_input("Mật khẩu", type="password",
                                      autocomplete="current-password")
            submitted = st.form_submit_button("Đăng nhập", type="primary",
                                             use_container_width=True)
        if submitted:
            try:
                with st.spinner("Đang xác thực..."):
                    private_key_hex, address = accounts_mod.authenticate(
                        login_user, login_pwd
                    )
            except accounts_mod.AuthError as exc:
                st.error(str(exc))
            else:
                st.session_state.my_pk = private_key_hex
                st.session_state.my_address = to_checksum(address)
                st.session_state.active_user = (login_user or "").strip()
                st.session_state.active_role = accounts_mod.get_role(
                    st.session_state.active_user
                )
                # Đăng nhập lại = phiên mới, khôi phục danh bạ sạch.
                for k in ("contacts", "messages", "processed_tx_ids",
                          "dpki_initialized", "last_drop_ticket"):
                    st.session_state.pop(k, None)
                _init_session_state()
                st.success(f"Xin chào {st.session_state.active_user}!")
                st.rerun()

    # ---------------- ĐĂNG KÝ ----------------
    with right:
        st.markdown("### Tạo Tài Khoản Mới")
        with st.form("register_form"):
            reg_user = st.text_input("Tên đăng nhận", placeholder="charlie",
                                     autocomplete="username")
            reg_pwd = st.text_input("Mật khẩu (>= 8 ký tự)", type="password",
                                    autocomplete="new-password")
            reg_pwd2 = st.text_input("Xác nhận mật khẩu", type="password",
                                     autocomplete="new-password")
            reg_submit = st.form_submit_button("Tạo ví + đăng ký",
                                               use_container_width=True)
        if reg_submit:
            if reg_pwd != reg_pwd2:
                st.error("Hai mật khẩu không khớp.")
            elif len(reg_pwd or "") < 8:
                st.error("Mật khẩu phải có ít nhất 8 ký tự.")
            else:
                try:
                    with st.spinner("Đang sinh cặp khóa ví..."):
                        wallet = Account.create()
                        accounts_mod.register(
                            reg_user, reg_pwd, wallet.key.hex(), wallet.address
                        )
                except accounts_mod.UsernameTaken as exc:
                    st.error(str(exc))
                except accounts_mod.AuthError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.my_pk = wallet.key.hex()
                    st.session_state.my_address = to_checksum(wallet.address)
                    st.session_state.active_user = (reg_user or "").strip()
                    st.session_state.active_role = "user"  # tài khoản mới luôn là 'user'
                    for k in ("contacts", "messages", "processed_tx_ids",
                              "dpki_initialized", "last_drop_ticket"):
                        st.session_state.pop(k, None)
                    _init_session_state()
                    st.session_state.contacts[st.session_state.active_user] = (
                        to_checksum(wallet.address)
                    )
                    st.success("Đã tạo tài khoản và đăng nhập thành công!")
                    st.rerun()

    st.markdown(
        '<div class="auth-foot">Khoá riêng ví được mã hoá Fernet '
        '(PBKDF2-HMAC-SHA256 390.000 vòng) trước khi lưu xuống đĩa.<br>'
        'Broker Zero-Log không bao giờ nhìn thấy khóa này.</div>',
        unsafe_allow_html=True,
    )
    st.stop()


# ==========================================
# QUẢN LÝ TÀI KHOẢN & DANH BẠ (BẢO TOÀN TRẠNG THÁI)
# ==========================================
def _init_session_state() -> None:
    """Khởi tạo các khoá session tương tác (danh bạ, tin nhắn, ...)."""
    if "contacts" not in st.session_state:
        st.session_state.contacts = {
            "Anvil #0": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            "Anvil #1": "0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
        }
    if "selected_peer" not in st.session_state or st.session_state.selected_peer not in st.session_state.contacts:
        st.session_state.selected_peer = list(st.session_state.contacts.keys())[0]
    if "select_chat_peer" in st.session_state and st.session_state.select_chat_peer not in st.session_state.contacts:
        st.session_state.select_chat_peer = st.session_state.selected_peer
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "processed_tx_ids" not in st.session_state:
        st.session_state.processed_tx_ids = set()
    if "last_drop_ticket" not in st.session_state:
        st.session_state.last_drop_ticket = None


if "contacts" not in st.session_state:
    _init_session_state()


def to_checksum(addr: str) -> str:
    try:
        return Web3.to_checksum_address(addr.strip())
    except Exception:
        return addr.strip()


def get_or_create_keys(wallet_pk: str) -> tuple[str, str]:
    acc = Account.from_key(wallet_pk)
    priv_hex = acc.key.hex()
    priv = eth_keys.keys.PrivateKey(acc.key)
    pub_hex = priv.public_key.to_hex()
    return priv_hex, pub_hex


def fund_and_register_dpki(wallet_pk: str, pub_pem: str) -> bool:
    """Đăng ký khoá RSA của tôi lên dPKI.

    VÁ #4: UI cho phép chạy degraded (allow_offline=True) để demo được khi
    không có Anvil — nhưng BẮT BUỘC hiển thị banner cảnh báo (xem
    `render_trust_banner()` bên dưới). Trước đây hàm này còn THIẾU `return True`
    nên luôn trả None dù thành công.
    """
    try:
        dpki = DPKIClient(
            contract_address=DEFAULT_CONTRACT,
            rpc_url=DEFAULT_RPC,
            broker_url=st.session_state.broker_url,
            allow_offline=True,
        )
        dpki.register_public_key(wallet_pk, pub_pem)
        return True
    except Exception:
        return False


# Chặn render cho tới khi đăng nhập thành công.
if "my_pk" not in st.session_state:
    render_auth_gate()

my_pk = st.session_state.my_pk
my_address = st.session_state.my_address
my_account = Account.from_key(my_pk)

# Vai trò của tài khoản đang đăng nhập. Chỉ "admin" mới xem được Dashboard
# giám sát Zero-Log (trang thông số + biểu đồ RAM thời gian thực).
if "active_role" not in st.session_state:
    st.session_state.active_role = accounts_mod.get_role(
        st.session_state.get("active_user", "")
    )
IS_ADMIN = st.session_state.active_role == "admin"

my_priv_pem, my_pub_pem = get_or_create_keys(my_pk)
dpki_client = DPKIClient(
    contract_address=DEFAULT_CONTRACT,
    rpc_url=DEFAULT_RPC,
    broker_url=st.session_state.broker_url,
    # VÁ #4: UI được phép chạy degraded để demo, NHƯNG phải hiện banner.
    allow_offline=True,
)


def render_trust_banner() -> None:
    """VÁ #4: KHAI BÁO mức tin cậy hiện tại — không bao giờ im lặng hạ cấp.

    Người dùng phải biết: khoá đang dùng có được blockchain xác thực hay không.
    Im lặng chuyển sang nguồn yếu chính là lỗ hổng cũ.
    """
    try:
        stt = dpki_client.get_status()
    except Exception:
        return

    mode = stt.get("mode", "unknown")
    if mode == "on-chain":
        st.success(
            "🔒 **dPKI: ON-CHAIN** — Khoá công khai được xác thực bởi smart contract. "
            f"Mức tin cậy: **{stt.get('trust_level', 'trustless')}**."
        )
        return

    # Degraded hoặc unavailable -> cảnh báo đỏ, KHÔNG được im lặng.
    st.error(
        "⚠️ **CẢNH BÁO MỨC TIN CẬY** — Chế độ hiện tại: "
        f"`{mode}` · Mức tin cậy: `{stt.get('trust_level', 'degraded')}`.\n\n"
        "Khoá công khai **CHƯA được xác thực on-chain**. Trong chế độ này, "
        "máy chủ trung gian (Broker) là nguồn cung cấp khoá — nghĩa là **không có "
        "bảo đảm trustless**. Chỉ dùng để demo. Khi gửi dữ liệu thật, hãy bật "
        "Anvil/EVM node và deploy dPKIRegistry."
    )
    unverified = stt.get("unverified_keys_count", 0)
    if unverified:
        st.warning(
            f"Hiện có **{unverified}** khoá trong bộ đệm ở trạng thái "
            "`broker-unverified` (chưa có chứng thực on-chain)."
        )


render_trust_banner()

# Fetch balance
balance_eth = 0.0
try:
    if dpki_client.is_live_chain():
        balance_wei = dpki_client.w3.eth.get_balance(my_address)
        balance_eth = balance_wei / 10**18
except Exception:
    pass

fund_and_register_dpki(my_pk, my_pub_pem)

# Tự động đồng bộ các đối tác từ Broker dPKI vào danh bạ
try:
    _d_res = requests.get(f"{st.session_state.broker_url}/api/v1/dpki/list", timeout=1)
    if _d_res.status_code == 200:
        for _r_addr in _d_res.json().get("addresses", []):
            if _r_addr.lower() not in [c.lower() for c in st.session_state.contacts.values()]:
                _label = f"Đối tác ({_r_addr[:6]}...{_r_addr[-4:]})"
                st.session_state.contacts[_label] = _r_addr
except Exception:
    pass


def transfer_text(m: dict) -> str:
    """Câu chữ tin nhắn chuyển tiền, tính theo người đang xem."""
    if m["from"].lower() == my_address.lower():
        who = m.get("to_name") or (m["to"][:8] + "...")
        return f"Đã chuyển cho {who} {m['amount']} ETH"
    who = m.get("from_name") or (m["from"][:8] + "...")
    return f"Đã nhận {m['amount']} ETH từ {who}"


def notify_transfer(to_addr: str, to_name: str, amt: str, tx_id: str) -> None:
    """Gửi thông báo chuyển tiền qua kênh E2E (đi qua broker nên máy nào cũng nhận được)."""
    try:
        peer_pub = dpki_client.get_public_key(to_addr)
        payload = {
            "sender": my_address,
            "sender_name": st.session_state.active_user,
            "text": f"Đã nhận {amt} ETH từ {st.session_state.active_user}",
            "kind": "transfer",
            "amount": amt,
            "is_file": False,
            "filename": "",
            "file_b64": "",
        }
        raw_bytes = json.dumps(payload).encode("utf-8")
        aes_key, iv, ciphertext = CLIAdapter.encrypt_bytes(gzip.compress(raw_bytes))
        wrapped_key = ECIESEnvelope.wrap_key(aes_key, peer_pub)
        signature = IntegritySigner.sign_file(ciphertext, my_priv_pem)
        requests.post(
            f"{st.session_state.broker_url}/api/v1/stage",
            json={
                "tx_id": tx_id,
                "recipient": to_addr,
                "iv": iv.hex(),
                "wrapped_key": wrapped_key.hex(),
                "ciphertext": ciphertext.hex(),
                "signature": signature.hex(),
                "ttl_seconds": 600,
            },
            timeout=5,
        )
    except Exception:
        pass


def send_eth(to_addr: str, to_name: str, amount: float) -> tuple[bool, str]:
    """Chuyển ETH thật trên chain (Anvil) từ tài khoản đang dùng sang đối tác."""
    try:
        w3 = dpki_client.w3
        if not dpki_client.is_live_chain():
            return False, "Chưa kết nối được blockchain (Anvil). Kiểm tra RPC_URL và Anvil có chạy với --host 0.0.0.0 không."
        to = Web3.to_checksum_address(to_addr)
        if to.lower() == my_address.lower():
            return False, "Không thể tự chuyển cho chính mình."
        value = Web3.to_wei(Decimal(str(amount)), "ether")
        gas_price = w3.eth.gas_price
        if w3.eth.get_balance(my_address) < value + 21000 * gas_price:
            return False, "Không đủ số dư (cần dư thêm một chút phí gas)."
        tx = {
            "to": to,
            "value": value,
            "gas": 21000,
            "gasPrice": gas_price,
            "nonce": w3.eth.get_transaction_count(my_address),
            "chainId": w3.eth.chain_id,
        }
        signed = w3.eth.account.sign_transaction(tx, my_pk)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
    except Exception as e:
        return False, f"Chuyển thất bại: {e}"

    amt = f"{amount:.4f}".rstrip("0").rstrip(".")
    tf_id = f"0x{uuid.uuid4().hex}"
    st.session_state.messages.append({
        "id": tf_id,
        "kind": "transfer",
        "amount": amt,
        "from": my_address,
        "from_name": st.session_state.active_user,
        "to": to,
        "to_name": to_name,
        "text": "",
        "is_file": False,
        "file_data": None,
        "filename": "",
        "time": time.strftime("%H:%M"),
        "verified": True,
        "has_signature": True,
    })
    notify_transfer(to, to_name, amt, tf_id)
    return True, f"Đã chuyển {amt} ETH cho {to_name}."


def poll_inbox():
    now_ts = int(time.time())
    sign_msg = f"CloakShare Inbox Access:{now_ts}"
    signed = my_account.sign_message(encode_defunct(text=sign_msg))
    req_headers = {
        "X-Wallet-Address": my_address,
        "X-Timestamp": str(now_ts),
        "X-Signature": signed.signature.hex(),
    }
    try:
        res = requests.get(f"{st.session_state.broker_url}/api/v1/inbox", headers=req_headers, timeout=2)
        if res.status_code == 200:
            existing_ids = {m["id"] for m in st.session_state.messages}
            for item in res.json():
                tx_id = item["tx_id"]
                if tx_id in existing_ids:
                    continue

                try:
                    iv = bytes.fromhex(item["iv"])
                    wrapped_key = bytes.fromhex(item["wrapped_key"])
                    ciphertext = bytes.fromhex(item["ciphertext"])
                    sig_hex = item.get("signature", "")
                    sig_bytes = bytes.fromhex(sig_hex) if sig_hex else b""

                    aes_key = ECIESEnvelope.unwrap_key(wrapped_key, my_priv_pem)
                    decrypted_raw = CLIAdapter.decrypt_bytes(ciphertext, aes_key, iv)
                    parsed = json.loads(gzip.decompress(decrypted_raw).decode("utf-8"))

                    sender_addr = parsed.get("sender", "Unknown")
                    sender_name = parsed.get("sender_name", sender_addr[:8])
                    content_text = parsed.get("text", "")
                    is_file = parsed.get("is_file", False)
                    file_name = parsed.get("filename", "")
                    file_data = base64.b64decode(parsed.get("file_b64", "")) if is_file else None

                    is_verified = False
                    if sig_bytes:
                        try:
                            sender_pub = dpki_client.get_public_key(sender_addr)
                            is_verified = IntegritySigner.verify_file(ciphertext, sig_bytes, sender_pub)
                        except Exception:
                            is_verified = False

                    st.session_state.messages.append({
                        "id": tx_id,
                        "from": sender_addr,
                        "from_name": sender_name,
                        "to": my_address,
                        "text": content_text,
                        "is_file": is_file,
                        "file_data": file_data,
                        "filename": file_name,
                        "time": time.strftime("%H:%M"),
                        "verified": is_verified,
                        "has_signature": bool(sig_bytes),
                        "kind": parsed.get("kind", ""),
                        "amount": parsed.get("amount", ""),
                    })
                except Exception:
                    pass
    except Exception:
        pass


poll_inbox()


# ==========================================
# THANH ĐIỀU KHIỂN DANH TÍNH (TRỰC QUAN TRÊN MÀN HÌNH)
# ==========================================
net_label = f"Tailscale: {TAILSCALE_IP}" if TAILSCALE_IP else f"LAN: {LOCAL_IP}"

def _read_balance() -> float:
    try:
        if dpki_client.is_live_chain():
            return dpki_client.w3.eth.get_balance(my_address) / 10**18
    except Exception:
        pass
    return 0.0


def _qr_image_base64(url: str) -> str | None:
    """Sinh ảnh QR TỰ CHỖ (offline) bằng thư viện `qrcode`.

    Trả về data-URI base64 để st.image hiển thị mà không cần Internet.
    Trả về None nếu chưa cài `qrcode` (caller sẽ fallback sang API ngoài).
    """
    if _qrcode_lib is None:
        return None
    try:
        qr = _qrcode_lib.QRCode(
            box_size=10,
            border=2,
            error_correction=_qrcode_lib.constants.ERROR_CORRECT_M,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


@st.fragment(run_every=5)
def render_header():
    balance_eth = _read_balance()
    st.markdown(f"""
<div class="user-card">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div class="user-header-title" style="flex-direction: column; align-items: flex-start; gap: 2px;">
            <div>CloakShare <span style="font-size: 0.85rem; color: #94a3b8; font-weight: 500;">Messenger</span></div>
            <div style="font-size: 0.8rem; color: #10b981; font-weight: 500;">Số dư: {balance_eth:.4f} ETH | Gửi tin/file: 0 ETH (Off-chain)</div>
        </div>
        <div class="user-badge-net">{net_label}</div>
    </div>
</div>
""", unsafe_allow_html=True)


render_header()

# THANH TÀI KHOẢN: tên đăng nhập đang hoạt động + Đăng xuất.
# (Đổi tài khoản giờ chỉ qua đăng nhập lại - nhập mật khẩu, không còn
#  dropdown chọn bừa.)
top_col1, top_col2, top_col3 = st.columns([2, 1.4, 1])

with top_col1:
    _role_tag = " 🛡️ ADMIN" if IS_ADMIN else ""
    st.markdown(
        f"**Tài khoản:** `{st.session_state.active_user}`{_role_tag}  \n"
        f"`{my_address}`",
    )

with top_col2:
    if st.button("Đăng ký lại khóa lên dPKI", use_container_width=True):
        with st.spinner("Đang đăng ký..."):
            try:
                tx = dpki_client.register_public_key(my_pk, my_pub_pem)
                st.success(f"Đã đăng ký! Ref: {tx}")
            except Exception as e:
                st.error(f"Lỗi: {e}")

with top_col3:
    if st.button("Đăng xuất", use_container_width=True):
        _logout_and_stop("Đã đăng xuất. Phiên làm việc được dọn sạch.")

st.caption("Để đổi tài khoản: đăng xuất rồi đăng nhập lại bằng mật khẩu.")


# ==========================================
# CÁC TAB CHÍNH (DEFAULT: CHAT TAB)
# ==========================================
tab_chat, tab_drop, tab_monitor, tab_keys = st.tabs([
    "Trò Chuyện (Chat)",
    "CloakDrop (Gửi File)",
    "Giám Sát Zero-Log",
    "Quản Lý Khóa & Mạng",
])


# ------------------------------------------------------------------ #
# TAB 1: TRÒ CHUYỆN (CHAT)                                           #
# ------------------------------------------------------------------ #
with tab_chat:
    available_peers = [name for name, addr in st.session_state.contacts.items() if addr.lower() != my_address.lower()]
    
    chat_top_c1, chat_top_c2, chat_top_c3 = st.columns([2, 1, 1])
    with chat_top_c1:
        if not available_peers:
            st.info("Chưa có liên hệ khác. Bấm 'Thêm ví' để nhập địa chỉ ví đối tác.")
            active_peer_name = ""
            active_peer_addr = ""
        else:
            p_idx = available_peers.index(st.session_state.selected_peer) if st.session_state.selected_peer in available_peers else 0
            active_peer_name = st.selectbox(
                "Đối tác trò chuyện:",
                available_peers,
                index=p_idx,
                key="select_chat_peer",
            )
            st.session_state.selected_peer = active_peer_name
            active_peer_addr = st.session_state.contacts.get(active_peer_name, "")
    
    with chat_top_c2:
        st.write("")
        st.write("")
        with st.popover("Thêm ví", use_container_width=True):
            st.markdown("##### Nhập địa chỉ ví đối tác")
            c_name = st.text_input("Tên gợi nhớ:", placeholder="VD: Điện thoại, Bạn A...", key="c_add_name")
            c_addr = st.text_input("Địa chỉ ví Ethereum:", placeholder="0x...", key="c_add_addr")
            if st.button("Lưu liên hệ", type="primary", use_container_width=True, key="c_add_save"):
                clean_addr = c_addr.strip()
                if clean_addr.startswith("0x") and len(clean_addr) == 42:
                    tag = c_name.strip() or f"Peer ({clean_addr[:6]}...)"
                    st.session_state.contacts[tag] = clean_addr
                    st.session_state.selected_peer = tag
                    st.success("Đã thêm liên hệ!")
                    st.rerun()
                else:
                    st.error("Địa chỉ ví không hợp lệ (phải bắt đầu bằng 0x và đủ 42 ký tự).")

    with chat_top_c3:
        st.write("")
        st.write("")
        if st.button("Nhận tin", use_container_width=True, help="Đồng bộ tin nhắn mới ngay lập tức"):
            poll_inbox()
            st.rerun()

    @st.fragment(run_every=2)
    def render_chat_stream():
        poll_inbox()
        # Lọc lịch sử tin nhắn
        conversation = []
        if active_peer_addr:
            for msg in st.session_state.messages:
                from_me = (msg["from"].lower() == my_address.lower() and msg["to"].lower() == active_peer_addr.lower())
                from_peer = (msg["from"].lower() == active_peer_addr.lower() and msg["to"].lower() == my_address.lower())
                if from_me or from_peer:
                    conversation.append((msg, "right" if from_me else "left"))

        # Cửa sổ chat cuộn
        with st.container(height=380):
            if not conversation:
                st.markdown(
                    '<div style="color: #64748b; text-align: center; margin-top: 140px;">'
                    'Kênh bảo mật E2E đã sẵn sàng. Chưa có tin nhắn nào.<br>Hãy gửi lời chào đầu tiên.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                for m, side in conversation:
                    wrap_cls = "bubble-wrapper-right" if side == "right" else "bubble-wrapper-left"
                    b_cls = "chat-bubble-right" if side == "right" else "chat-bubble-left"
                    sender_label = "Bạn" if side == "right" else m.get("from_name", active_peer_name)

                    sig_badge = (
                        '<span class="badge-tag badge-ok">ECDSA Ký Chuẩn</span>'
                        if m.get("verified")
                        else '<span class="badge-tag badge-enc">AES-128 C</span>'
                    )

                    bubble_txt = transfer_text(m) if m.get("kind") == "transfer" else m["text"]

                    bubble_html = f"""
                        <div class="{wrap_cls}">
                            <div class="{b_cls}">
                                <div class="bubble-sender">{sender_label}</div>
                                <div class="bubble-text">{bubble_txt}</div>
                                <div class="bubble-badges">
                                    {sig_badge}
                                    <span class="badge-tag badge-enc">ECIES (SECP256K1)</span>
                                </div>
                                <div class="chat-time">{m['time']}</div>
                            </div>
                        </div>
                    """
                    st.markdown(bubble_html, unsafe_allow_html=True)

                    if m.get("is_file") and m.get("file_data"):
                        st.download_button(
                            label=f"Tải file đính kèm: {m['filename']}",
                            data=m["file_data"],
                            file_name=m["filename"],
                            key=f"dl_msg_{m['id']}",
                            use_container_width=True,
                        )

    render_chat_stream()

    if "transfer_flash" in st.session_state:
        st.success(st.session_state.pop("transfer_flash"))

    if active_peer_addr:
        with st.expander(f"Chuyển tiền cho {active_peer_name}"):
            with st.form("transfer_form", clear_on_submit=True):
                t_amount = st.number_input("Số ETH", min_value=0.0001, value=None, step=0.1, format="%.4f", placeholder="Nhập số ETH")
                t_submit = st.form_submit_button("Chuyển", type="primary")
            if t_submit:
                if t_amount is None:
                    st.error("Hãy nhập số ETH cần chuyển.")
                else:
                    ok, t_msg = send_eth(active_peer_addr, active_peer_name, float(t_amount))
                    if ok:
                        st.session_state.transfer_flash = t_msg
                        st.rerun()
                    else:
                        st.error(t_msg)

    # Form nhập tin nhắn
    with st.form("chat_send_form", clear_on_submit=True):
        f_c1, f_c2 = st.columns([3.5, 1])
        with f_c1:
            chat_input = st.text_input("Nội dung tin nhắn:", placeholder="Nhập tin nhắn bảo mật...", label_visibility="collapsed")
            attached_file = st.file_uploader("Đính kèm file", type=None, label_visibility="collapsed")
        with f_c2:
            st.write("")
            send_btn = st.form_submit_button("Gửi", use_container_width=True, type="primary")

    if send_btn and active_peer_addr:
        if not chat_input and not attached_file:
            st.warning("Vui lòng nhập tin nhắn hoặc chọn file.")
        else:
            with st.spinner("Đang mã hóa C AES-128 và gửi lên RAM..."):
                try:
                    peer_pub = dpki_client.get_public_key(active_peer_addr)
                    tx_id = f"0x{uuid.uuid4().hex}"
                    is_file = attached_file is not None
                    f_name = attached_file.name if is_file else ""
                    f_bytes = attached_file.getvalue() if is_file else b""

                    payload_content = {
                        "sender": my_address,
                        "sender_name": st.session_state.active_user,
                        "text": chat_input if not is_file else (f"[Tệp] {chat_input}" if chat_input else f"[Tệp]: {f_name}"),
                        "is_file": is_file,
                        "filename": f_name,
                        "file_b64": base64.b64encode(f_bytes).decode("utf-8") if is_file else "",
                    }
                    raw_bytes = json.dumps(payload_content).encode("utf-8")

                    # Mã hóa 100% RAM
                    aes_key, iv, ciphertext = CLIAdapter.encrypt_bytes(gzip.compress(raw_bytes))
                    wrapped_key = ECIESEnvelope.wrap_key(aes_key, peer_pub)
                    signature = IntegritySigner.sign_file(ciphertext, my_priv_pem)

                    body = {
                        "tx_id": tx_id,
                        "recipient": active_peer_addr,
                        "iv": iv.hex(),
                        "wrapped_key": wrapped_key.hex(),
                        "ciphertext": ciphertext.hex(),
                        "signature": signature.hex(),
                        "ttl_seconds": 600,
                    }

                    res = requests.post(f"{st.session_state.broker_url}/api/v1/stage", json=body, timeout=5)
                    if res.status_code == 201:
                        st.session_state.messages.append({
                            "id": tx_id,
                            "from": my_address,
                            "from_name": st.session_state.active_user,
                            "to": active_peer_addr,
                            "text": payload_content["text"],
                            "is_file": is_file,
                            "file_data": f_bytes if is_file else None,
                            "filename": f_name,
                            "time": time.strftime("%H:%M"),
                            "verified": True,
                            "has_signature": True,
                        })
                        st.toast("Đã gửi thành công.")
                        st.rerun()
                    else:
                        st.error(f"Lỗi Broker: {res.text}")
                except ValueError as err:
                    if "chưa đăng ký" in str(err):
                        st.error(f"Thất bại: Đối tác chưa trực tuyến hoặc chưa có khóa bảo mật. Hãy chắc chắn đối tác đã tạo/đăng nhập ví!")
                    else:
                        st.error(f"Lỗi dữ liệu: {err}")
                except Exception as err:
                    st.error(f"Thao tác thất bại: {err}")


# ------------------------------------------------------------------ #
# TAB 2: CLOAKDROP (GỬI FILE ĐỘC LẬP & TỰ HỦY)                       #
# ------------------------------------------------------------------ #
with tab_drop:
    st.subheader("CloakDrop Vault - Chia Sẻ File Tự Hủy")
    st.caption("Mã hóa file độc lập, bọc khóa và chia sẻ mã Ticket ID để người nhận tự rút và giải mã.")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("##### Gửi File Mới")
        with st.form("form_drop_send"):
            d_recipient = st.selectbox(
                "Gửi tới đối tác:",
                [name for name in st.session_state.contacts.keys() if st.session_state.contacts[name].lower() != my_address.lower()],
            )
            d_file = st.file_uploader("Chọn tệp tin cần bảo vệ:")
            d_ttl = st.selectbox("Thời gian tự hủy (TTL):", [60, 300, 1800, 3600], index=1, format_func=lambda s: f"{s} giây" if s < 60 else f"{s//60} phút")
            d_burn = st.checkbox("Xóa ngay sau khi tải (Burn-After-Read)", value=True)
            d_submit = st.form_submit_button("Mã Hóa & Tải Lên RAM", type="primary", use_container_width=True)

        if d_submit and d_file and d_recipient:
            rec_addr = st.session_state.contacts[d_recipient]
            with st.spinner("Đang mã hóa..."):
                try:
                    r_pub = dpki_client.get_public_key(rec_addr)
                    ticket = f"drop-{uuid.uuid4().hex[:10]}"
                    content = {
                        "sender": my_address,
                        "filename": d_file.name,
                        "file_b64": base64.b64encode(d_file.getvalue()).decode("utf-8"),
                        "burn": d_burn,
                    }
                    raw_b = json.dumps(content).encode("utf-8")
                    k, iv_b, ct_b = CLIAdapter.encrypt_bytes(raw_b)
                    wk_b = ECIESEnvelope.wrap_key(k, r_pub)
                    sig_b = IntegritySigner.sign_file(ct_b, my_priv_pem)

                    body = {
                        "tx_id": ticket,
                        "recipient": rec_addr,
                        "iv": iv_b.hex(),
                        "wrapped_key": wk_b.hex(),
                        "ciphertext": ct_b.hex(),
                        "signature": sig_b.hex(),
                        "ttl_seconds": d_ttl,
                    }
                    res = requests.post(f"{st.session_state.broker_url}/api/v1/stage", json=body, timeout=5)
                    if res.status_code == 201:
                        st.session_state.last_drop_ticket = ticket
                        st.success("Đã mã hóa và đưa lên RAM Broker.")
                    else:
                        st.error(f"Lỗi: {res.text}")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

        if st.session_state.last_drop_ticket:
            st.info(f"**Mã Ticket gửi cho đối tác:** `{st.session_state.last_drop_ticket}`")

    with col_d2:
        st.markdown("##### Rút & Giải Mã File")
        with st.form("form_drop_claim"):
            claim_ticket = st.text_input("Nhập mã Ticket ID:", placeholder="drop-...")
            claim_burn = st.checkbox("Xóa khỏi RAM sau khi tải", value=True)
            claim_btn = st.form_submit_button("Xác Thực Ví & Nhận File", type="primary", use_container_width=True)

        if claim_btn and claim_ticket:
            with st.spinner("Đang xác thực ví Web3..."):
                try:
                    now_ts = int(time.time())
                    ts, sig_hex = Web3Auth.sign_retrieve_request(claim_ticket, my_pk, now_ts)
                    headers = {
                        "X-Wallet-Address": my_address,
                        "X-Timestamp": str(ts),
                        "X-Signature": sig_hex,
                    }
                    burn_p = "?burn=true" if claim_burn else ""
                    res = requests.get(f"{st.session_state.broker_url}/api/v1/retrieve/{claim_ticket}{burn_p}", headers=headers, timeout=5)
                    if res.status_code == 200:
                        d = res.json()
                        iv_b = bytes.fromhex(d["iv"])
                        wk_b = bytes.fromhex(d["wrapped_key"])
                        ct_b = bytes.fromhex(d["ciphertext"])
                        sig_hex = d.get("signature", "")

                        aes_k = ECIESEnvelope.unwrap_key(wk_b, my_priv_pem)
                        plain_b = CLIAdapter.decrypt_bytes(ct_b, aes_k, iv_b)
                        f_info = json.loads(plain_b.decode("utf-8"))

                        fn = f_info.get("filename", "file.bin")
                        fb = base64.b64decode(f_info.get("file_b64", ""))
                        st.success(f"Đã giải mã thành công: **{fn}** ({len(fb)} bytes).")
                        st.download_button(f"Tải về máy: {fn}", data=fb, file_name=fn, use_container_width=True)
                    else:
                        st.error(f"Lỗi rút file ({res.status_code}): {res.text}")
                except Exception as e:
                    st.error(f"Lỗi: {e}")


# ------------------------------------------------------------------ #
# NỘI DUNG DASHBOARD GIÁM SÁT - CHỈ ADMIN ĐƯỢC XEM                       #
# ------------------------------------------------------------------ #
def _format_bytes_human(b: int) -> str:
    """Chuyển đổi số bytes sang đơn vị B hoặc KB / MB chuẩn xác."""
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.2f} KB"
    else:
        return f"{b / (1024 * 1024):.2f} MB"


@st.fragment(run_every=2)
def _render_zero_log_dashboard_fragment() -> None:
    """Dashboard giám sát Zero-Log với cơ chế cập nhật mượt mà 2s/lần qua st.fragment.

    Không làm reload toàn trang, giữ giao diện ổn định và WCAG AA compliant.
    """
    _PL_LAYOUT = dict(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.45)",
        font=dict(family="Inter, sans-serif", color="#e2e8f0", size=13),
        margin=dict(l=50, r=20, t=35, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="rgba(148,163,184,0.14)", zerolinecolor="rgba(148,163,184,0.25)"),
        yaxis=dict(gridcolor="rgba(148,163,184,0.14)", zerolinecolor="rgba(148,163,184,0.25)"),
        hovermode="x unified",
        height=260,
    )

    st.markdown("### 📊 Tổng Quan Giám Sát Zero-Log Broker")
    st.caption(
        "Theo dõi trực tiếp vòng đời dữ liệu trên RAM của Broker: ghi lên RAM khi gửi, "
        "ghi đè 0x00 khi hết hạn TTL hoặc khi đối tác rút gói tin (cam kết Zero-Log 0 ghi đĩa)."
    )

    stats_data = {}
    ram_data = {}
    broker_ok = False

    try:
        r = requests.get(f"{st.session_state.broker_url}/api/v1/stats", timeout=1.5)
        if r.status_code == 200:
            stats_data = r.json()
            rr = requests.get(f"{st.session_state.broker_url}/api/v1/ram", timeout=1.5)
            if rr.status_code == 200:
                ram_data = rr.json()
            broker_ok = True
            st.session_state["cached_stats_data"] = stats_data
            st.session_state["cached_ram_data"] = ram_data
    except Exception:
        broker_ok = False

    if not broker_ok:
        st.error(
            f"🚨 **[BROKER NGOẠI TUYẾN]** Không thể kết nối tới Broker tại `{st.session_state.broker_url}`. "
            "Đang hiển thị bản chụp dữ liệu gần nhất đã lưu trong bộ nhớ tạm."
        )
        stats_data = st.session_state.get("cached_stats_data", {})
        ram_data = st.session_state.get("cached_ram_data", {})
    else:
        st.success(f"🟢 **[TRỰC TUYẾN]** Broker kết nối ổn định tại `{st.session_state.broker_url}` (Cập nhật mỗi 2 giây)")

    totals = ram_data.get("totals", {})
    ram_b = totals.get("active_bytes", stats_data.get("approx_ram_bytes", 0))
    staged_b = totals.get("bytes_staged", stats_data.get("approx_ram_bytes", 0))
    wiped_b = totals.get("bytes_wiped", 0)
    disk_writes = totals.get("disk_writes", stats_data.get("disk_writes", 0))
    entries = ram_data.get("entries", [])
    raw_events = ram_data.get("events", [])

    # Theo dõi đỉnh bộ nhớ trong phiên (Peak Memory High-Watermark)
    if "peak_ram_bytes" not in st.session_state:
        st.session_state.peak_ram_bytes = 0
    st.session_state.peak_ram_bytes = max(st.session_state.peak_ram_bytes, ram_b)
    peak_b = st.session_state.peak_ram_bytes

    # Tính toán TTL ngắn nhất còn lại
    if entries:
        min_ttl = min(e.get("ttl_remaining", 0) for e in entries)
        min_ttl_str = f"{min_ttl // 60:02d}:{min_ttl % 60:02d}"
        min_ttl_sub = f"{min_ttl} giây còn lại"
    else:
        min_ttl_str = "--:--"
        min_ttl_sub = "Không có payload chờ"

    # Lớp phủ mờ nếu Broker bị ngắt kết nối
    opacity_style = "opacity: 0.65; filter: grayscale(20%); pointer-events: none;" if not broker_ok else ""

    if opacity_style:
        st.markdown(f'<div style="{opacity_style}">', unsafe_allow_html=True)

    # ==========================================
    # 1. HÀNG 5 THẺ KPI CHUẨN ĐƠN VỊ & WCAG AA
    # ==========================================
    k1, k2, k3, k4, k5 = st.columns(5, gap="medium")

    with k1:
        st.markdown(
            f'<div class="metric-box">'
            f'<div class="metric-num" style="color: #38bdf8;">{_format_bytes_human(ram_b)}</div>'
            f'<div class="metric-sub">RAM Đang Chiếm ({stats_data.get("active_payloads", len(entries))} gói)</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with k2:
        st.markdown(
            f'<div class="metric-box">'
            f'<div class="metric-num" style="color: #60a5fa;">{_format_bytes_human(peak_b)}</div>'
            '<div class="metric-sub">Đỉnh Trong Phiên (Peak)</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with k3:
        st.markdown(
            f'<div class="metric-box">'
            f'<div class="metric-num" style="color: #fbbf24;">{min_ttl_str}</div>'
            f'<div class="metric-sub">TTL Ngắn Nhất ({min_ttl_sub})</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with k4:
        disk_color = "#10b981" if disk_writes == 0 else "#ef4444"
        disk_label = "Disk Writes (Chuẩn Zero-Log)" if disk_writes == 0 else "Cảnh Báo Ghi Đĩa!"
        st.markdown(
            f'<div class="metric-box">'
            f'<div class="metric-num" style="color: {disk_color};">{disk_writes}</div>'
            f'<div class="metric-sub">{disk_label}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with k5:
        st.markdown(
            f'<div class="metric-box">'
            f'<div class="metric-num" style="color: #f97316;">{_format_bytes_human(wiped_b)}</div>'
            f'<div class="metric-sub">Đã Ghi Đè 0x00 (Gốc: {_format_bytes_human(staged_b)})</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # ==========================================
    # 2. HAI BIỂU ĐỒ TỔNG QUAN THANH NGANG + TOOLTIP
    # ==========================================
    o1, o2 = st.columns(2, gap="medium")

    with o1:
        st.markdown("##### 📈 Tổng Quan Thao Tác RAM")
        staged_cnt = stats_data.get("total_staged", 0)
        wipe_cnt = stats_data.get("total_retrieved", 0)
        expire_cnt = stats_data.get("total_purged_expired", 0)

        fig_ops = _go.Figure(
            data=[
                _go.Bar(
                    x=[expire_cnt, wipe_cnt, staged_cnt],
                    y=["EXPIRE", "WIPE", "STAGE"],
                    orientation="h",
                    marker=dict(color=["#a855f7", "#f97316", "#3b82f6"]),
                    text=[f"{expire_cnt:,} lần", f"{wipe_cnt:,} lần", f"{staged_cnt:,} lần"],
                    textposition="auto",
                    hovertemplate="<b>Thao tác %{y}</b><br>Số lần thực thi: %{x:,} lượt<extra></extra>",
                )
            ]
        )
        fig_ops.update_layout(
            {**_PL_LAYOUT, "height": 220},
            xaxis=dict(title="Số lượt thực hiện", gridcolor="rgba(148,163,184,0.12)"),
            yaxis=dict(title="", tickfont=dict(size=13, color="#f8fafc")),
        )
        st.plotly_chart(fig_ops, use_container_width=True, config={"displayModeBar": False})

    with o2:
        st.markdown("##### 🧠 Phân Bố Bộ Nhớ RAM")
        # Tự động chuyển đổi đơn vị B / KB theo dữ liệu thực tế
        max_mem = max(staged_b, wiped_b, ram_b, 1)
        use_kb_dist = max_mem >= 2048
        scale_div = 1024.0 if use_kb_dist else 1.0
        unit_str = "KB" if use_kb_dist else "Bytes"

        vals = [ram_b / scale_div, wiped_b / scale_div, staged_b / scale_div]
        raw_b_list = [f"{ram_b:,} Bytes", f"{wiped_b:,} Bytes", f"{staged_b:,} Bytes"]
        text_labels = [f"{v:.1f} {unit_str}" if use_kb_dist else f"{int(v):,} B" for v in vals]

        fig_dist = _go.Figure(
            data=[
                _go.Bar(
                    x=vals,
                    y=["Đang Chiếm", "Đã Ghi Đè 0x00", "Đã Stage"],
                    orientation="h",
                    marker=dict(color=["#38bdf8", "#f97316", "#10b981"]),
                    text=text_labels,
                    textposition="auto",
                    customdata=raw_b_list,
                    hovertemplate="<b>%{y}</b><br>Dung lượng: %{x:.2f} " + unit_str + "<br>Chính xác: %{customdata}<extra></extra>",
                )
            ]
        )
        fig_dist.update_layout(
            {**_PL_LAYOUT, "height": 220},
            xaxis=dict(title=f"Dung lượng ({unit_str})", gridcolor="rgba(148,163,184,0.12)"),
            yaxis=dict(title="", tickfont=dict(size=13, color="#f8fafc")),
        )
        st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar": False})

    # ==========================================
    # 3. TIẾN TRÌNH DỌN SẠCH RAM (ZERO-LOG SCRUBBING RATIO)
    # ==========================================
    st.markdown("##### 🧹 Tiến Trình Dọn Sạch RAM (Zero-Log Scrubbing)")
    if staged_b == 0:
        st.progress(1.0, text="Không có dữ liệu cần dọn (RAM 100% sạch, 0 byte tồn dư)")
        st.caption("Trạng thái nhàn rỗi: 100% sạch sẽ, chưa phát sinh gói tin lưu trữ tạm thời.")
    else:
        wipe_ratio = min(1.0, wiped_b / staged_b)
        pct = wipe_ratio * 100.0
        bar_text = f"Tỷ lệ dọn sạch RAM: {pct:.1f}% ({_format_bytes_human(wiped_b)} / {_format_bytes_human(staged_b)})"
        st.progress(wipe_ratio, text=bar_text)
        if wipe_ratio >= 1.0:
            st.caption("✅ Toàn bộ dữ liệu sau khi truyền tải đã được ghi đè 0x00 an toàn tuyệt đối.")
        else:
            diff_b = staged_b - wiped_b
            st.caption(
                f"⏳ Còn {_format_bytes_human(diff_b)} đang lưu tạm trên RAM, "
                "sẽ tự động hủy bằng 0x00 ngay khi người nhận đọc hoặc hết hạn TTL."
            )

    st.write("")

    # ==========================================
    # 4. BIỂU ĐỒ REALTIME VÙNG TÔ + TỰ CO GIÃN + ĐÁNH DẤU SỰ KIỆN
    # ==========================================
    st.markdown("##### ⚡ Giám Sát RAM Thời Gian Thực (Cửa sổ 60 mẫu - Cập nhật 2s)")
    if "ram_history" not in st.session_state:
        st.session_state.ram_history = []

    now_str = time.strftime("%H:%M:%S")
    now_ts = time.time()

    # Thêm mẫu mới vào lịch sử
    st.session_state.ram_history.append(
        {
            "time": now_str,
            "ts": now_ts,
            "active_bytes": ram_b,
            "staged_bytes": staged_b,
            "wiped_bytes": wiped_b,
        }
    )

    # Giới hạn cửa sổ trượt 60 mẫu gần nhất (~2 phút)
    if len(st.session_state.ram_history) > 60:
        st.session_state.ram_history = st.session_state.ram_history[-60:]

    hist = st.session_state.ram_history
    if hist:
        rt_df = pd.DataFrame(hist)
        max_active = rt_df["active_bytes"].max()
        
        # Tự động co giãn trục Y: Dùng Bytes nếu dữ liệu nhỏ (< 2048 B), KB nếu lớn
        use_kb_rt = max_active >= 2048 or staged_b >= 4096
        y_div = 1024.0 if use_kb_rt else 1.0
        rt_unit = "KB" if use_kb_rt else "Bytes"

        rt_df["plot_active"] = rt_df["active_bytes"] / y_div
        rt_df["plot_staged"] = rt_df["staged_bytes"] / y_div
        rt_df["plot_wiped"] = rt_df["wiped_bytes"] / y_div

        fig_rt = _go.Figure()

        # Vùng tô (area fill) cho 'Đang chiếm'
        fig_rt.add_trace(
            _go.Scatter(
                x=rt_df["time"],
                y=rt_df["plot_active"],
                mode="lines",
                name="Đang chiếm trên RAM",
                line=dict(color="#38bdf8", width=2.8),
                fill="tozeroy",
                fillcolor="rgba(56, 189, 248, 0.20)",
                customdata=rt_df["active_bytes"],
                hovertemplate="<b>Đang chiếm</b>: %{y:.2f} " + rt_unit + " (%{customdata:,} B)<extra></extra>",
            )
        )

        # Đường tham chiếu Đã Stage & Đã Ghi Đè 0x00
        fig_rt.add_trace(
            _go.Scatter(
                x=rt_df["time"],
                y=rt_df["plot_staged"],
                mode="lines",
                name="Tổng Đã Stage",
                line=dict(color="#10b981", width=1.8, dash="dot"),
                customdata=rt_df["staged_bytes"],
                hovertemplate="<b>Đã Stage</b>: %{y:.2f} " + rt_unit + " (%{customdata:,} B)<extra></extra>",
            )
        )

        fig_rt.add_trace(
            _go.Scatter(
                x=rt_df["time"],
                y=rt_df["plot_wiped"],
                mode="lines",
                name="Tổng Đã Ghi Đè 0x00",
                line=dict(color="#f97316", width=1.8, dash="dash"),
                customdata=rt_df["wiped_bytes"],
                hovertemplate="<b>Đã Ghi Đè 0x00</b>: %{y:.2f} " + rt_unit + " (%{customdata:,} B)<extra></extra>",
            )
        )

        # Chấm đánh dấu sự kiện STAGE / WIPE / EXPIRE trên dòng thời gian
        earliest_ts = hist[0]["ts"]
        window_events = [ev for ev in raw_events if ev.get("ts", 0) >= earliest_ts - 2]
        if window_events:
            ev_times = []
            ev_y = []
            ev_text = []
            ev_colors = []
            ev_symbols = []

            color_map = {"STAGE": "#38bdf8", "WIPE": "#f97316", "EXPIRE": "#a855f7"}
            sym_map = {"STAGE": "circle", "WIPE": "square", "EXPIRE": "diamond"}

            for ev in window_events:
                ev_t_str = time.strftime("%H:%M:%S", time.localtime(ev["ts"]))
                # Tìm điểm Y tương ứng trong df hoặc nội suy
                matching = rt_df[rt_df["time"] == ev_t_str]
                y_val = matching["plot_active"].values[0] if not matching.empty else (ev.get("size_bytes", 0) / y_div)
                
                act = ev.get("action", "EVENT")
                ev_times.append(ev_t_str)
                ev_y.append(y_val)
                ev_colors.append(color_map.get(act, "#94a3b8"))
                ev_symbols.append(sym_map.get(act, "circle"))
                ev_text.append(f"<b>{act}</b> ({ev.get('size_bytes', 0)} B)<br>{ev.get('detail', '')}")

            fig_rt.add_trace(
                _go.Scatter(
                    x=ev_times,
                    y=ev_y,
                    mode="markers",
                    name="Sự Kiện RAM",
                    marker=dict(size=10, color=ev_colors, symbol=ev_symbols, line=dict(color="#ffffff", width=1.5)),
                    hoverinfo="text",
                    hovertext=ev_text,
                )
            )

        # Tính toán trần trục Y tự động để đường không bao giờ bị phẳng dẹt
        max_y_plot = max(rt_df["plot_active"].max(), rt_df["plot_staged"].max(), 0.1)
        y_upper = max(max_y_plot * 1.25, 10.0 if not use_kb_rt else 0.5)

        fig_rt.update_layout(
            {**_PL_LAYOUT, "height": 280},
            xaxis=dict(title="Mốc thời gian", gridcolor="rgba(148,163,184,0.12)", tickfont=dict(size=11)),
            yaxis=dict(
                title=f"Dung lượng ({rt_unit})",
                range=[0, y_upper],
                gridcolor="rgba(148,163,184,0.12)",
                zeroline=True,
            ),
        )
        st.plotly_chart(fig_rt, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"Đang hiển thị {len(hist)} mẫu gần nhất. Mẫu mới nhất lúc {hist[-1]['time']}.")

    st.write("")

    # ==========================================
    # 5. HAI BẢNG DỮ LIỆU ĐẦY ĐỦ CHUỖI & COPYABLE
    # ==========================================
    b1, b2 = st.columns(2, gap="medium")

    with b1:
        st.markdown("##### 🧾 Danh Sách Payload Đang Nằm Trên RAM")
        if entries:
            payload_rows = []
            for e in entries:
                ttl = e.get("ttl_remaining", 0)
                ttl_fmt = f"{ttl // 60:02d}:{ttl % 60:02d} ({ttl}s)"
                payload_rows.append(
                    {
                        "Mã Gói (tx_id)": e.get("tx_id", ""),
                        "Người Nhận": e.get("recipient", ""),
                        "Kích Thước": _format_bytes_human(e.get("size_bytes", 0)),
                        "TTL Đếm Ngược": ttl_fmt,
                        "Trạng Thái": "🟢 ACTIVE (Trên RAM)",
                    }
                )
            st.dataframe(
                payload_rows,
                column_config={
                    "Mã Gói (tx_id)": st.column_config.TextColumn("Mã Gói (tx_id)", help="Click đúp hoặc chọn để sao chép toàn bộ chuỗi"),
                    "Người Nhận": st.column_config.TextColumn("Người Nhận (Địa Chỉ Ví)", help="Địa chỉ ví nhận E2E"),
                    "Kích Thước": st.column_config.TextColumn("Kích Thước", width="small"),
                    "TTL Đếm Ngược": st.column_config.TextColumn("TTL Đếm Ngược (mm:ss)", width="medium"),
                    "Trạng Thái": st.column_config.TextColumn("Trạng Thái", width="medium"),
                },
                hide_index=True,
                use_container_width=True,
            )
            st.caption("Payload được giải phóng và ghi đè 0x00 ngay khi người nhận rút hoặc khi bộ đếm TTL về 00:00.")
        else:
            st.info("ℹ️ Broker hiện đang trống - không có gói tin nào lưu giữ trên RAM.")

    with b2:
        st.markdown("##### 📜 Nhật Ký Sự Kiện Ghi & Ghi Đè 0x00")
        if raw_events:
            events_reversed = list(reversed(raw_events))
            event_rows = []
            for ev in events_reversed[:40]:
                action = ev.get("action", "")
                if action == "STAGE":
                    badge = "🔵 STAGE (Ghi RAM)"
                elif action == "WIPE":
                    badge = "🟠 WIPE (Ghi đè 0x00)"
                elif action == "EXPIRE":
                    badge = "🟣 EXPIRE (Hết hạn)"
                else:
                    badge = f"⚪ {action}"

                ev_time_str = time.strftime("%H:%M:%S", time.localtime(ev.get("ts", time.time())))
                event_rows.append(
                    {
                        "Thời Gian": ev_time_str,
                        "Sự Kiện": badge,
                        "Mã Gói (tx_id)": ev.get("tx_id", ""),
                        "Dung Lượng": _format_bytes_human(ev.get("size_bytes", 0)),
                        "Chi Tiết Thao Tác": ev.get("detail", ""),
                    }
                )
            st.dataframe(
                event_rows,
                column_config={
                    "Thời Gian": st.column_config.TextColumn("Thời Gian", width="small"),
                    "Sự Kiện": st.column_config.TextColumn("Sự Kiện", width="medium"),
                    "Mã Gói (tx_id)": st.column_config.TextColumn("Mã Gói (tx_id)", help="Click đúp hoặc chọn để sao chép"),
                    "Dung Lượng": st.column_config.TextColumn("Dung Lượng", width="small"),
                    "Chi Tiết Thao Tác": st.column_config.TextColumn("Chi Tiết Thao Tác", width="large"),
                },
                hide_index=True,
                use_container_width=True,
            )
            st.caption("Minh chứng minh bạch nguyên tắc Zero-Log: Ghi nhận đầy đủ thao tác xóa sạch 0x00.")
        else:
            st.info("ℹ️ Chưa có sự kiện RAM nào được ghi nhận. Hãy thực hiện gửi tin nhắn hoặc file để quan sát.")

    if opacity_style:
        st.markdown("</div>", unsafe_allow_html=True)


def _render_admin_dashboard() -> None:
    """Dashboard giám sát Zero-Log - CHỈ gọi khi vai trò là admin."""
    _render_zero_log_dashboard_fragment()



# TAB 3: GIÁM SÁT ZERO-LOG BROKER                                    #
# ------------------------------------------------------------------ #
with tab_monitor:
    # ---- CỔNG QUYỀN ADMIN ----
    # Chỉ tài khoản vai trò "admin" mới xem được thông số Dashboard giám sát.
    # Tài khoản thường vẫn dùng bình thường các tab khác (Chat/CloakDrop/QR).
    if IS_ADMIN:
        _render_admin_dashboard()
    else:
        st.subheader("Dashboard RAM Zero-Log Broker")
        st.warning(
            "🔒 **Khu vực hạn chế.** Bạn cần đăng nhập bằng tài khoản "
            "**admin** để xem thông số Dashboard giám sát Zero-Log."
        )
        st.info(
            f"Tài khoản hiện tại: `{st.session_state.get('active_user', '?')}` "
            "(vai trò: `user`). Hãy đăng xuất rồi đăng nhập bằng tài khoản admin."
        )


# ------------------------------------------------------------------ #
# TAB 4: QUẢN LÝ KHÓA & MẠNG                                         #
# ------------------------------------------------------------------ #
with tab_keys:
    st.subheader("Quản Lý Khóa & Cấu Hình Mạng")

    # ---- PANEL CHIA SẺ: cho bạn cùng lớp quét mã QR dùng thử (nổi bật) ----
    st.markdown("##### 📱 Cho Bạn Cùng Lớp Quét Mã QR Dùng Thử")
    st.caption(
        "Mọi người kết nối chung Wi-Fi (hoặc Tailscale) rồi quét mã QR bằng camera "
        "điện thoại là vào được CloakShare ngay - không cần cài gì thêm."
    )
    _qr_col1, _qr_col2 = st.columns(2)
    with _qr_col1:
        lan_url = f"http://{LOCAL_IP}:8501"
        st.markdown(f"**Wi-Fi Nội Bộ (LAN):** `{lan_url}`")
        _b64 = _qr_image_base64(lan_url)
        if _b64:
            st.image(_b64, width=200, caption="Quét khi chung Wi-Fi")
        else:
            st.image(
                f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={lan_url}",
                width=200,
                caption="Quét khi chung Wi-Fi",
            )
    with _qr_col2:
        if TAILSCALE_IP:
            ts_url = f"http://{TAILSCALE_IP}:8501"
            st.markdown(f"**Tailscale (Từ xa / 4G):** `{ts_url}`")
            _b64 = _qr_image_base64(ts_url)
            if _b64:
                st.image(_b64, width=200, caption="Quét từ bất kỳ đâu")
            else:
                st.image(
                    f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={ts_url}",
                    width=200,
                    caption="Quét từ bất kỳ đâu",
                )
        else:
            st.info("Chưa phát hiện IP Tailscale. Bật Tailscale để quét mã từ xa.")
    st.divider()

    k_c1, k_c2 = st.columns(2)
    with k_c1:
        st.markdown("##### Ví Web3 Hiện Tại")
        st.text_input("Địa chỉ ví Ethereum:", value=my_address, disabled=True)
        show_key = st.checkbox("Hiển thị Private Key ví", value=False)
        if show_key:
            st.text_input("Private Key:", value=my_pk, disabled=True)

        if st.button("Đăng Ký Lại Khóa Lên dPKI", type="primary", use_container_width=True):
            with st.spinner("Đang đăng ký..."):
                try:
                    tx = dpki_client.register_public_key(my_pk, my_pub_pem)
                    st.success(f"Đã đăng ký thành công! Ref: {tx}")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    with k_c2:
        st.markdown("##### RSA 2048-bit Public Key")
        st.text_area("Public Key PEM:", value=my_pub_pem, height=130)

    st.divider()
    st.markdown("##### Kết Nối Đa Thiết Bị (Mobile / Laptop / LAN / Tailscale)")
    st.caption("Quét mã QR bằng điện thoại (Android/iOS) hoặc mở đường dẫn từ máy khác để truy cập CloakShare:")
    
    net_col1, net_col2 = st.columns(2)
    with net_col1:
        if TAILSCALE_IP:
            tailscale_url = f"http://{TAILSCALE_IP}:8501"
            st.markdown(f"**Mạng Tailscale (Từ xa / 4G / Mọi nơi):**")
            st.code(tailscale_url, language="text")
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={tailscale_url}", caption="Quét bằng camera điện thoại")
        else:
            st.info("Chưa phát hiện IP Tailscale. Bật Tailscale để kết nối từ xa mọi nơi.")
            
    with net_col2:
        lan_url = f"http://{LOCAL_IP}:8501"
        st.markdown(f"**Mạng Wi-Fi Nội Bộ (LAN):**")
        st.code(lan_url, language="text")
        st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={lan_url}", caption="Quét khi chung mạng Wi-Fi")

    custom_broker = st.text_input("Địa chỉ Broker URL kết nối:", value=st.session_state.broker_url)
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("Lưu Thay Đổi Broker URL", use_container_width=True):
            st.session_state.broker_url = custom_broker.strip()
            st.success("Đã cập nhật Broker URL!")
            st.rerun()
    with c_btn2:
        if st.button("Kiểm Tra Kết Nối Broker", use_container_width=True):
            try:
                r = requests.get(f"{custom_broker.strip()}/health", timeout=3)
                if r.status_code == 200:
                    st.success(f"Kết nối Broker thành công ({r.json().get('status', 'ok')}).")
                else:
                    st.warning(f"Broker phản hồi mã HTTP {r.status_code}")
            except Exception as ex:
                st.error(f"Không thể kết nối tới Broker: {ex}")
