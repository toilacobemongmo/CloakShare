import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web3 import Web3
from solcx import compile_standard, install_solc

# 1. Trỏ về mạng Anvil Local đang chạy
RPC_URL = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC_URL))
assert w3.is_connected(), "Không thể kết nối Anvil Node tại 127.0.0.1:8545! Hãy kiểm tra cửa sổ Git Bash chạy anvil."

# 2. Dùng Account (0) mặc định của Anvil
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
account = w3.eth.account.from_key(DEPLOYER_KEY)
print(f"[*] Deployer: {account.address}")
print(f"[*] Balance: {w3.from_wei(w3.eth.get_balance(account.address), 'ether')} ETH")

# 3. Biên dịch dPKIRegistry.sol
print("[*] Compiling dPKIRegistry.sol...")
install_solc("0.8.20")
contract_path = ROOT_DIR / "contracts" / "dPKIRegistry.sol"
contract_source = contract_path.read_text(encoding="utf-8")

compiled = compile_standard(
    {
        "language": "Solidity",
        "sources": {"dPKIRegistry.sol": {"content": contract_source}},
        "settings": {"outputSelection": {"*": {"*": ["abi", "evm.bytecode"]}}},
    },
    solc_version="0.8.20",
)

abi = compiled["contracts"]["dPKIRegistry.sol"]["dPKIRegistry"]["abi"]
bytecode = compiled["contracts"]["dPKIRegistry.sol"]["dPKIRegistry"]["evm"]["bytecode"]["object"]

# 4. Gửi transaction deploy lên Anvil
print("[*] Deploying contract...")
Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
tx = Contract.constructor().build_transaction({
    "from": account.address,
    "nonce": w3.eth.get_transaction_count(account.address),
    "chainId": 31337,
    "gas": 1_000_000,
    "gasPrice": w3.eth.gas_price,
})

signed_tx = w3.eth.account.sign_transaction(tx, private_key=DEPLOYER_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

print("\n" + "=" * 50)
print(f" Deploy Contract thành công!")
print(f" Contract Address: {receipt.contractAddress}")
print(f" Transaction Hash: {tx_hash.hex()}")
print("=" * 50)