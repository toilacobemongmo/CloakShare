"""
engine/cli.py

Giao diện dòng lệnh (CLI) cho CloakShare:
- keygen   : Tạo cặp khóa RSA-2048 (private.pem / public.pem)
- register : Đăng ký Public Key lên dPKI (Blockchain hoặc Local Fallback)
- send     : Mã hóa AES-128 (C Core), bọc khóa RSA-OAEP, ký RSA-PSS và stage lên RAM Broker
- receive  : Rút payload với chữ ký ví Web3 (SIWE), kiểm tra RSA-PSS, giải mã file trong RAM
"""

import argparse
import os
import sys
import uuid
import time
import getpass
from pathlib import Path

# Đảm bảo UTF-8 stream trên Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import requests
from eth_account import Account
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from engine.cli_adapter import CLIAdapter
from engine.dpki_client import DPKIClient
from engine.rsa_envelope import RSAEnvelope
from engine.signer import IntegritySigner
from engine.wallet_auth import Web3Auth

DEFAULT_CONTRACT = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"
DEFAULT_RPC = "http://127.0.0.1:8545"
DEFAULT_BROKER = "http://127.0.0.1:8000"


def _generate_rsa_keys() -> tuple[bytes, bytes]:
    """Tạo cặp khóa RSA 2048-bit."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_priv = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem_priv, pem_pub


def main():
    parser = argparse.ArgumentParser(description="CloakShare CLI - Zero-Log Hybrid Secure Messaging & File Sharing")
    subparsers = parser.add_subparsers(dest="command", help="Các lệnh hỗ trợ")

    # 1. Keygen
    parser_keygen = subparsers.add_parser("keygen", help="Tạo cặp khóa RSA 2048-bit")
    parser_keygen.add_argument("--out", default="my_keys", help="Thư mục lưu khóa (mặc định: my_keys)")

    # 2. Register
    parser_reg = subparsers.add_parser("register", help="Đăng ký Public Key lên dPKI Smart Contract")
    parser_reg.add_argument("--pub", required=True, help="Đường dẫn file Public Key (.pem)")
    parser_reg.add_argument("--private-key", default=None, help="Private Key ví Ethereum (hoặc nhập qua prompt/env CLOAKSHARE_PRIVATE_KEY)")
    parser_reg.add_argument("--contract", default=DEFAULT_CONTRACT, help="Địa chỉ Smart Contract")
    parser_reg.add_argument("--rpc", default=DEFAULT_RPC, help="URL RPC Blockchain (mặc định: http://127.0.0.1:8545)")

    # 3. Send
    parser_send = subparsers.add_parser("send", help="Mã hóa và gửi file lên RAM Broker")
    parser_send.add_argument("--file", required=True, help="Đường dẫn file cần gửi")
    parser_send.add_argument("--to", required=True, help="Địa chỉ ví người nhận (Buyer)")
    parser_send.add_argument("--sender-priv", default="my_keys/private.pem", help="Đường dẫn RSA Private Key của người gửi để ký số")
    parser_send.add_argument("--broker", default=DEFAULT_BROKER, help="URL RAM Broker")
    parser_send.add_argument("--contract", default=DEFAULT_CONTRACT, help="Địa chỉ Smart Contract")
    parser_send.add_argument("--rpc", default=DEFAULT_RPC, help="URL RPC Blockchain")
    parser_send.add_argument("--ttl", type=int, default=300, help="Thời gian tồn tại trên RAM (giây, mặc định 300)")

    # 4. Receive
    parser_recv = subparsers.add_parser("receive", help="Tải và giải mã file từ RAM Broker")
    parser_recv.add_argument("--tx", required=True, help="Mã Ticket / TX ID")
    parser_recv.add_argument("--out", required=True, help="Đường dẫn lưu file tải về")
    parser_recv.add_argument("--priv-key", default="my_keys/private.pem", help="Đường dẫn RSA Private Key của người nhận (.pem)")
    parser_recv.add_argument("--wallet-key", default=None, help="Private Key ví Ethereum của người nhận (hoặc nhập qua prompt/env CLOAKSHARE_WALLET_KEY)")
    parser_recv.add_argument("--sender-pub", help="Đường dẫn file RSA Public Key người gửi (để xác thực chữ ký)")
    parser_recv.add_argument("--broker", default=DEFAULT_BROKER, help="URL RAM Broker")
    parser_recv.add_argument("--burn", action="store_true", help="Tự huỷ dữ liệu khỏi RAM Broker sau khi nhận (burn-after-read)")

    args = parser.parse_args()

    if args.command == "keygen":
        out_dir = Path(args.out)
        out_dir.mkdir(exist_ok=True, parents=True)
        priv_bytes, pub_bytes = _generate_rsa_keys()
        (out_dir / "private.pem").write_bytes(priv_bytes)
        (out_dir / "public.pem").write_bytes(pub_bytes)
        print(f"[+] Tạo cặp khóa RSA 2048 thành công tại: {out_dir.resolve()}")
        print(f"    - Khóa bí mật: {out_dir / 'private.pem'}")
        print(f"    - Khóa công khai: {out_dir / 'public.pem'}")

    elif args.command == "register":
        priv_key = args.private_key or os.environ.get("CLOAKSHARE_PRIVATE_KEY")
        if not priv_key:
            priv_key = getpass.getpass("Nhập Private Key ví Ethereum: ")
            
        pub_text = Path(args.pub).read_text(encoding="utf-8")
        dpki = DPKIClient(contract_address=args.contract, rpc_url=args.rpc)
        account = Account.from_key(priv_key)
        print(f"[*] Đang đăng ký Public Key cho ví {account.address}...")
        tx_hash_hex = dpki.register_public_key(
            private_key_hex=priv_key,
            public_key_pem=pub_text,
        )
        print(f"[+] Đăng ký thành công! Tx Hash / Ref: {tx_hash_hex}")

    elif args.command == "send":
        dpki = DPKIClient(contract_address=args.contract, rpc_url=args.rpc)
        try:
            recipient_pub = dpki.get_public_key(args.to)
        except Exception as err:
            print(f"[-] Không thể tìm thấy Public Key của người nhận ({args.to}): {err}")
            sys.exit(1)

        file_path = Path(args.file)
        if not file_path.exists():
            print(f"[-] File không tồn tại: {file_path}")
            sys.exit(1)

        raw_bytes = file_path.read_bytes()
        print(f"[*] Đang mã hóa file ({len(raw_bytes)} bytes) bằng C Core AES-128-CBC...")
        aes_key, iv, ciphertext = CLIAdapter.encrypt_bytes(raw_bytes)

        print("[*] Đang bọc Session Key bằng RSA-2048 OAEP...")
        wrapped_key = RSAEnvelope.wrap_key(aes_key, recipient_pub)

        # Ký số toàn vẹn nếu có private key
        signature = b""
        priv_path = Path(args.sender_priv)
        if priv_path.exists():
            print("[*] Đang ký số toàn vẹn (RSA-PSS SHA-256)...")
            sender_priv_pem = priv_path.read_text(encoding="utf-8")
            signature = IntegritySigner.sign_file(ciphertext, sender_priv_pem)

        tx_id = f"0x{uuid.uuid4().hex}"
        payload_data = {
            "tx_id": tx_id,
            "recipient": args.to,
            "iv": iv.hex(),
            "wrapped_key": wrapped_key.hex(),
            "ciphertext": ciphertext.hex(),
            "signature": signature.hex(),
            "ttl_seconds": args.ttl,
        }

        print(f"[*] Đang đẩy payload lên RAM Broker ({args.broker})...")
        try:
            res = requests.post(f"{args.broker}/api/v1/stage", json=payload_data, timeout=5)
            if res.status_code == 201:
                print(f"[+] Gửi thành công lên RAM! Ticket TX: {tx_id}")
                print(f"    - Thời gian sống (TTL): {args.ttl}s")
                print(f"    - Recipient: {args.to}")
            else:
                print(f"[-] Lỗi từ RAM Broker ({res.status_code}): {res.text}")
                sys.exit(1)
        except Exception as err:
            print(f"[-] Không thể kết nối tới RAM Broker tại {args.broker}: {err}")
            sys.exit(1)

    elif args.command == "receive":
        wallet_key = args.wallet_key or os.environ.get("CLOAKSHARE_WALLET_KEY")
        if not wallet_key:
            wallet_key = getpass.getpass("Nhập Private Key ví Ethereum: ")
            
        timestamp = int(time.time())
        account = Account.from_key(wallet_key)
        wallet_address = account.address

        print(f"[*] Ký challenge xác thực ví Web3 (EIP-191) cho Ticket: {args.tx}...")
        ts, signature_hex = Web3Auth.sign_retrieve_request(args.tx, wallet_key, timestamp)

        headers = {
            "X-Wallet-Address": wallet_address,
            "X-Timestamp": str(ts),
            "X-Signature": signature_hex,
        }

        burn_query = "?burn=true" if args.burn else ""
        print(f"[*] Đang rút payload từ RAM Broker ({args.broker})...")
        try:
            res = requests.get(f"{args.broker}/api/v1/retrieve/{args.tx}{burn_query}", headers=headers, timeout=5)
            if res.status_code != 200:
                print(f"[-] Lỗi Broker ({res.status_code}): {res.text}")
                sys.exit(1)
        except Exception as err:
            print(f"[-] Không kết nối được tới Broker: {err}")
            sys.exit(1)

        data = res.json()
        iv = bytes.fromhex(data["iv"])
        wrapped_key = bytes.fromhex(data["wrapped_key"])
        ciphertext = bytes.fromhex(data["ciphertext"])
        sig_hex = data.get("signature", "")
        sig_bytes = bytes.fromhex(sig_hex) if sig_hex else b""

        # Kiểm tra chữ ký người gửi nếu có
        if args.sender_pub and sig_bytes:
            sender_pub_pem = Path(args.sender_pub).read_text(encoding="utf-8")
            is_valid = IntegritySigner.verify_file(ciphertext, sig_bytes, sender_pub_pem)
            if is_valid:
                print("[+] Xác thực chữ ký số RSA-PSS: HỢP LỆ (Dữ liệu nguyên vẹn 100%)")
            else:
                print("[!] CẢNH BÁO: Chữ ký số KHÔNG hợp lệ! Dữ liệu có thể đã bị can thiệp.")
        elif sig_bytes:
            print("[i] Gói tin có chữ ký số RSA-PSS của người gửi (có thể truyền --sender-pub để verify).")

        priv_pem = Path(args.priv_key).read_text(encoding="utf-8")
        print("[*] Đang mở bọc khóa AES bằng RSA Private Key...")
        aes_key = RSAEnvelope.unwrap_key(wrapped_key, priv_pem)

        print("[*] Đang giải mã nội dung trong RAM bằng C Core AES-128-CBC...")
        plaintext = CLIAdapter.decrypt_bytes(ciphertext, aes_key, iv)

        out_path = Path(args.out)
        out_path.parent.mkdir(exist_ok=True, parents=True)
        out_path.write_bytes(plaintext)
        print(f"[+] Giải mã thành công! Đã lưu file an toàn tại: {out_path.resolve()}")
        if args.burn:
            print("[+] Payload đã được kích hoạt burn-after-read và xoá hoàn toàn khỏi RAM Broker.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()