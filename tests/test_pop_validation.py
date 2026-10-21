"""
Test suite for Proof-of-Possession (PoP) validation in dPKI Smart Contract.

Kiểm tra khả năng smart contract từ chối key substitution attack và chỉ chấp nhận
public key khi người dùng chứng minh được họ sở hữu RSA private key tương ứng.
"""

import pytest
import subprocess
import time
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from eth_account import Account
from web3 import Web3

# Import các module dPKI
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.dpki_client import DPKIClient
from engine import pop_helper


@pytest.fixture(scope="module")
def anvil_node():
    """Khởi động Anvil blockchain node để test."""
    print("\n🔧 Starting Anvil test blockchain...")
    anvil_process = subprocess.Popen(
        ["anvil", "--port", "8545", "--block-time", "1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(3)  # Chờ Anvil khởi động
    
    yield anvil_process
    
    print("\n🛑 Stopping Anvil...")
    anvil_process.terminate()
    anvil_process.wait()


@pytest.fixture(scope="module")
def deployed_contract(anvil_node):
    """Deploy smart contract dPKIRegistry lên Anvil."""
    print("\n📜 Deploying dPKIRegistry contract...")
    
    # Compile contract
    compile_result = subprocess.run(
        ["solc", "--bin", "--abi", "contracts/dPKIRegistry.sol"],
        capture_output=True,
        text=True
    )
    
    if compile_result.returncode != 0:
        pytest.skip(f"Cannot compile contract: {compile_result.stderr}")
    
    # Deploy using deploy_dpki.py script
    deploy_result = subprocess.run(
        ["python", "scripts/deploy_dpki.py", "--rpc-url", "http://127.0.0.1:8545"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    if deploy_result.returncode != 0:
        pytest.skip(f"Cannot deploy contract: {deploy_result.stderr}")
    
    # Extract contract address from output
    for line in deploy_result.stdout.split('\n'):
        if "Contract deployed at:" in line or "Địa chỉ Smart Contract:" in line:
            contract_address = line.split()[-1]
            print(f"✓ Contract deployed: {contract_address}")
            return contract_address
    
    pytest.skip("Could not find contract address in deploy output")


@pytest.fixture
def test_wallet():
    """Tạo ví Ethereum test."""
    account = Account.create()
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
    
    # Transaction PHẢI revert
    with pytest.raises(Exception):
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
        assert receipt.status == 0, "Transaction với signature sai phải bị revert"
    
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
    
    # Transaction PHẢI revert (key substitution attack detected)
    with pytest.raises(Exception):
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
        assert receipt.status == 0, "Key substitution attack phải bị chặn"
    
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
    
    # Tạo wallet B (attacker)
    wallet_b = Account.create()
    
    # Attacker thử replay signature của wallet A
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
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
    
    # Transaction PHẢI revert (signature không match với msg.sender)
    with pytest.raises(Exception):
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
        assert receipt.status == 0, "Replay attack phải bị chặn"
    
    print("✓ Replay attack successfully prevented")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
