<#
Registrerar DrJonsson-ButikMail: 08:10 varje dag.

  powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule\install_butiksmail_task.ps1

Uppgiften kor butiksmail.ps1, som lagger ETT uppdrag pa The Work List: "kolla
Gmail efter butiksbesked". Vakthunden som tar uppdraget har Gmail som verktyg -
det har inte ett schemalagt skript, och ingen Gmail-nyckel far skaffas at ett.
08:10 ar valt sa att uppdraget hinner ligga pa listan innan bevakningen
(WorkList-Poll, var 10:e minut) tittar nasta gang, utan att krocka med
DrJonsson-Daily 07:30.

Samma monster som install_drain_task.ps1: kommandoraden i en .cmd, VBS:en doljer
fonstret, Register-ScheduledTask (schtasks /TR med \" dor under PS 7).
#>
param([string]$Time = "08:10",
      [string]$TaskName = "DrJonsson-ButikMail")

$Root = Split-Path $PSScriptRoot -Parent
$PS   = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Job  = Join-Path $PSScriptRoot "butiksmail.ps1"
if (-not (Test-Path $Job)) { throw "hittar inte $Job" }
$cmd  = Join-Path $PSScriptRoot "run_butiksmail.cmd"
$vbs  = Join-Path $PSScriptRoot "run_butiksmail.vbs"
$log  = Join-Path $Root "outputs\butiksmail-launcher.log"

Set-Content -Path $cmd -Encoding ascii -Value @(
  "@echo off",
  "rem Autogenererad av install_butiksmail_task.ps1 - $TaskName",
  "cd /d ""$Root""",
  """$PS"" -NoProfile -ExecutionPolicy Bypass -File ""$Job"" >> ""$log"" 2>&1"
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
# StartWhenAvailable tar igen tillfallet om datorn sov 08:10 - men bara om
# uppgiften har kort minst en gang (ett jobb som aldrig kort tas aldrig igen).
$trigger  = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited -Force | Out-Null

$rad = (schtasks /Query /TN $TaskName /FO LIST /V | Select-String 'Task To Run') -join ''
if ($rad -match '\\"') { throw "$TaskName registrerades med literala \`" - trasig: $rad" }
Write-Host "$TaskName $Time -> $($rad.Trim())"
