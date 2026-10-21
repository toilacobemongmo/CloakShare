"""
tests/test_pop_validation_FIXED.py

PoP validation suite — Anvil-backed, self-contained.

Fixes vs. tests/test_pop_validation.py:
  D1  test_wallet funded from Anvil account #0 (0-wei wallet => mempool reject
      => DPKIClient falls back to synthetic tx id => len()==66 assert fails).
  D2  negative tests assert via eth_call revert + explicit receipt.status==0
      (wait_for_transaction_receipt does NOT raise on revert; pytest.raises
      was swallowing AssertionError => all three negative tests false-passed).
  D3  generate_pop_signature arg order matches engine/pop_helper.py contract:
      (eth_private_key_hex, rsa_private_key_pem) — NOT (pem, address).
  D4  anvil_node probes the port BEFORE the binary, so an already-running
      node (Terminal 1) is reused instead of failing on shutil.which.
  D5  negative tests now check ContractCustomError 4-byte selector instead of
      naive substring matching (web3.py raises ContractCustomError with selector
      in .args[0], not a prose revert string).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time

import pytest
from eth_account import Account
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from web3 import Web3
from web3.exceptions import ContractCustomError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine.pop_helper as pop_helper  # noqa: E402
import tests.pop_utils as pop_utils  # noqa: E402

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

RPC_HOST = "127.0.0.1"
RPC_PORT = 8545
RPC_URL = f"http://{RPC_HOST}:{RPC_PORT}"

# Anvil account #0 — public, deterministic, unlocked.
ANVIL_FUNDER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ANVIL_FUNDER = Account.from_key(ANVIL_FUNDER_KEY).address

FUND_AMOUNT_WEI = 50 * 10**18
GAS_LIMIT = 5_000_000

DPKI_ABI = [
    {
        "inputs": [{"internalType": "string", "name": "publicKeyPem", "type": "string"}],
        "name": "registerPublicKey",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "publicKeyPem", "type": "string"},
            {"internalType": "bytes", "name": "signature", "type": "bytes"},
        ],
        "name": "registerPublicKeyWithPoP",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "getPublicKey",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_port(host: str, port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(host, port, timeout=0.2):
            return
        time.sleep(0.25)
    raise RuntimeError(f"{host}:{port} did not open within {timeout}s")


def _find_anvil() -> str | None:
    exe = "anvil.exe" if os.name == "nt" else "anvil"
    for d in (
        os.path.expanduser(r"~\.foundry\bin"),
        os.path.expanduser("~/.foundry/bin"),
        r"C:\Users\Public\foundry\bin",
    ):
        cand = os.path.join(d, exe)
        if os.path.isfile(cand):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            return cand
    return shutil.which("anvil")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def anvil_node():
    """Reuse a listening node on 8545; only spawn if the port is dead."""
    if _port_open(RPC_HOST, RPC_PORT):
        print(f"\n✓ Reusing existing anvil at {RPC_URL}")
        yield RPC_URL
        return

    anvil_exe = _find_anvil()
    if anvil_exe is None:
        pytest.fail(
            "anvil not found and nothing listening on 8545.\n"
            r"Run: powershell -File scripts/install_foundry_windows.ps1"
        )

    print(f"\n▶ Spawning anvil: {anvil_exe}")
    proc = subprocess.Popen(
        [anvil_exe, "--port", str(RPC_PORT), "--block-time", "1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_port(RPC_HOST, RPC_PORT, timeout=30)
        yield RPC_URL
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def w3(anvil_node):
    provider = Web3.HTTPProvider(anvil_node, request_kwargs={"timeout": 60})
    client = Web3(provider)
    if not client.is_connected():
        pytest.fail(f"Cannot connect to {anvil_node}")
    return client


@pytest.fixture(scope="module")
def deployed_contract(anvil_node):
    """Deploy dPKIRegistry once per module via scripts/deploy_dpki.py."""
    print("\n📜 Deploying dPKIRegistry...")
    env = pop_utils.child_env() if hasattr(pop_utils, "child_env") else None
    result = subprocess.run(
        [sys.executable, "scripts/deploy_dpki.py", "--rpc", RPC_URL],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
    )
    if result.returncode != 0:
        pytest.fail(f"Deploy failed (exit {result.returncode}):\n{result.stderr}")

    address = None
    if hasattr(pop_utils, "parse_contract_address"):
        address = pop_utils.parse_contract_address(result.stdout, result.stderr)
    if not address:
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            if "0x" in line and len(line.strip()) > 0:
                for tok in line.replace(":", " ").replace("=", " ").split():
                    tok = tok.strip(".,;'\"")
                    if tok.startswith("0x") and len(tok) == 42:
                        address = tok
    if not address:
        pytest.fail(f"Could not parse contract address from:\n{result.stdout}")

    print(f"✓ Contract deployed: {address}")
    return address


@pytest.fixture(scope="module")
def contract(w3, deployed_contract):
    return w3.eth.contract(
        address=Web3.to_checksum_address(deployed_contract),
        abi=DPKI_ABI,
    )


@pytest.fixture
def test_wallet(w3):
    """Fresh wallet, funded from Anvil account #0 (D1)."""
    acct = Account.create()
    tx_hash = w3.eth.send_transaction(
        {
            "from": Web3.to_checksum_address(ANVIL_FUNDER),
            "to": acct.address,
            "value": FUND_AMOUNT_WEI,
        }
    )
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    assert receipt["status"] == 1, "Funding tx failed"

    balance = w3.eth.get_balance(acct.address)
    assert balance == FUND_AMOUNT_WEI, f"Wallet not funded (balance={balance})"

    return {"address": acct.address, "private_key": acct.key.hex(), "account": acct}


