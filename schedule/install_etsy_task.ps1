<#
Registrerar DrJonsson-Etsy: varje timme (minut 20), dolt fonster.
Kor pipeline/drain.py: hamtar Marcs ✅/❌ fran GitHub (docs/data/approvals.json,
skrivet av dashboarden) och publicerar BARA godkanda motiv pa Etsy. Inget genereras.

  powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule\install_etsy_task.ps1
#>
param([string]$TaskName = "DrJonsson-Etsy")

$Root = Split-Path $PSScriptRoot -Parent
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "hittar inte $Py" }
$cmd  = Join-Path $PSScriptRoot "run_etsy.cmd"
$vbs  = Join-Path $PSScriptRoot "run_etsy.vbs"
$log  = Join-Path $Root "outputs\etsy-hourly.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

Set-Content -Path $cmd -Encoding ascii -Value @(
  "@echo off",
  "rem Autogenererad av install_etsy_task.ps1 - $TaskName",
  "cd /d ""$Root""",
  "set PYTHONIOENCODING=utf-8",
  """$Py"" ""$Root\pipeline\drain.py"" >> ""$log"" 2>&1"
)
Set-Content -Path $vbs -Encoding ascii -Value @(
  "' Autogenererad dold startare for $TaskName",
  "Option Explicit",
  "Dim sh, q, rc",
  "Set sh = CreateObject(""WScript.Shell"")",
  "q = Chr(34)",
  "sh.CurrentDirectory = ""$Root""",
  "rc = sh.Run(""cmd.exe /c "" & q & ""$cmd"" & q, 0, True)",
  "WScript.Quit rc"
)

$action  = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\wscript.exe" -Argument ("//B //Nologo `"" + $vbs + "`"") -WorkingDirectory $Root
# Varje timme, minut 20 (07:30-jobbet ar igang 07:30-13:30 med 35 motiv; IgnoreNew skyddar bara samma uppgift,
# och de tva skriver olika saker: state.json delas men printify_bulk laser om filen per produkt).
$trigger = New-ScheduledTaskTrigger -Once -At "00:20" -RepetitionInterval (New-TimeSpan -Hours 1)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 50)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited -Force | Out-Null

$rad = (schtasks /Query /TN $TaskName /FO LIST /V | Select-String 'Task To Run') -join ''
if ($rad -match '\\"') { throw "$TaskName registrerades med literala \`" - trasig: $rad" }
Write-Host "$TaskName varje timme :20 -> $($rad.Trim())"
