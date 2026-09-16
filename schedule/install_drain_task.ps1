<#
Registrerar DrJonsson-Drain: 10, 13, 16, 19 och 22 varje dag.

  powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule\install_drain_task.ps1

Morgonkorningen (DrJonsson-Daily 07:30) hinner bara ca 50 av dygnets 280
Printify-publiceringar innan Printify svarar 429. De har fem draneringarna tar
resten. Samma monster som install_task.ps1: kommandoraden i en .cmd, VBS:en
doljer fonstret, Register-ScheduledTask (schtasks /TR med \" dor under PS 7).
#>
param([string[]]$Times = @("10:00", "13:00", "16:00", "19:00", "22:00"),
      [string]$TaskName = "DrJonsson-Drain")

$Root = Split-Path $PSScriptRoot -Parent
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "hittar inte $Py" }
$PS    = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Drain = Join-Path $PSScriptRoot "drain.ps1"
$cmd   = Join-Path $PSScriptRoot "run_drain.cmd"
$vbs   = Join-Path $PSScriptRoot "run_drain.vbs"
$log   = Join-Path $Root "outputs\drain-launcher.log"

Set-Content -Path $cmd -Encoding ascii -Value @(
  "@echo off",
  "rem Autogenererad av install_drain_task.ps1 - $TaskName",
  "cd /d ""$Root""",
  """$PS"" -NoProfile -ExecutionPolicy Bypass -File ""$Drain"" >> ""$log"" 2>&1"
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

$action   = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\wscript.exe" -Argument ("//B //Nologo `"" + $vbs + "`"") -WorkingDirectory $Root
$triggers = $Times | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -RunLevel Limited -Force | Out-Null

$rad = (schtasks /Query /TN $TaskName /FO LIST /V | Select-String 'Task To Run') -join ''
if ($rad -match '\\"') { throw "$TaskName registrerades med literala \`" - trasig: $rad" }
Write-Host "$TaskName $($Times -join ', ') -> $($rad.Trim())"
