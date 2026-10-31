#!/usr/bin/env python3
"""BBL Command Center, run on your own PC, for your own team (the one your CBS sign-in manages).

    python cc/run.py            nightly run (waits up to 60 min for late games)
    python cc/run.py --now      don't wait for late games
    python cc/run.py --offline  rebuild from the data already saved (no browser, no email)
    python cc/run.py --no-email / --show-browser / --no-notify

Steps:
 1. ESPN (public): schedule, box scores, defense vs position, game logs, news
 2. CBS (your saved sign-in, read only): every roster with CBS projections, roster trends, league transactions,
    and CBS's own stat lines for the last 7 nights (box scores corrected where ESPN differs; listed in data/cbs_fixes.txt)
 3. Your team: best & worst tables, breakout alerts, Monday 2-for-1 report, the Command Center page
 4. Your page + images, then emails and a Windows notification
"""
import datetime as dt
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENGINE = os.path.join(HERE, "engine")
SEED = os.path.join(HERE, "seed")
DATA = os.path.join(ROOT, "data")          # shared league data
TEAMS_DATA = os.path.join(DATA, "teams")   # one working folder per team
MANAGERS = os.path.join(ROOT, "managers")  # per-team settings.txt + watchlist.txt you can edit
OUT = os.path.join(ROOT, "output")
sys.path.insert(0, HERE)

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Edmonton")
except Exception:
    TZ = None

LOG = []
if sys.stdout is None:  # pythonw (scheduled run) has no console
    sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")

SHARED = ["careers.txt", "bio.txt", "hb.txt", "draft.txt", "draft_history.txt", "dvp_2026.txt", "dvp_cur.txt", "matchups.txt", "opp.txt", "tx.txt", "trends.txt",
          "news.txt", "box.txt", "log.txt", "lock.txt", "tips.txt", "prizes.txt", "cbs_primary.txt"]


