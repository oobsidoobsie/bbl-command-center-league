#!/usr/bin/env python3
"""Pre-lock lineup check: about an hour before lineups lock, read your CBS lineup for today and compare it with the best
lineup from the players who play tonight. If it can be better (a starter with no game or ruled out, or a reserve who
projects more), you get a Windows notification (and an email when email=yes in config.txt). Read only: nothing on CBS changes.

    python cc/lineup_check.py          what the scheduled task runs (every 15 min, 8 AM to 9 PM); acts only in the
                                       hour before lock: once ~75 min before, and again ~30 min before if something was wrong
    python cc/lineup_check.py --now    check right away (always shows the result)

Lineup rule, as on the page: G, F, C + 2 Util, each player at his best eligible slot (CBS FP/G, or your proj| override).
Your out_until dates and rest_b2b nights (settings.txt) count as not playing. Result log: output/lineup check.txt
"""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402  (config, paths, Calgary time, team names)

CBS_ABBR = {"WSH": "WAS", "PHX": "PHO", "GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTAH": "UTA", "BRK": "BKN", "CHO": "CHA"}
STATE = os.path.join(run.DATA, "lineup_check_state.txt")
LOGF = os.path.join(run.OUT, "lineup check.txt")


def lock_time(today):
    """First tip today (Calgary) minus 5 minutes, from data/opp.txt (date|away|home|tip UTC); None if no games."""
    tips = []
    for l in run.rd("opp.txt").splitlines():
        f = l.split("|")
        if len(f) >= 4 and f[0] == today.strftime("%Y%m%d"):
            try:
                t = dt.datetime.strptime(f[3][:16], "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc)
            except ValueError:
                continue
            tips.append(t.astimezone(run.TZ).replace(tzinfo=None) if run.TZ else t.replace(tzinfo=None) - dt.timedelta(hours=6))
    return min(tips) - dt.timedelta(minutes=5) if tips else None


def settings(team):
    proj, out, rest = {}, {}, set()
    for l in run.rd("settings.txt", run.manager_dir(team)).splitlines():
        f = l.strip().split("|")
        if l.startswith("#") or len(f) != 3:
            continue
        try:
            if f[0] == "proj":
                proj[f[1]] = float(f[2])
            elif f[0] == "out_until":
                out[f[1]] = dt.date.fromisoformat(f[2])
            elif f[0] == "rest_b2b":
                rest.add(f[1])
        except ValueError:
            pass
    return proj, out, rest


def slot_values(proj):
    """name -> {slot: CBS FP/G at that slot} from pool_all.txt (same fill-in and overrides as the page)."""
    sv = {}
    for l in run.rd("pool_all.txt").splitlines():
        p = l.split("|")
        if l.startswith("#") or len(p) < 8:
            continue
        n, pos = p[0], p[2]
        s = {k: float(v) for k, v in zip("GFC", p[5:8]) if v}
        for k in pos.split(","):
            if k not in s and s:
                s[k] = max(s.values())
        if n in proj:
            s = {k: proj[n] for k in (s or dict.fromkeys(pos.split(",")))}
        sv[n] = s
    return sv


def best_lineup(pl):
    """pl: [(name, {slot: value})]. Best G, F, C + 2 Util lineup: (points, set of names). An empty G/F/C slot stays empty.
    Ties keep the earlier players in pl (your current starters go first, so a tie never suggests a pointless swap)."""
    top = [max(s.values()) for _, s in pl]
    order = sorted(range(len(pl)), key=lambda i: -top[i])
    bv, bset = -1.0, set()
    opts = {r: [None] + [i for i, (_, s) in enumerate(pl) if r in s] for r in "GFC"}
    for g in opts["G"]:
        for f in opts["F"]:
            if f is not None and f == g:
                continue
            for c in opts["C"]:
                if c is not None and c in (g, f):
                    continue
                pick = [i for i in (g, f, c) if i is not None]
                v = sum(pl[i][1][r] for i, r in zip((g, f, c), "GFC") if i is not None)
                rest = [i for i in order if i not in pick and top[i] > 0][:2]
                v += sum(top[i] for i in rest)
                if v > bv + 1e-9:
                    bv, bset = v, {pl[i][0] for i in pick + rest}
    return max(bv, 0.0), bset


def check(team, day):
    """Read the lineup and compare. Returns (problem: bool, title, lines)."""
    from browser import Browser
    with Browser() as b:
        if not b.cbs_signed_in():
            return True, "Lineup check: CBS signed out", ["Double-click '2 - Sign in to CBS' so the lineup check can read your lineup."]
        rows = json.loads(b.cbs("fetch_myline", TEAM=team, DATE=day.strftime("%Y%m%d"), PERIOD=str(run.fperiod(day))) or "[]")
    if not rows:
        return True, "Lineup check: lineup not read", ["CBS showed no players for today."]
    proj, out, rest = settings(team)
    sv = slot_values(proj)
    games = {}
    for l in run.rd("opp.txt").splitlines():   # team -> played yesterday (for rest_b2b nights)
        f = l.split("|")
        if len(f) >= 3 and f[0] == (day - dt.timedelta(days=1)).strftime("%Y%m%d"):
            games[CBS_ABBR.get(f[1], f[1])] = games[CBS_ABBR.get(f[2], f[2])] = True
    why = {}   # player -> reason he can't score tonight
    for r in rows:
        n = r["n"]
        if r["sec"] == "I":
            why[n] = "on IR"
        elif not r["tip"]:
            why[n] = "no game"
        elif r["out"]:
            why[n] = "ruled out" + (f" ({r['inj'].split(':')[0]})" if r["inj"] else "")
        elif n in out and day < out[n]:
            why[n] = f"out until {out[n]:%b} {out[n].day} (your setting)"
        elif n in rest and games.get(CBS_ABBR.get(r["nba"], r["nba"])):
            why[n] = "rests the 2nd night of a back-to-back (your setting)"
        elif n not in sv or not sv[n]:
            why[n] = "no CBS projection"
    act = [r["n"] for r in rows if r["sec"] == "A"]
    plays = [(n, sv[n]) for n in sorted((r["n"] for r in rows if r["n"] not in why), key=lambda n: n not in act)]
    bv, bset = best_lineup(plays)
    cv, _ = best_lineup([(n, s) for n, s in plays if n in act])
    gtd = [r for r in rows if r["n"] in bset and r["inj"] and not r["out"] and r["sec"] == "A"]
    spare = [n for n, _ in plays if n not in bset]   # a reserve who plays tonight, to swap in if a game-time decision sits
    v = lambda n: max(sv.get(n, {"": 0}).values())
    lines = []
    dead = [n for n in act if n in why]
    if dead:
        lines.append("Starting but won't score: " + ", ".join(f"{n} ({why[n]})" for n in dead))
    start = sorted((n for n in bset if n not in act), key=lambda n: -v(n))
    sit = sorted((n for n in act if n not in bset and n not in why), key=v)
    gain = bv - cv
    if gain >= 1:
        lines.append("Start " + ", ".join(f"{n} ({v(n):.1f})" for n in start)
                     + (" · bench " + ", ".join(f"{n} ({v(n):.1f})" for n in sit) if sit else "")
                     + f": +{gain:.0f} projected")
    if gtd:
        lines.append("Game-time decision: " + ", ".join(f"{r['n']} ({r['inj'].split(':', 1)[-1].strip()})" for r in gtd))
    if gtd and spare:
        lines.append("If he sits, spares who play tonight: " + ", ".join(f"{n} ({v(n):.1f})" for n in spare[:3]))
    problem = gain >= 1
    title = (f"⚠️ Lineup: +{gain:.0f} pts available" if problem else "❓ Lineup: check a game-time decision" if gtd and spare else "✅ Lineup is set") + f" · {run.label_of(day)}"
    if not problem and not gtd:
        lines.insert(0, f"Your {len([n for n in act if n not in why])} starters are the best lineup from the {len(plays)} players who play tonight ({bv:.0f} projected).")
    return problem, title, lines


def main():
    args = sys.argv[1:]
    cfg, secret = run.read_config()
    team = run.my_team()
    if not team:
        print("Your team isn't known yet. Double-click '3 - Run now' first.")
        return
    now = run.now_calgary()
    day = now.date()
    lock = lock_time(day)
    st = run.rd("lineup_check_state.txt").split("|")
    runs, prob = (int(st[1]), st[2].strip() == "1") if len(st) == 3 and st[0] == day.strftime("%Y%m%d") else (0, False)
    if "--now" not in args:
        if cfg.get("lineup_check", "yes").lower() == "no" or not lock:
            return
        mins = (lock - now).total_seconds() / 60
        first = runs == 0 and 10 <= mins <= 90
        again = runs == 1 and prob and 5 <= mins <= 40
        if not (first or again):
            return
    problem, title, lines = check(team, day)
    lk = f"lineups lock {lock:%I:%M %p}".replace(" 0", " ") if lock else "no games today"
    text = "\n".join(lines) + f"\n({lk})"
    run.wr("lineup_check_state.txt", f"{day:%Y%m%d}|{runs + 1}|{1 if problem else 0}\n")
    os.makedirs(run.OUT, exist_ok=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(f"{now:%Y-%m-%d %H:%M} {title}\n" + "".join(f"   {l}\n" for l in lines))
    print(title)
    print(text)
    if problem or title.startswith("❓") or "--now" in args:
        if cfg.get("notify", "yes").lower() != "no":
            from notify import notify
            notify(title, " · ".join(lines)[:240])
        if problem and cfg.get("email", "yes").lower() == "yes" and secret:
            import html
            from mailer import send
            try:
                send(cfg, secret, title, "<p>" + "</p><p>".join(html.escape(l) for l in lines) + f"</p><p style='color:#667085'>{html.escape(lk)}. "
                     "Fix it on CBS before lock. (BBL Command Center lineup check)</p>", text)
            except Exception as e:
                print("email failed:", e)


if __name__ == "__main__":
    if sys.stdout is None:
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    main()
