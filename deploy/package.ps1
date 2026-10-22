#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$AppDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$stage = Join-Path $env:TEMP ("QueueMail-stage-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stage | Out-Null

$files = @(
    "app.py",
    "serve.py",
    "np_rules.json",
    "requirements.txt",
    "server.json",
    "signature.txt",
    "README.md"
)
foreach ($name in $files) {
    $src = Join-Path $AppDir $name
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $stage $name)
    }
}

Copy-Item -LiteralPath (Join-Path $AppDir "templates") -Destination (Join-Path $stage "templates") -Recurse
Copy-Item -LiteralPath (Join-Path $AppDir "deploy") -Destination (Join-Path $stage "deploy") -Recurse

$release = Join-Path $AppDir "release"
New-Item -ItemType Directory -Force -Path $release | Out-Null
$zip = Join-Path $release "QueueMail-deploy.zip"
if (Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
}

Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip
Remove-Item -LiteralPath $stage -Recurse -Force
Write-Host $zip
