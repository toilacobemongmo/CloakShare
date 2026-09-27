import os
import socket
import base64
import json
import time
import uuid
from pathlib import Path

import requests
import streamlit as st
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from eth_account import Account
from eth_account.messages import encode_defunct

from engine.cli_adapter import CLIAdapter
from engine.dpki_client import DPKIClient
from engine.rsa_envelope import RSAEnvelope
from engine.signer import IntegritySigner
from engine.wallet_auth import Web3Auth
from engine.wrappers.aes_wrapper import AESWrapper

st.set_page_config(
    page_title="CloakShare | Web3 Secure Messenger",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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
DEFAULT_CONTRACT = os.getenv("CONTRACT_ADDRESS", "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0")

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
        max-width: 1000px !important;
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
        padding: 12px;
        text-align: center;
    }
    .metric-num {
        font-size: 1.5rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-sub {
        font-size: 0.75rem;
        color: #94a3b8;
    }

    /* Chống mờ giao diện khi Streamlit cập nhật */
    [data-stale="true"] {
        opacity: 1 !important;
        filter: none !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# QUẢN LÝ TÀI KHOẢN & DANH BẠ (BẢO TOÀN TRẠNG THÁI)
# ==========================================
ACCOUNTS_FILE = Path.home() / ".cloakshare" / "accounts.json"

def load_persisted_accounts() -> dict[str, str]:
    defaults = {
        "Alice (Seller)": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        "Bob (Buyer)": "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    }
    try:
        if ACCOUNTS_FILE.exists():
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    defaults.update(data)
    except Exception:
        pass
    return defaults

def save_persisted_account(name: str, pk: str):
    try:
        ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        accs = load_persisted_accounts()
        accs[name] = pk
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accs, f, indent=2)
    except Exception:
        pass

if "accounts" not in st.session_state:
    st.session_state.accounts = load_persisted_accounts()

# Đảm bảo active_user luôn hợp lệ (chống văng KeyError khi tải lại)
if "active_user" not in st.session_state or st.session_state.active_user not in st.session_state.accounts:
    st.session_state.active_user = list(st.session_state.accounts.keys())[0]

if "main_acc_select" in st.session_state and st.session_state.main_acc_select not in st.session_state.accounts:
    st.session_state.main_acc_select = st.session_state.active_user

if "contacts" not in st.session_state:
    st.session_state.contacts = {
        "Alice (Seller)": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "Bob (Buyer)": "0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
        "Mobile (0x84bE)": "0x84bE462356eD3626C242D2aa21f7D257bE926E10",
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


def get_or_create_keys(wallet_address: str) -> tuple[str, str]:
    key_store_id = f"rsa_{wallet_address.lower()}"
    if key_store_id not in st.session_state:
        priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        pub_pem = (
            priv_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )
        st.session_state[key_store_id] = (priv_pem, pub_pem)
    return st.session_state[key_store_id]


def ensure_dpki_registered(wallet_pk: str, pub_pem: str):
    try:
        dpki = DPKIClient(
            contract_address=DEFAULT_CONTRACT,
            rpc_url=DEFAULT_RPC,
            broker_url=st.session_state.broker_url,
        )
        dpki.register_public_key(wallet_pk, pub_pem)
    except Exception:
        pass


if "dpki_initialized" not in st.session_state:
    st.session_state.dpki_initialized = set()

for acc_name, acc_pk in st.session_state.accounts.items():
    if acc_name not in st.session_state.dpki_initialized:
        acc_obj = Account.from_key(acc_pk)
        _, p_pem = get_or_create_keys(acc_obj.address)
        ensure_dpki_registered(acc_pk, p_pem)
        st.session_state.dpki_initialized.add(acc_name)

my_pk = st.session_state.accounts.get(st.session_state.active_user, list(st.session_state.accounts.values())[0])
my_account = Account.from_key(my_pk)
my_address = my_account.address
my_priv_pem, my_pub_pem = get_or_create_keys(my_address)
dpki_client = DPKIClient(
    contract_address=DEFAULT_CONTRACT,
    rpc_url=DEFAULT_RPC,
    broker_url=st.session_state.broker_url,
)
ensure_dpki_registered(my_pk, my_pub_pem)

# Tự động đồng bộ các đối tác từ Broker dPKI vào danh bạ
try:
    _d_res = requests.get(f"{st.session_state.broker_url}/api/v1/dpki/list", timeout=1)
    if _d_res.status_code == 200:
        for _r_addr in _d_res.json().get("addresses", []):
            if _r_addr.lower() not in [c.lower() for c in st.session_state.contacts.values()]:
                _label = f"📱 Đối tác ({_r_addr[:6]}...{_r_addr[-4:]})"
                st.session_state.contacts[_label] = _r_addr
except Exception:
    pass


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
            for item in res.json():
                tx_id = item["tx_id"]
                if tx_id in st.session_state.processed_tx_ids:
                    continue

                try:
                    iv = bytes.fromhex(item["iv"])
                    wrapped_key = bytes.fromhex(item["wrapped_key"])
                    ciphertext = bytes.fromhex(item["ciphertext"])
                    sig_hex = item.get("signature", "")
                    sig_bytes = bytes.fromhex(sig_hex) if sig_hex else b""

                    aes_key = RSAEnvelope.unwrap_key(wrapped_key, my_priv_pem)
                    decrypted_raw = CLIAdapter.decrypt_bytes(ciphertext, aes_key, iv)
                    parsed = json.loads(decrypted_raw.decode("utf-8"))

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
                    })
                    st.session_state.processed_tx_ids.add(tx_id)
                except Exception:
                    pass
    except Exception:
        pass


poll_inbox()


# ==========================================
# THANH ĐIỀU KHIỂN DANH TÍNH (TRỰC QUAN TRÊN MÀN HÌNH)
# ==========================================
net_label = f"🦎 Tailscale: {TAILSCALE_IP}" if TAILSCALE_IP else f"🏠 LAN: {LOCAL_IP}"

st.markdown(f"""
<div class="user-card">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div class="user-header-title">
            🛡️ CloakShare <span style="font-size: 0.85rem; color: #94a3b8; font-weight: 500;">Messenger</span>
        </div>
        <div class="user-badge-net">{net_label}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# HÀNG CHUYỂN TÀI KHOẢN VÀ TẠO TÀI KHOẢN TRỰC TIẾP
top_col1, top_col2 = st.columns([2.5, 1])

with top_col1:
    account_names = list(st.session_state.accounts.keys())
    cur_idx = account_names.index(st.session_state.active_user) if st.session_state.active_user in account_names else 0
    selected_acc = st.selectbox(
        "👤 Đang dùng tài khoản:",
        account_names,
        index=cur_idx,
        key="main_acc_select",
        help="Chọn để đổi sang tài khoản khác ngay lập tức",
    )
    if selected_acc != st.session_state.active_user:
        st.session_state.active_user = selected_acc
        st.rerun()

with top_col2:
    st.write("") # Căn chỉnh khoảng trắng
    st.write("")
    with st.popover("➕ Tạo ví mới", use_container_width=True):
        st.subheader("✨ Tạo Tài Khoản Web3 Mới")
        new_name = st.text_input("Tên tài khoản:", placeholder="VD: Bob, Charlie...", key="new_acc_name_pop")
        if st.button("🚀 Tạo ngay", type="primary", use_container_width=True):
            if new_name.strip() and new_name not in st.session_state.accounts:
                w = Account.create()
                save_persisted_account(new_name, w.key.hex())
                st.session_state.accounts[new_name] = w.key.hex()
                st.session_state.contacts[new_name] = w.address
                st.session_state.active_user = new_name
                st.success(f"Đã tạo & kích hoạt ví '{new_name}'!")
                st.rerun()
            else:
                st.warning("Tên đã tồn tại hoặc không hợp lệ.")

st.caption(f"Địa chỉ ví của bạn: `{my_address}`")


# ==========================================
# CÁC TAB CHÍNH (DEFAULT: CHAT TAB)
# ==========================================
tab_chat, tab_drop, tab_monitor, tab_keys = st.tabs([
    "💬 Trò Chuyện (Chat)",
    "📦 CloakDrop (Gửi File)",
    "📊 Giám Sát Zero-Log",
    "🔑 Quản Lý Khóa & Mạng",
])


# ------------------------------------------------------------------ #
# TAB 1: TRÒ CHUYỆN (CHAT)                                           #
# ------------------------------------------------------------------ #
with tab_chat:
    available_peers = [name for name, addr in st.session_state.contacts.items() if addr.lower() != my_address.lower()]
    
    chat_top_c1, chat_top_c2, chat_top_c3 = st.columns([2, 1, 1])
    with chat_top_c1:
        if not available_peers:
            st.info("Chưa có liên hệ khác. Bấm '➕ Thêm ví' để nhập địa chỉ ví đối tác!")
            active_peer_name = ""
            active_peer_addr = ""
        else:
            p_idx = available_peers.index(st.session_state.selected_peer) if st.session_state.selected_peer in available_peers else 0
            active_peer_name = st.selectbox(
                "💬 Chat với đối tác:",
                available_peers,
                index=p_idx,
                key="select_chat_peer",
            )
            st.session_state.selected_peer = active_peer_name
            active_peer_addr = st.session_state.contacts.get(active_peer_name, "")
    
    with chat_top_c2:
        st.write("")
        st.write("")
        with st.popover("➕ Thêm ví", use_container_width=True):
            st.markdown("##### ➕ Nhập địa chỉ ví đối tác")
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
        if st.button("🔄 Nhận tin", use_container_width=True, help="Đồng bộ tin nhắn mới ngay lập tức"):
            poll_inbox()
            st.rerun()

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
                '🔒 Kênh bảo mật E2E đã sẵn sàng. Chưa có tin nhắn nào!<br>Hãy gửi lời chào đầu tiên.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            for m, side in conversation:
                wrap_cls = "bubble-wrapper-right" if side == "right" else "bubble-wrapper-left"
                b_cls = "chat-bubble-right" if side == "right" else "chat-bubble-left"
                sender_label = "Bạn" if side == "right" else m.get("from_name", active_peer_name)

                sig_badge = (
                    '<span class="badge-tag badge-ok">🛡️ RSA-PSS Chuẩn</span>'
                    if m.get("verified")
                    else '<span class="badge-tag badge-enc">🔒 AES-128</span>'
                )

                bubble_html = f"""
                    <div class="{wrap_cls}">
                        <div class="{b_cls}">
                            <div class="bubble-sender">{sender_label}</div>
                            <div class="bubble-text">{m['text']}</div>
                            <div class="bubble-badges">
                                {sig_badge}
                                <span class="badge-tag badge-enc">🔑 RSA-OAEP</span>
                            </div>
                            <div class="chat-time">{m['time']}</div>
                        </div>
                    </div>
                """
                st.markdown(bubble_html, unsafe_allow_html=True)

                if m.get("is_file") and m.get("file_data"):
                    st.download_button(
                        label=f"💾 Tải file đính kèm: {m['filename']}",
                        data=m["file_data"],
                        file_name=m["filename"],
                        key=f"dl_msg_{m['id']}",
                        use_container_width=True,
                    )

    # Form nhập tin nhắn
    with st.form("chat_send_form", clear_on_submit=True):
        f_c1, f_c2 = st.columns([3.5, 1])
        with f_c1:
            chat_input = st.text_input("Nội dung tin nhắn:", placeholder="Nhập tin nhắn bảo mật...", label_visibility="collapsed")
            attached_file = st.file_uploader("Đính kèm file", type=None, label_visibility="collapsed")
        with f_c2:
            st.write("")
            send_btn = st.form_submit_button("🚀 Gửi", use_container_width=True, type="primary")

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
                        "text": chat_input if not is_file else (f"📎 {chat_input}" if chat_input else f"📎 Tệp: {f_name}"),
                        "is_file": is_file,
                        "filename": f_name,
                        "file_b64": base64.b64encode(f_bytes).decode("utf-8") if is_file else "",
                    }
                    raw_bytes = json.dumps(payload_content).encode("utf-8")

                    # Mã hóa 100% RAM
                    aes_key, iv, ciphertext = CLIAdapter.encrypt_bytes(raw_bytes)
                    wrapped_key = RSAEnvelope.wrap_key(aes_key, peer_pub)
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
                        st.toast("✅ Đã gửi thành công!")
                        st.rerun()
                    else:
                        st.error(f"Lỗi Broker: {res.text}")
                except Exception as err:
                    st.error(f"Thao tác thất bại: {err}")


# ------------------------------------------------------------------ #
# TAB 2: CLOAKDROP (GỬI FILE ĐỘC LẬP & TỰ HỦY)                       #
# ------------------------------------------------------------------ #
with tab_drop:
    st.subheader("📦 CloakDrop Vault - Chia Sẻ File Tự Hủy")
    st.caption("Mã hóa file độc lập, bọc khóa và chia sẻ mã Ticket ID để người nhận tự rút và giải mã.")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("##### 📤 Gửi File Mới")
        with st.form("form_drop_send"):
            d_recipient = st.selectbox(
                "Gửi tới đối tác:",
                [name for name in st.session_state.contacts.keys() if st.session_state.contacts[name].lower() != my_address.lower()],
            )
            d_file = st.file_uploader("Chọn tệp tin cần bảo vệ:")
            d_ttl = st.selectbox("Thời gian tự hủy (TTL):", [60, 300, 1800, 3600], index=1, format_func=lambda s: f"{s} giây" if s < 60 else f"{s//60} phút")
            d_burn = st.checkbox("🔥 Xóa ngay sau khi tải (Burn-After-Read)", value=True)
            d_submit = st.form_submit_button("🔒 Mã Hóa & Tải Lên RAM", type="primary", use_container_width=True)

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
                    wk_b = RSAEnvelope.wrap_key(k, r_pub)
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
                        st.success("✅ Đã mã hóa và đưa lên RAM Broker!")
                    else:
                        st.error(f"Lỗi: {res.text}")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

        if st.session_state.last_drop_ticket:
            st.info(f"🔑 **Mã Ticket gửi cho đối tác:** `{st.session_state.last_drop_ticket}`")

    with col_d2:
        st.markdown("##### 📥 Rút & Giải Mã File")
        with st.form("form_drop_claim"):
            claim_ticket = st.text_input("Nhập mã Ticket ID:", placeholder="drop-...")
            claim_burn = st.checkbox("Xóa khỏi RAM sau khi tải", value=True)
            claim_btn = st.form_submit_button("🔓 Xác Thực Ví & Nhận File", type="primary", use_container_width=True)

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

                        aes_k = RSAEnvelope.unwrap_key(wk_b, my_priv_pem)
                        plain_b = CLIAdapter.decrypt_bytes(ct_b, aes_k, iv_b)
                        f_info = json.loads(plain_b.decode("utf-8"))

                        fn = f_info.get("filename", "file.bin")
                        fb = base64.b64decode(f_info.get("file_b64", ""))
                        st.success(f"🎉 Đã giải mã thành công: **{fn}** ({len(fb)} bytes)!")
                        st.download_button(f"💾 Tải về máy: {fn}", data=fb, file_name=fn, use_container_width=True)
                    else:
                        st.error(f"Lỗi rút file ({res.status_code}): {res.text}")
                except Exception as e:
                    st.error(f"Lỗi: {e}")


# ------------------------------------------------------------------ #
# TAB 3: GIÁM SÁT ZERO-LOG BROKER                                    #
# ------------------------------------------------------------------ #
with tab_monitor:
    st.subheader("📊 Giám Sát Zero-Log Broker")
    st.caption("Kiểm chứng thời gian thực nguyên tắc 0 Disk Writes và dung lượng bộ nhớ RAM.")

    stats_data = {}
    broker_ok = False
    try:
        r = requests.get(f"{st.session_state.broker_url}/api/v1/stats", timeout=2)
        if r.status_code == 200:
            stats_data = r.json()
            broker_ok = True
    except Exception:
        broker_ok = False

    if broker_ok:
        st.success(f"🟢 Broker kết nối tốt tại `{st.session_state.broker_url}`")
    else:
        st.error(f"🔴 Không thể kết nối Broker tại `{st.session_state.broker_url}`")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-box"><div class="metric-num">{stats_data.get("active_payloads", 0)}</div><div class="metric-sub">Payloads Trên RAM</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-box"><div class="metric-num">{stats_data.get("total_staged", 0)}</div><div class="metric-sub">Tổng Đã Stage</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-box"><div class="metric-num">{stats_data.get("total_retrieved", 0)}</div><div class="metric-sub">Tổng Lượt Rút</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-box"><div class="metric-num" style="color: #10b981;">{stats_data.get("disk_writes", 0)}</div><div class="metric-sub">Disk Writes (Luôn 0)</div></div>', unsafe_allow_html=True)

    st.write("")
    ram_b = stats_data.get("approx_ram_bytes", 0)
    st.info(f"⚡ RAM cấp phát cho payload: **{ram_b} bytes ({ram_b / 1024:.2f} KB)** | Đã tự hủy hết hạn TTL: **{stats_data.get('total_purged_expired', 0)}**")


# ------------------------------------------------------------------ #
# TAB 4: QUẢN LÝ KHÓA & MẠNG                                         #
# ------------------------------------------------------------------ #
with tab_keys:
    st.subheader("🔑 Quản Lý Khóa & Cấu Hình Mạng")

    k_c1, k_c2 = st.columns(2)
    with k_c1:
        st.markdown("##### 🌐 Ví Web3 Hiện Tại")
        st.text_input("Địa chỉ ví Ethereum:", value=my_address, disabled=True)
        show_key = st.checkbox("Hiển thị Private Key ví", value=False)
        if show_key:
            st.text_input("Private Key:", value=my_pk, disabled=True)

        if st.button("⛓️ Đăng Ký Lại Khóa Lên dPKI", type="primary", use_container_width=True):
            with st.spinner("Đang đăng ký..."):
                try:
                    tx = dpki_client.register_public_key(my_pk, my_pub_pem)
                    st.success(f"Đã đăng ký thành công! Ref: {tx}")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    with k_c2:
        st.markdown("##### 🔐 RSA 2048-bit Public Key")
        st.text_area("Public Key PEM:", value=my_pub_pem, height=130)

    st.divider()
    st.markdown("##### 🌐 Cấu Hình Kết Nối Hai Máy (Tailscale / LAN)")
    if TAILSCALE_IP:
        st.success(f"🦎 **IP Tailscale của máy này:** `{TAILSCALE_IP}` (Dùng IP này để kết nối từ xa mọi nơi)")
    st.write(f"🏠 **IP LAN Wi-Fi:** `{LOCAL_IP}`")
    
    custom_broker = st.text_input("Địa chỉ Broker URL kết nối:", value=st.session_state.broker_url)
    if st.button("Lưu Thay Đổi Broker URL", use_container_width=True):
        st.session_state.broker_url = custom_broker.strip()
        st.success("Đã cập nhật Broker URL!")
        st.rerun()