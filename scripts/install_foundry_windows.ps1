# Cai Foundry (anvil/forge/cast) cho Windows - khong can admin, khong can Rust
$ErrorActionPreference = "Stop"

$dir = "$env:USERPROFILE\.foundry"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

$zip = "$env:TEMP\foundry_win_amd64.zip"
$url = "https://github.com/foundry-rs/foundry/releases/latest/download/foundry_win_amd64.zip"

Write-Host "[*] Downloading foundry from $url ..."
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

Write-Host "[*] Extracting -> $dir"
Expand-Archive -Path $zip -DestinationPath $dir -Force

# Persist PATH cho user (khong can quyen admin)
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$dir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$dir", "User")
    Write-Host "[*] Da them $dir vao User PATH"
} else {
    Write-Host "[*] $dir da co trong User PATH"
}

# Cho session hien tai
$env:Path += ";$dir"

Write-Host "[*] Versions:"
& "$dir\anvil.exe" --version
& "$dir\forge.exe" --version
& "$dir\cast.exe" --version

Write-Host ""
Write-Host "[OK] Foundry da cai xong. Dong terminal va mo lai de PATH co hieu luc."
Write-Host "     Hoac chay ngay trong session nay: `$env:Path += ';$dir'"
