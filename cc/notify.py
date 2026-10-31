"""Windows desktop notification (no extra installs: uses PowerShell's built-in tray balloon)."""
import subprocess
import sys


def notify(title, text):
    if sys.platform != "win32":
        print(f"[notification] {title}: {text}")
        return
    t = title.replace("'", "''")[:63]
    m = text.replace("'", "''")[:250]
    ps = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing;"
          "$n=New-Object System.Windows.Forms.NotifyIcon; $n.Icon=[System.Drawing.SystemIcons]::Information;"
          f"$n.BalloonTipTitle='{t}'; $n.BalloonTipText='{m}'; $n.Visible=$true; $n.ShowBalloonTip(15000);"
          "Start-Sleep -Seconds 16; $n.Dispose()")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        print("notification failed:", e)
