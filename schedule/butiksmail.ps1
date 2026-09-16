<#
DrJonsson-ButikMail - daglig Gmail-koll: har det kommit en bekraftelse pa att
butiken far oppnas, eller vantar Etsy/Printify pa Marc?

  powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule\butiksmail.ps1

Pipelinen kan inte lasa Gmail sjalv - det finns ingen Gmail-nyckel pa datorn och
inget skript far skaffa en (det kravs Marcs OAuth). Gmail nas bara av en
Claude-session, dar brevladan ligger som ett MCP-verktyg. Darfor gor den har
uppgiften en enda sak: den lagger ETT uppdrag pa The Work List med rutinfilen
som instruktion. Vakthunden som tar det laser Gmail, klassar laget och skriver
state\store-mail.json - som generate_daily.py lyfter in i dashboardens
status.json och som bockar av "etsy-account" nar butiken ar klar.

Uppdraget laggs inte:
  * nar store-mail.json redan sager att butiken ar oppen (rutinen ar fardig), eller
  * nar gardagens ButikMail-uppdrag fortfarande ligger oppet (ingen dubblett).
#>
param(
  [string]$WorkList = "E:\CHAT-RTX\CLAUDECODE GENERAL BRAIN\APP ideas\the-work-list\worklist.js",
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root   = Split-Path $PSScriptRoot -Parent
$State  = Join-Path $Root "state\store-mail.json"
$Skill  = Join-Path $env:USERPROFILE ".claude\scheduled-tasks\drjonsson-butiksmail\SKILL.md"
$Log    = Join-Path $Root "outputs\butiksmail.log"
$Marker = "DrJonsson-ButikMail"

function Write-Log([string]$m) {
  $rad = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m
  New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null
  Add-Content -Path $Log -Value $rad -Encoding utf8
  Write-Host $rad
}

# 1. Ar butiken redan bekraftad? Da har rutinen gjort sitt och ska inte tjata.
if (-not $Force -and (Test-Path $State)) {
  try {
    $s = Get-Content $State -Raw -Encoding utf8 | ConvertFrom-Json
    if ($s.shop_open -eq $true) {
      Write-Log "butiken ar redan bekraftad oppen ($($s.headline)) - inget uppdrag laggs"
      exit 0
    }
  } catch {
    Write-Log "kunde inte lasa $State ($($_.Exception.Message)) - fortsatter anda"
  }
}

# 2. Ligger gardagens koll kvar olost? Lagg inte en dubblett ovanpa den.
if (-not $Force) {
  $oppet = & node -e @"
const fs = require('fs');
const p = process.argv[1];
try {
  const d = JSON.parse(fs.readFileSync(p, 'utf8'));
  const kvar = (d.items || []).filter((i) => ['open', 'working', 'paused'].includes(i.status) && String(i.text || '').includes(process.argv[2]));
  console.log(kvar.length ? kvar.map((i) => '#' + i.id + ' ' + i.status).join(', ') : '');
} catch (e) { console.log(''); }
"@ $(if ($env:WL_DATA) { $env:WL_DATA } else { Join-Path (Split-Path $WorkList) "worklist.json" }) $Marker
  if ($LASTEXITCODE -ne 0) { Write-Log "kunde inte lasa listan - fortsatter anda"; $oppet = "" }
  if ($oppet) { Write-Log "ButikMail-uppdrag ligger redan kvar ($oppet) - inget nytt laggs"; exit 0 }
}

# 3. Lagg uppdraget. Texten ar sjalvbarande sa att vakthunden klarar sig aven om
#    rutinfilen skulle saknas.
$text = @"
$Marker $(Get-Date -Format 'yyyy-MM-dd'): kolla Gmail efter butiksbesked for DrJonsson (projekt aaron-prints).

Sok i Gmail efter mail nyare an 3 dygn fran Etsy och Printify - bade bekraftelser och krav pa atgard. Avgor EN sak: far butiken oppnas nu, eller vantar den pa Marc? Skriv svaret i E:\CHAT-RTX\CLAUDECODE GENERAL BRAIN\APP ideas\aaron-prints\state\store-mail.json enligt mallen i rutinfilen, committa och pusha (GitHub Pages visar det pa marcdshark666.github.io/drjonsson). Har ingenting andrats sedan forra kollen racker det att uppdatera faltet checked.

Rutinfil med sokstrangar, klassning och exakt filformat: $Skill
"@

$out = & node "$WorkList" add $text 2>&1
if ($LASTEXITCODE -ne 0) { Write-Log "kunde inte lagga uppdraget: $out"; exit 1 }
Write-Log "uppdrag lagt pa The Work List: $out"
exit 0
