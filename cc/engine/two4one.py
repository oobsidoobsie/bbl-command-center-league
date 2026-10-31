#!/usr/bin/env python3
"""2-for-1 trade finder for Oobsidoobsie. Run weekly (Monday nights) in the plan folder: python3 two4one.py "<Mon Oct 26>"
Packages pairs of your cheapest players (by lineup value; players listed as notrade| in settings.txt are left out) for one better rival player,
models both sides with the league scoring and best daily lineups, and writes:
  two4one.json        data read by plan.py (Waivers -> Trades -> 2-for-1 packages)
  two4one_email.html / two4one_email.txt / two4one_subject.txt   the weekly email"""
import sys, json, html, itertools, datetime as dt
LABEL = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().strftime('%a %b %-d')
sys.argv = ['plan.py']
src = open('plan.py', encoding='utf-8').read().split('# ---- rows')[0]
g = {'__file__': 'plan.py'}
exec(src, g)
R, OTH, INFO, ptot, REG, PO, FA, healthy, GA, tot, out, MV, short, G, P, gains, avail = [g[k] for k in
    'R OTH INFO ptot REG PO FA healthy GA tot out MV short G P gains avail'.split()]
NEVER = {l.split('|')[1] for l in open('settings.txt', encoding='utf-8') if l.startswith('notrade|') and l.count('|') >= 2}  # players this manager won't trade
T = lambda r, ps: sum(ptot(r, p) for p in ps)
myR, myP = T(R, REG), T(R, PO)
cheap = sorted([n for n in R if n not in NEVER and not (n in out and out[n] > g['TODAY'] + dt.timedelta(30))],
               key=lambda n: tot(MV[n], REG) + tot(MV[n], PO))[:4]
pairs = list(itertools.combinations(cheap, 2))
lo = min(INFO[n]['best'] for n in cheap)
base = {k: (T(ro, REG), T(ro, PO)) for k, ro in OTH.items()}
res = []
for k, ro in OTH.items():
    for X, (t, s) in ro.items():
        b = INFO[X]['best']
        if b < max(lo, 33) or b > 44 or X in out: continue
        for A, B in pairs:
            r = dict(R); del r[A]; del r[B]; r[X] = (t, s)
            mr, mp = T(r, REG) - myR, T(r, PO) - myP
            if mr + mp <= 0: continue
            o = dict(ro); del o[X]; o[A] = R[A]; o[B] = R[B]
            D = min([n for n in o if n not in (A, B)], key=lambda n: INFO[n]['best']); del o[D]
            tr, tp = T(o, REG) - base[k][0], T(o, PO) - base[k][1]
            res.append(dict(team=k, X=X, pos=INFO[X]['pos'], nt=INFO[X]['team'], best=round(b, 1), give=[A, B],
                            mr=round(mr), mp=round(mp), tr=round(tr), tp=round(tp), drop=D))
# ---- target watch: fixed targets (settings.txt target|Name|1) + every rival-owned player from target teams (target_team|POR|1)
TGT, TTEAM = [], []
for l in open('settings.txt', encoding='utf-8'):
    f = l.strip().split('|')
    if len(f) == 3 and f[0] == 'target': TGT.append(f[1])
    if len(f) == 3 and f[0] == 'target_team': TTEAM.append(f[1])
owner = {X: k for k, ro in OTH.items() for X in ro}
tlist = list(dict.fromkeys([n for n in TGT if n in owner] + [X for X in owner if INFO[X]['team'] in TTEAM]))
try:
    _pj = json.load(open('two4one.json', encoding='utf-8'))
    prev = {t['X']: t for t in _pj.get('targets', []) + [q for tt in _pj.get('teams', []) for q in tt.get('players', [])]}
except Exception: prev = {}
gpool = sorted([n for n in R if n not in NEVER and not (n in out and out[n] > g['TODAY'] + dt.timedelta(30))],
               key=lambda n: tot(MV[n], REG) + tot(MV[n], PO))[:8]
