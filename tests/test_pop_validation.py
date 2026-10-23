"""
Test suite for Proof-of-Possession (PoP) validation in dPKI Smart Contract.

Kiểm tra khả năng smart contract từ chối key substitution attack và chỉ chấp nhận
public key khi người dùng chứng minh được họ sở hữu RSA private key tương ứng.

LƯU Ý: bản này đã được "chữa cháy" để chạy được. File kế nhiệm là
`tests/test_pop_validation_FIXED.py` (tự deploy, assert đúng chuẩn). Giữ lại file
này để đối chiếu, nhưng các lỗi dưới đây từng khiến nó im lặm SKIP toàn bộ:

  B1  `["python", ...]` — trên Windows "python" có thể không resolve (Microsoft
      Store stub). Phải dùng `sys.executable`.
  B2  `--rpc-url` không tồn tại; script chỉ nhận `--rpc`.
  B3  Chuỗi tìm kiếm "Contract deployed at:" / "Địa chỉ Smart Contract:" KHÔNG
      khớp output thật của deploy_dpki.py ("📍 Contract Address : 0x...").
  B4  Fixture `anvil_node` luôn spawn anvil MỚI dù đã c node ở cổng 8545 →
      Address already in use, rồi terminate cả node đang chạy của người khác.
"""

import pytest
import subprocess
import time
import os
import socket
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from eth_account import Account
from web3 import Web3

# Import các module dPKI
sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.dpki_client import DPKIClient
from engine import pop_helper

RPC_URL = "http://127.0.0.1:8545"
ROOT_DIR = Path(__file__).resolve().parent.parent


def _port_open(host: str = "127.0.0.1", port: int = 8545, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_contract_address(text) -> str | None:
    """B3: parse đúng định dạng output THẬT của scripts/deploy_dpki.py.

    Nhận `bytes` HOẶC `str` — solc/deploy có thể trả ra bytes chưa decode.
    """
    if text is None:
        return None
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    for line in text.splitlines():
        if "Contract Address" in line or "Contract deployed at" in line:
            for tok in line.replace(":", " ").split():
                tok = tok.strip(".,;'\"")
                if tok.startswith("0x") and len(tok) == 42:
                    return tok
    return None


@pytest.fixture(scope="module")
def anvil_node():
    """B4: TÁI SỬ DỤNG node đang chạy ở cổng 8545; chỉ spawn khi cổng chết."""
    if _port_open():
        print(f"\n✓ Reusing existing anvil at {RPC_URL}")
        yield None
        return

    print("\n🔧 Starting Anvil test blockchain...")
    anvil_process = subprocess.Popen(
        ["anvil", "--port", "8545", "--block-time", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + 30
    while time.time() < deadline and not _port_open():
        time.sleep(0.25)
    if not _port_open():
        anvil_process.terminate()
        pytest.fail("Anvil không mở được cổng 8545 trong 30s")

    yield anvil_process

    print("\n🛑 Stopping Anvil...")
    anvil_process.terminate()
    anvil_process.wait()


@pytest.fixture(scope="module")
def deployed_contract(anvil_node):
    """Deploy dPKIRegistry mới và trả về địa chỉ (B1/B2/B3)."""
    print("\n📜 Deploying dPKIRegistry contract...")

    # Compile contract — conftest đã đưa solc.exe vào PATH.
    # B5: `solc --bin` đẩy BYTECODE NHỊ PHÂN ra stdout; với `text=True` Python
    # decode bằng locale codec (cp1252) và nổ UnicodeDecodeError. Capture bytes
    # rồi decode errors="replace".
    compile_result = subprocess.run(
        ["solc", "--bin", "--abi", "contracts/dPKIRegistry.sol"],
        capture_output=True,
        cwd=str(ROOT_DIR),
        timeout=120,
    )
    if compile_result.returncode != 0:
        stderr = compile_result.stderr or b""
        pytest.skip(f"Cannot compile contract: {stderr.decode('utf-8', 'replace')[:300]}")

    # B1: sys.executable thay vì "python". B2: --rpc thay vì --rpc-url.
    # B6: output tiếng Việt có dấu → phải chỉ định encoding="utf-8", nếu không
    # `text=True` dùng locale codec (cp1252) và lại nổ UnicodeDecodeError.
    deploy_result = subprocess.run(
        [sys.executable, "scripts/deploy_dpki.py", "--rpc", RPC_URL],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        cwd=str(ROOT_DIR),
    )
    if deploy_result.returncode != 0:
        pytest.skip(f"Cannot deploy contract: {(deploy_result.stderr or '')[:300]}")

    contract_address = _parse_contract_address(deploy_result.stdout)
    if not contract_address:
        pytest.skip(
            "Could not find contract address in deploy output:\n"
            + (deploy_result.stdout or "")[:500]
        )
    print(f"✓ Contract deployed: {contract_address}")
    return contract_address


# Anvil account #0 — public, deterministic, unlocked.
ANVIL_FUNDER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ANVIL_FUNDER = Account.from_key(ANVIL_FUNDER_KEY).address


@pytest.fixture
def test_wallet():
    """Tạo ví Ethereum test.

    B7: ví `Account.create()` có số dư 0 → mọi transaction bị Anvil từ chối với
    "Insufficient funds for gas * price + value", và `DPKIClient` sẽ âm thầm rơi
    xuống tx-id tổng hợp (không phải hash 66 ký tự) khiến assert sai. Phải nạp
    gas từ tài khoản #0 của Anvil.
    """
    account = Account.create()
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 10}))
        if w3.is_connected() and w3.eth.get_balance(ANVIL_FUNDER) > 0:
            w3.eth.send_transaction(
                {"from": ANVIL_FUNDER, "to": account.address, "value": 50 * 10**18}
            )
    except Exception as e:
        print(f"[!] Không nạp được gas cho {account.address}: {e}")
    return {
        "address": account.address,
        "private_key": account.key.hex()
    }


