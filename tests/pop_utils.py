"""Helper parse output deploy_dpki.py + quản lý node Anvil cho test PoP.

Tồn tại vì:
- deploy_dpki.py in emoji (📍🔗⛓️); dưới cp1252 chúng thành '?' nên
  label-matching kiểu "Contract Address" là fragile.
- Windows subprocess mặc định cp1252 -> cần ép UTF-8 ở CẢ HAI phía.
- Anvil --block-time 1 ghi log liên tục; nếu Popen(stdout=PIPE) mà không
  drain thì pipe 64KB đầy và node treo giữa test.
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
from typing import Optional

ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}")
MARKER = "__CONTRACT_ADDRESS__="

_LABEL_RE = re.compile(
    r"(contract\s*address|contract\s*deployed\s*at|"
    r"địa\s*chỉ\s*smart\s*contract|dia\s*chi\s*smart\s*contract)",
    re.IGNORECASE,
)


def child_env() -> dict:
    """Env cho subprocess con: buộc UTF-8, không buffer."""
    env = {**os.environ}
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("PYTHONLEGACYWINDOWSSTDIO", "0")
    return env


def port_open(host: str = "127.0.0.1", port: int = 8545, timeout: float = 0.25) -> bool:
    """Kiểm tra nhanh xem port có đang listen không."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def wait_for_port(host: str = "127.0.0.1", port: int = 8545, timeout: float = 20.0) -> bool:
    """Chờ port sẵn sàng (cho Anvil khởi động)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(host, port):
            return True
        time.sleep(0.15)
    return False


def parse_contract_address(stdout: str, stderr: str = "") -> Optional[str]:
    """Bóc địa chỉ contract theo 4 tầng ưu tiên, không phụ thuộc emoji.
    
    1. Machine marker: __CONTRACT_ADDRESS__=0x...
    2. JSON line: {"contract_address": "0x..."}
    3. Dòng có label: "Contract Address : 0x..."
    4. Fallback: địa chỉ cuối cùng trong stdout (vì deploy_dpki.py in gợi ý ở cuối)
    """
    blob = f"{stdout}\n{stderr}"

    # 1) machine marker (nguồn tin cậy nhất)
    for line in blob.splitlines():
        line = line.strip()
        if line.startswith(MARKER):
            cand = line[len(MARKER):].strip()
            if ADDR_RE.fullmatch(cand):
                return cand

    # 2) JSON line (deploy_dpki.py --json)
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            for key in ("contract_address", "contractAddress", "address"):
                val = obj.get(key)
                if isinstance(val, str) and ADDR_RE.fullmatch(val):
                    return val

    # 3) dòng có label (đã chuẩn hoá, chịu được emoji bị thay bằng '?')
    for line in stdout.splitlines():
        if _LABEL_RE.search(line):
            m = ADDR_RE.search(line)
            if m:
                return m.group(0)

    # 4) fallback: address cuối cùng trong output
    #    (deploy_dpki.py in gợi ý cập nhật DEFAULT_CONTRACT ở cuối -> đúng contract)
    hits = ADDR_RE.findall(stdout)
    if hits:
        return hits[-1]
    return None
