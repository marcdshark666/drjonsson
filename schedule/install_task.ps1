<#
Registrerar DrJonsson-Daily: 07:30 varje dag (35 motiv, upp till 6 h), dolt fönster, tas igen om datorn sov.

  powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule\install_task.ps1 [-Time 07:30]

Samma mönster som gadget-drop/schedule/install_daily15_task.ps1: kommandoraden
ligger i en .cmd, VBS:en döljer fönstret, och uppgiften registreras med
Register-ScheduledTask (schtasks /TR med \" dör under PS 7).
#>
param([string]$Time = "07:30", [string]$TaskName = "DrJonsson-Daily")

$Root = Split-Path $PSScriptRoot -Parent
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "hittar inte $Py" }
$PS   = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Daily = Join-Path $PSScriptRoot "daily.ps1"
$cmd  = Join-Path $PSScriptRoot "run_daily.cmd"
$vbs  = Join-Path $PSScriptRoot "run_daily.vbs"
$log  = Join-Path $Root "outputs\schedule-launcher.log"

Set-Content -Path $cmd -Encoding ascii -Value @(
  "@echo off",
  "rem Autogenererad av install_task.ps1 - $TaskName",
  "cd /d ""$Root""",
  """$PS"" -NoProfile -ExecutionPolicy Bypass -File ""$Daily"" >> ""$log"" 2>&1"
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
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 6)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited -Force | Out-Null

$rad = (schtasks /Query /TN $TaskName /FO LIST /V | Select-String 'Task To Run') -join ''
if ($rad -match '\\"') { throw "$TaskName registrerades med literala \`" - trasig: $rad" }
Write-Host "$TaskName $Time -> $($rad.Trim())"
