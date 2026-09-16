# DrJonsson - draneringen. Publicerar det som blev kvar av dagens Printify-produkter.
#
# 35 motiv x 8 produkttyper = 280 produkter per dygn, men Printify stryper
# publiceringen med HTTP 429 efter ca 50 i rad oavsett hur langsamt man gar
# (uppmatt 2026-09-16: 52 publiceringar pa 12 s takt, sedan 429). Morgonkorningen
# hinner alltsa inte allt. Uppgiften DrJonsson-Drain kor den har flera ganger om
# dagen; printify_queue i generate_daily.py plockar upp efterslapningen, och
# pipeline/state.json gor att inget skapas eller publiceras tva ganger.
#
# For hand: powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule\drain.ps1
param([int]$Count = 35, [double]$Minutes = 50)
$ErrorActionPreference = "Continue"
$Root = Split-Path $PSScriptRoot -Parent
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
$Log  = Join-Path $Root "outputs\drain.log"
New-Item -ItemType Directory -Force (Split-Path $Log) | Out-Null
$env:HF_HOME = "E:\CHAT-RTX\hf-cache"
$env:PYTHONIOENCODING = "utf-8"
# Ingen Telegram: draneringen ska inte skicka ett meddelande per korning, och
# Etsy-fragan (0,20 USD per listning) hor hemma i morgonkorningen.
$a = @((Join-Path $Root "pipeline\generate_daily.py"), "--count", $Count,
       "--no-telegram", "--printify-minutes", $Minutes)
Add-Content -Path $Log -Value ("[{0}] dranering start" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -Encoding utf8
Push-Location $Root
& $Py @a 2>&1 | ForEach-Object { Add-Content -Path $Log -Value $_ -Encoding utf8 }
$rc = $LASTEXITCODE
Pop-Location
Add-Content -Path $Log -Value ("[{0}] dranering slut rc={1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $rc) -Encoding utf8
exit $rc