def say(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print(s, flush=True)
    if os.environ.get("BBL_PROGRESS"):  # the page's Apply & rebuild bar (cc/serve.py); plan.py adds its own steps
        try:
            with open(os.environ["BBL_PROGRESS"], "a", encoding="utf-8") as f:
                f.write("run|" + s.replace("\n", " ") + "\n")
        except OSError:
            pass


def now_calgary():
    return dt.datetime.now(TZ).replace(tzinfo=None) if TZ else dt.datetime.now()


def label_of(d):
    return f"{d:%a %b} {d.day}"


def rd(name, where=DATA, default=""):
    p = os.path.join(where, name)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else default


def wr(name, text, where=DATA):
    p = os.path.join(where, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_config():
    cfg = {}
    cp = os.path.join(ROOT, "config.txt")
    if not os.path.exists(cp):  # your own settings stay out of Git: start from the example the first time
        shutil.copy2(os.path.join(ROOT, "config.example.txt"), cp)
    for l in open(cp, encoding="utf-8-sig"):  # utf-8-sig: PowerShell may add a BOM
        l = l.strip()
        if l and not l.startswith("#") and "=" in l:
            k, v = l.split("=", 1)
            cfg[k.strip().lower()] = v.strip()
    secret = ""
    sp = os.path.join(ROOT, "secret.txt")
    if os.path.exists(sp):
        for l in open(sp, encoding="utf-8"):
            if l.strip() and not l.strip().startswith("#"):
                secret = l.strip()
                break
    return cfg, secret


# ---------------------------------------------------------------- teams
def display(team):
    return "TINOLA JO'CHIĆK" if "ɪɴᴏʟᴀ" in team else team


def slug(team):
    import unicodedata
    s = unicodedata.normalize("NFKD", display(team)).encode("ascii", "ignore").decode().replace("&", " and ").replace("'", "")
    s = "".join(c for c in s if c.isalnum() or c in " -_")
    return re.sub(r"\s+", " ", s).strip() or "team"


def same_team(a, b):
    a, b = display(a).lower().replace("’", "'"), display(b).lower().replace("’", "'")
    return a == b or ("tinola" in a and "tinola" in b)


def league_teams(pool_all):
    t = []
    for l in pool_all.splitlines():
        f = l.split("|")
        if len(f) >= 4 and not l.startswith("#") and f[3].startswith("TAKEN:") and f[3][6:] not in t:
            t.append(f[3][6:])
    return sorted(t, key=lambda x: display(x).lower())


def pool_for(pool_all, team):
    """Ownership from this team's point of view: its players become MINE."""
    out = []
    for l in pool_all.splitlines():
        f = l.split("|")
        if len(f) >= 4 and not l.startswith("#") and f[3] == "TAKEN:" + team:
            f[3] = "MINE"
            l = "|".join(f)
        out.append(l)
    return "\n".join(out) + "\n"


def normalize_pool(pool):
    """fetch_pool marks your players MINE; store everyone as TAKEN:<team>."""
    out = []
    for l in pool.splitlines():
        f = l.split("|")
        if len(f) >= 4 and not l.startswith("#") and f[3] == "MINE":
            f[3] = "TAKEN:" + my_team()
            l = "|".join(f)
        out.append(l)
    return "\n".join(out).strip() + "\n"


def my_team():
    """Your team, as CBS reported it for your sign-in on the last run (detect_me)."""
    return rd("my_team.txt").strip()


def detect_me(show):
    """Reads which team your CBS sign-in manages: this copy only ever builds that team's page."""
    from browser import Browser
    with Browser(show=show) as b:
        team = b.cbs("fetch_whoami").strip()
    if not team:
        raise SystemExit("CBS didn't show a team for this sign-in. Double-click '2 - Sign in to CBS' and sign in with your own account, then run again.")
    wr("my_team.txt", team + "\n")
    return team


def manager_dir(team):
    """managers/<team>/settings.txt and watchlist.txt, created the first time a team is built."""
    d = os.path.join(MANAGERS, slug(team))
    if not os.path.isdir(d):
        os.makedirs(d)
        src = os.path.join(SEED, "teams", slug(team))
        if os.path.isdir(src):
            for f in ("settings.txt", "watchlist.txt"):
                if os.path.exists(os.path.join(src, f)):
                    shutil.copy2(os.path.join(src, f), os.path.join(d, f))
    if not os.path.exists(os.path.join(d, "settings.txt")):
        shutil.copy2(os.path.join(SEED, "settings_template.txt"), os.path.join(d, "settings.txt"))
    if not os.path.exists(os.path.join(d, "watchlist.txt")):
        wr("watchlist.txt", "# one full CBS player name per line\n", d)
    return d


def watch_of(team):
    return [l.strip() for l in rd("watchlist.txt", manager_dir(team)).splitlines() if l.strip() and not l.startswith("#")]


# ---------------------------------------------------------------- setup
def prepare():
    os.makedirs(DATA, exist_ok=True)
    for f in os.listdir(SEED):
        src = os.path.join(SEED, f)
        if os.path.isfile(src) and not f.startswith("settings") and f != "watch.txt" and not os.path.exists(os.path.join(DATA, f)):
            shutil.copy2(src, os.path.join(DATA, f))
    if not os.path.exists(os.path.join(DATA, "pool_all.txt")) and os.path.exists(os.path.join(DATA, "pool.txt")):
        wr("pool_all.txt", normalize_pool(rd("pool.txt")))


def workspace(team):
    """data/teams/<team>: the engine runs here with the shared data, this team's pool, settings and watchlist."""
    ws = os.path.join(TEAMS_DATA, slug(team))
    first = not os.path.isdir(ws)
    os.makedirs(ws, exist_ok=True)
    if first:  # starting archives (only your team has history from the online version)
        for sub in ("nights", "reports"):
            src = os.path.join(SEED, "teams", slug(team), sub) if os.path.isdir(os.path.join(SEED, "teams", slug(team), sub)) else None
            if src:
                shutil.copytree(src, os.path.join(ws, sub), dirs_exist_ok=True)
        for f in ("two4one.json", "breakout.tsv", "breakout_label.txt", "breakout_summary.html"):
            src = os.path.join(SEED, "teams", slug(team), f)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(ws, f))
    for f in SHARED:
        p = os.path.join(DATA, f)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(ws, f))
        elif os.path.exists(os.path.join(ws, f)) and f in ("box.txt", "lock.txt", "tips.txt", "log.txt"):
            os.remove(os.path.join(ws, f))
    for p in glob.glob(os.path.join(DATA, "box_*.txt")):  # nightly box scores feed the usage-rate (USG%) history
        dst = os.path.join(ws, os.path.basename(p))
        if not os.path.exists(dst):
            shutil.copy2(p, dst)
        elif os.path.getmtime(p) > os.path.getmtime(dst):
            shutil.copy2(p, dst)  # re-fetched since (a run during live games, then the complete box)
    for f in os.listdir(ENGINE):
        if os.path.isdir(os.path.join(ENGINE, f)):  # fonts/ for the mobile Top 10 images
            shutil.copytree(os.path.join(ENGINE, f), os.path.join(ws, f), dirs_exist_ok=True)
            continue
        dst = os.path.join(ws, "daily_email.py" if f == "email.py" else f)
        if f.endswith(".py") and sys.platform == "win32":
            # the engine was written on Linux: "%-d" (day without a leading zero) is "%#d" on Windows
            src = open(os.path.join(ENGINE, f), encoding="utf-8").read()
            open(dst, "w", encoding="utf-8").write(re.sub(r"%-([a-zA-Z])", r"%#\1", src))
        else:
            shutil.copy2(os.path.join(ENGINE, f), dst)
    md = manager_dir(team)
    shutil.copy2(os.path.join(md, "settings.txt"), os.path.join(ws, "settings.txt"))
    wr("watch.txt", "# watchlist\n" + "\n".join(watch_of(team)) + "\n", ws)
    if os.path.exists(os.path.join(ws, "pool.txt")):
        shutil.copy2(os.path.join(ws, "pool.txt"), os.path.join(ws, "pool_old.txt"))
    wr("pool.txt", pool_for(rd("pool_all.txt"), team) + rd("lineups.txt"), ws)  # + each night's lineups (#STATUS lines)
    return ws


