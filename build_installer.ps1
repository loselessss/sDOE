param(
    [switch]$SkipClean,
    [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv-build-py312\Scripts\python.exe"
$InnoCompiler = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}
if (-not (Test-Path -LiteralPath $InnoCompiler)) {
    throw "Inno Setup compiler not found: $InnoCompiler"
}

Set-Location -LiteralPath $ProjectRoot

if (-not $SkipClean) {
    $cleanPaths = if ($SkipAppBuild) { @("installer_output") } else { @("build", "dist\DOE_RSM", "installer_output") }
    foreach ($relativePath in $cleanPaths) {
        $target = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $relativePath))
        if (-not $target.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean outside project: $target"
        }
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
}

if (-not $SkipAppBuild) {
    & $Python -m PyInstaller --noconfirm --clean "rsm_desktop.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "dist\DOE_RSM\DOE_RSM.exe"))) {
    throw "Desktop build not found. Run without -SkipAppBuild first."
}

& $InnoCompiler "rsm_setup.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup build failed with exit code $LASTEXITCODE"
}

$Installer = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "installer_output") -Filter "DOE_RSM_Setup_*.exe" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($null -eq $Installer) {
    throw "Installer output was not created."
}

$Hash = Get-FileHash -LiteralPath $Installer.FullName -Algorithm SHA256
Write-Host "Installer: $($Installer.FullName)"
Write-Host "SHA256: $($Hash.Hash)"
