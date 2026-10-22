#Requires -Version 5.1
<#
.SYNOPSIS
  Installs Queue Mail Generator on Windows Server and starts it at boot.
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$ListenHost = "0.0.0.0",
    [int]$Threads = 8,
    [string]$TaskName = "QueueMailGenerator",
    [switch]$SkipFirewall
)

$ErrorActionPreference = "Stop"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Запустите PowerShell от имени администратора."
    }
}

function Resolve-PythonLauncher {
    $candidates = @(
        @{ Exe = "py"; Args = @("-3") },
        @{ Exe = "python"; Args = @() },
        @{ Exe = "python3"; Args = @() }
    )
    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) {
            continue
        }
        $versionText = @(
            & $candidate.Exe @($candidate.Args) -c "import sys; print('%d.%d' % (sys.version_info[0], sys.version_info[1]))"
        ) | Where-Object { $_ } | Select-Object -Last 1
        if ($LASTEXITCODE -ne 0 -or -not $versionText) {
            continue
        }
        $version = $versionText.ToString().Trim()
        $parts = $version.Split(".")
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
            return @{ Exe = $candidate.Exe; Args = $candidate.Args; Version = $version }
        }
    }
    throw "Нужен Python 3.10 или новее в PATH. При установке отметьте Add python.exe to PATH."
}

function Convert-ToFirewallProfile {
    param($Category)
    switch ($Category) {
        "DomainAuthenticated" { "Domain" }
        "Private" { "Private" }
        "Public" { "Public" }
        default { $null }
    }
}

Assert-Administrator

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Некорректный порт: $Port"
}
if ($Threads -lt 1) {
    throw "Некорректное число потоков: $Threads"
}

$AppDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Rules = Join-Path $AppDir "np_rules.json"
$Requirements = Join-Path $AppDir "requirements.txt"
if (-not (Test-Path -LiteralPath $Rules)) {
    throw "Не найден np_rules.json в $AppDir"
}
if (-not (Test-Path -LiteralPath $Requirements)) {
    throw "Не найден requirements.txt в $AppDir"
}

$python = Resolve-PythonLauncher
Write-Host "Python $($python.Version)"

$VenvDir = Join-Path $AppDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Создаю виртуальное окружение..."
    & $python.Exe @($python.Args + @("-m", "venv", $VenvDir))
    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось создать виртуальное окружение."
    }
}

Write-Host "Устанавливаю зависимости..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Не удалось обновить pip." }
& $VenvPython -m pip install -r $Requirements
if ($LASTEXITCODE -ne 0) { throw "Не удалось установить зависимости." }

$config = [ordered]@{
    host    = $ListenHost
    port    = $Port
    threads = $Threads
}
$configPath = Join-Path $AppDir "server.json"
$json = $config | ConvertTo-Json
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($configPath, $json, $utf8)
New-Item -ItemType Directory -Force -Path (Join-Path $AppDir "logs") | Out-Null

if (-not $SkipFirewall) {
    $ruleName = "Queue Mail Generator TCP $Port"
    Get-NetFirewallRule -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -like "Queue Mail Generator TCP *" } |
        Remove-NetFirewallRule
    $profiles = @(
        Get-NetConnectionProfile -ErrorAction SilentlyContinue |
            ForEach-Object { Convert-ToFirewallProfile $_.NetworkCategory } |
            Where-Object { $_ } |
            Select-Object -Unique
    )
    if ($profiles.Count -eq 0) {
        $profiles = @("Domain", "Private")
    }
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile $profiles | Out-Null
    Write-Host ("Правило брандмауэра '{0}': {1}" -f $ruleName, ($profiles -join ", "))
}

$runScript = Join-Path $PSScriptRoot "run.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runScript`"" -WorkingDirectory $AppDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 3650) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

& (Join-Path $PSScriptRoot "stop.ps1") -TaskName $TaskName -Quiet
Start-Sleep -Seconds 1

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Queue Mail Generator" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

$listening = $false
for ($i = 0; $i -lt 20; $i++) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $listening = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $listening) {
    $logPath = Join-Path $AppDir "logs\queuemail.log"
    $startupLog = Join-Path $AppDir "logs\startup.log"
    Write-Host "Процесс не занял порт $Port. Проверьте журналы:"
    Write-Host "  $logPath"
    Write-Host "  $startupLog"
    throw "Запуск не подтверждён."
}

Write-Host "Сервис запущен. Откройте http://<имя-сервера>:$Port"