def engine(ws, team, *args, quiet=True, extra_env=None):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", BBL_ME=team, **(extra_env or {}))
    r = subprocess.run([sys.executable, *args], cwd=ws, env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"{args[0]} failed for {display(team)}:\n{(r.stderr or r.stdout)[-1500:]}")
    if not quiet and r.stdout.strip():
        say("   " + r.stdout.strip().splitlines()[-1][:200])
    return r.stdout


# ---------------------------------------------------------------- data (shared)
SCORE_JS = ("const sb=await (await fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=__D__&_='+Date.now())).json();"
            "JSON.stringify((sb.events||[]).filter(e=>e.season&&e.season.type===2).map(e=>[e.status.type.state,e.status.type.name]))")


def games_status(b, ymd):
    ev = json.loads(b.run("espn", "https://www.espn.com/nba/", SCORE_JS.replace("__D__", ymd)) or "[]")
    live = [e for e in ev if e[0] == "in" or (e[0] == "pre" and e[1] not in ("STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_SUSPENDED"))]
    return len(ev), len(live)


def box_done(path):
    """Number of finished games in a box score file (first line '#games|finished|in progress')."""
    try:
        head = open(path, encoding="utf-8").readline().lstrip("#").split("|")
        return int(head[1])
    except (OSError, ValueError, IndexError):
        return 0


SEASON0 = dt.date(2026, 10, 20)


def fperiod(d):
    """BBL 2026-27 fantasy period: P1 = Oct 20-25, then Monday-Sunday weeks."""
    return 1 if d <= dt.date(2026, 10, 25) else 2 + (d - dt.date(2026, 10, 26)).days // 7


def save_lineups(b, d):
    """Every team's CBS lineup for date d (who was in an active slot), kept in data/lineups.txt as #STATUS lines."""
    y = d.strftime("%Y%m%d")
    try:
        got = [l for l in b.cbs("fetch_lineups", DATE=y, PERIOD=str(fperiod(d))).splitlines() if l.startswith("#STATUS|")]
    except Exception as e:
        say("⚠️  lineups for", label_of(d), "not read:", str(e).splitlines()[0][:120])
        return
    if got:
        keep = [l for l in rd("lineups.txt").splitlines() if l.startswith("#STATUS|") and l.split("|")[1] != y]
        wr("lineups.txt", "\n".join(keep + got) + "\n")


def nkey(n):
    """Name key that ignores accents, punctuation and Jr/Sr/II/III (ESPN and CBS spell some names differently)."""
    import unicodedata
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"[.'’\-]", "", n)
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", n)
    return " ".join(n.split())


def _num(x):
    try:
        return float(x)
    except ValueError:
        return 0.0


def cbs_correct(b, d):
    """Make box_<date>.txt agree with CBS, whose stats are the ones that count in the league.

    ESPN and CBS disagree on about 1 player-game in 100, nearly always by one steal, block or turnover.
    CBS's per-night stats page fills in the morning after the games, so each run re-checks the last 7 nights:
    a player whose points differ gets CBS's counting stats (attempts from CBS's percentages; anything CBS's page
    doesn't show, like fouls, takes up the rest). Returns the number of players corrected (0 = nothing changed)."""
    y = d.strftime("%Y%m%d")
    path = os.path.join(DATA, f"box_{y}.txt")
    try:
        rows = [l.split("|") for l in b.cbs("fetch_cbs_day", DATE=y).splitlines() if l.count("|") == 15]
    except Exception as e:
        say("⚠️  CBS stats for", label_of(d), "not read:", str(e).splitlines()[0][:120])
        return 0
    if not rows:
        return 0  # CBS hasn't filled that night in yet
    lines = open(path, encoding="utf-8").read().splitlines()
    box = {}
    for i, l in enumerate(lines):
        f = l.split("|")
        if not l.startswith("#") and len(f) >= 16:
            box.setdefault(nkey(f[0]), i)
    prim = dict(l.split("|", 1) for l in rd("cbs_primary.txt").splitlines() if l.count("|") == 1)
    slot = {"PG": "G", "SG": "G", "SF": "F", "PF": "F", "C": "C", "G": "G", "F": "F"}
    left = {k: i for k, i in box.items()}
    fixed, log = 0, []
    for r in rows:
        k = nkey(r[0])
        if k not in left:  # Ron Holland / Ronald Holland II, GG / Gregory Jackson: same first initial, CBS's last name in ESPN's
            t = k.split()
            m = [kk for kk in left if t and kk[:1] == k[:1] and t[-1] in kk.split()]
            if len(m) != 1:
                continue
            k = m[0]
        i = left.pop(k)
        f = lines[i].split("|")
        s = [int(_num(x)) for x in f[2:16]]  # min pts fgm fga tpm tpa ftm fta reb ast to stl blk pf
        mi, pts, fgm, fga, tpm, tpa, ftm, fta, reb, ast, to, stl, blk, pf = s
        base = pts + 2 * fgm - fga + ftm - fta + reb + 2 * ast + 4 * stl + 4 * blk - 2 * to - pf
        want = int(_num(r[15]))
        if want in (base, base + reb, base + ast, base + tpm):
            continue
        c = [int(_num(x)) for x in (r[3], r[4], r[6], r[8], r[10], r[11], r[12], r[13], r[14])]
        pts, fgm, ftm, tpm, reb, ast, stl, to, blk = c

        def att(made, pct, old):  # attempts from CBS's made shots and percentage (one decimal)
            p = _num(pct)
            if made and p:
                a = round(made * 100 / p)
                if a >= made and round(made * 100 / a, 1) == p:
                    return a
            return max(old, made) if made or not p else old
        fga, fta, tpa = att(fgm, r[5], fga), att(ftm, r[7], fta), att(tpm, r[9], tpa)
        pos = prim.get(r[0]) or r[1].split(",")[0]
        bonus = {"G": reb, "F": ast, "C": tpm}.get(slot.get(pos, ""), 0)
        rest = pts + 2 * fgm - fga + ftm - fta + reb + 2 * ast + 4 * stl + 4 * blk - 2 * to + bonus - want
        pf = max(0, rest)  # fouls aren't on CBS's page: whatever's left over
        if rest < 0:
            fga += -rest
        old = lines[i]
        f[2:16] = [str(x) for x in (mi, pts, fgm, fga, tpm, tpa, ftm, fta, reb, ast, to, stl, blk, pf)]
        lines[i] = "|".join(f)
        names = "min pts fgm fga tpm tpa ftm fta reb ast to stl blk pf".split()
        ch = [f"{n} {a}→{z}" for n, a, z in zip(names, old.split("|")[2:16], f[2:16]) if a != z]
        log.append(f"{y}|{f[0]}|{', '.join(ch)}|CBS {want}")
        fixed += 1
    if fixed:
        wr(f"box_{y}.txt", "\n".join(lines) + "\n")
        wr("cbs_fixes.txt", rd("cbs_fixes.txt") + "\n".join(log) + "\n")
        for u in glob.glob(os.path.join(TEAMS_DATA, "*", "usg.txt")):  # team scores for that night are worked out again
            keep = [l for l in open(u, encoding="utf-8").read().splitlines() if not l.startswith(f"S|{y}|")]
            open(u, "w", encoding="utf-8").write("\n".join(keep) + "\n")
        say(f"CBS: {fixed} stat line(s) on {label_of(d)} corrected to CBS's numbers: " + "; ".join(x.split("|")[1] for x in log))
    return fixed


