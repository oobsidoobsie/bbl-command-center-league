#!/usr/bin/env python3
"""Opens the Command Center from a small server on this PC, so the Watchlist tab can add and remove players.

    python cc/serve.py            start the server (if it isn't running) and open your page
    python cc/serve.py --no-open  start the server without opening a browser

Only this PC can reach it (127.0.0.1). It serves the Command Center pages and images, nothing else
(not config.txt, secret.txt, data\\ or managers\\). It writes two things: managers\\<team>\\watchlist.txt, and your own managers\\<team>\\settings.txt
(the page's stream slot and roster settings: stream, proj, out_until, keep and rest_b2b lines), after which it rebuilds
your page from the saved data (run.py --offline: no browser, no email).
Close the window to stop it; the pages still open as plain files, just with a read-only watchlist.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MANAGERS = os.path.join(ROOT, "managers")
PAGE = "BBL Command Center.html"
SERVED_DIRS = ("output",)          # plus the main page in the top folder
SERVED_EXT = (".html", ".png", ".jpg", ".jpeg", ".svg", ".css", ".js", ".ttf", ".woff2", ".ico")
HEADER = "# one full CBS player name per line\n"
LOCK = threading.Lock()
BUILD_LOCK = threading.Lock()  # one page rebuild at a time


def port_of():
    try:
        for l in open(os.path.join(ROOT, "config.txt"), encoding="utf-8-sig"):
            k, _, v = l.strip().partition("=")
            if k.strip().lower() == "page_port" and v.strip().isdigit():
                return int(v.strip())
    except OSError:
        pass
    return 8765


def team_dir(team):
    """managers/<team> for a team that has been built; None for anything else (no paths, no new folders)."""
    if not team or team in (".", "..") or any(c in team for c in '/\\:*?"<>|') or len(team) > 80:
        return None
    d = os.path.join(MANAGERS, team)
    return d if os.path.isdir(d) else None


def read_list(d):
    p = os.path.join(d, "watchlist.txt")
    lines = open(p, encoding="utf-8-sig").read().splitlines() if os.path.exists(p) else []
    return [l for l in lines if l.strip().startswith("#")] or [HEADER.strip()], [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def my_slug():
    """Folder name of your own team (read from your CBS sign-in): the only page its settings can be changed from."""
    sys.path.insert(0, HERE)
    from run import my_team, slug
    return slug(my_team())


def pool_names(team):
    """Every player name in that team's pool (free agents and all rosters)."""
    p = os.path.join(ROOT, "data", "teams", team, "pool.txt")
    if not os.path.exists(p):
        return set()
    return {l.split("|", 1)[0] for l in open(p, encoding="utf-8") if not l.startswith("#") and l.count("|") >= 7}


def roster(team):
    """Your players' full CBS names, from tonight's pool for that team."""
    p = os.path.join(ROOT, "data", "teams", team, "pool.txt")
    if not os.path.exists(p):
        return set()
    return {f[0] for f in (l.split("|") for l in open(p, encoding="utf-8")) if len(f) > 3 and f[3] == "MINE"}


def parse_settings(req, players, team):
    """The page's settings, checked: stream slot, and for your players FP/G (0-120), out-until date and keep.
    Returns (new settings lines by key, error)."""
    import datetime as dt
    stream = " ".join(str(req.get("stream") or "").split())
    if stream and stream not in players:
        return None, f"{stream} isn't on your roster"
    new = {"stream": [f"stream|{stream}|1"] if stream else [], "proj": [], "out_until": [], "keep": [], "rest_b2b": []}
    proj, out, keep, rest = req.get("proj") or {}, req.get("out") or {}, req.get("keep") or [], req.get("rest")
    if not isinstance(proj, dict) or not isinstance(out, dict) or not isinstance(keep, list) or not isinstance(rest, (list, type(None))):
        return None, "bad request"
    if rest is not None:  # rests on back-to-backs: any player (Watchlist 🛌 B2B), not just yours
        known = pool_names(team)
        for n in sorted({" ".join(str(x).split()) for x in rest}):
            if n not in known:
                return None, f"{n} isn't in the player pool"
            new["rest_b2b"].append(f"rest_b2b|{n}|1")
    else:
        new.pop("rest_b2b")
    for n in sorted(players):
        v = proj.get(n)
        if v is not None:
            try:
                v = float(v)
            except (TypeError, ValueError):
                return None, f"FP/G for {n} isn't a number"
            if not 0 <= v <= 120:
                return None, f"FP/G for {n} must be from 0 to 120"
            new["proj"].append(f"proj|{n}|{v:g}")
        d = out.get(n)
        if d:
            try:
                new["out_until"].append(f"out_until|{n}|{dt.date.fromisoformat(str(d)).isoformat()}")
            except ValueError:
                return None, f"out-until date for {n} isn't a date"
        if n in keep:
            new["keep"].append(f"keep|{n}|1")
    return new, None


