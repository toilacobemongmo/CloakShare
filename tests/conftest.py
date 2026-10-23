"""Conftest: tu resolve anvil/solc path cho moi truong Windows."""
import os
import shutil
from pathlib import Path

import pytest

# BUG ĐÃ SỬA: trước đây chỉ thêm `~/.foundry`, nhưng foundryup cài binary vào
# `~/.foundry/bin`. Hệ quả: `shutil.which("anvil")` vẫn trả None và toàn bộ
# test run bị `pytest.exit()` chặn dù anvil đã cài đúng.
FOUNDRY_DIRS = [
    Path.home() / ".foundry" / "bin",
    Path.home() / ".foundry",
    Path(r"C:\Users\Public\foundry\bin"),
]


def _ensure_foundry_on_path() -> None:
    """Dam bao anvil/forge/cast co trong PATH."""
    if shutil.which("anvil"):
        return
    for d in FOUNDRY_DIRS:
        if d.is_dir():
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
            if shutil.which("anvil"):
                break
    if not shutil.which("anvil"):
        pytest.exit(
            "anvil not found. Chay: powershell -File scripts/install_foundry_windows.ps1\n"
            f"Hoac them mot trong cac thu muc sau vao PATH: "
            + ", ".join(str(d) for d in FOUNDRY_DIRS),
            returncode=2,
        )


def _ensure_solc() -> str:
    """Dam bao solc 0.8.20 da cai qua py-solc-x.

    BUG ĐÃ SỬA: `tests/test_pop_validation.py` (bản cũ) gọi thẳng
    `subprocess.run(["solc", "--bin", ...])` — tức là cần `solc.exe` CÓ TRONG
    PATH. py-solc-x cài binary vào `~/.solcx/solc-v0.8.20/solc.exe`, không hề
    đăng ký PATH. Trước đây conftest chỉ `set_solc_version()` (đủ cho
    `compile_standard` nhưng KHÔNG đủ cho subprocess) nên 4 test trong file cũ
    luôn ERROR với `FileNotFoundError`.
    """
    try:
        import solcx
    except ImportError:
        pytest.exit("Thieu py-solc-x. Chay: pip install py-solc-x", returncode=2)

    wanted = "0.8.20"
    installed = [str(v) for v in solcx.get_installed_solc_versions()]
    if wanted not in installed:
        print(f"[conftest] Installing solc {wanted}...")
        solcx.install_solc(wanted)
    solcx.set_solc_version(wanted)

    # Thêm thư mục chứa solc.exe vào PATH cho các test gọi subprocess trực tiếp.
    solc_bin = Path.home() / ".solcx" / f"solc-v{wanted}" / (
        "solc.exe" if os.name == "nt" else "solc"
    )
    if solc_bin.is_file() and not shutil.which("solc"):
        os.environ["PATH"] = str(solc_bin.parent) + os.pathsep + os.environ.get("PATH", "")
    return wanted


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_toolchain():
    """Tu dong kiem tra va setup toolchain truoc khi chay test."""
    _ensure_foundry_on_path()
    version = _ensure_solc()
    anvil_path = shutil.which("anvil")
    print(f"\n[toolchain] anvil={anvil_path} solc={version}")
    yield
