param(
    [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv-build-py312\Scripts\python.exe"
$SetupScript = Join-Path $ProjectRoot "rsm_setup.iss"
$DistDir = Join-Path $ProjectRoot "dist\DOE_RSM"
$OutputRoot = Join-Path $ProjectRoot "portable_output"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python executable not found: $Python"
}

$setupText = Get-Content -LiteralPath $SetupScript -Raw -Encoding UTF8
$versionMatch = [regex]::Match($setupText, '#define MyAppVersion "([^"]+)"')
if (-not $versionMatch.Success) {
    throw "Could not read MyAppVersion from rsm_setup.iss"
}
$Version = $versionMatch.Groups[1].Value
$PortableName = "DOE_RSM_Portable_$Version"
$PortableDir = Join-Path $OutputRoot $PortableName
$ZipPath = Join-Path $OutputRoot "$PortableName.zip"

Set-Location -LiteralPath $ProjectRoot

if (-not $SkipAppBuild) {
    & $Python -m PyInstaller --noconfirm --clean "rsm_desktop.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $DistDir "DOE_RSM.exe"))) {
    throw "Desktop build not found: $DistDir"
}

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputRoot)
$resolvedProject = [System.IO.Path]::GetFullPath($ProjectRoot)
if (-not $resolvedOutput.StartsWith($resolvedProject, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write outside project: $resolvedOutput"
}
if (Test-Path -LiteralPath $OutputRoot) {
    Remove-Item -LiteralPath $OutputRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $PortableDir -Force | Out-Null
Copy-Item -Path (Join-Path $DistDir "*") -Destination $PortableDir -Recurse -Force
New-Item -ItemType File -Path (Join-Path $PortableDir "portable.flag") -Force | Out-Null

$Readme = @"
sDOE Portable $Version

[한국어]
1. 압축을 원하는 폴더에 풉니다.
2. DOE_RSM.exe를 실행합니다.
3. 첫 실행에서 한국어 또는 International (English)을 선택합니다.
4. 설정, 로그, WebView 데이터는 이 폴더의 data 안에 저장됩니다.
5. 프로그램 폴더 전체에 쓰기 권한이 있는 위치에서 사용하세요.

[English]
1. Extract the ZIP to a writable folder.
2. Run DOE_RSM.exe.
3. Select Korean or International (English) on first launch.
4. Settings, logs, and WebView data remain in the local data folder.
5. Keep the entire folder together when moving the app.

Windows WebView2 Runtime is required.
"@
[System.IO.File]::WriteAllText((Join-Path $PortableDir "README_PORTABLE.txt"), $Readme, [System.Text.UTF8Encoding]::new($true))

Compress-Archive -LiteralPath $PortableDir -DestinationPath $ZipPath -CompressionLevel Optimal
$Hash = Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256
$SizeMb = [math]::Round((Get-Item -LiteralPath $ZipPath).Length / 1MB, 2)
Write-Host "Portable ZIP: $ZipPath"
Write-Host "Size: $SizeMb MB"
Write-Host "SHA256: $($Hash.Hash)"
