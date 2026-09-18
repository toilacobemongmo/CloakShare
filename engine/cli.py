from pathlib import Path
import argparse
import sys
from engine.cli_adapter import CLIAdapter
from engine.wallet_auth import sign_payload
from engine.dpki_client import DPKIClient
from engine.rsa_envelope import generate_rsa_key_pair
import argparse
import os
import sys
from pathlib import Path
import requests  # <-- Thêm dòng này

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 1. Các module Web3 & dPKI
from eth_account import Account
from eth_account.messages import encode_defunct
from engine.dpki_client import DPKIClient

# 2. Giữ nguyên đúng định dạng các module cũ của bạn
from engine.signer import IntegritySigner
from engine.rsa_envelope import RSAEnvelope

# 3. Import sinh khóa RSA nội bộ cho CLI (không cần sửa rsa_envelope.py)
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

DEFAULT_CONTRACT = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
DEFAULT_RPC = "http://127.0.0.1:8545"
DEFAULT_BROKER = "http://127.0.0.1:8000"

def _generate_rsa_keys():
    """Tự tạo cặp khóa RSA 2048-bit phục vụ CLI mà không sửa file rsa_envelope.py."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_priv = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pem_pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem_priv, pem_pub

def _sign_eip191(private_key: str, message_text: str) -> str:
    """Ký ví Ethereum EIP-191 trực tiếp bằng eth_account (không đụng vào engine/signer.py)."""
    message = encode_defunct(text=message_text)
    signed_message = Account.sign_message(message, private_key=private_key)
    return signed_message.signature.hex()

def main():
    parser = argparse.ArgumentParser(description="CloakShare CLI")
    subparsers = parser.add_subparsers(dest="command", help="Các lệnh hỗ trợ")

    # 1. Keygen
    parser_keygen = subparsers.add_parser("keygen", help="Tạo cặp khóa RSA 2048")
    parser_keygen.add_argument("--out", default="my_keys", help="Thư mục lưu khóa")

    # 2. Register
    parser_reg = subparsers.add_parser("register", help="Đăng ký Public Key lên dPKI Smart Contract")
    parser_reg.add_argument("--pub", required=True, help="Đường dẫn file Public Key (.pem)")
    parser_reg.add_argument("--address", required=True, help="Địa chỉ ví Ethereum")
    parser_reg.add_argument("--private-key", required=True, help="Private Key ví Ethereum")
    parser_reg.add_argument("--contract", default=DEFAULT_CONTRACT, help="Địa chỉ Smart Contract")

    # 3. Send (Seller)
    parser_send = subparsers.add_parser("send", help="Mã hóa và gửi file lên RAM Broker")
    parser_send.add_argument("--file", required=True, help="Đường dẫn file cần gửi")
    parser_send.add_argument("--to", required=True, help="Địa chỉ ví người nhận (Buyer)")
    parser_send.add_argument("--broker", default=DEFAULT_BROKER, help="URL RAM Broker")
    parser_send.add_argument("--contract", default=DEFAULT_CONTRACT, help="Địa chỉ Smart Contract")

    # 4. Receive (Buyer)
    parser_recv = subparsers.add_parser("receive", help="Tải và giải mã file từ RAM Broker")
    parser_recv.add_argument("--tx", required=True, help="Mã Ticket / TX ID")
    parser_recv.add_argument("--out", required=True, help="Đường dẫn lưu file tải về")
    parser_recv.add_argument("--priv-key", required=True, help="Đường dẫn RSA Private Key (.pem)")
    parser_recv.add_argument("--wallet-key", required=True, help="Private Key ví Ethereum")
    parser_recv.add_argument("--broker", default=DEFAULT_BROKER, help="URL RAM Broker")

    args = parser.parse_args()

    if args.command == "keygen":
        out_dir = Path(args.out)
        out_dir.mkdir(exist_ok=True, parents=True)
        priv_bytes, pub_bytes = _generate_rsa_keys()
        (out_dir / "private.pem").write_bytes(priv_bytes)
        (out_dir / "public.pem").write_bytes(pub_bytes)
        print(f"[+] Tao cap khoa thanh cong tai: {out_dir.resolve()}")

    elif args.command == "register":
        pub_text = Path(args.pub).read_text(encoding="utf-8")
        dpki = DPKIClient(contract_address=args.contract, rpc_url=DEFAULT_RPC)
        print(f"[*] Dang dang ky Public Key cho vi {args.address}...")
        tx_hash_hex = dpki.register_public_key(
            private_key_hex=args.private_key,
            public_key_pem=pub_text
        )
        print(f"[+] Dang ky thanh cong! Tx Hash: {tx_hash_hex}")

    elif args.command == "send":
        dpki = DPKIClient(contract_address=args.contract, rpc_url=DEFAULT_RPC)
        recipient_pub = dpki.get_public_key(args.to)
        if not recipient_pub:
            print(f"[-] Khong tim thay Public Key tren blockchain cho vi: {args.to}")
            sys.exit(1)

        from engine.cli_adapter import CLIAdapter
        file_path = Path(args.file)
        enc_out = file_path.with_suffix(".enc")

        print("[*] Dang ma hoa file bang AES-128...")
        aes_key, iv = CLIAdapter.encrypt_file(str(file_path), str(enc_out))
        
        # Bọc khóa
        wrapped_key = RSAEnvelope.wrap_key(aes_key, recipient_pub)

        # Đọc file đã mã hóa thành bytes để đưa vào payload JSON
        ciphertext_bytes = enc_out.read_bytes()
        enc_out.unlink(missing_ok=True)

        # Tạo tx_id ngẫu nhiên hoặc dùng hash tùy theo StagePayload schema của bạn
        import uuid
        tx_id = str(uuid.uuid4())

        payload_data = {
            "tx_id": tx_id,
            "recipient": args.to,
            "iv": iv.hex(),
            "wrapped_key": wrapped_key.hex(),
            "ciphertext": ciphertext_bytes.hex(),
            "signature": "", # Nếu chưa bắt buộc chữ ký ở bước stage
            "ttl_seconds": 300
        }

        print("[*] Dang gui payload len RAM Broker...")
        res = requests.post(
            f"{args.broker}/api/v1/stage",
            json=payload_data
        )

        if res.status_code == 201:
            print(f"[+] Gui thanh cong! Ticket TX: {res.json().get('tx_id')}")
        else:
            print(f"[-] Loi tu RAM Broker ({res.status_code}): {res.text}")

    elif args.command == "receive":
        import time
        from eth_account import Account
        from engine.wallet_auth import Web3Auth
        from engine.cli_adapter import CLIAdapter
        from engine.rsa_envelope import RSAEnvelope

        print("[*] Tao chu ky EIP-191...")
        timestamp = int(time.time())
        account = Account.from_key(args.wallet_key)
        wallet_address = account.address

        # Tạo thông điệp chuẩn theo Web3Auth để Broker kiểm tra
        msg = Web3Auth.create_retrieve_message(args.tx, timestamp)
        signature = _sign_eip191(args.wallet_key, msg)

        headers = {
            "X-Wallet-Address": wallet_address,
            "X-Timestamp": str(timestamp),
            "X-Signature": signature,
        }

        print("[*] Dang tai du lieu tu Broker...")
        res = requests.get(f"{args.broker}/api/v1/retrieve/{args.tx}", headers=headers)
        if res.status_code != 200:
            print(f"[-] Loi Broker: {res.text}")
            sys.exit(1)

        data = res.json()
        iv = bytes.fromhex(data["iv"])
        wrapped_key = bytes.fromhex(data["wrapped_key"])
        ciphertext = bytes.fromhex(data["ciphertext"])

        priv_pem = Path(args.priv_key).read_text(encoding="utf-8")

        print("[*] Giai ma khoa AES bang RSA Private Key...")
        aes_key = RSAEnvelope.unwrap_key(wrapped_key, priv_pem)

        print("[*] Giai ma file bang AES-128...")
        temp_enc = Path(args.out).with_suffix(".tmp.enc")
        temp_enc.write_bytes(ciphertext)
        CLIAdapter.decrypt_file(str(temp_enc), args.out, aes_key, iv)
        temp_enc.unlink(missing_ok=True)

        print(f"[+] Giai ma thanh cong! File luu tai: {args.out}")

if __name__ == "__main__":
    main()