@pytest.fixture
def test_rsa_keypair(tmp_path):
    """RSA-2048 keypair, private key lưu file tạm."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    pem_path = tmp_path / "test_rsa_private.pem"
    pem_path.write_text(private_pem, encoding="utf-8")

    return {
        "public_pem": public_pem,
        "private_pem": private_pem,
        "private_key_path": str(pem_path),
        "private_key_obj": priv,
    }


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_pop_valid_signature_accepted(
    w3, contract, test_wallet, test_rsa_keypair, deployed_contract
):
    """TEST 1: Smart contract PHẢI chấp nhận registration khi có PoP hợp lệ."""
    # FIX D3: generate_pop_signature(eth_private_key_hex, rsa_private_key_pem)
    signature = pop_helper.generate_pop_signature(
        test_wallet["private_key"], test_rsa_keypair["private_pem"]
    )

    # Build + sign tx
    fn = contract.functions.registerPublicKeyWithPoP(
        test_rsa_keypair["public_pem"], signature
    )
    tx = fn.build_transaction(
        {
            "from": test_wallet["address"],
            "nonce": w3.eth.get_transaction_count(test_wallet["address"]),
            "gas": GAS_LIMIT,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=test_wallet["private_key"])
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    assert receipt["status"] == 1, f"Tx reverted: {receipt}"

    # Verify on-chain
    registered_key = contract.functions.getPublicKey(test_wallet["address"]).call()
    assert registered_key == test_rsa_keypair["public_pem"], "Public key mismatch on-chain"

    print(f"✓ Valid PoP accepted, tx: {tx_hash.hex()}")


def test_pop_invalid_signature_rejected(w3, contract, test_wallet, test_rsa_keypair):
    """TEST 2: Smart contract PHẢI từ chối khi signature bị corrupt."""
    # Generate correct signature (D3)
    correct_sig = pop_helper.generate_pop_signature(
        test_wallet["private_key"], test_rsa_keypair["private_pem"]
    )

    # Corrupt first byte
    corrupted_sig = bytearray(correct_sig)
    corrupted_sig[0] ^= 0xFF
    corrupted_sig = bytes(corrupted_sig)

    # Build tx
    fn = contract.functions.registerPublicKeyWithPoP(
        test_rsa_keypair["public_pem"], corrupted_sig
    )
    tx = fn.build_transaction(
        {
            "from": test_wallet["address"],
            "nonce": w3.eth.get_transaction_count(test_wallet["address"]),
            "gas": GAS_LIMIT,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )

    # eth_call probe: expect InvalidPoPSignature() = 0x14b94150 (D2, D5)
    try:
        w3.eth.call(tx)
        pytest.fail("eth_call should have reverted but didn't")
    except ContractCustomError as e:
        # Selector for InvalidPoPSignature() = keccak256("InvalidPoPSignature()")[:4]
        assert e.args[0] == "0x14b94150", f"Expected InvalidPoPSignature selector, got {e.args[0]}"
    except Exception as e:
        pytest.fail(f"Expected ContractCustomError with selector 0x14b94150, got {type(e).__name__}: {e}")

    # Gửi tx thật để kiểm tra receipt.status == 0
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=test_wallet["private_key"])
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    assert receipt["status"] == 0, "Tx với signature sai phải bị revert"

    print("✓ Invalid signature correctly rejected")


def test_pop_wrong_rsa_key_rejected(w3, contract, test_wallet, test_rsa_keypair):
    """TEST 3: Smart contract PHẢI từ chối khi signature được tạo bằng RSA key KHÁC.
    (Key Substitution Attack Defense)
    """
    # Generate attacker's RSA keypair
    attacker_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    attacker_priv_pem = attacker_priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    # Sign với attacker's key (D3)
    malicious_sig = pop_helper.generate_pop_signature(
        test_wallet["private_key"], attacker_priv_pem
    )

    # Thử register victim's public key với attacker's signature
    fn = contract.functions.registerPublicKeyWithPoP(
        test_rsa_keypair["public_pem"], malicious_sig
    )
    tx = fn.build_transaction(
        {
            "from": test_wallet["address"],
            "nonce": w3.eth.get_transaction_count(test_wallet["address"]),
            "gas": GAS_LIMIT,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )

    # eth_call probe: expect InvalidPoPSignature() = 0x14b94150 (D2, D5)
    try:
        w3.eth.call(tx)
        pytest.fail("eth_call should have reverted for key substitution")
    except ContractCustomError as e:
        assert e.args[0] == "0x14b94150", f"Expected InvalidPoPSignature selector, got {e.args[0]}"
    except Exception as e:
        pytest.fail(f"Expected ContractCustomError with selector 0x14b94150, got {type(e).__name__}: {e}")

    # Send tx và kiểm tra receipt
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=test_wallet["private_key"])
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    assert receipt["status"] == 0, "Key substitution attack phải bị chặn"

    print("✓ Key substitution attack successfully blocked")


def test_pop_replay_attack_prevented(w3, contract, test_wallet, test_rsa_keypair):
    """TEST 4: Signature phải bind với Ethereum address để chống replay attack.

    Một signature hợp lệ cho wallet A KHÔNG THỂ replay cho wallet B.
    """
    # Wallet A register thành công (đã fund) (D3)
    signature_a = pop_helper.generate_pop_signature(
        test_wallet["private_key"], test_rsa_keypair["private_pem"]
    )
    fn = contract.functions.registerPublicKeyWithPoP(
        test_rsa_keypair["public_pem"], signature_a
    )
    tx = fn.build_transaction(
        {
            "from": test_wallet["address"],
            "nonce": w3.eth.get_transaction_count(test_wallet["address"]),
            "gas": GAS_LIMIT,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=test_wallet["private_key"])
    tx_hash_a = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt_a = w3.eth.wait_for_transaction_receipt(tx_hash_a, timeout=60)
    assert receipt_a["status"] == 1, "Wallet A registration failed"

    # Tạo wallet B (attacker), fund nó
    wallet_b = Account.create()
    tx_hash_fund = w3.eth.send_transaction(
        {
            "from": Web3.to_checksum_address(ANVIL_FUNDER),
            "to": wallet_b.address,
            "value": FUND_AMOUNT_WEI,
        }
    )
    receipt_fund = w3.eth.wait_for_transaction_receipt(tx_hash_fund, timeout=60)
    assert receipt_fund["status"] == 1, "Wallet B funding failed"

    # Attacker thử replay signature_a (của wallet A) từ wallet B
    fn_b = contract.functions.registerPublicKeyWithPoP(
        test_rsa_keypair["public_pem"], signature_a  # Replay signature từ wallet A
    )
    tx_b = fn_b.build_transaction(
        {
            "from": wallet_b.address,  # Gửi từ wallet B
            "nonce": w3.eth.get_transaction_count(wallet_b.address),
            "gas": GAS_LIMIT,
            "gasPrice": w3.eth.gas_price,
            "chainId": w3.eth.chain_id,
        }
    )

    # eth_call probe: expect InvalidPoPSignature() = 0x14b94150 (D2, D5)
    try:
        w3.eth.call(tx_b)
        pytest.fail("eth_call should have reverted for replay attack")
    except ContractCustomError as e:
        assert e.args[0] == "0x14b94150", f"Expected InvalidPoPSignature selector, got {e.args[0]}"
    except Exception as e:
        pytest.fail(f"Expected ContractCustomError with selector 0x14b94150, got {type(e).__name__}: {e}")

    # Send tx và kiểm tra receipt
    signed_tx_b = w3.eth.account.sign_transaction(tx_b, private_key=wallet_b.key.hex())
    tx_hash_b = w3.eth.send_raw_transaction(signed_tx_b.raw_transaction)
    receipt_b = w3.eth.wait_for_transaction_receipt(tx_hash_b, timeout=60)
    assert receipt_b["status"] == 0, "Replay attack phải bị chặn"

    print("✓ Replay attack successfully prevented")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