def fetch_all(day, show, wait, watch_all):
    from browser import Browser
    ymd = day.strftime("%Y%m%d")
    info = dict(games=0)
    with Browser(show=show) as b:
        n, live = games_status(b, ymd)
        tries = 0
        while wait and live and tries < 6:
            say(f"⏳ {live} game(s) still going; checking again in 10 minutes ({tries + 1}/6)")
            time.sleep(600)
            tries += 1
            n, live = games_status(b, ymd)
        info["games"], info["late"] = n, live
        say(f"ESPN: {n} regular-season game(s) on {label_of(day)}" + (f", {live} not finished" if live else ""))

        s = b.espn("fetch_sched", FROM=ymd)
        if s.strip():
            wr("opp.txt", s.strip() + "\n")
        wr("news.txt", b.espn("fetch_news").strip() + "\n")
        for f in ("box.txt", "log.txt"):
            if os.path.exists(os.path.join(DATA, f)):
                os.remove(os.path.join(DATA, f))
        if n:
            box = b.espn("fetch_box", DATE=ymd)
            wr("box.txt", box)
            wr(f"box_{ymd}.txt", box)
            dv = b.espn("fetch_dvp", FROM=ymd, TO=ymd)
            have = {l.rsplit("|", 1)[-1] for l in rd("dvp_cur.txt").splitlines() if "|" in l}
            add = [l for l in dv.splitlines() if "|" in l and l.rsplit("|", 1)[-1] not in have]
            if add:
                wr("dvp_cur.txt", rd("dvp_cur.txt") + "\n".join(add) + "\n")
            if day >= dt.date(2026, 10, 22):
                frm = max(day - dt.timedelta(days=13), dt.date(2026, 10, 20))
                wr("log.txt", b.espn("fetch_log", FROM=frm.isoformat(), TO=day.isoformat(), STYPE="2"))

        # nights the PC missed (computer off, a failed run): fetch their box scores so the Best & Worst archive has every date
        for back in range(1, 8):
            d0 = day - dt.timedelta(days=back)
            if d0 < SEASON0:
                break
            y0 = d0.strftime("%Y%m%d")
            if box_done(os.path.join(DATA, f"box_{y0}.txt")):
                continue
            n0, live0 = games_status(b, y0)
            if n0 and not live0:
                wr(f"box_{y0}.txt", b.espn("fetch_box", DATE=y0))
                say(f"ESPN: added the missed night of {label_of(d0)} to the archive")
        if n:
            save_lineups(b, day)
        for back in range(1, 8):  # lineups for nights added to the archive above
            d0 = day - dt.timedelta(days=back)
            y0 = d0.strftime("%Y%m%d")
            if d0 >= SEASON0 and box_done(os.path.join(DATA, f"box_{y0}.txt")) and f"#STATUS|{y0}|" not in rd("lineups.txt"):
                save_lineups(b, d0)
        for back in range(0, 8):  # CBS's own stat lines for the last 7 nights (tonight's only once CBS has them)
            d0 = day - dt.timedelta(days=back)
            p0 = os.path.join(DATA, f"box_{d0:%Y%m%d}.txt")
            if d0 >= SEASON0 and os.path.exists(p0) and box_done(p0) == int(open(p0, encoding="utf-8").readline().lstrip("#").split("|")[0] or 0):
                if cbs_correct(b, d0) and back == 0:
                    shutil.copy2(p0, os.path.join(DATA, "box.txt"))
        # CBS primary positions of two-position players, saved once (cbs_primary.txt: name|PG); fetch_pool looks up new ones
        prim = dict(l.split("|", 1) for l in rd("cbs_primary.txt").splitlines() if l.count("|") == 1)
        pool = b.cbs("fetch_pool", ME=json.dumps(my_team()), WATCH=json.dumps(sorted(set(watch_all))), KNOWN=json.dumps(sorted(prim)))
        rows = [l for l in pool.splitlines() if "|" in l and not l.startswith("#")]
        if len(rows) < 100:
            raise SystemExit("CBS couldn't be read (signed out?). Double-click '2 - Sign in to CBS', then run again.")
        new = {f[1]: f[2] for f in (l.split("|") for l in pool.splitlines() if l.startswith("#PRIM|")) if len(f) == 3}
        if any(prim.get(n) != p for n, p in new.items()):  # blank = CBS shows no primary; saved so it isn't looked up again
            prim.update(new)
            wr("cbs_primary.txt", "".join(f"{n}|{p}\n" for n, p in sorted(prim.items())))
        wr("pool_all.txt", normalize_pool(pool))
        t = b.cbs("fetch_trends")
        if t.strip():
            wr("trends.txt", t.strip() + "\n")
        wr("tx.txt", b.cbs("fetch_tx").strip() + "\n")
        try:  # your finished periods (Period by period, shown on request)
            res = b.cbs("fetch_results").strip()
            if res:
                wr("results.txt", res + "\n")
        except Exception as e:
            say("⚠️  period results not read:", str(e).splitlines()[0][:120])
        say(f"CBS: {len(rows)} players, every roster and the league's transactions read")
    try:  # past seasons for the player card (ESPN, once per player; cc/careers.py)
        import careers
        careers.update(DATA, say)
    except Exception as e:
        say("⚠️  past seasons not read:", str(e).splitlines()[0][:120])
    return info


