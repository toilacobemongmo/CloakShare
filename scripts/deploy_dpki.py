import argparse
import os
import sys
from pathlib import Path

# Đảm bảo UTF-8 stream trên Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web3 import Web3
from solcx import compile_standard, install_solc


def main():
    parser = argparse.ArgumentParser(description="Triển khai dPKIRegistry Smart Contract lên EVM Blockchain")
    parser.add_argument("--rpc", default=os.getenv("RPC_URL", "http://127.0.0.1:8545"), help="URL RPC (Anvil, Polygon Amoy, Sepolia...)")
    parser.add_argument("--key", default=os.getenv("DEPLOYER_KEY", "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"), help="Private key của Deployer")
    args = parser.parse_args()

    w3 = Web3(Web3.HTTPProvider(args.rpc, request_kwargs={"timeout": 5}))
    if not w3.is_connected():
        print(f"[-] Không thể kết nối tới node EVM tại: {args.rpc}")
        print("    [!] Mẹo: Nếu đang test local, hãy bật Anvil bằng lệnh: 'anvil' hoặc kiểm tra RPC URL.")
        sys.exit(1)

    account = w3.eth.account.from_key(args.key)
    chain_id = w3.eth.chain_id
    balance = w3.eth.get_balance(account.address)

    print(f"[*] Kết nối thành công! Chain ID: {chain_id}")
    print(f"[*] Deployer Address : {account.address}")
    print(f"[*] Balance          : {w3.from_wei(balance, 'ether')} ETH/MATIC")

    if balance == 0:
        print("[!] CẢNH BÁO: Số dư tài khoản bằng 0, giao dịch có thể bị từ chối do thiếu gas!")

    # Biên dịch dPKIRegistry.sol
    print("[*] Đang biên dịch dPKIRegistry.sol (Solc 0.8.20)...")
    try:
        install_solc("0.8.20")
    except Exception as e:
        print(f"[*] install_solc info: {e}")

    contract_path = ROOT_DIR / "contracts" / "dPKIRegistry.sol"
    contract_source = contract_path.read_text(encoding="utf-8")

    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {"dPKIRegistry.sol": {"content": contract_source}},
            "settings": {
                "optimizer": {"enabled": True, "runs": 200},
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode"]}},
            },
        },
        solc_version="0.8.20",
    )

    abi = compiled["contracts"]["dPKIRegistry.sol"]["dPKIRegistry"]["abi"]
    bytecode = compiled["contracts"]["dPKIRegistry.sol"]["dPKIRegistry"]["evm"]["bytecode"]["object"]

    # Kich thuoc bytecode (EIP-170 gioi han 24576 bytes)
    code_size = len(bytecode) // 2
    print(f"[*] Bytecode size  : {code_size} bytes")
    if code_size > 24576:
        print("[-] Bytecode vuot gioi han EIP-170 (24576 bytes). Can bat optimizer hoac tach contract.")
        sys.exit(1)

    # Gửi transaction deploy
    print("[*] Đang gửi transaction deploy contract...")
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Uoc luong gas dong: gas trien khai = 21000 + 32000 + 200 * code_size (+constructor)
    # Dung eth_estimateGas de chinh xac, fallback ve cong thuc thu cong neu node tu choi.
    deploy_gas = 21000 + 32000 + 200 * code_size + 500_000
    try:
        estimated = Contract.constructor().estimate_gas({"from": account.address})
        deploy_gas = max(estimated, deploy_gas)
        print(f"[*] Estimated gas  : {estimated:,}")
    except Exception as e:
        print(f"[*] estimate_gas that bai ({e}); dung du phong {deploy_gas:,} gas")

    tx = Contract.constructor().build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": chain_id,
        "gas": deploy_gas,
        "gasPrice": w3.eth.gas_price,
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=args.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"[*] Tx Submitted: {tx_hash.hex()}. Đang chờ xác nhận khối...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

    if receipt.status != 1:
        print(f"[-] DEPLOY THAT BAI: receipt.status={receipt.status} (het gas hoac revert)")
        print(f"    Gas used: {receipt.gasUsed:,} / {deploy_gas:,}")
        print("    -> Khong co code tai dia chi du kien. Kiem tra lai hop dong.")
        sys.exit(1)

    if not receipt.contractAddress:
        print("[-] DEPLOY THAT BAI: receipt khong co contractAddress.")
        sys.exit(1)

    on_chain_code = w3.eth.get_code(receipt.contractAddress)
    if len(on_chain_code) == 0:
        print(f"[-] DEPLOY THAT BAI: khong co bytecode tai {receipt.contractAddress}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(" 🎉 DEPLOY CONTRACT THÀNH CÔNG!")
    print(f" 📍 Contract Address : {receipt.contractAddress}")
    print(f" 🔗 Transaction Hash : {tx_hash.hex()}")
    print(f" ⛓️ Chain ID         : {chain_id}")
    print("=" * 60 + "\n")
    print(f"Gợi ý: Cập nhật DEFAULT_CONTRACT trong engine/dpki_client.py và ui/app.py thành:\n{receipt.contractAddress}")


if __name__ == "__main__":
    main()