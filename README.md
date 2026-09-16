## 📂 Project Structure

```text
CloakShare/
├── core/                       # Lõi mật mã C (FIPS-197 AES & PKCS#7)
│   ├── aes128.c
│   ├── aes128.h
│   ├── padding.c
│   └── padding.h
├── engine/                     # Python Orchestration & Wrappers
│   ├── wrappers/
│   │   └── aes_wrapper.py      # ctypes binding tới aes128.dll / libaes.so
│   ├── rsa_envelope.py         # RSA-OAEP Key Wrapping
│   ├── signer.py               # RSA-PSS Digital Signatures
│   ├── wallet_auth.py          # Web3 Wallet Signature & Verification
│   └── dpki_client.py          # On-chain Public Key Discovery
├── broker/                     # Zero-Log RAM Staging Service
│   ├── main.py                 # FastAPI Application Endpoints
│   ├── memory_store.py         # In-memory dictionary with secure wipe
│   └── schemas.py              # Pydantic Payload Validation
├── scripts/                    # Kịch bản kiểm thử E2E tích hợp mạng
│   └── e2e_network_test.py
├── tests/                      # Pytest Automated Test Suite
├── requirements.txt            # Python Dependencies
└── README.md
```

---

## 🚀 Quick Start

### 1. Environment Setup
Clone the repository and install all required dependencies:
```bash
python -m pip install -r requirements.txt
```

### 2. Compile C-Crypto Core Library
Compile the underlying C implementation into a shared dynamic library for Python `ctypes` bindings.

* **On Windows (MinGW / GCC) -> Generate `.dll`:**
```powershell
gcc -O3 -shared core/aes128.c core/padding.c -o core/aes128.dll
```

* **On Linux / WSL (Ubuntu) -> Generate `.so`:**
```bash
gcc -O3 -shared -fPIC core/aes128.c core/padding.c -o core/libaes.so
```

* **On macOS -> Generate `.dylib`:**
```bash
clang -O3 -dynamiclib core/aes128.c core/padding.c -o core/libaes.dylib
```

### 3. Run Automated Tests
Execute the full unit test suite (Core Wrapper, RSA Envelope, Signer, and RAM Broker):
```bash
python -m pytest tests/ -v
```

### 4. Run End-to-End Network Pipeline
Launch the RAM Broker in one terminal:
```bash
python -m uvicorn broker.main:app --port 8000 --reload
```

Run the end-to-end encryption, network staging, and decryption workflow in another terminal:
```bash
python -m scripts.e2e_network_test
```