# ---------------------------------------------------------------- automatic text (what Claude used to write)
def write_lock(day):
    """lock.txt when tomorrow's first game starts before 5:00 PM Calgary (lineups and IR lock 5 min before)."""
    tom = day + dt.timedelta(days=1)
    tips = []
    for l in rd("opp.txt").splitlines():
        f = l.split("|")
        if len(f) >= 4 and f[0] == tom.strftime("%Y%m%d"):
            try:
                t = dt.datetime.strptime(f[3][:16], "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc)
            except ValueError:
                continue
            loc = t.astimezone(TZ).replace(tzinfo=None) if TZ else t.replace(tzinfo=None) - dt.timedelta(hours=6)
            tips.append((loc, f"{f[1]} @ {f[2]}"))
    p = os.path.join(DATA, "lock.txt")
    fmt = lambda x: f"{x:%I:%M %p}".lstrip("0")
    # tips.txt: every game tomorrow (label|lock|game@time;...) for the always-on "Tomorrow's games" strip
    if tips:
        tips.sort()
        wr("tips.txt", f"{label_of(tom)}|{fmt(tips[0][0] - dt.timedelta(minutes=5))}|"
           + ";".join(f"{g}@{fmt(t)}" for t, g in tips) + "\n")
    elif os.path.exists(os.path.join(DATA, "tips.txt")):
        os.remove(os.path.join(DATA, "tips.txt"))
    if tips and min(tips)[0].hour < 17:
        t0, g = min(tips)
        wr("lock.txt", f"{label_of(tom)}|{g}|{fmt(t0)}|{fmt(t0 - dt.timedelta(minutes=5))}\n")
        return f"{label_of(tom)}: {g} at {fmt(t0)}, lineups lock {fmt(t0 - dt.timedelta(minutes=5))}"
    if os.path.exists(p):
        os.remove(p)
    return ""


INJ = re.compile(r"\b(out|injur|hurt|questionable|doubtful|day-to-day|sprain|strain|surgery|mri|ankle|knee|hamstring|concussion)\b", re.I)


def write_brief(ws, team, day, lock):
    def own_map(text):
        m = {}
        for l in text.splitlines():
            f = l.split("|")
            if len(f) >= 4 and not l.startswith("#"):
                m[f[0]] = f[3]
        return m
    pool, old = own_map(rd("pool.txt", ws)), own_map(rd("pool_old.txt", ws))
    mine = [n for n, o in pool.items() if o == "MINE"]
    act = []
    if lock:
        act.append(f"⏰ <b>Early lock tomorrow:</b> {html.escape(lock)}.")
    for n in watch_of(team):
        if old.get(n) == "FA" and pool.get(n, "").startswith("TAKEN:"):
            act.append(f"👀 Watchlist: <b>{html.escape(n)}</b> was picked up by {html.escape(display(pool[n][6:]))}.")
    cut = now_calgary() - dt.timedelta(hours=24)
    for l in rd("tx.txt").splitlines():
        f = l.split("|")
        if len(f) < 6:
            continue
        try:
            when = dt.datetime.strptime(f[0].replace(" ET", "").strip(), "%m/%d/%y %I:%M %p") - dt.timedelta(hours=2)
        except ValueError:
            continue
        if when >= cut and same_team(f[1], team):
            act.append(f"Your move: {html.escape(f[5])} <b>{html.escape(f[2])}</b>.")
    hurt = []
    for l in rd("news.txt").splitlines():
        f = l.split("|")
        if len(f) >= 4:
            for n in mine:
                if (n in f[3] or n in f[2]) and INJ.search(f[2]) and n not in [h[0] for h in hurt]:
                    hurt.append((n, f[2][:180]))
    out = [f"<p><b>{label_of(day)}</b> · after the waiver run (built on your PC)</p>"]
    if act:
        out.append("<h3>⚠️ Action needed</h3><ul>" + "".join(f"<li>{a}</li>" for a in act[:4]) + "</ul>")
    out.append("<h3>Your team</h3><ul>" + ("".join(f"<li>🚑 <b>{html.escape(n)}</b>: {html.escape(t)}</li>" for n, t in hurt[:3])
                                           or "<li>No injury headlines for your players in today's ESPN news.</li>") + "</ul>")
    wr("brief.html", "\n".join(out) + "\n", ws)


def write_breakout_summary(ws, label):
    fa = [l.split("|") for l in rd("breakout.tsv", ws).splitlines() if l.count("|") >= 4]
    fa = [x for x in fa if x[4] == "FA"]
    if fa:
        names = ", ".join(f"<b>{html.escape(x[0])}</b> ({x[2]} over his last 3 vs {x[3]} projected)" for x in fa[:4])
        wr("breakout_summary.html", f"<p><b>Summary:</b> Free agents to look at first: {names}. Check minutes and injury news before you claim.</p>\n", ws)
    wr("breakout_label.txt", label + "\n", ws)


# ---------------------------------------------------------------- pages
def page_html(ws, nav, t10=None, where=None):
    """t10: {"best": png path, "worst": png path} for the page's 📸 Top 10 images button (paths made relative to `where`)."""
    js = ""
    if t10 and where:
        from urllib.parse import quote
        rel = {k: quote(os.path.relpath(v, where).replace(os.sep, "/")) for k, v in t10.items() if v and os.path.exists(v)}
        if rel:
            js = "<script>window.__T10=" + json.dumps(rel) + "</script>"
    # bbl-team: which managers\<team>\watchlist.txt the page's watchlist edits (through cc\serve.py)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="bbl-team" content="{html.escape(os.path.basename(ws))}">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><style>[hidden]{display:none!important}body{margin:0}</style>' + js + '</head><body>' + nav + rd("season_plan.html", ws) + "</body></html>")


def render_png(src_html, png, selector="#card", width=1080, scale=1):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": width, "height": 1400}, device_scale_factor=scale)
            pg.goto("file:///" + os.path.abspath(src_html).replace("\\", "/"))
            try:
                pg.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            pg.wait_for_timeout(300)
            pg.locator(selector).first.screenshot(path=png)
            b.close()
        return True
    except Exception as e:
        say("⚠️  image not made:", str(e).splitlines()[0][:150])
        return False


def pdates(p):
    """First and last date of BBL period p."""
    if p == 1:
        return SEASON0, dt.date(2026, 10, 25)
    a = dt.date(2026, 10, 26) + dt.timedelta(days=7 * (p - 2))
    return a, a + dt.timedelta(days=6)


def period_reports(ws, team, day):
    """reports/Pnn.html for every finished period that doesn't have one yet (weekly.py: Top 10 best and worst).
    A period counts as finished the night after it ends, or on its last night once every game is final."""
    os.makedirs(os.path.join(ws, "reports"), exist_ok=True)
    for p in range(1, fperiod(day) + 1):
        out = os.path.join(ws, "reports", f"P{p:02d}.html")
        a, b = pdates(p)
        days = (a + dt.timedelta(days=i) for i in range((b - a).days + 1))
        boxes = [p for p in (os.path.join(DATA, f"box_{d:%Y%m%d}.txt") for d in days) if os.path.exists(p)]  # data\: the latest copy
        if os.path.exists(out) and all(os.path.getmtime(f) <= os.path.getmtime(out) for f in boxes):
            continue  # made already, and no night of it corrected to CBS since
        heads = [open(f, encoding="utf-8").readline().lstrip("#").split("|") for f in boxes]
        final = all(len(h) > 1 and h[0] == h[1] for h in heads)
        if not boxes or day < b or (day == b and not final):
            continue
        title = f"P{p} · {a:%b} {a.day} – {b:%b} {b.day}"
        if os.path.exists(os.path.join(ws, "summary.html")):
            os.remove(os.path.join(ws, "summary.html"))  # the written outlook (online version only)
        engine(ws, team, "weekly.py", title, "pool.txt", *boxes)
        wr(f"reports/P{p:02d}.html", f"<!--title:{title}-->\n" + rd("weekly.html", ws), ws)
        say(f"📊 {display(team)}: period report {title}")


def build_team(team, day, lock, games, mine):
    label, ymd = label_of(day), day.strftime("%Y%m%d")
    ws = workspace(team)
    os.makedirs(os.path.join(ws, "nights"), exist_ok=True)
    res = os.path.join(ws, "results.txt")  # CBS's /schedule is the signed-in team's: only your page gets it
    if mine and os.path.exists(os.path.join(DATA, "results.txt")):
        shutil.copy2(os.path.join(DATA, "results.txt"), res)
    elif os.path.exists(res):
        os.remove(res)
    for p in sorted(glob.glob(os.path.join(DATA, "box_*.txt"))):
        y0 = os.path.basename(p)[4:12]
        if not y0.isdigit() or y0 == ymd:
            continue
        night = os.path.join(ws, "nights", f"{y0}.html")
        if not box_done(p):
            if os.path.exists(night):
                os.remove(night)  # an archive made before any game had finished
            continue
        if not os.path.exists(night) or os.path.getmtime(p) > os.path.getmtime(night):  # new, or corrected to CBS since
            d0 = dt.datetime.strptime(y0, "%Y%m%d").date()
            engine(ws, team, "nightly.py", os.path.basename(p), "pool.txt", label_of(d0), extra_env={"BBL_DATE": y0})
            wr(f"nights/{y0}.html", f"<!--title:{label_of(d0)}-->\n" + rd("nightly.html", ws), ws)
    if games and not box_done(os.path.join(ws, "box.txt")):
        games = False  # games tonight, but none finished yet (a daytime run): nothing to report for this date
        if os.path.exists(os.path.join(ws, "nights", f"{ymd}.html")):
            os.remove(os.path.join(ws, "nights", f"{ymd}.html"))
    if games:
        for mode in ("", "short", "share") if mine else ("",):
            engine(ws, team, "nightly.py", "box.txt", "pool.txt", label, *([mode] if mode else []), extra_env={"BBL_DATE": ymd})
        if mine:  # the two mobile-friendly Top 10 images (Best and Worst), same design as the bbl-best-worst repo
            engine(ws, team, "nightly.py", "box.txt", "pool.txt", label, "top10", extra_env={"BBL_MY_TEAM": display(team), "BBL_DATE": ymd})
        wr(f"nights/{ymd}.html", f"<!--title:{label}-->\n" + rd("nightly.html", ws), ws)
        if day >= dt.date(2026, 10, 22) and os.path.exists(os.path.join(ws, "log.txt")):
            engine(ws, team, "breakout.py", "log.txt", "pool.txt", label)
            if rd("breakout.tsv", ws).strip():
                write_breakout_summary(ws, label)
    else:
        for f in ("nightly.html", "nightly_short.html", "nightly_short.txt", "nightly_share.html", "nightly_share.txt",
                  "nightly_share_subject.txt", "nightly_top10.html", "nightly_top10_worst.html"):
            if os.path.exists(os.path.join(ws, f)):
                os.remove(os.path.join(ws, f))
    period_reports(ws, team, day)
    monday = day.weekday() == 0 and dt.date(2026, 10, 26) <= day <= dt.date(2027, 2, 22)
    if monday:
        engine(ws, team, "two4one.py", label)
    elif os.path.exists(os.path.join(ws, "two4one_email.html")):
        os.remove(os.path.join(ws, "two4one_email.html"))
    write_brief(ws, team, day, lock)
    engine(ws, team, "plan.py")
    if mine:
        cbs_check_report(ws)
    return ws


def cbs_check_report(ws):
    """plan.py compares your players' fantasy points, game by game, with their CBS game logs (cbs_check.txt)."""
    p = os.path.join(ws, "cbs_check.txt")
    if not os.path.exists(p):
        say("CBS check: skipped (no CBS game logs read this run)")
        return
    rows = [l.split("|") for l in open(p, encoding="utf-8").read().splitlines() if l]
    ok, nbad = rows[0][0], int(rows[0][1])
    if not nbad:
        say(f"CBS check: all {ok} games of your players match their CBS game logs")
        return
    say(f"⚠ CBS check: {nbad} game(s) of your players don't match CBS (also listed under This period → Roster):")
    for n, pos, d, ours, cbs, why in rows[1:]:
        say(f"   {n} ({pos}) {d[4:6]}/{d[6:]}: ours {ours or '—'}, CBS {cbs} · {why}")


def main():
    args = sys.argv[1:]
    cfg, secret = read_config()
    prepare()
    t = now_calgary()
    day = t.date() if t.hour >= 18 else (t - dt.timedelta(days=1)).date()  # before 6 PM, the latest finished night is last night
    label, ymd = label_of(day), day.strftime("%Y%m%d")
    say(f"🏀 BBL Command Center · {label}")

    teams0 = league_teams(rd("pool_all.txt"))
    if "--offline" not in args:
        sb = cfg.get("show_browser", "no").lower()
        show = True if ("--show-browser" in args or sb == "yes") else ("offscreen" if sb == "offscreen" else False)
        found = detect_me(show)
        me = next((x for x in teams0 if same_team(x, found)), found)
        info = fetch_all(day, show, "--now" not in args, watch_of(me))
    else:
        info = dict(games=0)
        if os.path.exists(os.path.join(DATA, f"box_{ymd}.txt")):
            shutil.copy2(os.path.join(DATA, f"box_{ymd}.txt"), os.path.join(DATA, "box.txt"))
            info["games"] = 1
        elif os.path.exists(os.path.join(DATA, "box.txt")):
            os.remove(os.path.join(DATA, "box.txt"))

    teams = league_teams(rd("pool_all.txt"))
    me = next((x for x in teams if same_team(x, my_team())), None)
    if not me:
        raise SystemExit("Your team isn't known yet. Double-click '3 - Run now' (it reads your team from your CBS sign-in).")

    lock = write_lock(day)
    games = info["games"] > 0 and os.path.exists(os.path.join(DATA, "box.txt"))
    say(f"Building {display(me)}'s Command Center…")
    ws = build_team(me, day, lock, games, True)

    os.makedirs(os.path.join(OUT, ymd), exist_ok=True)
    T10 = {}  # 4:5 phone images, saved at 2x (2160x2700)
    for key, src, name in (("best", "nightly_top10.html", "Top 10 Best - Mobile Friendly.png"), ("worst", "nightly_top10_worst.html", "Top 10 Worst - Mobile Friendly.png")):
        png = os.path.join(OUT, ymd, name)
        if games and os.path.exists(os.path.join(ws, src)) and render_png(os.path.join(ws, src), png, scale=2):
            T10[key] = png
    latest = os.path.join(ROOT, "BBL Command Center.html")
    open(latest, "w", encoding="utf-8").write(page_html(ws, "", T10, ROOT))
    open(os.path.join(OUT, ymd, "BBL Command Center.html"), "w", encoding="utf-8").write(page_html(ws, "", T10, os.path.join(OUT, ymd)))

    # emails and the notification
    sent = []
    engine(ws, me, "daily_email.py", label)
    em = re.sub(r'<a href="local-page"[^>]*>(.*?)</a>',
                r'<b>\1</b> <span style="font-size:12px;color:#667085">(the “BBL Command Center” file on your PC)</span>', rd("email.html", ws))
    if "--no-email" not in args and "--offline" not in args and secret and cfg.get("email", "yes").lower() != "no":
        from mailer import send
        try:
            if send(cfg, secret, rd("subject.txt", ws).strip(), em, rd("email.txt", ws)):
                sent.append("daily report")
            if day.weekday() == 0 and rd("two4one_email.html", ws):
                send(cfg, secret, rd("two4one_subject.txt", ws).strip(), rd("two4one_email.html", ws), rd("two4one_email.txt", ws))
                sent.append("2-for-1")
        except Exception as e:
            say("⚠️  email failed:", str(e)[:200], "(check gmail_address in config.txt and the app password in secret.txt)")
    msg = (f"{'⏰ Early lock ' + lock.split(': ', 1)[-1] + ' · ' if lock else ''}"
           f"{'Games: ' + str(info['games']) + ' · ' if info['games'] else 'No games tonight · '}"
           f"{'Emailed: ' + ', '.join(sent) if sent else 'Page updated'}")
    if cfg.get("notify", "yes").lower() != "no" and "--no-notify" not in args:
        from notify import notify
        notify(f"BBL Command Center · {label}", msg)
    say(f"✅ {display(me)}: {latest}")
    say(msg)

    if cfg.get("open_page", "no").lower() == "yes" and sys.platform == "win32":
        open_page()


def open_page():
    """Opens the page through cc/serve.py (editable watchlist) in its own window; falls back to the plain file."""
    py = os.path.join(os.path.dirname(sys.executable), "python.exe")
    try:
        subprocess.Popen([py if os.path.exists(py) else sys.executable, "-X", "utf8", os.path.join(HERE, "serve.py")],
                         cwd=ROOT, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    except Exception:
        os.startfile(os.path.join(ROOT, "BBL Command Center.html"))


def save_log():
    try:
        os.makedirs(OUT, exist_ok=True)
        open(os.path.join(OUT, "last run log.txt"), "w", encoding="utf-8").write("\n".join(LOG) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    import atexit
    atexit.register(save_log)
    try:
        main()
    except SystemExit as e:
        if e.code not in (0, None):
            say("❌", e.code)
            try:
                from notify import notify
                notify("BBL Command Center", str(e.code)[:200])
            except Exception:
                pass
        raise
    except Exception as e:
        say("❌ Something went wrong:", str(e)[:800])
        try:
            from notify import notify
            notify("BBL Command Center: run failed", str(e)[:200])
        except Exception:
            pass
        sys.exit(1)
