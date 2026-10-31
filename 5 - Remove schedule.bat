@echo off
powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName 'BBL Command Center' -Confirm:$false; Unregister-ScheduledTask -TaskName 'BBL Lineup check' -Confirm:$false -ErrorAction SilentlyContinue; Write-Host 'Nightly schedule and lineup check removed.'"
pause
