# 🛡️ CloakShare | Zero-Log Hybrid E2E Security Platform

**CloakShare** là nền tảng trao đổi dữ liệu, tin nhắn và tệp tin mã hóa lai (Hybrid Cryptography) end-to-end kết hợp danh tính phi tập trung Web3 và máy chủ trung chuyển bộ nhớ đệm tạm thời (Zero-Log In-Memory RAM Broker).

---

## 🏛️ Ba Trụ Cột Kiến Trúc (Core Pillars)

1. **Lõi Mật Mã Lai Hiệu Năng Cao (Hybrid Crypto C-Core):**
   - **AES-128-CBC** với **PKCS#7 padding** được lập trình trực tiếp bằng C chuẩn FIPS-197 (`core/`), biên dịch thành thư viện động (`.dll` / `.so`) và kết nối qua Python `ctypes`.
   - **RSA-2048 OAEP (SHA-256):** Bọc khóa phiên làm việc (Session Key Encapsulation).
   - **RSA-PSS + SHA-256:** Chữ ký số kiểm tra toàn vẹn dữ liệu, chống giả mạo kể cả khi lệch 1 bit.

2. **Hạ Tầng Khóa Công Khai Phi Tập Trung (dPKI Blockchain):**
   - Smart Contract trên EVM (Polygon / Anvil) ánh xạ địa chỉ ví Ethereum (`0x...`) tới RSA Public Key PEM.
   - Cơ chế **Local Safe-Mode Fallback:** Tự động dự phòng và mô phỏng khi chưa khởi động node blockchain, đảm bảo hệ thống luôn hoạt động trơn tru.

3. **Máy Chủ Đệm Zero-Log (In-Memory RAM Staging Broker):**
   - Gói tin chỉ lưu trên RAM tiến trình (FastAPI heap memory), **tuyệt đối 0 lần ghi ổ cứng** (`0 disk writes`).
   - Xác thực truy cập bằng chữ ký ví Web3 chuẩn **EIP-191 (SIWE challenge)** kèm timestamp chống **Replay Attack**.
   - Cơ chế tự hủy **Burn-After-Read** và ghi đè bộ nhớ byte `0x00` (`memset zeroize`) khi hết hạn TTL hoặc sau khi nhận.

---

## 📂 Cấu Trúc Dự Án (Project Structure)

```text
CloakShare/
├── core/                       # Lõi mật mã C chuẩn FIPS-197 (AES-128 & PKCS#7)
│   ├── aes128.c
│   ├── aes128.h
│   ├── padding.c
│   ├── padding.h
│   └── Makefile
├── engine/                     # Tầng điều phối & Wrappers Python
│   ├── wrappers/
│   │   └── aes_wrapper.py      # ctypes binding trực tiếp tới aes128.dll / libaes.so
│   ├── rsa_envelope.py         # RSA-OAEP Key Wrapping
│   ├── signer.py               # RSA-PSS Digital Signatures
│   ├── wallet_auth.py          # Web3 SIWE EIP-191 Challenge Signing & Verification
│   ├── dpki_client.py          # On-chain / Safe-Mode Public Key Registry Client
│   ├── cli_adapter.py          # Adapter hỗ trợ xử lý mã hóa in-memory cho CLI/UI
│   └── cli.py                  # Giao diện dòng lệnh toàn diện (keygen, reg, send, recv)
├── broker/                     # Trạm trung chuyển Zero-Log RAM Broker
│   ├── main.py                 # FastAPI Application (CORS, SIWE Auth, Burn-After-Read)
│   ├── memory_store.py         # In-memory dictionary kèm memset zeroize tự hủy
│   └── schemas.py              # Pydantic Schemas & RAM Metrics
├── ui/                         # Giao diện Web Người Dùng (Streamlit Dark Cyber Theme)
│   └── app.py                  # Messenger E2E, CloakDrop Vault, Monitor Dashboard, Key Studio
├── contracts/                  # Smart Contract Solidity dPKI
│   └── dPKIRegistry.sol
├── scripts/                    # Kịch bản kiểm thử tích hợp mạng & deploy
│   ├── deploy_dpki.py
│   └── e2e_network_test.py
├── tests/                      # Suite kiểm thử tự động (Pytest 35/35 Passed)
│   ├── test_aes_wrapper.py
│   ├── test_rsa_envelope.py
│   ├── test_signer.py
│   ├── test_broker_api.py
│   └── test_e2e_pipeline.py
├── demo_full_flow.py           # Kịch bản kiểm tra nhanh luồng mã hóa cục bộ
├── requirements.txt            # Thư viện phụ thuộc
├── CONTRIBUTING.md             # Hướng dẫn đóng góp & Quy chuẩn bảo mật
└── README.md
```

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng

### 1. Cài đặt môi trường Python
```bash
python -m pip install -r requirements.txt
```

### 2. Biên dịch thư viện C (Nếu chưa có file DLL / SO)
* **Windows (MinGW / GCC):**
```powershell
gcc -O3 -shared core/aes128.c core/padding.c -o core/aes128.dll
```
* **Linux / Ubuntu / WSL:**
```bash
gcc -O3 -shared -fPIC core/aes128.c core/padding.c -o core/libaes.so
```
* **macOS:**
```bash
clang -O3 -dynamiclib core/aes128.c core/padding.c -o core/libaes.dylib
```

---

### 3. Chạy Toàn Bộ Bộ Kiểm Thử Tự Động (35 Tests)
```bash
python -m pytest tests/ -v
```
Toàn bộ 35 bài kiểm thử bao gồm kiểm tra: Lõi C AES, bọc khóa RSA-OAEP, ký số RSA-PSS, Zero-Log RAM Broker, xác thực ví Web3 SIWE, chống Replay Attack, Burn-after-read, và kiểm chứng nghiêm ngặt **0 disk writes**.

---

### 4. Khởi Chạy Máy Chủ Đệm Zero-Log Broker
Chạy Broker trong chế độ chuẩn Zero-Log (tắt access log để không lộ `tx_id`):
```bash
python -m uvicorn broker.main:app --port 8000 --no-access-log
```
> API Docs (Swagger): `http://127.0.0.1:8000/docs`

---

### 5. Khởi Chạy Giao Diện Người Dùng Hiện Đại (Streamlit)
Mở một cửa sổ dòng lệnh khác và chạy:
```bash
python -m streamlit run ui/app.py
```
Giao diện sẽ tự động mở trên trình duyệt tại `http://localhost:8501`, cung cấp 4 phân hệ:
1. **💬 Tin Nhắn E2E (Messenger):** Trò chuyện mã hóa hai chiều, gửi kèm tệp tin với chữ ký số xác thực.
2. **📦 CloakDrop (File Vault):** Chia sẻ file bí mật bằng mã Ticket ID, tùy chỉnh thời gian sống TTL và tự hủy ngay sau khi tải (Burn-After-Read).
3. **📊 Giám Sát Zero-Log & dPKI:** Giám sát thời gian thực số lượng payload trên RAM, dung lượng bộ nhớ sử dụng và cam kết 0 lần ghi ổ cứng.
4. **🔑 Quản Lý Khóa & Danh Tính Web3:** Quản lý cặp khóa RSA 2048-bit, địa chỉ ví Ethereum, tra cứu và đăng ký lên dPKI.

---

### 6. Sử Dụng Qua Dòng Lệnh (CLI)

#### a. Tạo cặp khóa RSA 2048-bit:
```bash
python engine/cli.py keygen --out my_keys
```

#### b. Đăng ký Public Key lên dPKI:
```bash
python engine/cli.py register --pub my_keys/public.pem --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
```

#### c. Mã hóa & Gửi file (Seller):
```bash
python engine/cli.py send --file document.pdf --to 0x70997970c51812dc3a010c7d01b50e0d17dc79c8 --ttl 300
```

#### d. Tải & Giải mã file an toàn trên RAM (Buyer):
```bash
python engine/cli.py receive --tx <TX_ID> --out received.pdf --wallet-key 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d --priv-key my_keys/private.pem --burn
```

---

## 🔒 Cam Kết Bảo Mật (Security Compliance)

- **Zero-Disk-Persistence:** Dữ liệu mật mã trong quá trình xử lý, truyền nhận và giải mã luôn nằm hoàn toàn trong RAM heap.
- **Memset Zeroize:** Khi purge hoặc hết hạn TTL, các mảng byte nhạy cảm được ghi đè bằng `0x00`.
- **Chống Giả Mạo (Integrity Guaranteed):** Mọi gói tin đều được bảo vệ bởi RSA-PSS SHA-256. Bất kỳ sự can thiệp dù chỉ 1 bit đều bị từ chối giải mã.
- **Chống Replay Attack:** Chữ ký ví Web3 đi kèm timestamp với ngưỡng lệch cho phép tối đa 60 giây.