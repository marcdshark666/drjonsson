# DrJonsson – dagens 35 motiv. Körs 07:30 av uppgiften DrJonsson-Daily (install_task.ps1).
# Kan köras för hand: powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule\daily.ps1 [-DryRun]
param([switch]$DryRun, [int]$Count = 35)
$ErrorActionPreference = "Continue"
$Root = Split-Path $PSScriptRoot -Parent
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
$Log  = Join-Path $Root "outputs\schedule.log"
New-Item -ItemType Directory -Force (Split-Path $Log) | Out-Null
$env:HF_HOME = "E:\CHAT-RTX\hf-cache"
$env:PYTHONIOENCODING = "utf-8"
$args = @((Join-Path $Root "pipeline\generate_daily.py"), "--count", $Count)
if ($DryRun) { $args += "--dry-run" }
Add-Content -Path $Log -Value ("[{0}] start count={1} dry={2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Count, $DryRun) -Encoding utf8
Push-Location $Root
& $Py @args 2>&1 | ForEach-Object { Add-Content -Path $Log -Value $_ -Encoding utf8; Write-Host $_ }
$rc = $LASTEXITCODE
Pop-Location
Add-Content -Path $Log -Value ("[{0}] slut rc={1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $rc) -Encoding utf8
exit $rc
