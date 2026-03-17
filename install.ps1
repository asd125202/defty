# Defty one-line installer — Windows (PowerShell)
#
# Usage (run in PowerShell as normal user — no admin required):
#   irm https://raw.githubusercontent.com/asd125202/defty/main/install.ps1 | iex
#
# What this does:
#   1. Installs uv (the fast Python package manager)
#   2. Installs Python 3.12 via uv
#   3. Detects your GPU (NVIDIA → CUDA torch; no GPU → CPU torch)
#   4. Installs the `defty` CLI with the right torch wheel
#   5. Adds defty to your PATH

$ErrorActionPreference = "Stop"

$DEFTY_REPO   = "https://github.com/asd125202/defty.git"
$PYTHON_VER   = "3.12"

function Write-Info    { param($m) Write-Host "[defty] $m" -ForegroundColor Cyan }
function Write-Success { param($m) Write-Host "[defty] $m" -ForegroundColor Green }
function Write-Warn    { param($m) Write-Host "[defty] $m" -ForegroundColor Yellow }
function Write-Fail    { param($m) Write-Host "[defty] ERROR: $m" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  DEFTY - Physical AI IDE - Windows Installer" -ForegroundColor Cyan
Write-Host ""

# ── Detect arch ──────────────────────────────────────────────────────────────
$arch = $env:PROCESSOR_ARCHITECTURE
if ($arch -notin @("AMD64", "ARM64")) {
    Write-Fail "Unsupported architecture: $arch"
}
Write-Info "Detected: Windows ($arch)"

# ── Detect NVIDIA GPU ────────────────────────────────────────────────────────
$hasNvidia = $false
$gpuName   = ""
try {
    $nvsmi = Get-Command nvidia-smi -ErrorAction Stop
    $gpuName = (nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1).Trim()
    if ($LASTEXITCODE -eq 0 -and $gpuName) {
        $hasNvidia = $true
    }
} catch {}

if ($hasNvidia) {
    Write-Info "GPU detected: $gpuName  →  will install CUDA-enabled torch"
} else {
    Write-Info "No NVIDIA GPU detected  →  will install CPU-only torch"
}

# ── Step 1: Install uv ───────────────────────────────────────────────────────
Write-Info "Step 1/3 - Installing uv (Python package manager)..."

$uvPath = Get-Command uv -ErrorAction SilentlyContinue
if ($uvPath) {
    $uvVer = (uv --version 2>&1) -replace "uv ", ""
    Write-Info "uv already installed ($uvVer), skipping."
} else {
    try {
        # Official uv installer for Windows
        $uvInstallScript = Invoke-RestMethod "https://astral.sh/uv/install.ps1"
        Invoke-Expression $uvInstallScript
    } catch {
        Write-Fail "Failed to install uv: $_`nInstall manually: https://docs.astral.sh/uv/getting-started/installation/"
    }

    # Refresh PATH in current session
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    $env:PATH = "$userPath;$env:PATH"

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Fail "uv installed but not found on PATH. Please restart PowerShell and re-run this script."
    }
    Write-Success "uv installed."
}

# ── Step 2: Install Python 3.12 ──────────────────────────────────────────────
Write-Info "Step 2/3 - Installing Python $PYTHON_VER via uv..."
uv python install $PYTHON_VER
Write-Success "Python $PYTHON_VER ready."

# ── Step 3: Install defty (GPU-aware) ────────────────────────────────────────
if ($hasNvidia) {
    Write-Info "Step 3/3 - Installing defty with CUDA support ($gpuName)..."
    uv tool install "defty[cuda] @ git+$DEFTY_REPO" --python $PYTHON_VER --force
} else {
    Write-Info "Step 3/3 - Installing defty (CPU)..."
    uv tool install "git+$DEFTY_REPO" --python $PYTHON_VER --force
}
Write-Success "defty installed."

# ── PATH setup ────────────────────────────────────────────────────────────────
$uvToolsBin = (uv tool dir 2>$null) + "\bin"
$currentUserPath = [Environment]::GetEnvironmentVariable("PATH", "User")

if ($currentUserPath -notlike "*$uvToolsBin*") {
    Write-Warn "Adding $uvToolsBin to user PATH..."
    [Environment]::SetEnvironmentVariable(
        "PATH",
        "$currentUserPath;$uvToolsBin",
        "User"
    )
    $env:PATH = "$env:PATH;$uvToolsBin"
    Write-Warn "PATH updated. You may need to restart your terminal."
}

# ── Verify ───────────────────────────────────────────────────────────────────
Write-Host ""
$deftyCmd = Get-Command defty -ErrorAction SilentlyContinue
if ($deftyCmd) {
    $deftyVer = defty --version 2>&1
    Write-Success "Installation complete!  $deftyVer"
    if ($hasNvidia) {
        Write-Success "CUDA training enabled on: $gpuName"
    }
    Write-Host ""
    Write-Host "  Quick start:" -ForegroundColor White
    Write-Host "    mkdir my-robot; cd my-robot"
    Write-Host "    defty init"
    Write-Host "    defty scan ports"
    Write-Host "    defty scan cameras"
    Write-Host ""
} else {
    Write-Warn "defty installed but not yet on PATH."
    Write-Warn "Restart PowerShell, then run: defty --version"
}