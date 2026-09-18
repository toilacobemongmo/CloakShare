from engine.dpki_client import DPKIClient

# Thay chuỗi mẫu bằng địa chỉ contract thật vừa deploy xong
dpki = DPKIClient(
    contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",  # Hoặc địa chỉ trên máy bạn
    rpc_url="http://127.0.0.1:8545"
)

wallet_address = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
dummy_pub_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----"

print("Đã khởi tạo DPKIClient thành công với contract address hợp lệ.")
# Gọi hàm đăng ký (dùng private key tương ứng)
# tx_hash = dpki.register_key(wallet_address, dummy_pub_key, private_key="0xac0974...")

# Tra cứu lại xem có lấy đúng không
# retrieved_key = dpki.get_public_key(wallet_address)
# print(retrieved_key)