def package(X, fixed=False):
    k = owner[X]; ro = OTH[k]; t, s = ro[X]
    opts = []
    for size in (1, 2):
        for gv in itertools.combinations([n for n in gpool if INFO[n]['best'] < INFO[X]['best'] + 3], size):
            r = dict(R)
            for n in gv: del r[n]
            r[X] = (t, s)
            mr, mp = T(r, REG) - myR, T(r, PO) - myP
            if mr + mp <= 0: continue
            o = dict(ro); del o[X]
            for n in gv: o[n] = R[n]
            D = None
            if size == 2:
                D = min([n for n in o if n not in gv], key=lambda n: INFO[n]['best']); del o[D]
            tr, tp = T(o, REG) - base[k][0], T(o, PO) - base[k][1]
            opts.append(dict(give=list(gv), mr=round(mr), mp=round(mp), tr=round(tr), tp=round(tp), drop=D))
    realistic = sorted([o for o in opts if o['tr'] >= -250], key=lambda o: -(o['mr'] + o['mp']))
    bestyou = max(opts, key=lambda o: o['mr'] + o['mp'], default=None)
    easiest = max(opts, key=lambda o: o['tr'], default=None)
    pick = realistic[0] if realistic else easiest
    p0 = prev.get(X); change = ''
    if pick and p0 and p0.get('pick'):
        q = p0['pick']; dyou = (pick['mr'] + pick['mp']) - (q['mr'] + q['mp']); dthem = pick['tr'] - q['tr']
        if (realistic and not p0.get('realistic')) or dyou >= 50 or dthem >= 75: change = 'price dropped'
        elif dyou <= -50 or dthem <= -75: change = 'price rose'
    return dict(X=X, team=k, nt=INFO[X]['team'], pos=INFO[X]['pos'], best=round(INFO[X]['best'], 1),
                fixed=fixed, realistic=bool(realistic), pick=pick, bestyou=bestyou, alts=realistic[1:3], change=change)
# ---- best NBA schedules for you: a generic 35 FP/G player (any slot) on each team, added in place of the stream slot
TEAMS = sorted(G.keys())
GEN = {'G': 35.0, 'F': 35.0, 'C': 35.0}
def openn(d): return 5 - min(5, len(avail(R, d)))
tv = []
for tm in TEAMS:
    gn = gains('__gen_' + tm, tm, GEN)
    reg, po = tot(gn, REG), tot(gn, PO)
    dr = [d for p in REG for d in P[p] if d in G[tm]]; dp = [d for p in PO for d in P[p] if d in G[tm]]
    tv.append(dict(t=tm, reg=round(reg), po=round(po), score=round(reg + 2 * po), g_reg=len(dr), g_po=len(dp),
                   open_reg=sum(1 for d in dr if openn(d) > 0), open_po=sum(1 for d in dp if openn(d) > 0),
                   b2b=sum(1 for d in dr if d - dt.timedelta(1) in G[tm])))
tv.sort(key=lambda x: -x['score'])
for i, x in enumerate(tv): x['rank'] = i + 1
NTOP = 5
teams = []
for x in tv[:NTOP]:
    tm = x['t']
    riv = sorted([X for X in owner if INFO[X]['team'] == tm and INFO[X]['best'] >= 24 and X not in out], key=lambda X: -INFO[X]['best'])[:4]
    x['players'] = [package(X) for X in riv]
    fa = sorted([(tot(GA[n], REG), tot(GA[n], PO), n) for n in FA if INFO[n]['team'] == tm and healthy(n)], reverse=True)[:3]
    x['fa'] = [dict(n=n, pos=INFO[n]['pos'], best=round(INFO[n]['best'], 1), reg=round(a), po=round(b)) for a, b, n in fa if a + b > 0]
    x['mine'] = [n for n in R if R[n][0] == tm]
    teams.append(x)
targets = [package(X, True) for X in TGT if X in owner and not any(X == q['X'] for tt in teams for q in tt['players'])]
tfa = []
tfa = [dict(n=n, nt=INFO[n]['team'], pos=INFO[n]['pos'], best=round(INFO[n]['best'], 1), reg=round(a), po=round(b)) for a, b, n in tfa]
fills = sorted([(tot(GA[n], REG), n) for n in FA if healthy(n)], reverse=True)[:2]
real = sorted([x for x in res if x['tr'] >= -250], key=lambda x: -(x['mr'] + x['mp']))[:8]
out_json = dict(label=LABEL, date=g['TODAY'].isoformat(), give=cheap, deals=real,
                fill=[dict(n=n, reg=round(v)) for v, n in fills], tested=len(res), targets=targets, target_teams=TTEAM, target_fa=tfa, teams=teams, team_rank=[{k: x[k] for k in ('t','reg','po','score','g_reg','g_po','open_reg','open_po','b2b','rank')} for x in tv])
