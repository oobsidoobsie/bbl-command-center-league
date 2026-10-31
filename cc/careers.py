"""Past-season stats and profiles for every player in the box scores, from ESPN's public player pages (read-only), saved
once for the player card. Past seasons and birth dates don't change, so a player is fetched only the first time he shows up.

data/careers.txt: espnid|season|team|gp|min|fgm|fga|3pm|3pa|ftm|fta|reb|ast|stl|blk|to|pf|pts   (regular-season totals)
                  espnid|-   when he has no season before this one (a rookie), so he isn't asked for again
  A traded season is ESPN's "Totals" row, team shown as DAL/LAL. This season isn't saved: the page has it from the box scores.
data/bio.txt:     espnid|height (7-4)|weight (lbs)|birth date (M/D/YYYY)|jersey|experience|draft
  The page works out his age from the birth date, so it stays right.

    python cc/careers.py      fetch any players missing from data/careers.txt or data/bio.txt
"""
import glob
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

THIS_SEASON = "2026-27"
URL = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{}/stats?region=us&lang=en&contentorigin=espn&_={}"
BIO_URL = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{}?region=us&lang=en&_={}"
TOT = ["fieldGoalsMade-fieldGoalsAttempted", "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
       "freeThrowsMade-freeThrowsAttempted", "totalRebounds", "assists", "steals", "blocks", "turnovers", "fouls", "points"]


def _get(pid, url=URL):
    for _ in range(3):   # ESPN sometimes answers with an empty body; a fresh cache-buster usually fixes it
        try:
            b = urllib.request.urlopen(url.format(pid, int(time.time() * 1000)), timeout=30).read()
            if b:
                return json.loads(b)
        except (OSError, ValueError):
            pass
        time.sleep(2)
    return None


def fetch_one(pid):
    """careers.txt lines for one player, or None if ESPN didn't answer (tried again next run)."""
    j = _get(pid)
    if j is None:
        return None
    cats = {c.get("name"): c for c in j.get("categories", [])}
    tot, avg = cats.get("totals"), cats.get("averages")
    if not tot or not avg:
        return [f"{pid}|-"]
    abbr = {k: v.get("abbreviation", "") for k, v in (j.get("teams") or {}).items()}
    ti = {n: i for i, n in enumerate(tot.get("names", []))}
    ai = {n: i for i, n in enumerate(avg.get("names", []))}
    if any(n not in ti for n in TOT) or "gamesPlayed" not in ai or "avgMinutes" not in ai:
        return [f"{pid}|-"]
    seasons = {}   # season -> (kind, totals row, averages row); a "Totals" row (traded) wins
    teams = {}
    for s_t, s_a in zip(tot.get("statistics", []), avg.get("statistics", [])):
        se = (s_t.get("season") or {}).get("displayName", "")
        if not se or se >= THIS_SEASON:
            continue
        slug = s_t.get("teamSlug", "")
        if slug in abbr:
            teams.setdefault(se, []).append(abbr[slug])
            seasons.setdefault(se, (None, s_t, s_a))
        else:   # "2024-25 Totals"
            seasons[se] = ("total", s_t, s_a)
    out = []
    for se, (_, s_t, s_a) in sorted(seasons.items()):
        st, sa = s_t["stats"], s_a["stats"]
        try:
            gp = int(float(sa[ai["gamesPlayed"]]))
            mi = round(float(sa[ai["avgMinutes"]]) * gp)
            fg, tp, ft = (st[ti[n]].split("-") for n in TOT[:3])
            rest = [st[ti[n]] for n in TOT[3:]]
            nums = [gp, mi, *fg, *tp, *ft, *rest]
            out.append("|".join([str(pid), se, "/".join(teams.get(se, [])) or "-"] + [str(int(float(x))) for x in nums]))
        except (KeyError, ValueError, IndexError):
            continue
    return out or [f"{pid}|-"]


def fetch_bio(pid):
    """One bio.txt line, or None if ESPN didn't answer (tried again next run)."""
    j = _get(pid, BIO_URL)
    if j is None:
        return None
    a = j.get("athlete") or {}
    h = (a.get("displayHeight") or "").replace("' ", "-").replace("'", "-").replace('"', "")   # 7' 4" -> 7-4
    v = [h, (a.get("displayWeight") or "").replace(" lbs", ""), a.get("displayDOB") or "", a.get("jersey") or "",
         a.get("displayExperience") or "", a.get("displayDraft") or ""]
    return "|".join([str(pid)] + [str(x).replace("|", "/") for x in v])


def _known(path):
    return {l.split("|", 1)[0] for l in open(path, encoding="utf-8") if l.strip()} if os.path.exists(path) else set()


def update(data_dir, say=print, workers=8):
    """Fetch the players in data_dir's box scores who aren't in careers.txt / bio.txt yet."""
    ids = set()
    for bf in glob.glob(os.path.join(data_dir, "box_*.txt")):
        for l in open(bf, encoding="utf-8"):
            f = l.rstrip("\n").split("|")
            if len(f) >= 18 and f[-1].strip().isdigit():
                ids.add(f[-1].strip())
    cpath, bpath = os.path.join(data_dir, "careers.txt"), os.path.join(data_dir, "bio.txt")
    ctodo, btodo = sorted(ids - _known(cpath)), sorted(ids - _known(bpath))
    if not ctodo and not btodo:
        return 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        cres = list(pool.map(fetch_one, ctodo))
        bres = list(pool.map(fetch_bio, btodo))
    cgot = [lines for lines in cres if lines]
    bgot = [l for l in bres if l]
    if cgot:
        with open(cpath, "a", encoding="utf-8") as f:
            for lines in cgot:
                f.write("\n".join(lines) + "\n")
    if bgot:
        with open(bpath, "a", encoding="utf-8") as f:
            f.write("\n".join(bgot) + "\n")
    miss = len(ctodo) - len(cgot) + len(btodo) - len(bgot)
    say(f"Player cards: {len(cgot)} past-season and {len(bgot)} profile record(s) saved" + (f", {miss} to retry next run" if miss else ""))
    return len(cgot) + len(bgot)


if __name__ == "__main__":
    update(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