def set_settings(d, new, players):
    """Rewrites settings.txt: the page's lines replace the stream line and your players' proj / out_until / keep lines,
    and every rest_b2b line, each under its own comment. Other lines (other players, notrade, target) stay as they are.
    Returns the old text so a failed rebuild can undo it."""
    p = os.path.join(d, "settings.txt")
    old = open(p, encoding="utf-8-sig", errors="replace").read() if os.path.exists(p) else ""
    def mine(l):
        f = l.split("|")
        return len(f) == 3 and (f[0] in ("stream",) + (("rest_b2b",) if "rest_b2b" in new else ()) or
                                (f[0] in ("proj", "out_until", "keep") and f[1] in players))
    lines = [l for l in old.splitlines() if not mine(l)]
    if new.get("rest_b2b") and not any(l.startswith("# rest_b2b") for l in lines):
        lines.append("# rest_b2b: sits the 2nd night of every back-to-back (load management); the page's 🛌 B2B / Rests B2Bs")
    for k in [k for k in ("stream", "proj", "out_until", "keep", "rest_b2b") if k in new]:
        at = next((i + 1 for i, l in enumerate(lines) if l.startswith("# " + k)), len(lines))
        lines[at:at] = new[k]
    with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(p + ".tmp", p)
    return old


PROGRESS = os.path.join(ROOT, "output", "rebuild_progress.txt")  # run.py and plan.py append their steps here
JOB = {"state": "idle"}  # the latest rebuild: idle / running / done / failed, with start time and any error


def rebuild():
    """Your page again from the data already saved: no browser, no email, no notification (about 40 s)."""
    os.makedirs(os.path.dirname(PROGRESS), exist_ok=True)
    open(PROGRESS, "w").close()
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "run.py"), "--offline", "--no-notify"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
                       env=dict(os.environ, BBL_PROGRESS=PROGRESS), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode == 0 and "Page updated" in r.stdout, (r.stdout + r.stderr).strip().splitlines()[-1:]


def progress():
    """(percent, step) of the running rebuild, from its progress file. plan.py's steps fill 6-86% and say where the
    next one is and how long they usually take, so the bar keeps moving through a long step instead of stalling."""
    pct, step, seg = 2, "Starting", None   # seg: (from %, to %, usual seconds, started at) of the step under way
    try:
        lines = open(PROGRESS, encoding="utf-8").read().splitlines()
    except OSError:
        lines = []
    for l in lines:
        src, _, rest = l.partition("|")
        f = rest.split("|")
        if src == "plan" and len(f) >= 2:
            try:
                a = 6 + int(f[0]) * 0.8
                b = 6 + int(f[2]) * 0.8 if len(f) > 4 else a
                seg = (a, b, float(f[3]), float(f[4])) if len(f) > 4 else None
                pct, step = max(pct, a), f[1]
            except ValueError:
                pass
        elif "Building" in rest:
            pct, step, seg = max(pct, 4), "Getting your saved data ready", None
        elif rest.startswith("CBS check"):
            pct, step, seg = max(pct, 88), "Checking your players against CBS", (88, 95, 5.0, os.path.getmtime(PROGRESS))
        elif rest.startswith("✅"):
            pct, step, seg = max(pct, 95), "Writing the page", None
        elif "Page updated" in rest:
            pct, step, seg = 99, "Done", None
    if seg:  # part of the way to the next step, never quite reaching it
        a, b, secs, t0 = seg
        pct = max(pct, a + (b - a) * min(0.95, max(0.0, time.time() - t0) / max(secs, 0.1)))
    return round(pct), step


def run_job(d, old):
    """Background rebuild after the settings were saved; puts settings.txt back if it fails."""
    try:
        ok, tail = rebuild()
        if not ok:
            with open(os.path.join(d, "settings.txt"), "w", encoding="utf-8", newline="\n") as f:
                f.write(old)
            JOB.update(state="failed", error="the rebuild failed: " + " ".join(tail)[:200], end=time.time())
        else:
            JOB.update(state="done", end=time.time())
    except Exception as e:  # a timeout or a crash: same as a failed rebuild
        with open(os.path.join(d, "settings.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(old)
        JOB.update(state="failed", error=str(e)[:200], end=time.time())
    finally:
        BUILD_LOCK.release()


def write_list(d, head, names):
    p = os.path.join(d, "watchlist.txt")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head + names) + "\n")
    os.replace(tmp, p)


