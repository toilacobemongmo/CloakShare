"""Conftest: tu resolve anvil/solc path cho moi truong Windows."""
import os
import shutil
from pathlib import Path

import pytest

FOUNDRY_DIR = Path.home() / ".foundry"


def _ensure_foundry_on_path() -> None:
    """Dam bao anvil/forge/cast co trong PATH."""
    if shutil.which("anvil"):
        return
    if FOUNDRY_DIR.exists():
        os.environ["PATH"] = str(FOUNDRY_DIR) + os.pathsep + os.environ.get("PATH", "")
    if not shutil.which("anvil"):
        pytest.exit(
            f"anvil not found. Chay: powershell -File scripts/install_foundry_windows.ps1\n"
            f"Hoac them {FOUNDRY_DIR} vao PATH.",
            returncode=2,
        )


def _ensure_solc() -> str:
    """Dam bao solc 0.8.20 da cai qua py-solc-x."""
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
    return wanted


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_toolchain():
    """Tu dong kiem tra va setup toolchain truoc khi chay test."""
    _ensure_foundry_on_path()
    version = _ensure_solc()
    anvil_path = shutil.which("anvil")
    print(f"\n[toolchain] anvil={anvil_path} solc={version}")
    yield