json.dump(out_json, open('two4one.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
# ---- weekly email
tn = lambda k: 'TINOLA' if 'ɪɴᴏʟᴀ' in k else k
def odds(x): return 'likely yes' if x['tr'] >= 0 else ('fair' if x['tr'] >= -120 else 'needs a sweetener')
rows = ''.join(f'<tr><td style="padding:6px 8px;border-bottom:1px solid #ddd">{" + ".join(html.escape(short(n)) for n in x["give"])}</td>'
               f'<td style="padding:6px 8px;border-bottom:1px solid #ddd"><b>{html.escape(short(x["X"]))}</b> ({x["nt"]}, {x["pos"]}, {x["best"]})</td>'
               f'<td style="padding:6px 8px;border-bottom:1px solid #ddd">{html.escape(tn(x["team"]))}</td>'
               f'<td style="padding:6px 8px;border-bottom:1px solid #ddd"><b>{x["mr"]:+}</b> / {x["mp"]:+}</td>'
               f'<td style="padding:6px 8px;border-bottom:1px solid #ddd">{x["tr"]:+} / {x["tp"]:+} · {odds(x)}</td></tr>' for x in real[:5])
eh = (f'<p><b>🔁 2-for-1 trade report · {html.escape(LABEL)}</b></p>'
      f'<p>Packaging your cheapest pieces ({", ".join(html.escape(short(n)) for n in cheap)}) for one better player. Only deals that cost the other manager 250 regular-season points or less are shown.</p>'
      + (f'<table style="border-collapse:collapse;font-size:13px"><tr><th align="left" style="padding:6px 8px">You give</th><th align="left" style="padding:6px 8px">You get</th><th align="left" style="padding:6px 8px">From</th><th align="left" style="padding:6px 8px">You: reg / playoffs</th><th align="left" style="padding:6px 8px">Them: reg / playoffs</th></tr>{rows}</table>' if real else '<p>No realistic 2-for-1 this week.</p>')
      + (f'<p>The open roster spot is worth extra: best free agent to fill it is {html.escape(short(fills[0][1]))} (+{fills[0][0]:.0f} rest of the regular season).</p>' if fills else '')
      + (('<p><b>🎯 Target watch · best schedules for you</b> (teams whose games land on your open lineup nights)</p><ol>' +
          ''.join(f'<li><b>{x["t"]}</b> · +{x["reg"]} reg / {x["po"]:+} playoffs for a 35 FP/G player · {x["g_po"]} playoff games ({x["open_po"]} on open nights)'
                  + ''.join(f'<br>&nbsp;&nbsp;{html.escape(short(t["X"]))} ({html.escape(tn(t["team"]))})' + (f' <b>· {t["change"].upper()}</b>' if t["change"] else '') + ': '
                            + (f'{" + ".join(html.escape(short(n)) for n in t["pick"]["give"])} → you {t["pick"]["mr"]:+}/{t["pick"]["mp"]:+}, them {t["pick"]["tr"]:+}/{t["pick"]["tp"]:+}' + ('' if t["realistic"] else ' (big ask)') if t["pick"] else 'no package helps you') for t in x['players'])
                  + (('<br>&nbsp;&nbsp;Free agents: ' + ', '.join(f'{html.escape(short(f["n"]))} (+{f["reg"]})' for f in x['fa'])) if x['fa'] else '') + '</li>' for x in teams)
          + '</ol>') if teams else '')
      + f'<p>Trade deadline: Thu Feb 25, 11:59 PM ET. Full table: Command Center → Trades</p>')
et = (f'2-for-1 trade report · {LABEL}\nGive from: {", ".join(short(n) for n in cheap)}\n' +
      ''.join(f'- {" + ".join(short(n) for n in x["give"])} → {short(x["X"])} ({tn(x["team"])}): you {x["mr"]:+}/{x["mp"]:+}, them {x["tr"]:+}/{x["tp"]:+} ({odds(x)})\n' for x in real[:5]) +
      ''.join(f'TEAM {x["t"]}: +{x["reg"]} reg / {x["po"]:+} playoffs; ' + '; '.join(f'{short(t["X"])} ({tn(t["team"])}){" ["+t["change"]+"]" if t["change"] else ""}: ' + (f'{" + ".join(short(n) for n in t["pick"]["give"])} -> you {t["pick"]["mr"]:+}/{t["pick"]["mp"]:+}, them {t["pick"]["tr"]:+}/{t["pick"]["tp"]:+}' if t["pick"] else 'no package') for t in x['players']) + '\n' for x in teams) +
      'Full table: Command Center → Trades\n')
open('two4one_email.html', 'w', encoding='utf-8').write(eh)
open('two4one_email.txt', 'w', encoding='utf-8').write(et)
top = real[0] if real else None
drops = [short(t['X']) for x in teams for t in x['players'] if t['change'] == 'price dropped']
open('two4one_subject.txt', 'w', encoding='utf-8').write(
    f'🔁 BBL 2-for-1 report — {LABEL}' + (f': {" + ".join(short(n) for n in top["give"])} → {short(top["X"])}' if top else '') + (f' · 🎯 price drop: {", ".join(drops)}' if drops else ''))
print('give', cheap, 'tested', len(res), 'shown', len(real))
