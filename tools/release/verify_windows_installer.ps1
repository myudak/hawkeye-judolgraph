param(
    [Parameter(Mandatory = $true)]
    [string]$Installer
)

$ErrorActionPreference = "Stop"
$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$installRoot = Join-Path $temporaryRoot ("hawkeye-installer-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $installRoot | Out-Null

try {
    $install = Start-Process `
        -FilePath $installerPath `
        -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$installRoot") `
        -Wait `
        -PassThru `
        -WindowStyle Hidden
    if ($install.ExitCode -ne 0) {
        throw "Installer failed with exit code $($install.ExitCode)"
    }

    $installedExecutable = Join-Path $installRoot "HAWK-EYE.exe"
    uv run python tools/release/verify_windows_bundle.py $installedExecutable
    if ($LASTEXITCODE -ne 0) {
        throw "Installed application smoke test failed"
    }

    $uninstaller = Join-Path $installRoot "unins000.exe"
    $uninstall = Start-Process `
        -FilePath $uninstaller `
        -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") `
        -Wait `
        -PassThru `
        -WindowStyle Hidden
    if ($uninstall.ExitCode -ne 0) {
        throw "Uninstaller failed with exit code $($uninstall.ExitCode)"
    }
    Write-Output "Windows installer smoke test passed"
}
finally {
    if (Test-Path -LiteralPath $installRoot) {
        $resolvedInstallRoot = [System.IO.Path]::GetFullPath($installRoot)
        if (-not $resolvedInstallRoot.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean an installer smoke path outside the temporary directory"
        }
        Remove-Item -LiteralPath $resolvedInstallRoot -Recurse -Force
    }
}
