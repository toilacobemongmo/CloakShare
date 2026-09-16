# CloakShare 🛡️
> Decentralized, Zero-Log Hybrid Cryptographic File Exchange Framework

CloakShare is a privacy-first, zero-trace file transfer framework that merges high-performance C-based symmetric encryption (AES-128-CBC) with asymmetric public-key cryptography (RSA-OAEP/PSS) and decentralized identity discovery (dPKI on EVM) over an ephemeral in-memory staging broker.

---

## 📌 Features

- **Hybrid Cryptographic Engine:** High-performance AES-128-CBC compiled in C (`core/aes128.dll` / `.so`) with PKCS#7 padding, orchestrated via Python `ctypes`.
- **Zero-Log Broker Architecture:** In-memory staging via FastAPI—data resides purely in RAM buffers with TTL autodestruction; no persistent disk writes or server-side access logs.
- **Web3 SIWE Authentication:** EIP-191 signature-based header verification (`X-Wallet-Address`, `X-Timestamp`, `X-Signature`) ensuring strictly authorized recipient retrieval and replay-attack mitigation.
- **Decentralized PKI (dPKI):** On-chain public key registry contract (`dPKIRegistry.sol`) eliminating centralized certificate authorities and manual key exchange.
- **Virtual Private Mesh Ready:** Seamless private deployment over LAN or virtual mesh networks (Tailscale/WireGuard) with local EVM testbeds.

---

## 🏗️ System Architecture

```text
[ Sender / Seller ]
    │
    ├─ 1. Query dPKI Contract on EVM Node: Retrieve Buyer's RSA Public Key (PEM)
    ├─ 2. Generate ephemeral 128-bit Session Key (AES-128) & IV
    ├─ 3. Encrypt payload using C-Core: Ciphertext = AES-128-CBC(File, SessionKey, IV)
    ├─ 4. Wrap key: WrappedKey = RSA-OAEP-Encrypt(SessionKey, Buyer_PubKey)
    ├─ 5. Sign payload: Signature = RSA-PSS-Sign(SHA256(Ciphertext), Seller_PrivKey)
    │
    ▼
[ Zero-Log RAM Broker ] ── (Ephemeral RAM Buffer: {IV, WrappedKey, Signature, Ciphertext})
    │
    ▼  [Challenge: EIP-191 Signature Verification via HTTP Headers]
[ Recipient / Buyer ]
    │
    ├─ 1. Present Web3 Wallet Signature over {tx_id} & timestamp
    ├─ 2. Retrieve staging bundle from RAM Broker
    ├─ 3. Verify integrity: RSA-PSS-Verify(SHA256(Ciphertext), Signature, Seller_PubKey)
    ├─ 4. Unwrap session key: SessionKey = RSA-OAEP-Decrypt(WrappedKey, Buyer_PrivKey)
    └─ 5. Decrypt using C-Core: Plaintext = AES-128-CBC-Decrypt(Ciphertext, SessionKey, IV)
```

---

## 📂 Project Structure

```text
CloakShare/
├── contracts/                  # Smart Contracts
│   └── dPKIRegistry.sol        # On-chain mapping (address => RSA Public Key)
├── core/                       # Lõi mật mã C thuần (FIPS-197 AES-128 & PKCS#7)
│   ├── aes128.c
│   ├── aes128.h
│   ├── padding.c
│   └── padding.h
├── engine/                     # Python Orchestration & Crypto Wrappers
│   ├── wrappers/
│   │   └── aes_wrapper.py      # ctypes bridge tới aes128.dll / libaes.so
│   ├── rsa_envelope.py         # RSA-OAEP Key Wrapping
│   ├── signer.py               # RSA-PSS Digital Signatures & Hash Verification
│   ├── wallet_auth.py          # EIP-191 SIWE Wallet Challenge & Verification
│   └── dpki_client.py          # On-chain Public Key Discovery Client
├── broker/                     # Zero-Log RAM Staging Broker
│   ├── main.py                 # FastAPI Endpoints with Auth Middleware
│   ├── memory_store.py         # In-memory dictionary with TTL auto-purge
│   └── schemas.py              # Pydantic schemas
├── scripts/                    # Deployment & Automation Scripts
│   ├── deploy_dpki.py          # Contract deployment script (Anvil / Polygon)
│   └── e2e_network_test.py     # Full E2E network verification test
├── tests/                      # Automated unit test suite
├── requirements.txt            # Python Dependencies
└── README.md
```

---

## 🚀 Quick Start

### 1. Environment Setup
Clone the repository and install dependencies:
```bash
python -m pip install -r requirements.txt
```

### 2. Compile C-Crypto Core Library
Compile the underlying C implementation into a dynamic library for `ctypes` bindings.

* **Windows (MinGW / GCC) -> `.dll`:**
```powershell
gcc -O3 -shared core/aes128.c core/padding.c -o core/aes128.dll
```

* **Linux / WSL (Ubuntu) -> `.so`:**
```bash
gcc -O3 -shared -fPIC core/aes128.c core/padding.c -o core/libaes.so
```

* **macOS -> `.dylib`:**
```bash
clang -O3 -dynamiclib core/aes128.c core/padding.c -o core/libaes.dylib
```

### 3. Run Automated Unit Tests
Verify cryptographic primitives and RAM storage:
```bash
python -m pytest tests/ -v
```

### 4. Run RAM Broker Server
Start the ephemeral in-memory staging service:
```bash
python -m uvicorn broker.main:app --port 8000 --reload
```

### 5. Run E2E Integration Test
Execute the end-to-end encryption, network staging, Web3 auth retrieval, and decryption pipeline:
```bash
python -m scripts.e2e_network_test
```

---

## 🌐 Private Mesh & Local Blockchain Setup

To run a collaborative node across multiple machines in a private virtual mesh network (e.g., Tailscale):

1. **Start Anvil EVM Node on Host:**
   ```bash
   anvil --host 0.0.0.0 --port 8545
   ```
2. **Start Broker on Host:**
   ```bash
   python -m uvicorn broker.main:app --host 0.0.0.0 --port 8000
   ```
3. **Deploy Contract:**
   Update `RPC_URL` in `scripts/deploy_dpki.py` with your Host IP (e.g., `http://100.x.y.z:8545`) and run:
   ```bash
   python -m scripts.deploy_dpki
   ```

---

## 🔐 Security Specifications

| Layer | Algorithm / Protocol | Implementation Target |
| :--- | :--- | :--- |
| **Bulk Data Cipher** | AES-128-CBC (PKCS#7) | Native C Core (`core/aes128.dll`) |
| **Session Key Exchange** | RSA-2048 (OAEP, MGF1-SHA256) | `cryptography` primitives |
| **Integrity & Origin** | SHA-256 with RSA-PSS | Strict tamper detection & non-repudiation |
| **Access Authentication** | EIP-191 Personal Sign (SIWE) | Anti-replay timestamped token in headers |
| **In-Transit Storage** | Ephemeral RAM Buffer | Zero persistent disk writes, Zero-Log |
| **Public Key Binding** | EVM Smart Contract (`dPKIRegistry`) | Decentralized identity lookup |

---

## 📜 License
This project is open-source under the [MIT License](LICENSE).
