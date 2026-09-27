"""
scripts/benchmark_crypto.py

Bộ đo lường hiệu năng mật mã (Cryptographic Performance Benchmark Suite) cho CloakShare:
- Đo thông lượng (Throughput MB/s) của C-Core AES-128-CBC
- Đo tốc độ bọc/mở bọc khóa RSA-2048 OAEP (ops/sec)
- Đo tốc độ ký/xác thực số RSA-PSS SHA-256 (ops/sec)
- Đo tốc độ ký xác thực ví Web3 SIWE EIP-191 (ops/sec)
- Đo độ trễ toàn trình luồng Hybrid Pipeline (Latency ms)
"""

import os
import sys
import time
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

from eth_account import Account
from engine.wrappers.aes_wrapper import AESWrapper
from engine.rsa_envelope import RSAEnvelope, generate_rsa_key_pair
from engine.signer import IntegritySigner
from engine.wallet_auth import Web3Auth


def benchmark_aes():
    print("\n" + "=" * 65)
    print(" 🚀 BENCHMARK: C-CORE AES-128-CBC & PKCS#7 (FIPS-197)")
    print("=" * 65)
    aes = AESWrapper()
    sizes = [
        ("1 KB", 1024, 2000),
        ("64 KB", 64 * 1024, 300),
        ("1 MB", 1024 * 1024, 30),
        ("10 MB", 10 * 1024 * 1024, 5),
    ]

    print(f"{'Kích thước':<12} | {'Enc Speed (MB/s)':<18} | {'Dec Speed (MB/s)':<18} | {'Chu kỳ'}")
    print("-" * 65)

    results = []
    for label, size_bytes, iters in sizes:
        raw = os.urandom(size_bytes)
        key = os.urandom(16)

        # Đo Encrypt
        t0 = time.perf_counter()
        iv, cipher = None, None
        for _ in range(iters):
            iv, cipher = aes.encrypt(raw, key)
        t_enc = time.perf_counter() - t0
        enc_mbs = (size_bytes * iters / (1024 * 1024)) / t_enc

        # Đo Decrypt
        t0 = time.perf_counter()
        for _ in range(iters):
            _ = aes.decrypt(cipher, key, iv)
        t_dec = time.perf_counter() - t0
        dec_mbs = (size_bytes * iters / (1024 * 1024)) / t_dec

        print(f"{label:<12} | {enc_mbs:>14.2f} MB/s | {dec_mbs:>14.2f} MB/s | {iters} lần")
        results.append((label, enc_mbs, dec_mbs))

    return results


def benchmark_rsa_and_signatures():
    print("\n" + "=" * 65)
    print(" 🔐 BENCHMARK: ASYMMETRIC CRYPTO & DIGITAL SIGNATURES")
    print("=" * 65)

    priv_bytes, pub_bytes = generate_rsa_key_pair()
    priv_pem = priv_bytes.decode("utf-8")
    pub_pem = pub_bytes.decode("utf-8")
    session_key = os.urandom(16)
    sample_data = os.urandom(1024)

    # 1. RSA-2048 OAEP Key Wrapping
    iters = 200
    t0 = time.perf_counter()
    wrapped = None
    for _ in range(iters):
        wrapped = RSAEnvelope.wrap_key(session_key, pub_pem)
    t_wrap = time.perf_counter() - t0
    wrap_ops = iters / t_wrap

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = RSAEnvelope.unwrap_key(wrapped, priv_pem)
    t_unwrap = time.perf_counter() - t0
    unwrap_ops = iters / t_unwrap

    print(f"RSA-2048 OAEP Wrap Key     : {wrap_ops:>8.1f} ops/sec ({t_wrap / iters * 1000:.2f} ms/op)")
    print(f"RSA-2048 OAEP Unwrap Key   : {unwrap_ops:>8.1f} ops/sec ({t_unwrap / iters * 1000:.2f} ms/op)")

    # 2. RSA-PSS SHA-256 Signatures
    t0 = time.perf_counter()
    sig = None
    for _ in range(iters):
        sig = IntegritySigner.sign_file(sample_data, priv_pem)
    t_sign = time.perf_counter() - t0
    sign_ops = iters / t_sign

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = IntegritySigner.verify_file(sample_data, sig, pub_pem)
    t_verify = time.perf_counter() - t0
    verify_ops = iters / t_verify

    print(f"RSA-PSS SHA-256 Sign       : {sign_ops:>8.1f} ops/sec ({t_sign / iters * 1000:.2f} ms/op)")
    print(f"RSA-PSS SHA-256 Verify     : {verify_ops:>8.1f} ops/sec ({t_verify / iters * 1000:.2f} ms/op)")

    # 3. Web3 EIP-191 Auth Challenge
    acc = Account.create()
    msg = Web3Auth.create_retrieve_message("tx-benchmark-test", int(time.time()))
    t0 = time.perf_counter()
    w3_sig = None
    for _ in range(iters):
        w3_sig = Web3Auth.sign_challenge(acc.key.hex(), msg)
    t_w3_sign = time.perf_counter() - t0
    w3_sign_ops = iters / t_w3_sign

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = Web3Auth.verify_signature(acc.address, msg, w3_sig)
    t_w3_ver = time.perf_counter() - t0
    w3_ver_ops = iters / t_w3_ver

    print(f"Web3 EIP-191 Challenge Sign: {w3_sign_ops:>8.1f} ops/sec ({t_w3_sign / iters * 1000:.2f} ms/op)")
    print(f"Web3 EIP-191 Recover/Verify: {w3_ver_ops:>8.1f} ops/sec ({t_w3_ver / iters * 1000:.2f} ms/op)")


def benchmark_e2e_latency():
    print("\n" + "=" * 65)
    print(" ⚡ BENCHMARK: END-TO-END HYBRID PIPELINE LATENCY")
    print("=" * 65)

    aes = AESWrapper()
    alice_priv, alice_pub = generate_rsa_key_pair()
    bob_priv, bob_pub = generate_rsa_key_pair()
    b_pub = bob_pub.decode("utf-8")
    b_priv = bob_priv.decode("utf-8")
    a_pub = alice_pub.decode("utf-8")
    a_priv = alice_priv.decode("utf-8")

    sample_sizes = [("1 KB", 1024), ("64 KB", 64 * 1024), ("1 MB", 1024 * 1024)]
    iters = 50

    for label, sz in sample_sizes:
        data = os.urandom(sz)
        t0 = time.perf_counter()
        for _ in range(iters):
            # 1. AES Encrypt (C)
            session_key = os.urandom(16)
            iv, ct = aes.encrypt(data, session_key)
            # 2. RSA Wrap
            wk = RSAEnvelope.wrap_key(session_key, b_pub)
            # 3. RSA Sign
            sig = IntegritySigner.sign_file(ct, a_priv)
            # 4. Verify Signature
            assert IntegritySigner.verify_file(ct, sig, a_pub) is True
            # 5. Unwrap Key
            rk = RSAEnvelope.unwrap_key(wk, b_priv)
            # 6. AES Decrypt (C)
            pt = aes.decrypt(ct, rk, iv)
            assert pt == data
        total_time = time.perf_counter() - t0
        avg_ms = (total_time / iters) * 1000
        print(f"Payload {label:<6}: {avg_ms:.2f} ms/chu kỳ hoàn chỉnh (Mã hóa + Ký + Xác thực + Mở khóa + Giải mã)")

    print("=" * 65 + "\n")


def main():
    benchmark_aes()
    benchmark_rsa_and_signatures()
    benchmark_e2e_latency()


if __name__ == "__main__":
    main()