@pytest.fixture
def test_rsa_keypair(tmp_path):
    """Tạo RSA keypair test và lưu vào file tạm."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    
    # Serialize to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    # Lưu private key vào file tạm
    private_key_path = tmp_path / "test_rsa_private.pem"
    private_key_path.write_bytes(private_pem)
    
    return {
        "public_pem": public_pem,
        "private_pem": private_pem,
        "private_key_path": str(private_key_path),
        "private_key_obj": private_key
    }


def test_pop_valid_signature_accepted(deployed_contract, test_wallet, test_rsa_keypair):
    """
    TEST 1: Smart contract PHẢI chấp nhận registration khi có PoP signature hợp lệ.
    """
    dpki = DPKIClient(contract_address=deployed_contract, rpc_url="http://127.0.0.1:8545")
    
    # Register với PoP signature
    tx_hash = dpki.register_public_key(
        private_key_hex=test_wallet["private_key"],
        public_key_pem=test_rsa_keypair["public_pem"],
        rsa_private_key_path=test_rsa_keypair["private_key_path"]
    )
    
    assert tx_hash.startswith("0x"), "Transaction hash phải bắt đầu với 0x"
    assert len(tx_hash) == 66, "Transaction hash phải dài 66 ký tự"
    
    # Verify on-chain
    registered_key = dpki.get_public_key(test_wallet["address"])
    assert registered_key == test_rsa_keypair["public_pem"], "Public key không khớp trên blockchain"
    
    print(f"✓ Valid PoP signature accepted, tx: {tx_hash}")


def test_pop_invalid_signature_rejected(deployed_contract, test_wallet, test_rsa_keypair, tmp_path):
    """
    TEST 2: Smart contract PHẢI từ chối registration khi signature không hợp lệ.
    """
    dpki = DPKIClient(contract_address=deployed_contract, rpc_url="http://127.0.0.1:8545")
    
    # Tạo signature SAI bằng cách thay đổi 1 byte
    correct_signature = pop_helper.generate_pop_signature(
        test_wallet["private_key"],
        test_rsa_keypair["private_pem"]
    )
    
    # Corrupt signature
    corrupted_signature = bytearray(correct_signature)
    corrupted_signature[0] ^= 0xFF  # Flip all bits in first byte
    corrupted_signature = bytes(corrupted_signature)
    
    # Thử register với signature bị corrupt
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    account = Account.from_key(test_wallet["private_key"])
    contract = w3.eth.contract(address=deployed_contract, abi=dpki.contract.abi)
    
    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.functions.registerPublicKeyWithPoP(
        test_rsa_keypair["public_pem"],
        corrupted_signature
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "chainId": w3.eth.chain_id,
        "gas": 2_000_000,
        "gasPrice": w3.eth.gas_price,
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=test_wallet["private_key"])
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    # B8: `wait_for_transaction_receipt()` KHÔNG raise khi tx revert — nó trả về
    # receipt với status == 0. Bao nó trong `pytest.raises(Exception)` khiến test
    # luôn fail ("DID NOT RAISE") dù hợp đồng chặn đúng. Cách đúng: kiểm status,
    # hoặc bắt ContractCustomError khi eth_call/estimate_gas revert.
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
    assert receipt.status == 0, (
        "Transaction với signature sai KHÔNG bị revert — hợp đồng đã chấp nhận "
        "chữ ký không hợp lệ!"
    )

    print("✓ Invalid signature correctly rejected")


def test_pop_wrong_rsa_key_rejected(deployed_contract, test_wallet, test_rsa_keypair, tmp_path):
    """
    TEST 3: Smart contract PHẢI từ chối khi signature được tạo bằng RSA key KHÁC.
    (Key Substitution Attack Defense)
    """
    dpki = DPKIClient(contract_address=deployed_contract, rpc_url="http://127.0.0.1:8545")
    
    # Tạo RSA keypair THỨ HAI (attacker's key)
    attacker_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attacker_private_pem = attacker_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Tạo signature bằng attacker's key
    malicious_signature = pop_helper.generate_pop_signature(
        test_wallet["private_key"],
        attacker_private_pem
    )
    
    # Thử register LEGITIMATE public key với MALICIOUS signature
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    account = Account.from_key(test_wallet["private_key"])
    contract = w3.eth.contract(address=deployed_contract, abi=dpki.contract.abi)
    
    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.functions.registerPublicKeyWithPoP(
        test_rsa_keypair["public_pem"],  # Victim's public key
        malicious_signature  # Attacker's signature
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "chainId": w3.eth.chain_id,
        "gas": 2_000_000,
        "gasPrice": w3.eth.gas_price,
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=test_wallet["private_key"])
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    # B8 (như TEST 2): revert biểu hiện bằng receipt.status == 0, KHÔNG phải exception.
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
    assert receipt.status == 0, (
        "Key substitution attack KHÔNG bị chặn — hợp đồng đã ghi khoá của nạn nhân "
        "dù chữ ký do kẻ tấn công tạo!"
    )

    print("✓ Key substitution attack successfully blocked")


def test_pop_replay_attack_prevented(deployed_contract, test_wallet, test_rsa_keypair):
    """
    TEST 4: Signature phải được bind với Ethereum address để chống replay attack.
    
    Một signature hợp lệ cho wallet A KHÔNG THỂ được replay cho wallet B.
    """
    dpki = DPKIClient(contract_address=deployed_contract, rpc_url="http://127.0.0.1:8545")
    
    # Wallet A register thành công
    tx_hash_a = dpki.register_public_key(
        private_key_hex=test_wallet["private_key"],
        public_key_pem=test_rsa_keypair["public_pem"],
        rsa_private_key_path=test_rsa_keypair["private_key_path"]
    )
    assert tx_hash_a.startswith("0x")
    
    # Capture signature của wallet A
    signature_a = pop_helper.generate_pop_signature(
        test_wallet["private_key"],
        test_rsa_keypair["private_pem"]
    )
    
    # Tạo wallet B (attacker) — cũng cần gas để tx revert vì lý do ĐÚNG
    # (chữ ký sai), chứ không phải vì hết tiền.
    wallet_b = Account.create()
    try:
        w3f = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 10}))
        if w3f.is_connected() and w3f.eth.get_balance(ANVIL_FUNDER) > 0:
            w3f.eth.send_transaction(
                {"from": ANVIL_FUNDER, "to": wallet_b.address, "value": 50 * 10**18}
            )
    except Exception as e:
        print(f"[!] Không nạp được gas cho wallet B: {e}")

    # Attacker thử replay signature của wallet A
    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    contract = w3.eth.contract(address=deployed_contract, abi=dpki.contract.abi)
    
    nonce = w3.eth.get_transaction_count(wallet_b.address)
    tx = contract.functions.registerPublicKeyWithPoP(
        test_rsa_keypair["public_pem"],
        signature_a  # Replay signature từ wallet A
    ).build_transaction({
        "from": wallet_b.address,  # Nhưng gửi từ wallet B
        "nonce": nonce,
        "chainId": w3.eth.chain_id,
        "gas": 2_000_000,
        "gasPrice": w3.eth.gas_price,
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=wallet_b.key.hex())
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    # B8 (như TEST 2/3): revert biểu hiện bằng receipt.status == 0, KHÔNG phải exception.
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
    assert receipt.status == 0, (
        "Replay attack KHÔNG bị chặn — chữ ký của ví A đã được chấp nhận cho ví B!"
    )

    print("✓ Replay attack successfully prevented")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
