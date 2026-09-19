from __future__ import annotations

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
from web3 import Web3

from engine.cli_adapter import CLIAdapter
from engine.dpki_client import DPKIClient
from engine.rsa_envelope import RSAEnvelope
from engine.wallet_auth import Web3Auth

st.set_page_config(page_title="CloakShare Messenger", page_icon="💬", layout="wide")

DEFAULT_RPC = "http://127.0.0.1:8545"
DEFAULT_CONTRACT = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"
BROKER_URL = "http://127.0.0.1:8000"

st.markdown("""
<style>
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
        background-color: #3e4042;
        color: #ffffff;
        padding: 10px 16px;
        border-radius: 18px 18px 18px 4px;
        max-width: 65%;
        word-break: break-word;
    }
    .chat-bubble-right {
        background-color: #0084ff;
        color: #ffffff;
        padding: 10px 16px;
        border-radius: 18px 18px 4px 18px;
        max-width: 65%;
        word-break: break-word;
    }
    .chat-time {
        font-size: 0.72rem;
        opacity: 0.7;
        margin-top: 4px;
        text-align: right;
    }
    [data-testid="stSidebar"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

if "accounts" not in st.session_state:
    st.session_state.accounts = {
        "Alice": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        "Bob": "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    }

if "active_user" not in st.session_state:
    st.session_state.active_user = "Alice"

if "contacts" not in st.session_state:
    st.session_state.contacts = {
        "Alice": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "Bob": "0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
    }

if "selected_peer" not in st.session_state:
    st.session_state.selected_peer = "Bob"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "processed_tx_ids" not in st.session_state:
    st.session_state.processed_tx_ids = set()


def to_checksum(addr: str) -> str:
    try:
        return Web3.to_checksum_address(addr.strip())
    except Exception:
        return addr.strip()


def get_or_create_keys(wallet_address: str) -> tuple[str, str]:
    key_store_id = f"rsa_{to_checksum(wallet_address).lower()}"
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


def fund_and_register_dpki(wallet_pk: str, pub_pem: str) -> bool:
    try:
        account = Account.from_key(wallet_pk)
        c_addr = to_checksum(account.address)

        # 1. Nạp 10 ETH gas ảo qua Anvil
        try:
            requests.post(
                DEFAULT_RPC,
                json={
                    "jsonrpc": "2.0",
                    "method": "anvil_setBalance",
                    "params": [c_addr, hex(10**19)],
                    "id": 1,
                },
                timeout=1,
            )
        except Exception:
            pass

        # 2. Kiểm tra xem contract đã có khóa chưa
        dpki = DPKIClient(contract_address=to_checksum(DEFAULT_CONTRACT), rpc_url=DEFAULT_RPC)
        has_key = False
        try:
            existing = dpki.get_public_key(c_addr)
            if existing and len(existing.strip()) > 0:
                has_key = True
        except Exception:
            has_key = False

        # 3. Đăng ký nếu chưa có
        if not has_key:
            dpki.register_public_key(wallet_pk, pub_pem)
        return True
    except Exception:
        return False


# Đồng bộ tất cả tài khoản
for acc_pk in list(st.session_state.accounts.values()):
    acc_obj = Account.from_key(acc_pk)
    _, p_pem = get_or_create_keys(acc_obj.address)
    fund_and_register_dpki(acc_pk, p_pem)

my_pk = st.session_state.accounts[st.session_state.active_user]
my_account = Account.from_key(my_pk)
my_address = to_checksum(my_account.address)
my_priv_pem, my_pub_pem = get_or_create_keys(my_address)


# ==========================================
# HEADER & POPOVER CÀI ĐẶT
# ==========================================
head_col1, head_col2 = st.columns([3, 1])
with head_col1:
    st.title("💬 CloakShare Messenger")
    st.caption(f"Tài khoản hiện tại: **{st.session_state.active_user}** (`{my_address}`)")

with head_col2:
    st.markdown("<div style='text-align: right;'>", unsafe_allow_html=True)
    with st.popover("⚙️ Cài đặt & Tài khoản", use_container_width=True):
        st.subheader("👤 Chuyển tài khoản")
        account_names = list(st.session_state.accounts.keys())
        cur_idx = account_names.index(st.session_state.active_user) if st.session_state.active_user in account_names else 0
        selected_acc = st.selectbox("Chọn tài khoản:", account_names, index=cur_idx, key="pop_acc_select")

        if selected_acc != st.session_state.active_user:
            st.session_state.active_user = selected_acc
            st.rerun()

        st.divider()
        st.subheader("✨ Tạo tài khoản mới")
        new_user_name = st.text_input("Tên tài khoản mới:", placeholder="VD: Charlie...", key="pop_new_user")
        if st.button("🚀 Tạo ví ngay", type="primary", use_container_width=True):
            if new_user_name.strip() and new_user_name not in st.session_state.accounts:
                with st.spinner("Đang tạo ví và đăng ký dPKI..."):
                    new_wallet = Account.create()
                    pk_hex = new_wallet._private_key.hex()
                    new_addr = to_checksum(new_wallet.address)

                    _, new_pub = get_or_create_keys(new_addr)
                    fund_and_register_dpki(pk_hex, new_pub)

                    st.session_state.accounts[new_user_name] = pk_hex
                    st.session_state.contacts[new_user_name] = new_addr
                    st.session_state.active_user = new_user_name
                    st.success(f"Đã tạo ví thành công cho {new_user_name}!")
                    st.rerun()
            else:
                st.warning("Tên không hợp lệ hoặc đã tồn tại.")

        st.divider()
        st.subheader("➕ Thêm liên hệ")
        contact_name = st.text_input("Tên gợi nhớ:", key="pop_contact_name")
        contact_addr = st.text_input("Địa chỉ ví (0x...):", key="pop_contact_addr")
        if st.button("Lưu liên hệ", use_container_width=True):
            if contact_name and contact_addr.startswith("0x"):
                c_addr = to_checksum(contact_addr)
                st.session_state.contacts[contact_name] = c_addr
                st.success("Đã thêm liên hệ!")
                st.rerun()
            else:
                st.warning("Địa chỉ không hợp lệ.")
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()


# ==========================================
# INBOX POLLING
# ==========================================
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
        res = requests.get(f"{BROKER_URL}/api/v1/inbox", headers=req_headers, timeout=2)
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

                    aes_key = RSAEnvelope.unwrap_key(wrapped_key, my_priv_pem)

                    t_enc = Path(f"dec_{tx_id}.enc")
                    t_dec = Path(f"dec_{tx_id}.dec")
                    t_enc.write_bytes(ciphertext)
                    CLIAdapter.decrypt_file(str(t_enc), str(t_dec), aes_key, iv)
                    decrypted_raw = t_dec.read_bytes()
                    t_enc.unlink(missing_ok=True)
                    t_dec.unlink(missing_ok=True)

                    parsed = json.loads(decrypted_raw.decode("utf-8"))
                    sender_addr = parsed.get("sender", "Unknown")
                    content_text = parsed.get("text", "")
                    is_file = parsed.get("is_file", False)
                    file_name = parsed.get("filename", "")
                    file_data = base64.b64decode(parsed.get("file_b64", "")) if is_file else None

                    st.session_state.messages.append({
                        "id": tx_id,
                        "from": to_checksum(sender_addr),
                        "to": my_address,
                        "text": content_text,
                        "is_file": is_file,
                        "file_data": file_data,
                        "filename": file_name,
                        "time": time.strftime("%H:%M"),
                    })
                except Exception:
                    pass
    except Exception:
        pass

poll_inbox()


# ==========================================
# KHUNG GIAO DIỆN CHAT 2 CỘT
# ==========================================
col_list, col_chat = st.columns([1, 2.5])

with col_list:
    st.subheader("💬 Đoạn chat")
    available_peers = [
        name for name, addr in st.session_state.contacts.items()
        if to_checksum(addr) != my_address
    ]

    if not available_peers:
        st.info("Chưa có liên hệ nào khác.")
    else:
        for peer_name in available_peers:
            is_active = (st.session_state.selected_peer == peer_name)
            btn_label = f"🟢 {peer_name}" if is_active else f"👤 {peer_name}"
            if st.button(btn_label, key=f"btn_peer_{peer_name}", use_container_width=True):
                st.session_state.selected_peer = peer_name
                st.rerun()

    if st.button("🔄 Làm mới tin nhắn", use_container_width=True):
        st.rerun()

with col_chat:
    active_peer_name = st.session_state.selected_peer
    active_peer_addr = to_checksum(st.session_state.contacts.get(active_peer_name, ""))

    st.subheader(f"💬 {active_peer_name}")
    st.caption(f"Địa chỉ ví: `{active_peer_addr}`")

    conversation = []
    for msg in st.session_state.messages:
        from_me = (msg["from"].lower() == my_address.lower() and msg["to"].lower() == active_peer_addr.lower())
        from_peer = (msg["from"].lower() == active_peer_addr.lower() and msg["to"].lower() == my_address.lower())
        if from_me or from_peer:
            conversation.append((msg, "right" if from_me else "left"))

    with st.container(height=480):
        if not conversation:
            st.markdown('<div style="color: #888; text-align: center; margin-top: 190px;">Chưa có tin nhắn nào. Hãy gửi lời chào đầu tiên!</div>', unsafe_allow_html=True)
        else:
            for m, side in conversation:
                wrap_cls = "bubble-wrapper-right" if side == "right" else "bubble-wrapper-left"
                b_cls = "chat-bubble-right" if side == "right" else "chat-bubble-left"
                txt = m["text"]

                bubble_html = f'''
                    <div class="{wrap_cls}">
                        <div class="{b_cls}">
                            <div>{txt}</div>
                            <div class="chat-time">{m["time"]}</div>
                        </div>
                    </div>
                '''
                st.markdown(bubble_html, unsafe_allow_html=True)

                if m.get("is_file") and m.get("file_data"):
                    btn_col1, btn_col2 = st.columns([1, 4]) if side == "left" else st.columns([4, 1])
                    target_col = btn_col1 if side == "left" else btn_col2
                    with target_col:
                        st.download_button(
                            label=f"💾 Tải về: {m['filename']}",
                            data=m["file_data"],
                            file_name=m["filename"],
                            key=f"dl_{m['id']}",
                        )

    with st.form("send_form", clear_on_submit=True):
        send_col1, send_col2 = st.columns([4, 1])
        with send_col1:
            msg_input = st.text_input("Nhập tin nhắn...", placeholder="Nhập tin nhắn và nhấn Gửi...", label_visibility="collapsed")
            attached_file = st.file_uploader("Upload", type=None, label_visibility="collapsed")
        with send_col2:
            submit_btn = st.form_submit_button("🚀 Gửi", use_container_width=True, type="primary")

    if submit_btn and active_peer_addr:
        if not msg_input and not attached_file:
            st.warning("Vui lòng nhập nội dung hoặc đính kèm tệp.")
        else:
            with st.spinner("Đang tra cứu khóa dPKI và mã hóa E2E..."):
                peer_pub_key = None
                try:
                    dpki = DPKIClient(contract_address=to_checksum(DEFAULT_CONTRACT), rpc_url=DEFAULT_RPC)
                    peer_pub_key = dpki.get_public_key(active_peer_addr)
                except Exception as err:
                    # Nếu contract revert do chưa tìm thấy khóa, thử tự động đăng ký nếu ví đó nằm trong session
                    target_pk = None
                    for name, pk in st.session_state.accounts.items():
                        if to_checksum(Account.from_key(pk).address) == active_peer_addr:
                            target_pk = pk
                            break
                    if target_pk:
                        _, t_pub = get_or_create_keys(active_peer_addr)
                        if fund_and_register_dpki(target_pk, t_pub):
                            peer_pub_key = t_pub

                if not peer_pub_key or len(peer_pub_key.strip()) == 0:
                    st.error(f"Không thể lấy Public Key của ví {active_peer_addr}. Hãy chắc chắn đối phương đã đăng ký khóa lên dPKI Smart Contract.")
                else:
                    try:
                        tx_id = str(uuid.uuid4())
                        is_file = attached_file is not None
                        file_name = attached_file.name if is_file else ""
                        file_bytes = attached_file.getvalue() if is_file else b""

                        payload_content = {
                            "sender": my_address,
                            "sender_name": st.session_state.active_user,
                            "text": msg_input if not is_file else (f"📎 {msg_input}" if msg_input else f"📎 Tệp: {file_name}"),
                            "is_file": is_file,
                            "filename": file_name,
                            "file_b64": base64.b64encode(file_bytes).decode("utf-8") if is_file else "",
                        }

                        raw_bytes = json.dumps(payload_content).encode("utf-8")

                        t_in = Path(f"snd_{tx_id}.in")
                        t_enc = Path(f"snd_{tx_id}.enc")
                        t_in.write_bytes(raw_bytes)
                        aes_key, iv = CLIAdapter.encrypt_file(str(t_in), str(t_enc))
                        wrapped_key = RSAEnvelope.wrap_key(aes_key, peer_pub_key)
                        ciphertext = t_enc.read_bytes()
                        t_in.unlink(missing_ok=True)
                        t_enc.unlink(missing_ok=True)

                        body = {
                            "tx_id": tx_id,
                            "recipient": active_peer_addr,
                            "iv": iv.hex(),
                            "wrapped_key": wrapped_key.hex(),
                            "ciphertext": ciphertext.hex(),
                            "signature": "",
                            "ttl_seconds": 300,
                        }

                        res = requests.post(f"{BROKER_URL}/api/v1/stage", json=body)
                        if res.status_code == 201:
                            st.session_state.messages.append({
                                "id": tx_id,
                                "from": my_address,
                                "to": active_peer_addr,
                                "text": payload_content["text"],
                                "is_file": is_file,
                                "file_data": file_bytes if is_file else None,
                                "filename": file_name,
                                "time": time.strftime("%H:%M"),
                            })
                            st.rerun()
                        else:
                            st.error(f"Lỗi Broker: {res.text}")
                    except Exception as err:
                        st.error(f"Thao tác thất bại: {err}")