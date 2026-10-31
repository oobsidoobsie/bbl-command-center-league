# Creates (or updates) the Windows scheduled task that runs the Command Center every night.
# The time comes from run_time= in config.txt; you can type a new one here and it is saved back to config.txt.
$ErrorActionPreference = 'Stop'
$d = Split-Path -Parent $PSScriptRoot
$cfg = Join-Path $d 'config.txt'
if (-not (Test-Path $cfg) -and (Test-Path (Join-Path $d 'config.example.txt'))) { Copy-Item (Join-Path $d 'config.example.txt') $cfg }
$lines = if (Test-Path $cfg) { Get-Content $cfg -Encoding UTF8 } else { @() }
$cur = ($lines | Where-Object { $_ -match '^\s*run_time\s*=' } | Select-Object -First 1)
$time = if ($cur) { ($cur -split '=', 2)[1].Trim() } else { '11:25 PM' }
Write-Host ''
Write-Host "The report runs every night at: $time"
Write-Host 'It waits up to an hour by itself if games are still going.'
Write-Host 'Waivers usually process about 11:09 PM Calgary (sometimes later). A time after midnight reports the night before.'
$new = Read-Host 'Press Enter to keep it, or type a new time (examples: 11:45 PM, 12:15 AM, 23:50)'
if ($new.Trim()) {
    try { $null = [datetime]::Parse($new.Trim(), [Globalization.CultureInfo]::InvariantCulture) } catch { Write-Host "`"$new`" isn't a time I understand. Nothing changed."; exit 1 }
    $time = ([datetime]::Parse($new.Trim(), [Globalization.CultureInfo]::InvariantCulture)).ToString('h:mm tt', [Globalization.CultureInfo]::InvariantCulture)
    if ($cur) { $lines = $lines | ForEach-Object { if ($_ -match '^\s*run_time\s*=') { "run_time=$time" } else { $_ } } }
    else { $lines += '# Time the nightly report runs on this PC (change it with "4 - Schedule nightly").'; $lines += "run_time=$time" }
    Set-Content -Path $cfg -Value $lines -Encoding UTF8
}
$at = [datetime]::Parse($time, [Globalization.CultureInfo]::InvariantCulture)
$a = New-ScheduledTaskAction -Execute (Join-Path $d '.venv\Scripts\pythonw.exe') -Argument ('-X utf8 "' + (Join-Path $d 'cc\run.py') + '"') -WorkingDirectory $d
$t = New-ScheduledTaskTrigger -Daily -At $at
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName 'BBL Command Center' -Action $a -Trigger $t -Settings $s -Description 'BBL Command Center nightly build' -Force | Out-Null
Write-Host "Scheduled: every night at $($at.ToString('h:mm tt', [Globalization.CultureInfo]::InvariantCulture)) (task name: BBL Command Center)."
Write-Host 'Run "4 - Schedule nightly" again any time to change the time.'
# Pre-lock lineup check (cc/lineup_check.py): starts every 15 minutes from 8 AM to 9 PM but only acts in the hour before
# lineups lock (a notification if your CBS lineup can be better). lineup_check=no in config.txt turns it off.
$la = New-ScheduledTaskAction -Execute (Join-Path $d '.venv\Scripts\pythonw.exe') -Argument ('-X utf8 "' + (Join-Path $d 'cc\lineup_check.py') + '"') -WorkingDirectory $d
$lt = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(8))
$lt.Repetition = (New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddHours(8)) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Hours 13)).Repetition
$ls = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'BBL Lineup check' -Action $la -Trigger $lt -Settings $ls -Description 'BBL Command Center: pre-lock lineup check' -Force | Out-Null
Write-Host 'Lineup check: about an hour before lineups lock each day, a notification if your CBS lineup can be better.'