class Handler(SimpleHTTPRequestHandler):
    server_version = "BBL"

    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, *a):  # quiet console
        pass

    def _host_ok(self):
        # only the addresses this server is opened at (stops other websites reaching it through DNS tricks)
        return self.headers.get("Host", "") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if not self._host_ok():
            return self.send_error(403)
        u = urlsplit(self.path)
        if u.path == "/":
            self.send_response(302)
            self.send_header("Location", "/" + quote(PAGE))
            return self.end_headers()
        if u.path == "/api/ping":
            return self._json(200, {"ok": True})
        if u.path == "/api/watchlist":
            d = team_dir(parse_qs(u.query).get("team", [""])[0])
            if not d:
                return self._json(404, {"error": "unknown team"})
            with LOCK:
                return self._json(200, {"names": read_list(d)[1]})
        if u.path == "/api/settings":
            team = parse_qs(u.query).get("team", [""])[0]
            return self._json(200, {"editable": bool(team_dir(team)) and team == my_slug()})
        if u.path == "/api/rebuild":  # the running rebuild: state, percent, current step, seconds so far
            pct, step = progress() if JOB.get("state") == "running" else ((100, "Done") if JOB.get("state") == "done" else (0, ""))
            el = round((JOB.get("end") or time.time()) - JOB["start"]) if JOB.get("start") else 0
            return self._json(200, {"state": JOB.get("state"), "pct": pct, "step": step, "elapsed": el, "error": JOB.get("error")})
        rel = unquote(u.path).lstrip("/").replace("\\", "/")
        parts = rel.split("/")
        allowed = (rel == PAGE or (len(parts) > 1 and parts[0] in SERVED_DIRS)) and ".." not in parts \
            and rel.lower().endswith(SERVED_EXT)
        if not allowed:
            return self.send_error(404)
        return super().do_GET()

    def do_HEAD(self):
        return self.send_error(405)

    def do_POST(self):
        path = urlsplit(self.path).path
        if not self._host_ok() or path not in ("/api/watchlist", "/api/settings"):
            return self.send_error(403)
        # the page itself must be asking (blocks other websites from posting to this PC)
        if self.headers.get("Origin", "") != f"http://{self.headers.get('Host')}" or \
                not self.headers.get("Content-Type", "").startswith("application/json"):
            return self.send_error(403)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(min(n, 32768)) or b"{}")
        except (ValueError, OSError):
            return self._json(400, {"error": "bad request"})
        team = str(req.get("team", ""))
        d = team_dir(team)
        name = " ".join(str(req.get("name", "")).split())
        act = req.get("action")
        if not d:
            return self._json(404, {"error": "unknown team"})
        if path == "/api/settings":
            if team != my_slug():
                return self._json(403, {"error": "only your own page can change its settings"})
            players = roster(team)
            new, err = parse_settings(req, players, team)
            if err:
                return self._json(400, {"error": err})
            if not BUILD_LOCK.acquire(blocking=False):
                return self._json(409, {"error": "a rebuild is already running; try again in a minute"})
            try:
                old = set_settings(d, new, players)
            except Exception:
                BUILD_LOCK.release()
                raise
            # the rebuild runs in the background; the page follows it on /api/rebuild (progress bar) and reloads when done
            JOB.clear(); JOB.update(state="running", start=time.time())
            threading.Thread(target=run_job, args=(d, old), daemon=True).start()
            return self._json(202, {"started": True})
        if not name or len(name) > 60 or name.startswith("#") or act not in ("add", "remove"):
            return self._json(400, {"error": "bad request"})
        with LOCK:
            head, names = read_list(d)
            low = name.lower()
            if act == "add" and all(x.lower() != low for x in names):
                names.append(name)
            elif act == "remove":
                names = [x for x in names if x.lower() != low]
            write_list(d, head, names)
        return self._json(200, {"names": names})


def running(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5) as s:
            s.sendall(f"GET /api/ping HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())
            data = b""
            while len(data) < 4096:  # headers and body arrive separately: read until the server closes
                chunk = s.recv(512)
                if not chunk:
                    break
                data += chunk
            return b'"ok"' in data
    except OSError:
        return False


def main():
    port = port_of()
    url = f"http://127.0.0.1:{port}/{quote(PAGE)}"
    if running(port):  # already open in another window: just show the page
        if "--no-open" not in sys.argv:
            webbrowser.open(url)
        return
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        raise SystemExit(f"Port {port} is used by another program. Set page_port= in config.txt to another number (e.g. 8766) and try again.")
    print("BBL Command Center is open at", url)
    print("The watchlist saves to managers\\<team>\\watchlist.txt. Close this window when you're done.")
    if "--no-open" not in sys.argv:
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
