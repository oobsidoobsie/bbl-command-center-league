#!/usr/bin/env python3
"""Breakout detector for BBL (points league).
Usage: python3 breakout.py log.txt pool.txt "<label>" [notes.html] [email]
log.txt lines: name|team|espnpos|n|MMDD:min:basefp:reb:ast:3pm,...  (oldest -> newest)
Writes breakout.html (or breakout_email.html with 'email').

Tiers (last 3 games vs baseline; baseline = CBS projected FP/G, else his earlier games):
  BREAKOUT  : L3 best-slot avg >= 30 AND >= 1.30x baseline AND 2 of 3 games >= 30
              AND minutes up (L3 MPG >= earlier MPG + 4, or >= 28 MPG)
  HEATING UP: L3 avg >= 28 AND >= 1.25x baseline AND one 30+ game AND minutes not down (top 8)
Stars already projected >= 45 FP/G are skipped (not a breakout, just good).
"""
import sys, os, html
logf, poolf, label = sys.argv[1], sys.argv[2], sys.argv[3]
notesf = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != 'email' else None
EMAIL = 'email' in sys.argv[4:]

POOL = {}
for l in open(poolf):
    if l.startswith('#') or '|' not in l: continue
    p = l.rstrip('\n').split('|')
    proj = max([float(x) for x in p[5:8] if x] or [0])
    POOL[p[0]] = dict(pos=p[2], own=p[3], proj=proj)

NOTES = {}
if notesf and os.path.exists(notesf):  # name|one-line catalyst/news/sentiment (filled by the nightly run)
    for l in open(notesf):
        if '|' in l:
            n, t = l.rstrip('\n').split('|', 1); NOTES[n] = t

def slotfp(base, reb, ast, tpm, pos):
    b = {'G': reb, 'F': ast, 'C': tpm}
    el = [s for s in 'GFC' if s in pos] or ['F']
    s = max(el, key=lambda k: b[k]); return base + b[s], s

out = []
for l in open(logf):
    if '|' not in l: continue
    n, t, ep, _, gs = l.rstrip('\n').split('|')
    pi = POOL.get(n, {})
    pos = pi.get('pos') or ep
    G = []
    for g in gs.split(','):
        d, mi, fp, r, a, tp = g.split(':')
        G.append((d, int(mi), *slotfp(int(fp), int(r), int(a), int(tp), pos)))
    if len(G) < 3: continue
    L3, prev = G[-3:], G[:-3]
    a3 = sum(x[2] for x in L3) / 3
    m3 = sum(x[1] for x in L3) / 3
    mp = sum(x[1] for x in prev) / len(prev) if prev else None
    base = pi.get('proj') or (sum(x[2] for x in prev) / len(prev) if prev else 0)
    if base >= 45: continue
    ratio = a3 / base if base else 9
    big = sum(1 for x in L3 if x[2] >= 30)
    minup = (mp is not None and m3 >= mp + 4) or m3 >= 28
    mindown = mp is not None and m3 < mp - 3
    tier = None
    if a3 >= 30 and ratio >= 1.30 and big >= 2 and minup: tier = 'BREAKOUT'
    elif a3 >= 28 and ratio >= 1.25 and big >= 1 and not mindown: tier = 'HEATING UP'
    if tier: out.append(dict(n=n, t=t, pos=pos, own=pi.get('own', 'FA?'), a3=a3, base=base, ratio=ratio,
                             m3=m3, mp=mp, L3=L3, tier=tier))

out.sort(key=lambda x: (x['tier'] != 'BREAKOUT', -(x['a3'] - x['base'])))
out = [x for x in out if x['tier'] == 'BREAKOUT'] + [x for x in out if x['tier'] != 'BREAKOUT'][:8]
e = html.escape
def owner(o):
    if o == 'MINE': return '★ yours'
    if o.startswith('TAKEN:'): return o[6:]
    return 'FA — available' if o == 'FA' else 'FA (unranked)'
GREEN, GRAY = '#1f9d55', '#9fb3bd'
rows = []
for x in out:
    tag = '🚀 BREAKOUT' if x['tier'] == 'BREAKOUT' else '🔥 Heating up'
    games = ' · '.join(f"{g[2]}<span style='color:{GRAY};font-size:11px'> {g[3]} {g[1]}m</span>" for g in x['L3'])
    mins = f"{x['m3']:.0f}" + (f" (was {x['mp']:.0f})" if x['mp'] is not None else '')
    ownc = GREEN if not x['own'].startswith('TAKEN') and x['own'] != 'MINE' else 'inherit'
    rows.append(f"<tr><td>{tag}</td><td><b>{e(x['n'])}</b> <span style='color:{GRAY};font-size:11px'>{x['t']} · {x['pos']}</span></td>"
                f"<td style='color:{ownc}'>{e(owner(x['own']))}</td><td><b style='color:{GREEN}'>{x['a3']:.1f}</b></td>"
                f"<td>{x['base']:.1f}</td><td>{x['ratio']:.2f}×</td><td>{mins}</td><td>{games}</td>"
                f"<td style='font-size:12px'>{e(NOTES.get(x['n'], ''))}</td></tr>")
tbl = ("<table cellpadding='4' cellspacing='0' border='1' bordercolor='#e5e7eb' style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px'>"
       "<tr><th align='left'>Alert</th><th align='left'>Player</th><th align='left'>Owner</th><th align='left'>L3 avg</th>"
       "<th align='left'>Proj</th><th align='left'>vs proj</th><th align='left'>MPG L3</th><th align='left'>Last 3 (best-slot pts · slot · min)</th>"
       "<th align='left'>Why / news &amp; buzz</th></tr>" + ''.join(rows) + "</table>") if rows else "<p>No breakout signals tonight.</p>"
legend = (f"<p style='font-size:12px;color:#667085'>🚀 Breakout = last-3 best-slot avg ≥30, ≥1.3× his CBS projection, 2 of 3 games ≥30, and minutes up "
          f"(+4 MPG or ≥28). 🔥 Heating up (top 8) = last-3 avg ≥28, ≥1.25× projection, at least one 30+ game, minutes not falling. Projected 45+ stars excluded.</p>")
summ = ''
if os.path.exists('breakout_summary.html'): summ = open('breakout_summary.html').read()
frag = (f"<div style='font-family:Arial,sans-serif'><h3 style='font-size:17px;margin:18px 0 6px'>🚀 Breakout alerts · {e(label)}</h3>"
        f"{summ}<div style='overflow-x:auto'>{tbl}</div>{legend}</div>")
open('breakout_email.html' if EMAIL else 'breakout.html', 'w').write(frag)
open('breakout.tsv','w').write(''.join(f"{x['n']}|{x['tier']}|{x['a3']:.1f}|{x['base']:.1f}|{x['own']}|{NOTES.get(x['n'],'')}\n" for x in out))
for x in out: print(x['tier'], x['n'], x['own'], round(x['a3'], 1), round(x['base'], 1), round(x['ratio'], 2), round(x['m3']), x['mp'] and round(x['mp']))
