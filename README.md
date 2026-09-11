# CloakShare 🛡️
> Decentralized, Zero-Log Hybrid Cryptographic File Exchange Framework

CloakShare is a privacy-focused, zero-trace file exchange system that combines low-level symmetric encryption (AES-128) with public-key cryptography and Web3 identity discovery to enable secure, confidential file sharing without central logging.

---

## 📌 Features

- **Hybrid Encryption Pipeline:** High-performance symmetric file encryption paired with asymmetric session key encapsulation.
- **Zero-Log Broker Architecture:** Ephemeral in-memory staging—files transit strictly through memory buffers without touching persistent server disks.
- **Tamper-Proof & Non-Repudiation:** Cryptographic digital signatures guarantee data integrity and sender identity verification.
- **Decentralized PKI (dPKI) Ready:** Architecture tailored for public-key binding and lookup via Ethereum/Polygon Smart Contracts.

---

## 🏗️ System Architecture

```text
[ Seller ]
    │
    ├─ 1. Generate random Session Key (AES-128)
    ├─ 2. Encrypt file: Ciphertext = AES_Encrypt(File, SessionKey)
    ├─ 3. Wrap key: EncryptedKey = RSA_Encrypt(SessionKey, Buyer_PubKey)
    ├─ 4. Sign file hash: Signature = Sign(SHA256(File), Seller_PrivKey)
    │
    ▼
[ CloakShare Broker ] ── (Zero-Log RAM Buffer: {IV, EncryptedKey, Signature, Ciphertext})
    │
    ▼
[ Buyer ]
    │
    ├─ 1. Unwrap key: SessionKey = RSA_Decrypt(EncryptedKey, Buyer_PrivKey)
    ├─ 2. Decrypt file: Plaintext = AES_Decrypt(Ciphertext, SessionKey)
    └─ 3. Verify signature: Verify(SHA256(Plaintext), Signature, Seller_PubKey)
```

---

## ⚙️ Mathematical & Cryptographic Workflow

### 1. Sender Packaging (Encryption & Signing)
1. Read binary source data $M$.
2. Generate ephemeral 128-bit key $K_{session}$ and 16-byte initialization vector $IV$.
3. Apply PKCS#7 padding:
   $$M_{padded} = \text{Pad}(M)$$
4. Compute symmetric ciphertext:
   $$C = \text{AES-128-CBC-Encrypt}(M_{padded}, K_{session}, IV)$$
5. Encapsulate session key with recipient's public key $PK_{buyer}$:
   $$EK = \text{RSA-OAEP-Encrypt}(K_{session}, PK_{buyer})$$
6. Compute SHA-256 hash and digital signature using sender's private key $SK_{seller}$:
   $$S = \text{Sign}(H(M), SK_{seller}) \quad \text{where } H = \text{SHA-256}$$
7. Construct broker payload:
   $$\text{Payload} = \{IV, EK, S, C\}$$

### 2. Recipient Unpacking (Decryption & Verification)
1. Parse the incoming payload into components: $IV$, $EK$, $S$, $C$.
2. Decapsulate the symmetric session key:
   $$K_{session} = \text{RSA-OAEP-Decrypt}(EK, SK_{buyer})$$
3. Decrypt ciphertext back to padded plaintext:
   $$M_{padded} = \text{AES-128-CBC-Decrypt}(C, K_{session}, IV)$$
4. Strip PKCS#7 padding to retrieve raw message $M$.
5. Verify sender integrity:
   $$\text{Verify}(H(M), S, PK_{seller}) \stackrel{?}{=} \text{VALID}$$

---

## 📂 Project Structure

```text
CloakShare/
├── aes128.c            # Core AES-128 symmetric encryption implementation
├── aes128.h            # Header file for AES primitives and state matrix
├── crypto_engine.py    # High-level orchestration (Hybrid packing & unpacking)
├── broker.py           # In-memory Zero-Log staging broker
└── README.md           # Project documentation
```

---

## 🚀 Quick Start

### 1. Build AES-128 Primitives (C)
Compile the C implementation into an object file or shared library:
```bash
gcc -O2 -c aes128.c -o aes128.o
```

To compile as a shared library for Python integration:
```bash
gcc -shared -o libaes128.so -fPIC aes128.c
```

### 2. Run Hybrid Cryptographic Engine (Python)
Install cryptographic prerequisites:
```bash
pip install cryptography
```

Run test suite:
```bash
python crypto_engine.py
```

---

## 🔐 Security Specifications

| Layer | Algorithm / Standard | Purpose |
| :--- | :--- | :--- |
| **Bulk Encryption** | AES-128 (CBC/GCM Mode) | Payload confidentiality |
| **Key Encapsulation** | RSA-2048 (OAEP) / ECC | Session Key distribution |
| **Integrity & Origin** | SHA-256 with PSS Padding | Non-repudiation & tamper checks |
| **Storage Security** | Ephemeral Memory (`/dev/shm`) | Zero-Log broker purging |

---

## 📜 License
This project is open-source under the [MIT License](LICENSE).
