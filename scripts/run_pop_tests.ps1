# Script chay test PoP validation - tu dong cai Foundry + solc neu thieu
$ErrorActionPreference = "Stop"

Write-Host "[*] Checking Foundry (anvil/forge)..."
$foundryDir = "$env:USERPROFILE\.foundry"
$anvilPath = "$foundryDir\anvil.exe"

if (-not (Test-Path $anvilPath)) {
    Write-Host "[!] Foundry chua cai. Dang cai tu dong..."
    & powershell -ExecutionPolicy Bypass -File "scripts/install_foundry_windows.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Khong cai duoc Foundry. Kiem tra ket noi internet."
        exit 1
    }
}

# Dam bao PATH co foundry trong session hien tai
if ($env:Path -notlike "*$foundryDir*") {
    $env:Path += ";$foundryDir"
}

Write-Host "[*] Checking py-solc-x..."
python -c "import solcx" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] py-solc-x chua cai. Dang cai..."
    pip install py-solc-x
}

Write-Host "[*] Installing solc 0.8.20 via py-solc-x..."
python -c "import solcx; solcx.install_solc('0.8.20'); print('[OK] solc', solcx.get_solc_version())"

Write-Host ""
Write-Host "[*] Running PoP validation tests..."
Write-Host ""
pytest tests/test_pop_validation.py -v -s --tb=short

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] Tat ca test cases PASS!"
} else {
    Write-Host ""
    Write-Host "[FAIL] Co loi trong qua trinh test. Xem log phia tren."
    exit 1
}
