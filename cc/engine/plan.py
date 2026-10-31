#!/usr/bin/env python3
"""Oobsidoobsie season plan builder. Usage: python3 plan.py [YYYY-MM-DD]
Inputs (same folder): hb.txt (NBA schedule grid), pool.txt (CBS pool: name|team|pos|own|gp|G|F|C),
watch.txt, settings.txt, head.html. Output: season_plan.html"""
import itertools, datetime as dt, html, sys, os, math, re, glob, json, time, base64, zlib
from collections import defaultdict
os.chdir(os.path.dirname(os.path.abspath(__file__)))
def _prog(pct,label,nxt=100,secs=1):   # rebuild progress for the page's Apply & rebuild bar (cc\serve.py sets BBL_PROGRESS to a file); nxt/secs = next step's % and this step's usual seconds
    f=os.environ.get('BBL_PROGRESS')
    if f:
        try:
            with open(f,'a',encoding='utf-8') as _pf: _pf.write(f'plan|{pct}|{label}|{nxt}|{secs}|{time.time():.1f}\n')
        except OSError: pass
_prog(0,'Reading your roster and the schedule',8,2.6)
TODAY=dt.date.fromisoformat(sys.argv[1]) if len(sys.argv)>1 else (dt.datetime.utcnow()-dt.timedelta(hours=6)).date()
LAST=dt.date(2027,4,2)
# ---- schedule
mon={'Oct':10,'Nov':11,'Dec':12,'Jan':1,'Feb':2,'Mar':3,'Apr':4}
G=defaultdict(set)
for line in open('hb.txt'):
    line=line.strip()
    if not line: continue
    head,ncol,teams=line.split('#'); wk,dates=head.split(': ')
    d0=dates.split(' - ')[0].split(); m=mon[d0[1]]; y=2026 if m>=10 else 2027
    start=dt.date(y,m,int(d0[0]))
    for t in teams.split():
        tm,idx=t.split(':')
        for i in map(int,idx.split('.')):
            if wk=='W17': d=dt.date(2027,2,15)+dt.timedelta(i if i<4 else i+6)
            else: d=start+dt.timedelta(i)
            if d<=LAST: G[tm].add(d)
def period(d): return 1 if d<=dt.date(2026,10,25) else 2+(d-dt.date(2026,10,26)).days//7
def pstart(p): return dt.date(2026,10,20) if p==1 else dt.date(2026,10,26)+dt.timedelta(7*(p-2))
def pend(p): return dt.date(2026,10,25) if p==1 else min(LAST,pstart(p)+dt.timedelta(6))
CUR=period(max(TODAY,dt.date(2026,10,20)))
ALLD=sorted({d for t in G for d in G[t] if d>=TODAY})
P=defaultdict(list)
for d in ALLD: P[period(d)].append(d)
PER=[p for p in range(CUR,25)]
REG=[p for p in PER if p<=21]; PO=[p for p in PER if p>=22]
# ---- whose Command Center this is (BBL_ME, default Oobsidoobsie)
ME=os.environ.get('BBL_ME','Oobsidoobsie')
MEKEY='TINOLA' if 'ɪɴᴏʟᴀ' in ME else ME   # matchups.txt and the division list use the short TINOLA name
MEDISP="TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in ME else ME
# ---- settings
proj={}; out={}; FORCE=None; KEEP=set(); REST=set()   # REST: rest_b2b| players, who sit the 2nd night of back-to-backs
for l in open('settings.txt',encoding='utf-8-sig',errors='replace'):
    if l.startswith('#') or not l.strip(): continue
    k,n,v=l.strip().split('|')
    if k=='proj': proj[n]=float(v)
    if k=='out_until': out[n]=dt.date.fromisoformat(v)
    if k=='stream': FORCE=n
    if k=='keep': KEEP.add(n)
    if k=='rest_b2b': REST.add(n)
watch=[l.strip() for l in open('watch.txt') if l.strip() and not l.startswith('#')]
# CBS Roster Trends: rostered % across all CBS leagues for the 50 most-added / 50 most-dropped players (trends.txt)
RT={}
if os.path.exists('trends.txt'):
    for l in open('trends.txt'):
        f=l.rstrip('\n').split('|')
        if len(f)>=6:
            try: RT[f[0]]=(int(f[3]),int(f[4]),int(f[5]))
            except ValueError: pass
# ESPN ownership (espn_rost.txt: name|pct owned|change this wk|pct started|rank), pulled nightly from ESPN's public fantasy API.
# ESPN has no league-size split; rank <= 150 is a proxy for "rostered in a 10-team, 15-man league".
import unicodedata as _ud, re as _re
def nk(n):
    n=_ud.normalize('NFKD',n).encode('ascii','ignore').decode().lower()
    n=_re.sub(r"[.'’\-]",'',n)
    n=_re.sub(r'\b(jr|sr|ii|iii|iv)\b','',n)
    return ' '.join(n.split())
NKALIAS={'gregory jackson':'gg jackson','nicolas claxton':'nic claxton','cam johnson':'cameron johnson','herb jones':'herbert jones','ron holland':'ronald holland','moe wagner':'moritz wagner'}
RE={}
USE_ESPN=False  # CBS numbers only; ESPN ownership is not shown
if USE_ESPN and os.path.exists('espn_rost.txt'):
    for l in open('espn_rost.txt',encoding='utf-8'):
        f=l.rstrip('\n').split('|')
        if len(f)>=5:
            try: RE[nk(f[0])]=(float(f[1]),float(f[2]),float(f[3]),int(f[4]))
            except ValueError: pass
def es(n):
    k=nk(n); return RE.get(k) or RE.get(NKALIAS.get(k,''))
TEN=150
ES_='<span class="src es">ESPN</span>'; CB_='<span class="src cb">CBS</span>'
def _p(x): return f'{x:.0f}' if x>=10 else (f'{x:.1f}'.rstrip('0').rstrip('.') if x>=0.1 else '<0.1')
def _a(d,unit=''):
    return f'▲{d:g}{unit}' if d>0 else (f'▼{-d:g}{unit}' if d<0 else '±0')
def rost(n,small=False):
    e=es(n); c=RT.get(n)
    if not e and not c: return ''
    parts=[]
    if e:
        parts.append(f'<span title="Rostered in {e[0]:.1f}% of ESPN leagues, started in {e[2]:.1f}% (rank {e[3]} by ownership)">{ES_}{_p(e[0])}% rostered <small>{_a(round(e[1],1))} this wk</small></span>')
    if c:
        lab=f'{CB_}{c[1]}%' if e else f'{CB_}{c[1]}% rostered'
        parts.append(f'<span title="Rostered in {c[1]}% of CBS leagues ({c[0]}% last week)">{lab} <small>{_a(c[2])}{"" if e else " this wk"}</small></span>')
    return '<span class="rost">'+' · '.join(parts)+'</span>'
def ten(n):
    e=es(n)
    if e and e[3]<=TEN and n in FA: return f'<span class="tag ok" title="ESPN ownership rank {e[3]}: players in the top 150 would be rostered in a typical 10-team, 15-man league">🔟 10-team level</span>'
    return ''
def rtier(n):
    e=es(n); c=RT.get(n)
    if (e and e[1]<=-1) or (c and c[2]<=-5): return '<span class="tag bad">📉 being dropped</span>'
    if e:
        if e[0]<10 and e[1]>0: return '<span class="tag ok">🕵️ under the radar</span>'
        if e[0]<=40 and e[1]>=1: return '<span class="tag warn">⏳ act now</span>'
        if e[0]>60: return '<span class="tag">📢 priced in</span>'
        return ''
    if c:
        a,cc,d=c
        if cc<30 and d>0: return '<span class="tag ok">🕵️ under the radar</span>'
        if cc<=60 and d>=10: return '<span class="tag warn">⏳ act now</span>'
        if cc>60: return '<span class="tag">📢 priced in</span>'
    return ''
# BBL draft results (draft.txt: name|round|pick|overall|fantasy team), read once from the league's /draft/results page
DR={}
if os.path.exists('draft.txt'):
    for l in open('draft.txt',encoding='utf-8'):
        f=l.rstrip('\n').split('|')
        if len(f)>=5:
            try: DR[nk(f[0])]=(int(f[1]),int(f[2]),int(f[3]),f[4])
            except ValueError: pass
_VR={}
def vrank(n):
    if not _VR:
        for i,m in enumerate(sorted(INFO,key=lambda m:-INFO[m]['best'])): _VR[m]=i+1
    return _VR.get(n)
def drf(n): return DR.get(nk(n))
def dsp(n): return (' '+dtag(n,True)) if drf(n) else ''
def dtn(t): return "TINOLA" if 'ɪɴᴏʟᴀ' in t else t
def dtag(n,own=False):
    d=drf(n)
    if not d: return ''
    r,p,o,t=d; vr=vrank(n); plays=(vr+9)//10 if vr else None
    out=f'<span class="tag" title="BBL draft: round {r}, pick {p} (#{o} overall) by {html.escape(dtn(t))}">Rd {r} · #{o}</span>'
    if n in FA: out+=f' <span class="tag warn" title="{html.escape(dtn(t))} drafted him in round {r} and has since dropped him">drafted by {html.escape(dtn(t))}, dropped</span>'
    elif plays and r>=7 and plays<=r-3:
        out+=(f' <span class="tag ok" title="Drafted in round {r}; his CBS projection ranks #{vr}, which is round-{plays} value">💰 sell-high chip · plays like Rd {plays}</span>' if own else
              f' <span class="tag ok" title="Drafted in round {r}; his CBS projection ranks #{vr}, which is round-{plays} value. Managers often value players by what they paid, so he may be a cheaper ask than his production">💰 late-pick value · plays like Rd {plays}</span>')
    return out
# ---- pool
R={}; FA={}; INFO={}; OTH={}; LOGO={}; EXTRA=[]; SV={}; GLOG={}; CBSFP={}; CBSGP={}   # SV: every pool player's (team, slot values)
for l in open('pool.txt'):
    p=l.rstrip('\n').split('|')
    if p[0]=='#LOGO' and len(p)>=3: LOGO[p[1]]=p[2]; continue
    if p[0]=='#GLOG' and len(p)>=3:   # CBS game log of one of your players: M/D:fpts,...
        GLOG[p[1]]=[x.split(':') for x in p[2].strip().split(',') if x.count(':')==1]; continue
    if p[0]=='#ALL' and len(p)>=5: EXTRA.append((p[1],p[2],p[3],float(p[4] or 0))); continue
    if len(p)<8: continue
    n,t,pos,own,gp=p[:5]; s={k:float(v) for k,v in zip('GFC',p[5:8]) if v}
    for k in pos.split(','):
        if k not in s and s: s[k]=max(s.values())  # slot value missing on CBS page -> use best
    CBSFP[n]=max(s.values()) if s else 0; CBSGP[n]=float(gp or 0)   # CBS's own projection, before any proj| override
    if n in proj:
        if not s: s={k:proj[n] for k in pos.split(',')}
        s={k:proj[n] for k in s}
        if not float(gp or 0): gp='78.5'  # manual projection for a player CBS hasn't projected
    INFO[n]=dict(team=t,pos=pos,own=own,gp=float(gp or 0),best=max(s.values()) if s else 0); SV[n]=(t,s)
    sec=p[8] if len(p)>8 else ''
    INFO[n]['sec']=sec
    INFO[n]['slot'],INFO[n]['rost'],INFO[n]['start']=(p[9:12]+['','',''])[:3]
    INFO[n]['inj']=p[12] if len(p)>12 else ''   # CBS's injury note, e.g. "Knee: Game Time Decision"
    if own=='MINE': R[n]=(t,s)
    elif own=='FA': FA[n]=(t,s)
    elif own.startswith('TAKEN:') and sec!='I': OTH.setdefault(own[6:],{})[n]=(t,s)
# Rests on back-to-backs (rest_b2b|): he sits the 2nd night of every back-to-back, so those games come off the schedule
# itself; his CBS games share is then left out (it already allows for some rest, and would count it twice)
def sits(n,t,d): return n in REST and (d-dt.timedelta(days=1)) in G.get(t,())
for n in REST:
    if n in INFO: INFO[n]['gp']=max(INFO[n]['gp'],78.5)
def b2bn(t):   # back-to-back 2nd nights left for team t: (regular season, playoffs)
    ds=[d for d in G.get(t,()) if d>=TODAY and (d-dt.timedelta(days=1)) in G[t]]
    return [sum(1 for d in ds if period(d)<=21),sum(1 for d in ds if period(d)>=22)]
def short(n): return n   # how a player is named on the page: full names
def avail(r,d): return [(n,s) for n,(t,s) in r.items() if d in G[t] and not (n in out and d<out[n]) and not sits(n,t,d)]
BCACHE={}
_COVER=((),('G',),('F',),('C',),('G','F'),('G','C'),('F','C'),('G','F','C'))
def best(pl,cache=True):   # cache=False for actual box-score points: the cache is keyed by names, so they'd mix with projections
    key=tuple(sorted(n for n,_ in pl))
    if cache and key in BCACHE: return BCACHE[key]
    # Exact best lineup without trying every combination: choose distinct players to cover some of G/F/C (each in that
    # slot), then add the 2 best other players at their best slot. An uncovered G/F/C costs a lineup spot, so there are
    # always exactly 2 free spots. Same answer as checking every lineup (verified on 3,000 random rosters), ~6x faster.
    n=len(pl); vals=[s for _,s in pl]; top=[max(s.values()) for s in vals]
    order=sorted(range(n),key=top.__getitem__,reverse=True)   # sorted once; the 2 free spots = first 2 not picked
    bv=0
    for R in _COVER:
        cand=[[i for i in range(n) if r in vals[i]] for r in R]
        for pick in itertools.product(*cand):
            if len(set(pick))<len(pick): continue
            v=sum(vals[i][r] for i,r in zip(pick,R))
            rest=[]
            for i in order:
                if i not in pick:
                    rest.append(top[i])
                    if len(rest)==2: break
            v+=sum(x for x in rest if x>0)   # summed apart, like before: same floats, same tie order
            if v>bv: bv=v
    if cache: BCACHE[key]=bv
    return bv
CACHE={}
def ptot(r,p):
    return sum(best(avail(r,d)) for d in P[p])
full={p:ptot(R,p) for p in PER}
# marginal value of each rostered player
MV={}
for n in R:
    r={k:v for k,v in R.items() if k!=n}
    MV[n]={p:full[p]-ptot(r,p) for p in PER}
tot=lambda d,ps: sum(d[p] for p in ps)
cand=[n for n in R if not (n in out and out[n]>TODAY+dt.timedelta(30))]; CAND0=list(cand)
AUTO=min([n for n in cand if n not in KEEP] or cand,key=lambda n:tot(MV[n],REG)+tot(MV[n],PO))   # the cheapest player
STREAM=FORCE if FORCE in R else AUTO
# IR players come back on their out_until date (no date: now) and each needs a roster spot: the stream slot goes for
# the first, then your next cheapest player (never a keep). RON(d) = your roster on day d, used by the period previews.
_IRB=sorted((max(out.get(n,TODAY),TODAY),n) for n in R if INFO[n]['sec']=='I')
_IRQ=[STREAM]+sorted((n for n in R if n!=STREAM and INFO[n]['sec']!='I' and n not in KEEP),key=lambda n:tot(MV[n],REG)+tot(MV[n],PO))
IRDROP={x:(d0,n) for (d0,n),x in zip(_IRB,_IRQ)}   # player dropped -> (from date, IR player he makes room for)
def RON(d): return {n:v for n,v in R.items() if not (n in IRDROP and d>=IRDROP[n][0])}
def projme(p): return sum(best(avail(RON(d),d)) for d in P.get(p,[]) if d not in SCD)
# ---- Your settings (page header): stream slot, and each player's FP/G, out-until date and keep, saved to settings.txt
# by cc\serve.py (page opened with "6 - Open Command Center"), which then rebuilds the page offline (about 40 s)
_SSCUR=FORCE if FORCE in R else ''
def _ssopt(v,lab): return f'<option value="{html.escape(v)}"{" selected" if v==_SSCUR else ""}>{html.escape(lab)}</option>'
def _ssrow(n):   # one player: CBS FP/G, your FP/G, out until, keep, worth
    i=INFO[n]; o=out.get(n); c=CBSFP.get(n,0)
    return (f'<tr data-n="{html.escape(n)}"><td><b>{html.escape(short(n))}</b> <span class="tm">{i["pos"]} · {i["team"]}</span>'
            +(' <span class="tag bad">IR</span>' if i['sec']=='I' else '')+(' <span class="tag warn">stream</span>' if n==STREAM else '')+'</td>'
            +f'<td class="num">{c:.1f}</td>'
            +f'<td><input type="number" class="ss-fp" step="0.5" min="0" max="120" placeholder="{c:.1f}" value="{f"{proj[n]:g}" if n in proj else ""}" disabled></td>'
            +f'<td><input type="date" class="ss-out" value="{o.isoformat() if o else ""}" disabled></td>'
            +f'<td class="c"><input type="checkbox" class="ss-keep"{" checked" if n in KEEP else ""} disabled></td>'
            +f'<td class="c"><label class="ssrest"><input type="checkbox" class="ss-rest" data-n="{html.escape(n)}"{" checked" if n in REST else ""} disabled> <small>{b2bn(i["team"])[0]} + {b2bn(i["team"])[1]}</small></label></td>'
            +f'<td class="num">{tot(MV[n],REG):.0f} <small>+ {tot(MV[n],PO):.0f}</small></td></tr>')
_SSR=sorted(R,key=lambda n:(INFO[n]['sec']=='I',tot(MV[n],REG)+tot(MV[n],PO)))
_ssn=[sum(1 for n in R if n in proj),sum(1 for n in R if n in out),sum(1 for n in R if n in KEEP),len(REST)]
_B2BT=' <span class="b2bt">🛌</span>'
# ESPN headshots for the stream slot bar: player ids from the box scores (last column), initials if he hasn't played yet
def _ek(n): return ' '.join(re.sub(r'\b(jr|sr|ii|iii|iv)\b','',re.sub(r"[.'’\-]",'',_ud.normalize('NFKD',n).encode('ascii','ignore').decode().lower())).split())
ESPNID={}
for _bf in sorted(glob.glob('box_*.txt')):
    for _l in open(_bf,encoding='utf-8'):
        _f=_l.rstrip('\n').split('|')
        if len(_f)>=18 and _f[-1].strip().isdigit(): ESPNID[_ek(_f[0])]=_f[-1].strip()
CAR=defaultdict(list)   # ESPN id -> past seasons [(season, team, gp, min, fgm, fga, 3pm, 3pa, ftm, fta, reb, ast, stl, blk, to, pf, pts)] (careers.txt)
if os.path.exists('careers.txt'):
    for _l in open('careers.txt',encoding='utf-8'):
        _f=_l.rstrip('\n').split('|')
        if len(_f)==18: CAR[_f[0]].append((_f[1],_f[2],*map(int,_f[3:])))
for _v in CAR.values(): _v.sort()
BIO={}   # ESPN id -> (height, weight, birth date M/D/YYYY, jersey, experience, draft) (bio.txt)
if os.path.exists('bio.txt'):
    for _l in open('bio.txt',encoding='utf-8'):
        _f=_l.rstrip('\n').split('|')
        if len(_f)==7: BIO[_f[0]]=tuple(_f[1:])
def bioline(n):   # [jersey, height, weight, age, experience, draft] for the player card
    b=BIO.get(ESPNID.get(_ek(n)))
    if not b: return None
    ht,wt,dob,jer,exp,dr=b; age=''
    try:
        m_,d_,y_=map(int,dob.split('/')); age=TODAY.year-y_-((TODAY.month,TODAY.day)<(m_,d_))
    except ValueError: pass
    return [jer,ht,wt,age,exp,dr]
def _ssface(n,big=False):
    i=ESPNID.get(_ek(n)); ini=''.join(w[0] for w in n.split()[:2]).upper()
    img=(f'<img src="https://a.espncdn.com/i/headshots/nba/players/full/{i}.png" alt="" loading="lazy" onerror="this.remove()">' if i else '')
    return f'<span class="ss-face{" big" if big else ""}" aria-hidden="true"><span>{ini}</span>{img}</span>'
_SSC=sorted((n for n in cand if INFO[n]['sec']!='I'),key=lambda n:tot(MV[n],REG)+tot(MV[n],PO))   # who can be the stream slot, cheapest first
_SSMX=max([tot(MV[n],REG)+tot(MV[n],PO) for n in _SSC] or [1]) or 1
def _ssbar(n,me=False): return f'<div class="bar{" me" if me else ""}"><i style="width:{max(2,round((tot(MV[n],REG)+tot(MV[n],PO))/_SSMX*100))}%"></i></div>'
def _sstag(n): return f'<span class="nbat" data-t="{INFO[n]["team"]}">{INFO[n]["team"]}</span> <span class="tm">{INFO[n]["pos"]}</span>'
def _ssalt(n):   # one "next cheapest" row: name, worth bar, worth, Use
    return (f'<div class="ssalt" data-n="{html.escape(n)}"><span class="ssan">{_ssface(n)}<b>{html.escape(short(n))}</b> {_sstag(n)}{_B2BT if n in REST else ""}</span>'
            f'{_ssbar(n)}<span class="num">{tot(MV[n],REG):.0f} <small>+ {tot(MV[n],PO):.0f}</small></span>'
            f'<button type="button" class="ssuse" data-n="{html.escape(n)}" disabled>Use</button></div>')
def _pkrow(n):   # one player in the stream slot picker: headshot, name, team, tags, worth bar, worth (reg. season, playoffs)
    return (f'{_ssface(n)}<span class="pk-who"><b>{html.escape(short(n))}</b><span class="pk-tags">{_sstag(n)}'
            +(' <span class="b2bt">🛌 B2B</span>' if n in REST else '')+(' <span class="pk-keep" title="Keep: never suggested as a drop">🔒</span>' if n in KEEP else '')+'</span></span>'
            +f'{_ssbar(n)}<span class="pk-n">{tot(MV[n],REG):.0f}</span><span class="pk-n pk-po">{tot(MV[n],PO):.0f}</span>')
_PKAUTO=f'<span class="ss-face"><span>A</span></span><span class="pk-who"><b>Automatic</b><small>your cheapest player each night · now {html.escape(short(AUTO))}</small></span>'
_pkbtn=(_pkrow(STREAM) if _SSCUR else _PKAUTO)+'<span class="pk-car" aria-hidden="true">▾</span>'   # the picker's closed state
def _pkopt(v,inner): return (f'<div class="pk-opt{" auto" if not v else ""}" role="option" tabindex="-1" data-v="{html.escape(v)}" aria-selected="{"true" if v==_SSCUR else "false"}">'
                             f'{inner}{"<span class=pk-cur>current</span>" if v==_SSCUR else ""}</div>')
_SSCH=[('🩹',_ssn[1],'out until'),('🔒',_ssn[2],'keep'),('🛌',_ssn[3],'rest B2Bs'),('✏️',_ssn[0],'custom FP/G')]
streamsel=(f'<script>window.__bblrest=new Set({json.dumps(sorted(REST))});</script>'   # also set from the Watchlist (🛌 B2B)
    +'<div class="streamsel"><div class="ss-hero"><div class="ss-cur">'
    +_ssface(STREAM,True)
    +f'<div class="ss-who"><div class="ss-k">Stream slot{" · automatic" if not _SSCUR else ""}</div>'
    +f'<div class="ss-name">{html.escape(short(STREAM))} {_sstag(STREAM)}{_B2BT[:-7]+" rests B2Bs</span>" if STREAM in REST else ""}</div>'
    +f'<div class="ss-sub">Every pickup on this page is measured as “add him, drop {html.escape(short(STREAM))}”.</div></div>'
    +f'<div class="ss-worth"><div><span class="lbl">Worth · reg. season</span><span class="num2">{tot(MV[STREAM],REG):.0f}</span></div>'
    +f'<div><span class="lbl">Playoffs</span><span class="num2">{tot(MV[STREAM],PO):.0f}</span></div></div>'
    +f'<div class="ss-mebar">{_ssbar(STREAM,True)}</div></div>'
    +'<div class="ss-alts"><div class="ss-k">Next cheapest · switch with one click</div>'
    +(''.join(_ssalt(n) for n in [x for x in _SSC if x!=STREAM][:3]) or '<div class="ss-sub">No other players to switch to.</div>')+'</div></div>'
    +'<div class="ss-row2"><span class="t" id="sspicklab">Or pick anyone</span>'
    # the real choice is this hidden select (what Apply saves); the picker below shows it with headshots and team tags
    +'<select id="streamsel" hidden disabled aria-hidden="true" tabindex="-1">'
    +_ssopt('',f'Automatic · your cheapest player ({short(AUTO)})')
    +''.join(_ssopt(n,short(n)) for n in _SSC)+'</select>'
    +'<div class="sspick"><button type="button" id="sspickbtn" aria-haspopup="listbox" aria-expanded="false" aria-labelledby="sspicklab" disabled title="Open the page with “6 - Open Command Center” to change it">'+_pkbtn+'</button>'
    +'<div class="sspop" role="listbox" aria-labelledby="sspicklab" hidden>'
    +_pkopt('',_PKAUTO)
    +'<div class="pk-head"><span>Your roster · cheapest first</span><span>Reg. season</span><span>Playoffs</span></div>'
    +''.join(_pkopt(n,_pkrow(n)) for n in _SSC)+'</div></div>'
    +'<button type="button" id="ssapply" class="ssbtn on" hidden>Apply &amp; rebuild</button>'
    +'<span id="streammsg" class="small"></span></div>'
    +'<details id="ssmore"><summary><span class="t">⚙️ Roster settings</span>'
    +''.join(f'<span class="chip2{" zero" if not c else ""}">{i} <b>{c}</b> {l}</span>' for i,c,l in _SSCH)+'<span class="ssedit">Edit ▸</span></summary>'
    +'<p class="small" style="margin:8px 0">Change any of these, then <b>Apply &amp; rebuild</b> (about a minute; nothing goes online). '
    +'<b>Your FP/G</b> replaces CBS&#39;s projection for that player everywhere on the page (his points in his best slot; leave it blank to use CBS). '
    +'<b>Out until</b>: he isn&#39;t counted in your lineups before that date (injuries, IR return). '
    +'<b>Keep</b>: never suggested as a drop or as the automatic stream slot. '
    +'<b>Rests B2Bs</b> (load management): he sits the 2nd night of every back-to-back, so those games come off his schedule everywhere '
    +'(the numbers = back-to-backs left for his team, regular season + playoffs); mark free agents and other teams&#39; players with <b>🛌 B2B</b> on the Watchlist. '
    +'<b>Worth</b> = points your lineups lose without him, rest of regular season + playoffs.</p>'
    +'<div class="scroll"><table class="sstab"><thead><tr><th>Player</th><th>CBS FP/G</th><th>Your FP/G</th><th>Out until</th><th>Keep</th><th>Rests B2Bs</th><th>Worth</th></tr></thead><tbody>'
    +''.join(_ssrow(n) for n in _SSR)+'</tbody></table></div></details>'
    +'<div id="ssbar" hidden><span></span><button type="button" class="ssbtn on">Apply &amp; rebuild</button></div>'
    +'<div id="ssprog" hidden role="status" aria-live="polite"><div class="pg-top"><b>Rebuilding your page</b><span class="pg-pct">0%</span></div>'
    +'<div class="pg-bar"><i></i></div><div class="pg-foot"><span class="pg-step">Starting</span><span class="pg-time"></span></div></div></div>')
streamjs=r'''<script>(function(){var s=document.getElementById("streamsel"),m=document.getElementById("streammsg"),btn=document.getElementById("ssapply"),box=document.querySelector(".streamsel"),t=document.querySelector('meta[name="bbl-team"]');
if(!s||!t||!/^https?:$/.test(location.protocol))return;var T=t.content,M0=m.innerHTML;
function rows(){return [].slice.call(box.querySelectorAll(".sstab tbody tr"))}
var RS=window.__bblrest,bar=document.getElementById("ssbar");   // RS: players who rest on back-to-backs (Watchlist 🛌 B2B too)
function state(){var o={stream:s.value,proj:{},out:{},keep:[],rest:Array.from(RS).sort()};rows().forEach(function(r){var n=r.dataset.n,f=r.querySelector(".ss-fp").value.trim(),d=r.querySelector(".ss-out").value;o.proj[n]=f===""?null:+f;o.out[n]=d||null;if(r.querySelector(".ss-keep").checked)o.keep.push(n)});return o}
var S0=JSON.stringify(state());
function last(n){return n.split(" ").filter(function(w){return !/^(Jr\.|Sr\.|II|III|IV)$/.test(w)}).slice(-1)[0]}
function diff(){var a=JSON.parse(S0),b=state(),c=[];if(a.stream!==b.stream)c.push("stream slot");Object.keys(b.proj).forEach(function(n){if(a.proj[n]!==b.proj[n])c.push(last(n)+" FP/G");if(a.out[n]!==b.out[n])c.push(last(n)+" out until");if((a.keep.indexOf(n)>=0)!==(b.keep.indexOf(n)>=0))c.push(last(n)+" keep")});
a.rest.concat(b.rest).forEach(function(n,i,all){if(all.indexOf(n)===i&&(a.rest.indexOf(n)>=0)!==(b.rest.indexOf(n)>=0))c.push(last(n)+(b.rest.indexOf(n)>=0?" rests B2Bs":" plays B2Bs"))});return c}
function bad(){return rows().filter(function(r){var v=r.querySelector(".ss-fp").value.trim();return v!==""&&!(+v>=0&&+v<=120)}).length}
function upd(){var c=diff(),b=bad();label();btn.disabled=!c.length||!!b;btn.hidden=!c.length||!!b;[].forEach.call(box.querySelectorAll(".ssalt"),function(r){r.classList.toggle("sel",r.dataset.n===s.value)});btn.classList.toggle("on",!!c.length&&!b);
m.innerHTML=b?"<b>⚠️ FP/G must be a number from 0 to 120.</b>":(c.length?"<b>"+c.length+" change"+(c.length>1?"s":"")+" not applied yet:</b> "+c.join(", ").replace(/</g,"&lt;"):M0);
bar.hidden=!c.length||!!b;bar.firstChild.textContent=c.length+" change"+(c.length>1?"s":"")+" not applied: "+c.join(", ")}
function syncrest(){[].forEach.call(box.querySelectorAll(".ss-rest"),function(e){e.checked=RS.has(e.dataset.n)})}
// the stream slot picker: a listbox over the hidden select (#streamsel), with headshots and team tags
var pb=document.getElementById("sspickbtn"),pp=box.querySelector(".sspop");
function popts(){return [].slice.call(pp.querySelectorAll(".pk-opt"))}
function label(){var o=popts().filter(function(x){return x.dataset.v===s.value})[0];popts().forEach(function(x){x.setAttribute("aria-selected",String(x.dataset.v===s.value))});if(o){var c=o.cloneNode(true),k=c.querySelector(".pk-cur");if(k)k.remove();pb.innerHTML=c.innerHTML+'<span class="pk-car" aria-hidden="true">▾</span>'}}
function openP(o){pp.hidden=!o;pb.setAttribute("aria-expanded",String(o));if(o){(pp.querySelector('[aria-selected="true"]')||popts()[0]).focus()}}
function pick(o){s.value=o.dataset.v;openP(false);pb.focus();upd()}
pb.addEventListener("click",function(){openP(pp.hidden)});
pp.addEventListener("click",function(e){var o=e.target.closest(".pk-opt");if(o)pick(o)});
pp.addEventListener("keydown",function(e){var l=popts(),k=l.indexOf(document.activeElement);if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();l[Math.max(0,Math.min(l.length-1,k+(e.key==="ArrowDown"?1:-1)))].focus()}else if(e.key==="Enter"||e.key===" "){e.preventDefault();if(k>=0)pick(l[k])}else if(e.key==="Escape"){openP(false);pb.focus()}else if(e.key==="Tab")openP(false)});
document.addEventListener("click",function(e){if(!pp.hidden&&!e.target.closest(".sspick"))openP(false)});
// the rebuild runs on your PC in the background: follow its progress, then reload
var pg=document.getElementById("ssprog");
function showP(j){pg.hidden=false;var p=Math.max(1,Math.min(100,j.pct||0));pg.querySelector(".pg-bar i").style.width=p+"%";pg.querySelector(".pg-pct").textContent=p+"%";pg.querySelector(".pg-step").textContent=(j.step||"Working")+(p<100?"…":"");var left=p>3&&p<100?Math.max(1,Math.round(j.elapsed*(100-p)/p)):null;pg.querySelector(".pg-time").textContent=j.elapsed+" s"+(left!=null?" · about "+left+" s left":"")}
function follow(){return new Promise(function(ok,no){(function tick(){fetch("/api/rebuild",{cache:"no-store"}).then(function(r){if(r.status===404)return {state:"done",elapsed:0};return r.json()}).then(function(j){showP(j);if(j.state==="done"){showP({pct:100,step:"Done · reloading",elapsed:j.elapsed});setTimeout(ok,400)}else if(j.state==="failed")no(new Error(j.error||"the rebuild failed"));else setTimeout(tick,600)}).catch(function(){setTimeout(tick,1500)})})()})}
fetch("/api/settings?team="+encodeURIComponent(T),{cache:"no-store"}).then(function(r){return r.ok?r.json():null}).then(function(j){if(!j||!j.editable)return;
[].forEach.call(box.querySelectorAll("select,input,.ssuse,#sspickbtn"),function(e){e.disabled=false});s.title="Who pickups replace";box.addEventListener("input",upd);box.addEventListener("change",function(e){
if(e.target.classList.contains("ss-rest")){if(e.target.checked)RS.add(e.target.dataset.n);else RS.delete(e.target.dataset.n);document.dispatchEvent(new Event("bbl-rest"))}upd()});
document.addEventListener("bbl-rest",function(){syncrest();upd()});box.addEventListener("click",function(e){var u=e.target.closest(".ssuse");if(!u||u.disabled)return;s.value=u.dataset.n===s.value?JSON.parse(S0).stream:u.dataset.n;upd()});bar.lastChild.addEventListener("click",function(){btn.click()});
window.__bblsetok=true;document.dispatchEvent(new Event("bbl-rest"));fetch("/api/rebuild",{cache:"no-store"}).then(function(r){return r.json()}).then(function(j){if(j.state==="running"){document.body.classList.add("rebuilding");follow().then(function(){location.reload()},function(e){pg.hidden=true;document.body.classList.remove("rebuilding");m.innerHTML="<b>⚠️ Couldn’t apply:</b> "+String(e.message||e).replace(/</g,"&lt;")})}}).catch(function(){})}).catch(function(){});
btn.addEventListener("click",async function(){var st=state();btn.disabled=true;bar.hidden=true;window.__bblsetok=false;document.dispatchEvent(new Event("bbl-rest"));[].forEach.call(box.querySelectorAll("select,input,.ssuse,#sspickbtn"),function(e){e.disabled=true});document.body.classList.add("rebuilding");
m.innerHTML="<b>⏳ Rebuilding your page with your settings…</b> about a minute; it reloads by itself.";
try{var r=await fetch("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.assign({team:T},st))}),j=await r.json().catch(function(){return {}});
if(!r.ok)throw new Error(j.error||("HTTP "+r.status));await follow();location.reload()}
catch(e){pg.hidden=true;[].forEach.call(box.querySelectorAll("select,input,.ssuse,#sspickbtn"),function(x){x.disabled=false});window.__bblsetok=true;document.dispatchEvent(new Event("bbl-rest"));document.body.classList.remove("rebuilding");upd();m.innerHTML="<b>⚠️ Couldn’t apply:</b> "+String(e.message||e).replace(/</g,"&lt;")}})})();</script>'''
base={k:v for k,v in R.items() if k!=STREAM}
bpt={p:ptot(base,p) for p in PER}
mit={p:full[p]-bpt[p] for p in PER}
def gains(name,t,s): r=dict(base); r[name]=(t,s); return {p:ptot(r,p)-bpt[p]-mit[p] for p in PER}
GA={}
for n,(t,s) in FA.items():  # scale by projected games share so injured players aren't overrated
    f=min(1.0,INFO[n]['gp']/78.5); GA[n]={p:v*f for p,v in gains(n,t,s).items()}
# watched players on other teams: the same gain, as if you got him for your stream slot (a trade target).
# Kept apart from GA, which is free agents only
WT=[n for n in watch if n in INFO and n not in FA and n not in R and SV[n][1]]
GT={n:{p:v*min(1.0,INFO[n]['gp']/78.5) for p,v in gains(n,*SV[n]).items()} for n in WT}
healthy=lambda n: INFO[n]['gp']>=60
_prog(8,'Projecting every period',9,0.3)
# ---- rows
def _opps():
    """This team's opponent each period from matchups.txt (first team listed is the away team): '@X' = away at X."""
    o={}
    if os.path.exists('matchups.txt'):
        for l in open('matchups.txt',encoding='utf-8'):
            f=l.strip().split('|')
            if len(f)>=3 and f[0].isdigit():
                if f[1]==MEKEY: o[int(f[0])]='@'+f[2]
                elif f[2]==MEKEY: o[int(f[0])]=f[1]
    return [o.get(p,'TBD') for p in range(1,22)]
OPP=_opps()
def opp(p): return OPP[p-1] if p<=21 else {22:'Playoffs · Quarterfinal',23:'Playoffs · Semifinal',24:'Championship · 5 days, Apr 3 cut'}[p]
# ---- Points already scored this period (actual box scores). Win odds = points so far + projection for the days left.
# Kept in usg.txt as lines S|date|fantasy team|points (one per team per night: each team's best daily lineup with every
# player's actual best-slot score, the same rule as the projections). Every box_YYYYMMDD.txt in the folder is added once.
MEN=globals().get('ME','Oobsidoobsie')
SCORES={}
if os.path.exists('usg.txt'):
    for l in open('usg.txt',encoding='utf-8'):
        q=l.rstrip('\n').split('|')
        if len(q)==4 and q[0]=='S':
            try: SCORES[(q[1],q[2])]=float(q[3])
            except ValueError: pass
_sd={k[0] for k in SCORES}; _newsc=[]
def _nk(n):   # name key: ESPN and CBS spell some names differently (accents, Jr., P.J./PJ)
    n=_ud.normalize('NFKD',n).encode('ascii','ignore').decode().lower()
    return ' '.join(re.sub(r'\b(jr|sr|ii|iii|iv)\b','',re.sub(r"[.'’\-]",'',n)).split())
def _who(n,own):   # (fantasy team, CBS name) for an ESPN box name; Ron Holland / Ronald Holland II: same initial and last name
    k=_nk(n)
    if k in own: return own[k]
    m=[x for x in own if x[:1]==k[:1] and k.split()[-1:] and k.split()[-1] in x.split()]
    return own[m[0]] if len(m)==1 else None
_NST={}   # date -> {name key: (fantasy team, CBS name)}: every team's roster each night, from pool.txt's #STATUS lines
_NSA={}   # date -> set of name keys in an ACTIVE lineup spot that night
for l in open('pool.txt',encoding='utf-8'):
    q=l.rstrip('\n').split('|')
    if q[0]=='#STATUS' and len(q)>=5:
        _NST.setdefault(q[1],{})[_nk(q[3])]=(MEN if q[2]==MEN else q[2],q[3])
        if q[4]=='ACTIVE': _NSA.setdefault(q[1],set()).add(_nk(q[3]))
BENCH={}   # (date, team) -> (best possible, active lineup, [(benched player, his points)]): finished nights with saved lineups
for _bf in sorted(glob.glob('box_*.txt')):
    _d=os.path.basename(_bf)[4:12]
    if not _d.isdigit() or (_d in _sd and _d not in _NST): continue
    _ln=open(_bf,encoding='utf-8').read().strip().splitlines()
    try: _all,_fin=[int(x) for x in _ln[0].lstrip('#').split('|')[:2]]
    except (IndexError,ValueError): _all=_fin=0
    if not _fin: continue
    _own={}
    if _d in _NST: _own=_NST[_d]   # that night's rosters (saved from CBS each night), not today's
    else:
        for n_,i_ in INFO.items():
            o_=i_['own']
            if o_=='MINE': _own[_nk(n_)]=(MEN,n_)
            elif o_.startswith('TAKEN:'): _own[_nk(n_)]=(o_[6:],n_)
    _tp=defaultdict(list)
    for l in _ln[1:]:
        q=l.split('|')
        _w=_who(q[0],_own) if len(q)>=16 else None
        if not _w: continue
        _t,q[0]=_w
        try: mi,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,to,stl,blk,pf=[float(x or 0) for x in q[2:16]]
        except ValueError: continue
        fp=pts+2*fgm-fga+ftm-fta+reb+2*ast+4*stl+4*blk-2*to-pf
        sl={k:fp+{'G':reb,'F':ast,'C':tpm}[k] for k in INFO.get(q[0],{'pos':''})['pos'].split(',') if k in ('G','F','C')} or {'F':fp}
        _tp[_t].append((q[0],sl))
    for t_,pl_ in _tp.items():
        if _fin>=_all and _d in _NST:   # points left on the bench: the active players' best lineup vs everyone's
            _ac=[x for x in pl_ if _nk(x[0]) in _NSA.get(_d,())]
            _bn=sorted(((n_,max(s_.values())) for n_,s_ in pl_ if _nk(n_) not in _NSA.get(_d,())),key=lambda x:-x[1])
            BENCH[(_d,t_)]=(best(pl_,False),best(_ac,False),_bn)
        if (_d,t_) in SCORES: continue   # saved already (a missing team-night is filled in)
        SCORES[(_d,t_)]=best(pl_,False)
        if _fin>=_all: _newsc.append((_d,t_,SCORES[(_d,t_)]))   # saved once every game is final; until then worked out each run
if _newsc:
    with open('usg.txt','a',encoding='utf-8') as _fh:
        for r in _newsc: _fh.write(f'S|{r[0]}|{r[1]}|{r[2]:g}\n')
SCD={dt.datetime.strptime(k[0],'%Y%m%d').date() for k in SCORES}   # nights with actual scores
def done(team,p): return sum(v for (d,t),v in SCORES.items() if t==team and period(dt.datetime.strptime(d,'%Y%m%d').date())==p)
def projleft(r,p): return sum(best(avail(r,d)) for d in P.get(p,[]) if d not in SCD)
def wlbox(it):   # a period's watchlist gains [(short name, "pos · team", gain)], best first: one line, tap to see all
    if not it: return '<div class="wl"><span class="wlh">Watchlist</span><div class="muted">No gain this period</div></div>'
    return (f'<details class="wl"><summary><span class="wlh">★ Watchlist · {len(it)}</span> best: {html.escape(it[0][0])} <b>+{it[0][2]}</b></summary>'
            +''.join(f'<div>{html.escape(s)} <span class="tm">{html.escape(pt)}</span> <b>+{g}</b></div>' for s,pt,g in it)+'</details>')
rows=[]; MU=[]; THIN={}
for p in PER:
    ds=P[p]; thin=[]; filled=0
    for d in ds:
        k=len(avail(RON(d),d)); filled+=min(k,5)
        if k<5: thin.append((d,k))
    THIN[p]=[d for d,_ in thin]
    sev='ok' if not thin else ('bad' if any(k<=2 for _,k in thin) or filled<0.85*5*len(ds) else 'warn')
    chips=' '.join(f'<span class="chip c{min(k,4)}">{d.strftime("%a %b %-d")} · {k}</span>' for d,k in thin) or '<span class="muted">None</span>'
    if p in (7,8): chips+=' <span class="note">NBA Cup knockout games still TBD; league will adjust. Cup final does not count.</span>'
    if p in (18,19): chips+=' <span class="note">All-Star break Feb 19–24</span>'
    if p==CUR and TODAY>pstart(p): chips+=f' <span class="note">Counting from today ({TODAY.strftime("%b %-d")})</span>'
    top=sorted([(GA[n][p],n) for n in FA if healthy(n)],reverse=True)[:3]
    fas='<br>'.join(f'{html.escape(short(n))} <span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span> <b>+{g:.0f}</b>' for g,n in top if g>=5) or '<span class="muted">No add beats your stream slot</span>'
    wl=sorted([(GA[n][p],n) for n in watch if n in GA and GA[n][p]>=1],reverse=True)
    fas+=wlbox([(short(n),f'{INFO[n]["pos"]} · {INFO[n]["team"]}',f'{g:.0f}') for g,n in wl])
    fas=f'<div class="ladd" data-p="{p}">'+fas+'</div>'
    thd=[d for d,_ in thin]; tg=[]
    for t in G:
        cov=[d for d in thd if d in G[t]]
        if cov: tg.append((len(cov),sum(1 for d in ds if d in G[t]),t,' · '.join(d.strftime('%a %-m/%-d') for d in cov)))
    tg.sort(key=lambda x:(-x[0],-x[1],x[2]))
    teams=' '.join(f'<span class="tchip">{t} <b>{f}</b><small>/{g}</small><span class="cov">{c}</span></span>' for f,g,t,c in [x for x in tg if x[0]==tg[0][0]][:8]) if tg else '<span class="muted">No empty slots</span>'
    dr=f'{pstart(p).strftime("%b %-d")} – {pend(p).strftime("%b %-d")}'
    oslot=''
    if p<=21:
        on=OPP[p-1].lstrip('@'); key=next((k for k in OTH if k==on or (on=='TINOLA' and 'ɪɴᴏʟᴀ' in k)),None)
        if key:
            of=sum(min(len(avail(OTH[key],d)),5) for d in ds)
            cls='better' if filled>of else ('worse' if filled<of else 'even')
            oslot=f'<div class="oslot {cls}">Opp slots {of}/{5*len(ds)} · you {filled-of:+d} vs them</div>'
            sm=done(MEN,p); so=done(key,p)
            mine_p=projme(p)+sm; opp_p=projleft(OTH[key],p)+so
            sdd=0.11*math.sqrt(mine_p**2+opp_p**2) or 1
            wp=0.5*(1+math.erf((mine_p-opp_p)/(sdd*math.sqrt(2))))
            cand=sorted([(GA[n][p],n) for n in FA if healthy(n)],reverse=True)
            tip=''
            if cand and cand[0][0]>=5:
                g,n=cand[0]; wp2=0.5*(1+math.erf((mine_p+g-opp_p)/(sdd*math.sqrt(2))))
                tip=f' Adding {short(n)} (+{g:.0f}) moves you to {wp2*100:.0f}%.'
            lab='Favored' if wp>=0.6 else ('Underdog' if wp<=0.4 else 'Toss-up')
            why=('Your schedule edge carries it.' if filled-of>=2 and mine_p>=opp_p else
                 'Their schedule edge is the gap.' if of-filled>=2 and opp_p>mine_p else
                 'Your top-end talent carries it.' if mine_p>opp_p else 'Their roster projects higher.')
            wcls='better' if wp>=0.6 else ('worse' if wp<=0.4 else 'even')
            MU.append(dict(p=p,key=key,sm=sm,so=so,opp=OPP[p-1].lstrip('@'),home=not OPP[p-1].startswith('@'),wp=wp,mine=mine_p,opp_p=opp_p,slot=filled-of,add=(short(cand[0][1]),cand[0][0],wp2) if tip else None))
            oslot+=f'<div class="winp {wcls}"><b>{wp*100:.0f}%</b> win · {lab}</div><div class="wsum">Proj {mine_p:,.0f}–{opp_p:,.0f} ({mine_p-opp_p:+,.0f}){f" incl. {sm:,.0f}–{so:,.0f} already scored" if (sm or so) else ""}. {why}{tip}</div>'
    rows.append(f'<tr class="{sev}{" po" if p>=22 else ""}{" cur" if p==CUR else ""}"{" id=\"curp\"" if p==CUR else ""}><td class="pn">{p}{"<span class=\"nowtag\">NOW</span>" if p==CUR else ""}</td><td>{dr}<div class="opp">{html.escape(opp(p))}</div>{oslot}</td><td class="minicell">@@MINI{p}@@</td><td class="num">{filled}/{5*len(ds)}</td><td>{chips}</td><td>{fas}</td><td class="teams">{teams}</td></tr>')
# ---- roster value table
order=sorted(R,key=lambda n:-tot(MV[n],REG))
mx=max(1,max(tot(MV[n],REG) for n in R))
def sellflag(n):
    e=es(n); c=RT.get(n)
    if (e and e[1]<=-1.5) or (c and c[2]<=-5):
        why=(f'ESPN {e[0]:.0f}% rostered ({e[1]:+.1f} this wk)' if e else '')+(' · ' if e and c else '')+(f'CBS {c[0]}% → {c[1]}%' if c else '')
        return f' <span class="tag bad" title="Managers are dropping him: {why}">📉 market selling</span>'
    if (e and e[1]>=2) or (c and c[2]>=10):
        why=(f'ESPN {e[1]:+.1f} this wk' if e else '')+(' · ' if e and c else '')+(f'CBS {c[0]}% → {c[1]}%' if c else '')
        return f' <span class="tag ok" title="{why}">📈 sell-high window</span>'
    return ''
def mkt(n):
    e=es(n)
    return f'<div class="small muted" title="ESPN: rostered / started across all leagues">{ES_}{_p(e[0])}% rostered · {_p(e[2])}% started</div>' if e else ''
pv='\n'.join(f'<tr><td>{html.escape(short(n))}{sellflag(n)}{dsp(n)}{mkt(n)}{" <span class=tm>stream</span>" if n==STREAM else ""}{" <span class=tm>IR</span>" if n in out and out[n]>TODAY else ""}</td><td class="bar"><span style="width:{max(0,tot(MV[n],REG))/mx*100:.1f}%"></span><em>{tot(MV[n],REG):.0f}</em></td><td class="num">{tot(MV[n],PO):.0f}</td></tr>' for n in order)
# ---- waiver wire
wire=sorted(FA,key=lambda n:-(tot(GA[n],REG)+tot(GA[n],PO)))[:15]
def bestp(n):
    ps=sorted(PER,key=lambda p:-GA[n][p])[:2]
    return ', '.join(f'P{p}' for p in ps if GA[n][p]>=5) or '—'
wr='\n'.join(f'<tr><td>{html.escape(short(n))}{" <span class=flag>★ watch</span>" if n in watch else ""}{" <span class=flag>injury · "+str(round(INFO[n]["gp"]))+" GP proj</span>" if not healthy(n) else ""}</td><td><span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span></td><td class="num">{INFO[n]["best"]:.1f}</td><td class="num">{tot(GA[n],REG):+.0f}</td><td class="num">{tot(GA[n],PO):+.0f}</td><td class="num">{bestp(n)}</td></tr>' for n in wire)
taken=[n for n in watch if INFO.get(n,{}).get('own','').startswith('TAKEN')]
missing=[n for n in watch if n not in INFO]
tk=''
if taken: tk+='<p class="small"><b>Taken from your watchlist:</b> '+', '.join(f'{html.escape(short(n))} ({html.escape(INFO[n]["own"][6:])})' for n in taken)+'</p>'
if missing: tk+='<p class="small">Not found on CBS: '+', '.join(html.escape(n) for n in missing)+'</p>'
# ---- key cards
sm=sum(1 for p in PER if mit[p]>0)
danger=sorted(PER,key=lambda p:(sum(max(0,5-len(avail(RON(d),d))) for d in P[p])),reverse=True)[:3]
CHEAP=sorted([n for n in R if INFO[n].get('sec')!='I' and not (n in out and out[n]>TODAY)],key=lambda n:tot(MV[n],REG)+tot(MV[n],PO))[:3]
def cheap_txt(k=3): return ', '.join(f'{html.escape(short(n))} ({tot(MV[n],REG):.0f})' for n in CHEAP[:k])
def dtxt(p):
    g,n=max((GA[n][p],n) for n in FA if healthy(n))
    return f'P{p} ({pstart(p).strftime("%b %-d")}): '+(f'{short(n)} +{g:.0f}' if g>=5 else 'no add beats your stream slot')
hold=sorted([n for n in FA if healthy(n)],key=lambda n:-(tot(GA[n],REG)+tot(GA[n],PO)))[:2]
h1,h2=hold
outs=[n for n in out if out[n]>TODAY and n in R]
if outs:
    o=outs[0]
    if FORCE==STREAM:
        k4=f'<div class="key"><b>When {html.escape(short(o))} comes back, someone has to go</b><p>{html.escape(short(o))} is out until about {out[o].strftime("%b %-d")}. Activating him from IR needs an open roster spot. Cheapest options today: {cheap_txt(2)}.'+(f' {", ".join(html.escape(short(k)) for k in R if k in KEEP)} stays.' if KEEP else '')+'</p></div>'
    else:
        rest=[n for n in R if n not in (o,STREAM) and n not in KEEP]
        dropn=min(rest,key=lambda n:tot(MV[n],REG)+tot(MV[n],PO))
        k4=f'<div class="key"><b>When {html.escape(short(o))} comes back, drop {html.escape(short(dropn))}</b><p>{html.escape(short(o))} is out until about {out[o].strftime("%b %-d")}. {html.escape(short(dropn))} is your lowest-value player apart from {html.escape(short(STREAM))}.</p></div>'
else:
    rest=[n for n in R if n!=STREAM and n not in KEEP]; dropn=min(rest,key=lambda n:tot(MV[n],REG)+tot(MV[n],PO))
    k4=f'<div class="key"><b>Next weakest spot: {html.escape(short(dropn))}</b><p>After {html.escape(short(STREAM))}, {html.escape(short(dropn))} adds the least to your lineups for the rest of the season.</p></div>'
keys=f'''<div class="key"><b>Your cheapest drops</b><p>{'<br>'.join(f'{html.escape(short(n))} <span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span> · worth {tot(MV[n],REG):.0f} + {tot(MV[n],PO):.0f} playoffs'+(' <span class="tm">stream slot</span>' if n==STREAM else '') for n in CHEAP)}<br><span class="small">Points your lineups lose without him, rest of season + playoffs. Pick who a pickup replaces with “If I drop” below.</span></p></div>
<div class="key"><b>Danger weeks</b><p>{'<br>'.join(html.escape(dtxt(p)) for p in danger)}</p></div>
<div class="key"><b>Best single hold: {html.escape(short(h1))}</b><p>Claimed for your stream slot ({html.escape(short(STREAM))}) and kept, he adds {tot(GA[h1],REG):+.0f} in the regular season and {tot(GA[h1],PO):+.0f} in the playoffs. Next best: {html.escape(short(h2))} ({tot(GA[h2],REG):+.0f} / {tot(GA[h2],PO):+.0f}).</p></div>
{k4}'''
def wbtn(n,force=False):  # quick add-to-watchlist button for free agents (state synced by WLJS)
    return f' <button type="button" class="wq" data-n="{html.escape(n)}" aria-label="Add {html.escape(short(n))} to watchlist">+ Watch</button>' if (n in FA or force) else ''
_prog(9,'Checking rival rosters',28,6.5)
# ---- rival waiver targets (current + next period)
RP=[p for p in PER[:2]]
mine_top=set(n for n in sorted([n for n in FA if healthy(n)],key=lambda n:-sum(GA[n][p] for p in RP))[:5])
rival=[]; cnt=defaultdict(list); rivseason=[]; DEM=defaultdict(dict); DEMP=defaultdict(dict); RB={}; FO={}
SEASONFA=sorted([n for n in FA if healthy(n)],key=lambda n:-INFO[n]['best'])[:45]
mine_season=sorted([n for n in FA if healthy(n)],key=lambda n:-(tot(GA[n],REG)+tot(GA[n],PO)))[:5]
for tn,roster in sorted(OTH.items(),key=lambda x:x[0].lower()):
    tp=lambda r: sum(ptot(r,p) for p in RP)
    b=tp(roster)
    # rest-of-season value of each player to this roster (what a manager weighs before dropping)
    full_o={p:ptot(roster,p) for p in PER}
    mv={n:sum(full_o[p]-ptot({k:v for k,v in roster.items() if k!=n},p) for p in PER) for n in roster}
    drops=sorted(roster,key=lambda n:(mv[n],INFO[n]['best']))[:3]
    drop=drops[0]; rb={k:v for k,v in roster.items() if k!=drop}
    empty=[(sum(min(5,len(avail(roster,d))) for d in P[p]),5*len(P[p])) for p in RP]
    g=[]
    for n,(t,s2) in FA.items():
        if not healthy(n): continue
        r2=dict(rb); r2[n]=(t,s2); g.append((tp(r2)-b,n))
    g.sort(reverse=True); top=[x for x in g[:5] if x[0]>0]
    for v,n in top: cnt[n].append(tn)
    rival.append((tn,[(d,mv[d]) for d in drops],empty,top))
    # rest-of-season value of the best free agents to this rival (same drop)
    sg=[]
    for n in SEASONFA:
        r2=dict(rb); r2[n]=FA[n]
        pg={p:ptot(r2,p)-full_o[p] for p in PER}; DEMP[n][tn]=pg
        sg.append((sum(pg[p] for p in REG),sum(pg[p] for p in PO),n))
    RB[tn]=rb; FO[tn]=full_o
    for rg,po_,n in sg: DEM[n][tn]=(rg,po_)
    sg.sort(key=lambda x:-x[0])
    rivseason.append((tn,drop,[x for x in sg[:3] if x[0]>0]))
def rl(tn,drops,empty,top):
    one=lambda n,v: f'{html.escape(short(n))} <span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span>{wbtn(n)} <b>+{v:.0f}</b>'+(' <span class="flag">⚔</span>' if n in mine_top else '')+(' <span class="flag">★</span>' if n in watch else '')
    claims=' · '.join(one(n,v) for v,n in top[:2]) or '<span class="muted">No add helps</span>'
    d0,v0=drops[0]
    more=''
    if len(drops)>1 or len(top)>2:
        more='<details><summary>more</summary><div class="small">Other drops: '+', '.join(f'{html.escape(short(d))} ({INFO[d]["best"]:.1f} FP/G)' for d,v in drops[1:])+'<br>Other claims: '+', '.join(one(n,v) for v,n in top[2:])+'</div></details>'
    chips=' '.join(f'<span class="chip c{4 if f>=0.9*t else (3 if f>=0.8*t else 2)}">P{p} {f}/{t}</span>' for p,(f,t) in zip(RP,empty))
    return f'<tr><td>{html.escape(tn)}</td><td class="num">{chips}</td><td>{html.escape(short(d0))} <span class="tm">{INFO[d0]["pos"]} · {INFO[d0]["best"]:.1f} FP/G</span></td><td>{claims}{more}</td></tr>'
rivrows='\n'.join(rl(*x) for x in rival)
def rsl(tn,d0,sg):
    one=lambda x,big: f'{html.escape(short(x[2]))} <span class="tm">{INFO[x[2]]["pos"]} · {INFO[x[2]]["team"]}</span>{wbtn(x[2])} '+(f'<b>{x[0]:+.0f}</b> <span class="tm">/ {x[1]:+.0f} playoffs</span>' if big else f'<b>{x[0]:+.0f}</b>')+(' <span class="flag">⚔</span>' if x[2] in mine_season else '')+(' <span class="flag">★</span>' if x[2] in watch else '')
    best=one(sg[0],True) if sg else '<span class="muted">No add helps</span>'
    nxt=' · '.join(one(x,False) for x in sg[1:3]) or '<span class="muted">–</span>'
    return f'<tr><td>{html.escape(tn)}</td><td>{html.escape(short(d0))} <span class="tm">{INFO[d0]["pos"]} · {INFO[d0]["best"]:.1f} FP/G</span></td><td>{best}</td><td>{nxt}</td></tr>'
myrow=(lambda n: f'<tr class="cur"><td><b>You</b></td><td>{html.escape(short(STREAM))} <span class="tm">stream slot</span></td><td>{html.escape(short(n))} <span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span> <b>{tot(GA[n],REG):+.0f}</b> <span class="tm">/ {tot(GA[n],PO):+.0f} playoffs</span></td><td>'+' · '.join(f'{html.escape(short(m))} <b>{tot(GA[m],REG):+.0f}</b>' for m in mine_season[1:3])+'</td></tr>')(mine_season[0]) if mine_season else ''
rivseasonrows='\n'.join(rsl(*x) for x in rivseason)+'\n'+myrow
shot=defaultdict(list)
for tn,_,sg in rivseason:
    for x in sg[:3]: shot[x[2]].append(tn)
shottxt=('<p class="small"><b>Most wanted for the season (top 3 for 2+ teams):</b> '+'; '.join(f'{html.escape(short(n))} ({len(v)} teams{", also your target" if n in mine_season else ""})' for n,v in sorted(shot.items(),key=lambda x:-len(x[1])) if len(v)>=2)+'</p>') if any(len(v)>=2 for v in shot.values()) else ''
hot=sorted([(len(v),n) for n,v in cnt.items() if len(v)>=2],reverse=True)
hottxt=('<p class="small"><b>Most contested (in 2+ teams&#39; top 5):</b> '+'; '.join(f'{html.escape(short(n))} ({k} teams{", also your target" if n in mine_top else ""})' for k,n in hot)+'</p>') if hot else ''
_prog(28,'Valuing trade targets',40,3.7)
# ---- trade targets on rival rosters: what each would add to YOUR lineups (in your stream slot), regular season and playoffs
CAPR=sorted((INFO[m]['best'] for m in R),reverse=True)[min(4,len(R)-1)]
TCAND=sorted([(n,k,t,s2) for k,ro in OTH.items() for n,(t,s2) in ro.items() if INFO[n]['best']<=CAPR],key=lambda x:-INFO[x[0]]['best'])[:45]
TT=[]
for n,k,t,s2 in TCAND:
    f=min(1.0,INFO[n]['gp']/78.5) if INFO[n]['gp'] else 1.0
    g=gains(n,t,s2); ro=OTH[k]; rw={a:b for a,b in ro.items() if a!=n}
    loss=sum(ptot(ro,p)-ptot(rw,p) for p in REG)
    TT.append(dict(n=n,k=k,t=t,reg=tot(g,REG)*f,po=tot(g,PO)*f,loss=loss))
TTGAIN={x['n']:(x['reg'],x['po']) for x in TT}   # for the player card (TT is reused by Streaming)
def ttrow(x,hl):
    tn=html.escape("TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in x['k'] else x['k'])
    return (f'<tr><td><b>{html.escape(short(x["n"]))}</b> <span class="nbat" data-t="{x["t"]}">{x["t"]}</span> <span class="tm">{INFO[x["n"]]["pos"]}</span>'+(' <span class="tag ok">💎 value</span>' if hl=='reg' and x['reg']>=x['loss'] else '')+(f'<div class="tags">{dtag(x["n"])}</div>' if drf(x['n']) else '')+mkt(x['n'])+f'</td><td>{tn}</td>'
            f'<td class="num">{INFO[x["n"]]["best"]:.1f}</td><td class="num">{"<b>" if hl=="reg" else ""}{x["reg"]:+,.0f}{"</b>" if hl=="reg" else ""}</td>'
            f'<td class="num">{"<b>" if hl=="po" else ""}{x["po"]:+,.0f}{"</b>" if hl=="po" else ""}</td><td class="num">{x["loss"]:,.0f}</td></tr>')
SEGCSS='<style>.seg{display:inline-flex;flex-wrap:wrap;gap:0;border:1px solid var(--line);border-radius:999px;overflow:hidden;margin:2px 0 10px}@media (max-width:560px){.seg{display:flex;border-radius:12px}.seg button{flex:1 1 40%}.seg button+button{border-left:1px solid var(--line)}}.segp table{min-width:1060px}.segp td:nth-child(5){min-width:260px}#stash .segp td:nth-child(4){min-width:200px}.seg button{font:600 .8rem var(--body);padding:7px 14px;border:0;background:var(--panel);color:var(--muted);cursor:pointer;min-height:36px}.seg button+button{border-left:1px solid var(--line)}.seg button[aria-pressed=true]{background:var(--fg);color:var(--bg)}.trade-intro{margin:0}</style>'
SEGJS='<script>[].forEach.call(document.querySelectorAll(".seg[data-grp]"),function(g){var k=g.dataset.grp;[].forEach.call(g.querySelectorAll("button"),function(b){b.addEventListener("click",function(){[].forEach.call(g.querySelectorAll("button"),function(x){x.setAttribute("aria-pressed",x===b?"true":"false")});[].forEach.call(document.querySelectorAll(".segp[data-grp="+k+"]"),function(p){p.hidden=p.dataset.v!==b.dataset.v});try{localStorage.setItem("bblseg-"+k,b.dataset.v)}catch(e){}})});try{var v=localStorage.getItem("bblseg-"+k),bb=v&&g.querySelector("button[data-v="+v+"]");if(bb)bb.click()}catch(e){}});</script>'
TTH='<thead><tr><th>Player</th><th>Manager</th><th>CBS FP/G</th><th>Reg. season gain</th><th>Playoff gain</th><th>Worth to them</th></tr></thead>'
ttreg=''.join(ttrow(x,'reg') for x in sorted(TT,key=lambda x:-x['reg'])[:10])
ttpo=''.join(ttrow(x,'po') for x in sorted(TT,key=lambda x:-x['po'])[:10])
TEAMCOL={'ATL':('#C8102E','#FFFFFF'),'BOS':('#007A33','#FFFFFF'),'BKN':('#000000','#FFFFFF'),'CHA':('#00788C','#FFFFFF'),'CHI':('#CE1141','#000000'),
 'CLE':('#860038','#FDBB30'),'DAL':('#00538C','#FFFFFF'),'DEN':('#0E2240','#FEC524'),'DET':('#1D42BA','#FFFFFF'),'GS':('#1D428A','#FFC72C'),
 'HOU':('#CE1141','#FFFFFF'),'IND':('#002D62','#FDBB30'),'LAC':('#C8102E','#FFFFFF'),'LAL':('#552583','#FDB927'),'MEM':('#5D76A9','#FFFFFF'),
 'MIA':('#98002E','#F9A01B'),'MIL':('#00471B','#EEE1C6'),'MIN':('#0C2340','#78BE20'),'NO':('#0C2340','#C8A974'),'NY':('#006BB6','#F58426'),
 'OKC':('#007AC1','#FFFFFF'),'ORL':('#0077C0','#FFFFFF'),'PHI':('#006BB6','#FFFFFF'),'PHO':('#1D1160','#E56020'),'POR':('#000000','#E03A3E'),
 'SAC':('#5A2D81','#FFFFFF'),'SA':('#C4CED4','#000000'),'TOR':('#CE1141','#FFFFFF'),'UTA':('#002B5C','#F9A01B'),'WAS':('#002B5C','#E31837')}
for a,b in {'GSW':'GS','NOP':'NO','NYK':'NY','PHX':'PHO','SAS':'SA','UTAH':'UTA','WSH':'WAS','BRK':'BKN','CHO':'CHA'}.items(): TEAMCOL[a]=TEAMCOL[b]
NBATCSS=('<style>.src{display:inline-block;font:700 .6rem var(--mono);letter-spacing:.04em;padding:1px 4px;border-radius:3px;color:#fff;vertical-align:1px;margin-right:3px}.src.es{background:#c8102e}.src.cb{background:none;color:inherit;font-weight:600;padding:0;letter-spacing:0}.rost{font:700 .78rem var(--mono);white-space:nowrap}.rost small{font-weight:600;color:var(--muted)}.nbat{display:inline-block;font:700 .72rem var(--mono);letter-spacing:.04em;padding:1px 7px;border-radius:6px;border:1px solid var(--line);background:var(--pobg);color:var(--fg);vertical-align:1px}.nbat.sm{font-size:.62rem;padding:0 5px;border-radius:5px}'
 +''.join(f'.nbat[data-t="{k}"]{{background:{bg};color:{fg};border-color:{"#6b7280" if bg=="#000000" else bg}}}' for k,(bg,fg) in TEAMCOL.items())+'</style>')
# recent form from the box scores (Watchlist and Trade analyzer: Last 3 / Season FP/G)
def _form_games():
    fm=defaultdict(list)   # name key -> [(YYYYMMDD, base pts, reb, ast, 3pm)] for games he played
    for bf in sorted(glob.glob('box_*.txt')):
        d=os.path.basename(bf)[4:12]; ln=open(bf,encoding='utf-8').read().strip().splitlines()
        try: fin=int(ln[0].lstrip('#').split('|')[1])
        except (IndexError,ValueError): fin=0
        if not d.isdigit() or not fin: continue
        for l in ln[1:]:
            q=l.split('|')
            if len(q)<16: continue
            try: mi,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,to,stl,blk,pf=[float(x or 0) for x in q[2:16]]
            except ValueError: continue
            if mi>0: k=nk(q[0]); fm[NKALIAS.get(k,k)].append((d,pts+2*fgm-fga+ftm-fta+reb+2*ast+4*stl+4*blk-2*to-pf,reb,ast,tpm))
    return fm
FORM=_form_games()
def form(n,last=None):  # [actual FP/G at his best slot (G +REB, F +AST, C +3PM), games], comparable to the CBS FP/G
    k=nk(n); gl=sorted(FORM.get(NKALIAS.get(k,k),[]))[-last if last else 0:]
    if not gl: return None
    return [round(max(sum(x[1]+x[{'G':2,'F':3,'C':4}[s]] for x in gl)/len(gl) for s in INFO[n]['pos'].split(',')),1),len(gl)]
# ---- Trade analyzer (Trades tab): pick any players on your side and one rival's; the browser re-runs both teams' best daily
# lineups (same rule as best(): G, F, C + 2 Util) for every day left, before and after. Data: each rostered player's slot values,
# CBS games share (gp/78.5) and a 0/1 string of the days he's available (games, out-until dates, rests on back-to-backs).
def _build_tana():
    global tasec
    _tn=lambda k:"TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in k else k   # dname() comes later in the file
    days=[d for p in PER for d in P[p]]; di={d:i for i,d in enumerate(days)}
    pl=[]; ros={'me':[]}
    def add(n,t,s,team):
        a=''.join('1' if d in G.get(t,()) and not (n in out and d<out[n]) and not sits(n,t,d) else '0' for d in days)
        g=INFO[n]['gp'] if n in INFO else 0
        pl.append(dict(n=short(n),t=t,p=INFO[n]['pos'] if n in INFO else '',fp=round(INFO[n]['best'],1) if n in INFO else 0,
                       s={k:round(v,2) for k,v in s.items()},f=round(min(1.0,g/78.5),3) if g else 1,a=a,ir=n in INFO and INFO[n]['sec']=='I',
                       N=n,l3=form(n,3) if n in INFO else None,sz=form(n) if n in INFO else None))
        ros[team].append(len(pl)-1)
    for n,(t,s) in sorted(R.items(),key=lambda kv:-INFO[kv[0]]['best']): add(n,t,s,'me')
    for k in sorted(OTH,key=lambda k:_tn(k).lower()):
        ros[k]=[]
        for n,(t,s) in sorted(OTH[k].items(),key=lambda kv:-INFO[kv[0]]['best']): add(n,t,s,k)
    ros['_fa']=[]   # free agents you could pick up after the trade, best first
    for n,(t,s) in sorted(((n,v) for n,v in FA.items() if v[1]),key=lambda kv:-INFO[kv[0]]['best']): add(n,t,s,'_fa')
    fai=ros.pop('_fa')
    _ij=lambda n:'' if not INFO[n].get('inj') else ('GTD' if 'game time decision' in INFO[n]['inj'].lower() else 'OUT')
    for i_ in fai: pl[i_]['ij']=_ij(pl[i_]['N'])
    cols=[dict(l=f'P{p}'+(' · now' if p==CUR else ''),ps=[[di[d] for d in P[p]]],x=int(k>=3)) for k,p in enumerate(REG)]
    if REG: cols.append(dict(l=f'Rest of reg. season',ps=[[di[d] for d in P[p]] for p in REG]))
    if PO: cols.append(dict(l='Playoffs · P22–P24',ps=[[di[d] for d in P[p]] for p in PO]))
    data=dict(pl=pl,ros=ros,cols=cols,names={k:_tn(k) for k in OTH},me=MEDISP,fa=fai,wl=[n for n in watch if n in FA],
              stream=next((i for i in ros['me'] if pl[i]['N']==STREAM),None),lim=13)   # 13 = 5 active + 8 reserves; IR is on top
    tasec=('<section id="tana" class="xwrap"><h2>Trade analyzer</h2><p class="small" style="margin:0 0 8px">Pick a manager, then any players you&#39;d give and get. '
           'Both teams&#39; best daily lineups are re-run for every day left, before and after the trade.</p>'
           '<label class="dropsel">Trade with <select id="tawho"></select></label> <button type="button" class="xper" data-x="tana" data-l0="Show all periods ▸" data-l1="◂ Next 3 periods" aria-pressed="false" title="Show every regular-season period left">Show all periods ▸</button><div class="tagrid"><div><h3>You give</h3><div id="tagive" class="talist"></div></div>'
           '<div><h3>You get</h3><div id="taget" class="talist"></div></div></div>'
           '<div class="tawv"><h3>…then add from waivers <span class="small" style="font-weight:400;text-transform:none;letter-spacing:normal">optional</span></h3><div id="tafa"></div>'
           '<p class="tawb"><button type="button" id="taadd" class="tareset">+ Another pickup</button><button type="button" id="tasug" class="tareset" title="Tries the 60 highest free agents against this trade">Suggest pickups</button></p><div id="tasugo"></div></div><div id="taout"></div>'
           '<p class="small" style="margin:6px 0 0"><b>What if he plays like this?</b> Tap a player&#39;s FP/G to change it: type a number, or pick <b>Last 3</b> or <b>Season</b> for what he&#39;s actually averaged, and the trade re-runs. '
           'Changed ones show in blue; <b>↺</b> puts one back on his CBS projection. Same values as the Watchlist: a change here shows there, and the other way round (saved in this browser). '
           '<button type="button" id="tareset" class="tareset" hidden>↺ Reset FP/G</button></p>'
           '<p class="small">Points the trade adds to (+) or takes from (−) each team&#39;s best daily lineups (G, F, C + 2 Util, each player in his best slot), from today on, '
           'using CBS FP/G scaled down for players CBS projects to miss games, out-until dates and back-to-back rests. Pickups count only if you add them under <b>…then add from waivers</b>, each replacing who you pick in <b>for</b>; the note under the table tracks your 13 roster spots (IR is on top). '
           'A claim isn&#39;t guaranteed: he has to reach you on waivers. The other team&#39;s extra player isn&#39;t dropped. IR players count from their return date.</p></section>'
           '<style>.tagrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px 24px;margin:8px 0}.talist{display:grid;gap:2px}'
           '.talist label{display:flex;gap:8px;align-items:baseline;padding:3px 6px;border-radius:6px;cursor:pointer}.talist label:hover{background:var(--pobg)}'
           '.talist input{accent-color:var(--accent)}.talist .num{margin-left:auto;color:var(--muted)}.tarow{display:flex;align-items:baseline;gap:8px;padding:0 6px 0 0;border-radius:6px}.tarow:hover{background:var(--pobg)}.tarow label{flex:1}.tarow label:hover{background:none}.tarow .wif-td{color:var(--muted)}.tarow.wif{background:color-mix(in srgb,#2563eb 8%,transparent);box-shadow:inset 3px 0 0 #2563eb}.tarow.wif .wif-v{color:#2563eb;font-weight:600}.tarow.wjust{animation:wjust 2.2s ease-out}:root[data-theme="dark"] .tarow.wif .wif-v{color:#93c5fd}.tareset,.pgreset{font:600 .78rem var(--body);padding:3px 10px;border:1px solid var(--accent);border-radius:999px;background:none;color:var(--accent);cursor:pointer;margin-left:6px}.tawv{margin:6px 0 12px}.tawv h3{margin:0 0 4px}.tafar{display:flex;flex-wrap:wrap;gap:6px 22px;align-items:flex-start;padding:5px 0;border-bottom:1px solid var(--line)}.tafc{display:flex;flex-direction:column;gap:4px;align-items:flex-start;min-width:0}.tafp{align-items:baseline;gap:6px;padding:1px 8px 1px 6px;font-size:.88rem}.tafpl{color:var(--muted);font-size:.78rem}.tafp .wif-v{font-weight:600}.tafar .dropsel{margin:0}.tafar select{max-width:320px}.tafar .wif-td{color:var(--muted)}.tafx{border:0;background:none;color:var(--muted);cursor:pointer;font-size:1rem}.tawb{margin:6px 0 0}.tawb .tareset:first-child{margin-left:0}.tawb .tareset:disabled{opacity:.45;cursor:default}.tawarn{color:var(--warn);font-weight:600}#tasugo{margin-top:6px}#tasugo td{vertical-align:middle}#tasugo button{font:600 .75rem var(--body);padding:2px 9px;border:1px solid var(--accent);border-radius:999px;background:none;color:var(--accent);cursor:pointer}#taout table{min-width:640px}#taout .pos{color:var(--ok)}#taout .neg{color:var(--bad)}</style>'
           +TAJS.replace('__TA__',json.dumps(data,separators=(',',':')).replace('</','<\\/')))
TAJS=r'''<script>(function(){var D=__TA__;var who=document.getElementById("tawho");if(!who)return;
var PL=D.pl,COV=[[],["G"],["F"],["C"],["G","F"],["G","C"],["F","C"],["G","F","C"]],BC={};
function best(ix,sc){var key=(sc?"s":"u")+ix.join(",");if(key in BC)return BC[key];var n=ix.length,vals=ix.map(function(i){var p=PL[i],o={};for(var k in p.s)o[k]=sc?p.s[k]*p.f:p.s[k];return o}),
top=vals.map(function(o){var m=-1e9;for(var k in o)if(o[k]>m)m=o[k];return m}),ord=top.map(function(_,i){return i}).sort(function(a,b){return top[b]-top[a]}),bv=0,pick=[];
COV.forEach(function(R){var cand=R.map(function(r){var c=[];for(var i=0;i<n;i++)if(r in vals[i])c.push(i);return c});
(function rec(j,v){if(j===R.length){var k=0,ad=0;for(var q=0;q<n&&k<2;q++){var i=ord[q];if(pick.indexOf(i)>=0)continue;if(top[i]>0)ad+=top[i];k++}if(v+ad>bv)bv=v+ad;return}
for(var x=0;x<cand[j].length;x++){var i=cand[j][x];if(pick.indexOf(i)>=0)continue;pick.push(i);rec(j+1,v+vals[i][R[j]]);pick.pop()}})(0,0)});
return BC[key]=bv}
function tot(ro,days,sc){var s=0;days.forEach(function(d){var on=ro.filter(function(i){return PL[i].a.charAt(d)==="1"}).sort(function(a,b){return a-b});if(on.length)s+=best(on,sc)});return s}
function cols(ro,sc){return D.cols.map(function(c){var s=0;c.ps.forEach(function(ds){s+=tot(ro,ds,sc)});return s})}
window.__taCols=function(ro,sc){return cols(ro,sc)};window.__taRos=D.ros;
Object.keys(D.names).forEach(function(k){var o=document.createElement("option");o.value=k;o.textContent=D.names[k];who.appendChild(o)});
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function list(el,ro){el.innerHTML=ro.map(function(i){var p=PL[i];return '<div class="tarow'+(p.fp!==p.fp0?' wif':'')+'" data-r="'+i+'"><label><input type="checkbox" value="'+i+'"><b class="pcn" title="Player card (tick the box to add him to the trade)">'+esc(p.n)+'</b> <span class="nbat" data-t="'+esc(p.t)+'">'+esc(p.t)+'</span> <span class="tm">'+esc(p.p)+(p.ir?' · IR':'')+'</span></label><span class="num wif-td" data-c="'+i+'">'+cell(i)+'</span></div>'}).join("")}
// FP/G what-if, as on the Watchlist (and shared with it: the same saved values, by player): tap the number, type one or pick
// CBS / Last 3 / Season; his slot values move by the change, like the Watchlist's simulations
var TO=null,TF=false,WIF={};PL.forEach(function(p){p.fp0=p.fp;p.s0=p.s});
function rw(){try{WIF=JSON.parse(localStorage.getItem("bbl-wif")||"{}")||{}}catch(e){WIF={}}}
function apply(){BC={};PL.forEach(function(p){var v=WIF[p.N];v=v!=null&&v>=0?v:p.fp0;p.fp=v;var o={};for(var k in p.s0)o[k]=Math.max(0,p.s0[k]+v-p.fp0);p.s=o})}
function cell(i,zf){var p=PL[i],ch=p.fp!==p.fp0,op=TO===i&&!!zf===TF,h='<button type="button" class="wif-v" data-i="'+i+'" aria-expanded="'+op+'" title="'+(ch?'CBS projects '+p.fp0+'. ':'')+'Change his FP/G to see the trade at that level">'+p.fp+'</button>'
+(ch?'<button type="button" class="wif-r" data-i="'+i+'" title="Reset to the CBS projection ('+p.fp0+')">↺</button>':'');
if(op){var c=[["CBS",p.fp0]];if(p.l3)c.push([p.l3[1]>=3?"Last 3":"Last "+p.l3[1],p.l3[0]]);if(p.sz&&p.sz[1]>3)c.push(["Season",p.sz[0]]);
h+='<div class="wif-pop"><input type="number" class="wif-in" inputmode="decimal" step="0.5" min="0" value="'+p.fp+'" data-i="'+i+'" aria-label="FP/G for '+esc(p.n)+'">'+c.map(function(q){return '<button type="button" class="wif-c" data-i="'+i+'" data-v="'+q[1]+'" aria-pressed="'+(q[1]===p.fp)+'">'+q[0]+' <b>'+q[1]+'</b></button>'}).join("")+'</div>'}
return h}
function cells(){[].forEach.call(document.querySelectorAll("#tana [data-c]"),function(c){var i=+c.dataset.c;c.innerHTML=cell(i,!!c.closest("#tafa"));c.parentNode.classList.toggle("wif",PL[i].fp!==PL[i].fp0)});edn();optsync()}
function save(){try{localStorage.setItem("bbl-wif",JSON.stringify(WIF))}catch(e){}document.dispatchEvent(new CustomEvent("bbl-wif",{detail:"ta"}))}
function setv(i,v){var p=PL[i];if(v==null||isNaN(v)||v<0||Math.round(v*10)/10===p.fp0)delete WIF[p.N];else WIF[p.N]=Math.round(v*10)/10;save();apply()}
function edn(){var n=PL.filter(function(p){return p.fp!==p.fp0}).length,b=document.getElementById("tareset");if(b){b.hidden=!n;b.textContent="↺ Reset FP/G ("+n+")"}}
function shut(){if(TO===null)return;var i=TO;TO=null;cells();var r=document.querySelector('#tana [data-r="'+i+'"]');if(r){r.classList.remove("wjust");void r.offsetWidth;r.classList.add("wjust")}}
rw();apply();
function picked(el){return [].map.call(el.querySelectorAll("input:checked"),function(x){return +x.value})}
// waiver pickups: each row adds a free agent, for one of your players or into an open spot, on top of the trade
var ADDS=[{i:null,d:null}],fab=document.getElementById("tafa"),sugo=document.getElementById("tasugo");
function base(){var g=picked(gv),r=picked(gt);return D.ros.me.filter(function(i){return g.indexOf(i)<0}).concat(r)}
function withp(){var ro=base();ADDS.forEach(function(x){if(x.i==null)return;if(x.d!=null)ro=ro.filter(function(i){return i!==x.d});if(ro.indexOf(x.i)<0)ro.push(x.i)});return ro}
function room(ro){return D.lim-ro.filter(function(i){return !PL[i].ir}).length}
function pickd(ro,bar){if(D.stream!=null&&ro.indexOf(D.stream)>=0&&D.stream!==bar)return D.stream;var c=ro.filter(function(i){return !PL[i].ir&&D.fa.indexOf(i)<0&&i!==bar}).sort(function(a,b){return PL[a].fp-PL[b].fp});return c.length?c[0]:null}
function flab(i){var p=PL[i];return p.n+" ("+p.p+" · "+p.t+" · "+p.fp+" FP/G"+(p.ij?" · "+p.ij:"")+")"}
function dlab(i){var p=PL[i];return p.n+" ("+p.p+(i===D.stream?", stream slot":"")+" · "+p.fp+" FP/G)"}
function fopt(i,sel){return '<option value="'+i+'"'+(i===sel?' selected':'')+'>'+esc(flab(i))+'</option>'}
function optsync(){if(!fab)return;[].forEach.call(fab.querySelectorAll("option"),function(o){if(o.value==="")return;var i=+o.value,t=o.closest("select").classList.contains("tafas")?flab(i):dlab(i);if(o.text!==t)o.text=t})}
function chip(i){return '<span class="tarow tafp'+(PL[i].fp!==PL[i].fp0?' wif':'')+'" data-r="'+i+'"><b class="pcn">'+esc(PL[i].n)+'</b> <span class="tafpl">FP/G</span> <span class="num wif-td" data-c="'+i+'">'+cell(i,1)+'</span></span>'}
function fa(){var ro=base(),wl=(window.__bblwl||D.wl||[]).map(function(n){return String(n).toLowerCase()});
ADDS.forEach(function(x){if(x.d!=null&&ro.indexOf(x.d)<0)x.d=null});
fab.innerHTML=ADDS.map(function(x,k){var fr=D.fa.filter(function(i){return i===x.i||!ADDS.some(function(y){return y.i===i})}),w=fr.filter(function(i){return wl.indexOf(PL[i].N.toLowerCase())>=0});
var dr=ro.filter(function(i){return !PL[i].ir&&(i===x.d||!ADDS.some(function(y){return y.d===i}))});
return '<div class="tafar" data-k="'+k+'"><div class="tafc"><label class="dropsel">Add <select class="tafas"><option value="">Pick a free agent</option>'
+(w.length?'<optgroup label="Your watchlist">'+w.map(function(i){return fopt(i,x.i)}).join("")+'</optgroup>':'')+'<optgroup label="All free agents">'+fr.filter(function(i){return w.indexOf(i)<0}).map(function(i){return fopt(i,x.i)}).join("")+'</optgroup></select></label>'+(x.i!=null?chip(x.i):'')+'</div>'
+'<div class="tafc"><label class="dropsel">for <select class="tafad"'+(x.i==null?' disabled':'')+'><option value="">Nobody (open spot)</option>'+dr.map(function(i){return '<option value="'+i+'"'+(i===x.d?' selected':'')+'>'+esc(dlab(i))+'</option>'}).join("")+'</select></label>'+(x.d!=null?chip(x.d):'')+'</div>'
+(ADDS.length>1||x.i!=null?'<button type="button" class="tafx" aria-label="Remove this pickup" title="Remove">✕</button>':'')+'</div>'}).join("");
document.getElementById("taadd").disabled=ADDS.length>=4||ADDS.some(function(x){return x.i==null})}
function setfa(x,i){x.i=i;x.d=null;if(i!=null&&room(withp())<0)x.d=pickd(withp().filter(function(q){return q!==i}),i)}
function suggest(){var ro=withp(),ri=D.cols.findIndex(function(c){return /Rest/.test(c.l)}),pi=D.cols.findIndex(function(c){return /Playoffs/.test(c.l)});
function val(r,ci){if(ci<0)return 0;var s=0;D.cols[ci].ps.forEach(function(ds){s+=tot(r,ds,1)});return s}
var dp=room(ro)>0?null:pickd(ro),b=dp==null?ro:ro.filter(function(i){return i!==dp}),r0=val(ro,ri),p0=val(ro,pi);
var res=D.fa.filter(function(i){return ro.indexOf(i)<0}).slice().sort(function(a,c){return PL[c].fp-PL[a].fp}).slice(0,60).map(function(i){var n=b.concat([i]),r=val(n,ri)-r0,q=val(n,pi)-p0;return {i:i,r:r,q:q,t:r+q}}).filter(function(x){return x.t>0}).sort(function(a,c){return c.t-a.t}).slice(0,5);
sugo.innerHTML=res.length?'<p class="small" style="margin:0 0 4px">Best pickups for this move'+(dp!=null?', each replacing <b>'+esc(PL[dp].n)+'</b>':', into your open spot')+':</p><div class="scroll"><table data-xs><thead><tr><th>Free agent</th><th>FP/G</th><th>Rest of reg. season</th><th>Playoffs</th><th></th></tr></thead><tbody>'
+res.map(function(x){var p=PL[x.i];return '<tr><td><b class="pcn">'+esc(p.n)+'</b> <span class="nbat" data-t="'+esc(p.t)+'">'+esc(p.t)+'</span> <span class="tm">'+esc(p.p)+'</span></td><td class="num">'+p.fp+'</td><td class="num">'+f(x.r)+'</td><td class="num">'+f(x.q)+'</td><td><button type="button" class="tasa" data-i="'+x.i+'">Add</button></td></tr>'}).join("")+'</tbody></table></div>':'<p class="muted" style="margin:0">None of the top 60 free agents adds points to this move.</p>'}
function f(v){v=Math.round(v);return '<span class="'+(v>0?"pos":v<0?"neg":"")+'">'+(v>0?"+":"")+v.toLocaleString()+'</span>'}
var gv=document.getElementById("tagive"),gt=document.getElementById("taget"),out=document.getElementById("taout");
function run(){var g=picked(gv),r=picked(gt),k=who.value,hasA=ADDS.some(function(x){return x.i!=null}),hasT=g.length+r.length>0;sugo.innerHTML="";if(!hasT&&!hasA){out.innerHTML='<p class="muted">Tick players on both sides to see what the trade does.</p>';return}
var me=D.ros.me,th=D.ros[k],me2=me.filter(function(i){return g.indexOf(i)<0}).concat(r),th2=th.filter(function(i){return r.indexOf(i)<0}).concat(g);
var a=cols(me,1),b=cols(me2,1),c=cols(th,1),d=cols(th2,1),dm=b.map(function(x,i){return x-a[i]}),dt=d.map(function(x,i){return x-c[i]});
var nr=D.cols.length,ri=D.cols.findIndex(function(c){return /Rest/.test(c.l)}),pi=D.cols.findIndex(function(c){return /Playoffs/.test(c.l)});
var me3=withp(),e=hasA?cols(me3,1):b,dx=e.map(function(x,i){return x-a[i]}),de=e.map(function(x,i){return x-b[i]});
var yv=(ri>=0?dm[ri]:0)+(pi>=0?dm[pi]:0),tv=(ri>=0?dt[ri]:0)+(pi>=0?dt[pi]:0),yx=(ri>=0?dx[ri]:0)+(pi>=0?dx[pi]:0);
var verdict=!hasT?(yx>0?"These pickups add points on their own.":"These pickups don&#39;t add points."):yx>0&&tv>0?"Both teams gain: worth offering.":yx>0?"Good for you, but "+esc(D.names[k])+" loses points: expect a hard sell.":tv>0?"It helps "+esc(D.names[k])+" more than you: not worth it as is.":"Neither team gains.";
var line=function(lab,v,bold){return '<tr><td>'+lab+'</td>'+v.map(function(x,i){return '<td class="num'+(D.cols[i].x?' wx':'')+'">'+(bold?'<b>'+f(x)+'</b>':f(x))+'</td>'}).join("")+'</tr>'};
var fr_=room(me3),th3=hasT&&th2.length>D.lim?th2.length-D.lim:0,note=fr_<0?'<span class="tawarn">⚠️ You&#39;d be '+(-fr_)+' over your '+D.lim+' roster spots: pick who goes in “for” above.</span>':fr_>0?"You&#39;d have "+fr_+" open roster spot"+(fr_>1?"s":"")+(hasA?"":": add a free agent above to count him")+".":"";
if(th3)note+=(note?" ":"")+esc(D.names[k])+" would have to drop "+th3+" (not counted above).";
var cmp=hasA&&hasT?'<p class="small" style="margin:4px 0 0">Regular season + playoffs: trade alone '+f(yv)+', with pickups <b>'+f(yx)+'</b>.</p>':"";
out.innerHTML='<div class="scroll"><table data-xs><thead><tr><th></th>'+D.cols.map(function(c){return "<th"+(c.x?' class="wx"':"")+">"+esc(c.l)+"</th>"}).join("")+'</tr></thead><tbody>'
+(hasA?(hasT?line("You · trade only",dm):"")+line("Pickups add",de)+line("<b>You · "+(hasT?"trade + pickups":"with pickups")+"</b>",dx,1):line("<b>You</b>",dm,1))
+(hasT?line(esc(D.names[k]),dt):"")+'</tbody></table></div>'
+'<p style="margin:8px 0 0"><b>'+verdict+'</b> '+(note?'<span class="small">'+note+'</span>':'')+'</p>'+cmp}
function load(){list(gv,D.ros.me);list(gt,D.ros[who.value]||[]);edn();fa();run()}
fab.addEventListener("change",function(e){var q=e.target.closest(".tafas,.tafad");if(!q)return;var x=ADDS[+q.closest(".tafar").dataset.k],v=q.value===""?null:+q.value;if(q.classList.contains("tafas"))setfa(x,v);else x.d=v;fa();run()});
fab.addEventListener("click",function(e){var b=e.target.closest(".tafx");if(!b)return;ADDS.splice(+b.closest(".tafar").dataset.k,1);if(!ADDS.length)ADDS.push({i:null,d:null});fa();run()});
document.getElementById("taadd").addEventListener("click",function(){ADDS.push({i:null,d:null});fa()});
document.getElementById("tasug").addEventListener("click",function(){sugo.innerHTML='<p class="muted" style="margin:0">Trying the top free agents…</p>';setTimeout(suggest,30)});
sugo.addEventListener("click",function(e){var b=e.target.closest(".tasa");if(!b)return;var x=ADDS.filter(function(y){return y.i==null})[0];if(!x){if(ADDS.length>=4)return;x={i:null,d:null};ADDS.push(x)}setfa(x,+b.dataset.i);fa();run()});
[gv,gt,fab].forEach(function(el){el.addEventListener("click",function(e){var b=e.target.closest(".wif-v,.wif-r,.wif-c");if(!b)return;e.preventDefault();var i=+b.dataset.i;
if(b.classList.contains("wif-v")){var zf=!!b.closest("#tafa");if(TO===i&&TF===zf){shut();return}TO=i;TF=zf;cells();var x=document.querySelector('#tana .wif-pop .wif-in');if(x){x.focus();x.select()}return}
setv(i,b.classList.contains("wif-r")?null:parseFloat(b.dataset.v));TO=null;cells();run()});
el.addEventListener("input",function(e){var t=e.target;if(!t.classList.contains("wif-in"))return;var i=+t.dataset.i,p=PL[i];setv(i,t.value===""?NaN:+t.value);
var c=t.closest("[data-c]");[].forEach.call(document.querySelectorAll('#tana [data-c="'+i+'"]'),function(q){q.querySelector(".wif-v").textContent=p.fp;q.parentNode.classList.toggle("wif",p.fp!==p.fp0)});optsync();[].forEach.call(c.querySelectorAll(".wif-c"),function(b){b.setAttribute("aria-pressed",String(+b.dataset.v===p.fp))});edn();run()});
el.addEventListener("change",function(e){if(e.target.classList.contains("wif-in"))e.stopPropagation()},true);
el.addEventListener("keydown",function(e){if(e.target.classList.contains("wif-in")&&(e.key==="Enter"||e.key==="Escape")){e.preventDefault();shut()}})});
document.addEventListener("click",function(e){if(TO!==null&&e.target.isConnected&&!e.target.closest("#tana .wif-td"))shut()});
document.addEventListener("bbl-wif",function(e){if(e.detail==="ta")return;rw();apply();cells();run()});   // changed on the Watchlist
document.getElementById("tareset").addEventListener("click",function(){PL.forEach(function(p){delete WIF[p.N]});save();apply();TO=null;cells();run()});
window.__taPick=function(k,give,get){if(!D.ros[k])return;who.value=k;load();[[gv,give],[gt,get]].forEach(function(z){[].forEach.call(z[0].querySelectorAll("label"),function(l){var b=l.querySelector(".pcn");if(b&&z[1].indexOf(b.textContent.trim())>=0)l.querySelector("input").checked=true})});fa();run();document.getElementById("tana").scrollIntoView({behavior:"smooth",block:"start"})};
who.addEventListener("change",load);gv.addEventListener("change",function(){fa();run()});gt.addEventListener("change",function(){fa();run()});load()})();</script>'''
_build_tana()
# ---- Trade finder (Trades tab): every 1-for-1 swap with every manager, measured like the Trade analyzer (both teams' best
# daily lineups, CBS FP/G scaled by games share, rest of regular season + playoffs). Quick estimate for every pair (what he adds
# to the other roster minus what the player leaving was worth), then the best-looking ones re-run exactly. Lists deals where
# both teams gain; "Open in analyzer" ticks them there. notrade| players (settings.txt) are never offered.
def _build_tfind():
    global tfsec
    t0=time.time()
    NOTR={l.split('|')[1] for l in open('settings.txt',encoding='utf-8-sig',errors='replace') if l.startswith('notrade|') and l.count('|')>=2}
    DR=[d for p in REG for d in P[p]]; DP=[d for p in PO for d in P[p]]
    def scl(r): return {n:(t,{k:v*(min(1.0,INFO[n]['gp']/78.5) if INFO[n]['gp'] else 1.0) for k,v in s.items()}) for n,(t,s) in r.items()}
    C={}
    def sb(pl):
        k=tuple(sorted(n for n,_ in pl))
        if k not in C: C[k]=best(pl,False)
        return C[k]
    def val(r): return (sum(sb(avail(r,d)) for d in DR),sum(sb(avail(r,d)) for d in DP))
    def dif(a,b): return (a[0]-b[0],a[1]-b[1])
    me=scl(R); bme=val(me)
    give=[n for n in R if n not in NOTR and INFO[n]['sec']!='I' and not (n in out and out[n]>TODAY+dt.timedelta(30))]
    wme={y:sum(dif(bme,val({k:v for k,v in me.items() if k!=y}))) for y in give}
    res=[]
    for k,ro in OTH.items():
        th=scl(ro); bth=val(th)
        wth={x:sum(dif(bth,val({a:b for a,b in th.items() if a!=x}))) for x in th}
        addme={x:sum(dif(val({**me,x:th[x]}),bme)) for x in th}
        addth={y:sum(dif(val({**th,y:me[y]}),bth)) for y in give}
        est=sorted(((addme[x]-wme[y],addth[y]-wth[x],y,x) for y in give for x in th if addme[x]-wme[y]>0 and addth[y]-wth[x]>-40),reverse=True)[:6]
        for _,_,y,x in est:
            m=dif(val({**{a:b for a,b in me.items() if a!=y},x:th[x]}),bme)
            o=dif(val({**{a:b for a,b in th.items() if a!=x},y:me[y]}),bth)
            if sum(m)>0: res.append(dict(k=k,y=y,x=x,m=m,o=o))
    both=sorted((r for r in res if sum(r['o'])>0),key=lambda r:-sum(r['m']))
    near=sorted((r for r in res if -40<sum(r['o'])<=0),key=lambda r:-sum(r['m']))
    _tn=lambda k:"TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in k else k
    sg=lambda v:f'<span class="{"pos" if v>0.5 else "neg" if v<-0.5 else ""}">{v:+,.0f}</span>'
    def row(r):
        y,x,k=r['y'],r['x'],r['k']
        return (f'<tr><td><b>{html.escape(short(y))}</b> <span class="nbat" data-t="{INFO[y]["team"]}">{INFO[y]["team"]}</span> <span class="tm">{INFO[y]["pos"]} · {INFO[y]["best"]:.1f}</span></td>'
                f'<td><b>{html.escape(short(x))}</b> <span class="nbat" data-t="{INFO[x]["team"]}">{INFO[x]["team"]}</span> <span class="tm">{INFO[x]["pos"]} · {INFO[x]["best"]:.1f}</span></td>'
                f'<td>{html.escape(_tn(k))}</td><td class="num"><b>{sg(r["m"][0])}</b> / {sg(r["m"][1])}</td><td class="num">{sg(r["o"][0])} / {sg(r["o"][1])}</td>'
                f'<td><button type="button" class="tfgo" data-k="{html.escape(k)}" data-y="{html.escape(short(y))}" data-x="{html.escape(short(x))}">Open in analyzer</button></td></tr>')
    TH='<thead><tr><th>You give</th><th>You get</th><th>Manager</th><th>You · reg. season / playoffs</th><th>Them · reg. season / playoffs</th><th></th></tr></thead>'
    body=(f'<div class="scroll"><table class="tftab">{TH}<tbody>{"".join(row(r) for r in both[:12])}</tbody></table></div>' if both else
          '<p class="muted">No 1-for-1 swap helps both teams right now.</p>')
    if near: body+=(f'<details><summary>Good for you, small cost to them ({len(near[:8])})</summary><div class="scroll"><table class="tftab">{TH}<tbody>{"".join(row(r) for r in near[:8])}</tbody></table></div>'
                    '<p class="small">They lose under 40 points: a small sweetener or a schedule pitch may close these.</p></details>')
    tfsec=(f'<section id="tfind"><h2>Trade finder · 1-for-1 deals both teams should like</h2>{body}'
           f'<p class="small">Every one-for-one swap with every manager, scored like the Trade analyzer: both teams&#39; best daily lineups from today on, '
           f'regular season (P{REG[0] if REG else 21}–P21) / playoffs (P22–P24), CBS FP/G scaled for games CBS expects them to miss. A team that gains is more likely to say yes. '
           f'Your players on IR or out 30+ days{" and your no-trade list ("+", ".join(html.escape(n) for n in sorted(NOTR))+")" if NOTR else ""} aren&#39;t offered. '
           'For 2-for-1 deals see <a href="#twoforone">2-for-1 packages</a>.</p></section>'
           '<style>.tftab td:nth-child(4),.tftab td:nth-child(5){white-space:nowrap}.tftab .pos{color:var(--ok)}.tftab .neg{color:var(--bad)}'
           '.tfgo{font:600 .78rem var(--body);padding:4px 10px;border:1px solid var(--accent);border-radius:999px;background:none;color:var(--accent);cursor:pointer;white-space:nowrap}</style>'
           '<script>document.addEventListener("click",function(e){var b=e.target.closest(".tfgo");if(!b||!window.__taPick)return;window.__taPick(b.dataset.k,[b.dataset.y],[b.dataset.x])});</script>')
    print(f'trade finder: {len(res)} exact, {len(both)} both gain, {time.time()-t0:.1f}s',file=sys.stderr)
_build_tfind()
tradesec=f"""{NBATCSS}{SEGCSS}{tasec}{tfsec}<section id="ttargets">
<h2>Trade targets on rival rosters</h2>
<div class="seg" role="group" aria-label="Trade target view" data-grp="tt"><button type="button" data-v="reg" aria-pressed="true">Regular season · P{REG[0]}–P21</button><button type="button" data-v="po" aria-pressed="false">Playoffs · P22–P24</button></div>
<div class="segp" data-grp="tt" data-v="reg"><div class="scroll"><table>{TTH}<tbody>{ttreg}</tbody></table></div></div>
<div class="segp" data-grp="tt" data-v="po" hidden><div class="scroll"><table>{TTH}<tbody>{ttpo}</tbody></table></div></div>
<p class="small">Points each player would add to your best daily lineups if he took your stream slot ({html.escape(short(STREAM))}), scaled down for players CBS projects to miss games. Only players at or below your 5th-best player's CBS FP/G ({CAPR:.1f}) are listed, so these are realistic asks rather than stars. <b>Worth to them</b> = regular-season points his manager's lineups would lose without him: a big gain for you next to a low "worth to them" is the best value; 💎 marks players worth more to you than to their manager. <b>Rd · #</b> = where he went in the BBL draft; 💰 <b>late-pick value</b> = drafted in round 7 or later but projecting like a player taken 3+ rounds earlier, so his manager may value him at his draft price. Trade deadline: Thu Feb 25, 11:59 PM ET.</p>
</section>"""
rivsec=f"""<section>
<h2>What rivals will chase</h2>
<div class="seg" role="group" aria-label="Rivals view" data-grp="riv"><button type="button" data-v="now" aria-pressed="true">Next two periods · P{RP[0]}–P{RP[-1]}</button><button type="button" data-v="season" aria-pressed="false">Rest of season</button></div>
<div class="segp" data-grp="riv" data-v="now"><div class="scroll"><table>
<thead><tr><th>Manager</th><th>Slots filled</th><th>Likely drop</th><th>Likely claims · points added</th></tr></thead>
<tbody>
{rivrows}
</tbody></table></div>
{hottxt}
<p class="small">Slots: lineup spots each rival can fill (green 90%+, yellow 80–89%, red under 80%; red = more reason to claim). Likely drop = the player who adds least to their lineups the rest of the season. Claims = free agents that add the most to their P{RP[0]}–P{RP[-1]} lineups. ⚔ = also one of your targets. Tap "more" for their other drops and claims.</p></div>
<div class="segp" data-grp="riv" data-v="season" hidden><div class="scroll"><table>
<thead><tr><th>Manager</th><th>Likely drop</th><th>Best add · rest of regular season</th><th>Next best</th></tr></thead>
<tbody>
{rivseasonrows}
</tbody></table></div>
{shottxt}
<p class="small">Points the free agent adds to that manager's best daily lineups over the rest of the regular season (P{REG[0]}–P21), after dropping their likely drop; playoff gain shown separately. Players on IR aren't counted until they're activated. ⚔ = also one of your top season holds. Your own row is measured against your stream slot ({html.escape(short(STREAM))}).</p></div>
</section>"""


# ---- pickup board (merged waiver wire / best adds / watchlist / breakouts)
BO={}
if os.path.exists('breakout.tsv'):
    for l in open('breakout.tsv'):
        f=l.rstrip('\n').split('|')
        if len(f)>=6: BO[f[0]]=dict(tier=f[1],a3=float(f[2]),base=float(f[3]),own=f[4],note=f[5])
# ---- stash & flip: free agents rivals would value most (claim now, trade later)
# candidates: top-45 FAs by CBS FP/G (DEM, from the rivals loop) + watchlist and breakout free agents
def rivgain(n,t,s2):
    out={}
    for tn in RB:
        r2=dict(RB[tn]); r2[n]=(t,s2); pg={p:ptot(r2,p)-FO[tn][p] for p in PER}
        if not n.endswith(' ·up'): DEMP[n][tn]=pg
        out[tn]=(sum(pg[p] for p in REG),sum(pg[p] for p in PO))
    return out
for n in sorted((set(watch)|set(BO))&set(FA)):
    if n not in DEM and healthy(n): DEM[n]=rivgain(n,*FA[n])
UP={}; UPME={}
for n,bo in BO.items():
    if n in FA and healthy(n) and INFO[n]['best']>0 and bo['a3']>INFO[n]['best']:
        up=(bo['a3']+INFO[n]['best'])/2; k=up/INFO[n]['best']; t,s2=FA[n]; su={x:v*k for x,v in s2.items()}
        nu_=n+' ·up'; UP[n]=rivgain(nu_,t,su); g=gains(nu_,t,su); UPME[n]=(tot(g,REG),tot(g,PO),up)  # distinct name: lineup cache is keyed by player names
def tdn(t): return "TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in t else t
def flip(k,thr):
    rows=[]
    for n,d in DEM.items():
        v=sorted(((x[k],t) for t,x in d.items()),reverse=True)
        u=sorted(((x[k],t) for t,x in UP[n].items()),reverse=True) if n in UP else None
        nw=sum(1 for x in v if x[0]>=thr); nu=sum(1 for x in u if x[0]>=thr) if u else 0
        if not max(nw,nu): continue
        rows.append((max(nw,nu),sum(x[0] for x in (u if nu>nw else v)[:3]),n,v,nw,u,nu))
    rows.sort(key=lambda r:(-r[0],-r[1]))
    return rows[:10]
def fliprow(r,k):
    _,top3,n,v,nw,u,nu=r; mine=tot(GA[n],REG if k==0 else PO)
    who=' · '.join(f'{html.escape(tdn(t))} <b>{g:+,.0f}</b>' for g,t in v[:3] if g>0) or '<span class="muted">nobody yet at his CBS projection</span>'
    if u: who+=f'<div class="small" style="margin-top:3px">🔥 If his breakout holds (~{UPME[n][2]:.0f} FP/G): '+' · '.join(f'{html.escape(tdn(t))} <b>{g:+,.0f}</b>' for g,t in u[:3] if g>0)+'</div>'
    cost=f'<span class="num">{mine:+,.0f}</span>'+(' <span class="tag warn">costs you to hold</span>' if mine<0 else '')
    if n in UPME: cost+=f'<div class="small">{UPME[n][k]:+,.0f} if breakout holds</div>'
    nw_txt=f'<b>{nw}</b> of 9'+(f'<div class="small"><b>{nu}</b> of 9 if breakout holds</div>' if u else '')
    _e=es(n); _hot=(_e and _e[1]>=2) or (n in RT and RT[n][2]>=10)
    bz=(f'<div class="small">{rost(n)}'+(' <span class="tag warn">📈 buzz</span>' if _hot else '')+ten(n)+(' '+dtag(n) if drf(n) else '')+'</div>') if (_e or n in RT or drf(n)) else ''
    return (f'<tr><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span>{wbtn(n)}{bz}</td><td class="num">{INFO[n]["best"]:.1f}</td>'
            f'<td class="num">{nw_txt}</td><td>{peak(n,REG if k==0 else PO)}</td><td>{who}</td><td>{cost}</td></tr>')
FTH='<thead><tr><th>Free agent</th><th>CBS FP/G</th><th>Rivals who want him</th><th>Peak demand</th><th>Most interested · points he adds them</th><th>Your gain if you stash him</th></tr></thead>'
def peak(n,ps):
    d=DEMP.get(n) or {}
    if not d or not ps: return '<span class="muted">—</span>'
    sc={p:sum(max(0,g[p]) for g in d.values()) for p in ps}
    p=max(ps,key=lambda q:sc[q])
    if sc[p]<=0: return '<span class="muted">—</span>'
    k=sum(1 for g in d.values() if g[p]>=20)
    late='<div class="small"><b>after the trade deadline:</b> deal by Thu Feb 25</div>' if p>=20 else ''
    return f'<b>P{p}</b> <span class="tm">{pstart(p).strftime("%b %-d")}</span><div class="small">{k} rival{"s" if k!=1 else ""} gain 20+ that week</div>{late}'
fr=flip(0,100); fp=flip(1,25)
def flipall(k,thr,names):
    rows=[]
    for n in names:
        if n not in DEM: continue
        d=DEM[n]; v=sorted(((x[k],t) for t,x in d.items()),reverse=True)
        u=sorted(((x[k],t) for t,x in UP[n].items()),reverse=True) if n in UP else None
        nw=sum(1 for x in v if x[0]>=thr); nu=sum(1 for x in u if x[0]>=thr) if u else 0
        rows.append((max(nw,nu),sum(x[0] for x in (u if nu>nw else v)[:3]),n,v,nw,u,nu))
    rows.sort(key=lambda r:(-r[0],-r[1]))
    return rows
SPEC=sorted(((set(watch)|set(BO))&set(FA)),key=lambda n:(n not in BO,n))
fs=flipall(0,100,SPEC)
stashsec=f"""<section id="stash">
<h2>Stash &amp; flip: free agents rivals would trade for</h2>
<p class="small" style="margin:0 0 10px">Claim one before they do, then shop him to the managers below. Ranked by how many rivals he'd clearly help, then by how much. Watchlist and breakout players are always checked; for breakout players the 🔥 line shows demand if their recent form holds.</p>
<div class="seg" role="group" aria-label="Stash and flip view" data-grp="stash"><button type="button" data-v="reg" aria-pressed="true">Regular season · P{REG[0]}–P21</button><button type="button" data-v="po" aria-pressed="false">Playoffs · P22–P24</button><button type="button" data-v="wl" aria-pressed="false">Your watchlist &amp; breakouts</button></div>
<div class="segp" data-grp="stash" data-v="reg"><div class="scroll"><table>{FTH}<tbody>{''.join(fliprow(r,0) for r in fr) or '<tr><td colspan="6" class="muted">None right now</td></tr>'}</tbody></table></div></div>
<div class="segp" data-grp="stash" data-v="po" hidden><div class="scroll"><table>{FTH}<tbody>{''.join(fliprow(r,1) for r in fp) or '<tr><td colspan="6" class="muted">None right now</td></tr>'}</tbody></table></div></div>
<div class="segp" data-grp="stash" data-v="wl" hidden><div class="scroll"><table>{FTH}<tbody>{''.join(fliprow(r,0) for r in fs) or '<tr><td colspan="6" class="muted">No watchlist or breakout free agents right now</td></tr>'}</tbody></table></div></div>
<p class="small"><b>Peak demand</b> = the period when rivals gain the most from him (their combined gains that week), so it&#39;s your best window to shop him; the regular-season view looks at P{{REG[0]}}–P21, the playoff view at P22–P24. "Wants him" = he'd add at least 100 points to that manager's best daily lineups over the rest of the regular season (25 for the playoff weeks), after they drop their least useful player. Points shown are what he adds to each manager's lineups. <b>Your gain if you stash him</b> = what he does for you in your stream slot ({html.escape(short(STREAM))}) while you hold him; a negative number means holding him costs you points, so only stash him if a deal is likely soon. Each claim uses one of your 2 waiver adds per period. Trade deadline: Thu Feb 25, 11:59 PM ET. Add/drops are restricted in the playoffs, so playoff flips have to happen before then.</p>
</section>"""
_prog(40,'Finding pickups for each player you could drop',66,8.6)
# ---- 2-for-1 packages (two4one.json, refreshed weekly by two4one.py)
T41=None
if os.path.exists('two4one.json'):
    try: T41=json.load(open('two4one.json',encoding='utf-8'))
    except Exception: T41=None
def t41odds(x):
    return ('<span class="tag ok">likely yes</span>' if x['tr']>=0 else '<span class="tag">fair</span>' if x['tr']>=-120 else '<span class="tag warn">needs a sweetener</span>')
def t41row(x):
    tn=html.escape("TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in x['team'] else x['team'])
    return (f'<tr><td>{" + ".join(html.escape(short(n)) for n in x["give"])}</td>'
            f'<td><b>{html.escape(short(x["X"]))}</b> <span class="nbat" data-t="{x["nt"]}">{x["nt"]}</span> <span class="tm">{x["pos"]}</span>{(" "+dtag(x["X"])) if drf(x["X"]) else ""}</td>'
            f'<td>{tn}</td><td class="num">{x["best"]:.1f}</td><td class="num"><b>{x["mr"]:+,}</b></td><td class="num">{x["mp"]:+,}</td>'
            f'<td class="num">{x["tr"]:+,} / {x["tp"]:+,}<div>{t41odds(x)}</div><div class="small">they drop {html.escape(short(x["drop"]))}</div></td></tr>')
if T41 and TODAY<=dt.date(2027,2,25):
    gv=", ".join(html.escape(short(n)) for n in T41.get('give',[]))
    fl=T41.get('fill') or []
    t41body=(f'<div class="scroll"><table><thead><tr><th>You give</th><th>You get</th><th>From</th><th>CBS FP/G</th><th>You · reg. season</th><th>You · playoffs</th><th>Them · reg / playoffs</th></tr></thead><tbody>'
             +(''.join(t41row(x) for x in T41.get('deals',[])) or '<tr><td colspan="7" class="muted">No realistic 2-for-1 this week</td></tr>')+'</tbody></table></div>'
             +f'<p class="small">Updated {html.escape(T41.get("label",""))} (weekly, Monday nights). Packages pair two of your cheapest players by lineup value ({gv}) for one better rival player. Both sides are modelled with the league scoring and best daily lineups; the other manager drops his weakest player to make room. Only deals that cost him 250 regular-season points or less are shown, so these are realistic asks. <b>Odds:</b> likely yes = he gains in the regular season; fair = he loses up to 120; needs a sweetener = more than that.'
             +(f' The deal also opens a roster spot: the best free agent to fill it is <b>{html.escape(short(fl[0]["n"]))}</b> (+{fl[0]["reg"]} rest of the regular season).' if fl else '')+' Trade deadline: Thu Feb 25, 11:59 PM ET.</p>')
elif TODAY>dt.date(2027,2,25): t41body='<p class="muted">The trade deadline (Thu Feb 25) has passed.</p>'
else: t41body='<p class="muted">The first 2-for-1 report runs Monday night.</p>'
def tgtrow(t):
    tn=html.escape("TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in t['team'] else t['team'])
    pk=t.get('pick'); by=t.get('bestyou')
    chg={'price dropped':'<span class="tag ok">📉 price dropped</span>','price rose':'<span class="tag warn">📈 price rose</span>'}.get(t.get('change',''),'')
    if pk:
        pkt=(f'{" + ".join(html.escape(short(n)) for n in pk["give"])}<div class="small">you <b>{pk["mr"]:+,}</b> / {pk["mp"]:+,} · them {pk["tr"]:+,} / {pk["tp"]:+,}'
             +(f' · they drop {html.escape(short(pk["drop"]))}' if pk.get('drop') else '')+'</div>'+('' if t['realistic'] else '<div class="small"><span class="tag warn">still a big ask</span> (closest to even for them)</div>'))
    else: pkt='<span class="muted">No package from your spare players helps you</span>'
    byt=(f'{" + ".join(html.escape(short(n)) for n in by["give"])}<div class="small">you <b>{by["mr"]:+,}</b> / {by["mp"]:+,} · them {by["tr"]:+,} / {by["tp"]:+,}</div>' if by and by!=pk else '<span class="muted">same</span>')
    return (f'<tr><td><b>{html.escape(short(t["X"]))}</b> <span class="nbat" data-t="{t["nt"]}">{t["nt"]}</span> <span class="tm">{t["pos"]}</span>'
            +(' <span class="tag">★ fixed target</span>' if t.get('fixed') else '')+f' {chg}<div class="small">{tn} · {t["best"]:.1f} CBS FP/G</div></td><td>{pkt}</td><td>{byt}</td></tr>')
tgsec=''
if T41 and T41.get('teams') and TODAY<=dt.date(2027,2,25):
    def _tins(x):
        bits=[]
        if x['open_po']>=2: bits.append(f'{x["open_po"]} of his {x["g_po"]} playoff games land on nights you have an open slot')
        elif x['po']>=80: bits.append(f'{x["g_po"]} playoff games, and they fit around your stars')
        if x['po']<20: bits.append('almost no playoff value: a regular-season piece only')
        if x['b2b']>=13: bits.append(f'{x["b2b"]} back-to-backs (rest risk)')
        return '; '.join(bits)
    trows=''
    for x in T41['teams']:
        mine=', '.join(html.escape(short(n)) for n in x.get('mine',[]))
        trows+=(f'<tr class="tghead"><td colspan="3"><span class="tgrk">#{x["rank"]}</span> <span class="nbat" data-t="{x["t"]}">{x["t"]}</span> '
                f'<b>+{x["reg"]:,}</b> reg. season · <b>{x["po"]:+,}</b> playoffs <span class="tm">for a 35 FP/G player</span>'
                f'<div class="small">{x["g_reg"]} games left ({x["open_reg"]} on your open nights) · {x["g_po"]} in the playoffs ({x["open_po"]} open)'
                +(f' · you already have {mine}' if mine else '')+(f' · {_tins(x)}' if _tins(x) else '')+'</div></td></tr>')
        trows+=''.join(tgtrow(t) for t in x['players']) or '<tr><td colspan="3" class="muted small">No rival player worth 24+ FP/G on this team</td></tr>'
        if x.get('fa'): trows+='<tr><td colspan="3" class="small"><b>Free agents, no trade needed:</b> '+' · '.join(f'{html.escape(short(f["n"]))} <span class="tm">{f["pos"]}</span> +{f["reg"]} reg / {f["po"]:+} playoffs' for f in x['fa'])+'</td></tr>'
    rk=T41.get('team_rank') or []
    rkrows=''.join(f'<tr><td class="num">{x["rank"]}</td><td><span class="nbat" data-t="{x["t"]}">{x["t"]}</span></td><td class="num">{x["reg"]:+,}</td><td class="num">{x["po"]:+,}</td><td class="num">{x["g_reg"]} <span class="tm">({x["open_reg"]} open)</span></td><td class="num">{x["g_po"]} <span class="tm">({x["open_po"]} open)</span></td><td class="num">{x["b2b"]}</td></tr>' for x in rk)
    tgsec=(f'<h3 class="sh">🎯 Target watch · best schedules for you</h3>'
           '<p class="small" style="margin:0 0 8px">Which NBA teams add the most to <b>your</b> lineups: a generic 35 FP/G player from each team is dropped into your roster in place of the stream slot, and the extra points from your best daily lineups are counted. Teams that play on nights you have open slots (and in P22–P24) rise to the top. Under each of the top 5: the rival-owned players worth targeting with a package, and free agents you can just claim. Ranking = regular season + playoffs counted twice.</p>'
           f'<div class="scroll"><table class="tgtab"><thead><tr><th>Team · target</th><th>Best realistic package</th><th>Best for you (if they’d take it)</th></tr></thead><tbody>{trows}</tbody></table></div>'
           +(''.join(tgtrow(t) for t in T41.get('targets',[])) and f'<p class="small"><b>Fixed targets outside the top 5:</b></p><div class="scroll"><table><tbody>{"".join(tgtrow(t) for t in T41.get("targets",[]))}</tbody></table></div>')
           +(f'<details class="rep"><summary>All 30 teams ranked for your schedule</summary><div class="brief"><div class="scroll"><table><thead><tr><th>#</th><th>Team</th><th>Reg. season</th><th>Playoffs</th><th>Games left</th><th>Playoff games</th><th>B2Bs</th></tr></thead><tbody>{rkrows}</tbody></table></div></div></details>' if rk else '')
           +'<p class="small">Packages come from your 8 cheapest players, one or two at a time. "Realistic" = costs the other manager 250 regular-season points or less. 📉 price dropped = this week&#39;s best realistic package gives you 50+ more points, or costs them 75+ fewer, than last week. Updated weekly with the 2-for-1 report.</p>'
           '<style>.tgtab tr.tghead td{background:var(--pobg);border-top:2px solid var(--line);padding-top:12px}.tgrk{font:700 1.1rem var(--display);color:var(--accent);margin-right:4px}</style>')
teamadds=''
if T41 and T41.get('team_rank'):
    _tr=''
    for x in T41['team_rank'][:5]:
        fa=sorted([n for n in FA if INFO[n]['team']==x['t']],key=lambda n:-(tot(GA[n],REG)+tot(GA[n],PO)))[:5]
        _tr+=(f'<tr class="tghead"><td colspan="6"><span class="tgrk">#{x["rank"]}</span> <span class="nbat" data-t="{x["t"]}">{x["t"]}</span> '
              f'<b>+{x["reg"]:,}</b> reg. season · <b>{x["po"]:+,}</b> playoffs <span class="tm">for a 35 FP/G player</span>'
              f'<div class="small">{x["g_reg"]} games left ({x["open_reg"]} on your open nights) · {x["g_po"]} in the playoffs ({x["open_po"]} open) · {x["b2b"]} back-to-backs</div></td></tr>')
        _tr+=''.join(f'<tr><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]}</span>{wbtn(n)}'
                     +('' if healthy(n) else f' <span class="tag bad">injury · {INFO[n]["gp"]:.0f} GP proj</span>')+'</td>'
                     f'<td class="num">{INFO[n]["best"]:.1f}</td><td class="num">{GA[n][PER[0]]:+.0f}</td><td class="num">{tot(GA[n],REG):+.0f}</td><td class="num">{tot(GA[n],PO):+.0f}</td><td class="num"><b>{tot(GA[n],REG)+tot(GA[n],PO):+.0f}</b></td></tr>' for n in fa) \
             or '<tr><td colspan="6" class="muted small">No free agents on this team</td></tr>'
    teamadds=(f'<section id="teamadds"><h2>Best adds by team schedule</h2>'
              f'<p class="small" style="margin:0 0 8px">The 5 NBA teams whose schedules add the most to your lineups (ranked weekly on the Trades tab), with the top 5 free agents on each. Gains assume you drop your stream slot ({html.escape(short(STREAM))}).</p>'
              f'<div class="scroll"><table class="tgtab"><thead><tr><th>Team · free agent</th><th>CBS FP/G</th><th>P{PER[0]} gain</th><th>Rest of reg. season</th><th>Playoffs</th><th>Total</th></tr></thead><tbody>{_tr}</tbody></table></div>'
              '<style>.tgtab tr.tghead td{background:var(--pobg);border-top:2px solid var(--line);padding-top:12px}.tgrk{font:700 1.1rem var(--display);color:var(--accent);margin-right:4px}</style></section>')
t41sec=f'''<section id="twoforone"><h2>2-for-1 packages</h2>{t41body}{tgsec}</section>'''

tradepane=f'''<section class="brief trade-intro"><p style="margin:0"><b>Ways to trade up.</b> <a href="#tfind">Trade finder</a> = 1-for-1 swaps where both teams gain. <a href="#buysell">Buy low · sell high</a> = players whose shooting luck has their value out of line. <a href="#ttargets">Trade targets</a> = players on rival rosters who'd add the most to your lineups. <a href="#stash">Stash &amp; flip</a> = free agents you could claim now because rivals will want them later. <a href="#twoforone">2-for-1 packages</a> = two of your spare pieces for one better player, which also opens a roster spot. Use the switch on each table for regular season or playoffs.</p></section>'''+tradesec+stashsec+t41sec+SEGJS
p0=PER[0]; th0=THIN.get(p0,[]); NX=PER[:3]
NA=NX+[p for p in REG if p not in NX and p>NX[-1]]   # Watchlist: every regular-season period left (NX shown, the rest on "Show all periods")
ros=lambda n: tot(GA[n],REG)+tot(GA[n],PO)
pick=set(sorted(FA,key=lambda n:-ros(n))[:12])|set(sorted([n for n in FA if healthy(n)],key=lambda n:-GA[n][p0])[:5])
pick|={n for n in watch if n in FA and ros(n)>0}|{n for n in BO if n in FA}
# ---- Usage rate (USG%): share of team plays a player uses while on the floor (FGA + 0.44*FTA + TO).
# usg.txt keeps one line per player-game since opening night: date|name|team|min|fga|fta|to|tm_min|tm_fga|tm_fta|tm_to
# Every box_YYYYMMDD.txt in the folder (written nightly) is added once.
USGROWS=[]
if os.path.exists('usg.txt'):
    for l in open('usg.txt',encoding='utf-8'):
        q=l.rstrip('\n').split('|')
        if len(q)==11:
            try: USGROWS.append((q[0],q[1],q[2])+tuple(float(x) for x in q[3:]))
            except ValueError: pass
_ud_dates={r[0] for r in USGROWS}; _new_rows=[]
for _bf in sorted(glob.glob('box_*.txt')):
    _d=os.path.basename(_bf)[4:12]
    if not _d.isdigit() or _d in _ud_dates: continue
    _pl=[]
    for l in open(_bf,encoding='utf-8'):
        q=l.rstrip('\n').split('|')
        if l.startswith('#') or len(q)<16: continue
        try: _pl.append((q[0],q[1],float(q[2] or 0),float(q[5] or 0),float(q[9] or 0),float(q[12] or 0)))
        except ValueError: pass
    _tm={}
    for n_,t_,mi,fga,fta,to in _pl:
        a=_tm.setdefault(t_,[0,0,0,0]); a[0]+=mi; a[1]+=fga; a[2]+=fta; a[3]+=to
    for n_,t_,mi,fga,fta,to in _pl:
        if mi>0: _new_rows.append((_d,n_,t_,mi,fga,fta,to)+tuple(_tm[t_]))
if _new_rows:
    USGROWS+=_new_rows
    with open('usg.txt','a',encoding='utf-8') as _fh:
        for r in _new_rows: _fh.write('|'.join([r[0],r[1],r[2]]+[f'{x:g}' for x in r[3:]])+'\n')
def _usg(rows):
    num=sum((r[4]+0.44*r[5]+r[6])*(r[7]/5) for r in rows); den=sum(r[3]*(r[8]+0.44*r[9]+r[10]) for r in rows)
    return 100*num/den if den else 0
_ug=defaultdict(list)
for r in USGROWS: _ug[nk(r[1])].append(r)
USG={}   # nk(name) -> dict(season, l3, prior, g, min3)
for k,_rws in _ug.items():
    _rws.sort(key=lambda r:r[0])
    l3=_rws[-3:]; pr=_rws[:-3]
    USG[k]=dict(season=_usg(_rws),l3=_usg(l3),prior=_usg(pr) if len(pr)>=3 else None,g=len(_rws),min3=sum(r[3] for r in l3)/len(l3))
def usg(n):
    k=nk(n); return USG.get(k) or USG.get(NKALIAS.get(k,''))
def usgtag(n):
    u=usg(n)
    if not u or u['min3']<12: return ''
    if u['prior'] is not None and u['l3']-u['prior']>=5:
        return f'<span class="tag hot" title="Usage rate: share of his team\'s plays he uses on the floor. Last 3 games {u["l3"]:.0f}% vs {u["prior"]:.0f}% before">📈 usage {u["prior"]:.0f}→{u["l3"]:.0f}%</span>'
    if u['prior'] is not None and u['prior']-u['l3']>=6:
        return f'<span class="tag bad" title="Usage rate fell: last 3 games {u["l3"]:.0f}% vs {u["prior"]:.0f}% before">📉 usage {u["prior"]:.0f}→{u["l3"]:.0f}%</span>'
    if u['season']>=26:
        return f'<span class="tag" title="Usage rate {u["season"]:.0f}% over {u["g"]} game{"s" if u["g"]!=1 else ""} (26%+ is a featured scorer)">USG {u["season"]:.0f}%</span>'
    return ''
def tags(n):
    t=[]
    e=es(n)
    if e: t.append(f'<span class="tag" title="Rostered in {e[0]:.1f}% of ESPN leagues, started in {e[2]:.1f}%">{ES_}{_p(e[0])}% rostered {_a(round(e[1],1))}</span>')
    if n in RT: t.append(f'<span class="tag" title="Rostered across CBS leagues ({RT[n][0]}% last week)">{CB_}{RT[n][1]}% {_a(RT[n][2])}</span>')
    if ten(n): t.append(ten(n))
    if n in FA and drf(n): t.append(dtag(n))
    if n in FA and (e[0]<10 if e else (n in RT and RT[n][1]<30)) and ros(n)>=100: t.append('<span class="tag ok">💎 hidden gem</span>')
    if n in FA and (e[0]>=40 if e else (n in RT and RT[n][1]>=60)) and ros(n)<=0: t.append('<span class="tag bad">🎈 hype trap for you</span>')
    if n in BO: t.append('<span class="tag hot">🚀 breakout</span>' if BO[n]['tier']=='BREAKOUT' else '<span class="tag hot">🔥 heating up</span>')
    if usgtag(n): t.append(usgtag(n))
    if n in watch and n not in FA: t.append('<span class="tag">★ watch</span>')
    k=len(cnt.get(n,[]))
    if k: t.append(f'<span class="tag warn">⚔ {k} rival{"s" if k>1 else ""}</span>')
    if n in FA and th0:
        c=sum(1 for d in th0 if d in G[FA[n][0]])
        if c: t.append(f'<span class="tag ok">covers {c}/{len(th0)} thin days</span>')
    if n in INFO and not healthy(n): t.append(f'<span class="tag bad">injury · {INFO[n]["gp"]:.0f} GP proj</span>')
    return ' '.join(t)
def why(n):
    if n in BO and BO[n]['note']: return html.escape(BO[n]['note'])
    if n in BO: return f'Last 3: {BO[n]["a3"]:.1f} vs {BO[n]["base"]:.1f} projected'
    return 'Best periods: '+bestp(n)
bord=sorted(pick,key=lambda n:-ros(n))
# ---- alternative drop candidates: bottom 5 on the roster (stream slot first), gains recomputed for board players
import json
dc=[n for n in sorted(R,key=lambda n:tot(MV[n],REG)+tot(MV[n],PO)) if n!=STREAM and INFO[n].get('sec')!='I']
DROPS=[STREAM]+dc
IRP=[n for n in R if INFO[n].get('sec')=='I']
IRW={n:{p:ptot({k:v for k,v in R.items() if k!=n},p) for p in PER} for n in IRP}
ALT={}
WLX=[n for n in watch if n in FA and n not in bord]   # watched free agents not on the board
LX=sorted({n for p in PER for _,n in sorted([(GA[m][p],m) for m in FA if healthy(m)],reverse=True)[:3]}-set(bord)-set(WLX))  # best one-week streams for the Overview ledger
GD={}
for d in DROPS:
    bdp={p:ptot({k:v for k,v in R.items() if k!=d},p) for p in PER}
    if d==STREAM: g=GA
    else:
        bd={k:v for k,v in R.items() if k!=d}; bp={p:ptot(bd,p) for p in PER}; md={p:full[p]-bp[p] for p in PER}
        g={}
        for n in bord+WLX+LX:
            t,s2=FA[n]; r=dict(bd); r[n]=(t,s2); f=min(1.0,INFO[n]['gp']/78.5)
            g[n]={p:(ptot(r,p)-bp[p]-md[p])*f for p in PER}
    GD[d]=g
    ALT[d]={'v':round(tot(MV[d],REG)),'vp':round(tot(MV[d],PO)),'g':[[round(g[n][p]) for p in NA]+[round(tot(g[n],REG)),round(tot(g[n],PO))] for n in bord],'ir':[[round(bdp[p]-IRW[n][p]) for p in NA]+[round(sum(bdp[p]-IRW[n][p] for p in REG)),round(sum(bdp[p]-IRW[n][p] for p in PO))] for n in IRP]}
    ALT[d]['w']={n:[round(g[n][p]) for p in NA]+[round(tot(g[n],REG)),round(tot(g[n],PO))] for n in bord+WLX if n in watch and n in g}
    if d==STREAM: gt=GT
    else:
        gt={}
        for n in WT:
            r=dict(bd); r[n]=SV[n]; f=min(1.0,INFO[n]['gp']/78.5)
            gt[n]={p:(ptot(r,p)-bp[p]-md[p])*f for p in PER}
    ALT[d]['w'].update({n:[round(gt[n][p]) for p in NA]+[round(tot(gt[n],REG)),round(tot(gt[n],PO))] for n in WT})
dropsel='<label class="dropsel">If I drop <select id="dropsel">'+''.join(f'<option value="{i}">{html.escape(short(d))} ({INFO[d]["pos"]} · worth {ALT[d]["v"]} reg. season + {ALT[d]["vp"]} playoffs{", stream slot" if d==STREAM else ""}{", holding" if d in KEEP else ""})</option>' for i,d in enumerate(DROPS))+'</select></label>'+'<p class="small" style="margin:4px 0 0"><b>Worth</b> = points your lineups would lose without him, after your bench fills his slot. It isn&#39;t his total points: a low number means he&#39;s easy to replace, so he costs you the least to drop.</p>'
# Overview ledger: best adds / watchlist per period for every "If I drop" choice
LADD=[]
for d in DROPS:
    g=GD[d]; cand=[n for n in g if n in FA and healthy(n)]
    per={}
    for p in PER:
        top=sorted([(g[n][p],n) for n in cand],reverse=True)[:3]
        wl=sorted([(g[n][p],n) for n in watch if n in g and g[n][p]>=1],reverse=True)
        per[p]=[[short(n),INFO[n]['pos']+' · '+INFO[n]['team'],round(v)] for v,n in top if v>=5]+[None]+[[short(n),INFO[n]['pos']+' · '+INFO[n]['team'],round(v)] for v,n in wl]
    LADD.append(per)
BOG=[{n:round(tot(GD[d][n],REG)) for n in BO if n in GD[d]} for d in DROPS]
dropsel_ov=dropsel.replace('id="dropsel"','id="dropsel-ov"').split('<p class="small"')[0]
# ---- Period by period: finished periods (results.txt, your CBS schedule: P|opponent|Won/Lost/Tied|you|them|record),
# hidden until "Show finished periods"; and the watchlist cells (wlbox), one line each until "Expand all"
PAST=[]
if os.path.exists('results.txt'):
    for l in open('results.txt',encoding='utf-8'):
        f=l.rstrip('\n').split('|')
        if len(f)==6 and f[0].isdigit() and int(f[0])<CUR:
            try: PAST.append((int(f[0]),f[1],f[2],float(f[3]),float(f[4]),f[5]))
            except ValueError: pass
def _pastrow(x):
    p,o,res,me,them,rec=x; a,b=(dt.date(2026,10,20),dt.date(2026,10,25)) if p==1 else (dt.date(2026,10,26)+dt.timedelta(days=7*(p-2)),dt.date(2026,10,26)+dt.timedelta(days=7*(p-2)+6))
    mx=done(MEN,p); cls={'Won':'good','Lost':'bad'}.get(res,'even')
    bench=(f'Your best possible lineups scored <b>{mx:,.0f}</b>: <b>{mx-me:,.0f}</b> points left on your bench.' if mx>me else
           (f'Your best possible lineups scored <b>{mx:,.0f}</b>.' if mx else ''))
    return (f'<tr class="pastp"><td class="pn">{p}<span class="nowtag pasttag">FINAL</span></td><td>{a.strftime("%b %-d")} – {b.strftime("%b %-d")}<div class="opp">{html.escape(o)}</div></td>'
            f'<td><span class="vpill {cls}">{res.upper()}</span> <b class="pastsc">{me:,.0f}–{them:,.0f}</b><div class="small">{"by" if res!="Tied" else "at"} {abs(me-them):,.0f} · record {html.escape(rec)}</div></td>'
            f'<td colspan="4" class="small">{bench}</td></tr>')
PASTROWS=''.join(_pastrow(x) for x in sorted(PAST))
WLALL=('<div class="ledbtns">'+(f'<button type="button" id="pastbtn" class="ledbtn" data-o="0">▸ Show finished period{"s" if len(PAST)>1 else ""} ({len(PAST)})</button>' if PAST else '')
 +'<button type="button" id="wlall" class="ledbtn wlall" data-o="0">★ Expand all watchlists</button></div>'
 +r'''<script>(function(){var K="bbl-wlopen",KP="bbl-past";
function btns(){return [].slice.call(document.querySelectorAll(".wlall"))}
function all(){return [].slice.call(document.querySelectorAll(".ledger details.wl"))}
function set(o,save){all().forEach(function(d){d.open=o});btns().forEach(function(b){b.dataset.o=o?"1":"0";b.textContent=(o?"★ Collapse all":"★ Expand all")+(b.classList.contains("wlallth")?"":" watchlists")});if(save)try{localStorage.setItem(K,o?"1":"0")}catch(e){}}
function past(o,save){var t=document.getElementById("pastrows"),b=document.getElementById("pastbtn");if(!t||!b)return;t.hidden=!o;b.dataset.o=o?"1":"0";b.textContent=b.textContent.replace(/^[▸▾] (Show|Hide)/,o?"▾ Hide":"▸ Show");if(save)try{localStorage.setItem(KP,o?"1":"0")}catch(e){}}
document.addEventListener("click",function(e){var b=e.target.closest(".wlall");if(b){e.stopPropagation();e.preventDefault();set(b.dataset.o!=="1",true);return}
if(e.target.closest("#pastbtn"))past(document.getElementById("pastbtn").dataset.o!=="1",true)},true);   // capture: the header one sits inside a sort button
document.addEventListener("DOMContentLoaded",function(){try{if(localStorage.getItem(K)==="1")set(true);if(localStorage.getItem(KP)==="1")past(true)}catch(e){}});
document.addEventListener("bbldrop",function(){setTimeout(function(){if(btns()[0]&&btns()[0].dataset.o==="1")all().forEach(function(d){d.open=true})},0)})})();</script>''')
dropsel_tp=dropsel_ov.replace('id="dropsel-ov"','id="dropsel-tp"')
dropsel_bo=dropsel_ov.replace('id="dropsel-ov"','id="dropsel-bo"')
OVJS='<script>(function(){var L='+json.dumps(LADD)+';var B='+json.dumps(BOG)+';var bs=document.getElementById("dropsel"),SS=[].slice.call(document.querySelectorAll("#dropsel-ov,#dropsel-tp,#dropsel-bo"));SS.forEach(function(x){x.addEventListener("change",function(){if(bs){bs.value=x.value;bs.dispatchEvent(new Event("change"))}})});function e(t){var d=document.createElement("div");d.textContent=t;return d.innerHTML}function r(i){var a=L[i];if(!a)return;SS.forEach(function(x){x.value=String(i)});var bg=B[i]||{};[].forEach.call(document.querySelectorAll("td.bog[data-n]"),function(c){var v=bg[c.dataset.n];if(v!=null)c.innerHTML="<b>"+(v>=0?"+":"")+v+"</b>"});[].forEach.call(document.querySelectorAll(".ladd[data-p]"),function(c){var x=a[c.dataset.p];if(!x)return;var k=x.indexOf(null),top=x.slice(0,k),wl=x.slice(k+1);var h=top.length?top.map(function(y){var q=y[1].split(" · ");return e(y[0])+" "+(q.length>1?\'<span class="nbat" data-t="\'+e(q[1])+\'">\'+e(q[1])+\'</span> <span class="tm">\'+e(q[0])+"</span>":\'<span class="tm">\'+e(y[1])+"</span>")+" <b>+"+y[2]+"</b>"}).join("<br>"):\'<span class="muted">No add beats \'+e(document.querySelector("#dropsel option:checked").textContent.split(" (")[0])+"</span>";var od=c.querySelector("details.wl"),op=od&&od.open;h+=wl.length?\'<details class="wl"><summary><span class="wlh">★ Watchlist · \'+wl.length+"</span> best: "+e(wl[0][0])+" <b>+"+wl[0][2]+"</b></summary>"+wl.map(function(y){var q=y[1].split(" · ");return "<div>"+e(y[0])+" "+(q.length>1?\'<span class="nbat sm" data-t="\'+e(q[1])+\'">\'+e(q[1])+\'</span> <span class="tm">\'+e(q[0])+"</span>":\'<span class="tm">\'+e(y[1])+"</span>")+" <b>+"+y[2]+"</b></div>"}).join("")+"</details>":\'<div class="wl"><span class="wlh">Watchlist</span><div class="muted">No gain this period</div></div>\';c.innerHTML=h;if(op){var nd=c.querySelector("details.wl");if(nd)nd.open=true}})}document.addEventListener("bbldrop",function(ev){r(ev.detail.i)});if(window.__bbldrop)r(window.__bbldrop.i)})();</script>'

DROPJS='<script>(function(){var D='+json.dumps([ALT[d] for d in DROPS])+',N='+json.dumps([short(d) for d in DROPS])+';var sel=document.getElementById("dropsel");if(!sel)return;var tb=document.getElementById("boardbody");function f(v){return(v>=0?"+":"")+v}function go(){var a=D[+sel.value];var rows=[].slice.call(tb.querySelectorAll("tr[data-k]"));rows.forEach(function(tr){var g=a.g[+tr.dataset.k],td=tr.children;for(var i=0;i<g.length;i++){var c=td[2+i];c.textContent=f(g[i]);if(i<g.length-2)c.classList.toggle("hi",g[i]>=20)}tr.dataset.s=g[g.length-2]+g[g.length-1]});rows.sort(function(x,y){return y.dataset.s-x.dataset.s}).forEach(function(r){tb.insertBefore(r,tb.querySelector("tr.unr"))});[].forEach.call(document.querySelectorAll("#irbody tr[data-ir]"),function(tr){var g=a.ir[+tr.dataset.ir],td=tr.children;for(var i=0;i<g.length;i++){var c=td[2+i];c.textContent=f(g[i]);if(i<g.length-2)c.classList.toggle("hi",g[i]>=20)}});if(window.bblSort)window.bblSort();[].forEach.call(document.querySelectorAll(".dropname"),function(e){e.textContent=N[+sel.value]});try{localStorage.setItem("bbldrop",sel.value)}catch(e){}window.__bbldrop={w:a.w,name:N[+sel.value],i:+sel.value};document.dispatchEvent(new CustomEvent("bbldrop",{detail:window.__bbldrop}))}sel.addEventListener("change",go);try{var v=localStorage.getItem("bbldrop");if(v!==null&&D[+v]){sel.value=v;go()}}catch(e){}})();</script>'
brows='\n'.join(f'<tr data-k="{k}"><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span>{wbtn(n)}<div class="tags">{tags(n)}</div></td><td class="num">{INFO[n]["best"]:.1f}</td>{''.join(f'<td class="num{" hi" if GA[n][p]>=20 else ""}{" wx" if p not in NX else ""}">{GA[n][p]:+.0f}</td>' for p in NA)}<td class="num">{tot(GA[n],REG):+.0f}</td><td class="num">{tot(GA[n],PO):+.0f}</td><td class="why">{why(n)}</td></tr>' for k,n in enumerate(bord))
unr=[n for n in BO if n not in INFO and BO[n]['own'] in ('FA?','FA')]
if unr: brows+='\n'+'\n'.join(f'<tr class="unr"><td><b>{html.escape(short(n))}</b>'+(lambda ex:f' <span class="tm">{ex[1]} · {ex[0]}</span>' if ex else '')(next(((t,ps) for nn,t,ps,_ in EXTRA if nn==n),None))+f' <span class="tm">deep bench on CBS</span><div class="tags">{tags(n)}</div></td><td class="num">{BO[n]["base"]:.1f}</td>{'<td class="num">—</td>'*len(NX)}{'<td class="num wx">—</td>'*(len(NA)-len(NX))}<td class="num">—</td><td class="num">—</td><td class="why">{why(n)}</td></tr>' for n in unr)
rivbo=[n for n in BO if BO[n]['own'].startswith('TAKEN')]
rbtxt=('<p class="small"><b>Rival players breaking out:</b> '+', '.join(f'{html.escape(short(n))} ({html.escape(BO[n]["own"][6:])}, {BO[n]["a3"]:.1f} last 3)' for n in rivbo)+'</p>') if rivbo else ''
bsum=open('breakout_summary.html').read() if os.path.exists('breakout_summary.html') and BO else ''
SORTJS="""<script>(function(){var h=document.getElementById('boardhead'),tb=document.getElementById('boardbody');if(!h||!tb)return;var ths=[].slice.call(h.querySelectorAll('th')),col=-1,dir=-1;
function val(tr,i){var t=tr.children[i].textContent.trim();if(i===0)return t.toLowerCase();var v=parseFloat(t.replace('+',''));return isNaN(v)?-1e9:v}
function apply(){if(col<0)return;var rows=[].slice.call(tb.querySelectorAll('tr'));rows.sort(function(a,b){var x=val(a,col),y=val(b,col);if(x===-1e9)return 1;if(y===-1e9)return -1;return (x<y?-1:x>y?1:0)*dir});rows.forEach(function(r){tb.appendChild(r)});
ths.forEach(function(th,i){th.setAttribute('aria-sort',i===col?(dir>0?'ascending':'descending'):'none');var a=th.querySelector('.arr');if(a)a.textContent=i===col?(dir>0?' ▲':' ▼'):' ↕'})}
window.bblSort=apply;
ths.forEach(function(th,i){if(i>__LASTSORT__)return;var b=document.createElement('button');b.type='button';b.className='sortbtn';b.innerHTML=th.innerHTML+'<span class="arr"> ↕</span>';th.innerHTML='';th.appendChild(b);b.addEventListener('click',function(){if(col===i)dir=-dir;else{col=i;dir=i===0?1:-1}apply()})});})();</script>"""
def irrow(k,n):
    g=ALT[STREAM]['ir'][k]
    when=f'back ~{out[n].strftime("%b %-d")}' if n in out and out[n]>TODAY else 'on IR'
    return f'<tr data-ir="{k}" class="irrow"><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span><div class="tags"><span class="tag bad">IR · {when}</span></div></td><td class="num">{INFO[n]["best"]:.1f}</td>'+''.join(f'<td class="num{" hi" if v>=20 else ""}{" wx" if i>=len(NX) else ""}">{v:+d}</td>' for i,v in enumerate(g[:-2]))+f'<td class="num">{g[-2]:+d}</td><td class="num">{g[-1]:+d}</td><td class="why">Activate him from IR and drop <span class="dropname">{html.escape(short(STREAM))}</span>. Zero until he&#39;s healthy.</td></tr>'
irbody=('<tbody id="irbody"><tr class="irhead"><td colspan="'+str(len(NA)+5)+'">Your IR · if you activate him and drop the selected player</td></tr>'+''.join(irrow(k,n) for k,n in enumerate(IRP))+'</tbody>') if IRP else ''
boardsec=f"""<section id="xbo" class="xwrap">
<h2>Best adds <button type="button" class="xper" data-x="xbo" data-l0="Show all periods ▸" data-l1="◂ Next 3 periods" aria-pressed="false" title="Show every regular-season period left">Show all periods ▸</button></h2>
{dropsel}
{('<div class="brief"><p class="small" style="margin:0 0 6px">🚀 Breakout alerts'+(' · '+html.escape(open('breakout_label.txt').read().strip()) if os.path.exists('breakout_label.txt') else '')+' · full list in Breakout alerts above</p>'+bsum+'</div>') if bsum else ''}
<div class="scroll"><table>
<thead id="boardhead"><tr><th>Player · why he's here</th><th>CBS FP/G</th>{''.join(f'<th{" class=wx" if p not in NX else ""}>P{p} gain</th>' for p in NA)}<th>Rest of reg. season</th><th>Playoffs</th><th>Notes</th></tr></thead>
{irbody}
{('<tbody><tr class="irhead"><td colspan="'+str(len(NA)+5)+'">Free agents</td></tr></tbody>') if irbody else ''}
<tbody id="boardbody" class="cap">
{brows}
</tbody></table></div>
<style>#boardbody.cap>tr:nth-child(n+16){{display:none}}.showall{{margin-top:10px;font:600 .9rem var(--body);color:var(--accent);background:none;padding:8px 12px;border:1px solid var(--line);border-radius:999px;cursor:pointer}}</style>
{(f'<button type="button" class="showall" onclick="var b=document.getElementById(&#39;boardbody&#39;),c=b.classList.toggle(&#39;cap&#39;);this.textContent=c?&#39;Show all {brows.count("<tr")} free agents&#39;:&#39;Show the top 15&#39;">Show all {brows.count("<tr")} free agents</button>') if brows.count("<tr")>15 else ''}
<p class="small">The top 15 for the current sort and "If I drop" pick; Show all for the rest. Every free agent worth a look, in one list, ranked by points added if claimed for <span class="dropname">{html.escape(short(STREAM))}</span> and held. Use "If I drop" to compare against any active player on your roster (IR players aren't listed: dropping them opens an IR slot, not a lineup spot; see Watchlist → Your IR), and tap any column header to sort (tap again to flip the order). P gains are the points he'd add as a one-week pickup in this period and the next two (green = +20 or more, a strong stream; a negative number means he'd score less than <span class="dropname">{html.escape(short(STREAM))}</span> would that week). Tags show why he's here: 🚀/🔥 hot streak (last 3 games vs his projection), ★ your watchlist, ⚔ rivals who also want him, thin days he covers this period (P{p0}), injury risk.</p>
{rbtxt}{tk}
</section>"""+DROPJS+SORTJS.replace('__LASTSORT__',str(len(NA)+3))
# moves to consider (top 3, used on Today tab and in the email)
MV3=[]
def wpline(n,g):
    m=next((m for m in MU if m['p']==p0),None)
    if not m: return ''
    sdd=0.11*math.sqrt(m['mine']**2+m['opp_p']**2) or 1
    w2=0.5*(1+math.erf((m['mine']+g-m['opp_p'])/(sdd*math.sqrt(2))))
    return f', P{p0} win odds {m["wp"]*100:.0f}% → {w2*100:.0f}%'
hp=[n for n in FA if healthy(n)]
if hp:
    a=max(hp,key=lambda n:GA[n][p0])
    if GA[a][p0]>=5:
        c=sum(1 for d in th0 if d in G[FA[a][0]]); k=len(cnt.get(a,[]))
        MV3.append(('This week',a,f'+{GA[a][p0]:.0f} in P{p0} over your stream slot ({short(STREAM)}){wpline(a,GA[a][p0])}'+(f'; covers {c} of your {len(th0)} thin days' if c else '')+(f'; {k} rivals want him' if k else '')))
    else:
        MV3.append(('This week',STREAM,f'your stream slot: no pickup beats keeping him in P{p0} (best: {short(a)} {GA[a][p0]:+.0f}), so hold'))
    b=max([n for n in hp if n not in [x[1] for x in MV3]],key=ros)
    MV3.append(('Long-term hold',b,f'+{tot(GA[b],REG):.0f} rest of season, {tot(GA[b],PO):+.0f} playoffs'))
bos=sorted([n for n in BO if n in FA and n not in [x[1] for x in MV3]],key=lambda n:(BO[n]['tier']!='BREAKOUT',n not in watch,-(BO[n]['a3']-BO[n]['base'])))
if bos:
    n=bos[0]; MV3.append(('Hot streak',n,f'{"🚀" if BO[n]["tier"]=="BREAKOUT" else "🔥"} {BO[n]["a3"]:.1f} pts over his last 3 vs {BO[n]["base"]:.1f} projected'+(' · watchlist' if n in watch else '')+(f'. {BO[n]["note"]}' if BO[n]['note'] else '')))
def mvname(n): return f'{short(n)} ({INFO[n]["pos"]} · {INFO[n]["team"]})' if n in INFO else n
movesli=''.join(f'<li><b>{k}: {html.escape(mvname(n))}</b> — {html.escape(t)}</li>' for k,n,t in MV3)
open('moves_email.html','w').write('<ul style="margin:0;padding-left:18px">'+''.join(f'<li style="margin:3px 0"><b>{k}: {html.escape(mvname(n))}</b> — {html.escape(t)}</li>' for k,n,t in MV3)+'</ul>')
open('moves.txt','w').write(''.join(f'- {k}: {mvname(n)} — {t}\n' for k,n,t in MV3))
movessec=f'<section class="brief"><h2>Moves to consider</h2><ul>{movesli}</ul><p class="small">Full list on the Waivers tab. Gains assume you drop your stream slot ({html.escape(short(STREAM))}).</p></section>' if MV3 else ''
def lab(w): return 'favored' if w>=0.6 else ('underdog' if w<=0.4 else 'toss-up')
def vs(m): return ('vs ' if m['home'] else 'at ')+m['opp']
ins=[]
if MU:
    first=[]
    for m in MU[:4]:
        t=f"<li><b>P{m['p']} {html.escape(vs(m))}: {m['wp']*100:.0f}%, {lab(m['wp'])}.</b> Projected {m['mine']:,.0f}–{m['opp_p']:,.0f}"
        if m['slot']<=-2 and m['opp_p']>m['mine']: t+=", mainly because of their schedule edge"
        elif m['slot']>=2 and m['mine']>m['opp_p']: t+=", helped by your schedule edge"
        t+='.'
        if m['add']: t+=f" Adding {html.escape(m['add'][0])} moves you to {m['add'][2]*100:.0f}%."
        first.append(t+'</li>')
    ins.append('<p><b>The next few weeks</b></p><ul>'+''.join(first)+'</ul>')
    tough=sorted(MU,key=lambda m:m['wp'])[:4]
    bestm=max(MU,key=lambda m:m['wp'])
    swing=max([m for m in MU if m['add']],key=lambda m:m['add'][2]-m['wp'],default=None)
    rec=sum(m['wp'] for m in MU)
    played=CUR-1
    bl=[f"<li><b>Toughest weeks:</b> "+', '.join(f"P{m['p']} {html.escape(vs(m))} ({m['wp']*100:.0f}%)" for m in tough)+".</li>",
        f"<li><b>Best week:</b> P{bestm['p']} {html.escape(vs(bestm))} ({bestm['wp']*100:.0f}%).</li>"]
    if swing: bl.append(f"<li><b>Where a pickup helps most:</b> P{swing['p']} {html.escape(vs(swing))}, where {html.escape(swing['add'][0])} moves you from {swing['wp']*100:.0f}% to {swing['add'][2]*100:.0f}%.</li>")
    bl.append(f"<li><b>Projected record:</b> about {rec:.0f}–{len(MU)-rec:.0f} over the {len(MU)} remaining regular-season weeks{' (not counting weeks already played)' if played>0 else ''}.</li>")
    ins.append('<ul>'+''.join(bl)+'</ul>')
    ins.append('<p class="small"><b>How the odds work:</b> they compare your projected lineup totals against your opponent\'s current roster, allowing for normal week-to-week swings. They don\'t account for injuries, trades or hot streaks. They refresh every night, so they get sharper as rosters change.</p>')
insights=('<div class="insights"><h3>Matchup outlook</h3>'+''.join(ins)+'</div>') if ins else ''
_prog(66,'Building the period table and matchups',66,0.2)
# ---- matchup graphics tab
def lg(team,sz):
    k=next((t for t in LOGO if t==team or (team=='TINOLA' and 'ɪɴᴏʟᴀ' in t)),None)
    return f'<img src="{LOGO[k]}" width="{sz}" height="{sz}" alt="" class="mlogo">' if k else f'<span class="mlogo ph" style="width:{sz}px;height:{sz}px"></span>'
def dname(t): return "TINOLA JO'CHIĆK" if t=='TINOLA' else t
def edge(m):
    d=(m['mine']-m['opp_p'])/max(1,(m['mine']+m['opp_p'])/2)
    a=abs(d); lvl='EVEN' if a<0.02 else 'SLIGHT' if a<0.06 else 'MODERATE' if a<0.12 else 'EDGE'
    return d,lvl
def bar(m,big):
    d,lvl=edge(m); w=min(1,abs(d)/0.2)*100
    fill=f'<span class="fill {"me" if d>0 else "them"}" style="width:{max(w,4 if lvl!="EVEN" else 0):.0f}%"></span>'
    left=fill if d>0 else ''; right=fill if d<0 else ''
    sc=''.join(f'<span class="{"on" if (lvl==x and ((d>0)==(i==0))) else ""}">{x}</span>' for i,x in [(0,'EDGE'),(0,'MODERATE'),(0,'SLIGHT')])
    sc2=''.join(f'<span class="{"on" if (lvl==x and d<0) else ""}">{x}</span>' for x in ['SLIGHT','MODERATE','EDGE'])
    scale=f'<div class="mscale"><div>{sc}</div><div>{sc2}</div></div>' if big else ''
    return f'<div class="mbar"><div class="half l">{left}</div><span class="ev{" on" if lvl=="EVEN" else ""}">EVEN</span><div class="half r">{right}</div></div>{scale}'
def oc(m): return 'good' if m['wp']>=0.6 else ('bad' if m['wp']<=0.4 else 'even')
def verdict(m):
    o=oc(m); return f'<span class="vpill {o}">{"▲ FAVORED" if o=="good" else ("▼ UNDERDOG" if o=="bad" else "◆ TOSS-UP")} · {m["wp"]*100:.0f}%</span>'
def mcard(m,big,mid=False):
    d,lvl=edge(m); me_w=m['mine']>=m['opp_p']
    sz=64 if big else (48 if mid else 34)
    wcls='better' if m['wp']>=0.6 else ('worse' if m['wp']<=0.4 else 'even')
    extra=''
    if big:
        extra=f'<div class="mfoot">Slots {"+" if m["slot"]>=0 else ""}{m["slot"]} vs them'+(f' · adding {html.escape(m["add"][0])} → {m["add"][2]*100:.0f}%' if m['add'] else '')+'</div>'
    else:
        extra=f'<div class="mfoot">{lvl.title() if lvl!="EVEN" else "Even"}{" you" if d>0 and lvl!="EVEN" else (" them" if lvl!="EVEN" else "")}</div>'
    return f"""<div class="mcard o-{oc(m)}{' big' if big else ''}{' mid' if mid else ''}{' curcard' if m['p']==CUR else ''}"><div class="vrow">{verdict(m)}</div><div class="mhead">{'<span class="nowtag">NOW</span> ' if m['p']==CUR else ''}P{m['p']} · {pstart(m['p']).strftime('%b %-d')} – {pend(m['p']).strftime('%b %-d')} · {'home' if m['home'] else 'away'}</div>
<div class="mrow"><div class="mteam">{lg(ME,sz)}<b>{html.escape(MEDISP)}</b></div><div class="msc {'win' if me_w else 'lose'}">{m['mine']:,.0f}</div>
<div class="mmid">{bar(m,big)}</div>
<div class="msc {'win' if not me_w else 'lose'}">{m['opp_p']:,.0f}</div><div class="mteam">{lg(m['opp'],sz)}<b>{html.escape(dname(m['opp']))}</b></div></div>{extra}</div>"""
def mini(m):
    d,lvl=edge(m); me_w=m['mine']>=m['opp_p']
    return f'<div class="mini o-{oc(m)}">{verdict(m)}<div class="mini-s"><span class="{"w" if me_w else "l"}">{m["mine"]:,.0f}</span>{lg(ME,18)}<span class="vs">vs</span>{lg(m["opp"],18)}<span class="{"w" if not me_w else "l"}">{m["opp_p"]:,.0f}</span></div>{bar(m,False)}<div class="mini-l">{lvl.title() if lvl!="EVEN" else "Even"}{" you" if d>0 and lvl!="EVEN" else (" them" if lvl!="EVEN" else "")}</div></div>'
MUP={m['p']:m for m in MU}
rows=[re.sub(r'@@MINI(\d+)@@',lambda x: mini(MUP[int(x.group(1))]) if int(x.group(1)) in MUP else '<span class="muted">—</span>',r) for r in rows]
if MU:
    h2h_pane='<section><div class="mgrid">'+''.join(mcard(m,False) for m in MU)+'</div><p class="small">Projected totals = your best legal daily lineups vs your opponent\'s current roster, in BBL scoring with slot bonuses. They refresh nightly, so later weeks will shift as rosters change. CBS\'s own preview uses its own projections and usually shows lower totals.</p></section>'
else: h2h_pane='<p class="muted">No regular-season matchups left.</p>'
# ---- league news (news.txt: ISO|source|text|athletes), matched to owners
NEWS={'mine':[],'opp':[],'watch':[],'rival':[]}
if os.path.exists('news.txt'):
    cut=dt.datetime.utcnow()-dt.timedelta(hours=48)
    on=OPP[CUR-1].lstrip('@') if CUR<=21 else ''
    names=sorted(INFO,key=len,reverse=True)
    for l in open('news.txt'):
        f=l.rstrip('\n').split('|')
        if len(f)<3: continue
        try: when=dt.datetime.fromisoformat(f[0])
        except ValueError: continue
        if when<cut: continue
        tags=[a for a in (f[3].split(',') if len(f)>3 else []) if a in INFO]
        tags+=[n for n in names if n in f[2] and n not in tags]
        for n in tags:
            o=INFO[n]['own']
            if o=='MINE': g='mine'
            elif o.startswith('TAKEN:') and (o[6:]==on or (on=='TINOLA' and 'ɪɴᴏʟᴀ' in o)): g='opp'
            elif n in watch and o=='FA': g='watch'
            elif o.startswith('TAKEN:'): g='rival'
            else: continue
            NEWS[g].append((when,n,f[1],f[2]))
INJ=re.compile(r"injur|(?:is|be|was|ruled|remains?|will miss|sit) out|out (?:for|with|indefinitely)|miss(?:es|ing)? |torn|tear|achilles|sprain|strain|knee|ankle|hamstring|calf|foot|wrist|shoulder|back spasm|concussion|questionable|doubtful|day-to-day|surgery|limp|timetable|ruled out|mri|fracture|illness|sidelined|reevaluat|re-evaluat",re.I)
SER=re.compile(r"torn|tear|achilles|fracture|surgery|season-ending|out for the season|indefinitely|weeks|months|no timetable|without (a )?timetable",re.I)
def sev(txt,n=None):
    if n:  # only sentences that mention this player
        ln=n.split()[-1] if n.split()[-1] not in ('Jr.','Sr.','II','III','IV') else n.split()[-2]
        txt=' '.join(x for x in re.split(r'(?<=[.!?—])\s+',txt) if ln in x)
    return 2 if INJ.search(txt) and SER.search(txt) else (1 if INJ.search(txt) else 0)
def nli(it,email=False):
    when,n,src,txt=it; o=INFO[n]['own']; ow='yours' if o=='MINE' else (o[6:] if o.startswith('TAKEN:') else 'FA')
    loc=(when-dt.timedelta(hours=6)).strftime('%a %-I:%M %p')
    sv=sev(txt,n)
    mine=o=='MINE'
    if email:
        if sv and mine:
            badge='<b style="color:#991b1b;font-size:15px">🚑 YOUR PLAYER · '+('SERIOUS INJURY' if sv==2 else 'INJURY')+':</b> '
            st='style="margin:8px 0;padding:6px 8px;border:2px solid #991b1b"'
        else:
            badge={2:'<b style="color:#991b1b">🚑 SERIOUS INJURY:</b> ',1:'<b style="color:#dc2626">🚑 INJURY:</b> '}.get(sv,'')
            st='style="margin:5px 0"'
        own_html=f'<b style="color:#c2410c">★ YOURS</b>' if mine else f'<span style="color:#667085;font-size:12px">{html.escape(ow)}</span>'
        return f'<li {st}>{badge}<b>{html.escape(short(n))}</b> {own_html} — {html.escape(txt)} <span style="color:#667085;font-size:12px">· {html.escape(src)}, {loc}</span></li>'
    if sv and mine:
        badge='<span class="ibadge mine">🚑 Your player · '+('serious injury' if sv==2 else 'injury')+'</span> '
        st='class="inj mine"'
    else:
        badge={2:'<span class="ibadge sev">🚑 Serious injury</span> ',1:'<span class="ibadge">🚑 Injury</span> '}.get(sv,'')
        st=f'class="{"inj" if sv else ""}"'
    own_html='<span class="yours">★ Yours</span>' if mine else f'<span class="tm">{html.escape(ow)}</span>'
    return f'<li {st}>{badge}<b>{html.escape(short(n))}</b> {own_html} — {html.escape(txt)} <span class="small">· {html.escape(src)}, {loc}</span></li>'
NG=[('mine','Your team'),('opp','Your opponent ('+html.escape(OPP[CUR-1].lstrip('@') if CUR<=21 else '')+')'),('watch','Your watchlist'),('rival','Other managers')]
for k in NEWS: NEWS[k].sort(key=lambda it:(-sev(it[3],it[1]),-it[0].timestamp()))
MYINJ=sorted({short(n) for _,n,_,t in NEWS['mine'] if sev(t,n)})
# on the page each story is listed once, in its first group (yours, opponent, watchlist, other managers), with every
# player it mentions; NEWS (one entry per player) still feeds the email
STORY={}
for k,_ in NG:
    for when,n,src,txt in NEWS[k]:
        s=STORY.setdefault((when,src,txt),(k,[]))
        if n not in s[1]: s[1].append(n)
NEWSP={k:sorted([(w,s,t,ns) for (w,s,t),(g,ns) in STORY.items() if g==k],key=lambda it:(-max(sev(it[2],n) for n in it[3]),-it[0].timestamp())) for k,_ in NG}
def nlis(it):
    when,src,txt,ns=it
    loc=(when-dt.timedelta(hours=6)).strftime('%a %-I:%M %p')
    sv=max(sev(txt,n) for n in ns); hurt=[n for n in ns if INFO[n]['own']=='MINE' and sev(txt,n)]
    if hurt:
        badge='<span class="ibadge mine">🚑 Your player · '+('serious injury' if max(sev(txt,n) for n in hurt)==2 else 'injury')+'</span> '
        st='class="inj mine"'
    else:
        badge={2:'<span class="ibadge sev">🚑 Serious injury</span> ',1:'<span class="ibadge">🚑 Injury</span> '}.get(sv,'')
        st=f'class="{"inj" if sv else ""}"'
    def who(n):
        o=INFO[n]['own']
        return f'<b>{html.escape(short(n))}</b> '+('<span class="yours">★ Yours</span>' if o=='MINE' else f'<span class="tm">{html.escape(o[6:] if o.startswith("TAKEN:") else "FA")}</span>')
    return f'<li {st}>{badge}{" · ".join(who(n) for n in ns)} — {html.escape(txt)} <span class="small">· {html.escape(src)}, {loc}</span></li>'
newssec=''
if any(NEWS.values()):
    newssec='<section class="brief"><h2>League news</h2>'+(f'<div class="myinj">🚑 <b>Your injured players:</b> {html.escape(", ".join(MYINJ))}. Check status before lineup lock.</div>' if MYINJ else '')+''.join(f'<h3>{t}</h3><ul>'+''.join(nlis(i) for i in NEWSP[k][:12])+'</ul>' for k,t in NG if NEWSP[k])+'<p class="small">Last 48 hours from ESPN&#39;s NBA news feed and the latest @UnderdogNBA posts, matched to the players each manager rosters.</p></section>'
em=sorted([i for k in ('mine','opp','watch') for i in NEWS[k]],key=lambda it:(-(sev(it[3],it[1])>0 and INFO[it[1]]['own']=='MINE'),-sev(it[3],it[1])))[:6]
open('news_flag.txt','w').write(', '.join(MYINJ))
open('news_email.html','w').write(('<ul style="margin:0;padding-left:18px">'+''.join(nli(i,True) for i in em)+'</ul>') if em else '')
open('news.txt.out','w').write(''.join(f'- {["","[INJURY] ","[SERIOUS INJURY] "][sev(t,n)]}{"[YOUR PLAYER] " if INFO[n]["own"]=="MINE" and sev(t,n) else ""}{short(n)}: {t} ({s})\n' for _,n,s,t in em))
# IR check: IR needs him ruled out, so "Expected to be out" and "Out for the season" are IR eligible; "Game Time Decision" or no
# injury at all isn't. HASINJ: only when this pool has CBS's notes (an older one has none, and everyone would look healthy).
def injk(t): return 'none' if not t else ('gtd' if 'game time decision' in t.lower() else 'out')
HASINJ=any(i.get('inj') for i in INFO.values())
IRBAD=[n for n in IRP if HASINJ and injk(INFO[n].get('inj',''))!='out']
IRB=''
if IRBAD:
    _ln=''.join(f'<div class="lk-s"><b>{html.escape(short(n))}</b>: {html.escape("CBS lists him as "+INFO[n]["inj"].split(": ",1)[-1] if INFO[n].get("inj") else "no injury listed on CBS")}</div>' for n in IRBAD)
    IRB=(f'<div class="irban" role="alert"><div class="lk-ic">⚠️</div><div><div class="lk-h">IR check</div><div class="lk-t">{len(IRBAD)} player{"s" if len(IRBAD)!=1 else ""} in your IR shouldn&#39;t be there</div>{_ln}'
         f'<div class="lk-s">IR is for players ruled out. Move {"them" if len(IRBAD)!=1 else "him"} off IR on CBS before lineups lock. As of the last nightly read, so check CBS first.</div></div></div>'
         '<style>.irban{display:flex;gap:14px;align-items:center;background:#facc15;color:#1c1917;border-radius:10px;padding:16px 20px;margin:0 0 12px;box-shadow:0 0 0 3px color-mix(in srgb,#facc15 35%,transparent)}.irban .pcn{color:inherit;text-decoration-color:currentColor}</style>')
LOCKB=''
if os.path.exists('lock.txt'):
    lf=open('lock.txt').read().strip().split('|')
    if len(lf)>=4:
        LOCKB=f'<div class="lockban" role="alert"><div class="lk-ic">⏰</div><div><div class="lk-h">Early lock · {html.escape(lf[0])}</div><div class="lk-t">Lineups &amp; IR lock at <b>{html.escape(lf[3])}</b> Calgary</div><div class="lk-s">First game {html.escape(lf[1])} tips at {html.escape(lf[2])}, earlier than the usual 5:00 PM. Set your lineup and make sure everyone on IR is ruled Out before then.</div></div></div>'
# always-on game-times strip (tips.txt: label|lock|game@time;...), quieter than the early-lock banner
if os.path.exists('tips.txt'):
    tf=open('tips.txt').read().strip().split('|')
    if len(tf)>=3 and tf[2]:
        TG={}
        for gt in tf[2].split(';'):
            g,_,t=gt.rpartition('@'); TG.setdefault(t,[]).append(g)
        # the lock time sits in its own pill: easier to spot than plain text, still calmer than the early-lock banner
        LOCKB+=('<style>.tipstrip.lk{border-left-color:#2563eb}.tp-top{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}'
                '.tp-lock{display:inline-flex;align-items:baseline;gap:6px;font:600 .85rem var(--body);color:#1d4ed8;background:color-mix(in srgb,#2563eb 9%,transparent);'
                'border:1px solid color-mix(in srgb,#2563eb 35%,transparent);border-radius:8px;padding:3px 12px}.tp-lock b{font:700 1.3rem var(--display);letter-spacing:.02em}'
                '.tp-lock span{font-size:.75rem;opacity:.8}@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .tp-lock{color:#93c5fd}}:root[data-theme=dark] .tp-lock{color:#93c5fd}</style>'
                f'<div class="tipstrip lk"><div class="tp-top"><div class="tp-lock">🔒 Lineups lock <b>{html.escape(tf[1])}</b><span>Calgary</span></div>'
                f'<div class="tp-h">🏀 Game times · {html.escape(tf[0])} · {sum(map(len,TG.values()))} game{"s" if sum(map(len,TG.values()))!=1 else ""}</div></div>'
                '<div class="tp-l">'+''.join(f'<span class="tp-g"><b>{html.escape(t)}</b> {html.escape(", ".join(gs))}</span>' for t,gs in TG.items())+'</div></div>')
# ---- side-prize tracker (prizes.txt: P|teamA|scoreA|teamB|scoreB, final scores after the 2 AM correction)
PZ=[]
if os.path.exists('prizes.txt'):
    for l in open('prizes.txt'):
        f=l.strip().split('|')
        if len(f)==5 and not l.startswith('#'):
            try: PZ.append((int(f[0].lstrip('P')),f[1],float(f[2]),f[3],float(f[4])))
            except ValueError: pass
def fmtp(x): return f'{x:,.1f}'.rstrip('0').rstrip('.')
if PZ:
    scores=sorted([(sa,a,p) for p,a,sa,b,sb in PZ]+[(sb,b,p) for p,a,sa,b,sb in PZ],reverse=True)
    leads=sorted([(abs(sa-sb),a if sa>sb else b,b if sa>sb else a,p) for p,a,sa,b,sb in PZ],reverse=True)
    mys=[x for x in scores if x[1]==ME]; myl=[x for x in leads if x[1]==ME]
    rk=lambda lst,x: lst.index(x)+1
    top=lambda lst,f: ''.join(f'<li>{f(x)}</li>' for x in lst[:3])
    prizesec=f"""<section class="brief"><h2>Side-prize tracker · $100 each</h2><div class="two">
<div><h3>🔥 Highest score in a period</h3><ol>{top(scores,lambda x:f'<b>{fmtp(x[0])}</b> · {html.escape(x[1])} (P{x[2]})')}</ol>
<p class="small">{'Your best: <b>'+fmtp(mys[0][0])+f'</b> (P{mys[0][2]}), #{rk(scores,mys[0])} of {len(scores)} team-periods.' if mys else 'No scores yet.'}</p></div>
<div><h3>💪 Biggest lead in a period</h3><ol>{top(leads,lambda x:f'<b>+{fmtp(x[0])}</b> · {html.escape(x[1])} over {html.escape(x[2])} (P{x[3]})')}</ol>
<p class="small">{'Your best: <b>+'+fmtp(myl[0][0])+f'</b> over {html.escape(myl[0][2])} (P{myl[0][3]}), #{rk(leads,myl[0])} of {len(leads)} matchups.' if myl else 'You haven&#39;t won a period yet.'}</p></div></div>
<p class="small">Final period scores after the 2 AM stat correction. Your projected best chances: {', '.join(f'P{m["p"]} ({m["mine"]-m["opp_p"]:+,.0f} proj. vs {html.escape(m["opp"])})' for m in sorted(MU,key=lambda m:-(m['mine']-m['opp_p']))[:2]) if MU else '—'}.</p></section>"""
else:
    prizesec=f"""<section class="brief"><h2>Side-prize tracker · $100 each</h2><p>🔥 <b>Highest score in a period</b> and 💪 <b>biggest lead in a period</b>. Tracking starts after P1 ends (Oct 25), using final scores after the 2 AM stat correction.</p><p class="small">Your projected best chances for the biggest lead: {', '.join(f'P{m["p"]} ({m["mine"]-m["opp_p"]:+,.0f} vs {html.escape(m["opp"])})' for m in sorted(MU,key=lambda m:-(m['mine']-m['opp_p']))[:2]) if MU else '—'}. Highest projected score: {(lambda m: f'P{m["p"]} ({m["mine"]:,.0f})')(max(MU,key=lambda m:m['mine'])) if MU else '—'}.</p></section>"""
# ---- side-prize planner: Monte Carlo over all remaining regular-season matchups
import numpy as np
MT=[]
if os.path.exists('matchups.txt'):
    for l in open('matchups.txt'):
        f=l.strip().split('|')
        if len(f)>=3 and f[0].isdigit() and int(f[0]) in REG: MT.append((int(f[0]),f[1],f[2]))
def roster_of(t):   # your IR players count only with a return date (out_until), like other teams' (left out): same odds on every page
    if t==ME: return {n:v for n,v in R.items() if INFO[n]['sec']!='I' or n in out}
    return next((v for k,v in OTH.items() if k==t or (t=='TINOLA' and 'ɪɴᴏʟᴀ' in k)),None)
PLAN=''
if MT:
    TP={}
    for p,a,b in MT:
        for t in (a,b):
            if (t,p) not in TP:
                r=roster_of(t); TP[(t,p)]=ptot(r,p) if r else 0
    tkeys=list(TP); idx={k:i for i,k in enumerate(tkeys)}
    mu=np.array([TP[k] for k in tkeys]); N=4000
    rng=np.random.default_rng(7)
    S=mu+rng.standard_normal((N,len(tkeys)))*0.11*mu
    hs0=max([x[2] for x in PZ]+[x[4] for x in PZ],default=0); bl0=max([abs(x[2]-x[4]) for x in PZ],default=0)
    smax=S.max(1); hi_win=np.zeros(len(tkeys))
    am=S.argmax(1); ok=smax>hs0
    for i in range(len(tkeys)): hi_win[i]=np.mean((am==i)&ok)
    M=np.array([[idx[(a,p)],idx[(b,p)]] for p,a,b in MT])
    D=S[:,M[:,0]]-S[:,M[:,1]]; AD=np.abs(D)
    lam=AD.argmax(1); lmax=AD.max(1); okl=lmax>bl0
    lead_win={}
    for j,(p,a,b) in enumerate(MT):
        sel=(lam==j)&okl
        lead_win[(a,p)]=np.mean(sel&(D[:,j]>0)); lead_win[(b,p)]=np.mean(sel&(D[:,j]<0))
    rows_=[]
    for p,a,b in MT:
        if ME not in (a,b): continue
        o=b if a==ME else a
        my=TP[(ME,p)]; op=TP[(o,p)]
        rank=1+sum(1 for (t,q),v in TP.items() if q==p and v>my)
        rows_.append(dict(p=p,o=o,my=my,op=op,rank=rank,hs=hi_win[idx[(ME,p)]],bl=lead_win[(ME,p)]))
    tot_hs=sum(r['hs'] for r in rows_); tot_bl=sum(r['bl'] for r in rows_)
    best_hs=sorted(rows_,key=lambda r:-r['hs'])[:3]; best_bl=sorted(rows_,key=lambda r:-r['bl'])[:3]
    def pc(x): return f'{x*100:.1f}%' if x>=0.001 else '&lt;0.1%'
    hot=lambda r,k: ' class="hi"' if r in (best_hs if k=='hs' else best_bl) else ''
    trs=''.join(f'<tr><td class="num"><b>P{r["p"]}</b></td><td>{pstart(r["p"]).strftime("%b %-d")} · vs {html.escape(dname(r["o"]))}</td><td class="num">{r["my"]:,.0f}</td><td class="num">#{r["rank"]} of 10</td><td class="num"{hot(r,"hs")}>{pc(r["hs"])}</td><td class="num">{r["my"]-r["op"]:+,.0f}</td><td class="num"{hot(r,"bl")}>{pc(r["bl"])}</td></tr>' for r in rows_)
    lg_hs=max(TP.items(),key=lambda kv:kv[1])
    PLAN=f"""<section class="brief"><h2>Side-prize planner</h2>
<p>Chance you finish the season with each $100 prize: <b>🔥 highest period score {tot_hs*100:.0f}%</b> · <b>💪 biggest period lead {tot_bl*100:.0f}%</b> (a 1-in-10 team would be ~10%).</p>
<ul><li><b>Best weeks for the high score:</b> {', '.join(f'P{r["p"]} ({pc(r["hs"])}, proj. {r["my"]:,.0f})' for r in best_hs)}. These are the long, game-heavy weeks; the league's highest projected week is {html.escape(dname(lg_hs[0][0]))} in P{lg_hs[0][1]} ({lg_hs[1]:,.0f}).</li>
<li><b>Best weeks for the biggest lead:</b> {', '.join(f'P{r["p"]} vs {html.escape(dname(r["o"]))} ({pc(r["bl"])}, proj. {r["my"]-r["op"]:+,.0f})' for r in best_bl)}.</li>
<li><b>How to plan:</b> in those weeks, stream every open slot (the Best adds tab's P gains show who fills them) and avoid benching anyone for rest; a lopsided week pays more if you push it further.</li></ul>
<div class="scroll"><table><thead><tr><th>P</th><th>Week · opponent</th><th>Your proj.</th><th>League rank that week</th><th>🔥 High-score chance</th><th>Proj. margin</th><th>💪 Biggest-lead chance</th></tr></thead><tbody>{trs}</tbody></table></div>
<p class="small">{N:,} simulated seasons using every team's current roster and full NBA schedule, with normal week-to-week swings (about ±11%). Chances are for that week ending up as the season's record{' and beating the current marks ('+fmtp(hs0)+' / +'+fmtp(bl0)+')' if PZ else ''}. Rosters change, so this refreshes nightly.</p></section>"""
# ---- Standings & playoff odds (top of the Playoffs tab): finished periods from actual scores (your CBS results.txt; other
# teams: their ACTIVE players' points, BENCH), this period = scored so far + the side-prize simulation's remaining days, then
# 8 of 10 seeded (win %, division record, total points) and the bracket played out (1v8, 4v5, 2v7, 3v6, no reseeding).
def _build_odds():
    global oddsec
    oddsec=''
    allm=[]
    if os.path.exists('matchups.txt'):
        for l in open('matchups.txt'):
            f=l.strip().split('|')
            if len(f)>=3 and f[0].isdigit() and 1<=int(f[0])<=21: allm.append((int(f[0]),f[1],f[2]))
    if not allm or not MT: return
    teams=sorted({t for _,a,b in allm for t in (a,b)})
    WEST={'Binkas&Yams','Tank You Very Much','TINOLA','SOGGY','Oobsidoobsie'}
    act=defaultdict(float)   # (team, period) -> points scored on finished nights before today
    for (d,t),v in BENCH.items():
        dd=dt.datetime.strptime(d,'%Y%m%d').date()
        if dd<TODAY: act[(dtn(t),period(dd))]+=v[1]
    res={}
    for x in PAST: res[x[0]]=(x[3],x[4])   # your CBS results: period -> (you, them)
    N_=S.shape[0]; W=defaultdict(lambda:np.zeros(N_)); DW=defaultdict(lambda:np.zeros(N_)); PTS=defaultdict(lambda:np.zeros(N_)); rec=defaultdict(lambda:[0,0,0])
    for p,a,b in allm:
        if p<CUR:
            if ME in (a,b) and p in res: sa,sb=(res[p] if a==ME else res[p][::-1])
            else: sa,sb=act[(a,p)],act[(b,p)]
            sa=np.full(N_,sa); sb=np.full(N_,sb)
            w=1 if sa[0]>sb[0] else (0 if sa[0]<sb[0] else .5)
            rec[a][0 if w==1 else 1 if w==0 else 2]+=1; rec[b][1 if w==1 else 0 if w==0 else 2]+=1
        elif (a,p) in idx and (b,p) in idx:
            sa=S[:,idx[(a,p)]]+(act[(a,p)] if p==CUR else 0); sb=S[:,idx[(b,p)]]+(act[(b,p)] if p==CUR else 0)
        else: continue
        wa=(sa>sb)+0.5*(sa==sb); div=(a in WEST)==(b in WEST)
        W[a]+=wa; W[b]+=1-wa; PTS[a]+=sa; PTS[b]+=sb
        if div: DW[a]+=wa; DW[b]+=1-wa
    T=len(teams); key=np.stack([W[t]*1e7+DW[t]*1e5+PTS[t] for t in teams],1)   # wins, then division wins, then points
    order=np.argsort(-key,1); seed=np.empty_like(order); seed[np.arange(N_)[:,None],order]=np.arange(T)[None,:]
    PP=np.zeros((T,3))
    for i,t in enumerate(teams):
        r=roster_of(t)
        for j,p in enumerate((22,23,24)): PP[i,j]=ptot(r,p) if r and p in P else 0
    rng2=np.random.default_rng(11); champ=np.zeros(T); final=np.zeros(T)
    for s in range(N_):
        bys=order[s]   # team indices by seed
        def play(i,j,rd):
            a_=PP[i,rd]*(1+0.11*rng2.standard_normal()); b_=PP[j,rd]*(1+0.11*rng2.standard_normal()); return i if a_>=b_ else j
        q=[play(bys[0],bys[7],0),play(bys[3],bys[4],0),play(bys[1],bys[6],0),play(bys[2],bys[5],0)]
        f1,f2=play(q[0],q[1],1),play(q[2],q[3],1); final[f1]+=1; final[f2]+=1; champ[play(f1,f2,2)]+=1
    pc=lambda x:'<0.1%' if 0<x<0.001 else ('—' if x==0 else f'{x*100:.0f}%' if x>=0.995 or x>=0.1 else f'{x*100:.1f}%')
    rows=[]
    for i,t in enumerate(teams):
        sd=seed[:,i]; me=t==ME; r_=rec[t]
        rows.append((W[t].mean(),f'<tr{" class=me" if me else ""}><td>{"<b>" if me else ""}{html.escape(dname(t))}{"</b> ★" if me else ""}</td><td class="num">{r_[0]}-{r_[1]}'+(f'-{r_[2]}' if r_[2] else '')+'</td>'
            f'<td class="num">{W[t].mean():.1f}–{21-W[t].mean():.1f}</td><td class="num"><b>{pc(np.mean(sd<8))}</b></td><td class="num">{pc(np.mean(sd<2))}</td><td class="num">{pc(np.mean(sd==0))}</td>'
            f'<td class="num">{pc(np.mean(sd==T-1))}</td><td class="num">{pc(final[i]/N_)}</td><td class="num"><b>{pc(champ[i]/N_)}</b></td></tr>'))
    mi=teams.index(ME) if ME in teams else None
    lead=(f'<p style="margin:0 0 8px">You: <b>{pc(np.mean(seed[:,mi]<8))}</b> to make the playoffs, <b>{pc(champ[mi]/N_)}</b> to win the title (${800}), '
          f'{pc(np.mean(seed[:,mi]==T-1))} to finish last. Projected record {W[ME].mean():.1f}–{21-W[ME].mean():.1f}.</p>') if mi is not None else ''
    oddsec=(f'<section class="brief"><h2>Standings &amp; playoff odds</h2>{lead}<div class="scroll"><table><thead><tr><th>Team</th><th>Record</th><th>Proj. record</th><th>Make playoffs</th><th>Top-2 seed</th><th>#1 seed</th><th>Last place</th><th>Reach final</th><th>Champion</th></tr></thead><tbody>'
            +''.join(r for _,r in sorted(rows,key=lambda x:-x[0]))+'</tbody></table></div>'
            f'<p class="small">{N_:,} simulated seasons: finished periods as they ended (yours from CBS; other teams from their active players&#39; points, within a few points of CBS), '
            'this period&#39;s points so far, and every remaining matchup and playoff round from each team&#39;s best daily lineups on its current roster, with normal week-to-week swings (about ±11%). '
            'Seeds by wins, then division record, then total points; 8 of 10 make it; bracket 1v8, 4v5, 2v7, 3v6 with no reseeding. Trades, pickups and injuries after today aren&#39;t in it.</p></section>')
_build_odds()
# ---- Bench (Season → Bench): points each manager left on the bench, from BENCH (that night's ACTIVE players' best lineup vs
# the best lineup from everyone on the roster, actual box scores). Within a few points of CBS: CBS uses the slot each player was set in.
def _build_bench():
    global benchsec, benchline
    benchsec=''; benchline=''
    if not BENCH:
        benchsec='<p class="muted">Starts once a night with saved lineups is final.</p>'; return
    pday=lambda d:period(dt.datetime.strptime(d,'%Y%m%d').date())
    T=defaultdict(lambda:{'o':0,'a':0,'n':0,'ok':0,'po':0,'pa':0})
    for (d,t),(o,a,_) in BENCH.items():
        x=T[t]; x['o']+=o; x['a']+=a; x['n']+=1; x['ok']+=o-a<1
        if pday(d)==CUR: x['po']+=o; x['pa']+=a
    rk=sorted(T.items(),key=lambda kv:(kv[1]['o']-kv[1]['a'])/max(1,kv[1]['n']))
    def tr(i,t,x):
        me=t==MEN; lost=x['o']-x['a']
        return (f'<tr{" class=me" if me else ""}><td class="num">{i}</td><td>{"<b>" if me else ""}{html.escape(dname(dtn(t)))}{"</b> ★" if me else ""}</td>'
                f'<td class="num">{x["pa"]:,.0f} / {x["po"]:,.0f}</td><td class="num">{x["po"]-x["pa"]:,.0f}</td>'
                f'<td class="num">{x["a"]:,.0f} / {x["o"]:,.0f}</td><td class="num"><b>{lost:,.0f}</b></td><td class="num">{lost/max(1,x["n"]):.1f}</td>'
                f'<td class="num">{100*x["a"]/max(1,x["o"]):.1f}%</td><td class="num">{x["ok"]}/{x["n"]}</td></tr>')
    lt=('<div class="scroll"><table><thead><tr><th>#</th><th>Manager</th><th>P'+str(CUR)+' scored / possible</th><th>P'+str(CUR)+' left</th>'
        '<th>Season scored / possible</th><th>Season left on bench</th><th>Per night</th><th>Lineup efficiency</th><th>Perfect nights</th></tr></thead><tbody>'
        +''.join(tr(i+1,t,x) for i,(t,x) in enumerate(rk))+'</tbody></table></div>')
    mine=sorted(((d,v) for (d,t),v in BENCH.items() if t==MEN),reverse=True)
    def nr(d,v):
        o,a,bn=v; low=o-a
        miss=[f'{html.escape(short(n))} {p:.0f}' for n,p in bn if p>0][:3] if low>=1 else []
        return (f'<tr><td class="num">{dt.datetime.strptime(d,"%Y%m%d").strftime("%a %b %-d")}</td><td class="num">{a:,.0f}</td><td class="num">{o:,.0f}</td>'
                f'<td class="num">{"<b style=color:var(--bad)>"+format(low,",.0f")+"</b>" if low>=1 else "<span style=color:var(--ok)>✓ 0</span>"}</td>'
                f'<td>{("Benched: "+" · ".join(miss)) if miss else ""}</td></tr>')
    yt=('<div class="scroll"><table><thead><tr><th>Night</th><th>Your active lineup</th><th>Best possible</th><th>Left on bench</th><th>Who sat (his points)</th></tr></thead><tbody>'
        +''.join(nr(d,v) for d,v in mine)+'</tbody></table></div>') if mine else ''
    benchsec=(f'<section><h2>Points left on the bench</h2><p class="small" style="margin:0 0 8px">Each night, the points of the players a manager had in an active spot (each in his best open slot) '
              'against the best lineup anyone on his roster could have made, from actual box scores. Lineup efficiency = scored ÷ possible. '
              'Within a few points of CBS: CBS scores each player in the slot he was set in. Ranked by points left per night, fewest first.</p>'+lt+'</section>'
              +(f'<section><h2>Your nights</h2>{yt}</section>' if yt else ''))
    if mine:   # Today: one line on last night
        d,(o,a,bn)=mine[0]
        if o-a>=1:
            who=', '.join([f'{html.escape(short(n))} ({p:.0f})' for n,p in bn if p>0][:2])
            benchline=f'<b>{dt.datetime.strptime(d,"%Y%m%d").strftime("%a")}:</b> you scored {a:,.0f} of a possible {o:,.0f}, <b>{o-a:,.0f} left on the bench</b>{" (" + who + " sat)" if who else ""}.'
        else:
            benchline=f'<b>{dt.datetime.strptime(d,"%Y%m%d").strftime("%a")}:</b> you scored {a:,.0f}, the best your roster could do. Nothing left on the bench.'
        x=T[MEN]; r=[t for t,_ in rk].index(MEN)+1
        benchline=(f'<p class="small" style="margin:6px 0 0">🪑 {benchline} Season: {x["o"]-x["a"]:,.0f} left on the bench, {r}{"st" if r==1 else "nd" if r==2 else "rd" if r==3 else "th"} of {len(rk)} '
                   '<a href="#sben" onclick="var b=document.querySelector(&#39;.tabs button[data-t=season]&#39;);if(b)b.click();if(window.__sub)window.__sub(&#39;sben&#39;);return false">Season → Bench →</a></p>')
_build_bench()
# ---- breakouts sub-tab (from breakout.tsv; kept until the next alert night replaces it)
BOLAB=open('breakout_label.txt').read().strip() if os.path.exists('breakout_label.txt') else ''
def borow(n,b):
    i=INFO.get(n); own=b['own']
    if own=='MINE' or (i and i['own']=='MINE'): ow='<span class="tag warn">★ yours</span>'
    elif own.startswith('TAKEN:'): ow=f'<span class="tm">{html.escape(own[6:])}</span>'
    else: ow='<span class="tag ok">free agent</span>'
    ex=next(((t,ps) for nn,t,ps,_ in EXTRA if nn==n),None)
    who=f'<b>{html.escape(short(n))}</b>'+(f' <span class="tm">{i["pos"]} · {i["team"]}</span>' if i else (f' <span class="tm">{ex[1]} · {ex[0]}</span>' if ex else ''))+(' <span class="flag">★</span>' if n in watch else '')+wbtn(n,own=='FA?' and n not in INFO)
    ratio=f'{b["a3"]/b["base"]:.1f}×' if b['base']>0 else '—'
    g=GA.get(n) if n in FA else None
    gain=f'<b>{tot(g,REG):+.0f}</b>' if g else '<span class="muted">—</span>'
    tier='🚀 Breakout' if b['tier']=='BREAKOUT' else '🔥 Heating up'
    rc=(rost(n)+'<div>'+rtier(n)+ten(n)+'</div>') if (es(n) or n in RT) else '<span class="muted small">not in CBS trends</span>'
    return f'<tr><td>{tier}</td><td>{who}</td><td>{ow}</td><td>{rc}</td><td class="num"><b>{b["a3"]:.1f}</b></td><td class="num">{b["base"]:.1f}</td><td class="num">{ratio}</td><td class="num bog"'+(f' data-n="{html.escape(n)}"' if g else '')+f'>{gain}</td><td class="small" style="white-space:normal;min-width:220px">{html.escape(b["note"])}</td></tr>'
if BO:
    borows='\n'.join(borow(n,b) for n,b in sorted(BO.items(),key=lambda kv:(kv[1]['tier']!='BREAKOUT',-kv[1]['a3'])))
    bobody=(f'<div class="brief">{bsum}</div>' if bsum else '')+f"""<div class="scroll"><table>
<thead><tr><th>Alert</th><th>Player</th><th>Owner</th><th>Rostered % (CBS)</th><th>Last 3 avg</th><th>CBS proj</th><th>vs proj</th><th>Season gain</th><th>Why · news &amp; buzz</th></tr></thead>
<tbody>{borows}</tbody></table></div>
<p class="small">🚀 Breakout = averaging 30+ best-slot points over his last 3 games, at least 1.3× his CBS projection, 30+ in 2 of the 3, with minutes going up. 🔥 Heating up = last-3 average 28+ and at least 1.25× projection. Season gain = rest-of-regular-season points if you add him and drop <b class="dropname">{html.escape(short(STREAM))}</b> (free agents only; change it with “If I drop” on Best adds). ★ = on your watchlist. Alerts are checked on game nights from Thu Oct 22; this list stays until the next check replaces it.</p>"""
else:
    bobody='<p class="muted">No alerts yet. Breakout checks start once players have 3 regular-season games (from Thu Oct 22).</p>'
bosec=f"""<section><h2>Breakouts{(' · '+html.escape(BOLAB)) if BOLAB else ''}</h2>
{dropsel_bo if BO else ''}{bobody}</section>"""
_prog(66,'Re-running watchlist players at other FP/G levels',98,10.6)
# ---- FP/G what-if (Watchlist): each watched free agent's gains re-simulated at other FP/G levels (stream-slot drop),
# plus his recent form from the box scores, so the page can project gains for any FP/G typed in
WOFF=(-8,-6,-4,-2,0,2,4,6,8,10,12)   # FP/G offsets from his CBS projection
def whatif(n):  # [[FP/G, [gain per NX period..., rest of reg. season, playoffs]], ...] with the stream-slot drop;
    # for your own players, his worth to your lineups (MV) at each FP/G instead
    t,s=SV[n]; b=INFO[n]['best']; f=min(1.0,INFO[n]['gp']/78.5); res=[]; mine=n in R
    if mine: rest={k:v for k,v in R.items() if k!=n}; rp={p:full[p]-MV[n][p] for p in PER}   # rp = your lineups without him
    for o in sorted(set(WOFF)|{round(x[0]-b,1) for x in (form(n,3),form(n)) if x}):   # + his actual form, exact
        if b+o<1: continue
        if o:
            m=f'{n}#{o}'   # own name so the lineup cache (keyed by names) doesn't reuse his real-FP/G lineups
            if n in out: out[m]=out[n]
            s2={k:v+o for k,v in s.items()}
            if mine: r=dict(rest); r[m]=(t,s2); g={p:ptot(r,p)-rp[p] for p in PER}
            else: g={p:v*f for p,v in gains(m,t,s2).items()}
            out.pop(m,None)
        else: g=MV[n] if mine else (GA.get(n) or GT[n])
        res.append([round(b+o,1),[round(g[p]) for p in NA]+[round(tot(g,REG)),round(tot(g,PO))]])
    return res
# watched players, plus every "If I drop" choice: changing the FP/G of the player you'd drop changes what he's worth,
# so every gain moves by that much (exact: gain = lineups with the pickup - lineups with him)
WG={n:whatif(n) for n in dict.fromkeys([n for n in watch if n in FA or n in GT or n in R]+DROPS+IRP)}
_prog(98,'Laying out the tabs',100,0.6)
# ---- watchlist tab (live list in the artifact db collection "watchlist"; watch.txt is the fallback snapshot)
PL=[]; _B2B={}
for n,i in sorted(INFO.items(),key=lambda kv:-kv[1]['best']):
    g=GA.get(n) or GT.get(n) or MV.get(n)   # your own players: what he's worth to your lineups
    PL.append({'rt':RT.get(n),'re':(lambda e:[round(e[0],1),round(e[1],1)] if e else None)(es(n)),'n':n,'s':short(n),'t':i['team'],'p':i['pos'],'o':('yours' if i['own']=='MINE' else (i['own'][6:] if i['own'].startswith('TAKEN:') else 'FA')),'f':round(i['best'],1),
               'g':[round(g[p]) for p in NA]+[round(tot(g,REG)),round(tot(g,PO))] if g else None})
    if n in WG: PL[-1].update(k=WG[n],l3=form(n,3),sz=form(n))
    if n in R: PL[-1]['m']=1
    if n in WG or n in R: PL[-1]['bb']=_B2B.setdefault(i['team'],b2bn(i['team']))   # back-to-backs left (reg., playoffs)
    if n in REST: PL[-1]['rb']=1
    if n in IRP: PL[-1]['ir']='IR · back ~'+out[n].strftime('%b %-d') if n in out and out[n]>TODAY else 'IR'
    elif INFO[n]['gp']<78.5: PL[-1]['gf']=round(INFO[n]['gp']/78.5,3)   # gains are scaled by his projected games share
for n,t,pos,f in sorted(EXTRA,key=lambda x:-x[3]):  # deep-bench free agents: autocomplete only, full numbers once watched
    if n not in INFO: PL.append({'n':n,'s':short(n),'t':t,'p':pos,'o':'FA','f':round(f,1),'g':None})
WLJS="""<script>(function(){var P=__PL__,W0=__W0__,NX=__NX__,NS=__NS__,ST=__ST__,IRN=__IRN__,IRG=__IRG__;var by={};P.forEach(function(x){by[x.n.toLowerCase()]=x});
var inp=document.getElementById('wl-in'),dl=document.getElementById('wl-dl'),tb=document.getElementById('wl-body'),tb2=document.getElementById('wl-body2'),tb3=document.getElementById('wl-body3'),rsec=document.getElementById('wl-rsec'),msg=document.getElementById('wl-msg'),btn=document.getElementById('wl-add');
dl.innerHTML=P.map(function(x){return '<option value="'+x.n.replace(/"/g,'&quot;')+'">'+x.t+' · '+x.p+' · '+(x.o==='FA'?'free agent':x.o)+'</option>'}).join('');
var cur=W0.slice(),db=null,col=null,OV=null,HEADS=[document.getElementById('wl-head'),document.getElementById('wl-head2')];
var dfp=document.getElementById('wl-dfp'),DN=__DN__,DI=ws0();   // "If I drop" choices (full names) and the one picked
function ws0(){var w=document.getElementById('dropsel-wl');return window.__bbldrop?window.__bbldrop.i:(w?+w.value||0:0)}
function on(t,f){[tb,tb2,tb3,dfp].forEach(function(el){if(el)el.addEventListener(t,f)})}   // same handlers on both tables and the drop's FP/G
function syncQ(){[].forEach.call(document.querySelectorAll('.wq'),function(b){var n=b.dataset.n,on=cur.some(function(c){return c.toLowerCase()===n.toLowerCase()});b.classList.toggle('on',on);b.textContent=on?'★ Watching':'+ Watch';b.disabled=on||!col;b.title=on?'On your watchlist':(col?'Add to your watchlist':'Open the page with “6 - Open Command Center” to edit your watchlist')})}
document.addEventListener('DOMContentLoaded',function(){syncQ()});document.addEventListener('bbl-sync',syncQ);
document.addEventListener('click',async function(e){var b=e.target.closest('.wq');if(!b||!col||b.classList.contains('on'))return;var n=b.dataset.n;b.disabled=true;b.textContent='Adding…';try{await col.doc(key(n)).set({name:n,added:new Date().toISOString()});msg.textContent='Added '+n+' to your watchlist.'}catch(er){b.textContent='+ Watch';b.disabled=false;b.title='Couldn’t save ('+(er&&er.code||'error')+')'}});
var WIF={};try{WIF=JSON.parse(localStorage.getItem('bbl-wif')||'{}')||{}}catch(e){}   // FP/G you typed, per player
// shared with the Trade analyzer: a change on either side shows on the other
function wsave(){try{localStorage.setItem('bbl-wif',JSON.stringify(WIF))}catch(e){}document.dispatchEvent(new CustomEvent('bbl-wif',{detail:'wl'}))}
document.addEventListener('bbl-wif',function(e){if(e.detail==='wl')return;try{WIF=JSON.parse(localStorage.getItem('bbl-wif')||'{}')||{}}catch(er){}render()});
// ★ favourites: pinned to the top of their table (free agents / on a roster), whatever the sort; saved in this browser
var FAV={};try{FAV=JSON.parse(localStorage.getItem('bbl-wfav')||'{}')||{}}catch(e){}
document.addEventListener('bbl-wfav',function(){try{FAV=JSON.parse(localStorage.getItem('bbl-wfav')||'{}')||{}}catch(e){}render()});
function isfav(n){var x=by[n.toLowerCase()];return !!FAV[x?x.n:n]}
function fst(x){var o=!!FAV[x.n];return '<button type="button" class="wfav'+(o?' on':'')+'" data-n="'+esc(x.n)+'" aria-pressed="'+o+'" title="'+(o?'Favourite: pinned to the top. Click to unpin':'Favourite: pin to the top of this table')+'">'+(o?'★':'☆')+'</button>'}
function gi(k,v){if(v<=k[0][0])return k[0][1];var i=0;while(i<k.length-1&&k[i+1][0]<v)i++;if(i===k.length-1)return k[i][1];var a=k[i],b=k[i+1],t=(v-a[0])/(b[0]-a[0]);return a[1].map(function(y,j){return y+(b[1][j]-y)*t})}
function fv(x){return x&&x.k&&WIF[x.n]!=null?WIF[x.n]:(x?x.f:null)}
function dx(){return by[(DN[DI]||'').toLowerCase()]}   // the player in "If I drop"
// gains at your FP/G: the simulated gains at nearby FP/G levels, interpolated; for another drop, its gains plus the same change.
// If you changed the FP/G of the player you'd drop, every gain also moves by the change in his worth (scaled like the gain
// itself by the pickup's projected games share). Your own players' rows show their worth, which the drop doesn't change.
function eg(n,x){var g=(OV&&OV[n])||(x&&x.g)||null;if(!g)return g;var v=fv(x),a=null,z=null,d=dx(),dv=fv(d),sh=null;
if(x.k&&v!==x.f){a=gi(x.k,v);z=gi(x.k,x.f)}
if(!x.m&&d&&d.k&&dv!==d.f)sh=[gi(d.k,dv),gi(d.k,d.f)];if(!a&&!sh)return g;
return g.map(function(y,j){return Math.round(y+(a?a[j]-z[j]:0)-(sh?(x.gf||1)*(sh[0][j]-sh[1][j]):0))})}
// your IR players: gain from activating him and dropping the player in "If I drop" (IRG, per drop), moved by his FP/G change
// (his worth at that level) and by any FP/G change of the drop, like the rows above
function egi(x,k){var g=IRG[DI]&&IRG[DI][k];if(!g)return null;var v=fv(x),a=null,z=null,d=dx(),dv=fv(d),sh=null;
if(x.k&&v!==x.f){a=gi(x.k,v);z=gi(x.k,x.f)}if(d&&d.k&&dv!==d.f)sh=[gi(d.k,dv),gi(d.k,d.f)];
return g.map(function(y,j){return Math.round(y+(a?a[j]-z[j]:0)-(sh?sh[0][j]-sh[1][j]:0))})}
function gc(g){return NX.map(function(_,i){return '<td class="num gv'+(g[i]>=20?' hi':'')+(i>=NS?' wx':'')+'">'+f(g[i])+'</td>'}).join('')+'<td class="num gv">'+f(g[NX.length])+'</td><td class="num gv">'+f(g[NX.length+1])+'</td>'}
var OPEN=null,LAST=null;   // player whose FP/G editor is open; the last one changed (outlined, and flashed where it lands after the re-sort)
function wcls(x){return (x.k&&fv(x)!==x.f?' wif':'')+(x.n===LAST?' wlast':'')+(FAV[x.n]?' wfavr':'')}
function flash(){if(!LAST)return;var r=document.querySelector('#wwatch tr.wlast');if(!r)return;r.classList.remove('wjust');void r.offsetWidth;r.classList.add('wjust');
var b=r.getBoundingClientRect();if(b.top<60||b.bottom>innerHeight)r.scrollIntoView({block:'center',behavior:'smooth'})}
// FP/G cell: the number as before (tap to change it); a changed one shows in blue with ↺ to go back to the CBS projection
function fc(x){if(!x.k)return '<td class="num">'+(x.f==null?'—':x.f)+'</td>';return '<td class="num wif-td">'+fin(x)+'</td>'}
function fin(x,dd){var v=fv(x),ch=v!==x.f,n=esc(x.n),k=(dd?'drop:':'')+x.n;   // dd: the editor next to "If I drop"
var h='<button type="button" class="wif-v" data-n="'+n+'"'+(dd?' data-d="1"':'')+' aria-expanded="'+(OPEN===k)+'" title="'+(ch?'CBS projects '+x.f+'. ':'')+'Change his FP/G to see the gains at that level">'+v+'</button>'+(ch?'<button type="button" class="wif-r" data-n="'+n+'" title="Reset to the CBS projection ('+x.f+')" aria-label="Reset '+esc(x.s)+' to the CBS projection">↺</button>':'');
if(OPEN===k){var c=[['CBS',x.f]];if(x.l3)c.push([x.l3[1]>=3?'Last 3':'Last '+x.l3[1],x.l3[0]]);if(x.sz&&x.sz[1]>3)c.push(['Season',x.sz[0]]);
h+='<div class="wif-pop"><input type="number" class="wif-in" inputmode="decimal" step="0.5" min="'+x.k[0][0]+'" max="'+x.k[x.k.length-1][0]+'" value="'+v+'" data-n="'+n+'" aria-label="FP/G for '+esc(x.s)+'">'+c.map(function(q){return '<button type="button" class="wif-c" data-n="'+n+'" data-v="'+q[1]+'" aria-pressed="'+(q[1]===v)+'">'+q[0]+' <b>'+q[1]+'</b></button>'}).join('')+'</div>'}
return h}
function dfr(){if(!dfp)return;var d=dx();if(!d||!d.k){dfp.innerHTML='';return}var w=gi(d.k,fv(d));
dfp.innerHTML='<span class="small">his FP/G</span> '+fin(d,1)+' <span class="small wl-dw">worth '+f(Math.round(w[NX.length]))+' reg. season + '+f(Math.round(w[NX.length+1]))+' playoffs</span>';dfp.classList.toggle('wif',fv(d)!==d.f)}
function setv(n,v){var x=by[n.toLowerCase()];if(!x||!x.k)return;if(v!=null&&!isNaN(v))v=Math.min(Math.max(v,x.k[0][0]),x.k[x.k.length-1][0]);if(v==null||isNaN(v)||v===x.f)delete WIF[x.n];else WIF[x.n]=Math.round(v*10)/10;wsave()}
function dn(d){[].forEach.call(document.querySelectorAll('#wwatch .dropname'),function(e){e.textContent=d.name})}
var ws=document.getElementById('dropsel-wl'),bs=document.getElementById('dropsel');
if(ws&&bs){ws.addEventListener('change',function(){bs.value=ws.value;bs.dispatchEvent(new Event('change'))})}
document.addEventListener('bbldrop',function(e){OV=e.detail.w;DI=e.detail.i;dn(e.detail);if(ws)ws.value=String(e.detail.i);render()});if(window.__bbldrop){OV=window.__bbldrop.w;dn(window.__bbldrop);if(ws)ws.value=String(window.__bbldrop.i)}
function esc(t){var d=document.createElement('div');d.textContent=t;return d.innerHTML}
function f(v){return v==null?'—':(v>=0?'+':'')+v}
var sc=NX.length+3,sd=-1;function sv(n){var x=by[n.toLowerCase()];if(!x)return null;if(sc===0)return x.s.toLowerCase();if(sc===1)return x.o.toLowerCase();if(sc===2)return fv(x);var gg=eg(x.n,x);return gg?gg[sc-3]:null}
function render(skipD){setTimeout(syncQ,0);window.__bblwl=cur.slice();document.dispatchEvent(new Event('bbl-wl'));if(!skipD)dfr();[].forEach.call(document.querySelectorAll('#wwatch .wif-all'),function(b){b.disabled=!cur.concat(IRN).some(function(n){var x=by[n.toLowerCase()];return x&&x.k&&WIF[x.n]!=null&&grp(x)===b.dataset.g})});cur.sort(function(a,b){var x=sv(a),y=sv(b);if(x==null&&y==null)return 0;if(x==null)return 1;if(y==null)return -1;return (x<y?-1:x>y?1:0)*sd});cur=cur.filter(isfav).concat(cur.filter(function(n){return !isfav(n)}));
HEADS.forEach(function(h){[].forEach.call(h.querySelectorAll('th'),function(th,i){th.setAttribute('aria-sort',i===sc?(sd>0?'ascending':'descending'):'none');var a=th.querySelector('.arr');if(a)a.textContent=i===sc?(sd>0?' ▲':' ▼'):' ↕'})});
// free agents (and names not in the CBS pool yet) on top; players on a roster, yours or another manager's, in their own table below
var rl=cur.filter(function(n){var x=by[n.toLowerCase()];return x&&x.o!=='FA'});
tb.innerHTML=cur.filter(function(n){return rl.indexOf(n)<0}).map(row).join('')||'<tr><td colspan="9" class="muted">No free agents on your watchlist.</td></tr>';
tb2.innerHTML=rl.map(row).join('');rsec.hidden=!rl.length;
if(tb3)tb3.innerHTML=IRN.map(function(n,k){var x=by[n.toLowerCase()];if(!x)return '';return '<tr data-ir="'+k+'" class="'+wcls(x)+'"><td><b>'+esc(x.s)+'</b> <span class="nbat" data-t="'+esc(x.t)+'">'+esc(x.t)+'</span> <span class="tm">'+esc(x.p)+'</span>'+rbt(x)+'</td><td><span class="tag bad">'+esc(x.ir||'IR')+'</span></td>'+fc(x)+gc(egi(x,k)||[])+'<td></td></tr>'}).join('')}
// 🛌 B2B: he rests on back-to-backs (sits the 2nd night); clicks and syncing: RBJS (every table), saved with Apply & rebuild
function rbt(x){if(!x||!x.bb||!window.__bblrest)return '';var on=window.__bblrest.has(x.n),b=x.bb;return ' <button type="button" class="rb2b'+(on?' on':'')+(!!x.rb!==on?' pend':'')+'" data-n="'+esc(x.n)+'" data-s="'+(x.rb?1:0)+'"'+(window.__bblsetok?'':' disabled')+' title="'+(on?'Rests on back-to-backs: ':'Mark as resting on back-to-backs: ')+'sits the 2nd night of each, '+b[0]+' left in the regular season + '+b[1]+' in the playoffs. Then Apply &amp; rebuild at the top.">🛌 B2B</button>'}
function row(n){var x=by[n.toLowerCase()]||{n:n,s:n,t:'?',p:'?',o:'not in CBS pool yet',f:null,g:null};var g=eg(x.n,x)||[];
return '<tr class="'+wcls(x)+'"'+(x.m?' title="Your player: what he’s worth to your lineups, the points you’d lose without him"':'')+'><td>'+fst(x)+'<b>'+esc(x.s)+'</b> '+(x.t?'<span class="nbat" data-t="'+esc(x.t)+'">'+esc(x.t)+'</span> ':'')+'<span class="tm">'+esc(x.p)+'</span>'+rbt(x)+(x.re?' <span class="rost" title="Rostered across ESPN leagues"><span class="src es">ESPN</span>'+x.re[0]+'% rostered <small>'+(x.re[1]>0?'▲'+x.re[1]:(x.re[1]<0?'▼'+(-x.re[1]):'±0'))+' this wk</small></span>':'')+(x.rt?' <span class="rost" title="Rostered across CBS leagues"><span class="src cb">CBS</span>'+x.rt[1]+'%'+(x.re?'':' rostered')+' <small>'+(x.rt[2]>0?'▲'+x.rt[2]:(x.rt[2]<0?'▼'+(-x.rt[2]):'±0'))+(x.re?'':' this wk')+'</small></span>':'')+'</td><td>'+(x.o==='FA'?'<span class="tag ok">free agent</span>':'<span class="tag warn">'+esc(x.o)+'</span>')+'</td>'+fc(x)+gc(g)+'<td>'+(db?'<button type="button" class="wl-rm" data-n="'+esc(n)+'" aria-label="Remove '+esc(x.s)+'">Remove</button>':'')+'</td></tr>'}
function key(n){return n.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')}
HEADS.forEach(function(h){[].forEach.call(h.querySelectorAll('th'),function(th,i){if(i>NX.length+4)return;var b=document.createElement('button');b.type='button';b.className='sortbtn';b.innerHTML=th.innerHTML+'<span class="arr"> ↕</span>';th.innerHTML='';th.appendChild(b);b.addEventListener('click',function(){if(sc===i)sd=-sd;else{sc=i;sd=i<2?1:-1}render()})})});
// Show all periods: the columns after the next few (class wx) hide unless #wwatch has wlexp
var EXP=document.getElementById('wwatch');function xset(o){if(EXP)EXP.classList.toggle('wlexp',o);[].forEach.call(document.querySelectorAll('#wwatch .wl-exp'),function(b){b.setAttribute('aria-pressed',String(o));b.textContent=o?'◂ Next '+NS+' periods':'Show all periods ▸'});try{localStorage.setItem('bbl-wlexp',o?'1':'')}catch(e){}}
[].forEach.call(document.querySelectorAll('#wwatch .wl-exp'),function(b){b.addEventListener('click',function(){xset(!(EXP&&EXP.classList.contains('wlexp')))})});
try{xset(localStorage.getItem('bbl-wlexp')==='1')}catch(e){xset(false)}
render();
// on your PC (cc\\serve.py): the same calls, saved to managers\\<team>\\watchlist.txt
async function localCol(){var m=document.querySelector('meta[name="bbl-team"]'),t=m&&m.content;if(!t||!/^https?:$/.test(location.protocol))return null;
var U='/api/watchlist',subs=[],names=null;
function emit(){var q={empty:false,metadata:{hasPendingWrites:false},docs:names.map(function(n){return {data:function(){return {name:n}}}})};subs.forEach(function(f){f(q)})}
async function call(a,n){var r=await fetch(U,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({team:t,action:a,name:n})});if(!r.ok)throw {code:'http-'+r.status};names=(await r.json()).names;emit()}
try{var r=await fetch(U+'?team='+encodeURIComponent(t),{cache:'no-store'});if(!r.ok)return null;names=(await r.json()).names}catch(e){return null}
return {doc:function(k){return {set:function(d){return call('add',d.name)},delete:function(){var n=names.concat(cur).filter(function(x){return key(x)===k})[0];return n?call('remove',n):Promise.resolve()}}},onSnapshot:function(ok){subs.push(ok);emit()}}}
(async function(){try{db=await claude.use('db')}catch(e){db=null}
if(db){col=db.collection('watchlist')}else{col=await localCol();if(col)db={local:true}}
if(!col){msg.textContent='Read-only here: open the page with “6 - Open Command Center” (or in Claude) to add or remove players.';inp.disabled=true;btn.disabled=true;syncQ();return}
col.onSnapshot(function(q){if(q.empty&&!q.metadata.hasPendingWrites){cur=W0.slice()}else{cur=q.docs.map(function(d){return (d.data()||{}).name}).filter(Boolean)}render()},function(e){msg.textContent='Live list unavailable ('+(e&&e.code||'error')+'); showing tonight’s snapshot.'});
})();
async function add(){var v=inp.value.trim();if(!v)return;var x=by[v.toLowerCase()];if(!x){msg.textContent='Pick a name from the suggestions ('+v+' isn’t in the CBS player list).';return}
if(cur.some(function(n){return n.toLowerCase()===x.n.toLowerCase()})){msg.textContent=x.s+' is already on your watchlist.';return}
btn.disabled=true;try{await col.doc(key(x.n)).set({name:x.n,added:new Date().toISOString()});inp.value='';msg.textContent='Added '+x.s+'. Tonight’s update adds him to Best adds and news alerts.'}catch(e){msg.textContent='Couldn’t save ('+(e&&e.code||'error')+').'}btn.disabled=false}
btn.addEventListener('click',add);inp.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();add()}});
on('click',function(e){var b=e.target.closest('.wfav');if(!b)return;var n=b.dataset.n;if(FAV[n])delete FAV[n];else FAV[n]=1;try{localStorage.setItem('bbl-wfav',JSON.stringify(FAV))}catch(er){}LAST=n;render();flash()});
on('click',async function(e){var b=e.target.closest('.wl-rm');if(!b||!col)return;b.disabled=true;try{await col.doc(key(b.dataset.n)).delete();msg.textContent='Removed '+b.dataset.n+'.'}catch(er){msg.textContent='Couldn’t remove ('+(er&&er.code||'error')+').';b.disabled=false}});
on('input',function(e){var i=e.target.closest('.wif-in');if(!i)return;setv(i.dataset.n,parseFloat(i.value));
if(dfp&&dfp.contains(i)){var d=dx(),w=gi(d.k,fv(d));render(true);dfp.querySelector('.wif-v').textContent=fv(d);dfp.querySelector('.wl-dw').textContent='worth '+f(Math.round(w[NX.length]))+' reg. season + '+f(Math.round(w[NX.length+1]))+' playoffs';dfp.classList.toggle('wif',fv(d)!==d.f);return}
var x=by[i.dataset.n.toLowerCase()],tr=i.closest('tr'),td=i.closest('td'),v=fv(x);
[].forEach.call(tr.querySelectorAll('.gv'),function(c){c.remove()});td.insertAdjacentHTML('afterend',gc((tr.dataset.ir!=null?egi(x,+tr.dataset.ir):eg(x.n,x))||[]));tr.classList.toggle('wif',v!==x.f);td.querySelector('.wif-v').textContent=v;[].forEach.call(td.querySelectorAll('.wif-c'),function(b){b.setAttribute('aria-pressed',String(+b.dataset.v===v))})});
function shut(){if(OPEN!==null){if(OPEN.indexOf('drop:')){LAST=OPEN}OPEN=null;render();flash()}}
function edit(n){OPEN=n;render();var p=document.querySelector('#wwatch .wif-pop'),i=p&&p.querySelector('.wif-in');if(!p)return;
var s=p.closest('.scroll');if(s&&p.getBoundingClientRect().bottom>s.getBoundingClientRect().bottom)p.classList.add('up');i.focus();i.select()}
on('keydown',function(e){if(e.target.closest('.wif-in')&&(e.key==='Enter'||e.key==='Escape')){e.preventDefault();shut()}});
on('click',function(e){var b=e.target.closest('.wif-c,.wif-r,.wif-v');if(!b)return;var n=b.dataset.n;
if(b.classList.contains('wif-v')){var k=(b.dataset.d?'drop:':'')+n;if(OPEN===k)shut();else edit(k);return}
setv(n,b.classList.contains('wif-r')?null:parseFloat(b.dataset.v));if(!b.dataset.d)LAST=n;OPEN=null;render();flash()});
document.addEventListener('click',function(e){if(OPEN!==null&&e.target.isConnected&&!e.target.closest('.wif-td'))shut()});   // isConnected: the clicked button may have just been redrawn
// one reset per table: free agents, or players on a roster (yours and other managers')
function grp(x){return x&&x.ir?'ir':(x&&x.o!=='FA'?'ro':'fa')}
[].forEach.call(document.querySelectorAll('#wwatch .wif-all'),function(b){b.addEventListener('click',function(){Object.keys(WIF).forEach(function(n){if(grp(by[n.toLowerCase()])===b.dataset.g)delete WIF[n]});wsave();OPEN=null;render()})});
})();</script>""".replace('__PL__',json.dumps(PL)).replace('__W0__',json.dumps(watch)).replace('__NX__',json.dumps(NA)).replace('__NS__',json.dumps(len(NX))).replace('__ST__',json.dumps(short(STREAM))).replace('__DN__',json.dumps(DROPS)).replace('__IRN__',json.dumps(IRP)).replace('__IRG__',json.dumps([ALT[d]['ir'] for d in DROPS]))
WIFCSS="""<style>.wif-td{position:relative;white-space:nowrap}
.wif-v{font:inherit;font-variant-numeric:tabular-nums;color:inherit;background:none;border:0;padding:0;cursor:pointer;border-bottom:1px dotted var(--muted,#94a3b8)}
.wif-v:hover,.wif-v[aria-expanded="true"]{color:var(--accent,#2563eb);border-bottom-color:currentColor}
.wif-r{font:inherit;font-size:.8rem;line-height:1;margin-left:4px;padding:1px 4px;border:1px solid var(--line,#cbd5e1);border-radius:4px;background:none;color:var(--muted,#64748b);cursor:pointer}.wif-r:hover{color:var(--accent,#2563eb)}
.wif-pop{position:absolute;right:0;top:100%;z-index:5;display:flex;gap:4px;align-items:center;padding:6px;background:var(--panel,#fff);border:1px solid var(--line,#cbd5e1);border-radius:8px;box-shadow:0 6px 18px rgba(0,0,0,.14)}.wif-pop.up{top:auto;bottom:100%}
.wl-dfp{display:inline-flex;flex-wrap:wrap;gap:4px 6px;align-items:baseline;margin-left:10px}.wl-dfp .wif-pop{left:0;right:auto}.wl-dfp.wif .wif-v{color:#2563eb;font-weight:600}
.wif-in{width:4.4rem;font:inherit;font-variant-numeric:tabular-nums;text-align:right;padding:3px 6px;border:1px solid var(--accent,#2563eb);border-radius:6px;background:transparent;color:inherit}
.wif-c{font:inherit;font-size:.72rem;padding:2px 7px;border:1px solid var(--line,#cbd5e1);border-radius:999px;background:transparent;color:inherit;cursor:pointer}
.wif-c[aria-pressed="true"]{background:#2563eb;border-color:#2563eb;color:#fff}.wif-c b{font-weight:600}
.wif-all{font:inherit;font-size:.78rem;font-weight:600;letter-spacing:normal;text-transform:none;margin-left:10px;padding:2px 10px;border:1px solid #2563eb;border-radius:999px;background:none;color:#2563eb;cursor:pointer;white-space:nowrap;vertical-align:middle}
.wif-all:disabled{opacity:.4;cursor:default}
.wl-exp{font:inherit;font-size:.78rem;font-weight:600;letter-spacing:normal;text-transform:none;margin-left:10px;padding:2px 10px;border:1px solid var(--accent,#2563eb);border-radius:999px;background:none;color:var(--accent,#2563eb);cursor:pointer;white-space:nowrap;vertical-align:middle}.wl-exp[aria-pressed="true"]{background:var(--accent,#2563eb);color:#fff}
#wwatch:not(.wlexp) .wx{display:none}
#wwatch.wlexp table td:first-child,#wwatch.wlexp table th:first-child{position:sticky;left:0;z-index:1;background:var(--panel);min-width:230px}#wwatch.wlexp table th:first-child{z-index:2}#wwatch.wlexp tr.wfavr>td:first-child{background:linear-gradient(color-mix(in srgb,#eab308 13%,transparent) 0 0),var(--panel)}#wwatch.wlexp tr.wif>td:first-child{background:linear-gradient(color-mix(in srgb,#2563eb 8%,transparent) 0 0),var(--panel)}
tr.wif .wif-v,tr.wif td.gv{color:#2563eb;font-weight:600}
.wfav{font:inherit;font-size:1.05rem;line-height:1;padding:0 5px 0 0;border:0;background:none;color:var(--muted,#94a3b8);cursor:pointer;vertical-align:-1px}.wfav:hover,.wfav.on{color:#eab308}
#wwatch tr.wfavr>td{background:color-mix(in srgb,#eab308 13%,transparent)}#wwatch tr.wfavr>td:first-child{box-shadow:inset 3px 0 0 #eab308}#wwatch tr.wfavr+tr:not(.wfavr)>td{border-top:2px solid color-mix(in srgb,#eab308 55%,transparent)}
#wwatch tr.wif>td{background:color-mix(in srgb,#2563eb 8%,transparent)}#wwatch tr.wif>td:first-child{box-shadow:inset 3px 0 0 #2563eb}
#wwatch tr.wlast>td{box-shadow:inset 0 2px 0 #f59e0b,inset 0 -2px 0 #f59e0b}#wwatch tr.wlast>td:first-child{box-shadow:inset 3px 0 0 #f59e0b,inset 0 2px 0 #f59e0b,inset 0 -2px 0 #f59e0b}
#wwatch tr.wjust>td{animation:wjust 2.2s ease-out}@keyframes wjust{0%,35%{background:color-mix(in srgb,#f59e0b 35%,transparent)}}
@media (prefers-reduced-motion:reduce){#wwatch tr.wjust>td{animation:none}}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) tr.wif .wif-v,:root:not([data-theme="light"]) tr.wif td.gv{color:#93c5fd}}:root[data-theme="dark"] tr.wif .wif-v,:root[data-theme="dark"] tr.wif td.gv{color:#93c5fd}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .wl-dfp.wif .wif-v{color:#93c5fd}}:root[data-theme="dark"] .wl-dfp.wif .wif-v{color:#93c5fd}</style>"""
WLH=f'<tr><th>Player</th><th>Status</th><th>FP/G</th>{"".join(f'<th{" class=wx" if i>=len(NX) else ""}>P{p} gain</th>' for i,p in enumerate(NA))}<th>Rest of reg. season</th><th>Playoffs</th><th></th></tr>'
wlpane=f"""{WIFCSS}<section><h2>Watchlist</h2>
{dropsel.replace('id="dropsel"','id="dropsel-wl"').replace('</select></label>','</select></label><span id="wl-dfp" class="wif-td wl-dfp"></span>',1)}
<div class="wl-add"><label for="wl-in" class="dropsel" style="margin:0">Add a player</label><input id="wl-in" list="wl-dl" placeholder="Start typing a name… e.g. Egor Demin" autocomplete="off"><datalist id="wl-dl"></datalist><button type="button" id="wl-add">Add</button></div>
<p class="small" id="wl-msg" role="status">Suggestions come from every player in the CBS player list. Changes save instantly; Best adds, news alerts and breakout checks pick them up in tonight's update.</p>
"""+(f'''<h3 class="sh">Your IR · if you activate him and drop <span class="dropname">{html.escape(short(STREAM))}</span><button type="button" class="wl-exp" aria-pressed="false" title="Show the gain for every regular-season period left">Show all periods ▸</button><button type="button" class="wif-all" data-g="ir" disabled title="Put your IR players back on their CBS projection">↺ Reset FP/G</button></h3>
<div class="scroll"><table><thead>{WLH}</thead><tbody id="wl-body3"></tbody></table></div>
<p class="small">Always shows every player in your IR slots. Gains = points you add by activating him and dropping the player in “If I drop”, his points count from his return date (set it with out_until in settings.txt), the dropped player&#39;s are lost right away, so a week he&#39;s still out can be negative. Negative means the player you&#39;d drop is worth more to you. Tap his FP/G to see the gains if he comes back better or worse than CBS projects.</p>
''' if IRP else '')+f"""
<h3 class="sh">Free agents<button type="button" class="wl-exp" aria-pressed="false" title="Show the gain for every regular-season period left">Show all periods ▸</button><button type="button" class="wif-all" data-g="fa" disabled title="Put every free agent back on his CBS projection">↺ Reset FP/G</button></h3>
<div class="scroll"><table><thead id="wl-head">{WLH}</thead><tbody id="wl-body"></tbody></table></div>
<div id="wl-rsec" hidden><h3 class="sh">On a roster · yours and other managers'<button type="button" class="wl-exp" aria-pressed="false" title="Show the gain for every regular-season period left">Show all periods ▸</button><button type="button" class="wif-all" data-g="ro" disabled title="Put every rostered player back on his CBS projection">↺ Reset FP/G</button></h3>
<div class="scroll"><table><thead id="wl-head2">{WLH}</thead><tbody id="wl-body2"></tbody></table></div>
<p class="small"><b>Another manager's player</b> (status shows who owns him): the gain if you got him for the player in “If I drop”, e.g. in a trade. <b>Yours</b>: what he's worth to your lineups, the points you'd lose without him; at a different FP/G, what he'd be worth playing at that level.</p></div>
<p class="small"><b>What if he keeps playing like this?</b> Tap a player's FP/G (his CBS projection) to change it: type a number, or pick <b>Last 3</b> or <b>Season</b> for what he's actually averaged (at his best slot, like CBS FP/G). His gains update right away, with your lineups and schedule re-run at that level, and show in blue. <b>↺</b> puts one player back on his CBS projection; <b>↺ Reset FP/G</b> next to each table's title puts everyone in that table back. <b>His FP/G</b> next to “If I drop” does the same for the player you'd drop: if he'll score more than CBS thinks, he's worth more to you, so every gain shrinks by that much (here only; Best adds still uses CBS). Your numbers stay in this browser.</p>
<p class="small"><b>☆ Favourites</b>: click the star next to a name to pin him to the top of his table (gold), whatever column you sort by; click again to unpin. Saved in this browser.</p>
<p class="small">Gains assume you drop <b class="dropname">{html.escape(short(STREAM))}</b>, the player picked in “If I drop” here or on Best adds (the two selectors stay in sync). They refresh nightly; a player added today gets his numbers after tonight's update.</p></section>"""+WLJS
rd=lambda f: open(f).read() if os.path.exists(f) else ''
# ---- League moves (tx.txt: the league's /transactions page, refreshed nightly)
TX=[]
MEKEY_TX=globals().get('ME','Oobsidoobsie')
if os.path.exists('tx.txt'):
    for l in open('tx.txt',encoding='utf-8'):
        f=l.rstrip('\n').split('|')
        if len(f)>=6:
            try: when=dt.datetime.strptime(f[0].replace(' ET','').strip(),'%m/%d/%y %I:%M %p')-dt.timedelta(hours=2)
            except ValueError: continue
            TX.append((when,)+tuple(f[1:6]))
_cut=dt.datetime.combine(TODAY,dt.time())-dt.timedelta(days=7)
_curopp=OPP[CUR-1].lstrip('@') if CUR<=21 else ''
def _isopp(t): return bool(_curopp) and (t==_curopp or (_curopp=='TINOLA' and 'ɪɴᴏʟᴀ' in t))
def _tnice(t): return "TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in t else t
_lmr=[]
for when,team,n,pos,nt,act in TX:
    if when<_cut: continue
    mine=team==ME; fl=[]; note=''
    if act.startswith('Added'):
        mv='➕ Claimed' if 'Waivers' in act else '➕ Added'
        if n in watch and not mine: fl.append('<span class="tag warn">⚠ was on your watchlist</span>')
        if _isopp(team): fl.append('<span class="tag warn">⚔ your opponent this week</span>')
        if n in INFO: note=f'CBS {INFO[n]["best"]:.1f} FP/G'
    elif act.startswith('Dropped'):
        mv='➖ Dropped'
        if n in FA and n in GA:
            g=tot(GA[n],REG); note=(f'<b>On waivers · +{g:.0f}</b> rest of season for you' if g>=25 else 'On waivers · little gain for you')
            if g>=100: fl.append('<span class="tag ok">worth a claim</span>')
        elif n in INFO and INFO[n]['own'].startswith('TAKEN:'): note='Since picked up by '+html.escape(_tnice(INFO[n]['own'][6:]))
        elif n in INFO and INFO[n]['own']=='MINE': note='Now on your roster'
        else: note='On waivers'
    else: mv=html.escape(act)
    _lmr.append((when,f'<tr><td class="num">{when.strftime("%a %b %-d")}<div class="small">{when.strftime("%-I:%M %p")}</div></td><td>{"<b>You</b>" if mine else html.escape(_tnice(team))}</td><td>{mv}</td>'
                f'<td><b>{html.escape(short(n))}</b> <span class="nbat" data-t="{nt}">{nt}</span> <span class="tm">{html.escape(pos)}</span></td><td>{note} {" ".join(fl)}</td></tr>'))
import zoneinfo as _zi
_now=dt.datetime.now(_zi.ZoneInfo('America/Edmonton')).replace(tzinfo=None)
_lmr.sort(key=lambda r:r[0],reverse=True)
_new=[r for r in _lmr if r[0]>=_now-dt.timedelta(hours=24)]
if _new: _lbl='last 24 hours'
elif _lmr:
    _d=_lmr[0][0].date(); _new=[r for r in _lmr if r[0].date()==_d]; _lbl='latest · '+_lmr[0][0].strftime('%a %b %-d')
_old=[r for r in _lmr if r not in _new]
_TH='<thead><tr><th>When (Calgary)</th><th>Team</th><th>Move</th><th>Player</th><th>What it means for you</th></tr></thead>'
if _lmr:
    leaguesec=f'<section class="brief"><h2>League moves · {_lbl}</h2><div class="scroll"><table>{_TH}<tbody>{"".join(h for _,h in _new)}</tbody></table></div>'
    if _old: leaguesec+=f'<details class="lmmore"><summary>Show the rest of the last 7 days ({len(_old)} more move{"s" if len(_old)!=1 else ""})</summary><div class="scroll"><table>{_TH}<tbody>{"".join(h for _,h in _old)}</tbody></table></div></details>'
    leaguesec+='<p class="small">From the league&#39;s transactions page, refreshed nightly after the waiver run. Waiver claims process at about 11:09 PM Calgary; a dropped player sits on waivers for 2 days before anyone can claim him.</p></section>'
else: leaguesec='<section class="brief"><h2>League moves</h2><p class="muted" style="margin:0">No adds or drops in the last 7 days.</p></section>'
def _build_usg():
    global usgsec
    # ---- Usage watch (Waivers -> Best adds): who is getting more of the ball
    def _own_lbl(n):
        o=INFO[n]['own'] if n in INFO else 'FA'
        return '<b style="color:#c2410c">★ yours</b>' if o=='MINE' else ('FA' if o=='FA' else html.escape(dname(dtn(o[6:]))))
    _ux=[(n,usg(n)) for n in INFO if usg(n)]
    _ris=sorted([(u['l3']-u['prior'],n,u) for n,u in _ux if u['prior'] is not None and u['min3']>=15 and u['l3']-u['prior']>=4],reverse=True)[:10]
    _fal=sorted([(u['prior']-u['l3'],n,u) for n,u in _ux if u['prior'] is not None and u['min3']>=12 and INFO[n]['own']=='MINE' and u['prior']-u['l3']>=4],reverse=True)[:5]
    _hif=sorted([(u['season'],n,u) for n,u in _ux if INFO[n]['own']=='FA' and u['min3']>=18 and u['g']>=1],reverse=True)[:10]
    def _urow(n,u,extra=''):
        t=INFO[n]['team']; pr='—' if u['prior'] is None else f"{u['prior']:.0f}%"
        return (f'<tr><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]} · {t}</span> {extra}</td><td>{_own_lbl(n)}</td>'
                f'<td class="num">{u["season"]:.0f}%</td><td class="num">{pr}</td><td class="num"><b>{u["l3"]:.0f}%</b></td><td class="num">{u["min3"]:.0f}</td><td class="num">{INFO[n]["best"]:.1f}</td></tr>')
    _UTH='<thead><tr><th>Player</th><th>Owner</th><th>Season</th><th>Before</th><th>Last 3</th><th>Min (L3)</th><th>CBS FP/G</th></tr></thead>'
    _ngames=len({r[0] for r in USGROWS})
    if USGROWS:
        _ub=''
        _ub+=('<h3>📈 Usage risers</h3>'+(f'<div class="scroll"><table>{_UTH}<tbody>'+''.join(_urow(n,u) for _,n,u in _ris)+'</tbody></table></div>' if _ris else
              '<p class="muted" style="margin:0">Needs 6+ games per player (last 3 vs the games before). Fills in during the first two weeks.</p>'))
        if _fal: _ub+='<h3>📉 Your players losing usage</h3><div class="scroll"><table>'+_UTH+'<tbody>'+''.join(_urow(n,u) for _,n,u in _fal)+'</tbody></table></div>'
        _ub+=('<h3>Highest-usage free agents</h3>'+(f'<div class="scroll"><table>{_UTH}<tbody>'+''.join(_urow(n,u,wbtn(n)) for _,n,u in _hif)+'</tbody></table></div>' if _hif else '<p class="muted" style="margin:0">None with 18+ minutes yet.</p>'))
        usgsec=(f'<details class="rep" id="usgwatch"><summary>📊 Usage watch (USG%) · {_ngames} night{"s" if _ngames!=1 else ""} of games</summary><section>{_ub}'
                '<p class="small">Usage rate (USG%) = the share of his team\'s plays a player finishes (a shot, free throws or a turnover) while he\'s on the floor; 20% is average, 26%+ is a featured scorer, 30%+ is a team\'s top option. '
                'A rise usually comes before the fantasy points do (a teammate out, a bigger role), so risers are early breakout signs; a drop on one of your players is an early sell or bench sign. '
                'Computed from ESPN box scores since opening night. Tags in the tables: 📈/📉 = last 3 games vs before (5+ point change), USG = season usage 26%+.</p></section></details>')
    else: usgsec=''
_build_usg()
def _build_deny():
    global denysec
    # ---- Deny your opponent (Rivals): free agents and NBA teams that would help this period's opponent most
    def _okey(p):
        on=OPP[p-1].lstrip('@') if p<=21 else None
        return next((k for k in OTH if k==on or (on=='TINOLA' and 'ɪɴᴏʟᴀ' in k)),None) if on else None
    _denyp=[p for p in (CUR,CUR+1,CUR+2) if p<=21 and p in P and _okey(p)]
    _dfa=sorted([n for n in FA if healthy(n)],key=lambda n:-INFO[n]['best'])[:40]
    denyhtml=''
    for p in _denyp:
        key=_okey(p); orost=OTH[key]; ob=ptot(orost,p); ds=P[p]
        othin=[d for d in ds if len(avail(orost,d))<5]
        res=[]
        for n in _dfa:
            r2=dict(orost); r2[n]=FA[n]; g=ptot(r2,p)-ob
            if g>=3: res.append((g,GA[n][p] if n in GA else 0,n))
        res.sort(reverse=True)
        trs=''.join(f'<tr><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span> {usgtag(n)}</td><td class="num">{sum(1 for d in ds if d in G[FA[n][0]])}</td><td class="num"><b>+{g:.0f}</b></td><td class="num">{mg:+.0f}</td><td class="num"><b>{g+mg:+.0f}</b></td><td>{wbtn(n)}</td></tr>' for g,mg,n in res[:6])
        tms=[]
        for t in G:
            c=sum(1 for d in othin if d in G[t])
            if c: tms.append((c,sum(1 for d in ds if d in G[t]),t))
        tms.sort(key=lambda x:(-x[0],-x[1],x[2]))
        def _tbest(t):
            fs=sorted([n for n in FA if FA[n][0]==t and healthy(n)],key=lambda n:-INFO[n]['best'])[:2]
            return ', '.join(f'{html.escape(short(n))} {INFO[n]["best"]:.0f}' for n in fs) or 'no free agents'
        tchips=' '.join(f'<span class="tchip">{t} <b>{c}</b><small>/{gm}</small><span class="cov">{_tbest(t)}</span></span>' for c,gm,t in tms[:5]) if tms else '<span class="muted">They have no empty slots this period</span>'
        m=next((x for x in MU if x['p']==p),None)
        wtxt=f' · you {m["wp"]*100:.0f}% to win' if m else ''
        denyhtml+=(f'<h3>P{p} · {pstart(p).strftime("%b %-d")}–{pend(p).strftime("%b %-d")} · vs {html.escape(dname(dtn(key)))}{wtxt}</h3>'
                   f'<p class="small" style="margin:0 0 6px">Their empty lineup slots: {len(othin)} day{"s" if len(othin)!=1 else ""}'+(' ('+', '.join(d.strftime('%a %-m/%-d') for d in othin)+')' if othin else '')+f'. NBA teams that fill them: {tchips}</p>'
                   +(f'<div class="scroll"><table><thead><tr><th>Free agent</th><th>Games</th><th>Helps them</th><th>Helps you</th><th>Swing</th><th></th></tr></thead><tbody>{trs}</tbody></table></div>' if trs else '<p class="muted">No free agent adds 3+ points to their lineup this period.</p>'))
    denysec=(f'<section><h2>Deny your opponent · P{_denyp[0]}–P{_denyp[-1]}</h2>{denyhtml}'
             '<p class="small">Helps them = BBL points the free agent would add to that opponent\'s best daily lineups in that period (their roster as it is now). Helps you = what he adds to yours over your stream slot. '
             'Swing = both together: claiming him takes those points from them and gives you yours. Team chips: NBA teams playing on the opponent\'s empty days (games on those days / games in the period) and their best free agents. '
             'Grabbing a player only to block a rival is worth it when the swing is big and you have a spare spot.</p></section>') if _denyp else ''
_build_deny()
def _build_mymoves():
    global mymovessec, mymoves_w
    # ---- Your recent moves: how your own adds/drops (last 7 days, from tx.txt) change his lineup value
    def _filled(r,p): return sum(min(5,len(avail(r,d))) for d in P.get(p,[]))
    def _wpx(a,b):
        sd=0.11*math.sqrt(a*a+b*b) or 1
        return 0.5*(1+math.erf((a-b)/(sd*math.sqrt(2))))
    _mine=[x for x in TX if x[1]==MEKEY_TX and x[0]>=_cut]
    _grp={}
    for when,team,n,pos,nt,act in _mine:
        _grp.setdefault(when.replace(second=0),[]).append((n,pos,nt,act))
    mymoves_rows=[]
    for when in sorted(_grp,reverse=True):
        L=_grp[when]
        adds=[x for x in L if x[3].startswith('Added')]; drops=[x for x in L if x[3].startswith('Dropped')]
        before=dict(R); miss=[]
        for n,_,_,_ in adds:
            before.pop(n,None)
        for n,_,_,_ in drops:
            if n in R: continue  # re-added since
            src=FA.get(n) or next((o[n] for o in OTH.values() if n in o),None)
            if src: before[n]=src
            else: miss.append(n)
        if not [x for x in adds if x[0] in R] and not drops: continue
        d={p:projleft(R,p)-projleft(before,p) for p in PER}
        nxt=CUR+1 if CUR+1<=21 else None
        reg=sum(d[p] for p in REG); po=sum(d[p] for p in PO)
        slots=_filled(R,CUR)-_filled(before,CUR)
        wtxt=''
        m=next((x for x in MU if x['p']==CUR),None)
        if m:
            w1=_wpx(m['mine'],m['opp_p']); w0=_wpx(m['mine']-d.get(CUR,0),m['opp_p'])
            wtxt=f'win odds vs {html.escape(dname(m["opp"]))}: {w0*100:.0f}% → <b>{w1*100:.0f}%</b>'
        def _f(v): return f'<b style="color:{"var(--good,#15803d)" if v>0.5 else ("var(--bad,#b91c1c)" if v<-0.5 else "inherit")}">{v:+,.0f}</b>'
        who=' · '.join([f'➕ <b>{html.escape(short(n))}</b> <span class="nbat" data-t="{nt}">{nt}</span> <span class="tm">{html.escape(pos)}</span>' for n,pos,nt,_ in adds]+
                       [f'➖ {html.escape(short(n))} <span class="nbat" data-t="{nt}">{nt}</span> <span class="tm">{html.escape(pos)}</span>' for n,pos,nt,_ in drops])
        cells=[(f'This period (P{CUR}, from today)' if CUR<=21 else 'This round',_f(d.get(CUR,0))+(f' <span class="small">· {slots:+d} lineup slots</span>' if slots else '')+(f'<div class="small">{wtxt}</div>' if wtxt else ''))]
        if nxt and nxt in d:
            s2=_filled(R,nxt)-_filled(before,nxt)
            cells.append((f'Next period (P{nxt})',_f(d[nxt])+(f' <span class="small">· {s2:+d} lineup slots</span>' if s2 else '')))
        if REG: cells.append(('Rest of regular season',_f(reg)))
        cells.append(('Playoffs (P22–24)',_f(po)))
        tot_=reg+po
        verdict=('A clear upgrade' if tot_>=60 else 'A small upgrade' if tot_>=10 else 'About even' if tot_>-10 else 'A downgrade on paper')
        if po<-10 and reg>10: verdict+=', but it costs you in the playoffs'
        elif po>10 and reg<-10: verdict+=': a playoff play that costs regular-season points'
        elif d.get(CUR,0)>=5 and reg-d.get(CUR,0)<0: verdict+=': it helps this week, then costs you'
        note=(' <span class="small">('+', '.join(html.escape(short(n)) for n in miss)+' isn\'t in the CBS projections, so he counts as 0)</span>') if miss else ''
        mymoves_rows.append((when,who,cells,verdict+'.'+note))
    if mymoves_rows:
        _h='<h2>Your moves · what they did to your lineup</h2>'
        _b=''
        for when,who,cells,verdict in mymoves_rows[:3]:
            _b+=(f'<div class="mymv" style="margin:0 0 12px"><div class="small">{when.strftime("%a %b %-d · %-I:%M %p")}</div><div style="margin:2px 0 6px">{who}</div>'
                 '<div class="scroll"><table><thead><tr>'+''.join(f'<th>{c}</th>' for c,_ in cells)+'</tr></thead><tbody><tr>'+''.join(f'<td class="num">{v}</td>' for _,v in cells)+'</tr></tbody></table></div>'
                 f'<p style="margin:6px 0 0"><b>{verdict}</b></p></div>')
        _foot='<p class="small">BBL points your best daily lineup gains (+) or loses (−) because of the move, compared with your roster before it. Counts games from today on, each player in his best slot, using CBS projections.</p>'
        mymovessec=f'<section class="brief" id="mymoves" style="scroll-margin-top:72px">{_h}{_b}{_foot}</section>'
        # Waivers → Best adds: a pointer to the Today section, not a second copy
        _w1=mymoves_rows[0]
        mymoves_w=(f'<p class="small" style="margin:0">Your last move ({_w1[0].strftime("%a %b %-d")}: {_w1[1]}): <b>{html.escape(_w1[3].split(".")[0])}</b>. '
                   '<a href="#mymoves" onclick="var b=document.querySelector(&#39;.tabs button[data-t=today]&#39;);if(b){b.click();setTimeout(function(){document.getElementById(&#39;mymoves&#39;).scrollIntoView({behavior:&#39;smooth&#39;})},50)}return false">'
                   'What your moves did → Today</a></p>')
    else:
        mymovessec=''; mymoves_w=''
_build_mymoves()
def _build_oddsmoves():
    # Moves in the last 7 days by you or by a manager you face in the next 3 periods, and what each did to your win odds.
    global oddsmovessec
    oddsmovessec=''
    def _wpx(a,b):
        sd=0.11*math.sqrt(a*a+b*b) or 1
        return 0.5*(1+math.erf((a-b)/(sd*math.sqrt(2))))
    MUP_={m['p']:m for m in MU}
    pers=[p for p in (CUR,CUR+1,CUR+2) if p in MUP_]
    if not pers: return
    grp={}
    for when,team,n,pos,nt,act in TX:
        if when<_cut: continue
        grp.setdefault((when.replace(second=0),team),[]).append((n,pos,nt,act))
    rowsh=[]
    for (when,team),L in sorted(grp.items(),key=lambda x:x[0][0],reverse=True):
        mine_=team==MEN or (MEN=='Oobsidoobsie' and team=='Oobsidoobsie')
        tk=None if mine_ else next((k for k in OTH if k==team),None)
        if not mine_ and not tk: continue
        hits=[p for p in pers if mine_ or MUP_[p]['key']==tk]
        if not hits: continue
        cur=R if mine_ else OTH[tk]
        before=dict(cur)
        for n,_,_,a in L:
            if a.startswith('Added'): before.pop(n,None)
        for n,_,_,a in L:
            if a.startswith('Dropped') and n not in cur:
                src=FA.get(n) or R.get(n) or next((o[n] for o in OTH.values() if n in o),None)
                if src: before[n]=src
        who=' · '.join(('➕ ' if a.startswith('Added') else '➖ ')+f'<b>{html.escape(short(n))}</b> <span class="tm">{nt}</span>' for n,_,nt,a in L)
        cells=[]   # one row per move; each period it touches is a line in the last three cells
        for p in hits:
            m=MUP_[p]; dlt=projleft(cur,p)-projleft(before,p)
            if abs(dlt)<0.5: continue
            if mine_: w0=_wpx(m['mine']-dlt,m['opp_p'])
            else: w0=_wpx(m['mine'],m['opp_p']-dlt)
            w1=m['wp']; ch=(w1-w0)*100
            col='var(--good,#15803d)' if ch>0.4 else ('var(--bad,#b91c1c)' if ch<-0.4 else 'inherit')
            cells.append((f'P{p} vs {html.escape(dname(dtn(m["opp"])))}{" (now)" if p==CUR else ""}',f'{"you" if mine_ else "them"} {dlt:+.0f}',
                          f'{w0*100:.0f}% → <b>{w1*100:.0f}%</b> <b style="color:{col}">({ch:+.0f})</b>'))
        if cells:
            col3=lambda j:''.join(f'<div style="white-space:nowrap">{c[j]}</div>' for c in cells)   # one line each, so the 3 cells line up
            rowsh.append(f'<tr><td class="num">{when.strftime("%a %b %-d")}<div class="small">{when.strftime("%-I:%M %p")}</div></td>'
                         f'<td>{"<b>You</b>" if mine_ else html.escape(dname(dtn(team)))}</td><td>{who}</td>'
                         f'<td>{col3(0)}</td><td class="num">{col3(1)}</td><td class="num">{col3(2)}</td></tr>')
    if not rowsh:
        oddsmovessec=('<section class="brief"><h2>Moves that changed your win odds</h2><p class="muted" style="margin:0">'
                      'No moves in the last 7 days by you or by the managers you face in '+', '.join(f'P{p}' for p in pers)+'.</p></section>')
        return
    oddsmovessec=('<section class="brief"><h2>Moves that changed your win odds</h2><div class="scroll"><table><thead><tr><th>When (Calgary)</th><th>Manager</th><th>Move</th>'
                  '<th>Matchup</th><th>Projection change</th><th>Your win odds</th></tr></thead><tbody>'+''.join(rowsh[:10])+'</tbody></table></div>'
                  '<p class="small">Your moves and moves by the managers you face in the next 3 periods (last 7 days). Projection change = BBL points the move adds to (or takes from) '
                  'that team\'s best daily lineups in that period, from today on. Win odds count points already scored this period plus the projection for the days left. '
                  'Moves by other managers don\'t change your odds until you play them.</p></section>')
_build_oddsmoves()
today=IRB+LOCKB
if rd('brief.html'): today+='<section class="brief"><h2>Daily briefing</h2>'+rd('brief.html')+'</section>'
today+=movessec
today+=mymovessec
today+=oddsmovessec
today+=leaguesec
today+=newssec
# nightly best/worst archive: nights/YYYYMMDD.html (first line <!--title:...-->); newest shown by default
nightsec=''
NIGHTS=[]
for f in sorted(glob.glob('nights/*.html'),reverse=True):
    t=open(f).read(); m=re.match(r'<!--title:(.*?)-->',t); NIGHTS.append((os.path.basename(f)[:-5],m.group(1) if m else os.path.basename(f)[:-5],t))
if not NIGHTS and rd('nightly.html'): NIGHTS=[('latest','Last night',rd('nightly.html'))]
LG=[]; LGI={}   # every embedded logo (data URI) once for the whole page: window.__LG, filled into <img data-lg> (end of file)
def lgi(u):
    if u not in LGI: LGI[u]=len(LG); LG.append(u)
    return LGI[u]
def lgsub(m): return f'data-lg="{lgi(m.group(1))}"'
def ztpl(i,b,plain):   # an archive night/report: a <template>; older ones are compressed at the end of the file (after the team tags etc.)
    return f'<template id="{i}"{"" if plain else " data-z"}>{b}</template>'
if NIGHTS:
    tpls=''.join(ztpl(f'nt-{k}',re.sub(r'src="(data:image/[^"]+)"',lgsub,b),j==0) for j,(k,_,b) in enumerate(NIGHTS))
    opts=''.join(f'<option value="{k}">{html.escape(t)}</option>' for k,t,_ in NIGHTS)
    NJS='<script>(function(){var L=window.__LG;var s=document.getElementById("nightsel"),box=document.getElementById("nightbox");function show(k){window.__tpl("nt-"+k).then(function(t){if(!t||s.value!==k)return;box.innerHTML="";box.appendChild(t.content.cloneNode(true));[].forEach.call(box.querySelectorAll("img[data-lg]"),function(i){i.src=L[+i.dataset.lg]})})}s.addEventListener("change",function(){show(s.value)});show(s.value)})();</script>'
    nightsec=f'<section class="brief night"><h2>Best &amp; worst performances</h2><label class="dropsel">Date <select id="nightsel">{opts}</select></label><div id="nightbox"></div>{tpls}</section>'+NJS
if not today: today='<p class="muted">Nothing yet today.</p>'
mug=''
IRNOTE=('<p class="small" style="margin:8px 0 0">IR returns: '+' · '.join(f'<b>{html.escape(short(n))}</b> counts from {d0.strftime("%b %-d")} in place of {html.escape(short(x))}{" (stream slot)" if x==STREAM else ""}' for x,(d0,n) in sorted(IRDROP.items(),key=lambda kv:kv[1]))
        +'. Return dates: ⚙️ Your roster settings at the top.</p>') if IRDROP else ''
if MU: mug+='<section><h2>Scoring preview</h2>'+mcard(MU[0],True)+IRNOTE+'</section>'
if len(MU)>1: mug+=f'<section><h2>Next · P{MU[1]["p"]}</h2>'+mcard(MU[1],False,True)+'</section>'
if len(MU)>2: mug+=f'<section><h2>After that</h2><div class="mgrid">'+''.join(mcard(m,False) for m in MU[2:4])+'</div><p class="small">All periods are on the Season tab → H2H schedule.</p></section>'
# This period's two ledger rows leave out the scoring preview and win odds: the matchup cards above show them (matchup-adjusted)
def _tprow(r): return re.sub(r'<td class="minicell">.*?</td>|<div class="winp [^"]*">.*?</div><div class="wsum">.*?</div>','',r,flags=re.S)
thisp=IRB+LOCKB+mug+f"""<section><h2>P{p0} · {pstart(p0).strftime("%b %-d")} – {pend(p0).strftime("%b %-d")}</h2>
{dropsel_tp}
<div class="scroll"><table class="ledger"><thead><tr><th>P</th><th>Dates · opponent</th><th>Slots used</th><th>Thin days · players playing</th><th>Best adds if you drop <span class="dropname">{html.escape(short(STREAM))}</span> · your watchlist</th><th>Best teams to stream</th></tr></thead><tbody>{_tprow(rows[0])}</tbody></table></div></section>"""
if len(rows)>1: thisp+=f"""<section><h2>Next up · P{PER[1]}</h2><div class="scroll"><table class="ledger"><thead><tr><th>P</th><th>Dates · opponent</th><th>Slots used</th><th>Thin days · players playing</th><th>Best adds if you drop <span class="dropname">{html.escape(short(STREAM))}</span> · your watchlist</th><th>Best teams to stream</th></tr></thead><tbody>{_tprow(rows[1])}</tbody></table></div></section>"""
import glob
REPS=[]
for f in sorted(glob.glob('reports/P*.html'),reverse=True):
    t=open(f).read(); m=re.match(r'<!--title:(.*?)-->',t); REPS.append((m.group(1) if m else os.path.basename(f)[:-5],t,os.path.basename(f)[:-5]))
if REPS: thisp+=(f'<section class="brief"><h2>Latest period report · {html.escape(REPS[0][0])}</h2><p style="margin:0">'
                 f'<a href="#repsel" class="replink" data-rep="repsec" data-k="{REPS[0][2]}">📊 Open the {html.escape(REPS[0][0])} report →</a>'
                 '<span class="small"> Top 10 best and worst of the period, on Season → Reports with all the older ones.</span></p></section>')
repane=''
if REPS:
    ropts=''.join(f'<option value="{k}">{html.escape(t)}</option>' for t,_,k in REPS)
    rtpl=''.join(ztpl(f'rt-{k}',b,j==0) for j,(_,b,k) in enumerate(REPS))
    RJS='<script>(function(){var s=document.getElementById("repsel"),box=document.getElementById("repbox");if(!s||!box)return;function show(k){window.__tpl("rt-"+k).then(function(t){if(!t||s.value!==k)return;box.innerHTML="";box.appendChild(t.content.cloneNode(true))})}s.addEventListener("change",function(){show(s.value)});show(s.value)})();</script>'
    repane=f'<div class="brief night" id="repsec" style="scroll-margin-top:72px"><label class="dropsel">Period <select id="repsel">{ropts}</select></label><p class="small" style="margin:0 0 8px">{len(REPS)} report{"s" if len(REPS)!=1 else ""} so far · newest first. Pick any period to view its report.</p><div id="repbox"></div>{rtpl}</div>'+RJS
if NIGHTS:
    k0,t0,_=NIGHTS[0]
    rl=(f'<a href="#repsel" class="replink" data-rep="repsec" data-k="{REPS[0][2]}">📊 Period report · {html.escape(REPS[0][0])} →</a>') if REPS else ''
    today+=f'<section class="brief night"><h2>Best &amp; worst · {html.escape(t0)}</h2>{benchline}<div class="todayrep">{rl}<a href="#nightsel" class="replink" data-rep="nightsel">📅 Other dates →</a><button type="button" id="dltop10" hidden data-k="{k0}" style="font:600 .85rem var(--body);color:#fff;background:var(--accent);border:1px solid var(--accent);border-radius:999px;padding:6px 14px;cursor:pointer">📸 Top 10 images</button></div><div id="todaynight" data-k="{k0}"></div></section>'
    today+='<style>#t10m[hidden],#dltop10[hidden],#t10b[hidden],#t10w[hidden],#t10save[hidden]{display:none!important}</style>'
    today+='<div id="t10m" hidden style="position:fixed;inset:0;z-index:50;background:rgba(7,11,36,.97);display:flex;flex-direction:column;padding:max(12px,env(safe-area-inset-top)) 12px max(12px,env(safe-area-inset-bottom))"><div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 auto 10px;max-width:760px;width:100%"><span style="flex:1 1 auto;display:flex;gap:6px"><button type="button" id="t10b" style="font:600 .9rem var(--body);color:#fff;background:#f97316;border:1px solid #f97316;border-radius:999px;padding:8px 14px;cursor:pointer;min-height:40px">🔥 Best</button><button type="button" id="t10w" style="font:600 .9rem var(--body);color:#fff;background:none;border:1px solid rgba(255,255,255,.5);border-radius:999px;padding:8px 14px;cursor:pointer;min-height:40px">🤮 Worst</button></span><button type="button" id="t10save" style="font:600 .9rem var(--body);color:#fff;background:var(--accent);border:1px solid var(--accent);border-radius:999px;padding:8px 16px;cursor:pointer;min-height:40px">⬇️ Save</button><button type="button" id="t10zoom" style="font:600 .9rem var(--body);color:#fff;background:none;border:1px solid rgba(255,255,255,.5);border-radius:999px;padding:8px 16px;cursor:pointer;min-height:40px">🔍 Full size</button><button type="button" id="t10close" style="font:600 .9rem var(--body);color:#fff;background:none;border:1px solid rgba(255,255,255,.5);border-radius:999px;padding:8px 16px;cursor:pointer;min-height:40px">✕ Close</button><span id="dlmsg" style="color:#e2e8f0;font-size:.85rem;width:100%"></span></div><div id="t10box" style="flex:1;overflow:auto;-webkit-overflow-scrolling:touch;text-align:center"><img id="t10img" alt="Top 10 of the night" style="max-width:min(100%,760px);height:auto;border-radius:10px"></div></div>\n<script>(async function(){var b=document.getElementById("dltop10"),M=document.getElementById("t10m"),I=document.getElementById("t10img"),m=document.getElementById("dlmsg"),Z=document.getElementById("t10zoom"),S=document.getElementById("t10save"),TB=document.getElementById("t10b"),TW=document.getElementById("t10w");if(!b||!M)return;var L=window.__T10||null,U={},B={};function ok(u){return new Promise(function(r){var x=new Image();x.onload=function(){r(true)};x.onerror=function(){r(false)};x.src=u})}if(L){for(var k0 in L)if(L[k0]&&await ok(L[k0]))U[k0]=L[k0]}else if(window.claude){async function get(u){try{var r=await fetch(u+"?k="+b.dataset.k,{cache:"no-store"});return r&&r.ok?await r.blob():null}catch(e){return null}}B={best:await get("top10.png"),worst:await get("top10_worst.png")};for(var k1 in B)if(B[k1])U[k1]=URL.createObjectURL(B[k1])}if(!U.best&&!U.worst)return;var cur=U.best?"best":"worst";if(!U.worst)TW.hidden=true;if(!U.best)TB.hidden=true;function show(k){cur=k;I.src=U[k];I.alt=k=="best"?"Top 10 performances":"Top 10 worst performances";var a=k=="best"?TB:TW,o=k=="best"?TW:TB;a.style.background=k=="best"?"#f97316":"#a855f7";a.style.borderColor=a.style.background;o.style.background="none";o.style.borderColor="rgba(255,255,255,.5)";m.textContent=""}TB.addEventListener("click",function(){show("best")});TW.addEventListener("click",function(){show("worst")});show(cur);var d=null;if(!L){try{d=await window.claude.use("downloads")}catch(e){}if(!d)S.hidden=true}b.hidden=false;var big=false;function zoom(v){big=v;I.style.maxWidth=v?"none":"min(100%,760px)";I.style.width=v?"1080px":"";Z.textContent=v?"↔️ Fit to screen":"🔍 Full size"}b.addEventListener("click",function(){m.textContent="";zoom(false);M.hidden=false;document.body.style.overflow="hidden"});function close(){M.hidden=true;document.body.style.overflow=""}document.getElementById("t10close").addEventListener("click",close);M.addEventListener("click",function(e){if(e.target===M||e.target.id==="t10box")close()});document.addEventListener("keydown",function(e){if(e.key==="Escape"&&!M.hidden)close()});Z.addEventListener("click",function(){zoom(!big)});var fn=function(){return (cur=="best"?"Top 10 Best - Mobile Friendly ":"Top 10 Worst - Mobile Friendly ")+b.dataset.k+".png"};S.addEventListener("click",async function(){m.textContent="";if(L){var a=document.createElement("a");a.href=U[cur];a.download=fn();document.body.appendChild(a);a.click();a.remove();m.textContent="Also saved in the output folder for this date.";return}try{await d.save({filename:fn(),data:B[cur]});m.textContent="Saved ✓"}catch(e){if(e&&e.code==="declined")return;m.textContent=(e&&e.code==="rate_limited")?"One moment, then try again.":"Saving isn\'t available here. Long-press the image to save it instead.";if(!(e&&e.code==="rate_limited"))S.hidden=true}})})();</script>'
    NJS2='<script>document.addEventListener("DOMContentLoaded",function(){var b=document.getElementById("todaynight");if(b){var t=document.getElementById("nt-"+b.dataset.k);if(t){b.appendChild(t.content.cloneNode(true));var L=window.__LG||[];[].forEach.call(b.querySelectorAll("img[data-lg]"),function(i){i.src=L[+i.dataset.lg]})}}'+'[].forEach.call(document.querySelectorAll(".replink"),function(a){a.addEventListener("click",function(e){e.preventDefault();var sb=document.querySelector(".tabs button[data-t=season]");if(sb)sb.click();if(window.__sub)window.__sub("srep");if(a.dataset.k){var rs=document.getElementById("repsel");if(rs){rs.value=a.dataset.k;rs.dispatchEvent(new Event("change"))}}var el=document.getElementById(a.dataset.rep);if(el){if(el.tagName==="DETAILS")el.open=true;setTimeout(function(){el.scrollIntoView({behavior:"smooth",block:"start"})},50)}})})});</script>'
    today+=NJS2
repane=repane or '<p class="muted">No period reports yet. The first one (P1) is built Sun Oct 25.</p>'

headtxt=open('head.html',encoding='utf-8').read().replace('· Oobsidoobsie</title>',f'· {html.escape(MEDISP)}</title>').replace('.muted{color:var(--muted)}','.muted{color:var(--muted)}\n.brief{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 18px}.brief h3{font:600 1rem var(--display);text-transform:uppercase;letter-spacing:.03em;margin:12px 0 4px;color:var(--accent)}.night h3{color:var(--fg)}.night table th,.night table td{color:var(--fg)!important;border-color:var(--line)!important}.brief ul{margin:0;padding-left:18px}.brief li{margin:2px 0}\n.winp{font:700 .95rem var(--display);margin-top:4px;letter-spacing:.02em}.winp.better{color:var(--ok)}.winp.worse{color:var(--bad)}.winp.even{color:var(--warn)}.wsum{font-size:.78rem;color:var(--muted);max-width:30ch;line-height:1.35}\n.insights{margin-top:16px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 18px;max-width:900px}.insights h3{font:600 1.1rem var(--display);text-transform:uppercase;letter-spacing:.03em;margin:0 0 6px;color:var(--accent)}.insights ul{margin:4px 0 10px;padding-left:18px}.insights li{margin:3px 0}.insights p{margin:6px 0}\n.oslot{font:600 .72rem var(--mono);margin-top:3px;white-space:nowrap}.oslot.better{color:var(--ok)}.oslot.worse{color:var(--bad)}.oslot.even{color:var(--muted)}\n.flag{font:600 .66rem var(--mono);color:var(--accent);margin-left:4px;white-space:nowrap}\n.tabs{position:sticky;top:0;z-index:5;display:flex;gap:4px;overflow-x:auto;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line)}.tabs button{font:600 1rem var(--display);letter-spacing:.04em;text-transform:uppercase;background:none;border:1px solid transparent;border-radius:6px;color:var(--muted);padding:8px 14px;cursor:pointer;white-space:nowrap;min-height:40px}.tabs button[aria-selected=true]{color:var(--fg);background:var(--panel);border-color:var(--line)}.tabs button:focus-visible{outline:2px solid var(--accent)}.wrap>*,.pane>*{min-width:0}.pane{display:grid;gap:24px;min-width:0}.subpane{min-width:0;display:grid;gap:24px}.subpane>section{min-width:0}#dropsel{max-width:100%}.brief{overflow-x:auto}.pane[hidden]{display:none}\n.tags{margin-top:3px;display:flex;flex-wrap:wrap;gap:4px}.tag{font:600 .66rem var(--mono);padding:1px 6px;border-radius:999px;background:var(--pobg);color:var(--fg);white-space:nowrap}.tag.hot{background:var(--okbg);color:var(--ok)}.tag.warn{background:var(--warnbg);color:var(--warn)}.tag.ok{background:var(--okbg);color:var(--ok)}.tag.bad{background:var(--badbg);color:var(--bad)}.num.hi{font-weight:700;color:var(--ok)}.mcard{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;min-width:0}.mcard.big{padding:20px 22px}.big .mrow{grid-template-columns:minmax(110px,1fr) auto minmax(120px,2.4fr) auto minmax(110px,1fr)}.mhead{font:600 .7rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;text-align:center}.mrow{display:grid;grid-template-columns:76px auto minmax(50px,1fr) auto 76px;align-items:center;gap:10px}.mteam{display:flex;flex-direction:column;align-items:center;gap:4px;text-align:center;min-width:0}.mteam b{font:700 .78rem var(--display);letter-spacing:.01em;overflow-wrap:normal;word-break:normal;line-height:1.15}.big .mteam b{font-size:1.25rem}.mlogo{border-radius:50%;object-fit:cover;display:block}.mlogo.ph{background:var(--line)}.msc{font:700 1.5rem var(--display);font-variant-numeric:tabular-nums}.big .msc{font-size:3.2rem;line-height:1}.msc.win{color:var(--ok)}.msc.lose{color:var(--muted);opacity:.7}.mbar{display:flex;align-items:center;gap:4px}.mbar .half{flex:1;height:14px;background:var(--line);display:flex;overflow:hidden}.big .mbar .half{height:34px}.mbar .half.l{justify-content:flex-end}.mbar .fill{height:100%;background:var(--ok)}.mbar .ev{font:600 .55rem var(--mono);color:var(--muted);writing-mode:vertical-rl;transform:rotate(180deg)}.mbar .ev.on{color:var(--fg)}.mscale{display:flex;gap:18px;margin-top:6px}.mscale>div{flex:1;display:flex;justify-content:space-between;font:600 .6rem var(--mono);letter-spacing:.04em;color:var(--muted)}.mscale .on{color:#2563eb}.mfoot{text-align:center;margin-top:8px;font-size:.8rem;color:var(--muted)}.big .mfoot{font-size:.95rem}.mfoot .winp{display:inline;font-size:inherit}.mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}@media (max-width:560px){.mrow{gap:5px;grid-template-columns:60px auto minmax(30px,1fr) auto 60px}.msc{font-size:1.2rem}.mteam b{font-size:.7rem}.mcard{padding:10px}.big .msc{font-size:2.2rem}.big .mrow,.mid .mrow{gap:6px;grid-template-columns:80px auto minmax(40px,1fr) auto 80px}.mid .msc{font-size:1.6rem}.mscale{display:none}.big .mteam b{font-size:.95rem}}.sortbtn{all:unset;cursor:pointer;font:inherit;letter-spacing:inherit;text-transform:inherit;color:inherit;display:inline-block;padding:4px 0}.sortbtn:hover{color:var(--fg)}.sortbtn:focus-visible{outline:2px solid var(--accent)}.sortbtn .arr{opacity:.7}th[aria-sort=ascending] .sortbtn,th[aria-sort=descending] .sortbtn{color:var(--accent)}.irhead td{font:600 .7rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);background:var(--bg);padding-top:14px}.irrow{background:var(--badbg)}.subtabs{display:flex;flex-wrap:wrap;gap:6px}.wq{font:600 .7rem var(--mono);letter-spacing:.03em;text-transform:uppercase;border:1px solid var(--line);background:none;color:var(--muted);border-radius:999px;padding:1px 8px;min-height:24px;margin-left:6px;cursor:pointer;vertical-align:middle;white-space:nowrap}.wq:hover:not(:disabled){color:var(--fg);border-color:var(--fg)}.wq.on{color:#c2410c;border-color:transparent;cursor:default}.wq:disabled:not(.on){opacity:.5;cursor:default}.subtabs button{font:600 .8rem var(--mono);letter-spacing:.06em;text-transform:uppercase;padding:7px 12px;border-radius:999px;border:1px solid var(--line);background:none;color:var(--muted);cursor:pointer;min-height:36px;white-space:nowrap}.subtabs button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}.subpane{display:grid;gap:24px;min-width:0}.subpane[hidden]{display:none}.mcard.mid{padding:16px 18px}@media (min-width:561px){.mid .mrow{grid-template-columns:120px auto minmax(80px,1fr) auto 120px;max-width:820px;margin:0 auto}}@media (min-width:561px){.mid .msc{font-size:2.2rem}}.mid .mteam b{font-size:1rem}.mid .mbar .half{height:22px}.ledger{min-width:1100px}.minicell{min-width:190px}@media (max-width:560px){.big .mrow,.mid .mrow{grid-template-columns:62px auto minmax(24px,1fr) auto 62px;gap:5px}.big .mlogo,.mid .mlogo{width:44px;height:44px}.big .msc{font-size:1.9rem}.mid .msc{font-size:1.4rem}.big .mteam b,.mid .mteam b{font-size:.75rem}}.mini-s{display:flex;align-items:center;gap:5px;font:700 .95rem var(--display);font-variant-numeric:tabular-nums}.mini-s .w{color:var(--ok)}.mini-s .l{color:var(--muted)}.mini-s .vs{font:600 .6rem var(--mono);color:var(--muted)}.mini .mbar{margin-top:4px}.mini .mbar .half{height:8px}.mini-l{font:600 .66rem var(--mono);color:var(--muted);margin-top:2px;text-transform:uppercase;letter-spacing:.04em}.ledger tr.cur{background:color-mix(in srgb,#2563eb 9%,transparent);box-shadow:inset 0 3px 0 #2563eb,inset 0 -3px 0 #2563eb}.ledger tr.cur td{border-bottom-color:transparent}.nowtag{display:inline-block;font:700 .62rem var(--mono);letter-spacing:.08em;color:#fff;background:#2563eb;border-radius:4px;padding:2px 5px;margin-left:6px;vertical-align:middle}.ledger .pn .nowtag{display:block;margin:4px 0 0;width:max-content}.curjump{font:600 .8rem var(--mono);color:#2563eb;text-decoration:none;margin-left:10px}.vrow{text-align:center;margin-bottom:6px}.vpill{display:inline-block;font:700 .72rem var(--mono);letter-spacing:.06em;padding:3px 9px;border-radius:999px;color:#fff}.big .vpill{font-size:.95rem;padding:5px 14px}.mid .vpill{font-size:.82rem;padding:4px 11px}.vpill.good{background:#15803d}.vpill.bad{background:#b91c1c}.vpill.even{background:#b45309}.mcard.o-good{background:var(--okbg);border-color:color-mix(in srgb,var(--ok) 45%,transparent);border-top:5px solid var(--ok)}.mcard.o-bad{background:var(--badbg);border-color:color-mix(in srgb,var(--bad) 45%,transparent);border-top:5px solid var(--bad)}.mcard.o-even{background:var(--warnbg);border-color:color-mix(in srgb,var(--warn) 45%,transparent);border-top:5px solid var(--warn)}.o-bad .mbar .fill{background:var(--bad)}.o-even .mbar .fill{background:var(--warn)}.o-bad .msc.win{color:var(--bad)}.o-even .msc.win{color:var(--warn)}.o-bad .mbar .half,.o-good .mbar .half,.o-even .mbar .half{background:color-mix(in srgb,var(--fg) 10%,transparent)}.mini .vpill{font-size:.6rem;padding:2px 6px;margin-bottom:4px}.mini.o-bad .mini-s .w{color:var(--bad)}.mini.o-even .mini-s .w{color:var(--warn)}.mini.o-bad .mbar .fill{background:var(--bad)}.mini.o-even .mbar .fill{background:var(--warn)}.mcard.curcard{outline:3px solid #2563eb;outline-offset:3px;box-shadow:none}details.rep{margin:0 0 10px}details.rep>summary{font:600 1.05rem var(--display);letter-spacing:.03em;text-transform:uppercase;padding:10px 14px;background:var(--panel);border:1px solid var(--line);border-radius:8px;cursor:pointer}details.rep[open]>summary{border-radius:8px 8px 0 0}details.rep>.brief{border-top:none;border-radius:0 0 8px 8px}li.inj{background:var(--badbg);border-left:4px solid var(--bad);padding:6px 8px;border-radius:4px;list-style:none;margin:6px 0 6px -18px}.ibadge{display:inline-block;font:700 .66rem var(--mono);letter-spacing:.06em;text-transform:uppercase;background:var(--bad);color:#fff;padding:2px 6px;border-radius:4px;margin-right:4px}.ibadge.sev{background:#7f1d1d}.lockban{display:flex;gap:14px;align-items:center;background:#b45309;color:#fff;border-radius:10px;padding:16px 20px;box-shadow:0 0 0 3px color-mix(in srgb,#b45309 30%,transparent)}.lk-ic{font-size:2.2rem;line-height:1;display:inline-block;transform-origin:50% 20%;animation:lkring 6s ease-in-out infinite}@keyframes lkring{0%,14%,100%{transform:rotate(0)}2%{transform:rotate(9deg)}4%{transform:rotate(-8deg)}6%{transform:rotate(6deg)}8%{transform:rotate(-5deg)}10%{transform:rotate(3deg)}12%{transform:rotate(-2deg)}}@media (prefers-reduced-motion:reduce){.lk-ic{animation:none}}.lk-h{font:700 .78rem var(--mono);letter-spacing:.1em;text-transform:uppercase;opacity:.9}.lk-t{font:700 1.6rem var(--display);letter-spacing:.02em;line-height:1.1;margin:2px 0}.lk-s{font-size:.9rem;opacity:.95}.tipstrip{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--muted);border-radius:8px;padding:8px 14px}.lockban+.tipstrip{margin-top:-14px}.tp-h{font:600 .72rem var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}.tp-l{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:4px;font-size:.88rem}.tp-g b{font-variant-numeric:tabular-nums}li.inj.mine{border-left-width:7px;border:2px solid var(--bad);border-left:7px solid var(--bad);font-size:1.02rem}.ibadge.mine{background:#7f1d1d;font-size:.72rem;padding:3px 8px}.yours{font:700 .72rem var(--mono);color:#fff;background:var(--accent);padding:1px 6px;border-radius:4px;letter-spacing:.04em}.myinj{background:var(--badbg);border:2px solid var(--bad);color:var(--fg);border-radius:8px;padding:10px 14px;margin:6px 0 10px;font-size:1rem}td.hi{font-weight:700;color:var(--ok);background:var(--okbg)}.wl-add{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.wl-add input{flex:1 1 260px;font:inherit;padding:9px 12px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg);min-height:42px}.wl-add button,.wl-rm{font:600 .85rem var(--body);padding:9px 16px;border-radius:6px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer;min-height:42px}.wl-rm{background:none;color:var(--bad);border-color:var(--line);padding:6px 10px;min-height:36px}.wl-add button:disabled{opacity:.5}.todayrep{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 8px}.replink{font:600 .85rem var(--body);color:var(--accent);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:6px 12px}.replink:hover{border-color:var(--accent)}.dropsel{display:block;margin:0 0 10px;font-weight:600}.streamsel{margin:14px 0 0;border:1px solid var(--line);border-radius:14px;background:var(--panel)}.ss-hero{border-radius:13px 13px 0 0;overflow:hidden}#ssmore{border-radius:0 0 13px 13px}.ss-hero{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)}.ss-cur{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:6px 16px;align-items:center;padding:14px 18px;border-left:5px solid var(--accent)}.ss-face{position:relative;flex:none;display:inline-grid;place-items:center;width:24px;height:24px;border-radius:50%;overflow:hidden;vertical-align:middle;margin-right:6px;background:color-mix(in srgb,var(--accent) 16%,var(--panel));color:var(--accent);font:700 .62rem var(--display);letter-spacing:.02em}.ss-face img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center 18%;background:color-mix(in srgb,var(--fg) 6%,var(--panel))}.ss-face.big{width:64px;height:64px;margin-right:0;font-size:1.3rem;box-shadow:0 0 0 3px var(--panel),0 0 0 5px var(--accent)}.ss-k{font:700 .64rem var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}.ss-name{font:700 1.55rem/1.1 var(--display);letter-spacing:.01em;text-wrap:balance}.ss-name .tm{font-size:.8rem}.ss-sub{color:var(--muted);font-size:.86rem}.ss-worth{display:flex;gap:16px}.ss-worth .lbl{display:block;font:600 .58rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:2px}.ss-worth .num2{font:700 1.65rem/1 var(--display);font-variant-numeric:tabular-nums}.ss-mebar{grid-column:2/-1}.streamsel .bar{height:8px;border-radius:99px;background:var(--line);overflow:hidden;min-width:40px}.streamsel .bar i{display:block;height:100%;background:var(--accent);opacity:.75}.streamsel .bar.me i{background:var(--ok)}.ss-alts{display:grid;gap:7px;align-content:start;padding:14px 18px;border-left:1px solid var(--line)}.ssalt .ssan{display:flex;align-items:center;flex-wrap:wrap;gap:0 4px;min-width:0}.ssalt{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(40px,1fr) auto auto;gap:10px;align-items:center;font-size:.88rem;padding:2px 6px;margin:0 -6px;border-radius:8px}.ssalt.sel{background:color-mix(in srgb,var(--accent) 12%,transparent)}.ssalt .num{font-variant-numeric:tabular-nums;white-space:nowrap}.ssalt small{color:var(--muted)}.ssuse{font:600 .7rem var(--mono);padding:2px 10px;border-radius:999px;border:1px solid var(--line);background:none;color:var(--accent);cursor:pointer}.ssuse:disabled{color:var(--muted);cursor:default;opacity:.6}.ssalt.sel .ssuse{background:var(--accent);border-color:var(--accent);color:#fff}.b2bt{display:inline-block;font:600 .64rem var(--mono);padding:2px 8px;border-radius:999px;background:var(--warnbg);color:var(--fg);vertical-align:middle}.ss-row2{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:10px 18px;border-top:1px solid var(--line);background:color-mix(in srgb,var(--fg) 3%,transparent)}.ss-row2 .t,#ssmore .t{font:600 .8rem var(--body);color:var(--muted)}#ssmore{padding:8px 18px 10px;border-top:1px solid var(--line)}#ssmore>summary{display:flex;flex-wrap:wrap;gap:6px 8px;align-items:center;list-style:none}#ssmore>summary::-webkit-details-marker{display:none}.chip2{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border:1px solid var(--line);border-radius:999px;font-size:.8rem;background:var(--bg);color:var(--fg)}.chip2 b{font:700 .92rem var(--display)}.chip2.zero{opacity:.55}.ssedit{font:600 .8rem var(--body);color:var(--accent);margin-left:2px}#ssprog{position:fixed;left:50%;top:calc(14px + env(safe-area-inset-top,0px));transform:translateX(-50%);z-index:60;width:min(520px,calc(100% - 32px));padding:14px 16px;border-radius:12px;background:var(--panel);border:1px solid var(--accent);box-shadow:0 12px 32px color-mix(in srgb,#000 28%,transparent)}#ssprog[hidden]{display:none}.pg-top,.pg-foot{display:flex;justify-content:space-between;gap:10px;align-items:baseline}.pg-top b{font:700 1.05rem var(--display);letter-spacing:.02em}.pg-pct{font:700 1.2rem var(--display);font-variant-numeric:tabular-nums;color:var(--accent)}.pg-bar{height:10px;margin:8px 0;border-radius:99px;background:var(--line);overflow:hidden}.pg-bar i{display:block;height:100%;width:1%;border-radius:99px;background:var(--accent);transition:width .6s ease}.pg-foot{font-size:.82rem;color:var(--muted)}.pg-step{color:var(--fg);min-width:0}.pg-time{white-space:nowrap;font-variant-numeric:tabular-nums}@media (prefers-reduced-motion:reduce){.pg-bar i{transition:none}}.sspick{position:relative;flex:0 1 460px;min-width:0}#sspickbtn{display:flex;align-items:center;gap:8px;width:100%;font:inherit;text-align:left;padding:6px 10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--fg);cursor:pointer}#sspickbtn:hover:not(:disabled){border-color:var(--accent)}#sspickbtn:disabled{cursor:default;opacity:.85}#sspickbtn[aria-expanded=true]{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 20%,transparent)}#sspickbtn .bar,#sspickbtn .pk-po{display:none}#sspickbtn .pk-n::after{content:" reg.";font:500 .7rem var(--body);color:var(--muted)}.pk-car{margin-left:auto;color:var(--muted);padding-left:6px}.sspop{position:absolute;z-index:40;left:0;top:calc(100% + 6px);width:min(560px,calc(100vw - 32px));max-height:min(440px,70vh);overflow:auto;padding:6px;border:1px solid var(--line);border-radius:12px;background:var(--panel);box-shadow:0 12px 32px color-mix(in srgb,#000 28%,transparent)}.pk-head,.pk-opt{display:grid;grid-template-columns:24px minmax(0,1fr) 70px 46px 46px;gap:10px;align-items:center}.pk-head{padding:8px 10px 4px;font:600 .58rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);border-top:1px solid var(--line);margin-top:4px}.pk-head span:first-child{grid-column:1/3}.pk-head span:nth-child(2){grid-column:3/5;text-align:right}.pk-head span:nth-child(3){text-align:right}.pk-opt{position:relative;padding:6px 10px;border-radius:8px;cursor:pointer;outline:none}.pk-opt:hover,.pk-opt:focus{background:color-mix(in srgb,var(--fg) 6%,transparent)}.pk-opt[aria-selected=true]{background:color-mix(in srgb,var(--accent) 13%,transparent)}.pk-opt.auto{grid-template-columns:24px minmax(0,1fr)}.pk-who{display:flex;flex-direction:column;min-width:0;line-height:1.2}.pk-who b{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pk-who small{color:var(--muted);font-size:.74rem}.pk-tags{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin-top:2px}.pk-tags .nbat{font-size:.6rem}.pk-tags .b2bt{font-size:.58rem;padding:1px 6px}.pk-keep{font-size:.7rem}.pk-n{font:700 .95rem var(--display);font-variant-numeric:tabular-nums;text-align:right}.pk-po{color:var(--muted);font-weight:600}.pk-cur{position:absolute;right:8px;top:4px;font:700 .54rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}#sspickbtn .ss-face{margin-right:0}#sspickbtn .pk-who{flex:1}#sspickbtn .pk-tags{display:inline-flex;margin:0 0 0 6px}#sspickbtn .pk-who{flex-direction:row;align-items:center;flex-wrap:wrap}#ssmore[open] .ssedit{visibility:hidden}@media (max-width:760px){.ss-hero{grid-template-columns:minmax(0,1fr)}.ss-alts{border-left:0;border-top:1px solid var(--line)}.ss-cur{grid-template-columns:auto minmax(0,1fr);gap:8px 12px}.ss-worth,.ss-mebar{grid-column:1/-1}.ss-face.big{width:52px;height:52px}.ssalt{grid-template-columns:minmax(0,1fr) auto auto}.ssalt .bar{display:none}.sspick{flex:1 1 100%}.sspop{width:auto;right:0}.pk-head,.pk-opt{grid-template-columns:24px minmax(0,1fr) 40px 40px}.pk-opt .bar{display:none}.pk-head span:nth-child(2){grid-column:3/4}}.streamsel select{font:inherit;font-weight:400;margin-left:8px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg);max-width:100%}.streamsel select:disabled{opacity:.7}.streamsel .small{color:var(--muted);min-width:0}body.rebuilding .wrap>*:not(header){opacity:.45;pointer-events:none}.ssbtn{font:inherit;font-weight:700;padding:6px 14px;border-radius:6px;border:1px solid var(--line);background:var(--panel);color:var(--muted);cursor:pointer}.ssbtn:disabled{cursor:default;opacity:.6}.ssbtn.on{background:var(--accent);border-color:var(--accent);color:#fff}.sstab td,.sstab th{vertical-align:middle}.sstab td.c{text-align:center}.sstab small{color:var(--muted)}.sstab input{font:inherit;padding:4px 6px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg)}.sstab .ss-fp{width:5.5em}.sstab .ss-fp:not(:placeholder-shown){border-color:var(--accent);font-weight:700}.sstab input:disabled{opacity:.75}.sstab .ss-keep{width:18px;height:18px}details.wl>summary{cursor:pointer;list-style:none;font-size:.8rem;color:var(--muted)}details.wl>summary::-webkit-details-marker{display:none}details.wl>summary .wlh{display:inline;margin-right:4px}details.wl>summary::after{content:" ▸";color:var(--accent)}details.wl[open]>summary::after{content:" ▾"}details.wl[open]>summary{margin-bottom:2px}.ledbtns{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px}.ledbtn{font:600 .85rem var(--body);color:var(--accent);background:none;border:1px solid var(--line);border-radius:999px;padding:6px 12px;cursor:pointer}.ledbtn:hover{border-color:var(--accent)}.wlallth{font:600 .62rem var(--mono);letter-spacing:.03em;text-transform:none;margin-left:6px;padding:1px 7px;border:1px solid var(--line);border-radius:999px;background:var(--panel);color:var(--accent);cursor:pointer;white-space:nowrap}tr.pastp td{background:color-mix(in srgb,var(--fg) 4%,transparent);color:var(--fg)}.pasttag{background:var(--muted)!important}.pastsc{font:700 1.05rem var(--display);font-variant-numeric:tabular-nums;margin-left:4px}#pastrows[hidden]{display:none}.sstab .ss-rest{width:18px;height:18px;vertical-align:middle}.ssrest{white-space:nowrap}.rb2b{font:500 .6rem var(--mono);padding:0 4px;margin-left:2px;border-radius:999px;border:1px solid transparent;background:transparent;color:var(--muted);cursor:pointer;vertical-align:middle;opacity:.35}.rb2b:hover{opacity:.9}.rb2b.on{opacity:.85;color:var(--fg)}.rb2b.pend{opacity:1;border-style:dashed;border-color:var(--accent)}.rb2b:disabled{cursor:default}.rb2b:disabled:not(.on){opacity:.2}#ssbar{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:50;display:flex;align-items:center;gap:12px;max-width:calc(100% - 32px);padding:10px 14px;border-radius:10px;background:var(--panel);border:1px solid var(--accent);box-shadow:0 6px 24px rgba(0,0,0,.25);font-size:.85rem}#ssbar[hidden]{display:none}#ssbar span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dropsel select{font:inherit;font-weight:400;margin-left:6px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg);max-width:100%}.why{font-size:.82rem;color:var(--muted);max-width:42ch}details summary{cursor:pointer;color:var(--accent);font-size:.8rem}details.lmmore{margin-top:10px}details.lmmore>summary{font:600 .9rem var(--body);padding:8px 12px;border:1px solid var(--line);border-radius:999px;display:inline-block;list-style:none}details.lmmore[open]>summary{margin-bottom:8px}')
SCRIPT="""<script>
(function(){var b=document.querySelectorAll('.tabs button');function show(t){b.forEach(function(x){var on=x.dataset.t===t;x.setAttribute('aria-selected',on?'true':'false');document.getElementById(x.dataset.t).hidden=!on});try{localStorage.setItem('bbltab',t)}catch(e){}}
b.forEach(function(x){x.addEventListener('click',function(){show(x.dataset.t);try{history.replaceState(null,'','#'+x.dataset.t)}catch(e){}})});
var h=location.hash.slice(1),st=null;try{st=localStorage.getItem('bbltab')}catch(e){}
function sub(id){var x=document.querySelector('.subtabs button[data-s='+id+']');if(!x)return;var nav=x.closest('.subtabs');[].forEach.call(nav.querySelectorAll('button'),function(y){var on=y===x;y.setAttribute('aria-pressed',on?'true':'false');document.getElementById(y.dataset.s).hidden=!on});try{localStorage.setItem('bblsub-'+nav.dataset.g,id)}catch(e){}}
[].forEach.call(document.querySelectorAll('.subtabs button'),function(x){x.addEventListener('click',function(){sub(x.dataset.s)})});
[].forEach.call(document.querySelectorAll('.subtabs'),function(n){try{var ss=localStorage.getItem('bblsub-'+n.dataset.g);if(ss&&n.querySelector('button[data-s='+ss+']'))sub(ss)}catch(e){}});
window.__sub=sub;
var R={draft:['season','sdraft'],reports:['season','srep'],matchups:['season','smu'],prizes:['season','sprz'],pickups:['waivers','wpick'],bestadds:['waivers','wpick'],adds:['waivers','wpick'],watch:['waivers','wwatch'],watchlist:['waivers','wwatch'],rivals:['waivers','wriv'],twoforone:['trades',''],stash:['trades',''],ttargets:['trades',''],breakouts:['waivers','wpick'],matchup:['period','pmu'],startsit:['period','pmu'],roster:['period','prost'],top150:['season','stop'],h2h:['season','smu'],streaming:['waivers','wstr'],stream:['waivers','wstr']};if(R[h]){show(R[h][0]);if(R[h][1])sub(R[h][1]);var el=document.getElementById(h);if(el){if(el.tagName==='DETAILS')el.open=true;setTimeout(function(){el.scrollIntoView({block:'start'})},60)}}else if(st==='pickups'||st==='watch'){show('waivers')}else if(h&&document.querySelector('.tabs button[data-t="'+h+'"]'))show(h);else if(st&&document.querySelector('.tabs button[data-t="'+st+'"]'))show(st);})();
</script>"""
# ---- Playoffs tab: schedule strength P22–P24, the field, player games, targets and league playoff rules
POP=[22,23,24]; RND={22:'Quarterfinal',23:'Semifinal',24:'Final · 3rd-place game'}
WEST={'Binkas&Yams','Tank You Very Much','TINOLA','Oobsidoobsie','SOGGY'}
def tkey(t): return 'TINOLA' if 'ɪɴᴏʟᴀ' in t else t
def pdates(p):
    d=pstart(p); e=pend(p); out_=[]
    while d<=e: out_.append(d); d+=dt.timedelta(1)
    return out_
PD={p:pdates(p) for p in POP}
def ngames(t,p,n=None): return sum(1 for d in PD[p] if d in G[t] and not (n and n in out and d<out[n]) and not (n and sits(n,t,d)))
def filled(r,p): return sum(min(5,len(avail(r,d))) for d in PD[p])
def thin(r,p): return [d for d in PD[p] if len(avail(r,d))<5]
TEAMS={ME:R}; TEAMS.update({tkey(k):v for k,v in OTH.items()})
PT={t:{p:ptot(r,p) for p in POP} for t,r in TEAMS.items()}
PF={t:{p:filled(r,p) for p in POP} for t,r in TEAMS.items()}
def phi(z): return 0.5*(1+math.erf(z/math.sqrt(2)))
def wp(a,b): return phi((a-b)/max(1,0.11*math.sqrt(a*a+b*b)))
rk_po=lambda p: 1+sum(1 for t in PT if PT[t][p]>PT[ME][p])
TOT={t:sum(PT[t].values()) for t in PT}; myrk=1+sum(1 for t in TOT if TOT[t]>TOT[ME])
others=[t for t in PT if t!=ME]
avgop={p:sum(PT[t][p] for t in others)/len(others) for p in POP}
grade=('A' if myrk<=2 else 'B' if myrk<=4 else 'C' if myrk<=6 else 'D' if myrk<=8 else 'F')
# key cards
pk=[]
pk.append(f'<div class="key"><b>Playoff schedule grade: {grade}</b><p>Your current roster projects <strong>{TOT[ME]:,.0f}</strong> over P22–P24, <strong>#{myrk} of 10</strong> (league average {sum(TOT[t] for t in others)/9:,.0f}). It updates nightly as rosters change.</p></div>')
for p in POP:
    th=thin(R,p); mx=5*len(PD[p])
    pk.append(f'<div class="key"><b>P{p} · {RND[p]}</b><p>{pstart(p).strftime("%b %-d")}–{pend(p).strftime("%b %-d")} ({len(PD[p])} days). Projected <strong>{PT[ME][p]:,.0f}</strong> (#{rk_po(p)} of 10), slots <strong>{PF[ME][p]}/{mx}</strong>, {len(th)} thin day{"s" if len(th)!=1 else ""}{(" ("+", ".join(d.strftime("%a %-d") for d in th)+")") if th else ""}. Win chance vs an average playoff team: <strong>{wp(PT[ME][p],avgop[p])*100:.0f}%</strong>.</p></div>')
# the field
def fld(t):
    me=t==ME; nm=html.escape(dname(t))
    cells=''.join(f'<td class="num">{PT[t][p]:,.0f}<span class="tm"> · {PF[t][p]}/{5*len(PD[p])}</span></td>' for p in POP)
    vs=''.join(f'<td class="num">{"—" if me else f"{wp(PT[ME][p],PT[t][p])*100:.0f}%"}</td>' for p in POP)
    return f'<tr{" class=\"cur\"" if me else ""}><td>{lg(t,22)} <b>{nm}</b>{" <span class=\"nowtag\">YOU</span>" if me else ""} <span class="tm">{"West" if t in WEST else "East"}</span></td>{cells}<td class="num"><b>{TOT[t]:,.0f}</b></td>{vs}</tr>'
fieldrows=''.join(fld(t) for t in sorted(PT,key=lambda t:-TOT[t]))
# your players
def prow(n):
    t,s=R[n]; g=[ngames(t,p,n) for p in POP]; v=sum(MV[n].get(p,0) for p in POP)
    flag=[]
    if n in out and out[n]>dt.date(2027,3,15): flag.append('<span class="tag bad">out into playoffs</span>')
    lt=[(POP[i],x) for i,x in enumerate(g) if x<=(1 if POP[i]==24 else 2)]
    if lt: flag.append('<span class="tag warn">light: '+', '.join(f'{x} game{"s" if x!=1 else ""} in P{p}' for p,x in lt)+'</span>')
    if sum(g)>=11: flag.append('<span class="tag ok">heavy schedule</span>')
    return f'<tr><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]} · {t}</span>{" <span class=\"tm\">IR</span>" if INFO[n].get("sec")=="I" else ""}<div class="tags">{"".join(flag)}</div></td>'+''.join(f'<td class="num">{x}</td>' for x in g)+f'<td class="num"><b>{sum(g)}</b></td><td class="num">{v:,.0f}</td></tr>'
myrows=''.join(prow(n) for n in sorted(R,key=lambda n:-sum(MV[n].get(p,0) for p in POP)))
# targets: players on other rosters and free agents, measured as "add him in Ajay Mitchell's spot" for P22–P24 only
def pogain(n,t,s):
    r=dict(base); r[n]=(t,s); return sum(ptot(r,p)-bpt[p]-mit[p] for p in POP)
cands=sorted([(n,k,t,s) for k,ro in OTH.items() for n,(t,s) in ro.items()],key=lambda x:-INFO[x[0]]['best'])[:70]
TG=sorted([(pogain(n,t,s),n,tkey(k),t) for n,k,t,s in cands],reverse=True)
CAP=sorted((INFO[m]['best'] for m in R),reverse=True)[4]
tgt=TG[:15]  # stars included (tagged); everyone else is a realistic ask
def trow(g,n,own,t): return f'<tr><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]} · {t}</span>'+(' <span class="tag warn">⭐ star · costly</span>' if INFO[n]['best']>CAP else '')+f'</td><td>{html.escape(dname(own))}</td><td class="num">{INFO[n]["best"]:.1f}</td>'+''.join(f'<td class="num">{ngames(t,p)}</td>' for p in POP)+f'<td class="num"><b>{g:+,.0f}</b></td></tr>'
tgrows=''.join(trow(*x) for x in tgt)
FAPO=sorted([(sum(GA[n].get(p,0) for p in POP),n) for n in FA],reverse=True)[:6]
farows=''.join(f'<tr><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]} · {FA[n][0]}</span>{wbtn(n)}</td><td class="num">{INFO[n]["best"]:.1f}</td>'+''.join(f'<td class="num">{ngames(FA[n][0],p)}</td>' for p in POP)+f'<td class="num"><b>{g:+,.0f}</b></td></tr>' for g,n in FAPO)
# NBA teams: games per round and coverage of your thin playoff days
THD=[d for p in POP for d in thin(R,p)]
nba=sorted(G,key=lambda t:(-sum(1 for d in THD if d in G[t]),-sum(ngames(t,p) for p in POP)))
nbarows=''.join(f'<tr><td><b>{t}</b></td>'+''.join(f'<td class="num">{ngames(t,p)}</td>' for p in POP)+f'<td class="num">{sum(ngames(t,p) for p in POP)}</td><td class="num"><b>{sum(1 for d in THD if d in G[t])}</b>/{len(THD)}</td></tr>' for t in nba[:12])
divg=sum(1 for o in OPP if tkey(o.lstrip('@')) in WEST)
best_light=[n for n in R if any(ngames(R[n][0],p,n)<=(1 if p==24 else 2) for p in POP)]
insight=[]
weak=min(POP,key=lambda p:PT[ME][p]/max(1,avgop[p]))
insight.append(f'<li><b>Weakest round: P{weak} ({RND[weak]})</b> at {PT[ME][weak]:,.0f} vs a {avgop[weak]:,.0f} average. That is the week to fix first: the targets below are ranked by what they add across P22–P24.</li>')
if best_light: insight.append(f'<li><b>Light schedules on your roster:</b> {", ".join(html.escape(short(n)) for n in best_light)} {"plays" if len(best_light)==1 else "play"} only 2 games in P22 or P23, or 1 game in the 5-day final. Consider moving {'him' if len(best_light)==1 else 'them'} before the <b>Feb 25 trade deadline</b> if a similar player has a fuller schedule.</li>')
insight.append(f'<li><b>Strongest playoff schedules:</b> {", ".join(html.escape(dname(t))+f" ({TOT[t]:,.0f})" for t in sorted(others,key=lambda t:-TOT[t])[:2])}. They are the teams to beat in March, whatever their regular-season record.</li>')
insight.append(f'<li><b>Bench matters in the playoffs:</b> a tied playoff matchup goes to the team with more points from Reserves, so keep your bench players on teams that play that week.</li>')
insight.append(f'<li><b>Division:</b> you are in the West (Binkas&amp;Yams, Tank You Very Much, TINOLA, SOGGY). {divg} of your 21 regular-season matchups are division games, and division record is the 2nd standings tiebreaker.</li>')
# ---- Playoff roster plan (top of the Playoffs tab, under the key cards): for each of your players, the best like-for-like swap
# (a rival's player to trade for, or a free agent to claim, CBS FP/G from 15% below his to 5% above: the gain is his schedule) for P22–P24, with what it costs
# in the regular season; then a dated checklist. Projections as the rest of this tab: best daily lineups, current CBS FP/G.
def _build_poplan():
    global poplan
    NOTR={l.split('|')[1] for l in open('settings.txt',encoding='utf-8-sig',errors='replace') if l.startswith('notrade|') and l.count('|')>=2}
    bpo={p:ptot(R,p) for p in POP}; breg={p:ptot(R,p) for p in REG}
    pool=[(m,k,ro[m]) for k,ro in OTH.items() for m in ro]+[(m,'FA',FA[m]) for m in FA if healthy(m)]
    SW=[]
    for n in R:
        if INFO[n].get('sec')=='I' or (n in out and out[n]>dt.date(2027,3,15)): continue
        b=INFO[n]['best']
        if b<=0: continue
        rw={k:v for k,v in R.items() if k!=n}
        opts=[]
        for m,k,v in pool:
            if not (0.85*b<=INFO[m]['best']<=1.05*b) or (k!='FA' and n in NOTR): continue
            r=dict(rw); r[m]=v
            g=sum(ptot(r,p)-bpo[p] for p in POP)
            if g>=10: opts.append((g,m,k,r))
        if not opts: continue
        opts.sort(key=lambda x:-x[0])
        g,m,k,r=opts[0]
        reg=sum(ptot(r,p)-breg[p] for p in REG)
        SW.append(dict(n=n,m=m,k=k,po=g,reg=reg,gn=[ngames(R[n][0],p,n) for p in POP],gm=[ngames(INFO[m]['team'],p) for p in POP],alt=[(x[1],x[2]) for x in opts[1:3]]))
    SW.sort(key=lambda x:-x['po'])
    sg=lambda v:f'<span class="{"pos" if v>0.5 else "neg" if v<-0.5 else ""}">{v:+,.0f}</span>'
    def row(x):
        n,m,k=x['n'],x['m'],x['k']
        how='claim (free agent)' if k=='FA' else 'trade with '+html.escape(dname(tkey(k)))
        alt=(' <span class="small muted">· also: '+', '.join(html.escape(short(a))+(' (FA)' if b_=='FA' else '') for a,b_ in x['alt'])+'</span>') if x['alt'] else ''
        return (f'<tr><td><b>{html.escape(short(n))}</b> <span class="nbat" data-t="{INFO[n]["team"]}">{INFO[n]["team"]}</span> <span class="tm">{INFO[n]["best"]:.1f} · {"-".join(map(str,x["gn"]))} games</span></td>'
                f'<td><b>{html.escape(short(m))}</b> <span class="nbat" data-t="{INFO[m]["team"]}">{INFO[m]["team"]}</span> <span class="tm">{INFO[m]["best"]:.1f} · {"-".join(map(str,x["gm"]))} games</span>{alt}</td>'
                f'<td>{how}</td><td class="num"><b>{sg(x["po"])}</b></td><td class="num">{sg(x["reg"])}</td></tr>')
    tbl=(f'<div class="scroll"><table class="pptab"><thead><tr><th>Your player · FP/G · P22-P23-P24 games</th><th>Swap for</th><th>How</th><th>P22–24 gain</th><th>Reg. season</th></tr></thead><tbody>'
         +''.join(row(x) for x in SW[:8])+'</tbody></table></div>') if SW else '<p class="muted">No like-for-like swap adds 10+ playoff points right now: your playoff schedule is already in good shape.</p>'
    trades=[x for x in SW if x['k']!='FA'][:3]; claims=[x for x in SW if x['k']=='FA'][:2]
    irs=[n for n in R if n in out and out[n]>dt.date(2027,3,15)]
    TH=sum(len(thin(R,p)) for p in POP)
    todo=[]
    todo.append('<li><b>Now → Thu Feb 25 (trade deadline, 11:59 PM ET):</b> '+(('trade for a fuller playoff schedule: '+'; '.join(f'{html.escape(short(x["n"]))} → {html.escape(short(x["m"]))} ({html.escape(dname(tkey(x["k"])))}, {x["po"]:+,.0f} playoffs, {x["reg"]:+,.0f} reg. season)' for x in trades)+'. A trade costs regular-season points from the day it goes through, so the closer to the deadline, the less it costs (and the less the schedule picture can change).') if trades else 'no like-for-like trade adds 10+ playoff points; check again in February.')+'</li>')
    if irs: todo.append(f'<li><b>Before the deadline:</b> {", ".join(html.escape(short(n)) for n in irs)} {"is" if len(irs)==1 else "are"} out into the playoffs: trade or drop for someone who plays P22–P24.</li>')
    todo.append('<li><b>P20–P21 (Mar 1–14):</b> line up your playoff free agents. Only 2 waiver adds per period, so spread claims over both weeks; '
                +(('today&#39;s best like-for-like claims: '+'; '.join(f'{html.escape(short(x["m"]))} for {html.escape(short(x["n"]))} ({x["po"]:+,.0f})' for x in claims)+' (the wire will change by March).') if claims else 'see <b>Free agents with playoff schedules</b> below (the wire will change by March).')+'</li>')
    todo.append(f'<li><b>P22–P24 (Mar 15–Apr 2):</b> you have {TH} thin day{"s" if TH!=1 else ""} (fewer than 5 players) on your current roster: stream into them with players from <b>NBA teams for your thin playoff days</b>. Only teams still alive can add and drop, and ties go to bench points, so keep reserves who play.</li>')
    poplan=('<section class="brief" id="poplan"><h2>Playoff roster plan</h2><ul>'+''.join(todo)+'</ul>'
            '<h3>Like-for-like playoff swaps</h3>'+tbl+
            '<p class="small">For each of your players, the player at a similar or lower CBS FP/G (15% below to 5% above, so the gain comes from when he plays, not a better player: more games, games on nights you&#39;re short, or a position you can&#39;t fill) whose schedule adds the most to your P22–P24 best daily lineups (10+ points), from a rival roster (trade) or the free agents (claim). '
            'Games = his games in P22-P23-P24. Reg. season = what the same swap made today does to your lineups P'+str(REG[0] if REG else 21)+'–P21. IR players out into the playoffs and your no-trade list (for trades) are left out.</p></section>'
            '<style>.pptab .pos{color:var(--ok)}.pptab .neg{color:var(--bad)}.pptab td:nth-child(2){min-width:220px}</style>')
_build_poplan()
th_head=''.join(f'<th>P{p}</th>' for p in POP)
posec=f"""{oddsec}<section class="keys">{''.join(pk)}</section>{poplan}
<section class="brief"><h2>What it means</h2><ul>{''.join(insight)}</ul></section>
<section><h2>The playoff field · projected by round</h2>
<div class="scroll"><table><thead><tr><th>Team</th><th>P22 proj · slots</th><th>P23 proj · slots</th><th>P24 proj · slots</th><th>Total</th><th>Your win % P22</th><th>P23</th><th>P24</th></tr></thead><tbody>{fieldrows}</tbody></table></div>
<p class="small">Each team's best daily lineups from its current active roster (IR players left out for other teams) over each round's NBA schedule. Win % is your chance against that team in that round with normal week-to-week swing (about ±11%). Seeds aren't set until P21 ends, so this compares you with every possible opponent.</p></section>
<section class="two"><div><h2>Your players' playoff games</h2>
<div class="scroll"><table><thead><tr><th>Player</th>{th_head}<th>Total</th><th>Playoff value</th></tr></thead><tbody>{myrows}</tbody></table></div>
<p class="small">Games per round (P24 is only 5 days). Playoff value = points your playoff lineups lose without him after your bench fills in.</p></div>
<div><h2>NBA teams for your thin playoff days</h2>
<div class="scroll"><table><thead><tr><th>NBA team</th>{th_head}<th>Total</th><th>Thin days</th></tr></thead><tbody>{nbarows}</tbody></table></div>
<p class="small">Your thin days are days with fewer than 5 of your players playing ({len(THD)} across P22–P24). Teams that play on them fill empty slots; teams with 4 games in a round help most.</p></div></section>
<section class="two"><div><h2>Trade targets for the playoffs</h2>
<div class="scroll"><table><thead><tr><th>Player</th><th>Manager</th><th>CBS FP/G</th>{th_head}<th>P22–24 gain</th></tr></thead><tbody>{tgrows}</tbody></table></div>
<p class="small">Players on other rosters ranked by points they'd add to your P22–P24 lineups in your stream slot ({html.escape(short(STREAM))}), including stars and high draft picks. ⭐ marks players above your 5th-best player's CBS FP/G ({CAP:.1f}): getting one usually means giving up one of your core players, so weigh his gain against what you'd send. Trade deadline: Thu Feb 25, 11:59 PM ET.</p></div>
<div><h2>Free agents with playoff schedules</h2>
<div class="scroll"><table><thead><tr><th>Player</th><th>CBS FP/G</th>{th_head}<th>P22–24 gain</th></tr></thead><tbody>{farows}</tbody></table></div>
<p class="small">Today's free agents, for reference: the wire will look different by March. Gains are for P22–P24 in your stream slot ({html.escape(short(STREAM))}).</p></div></section>
<section class="brief"><h2>League notes · playoffs</h2><ul>
<li><b>Who gets in:</b> 8 of 10 teams make the playoffs (automatic). The bottom 2 miss out, and last place gets the league punishment.</li>
<li><b>When:</b> the last 3 periods. P22 Quarterfinal Mar 15–21, P23 Semifinal Mar 22–28, P24 Final Mar 29–Apr 2 (5 days; the NBA's last week isn't used).</li>
<li><b>Bracket:</b> no reseeding after each round, so the bracket set after P21 stays fixed. There is a 3rd-place game in P24; no consolation bracket.</li>
<li><b>Prizes:</b> champion $800, runner-up $300, 3rd place $200 (won in the 3rd-place game).</li>
<li><b>Seeding tiebreakers</b> (in order): winning percentage, division record, total points, points against, head-to-head. Two divisions: West (Binkas&amp;Yams, Tank You Very Much, TINOLA, SOGGY, you) and East (Deep Bag, Rudy Jobert, My Shaila, Pucs, Phil the new champion).</li>
<li><b>Playoff ties:</b> a tied playoff matchup goes to the team with more points from Reserves (bench). The same rule breaks regular-season ties.</li>
<li><b>Add/drops in the playoffs:</b> restricted, so only teams still alive can add and drop players. The 2-waiver-adds-per-period limit still applies.</li>
<li><b>Trades:</b> deadline Thu Feb 25, 2027, 11:59 PM ET (P19). Trades go through a 1-day vote; more than 5 objections sends it to the commissioner.</li>
<li><b>IR:</b> must still be legal 5 minutes before the first NBA game of each day, or the whole lineup scores zero that day.</li>
</ul><p class="small">From the league's Rules page on CBS (Schedule &amp; Playoffs, Transaction Settings) and the commissioner's season notes. CBS doesn't say whether division winners get a guaranteed seed.</p></section>"""

# ---- Streaming (Waivers → Streaming)
def ngames(d): return sum(1 for t in G if d in G[t])//2
def gtier(k):
    if k<=5: return ('prime','◆◆◆ Prime')
    if k<=8: return ('good','◆◆ Good')
    if k<=10: return ('med','◆ Medium')
    return ('heavy','Heavy')
SPER=[p for p in PER if p<=21][:3]
MUP={m['p']:m for m in MU}
SC=sorted([n for n in FA if healthy(n)],key=lambda n:-INFO[n]['best'])[:30]
SC=list(dict.fromkeys(SC+[n for n in watch if n in FA and healthy(n)]))
SFIRST=TODAY+dt.timedelta(days=1)
DV={}
def dval(n,d,D=None):
    D=D or STREAM; k=(n,d,D)
    if k not in DV:
        rb={q:v for q,v in R.items() if q!=D}
        r=dict(rb); r[n]=FA[n] if n in FA else R[n]
        DV[k]=best(avail(r,d))-best(avail(rb,d))
    return DV[k]
def openslots(d): return 5-min(5,len(avail(RON(d),d)))
def wpf(m,g):
    sdd=0.11*math.sqrt(m['mine']**2+m['opp_p']**2) or 1
    return 0.5*(1+math.erf((m['mine']+g-m['opp_p'])/(sdd*math.sqrt(2))))
def splan(p,D=None):
    D=D or STREAM
    ds=[d for d in P[p] if d>=SFIRST]
    if not ds: return None
    V={n:[dval(n,d,D) for d in ds] for n in SC+[D]}
    C={n:[0] for n in V}
    for n in V:
        for v in V[n]: C[n].append(C[n][-1]+v)
    S=lambda n,a,b: C[n][b]-C[n][a]
    L=len(ds); hold=S(D,0,L)
    one=(hold,None); two=(hold,None)
    for X in SC:
        for i in range(L):
            v=S(D,0,i)+S(X,i,L)
            if v>one[0]: one=(v,(X,i))
            for Y in SC:
                if Y==X: continue
                for j in range(i+1,L):
                    v2=S(D,0,i)+S(X,i,j)+S(Y,j,L)
                    if v2>two[0]: two=(v2,(X,i,Y,j))
    return dict(ds=ds,hold=hold,one=one,two=two,V=V)
def nm(n): return f'<b>{html.escape(short(n))}</b> <span class="nbat" data-t="{INFO[n]["team"]}">{INFO[n]["team"]}</span> <span class="tm">{INFO[n]["pos"]}</span>'
def dd(d): return d.strftime('%a %b %-d')
def night(d): return (d-dt.timedelta(days=1)).strftime('%a')
def strblock(D):
    STR=[]
    for p in SPER:
        pl=splan(p,D)
        if not pl: continue
        ds=pl['ds']; m=MUP.get(p)
        # calendar rows
        crow=[]
        for i,d in enumerate(ds):
            k=ngames(d); cls,lab=gtier(k); o=openslots(d); act=min(5,len(avail(RON(d),d)))
            top=max(((pl['V'][n][i],n) for n in SC),default=(0,None))
            if o==0: ver='<span class="sv full">— Full</span>'
            elif cls in ('prime','good') or o>=2: ver='<span class="sv go">🎯 Stream</span>'
            else: ver='<span class="sv maybe">◐ Maybe</span>'
            bt=(f'{nm(top[1])} <b class="num">+{top[0]:.0f}</b>' if top[1] and top[0]>=1 and o>0 else '<span class="muted">—</span>')
            crow.append(f'<tr><td>{dd(d)}</td><td><span class="gt {cls}">{lab}</span> <span class="num">{k} games</span></td><td class="num">{act}/5</td><td class="num">{o}</td><td>{ver}</td><td>{bt}</td></tr>')
        # plans
        hold=pl['hold']; (v1,a1)=pl['one']; (v2,a2)=pl['two']
        use2=a2 and v2-v1>=10
        if use2:
            X,i,Y,j=a2; gain=v2-hold
            steps=(f'<li>Claim {nm(X)} on <b>{night(ds[i])} night</b>, drop {html.escape(short(D))} → he plays from {dd(ds[i])}.</li>'
                   f'<li>Claim {nm(Y)} on <b>{night(ds[j])} night</b>, drop {html.escape(short(X))} → he plays from {dd(ds[j])} to the end of the period.</li>')
            alt=f'<p class="small">One-claim option: {"+"+format(v1-hold,".0f") if a1 else "none"}{(" with "+html.escape(short(a1[0]))) if a1 else ""}. The second claim adds <b>{v2-v1:+.0f}</b>.</p>'
        elif a1 and v1-hold>=5:
            X,i=a1; gain=v1-hold
            steps=f'<li>Claim {nm(X)} on <b>{night(ds[i])} night</b>, drop {html.escape(short(D))} → he plays from {dd(ds[i])}.</li>'
            alt=f'<p class="small">A second stream would add only {max(0,v2-v1):+.0f}, so keep the other claim for injuries or breakouts.</p>'
        else:
            gain=0; steps=f'<li>Hold {html.escape(short(D))}: no free agent adds 5+ points over him this period.</li>'; alt=''
        if m:
            lab='Favored' if m['wp']>=0.6 else ('Underdog' if m['wp']<=0.4 else 'Toss-up')
            pri='High' if 0.35<=m['wp']<=0.65 else ('Low' if m['wp']>0.8 or m['wp']<0.2 else 'Medium')
            mline=f'{html.escape(m["opp"])} · {m["wp"]*100:.0f}% {lab}'+(f' → <b>{wpf(m,gain)*100:.0f}%</b> with this plan' if gain>=1 else '')+f' · stream priority <b>{pri}</b>'
        else: mline=''
        # teams to stream from: games on your open-slot days, weighted by day quality
        od=[d for d in ds if openslots(d)>0]
        tt=[]
        for t in G:
            g_open=[d for d in od if d in G[t]]
            if g_open:
                light=sum(1 for d in g_open if ngames(d)<=8)
                tt.append((len(g_open),light,sum(1 for d in ds if d in G[t]),t,g_open))
        tt.sort(key=lambda x:(-x[0],-x[1],-x[2],x[3]))
        teams=' '.join(f'<span class="tchip"><span class="nbat" data-t="{t}">{t}</span> <b>{a}</b><small> on open nights · {c} total</small><span class="cov">{" · ".join(d.strftime("%a") for d in gd)}</span></span>' for a,l,c,t,gd in tt[:6]) or '<span class="muted">You have no open slots this period</span>'
        # most efficient free agents: points added if claimed for the whole remaining period, per claim
        eff=sorted(((sum(pl['V'][n]),n) for n in SC),reverse=True)[:6]
        effrows=''.join(f'<tr><td>{nm(n)}{wbtn(n)}</td><td class="num">{INFO[n]["best"]:.1f}</td><td class="num">{sum(1 for d in od if d in G[INFO[n]["team"]])}/{len(od)}</td><td class="num"><b>{g-hold:+.0f}</b></td><td>{rost(n) or "<span class=muted>—</span>"}</td></tr>' for g,n in eff if g-hold>0) or '<tr><td colspan="5" class="muted">No free agent beats holding your stream slot this period</td></tr>'
        STR.append(f'''<section class="strp"><h2>P{p} · {pstart(p).strftime("%b %-d")} – {pend(p).strftime("%b %-d")}{" · now" if p==CUR else ""}</h2>
    <p class="small" style="margin:0 0 8px">{mline}</p>
    <div class="brief"><h3>Best plan · {("+"+format(gain,".0f")+" pts vs holding "+html.escape(short(D))) if gain>=1 else "hold"}</h3><ol style="margin:4px 0 0;padding-left:20px">{steps}</ol>{alt}</div>
    <h3 class="sh">Teams to stream from</h3><div class="teams">{teams}</div>
    <h3 class="sh">Most efficient free agents</h3>
    <div class="scroll"><table><thead><tr><th>Free agent</th><th>CBS FP/G</th><th>Games on your open days</th><th>Gain per claim</th><th>Rostered %</th></tr></thead><tbody>{effrows}</tbody></table></div>
    <h3 class="sh">Day by day</h3>
    <div class="scroll"><table><thead><tr><th>Day</th><th>NBA slate</th><th>Your active</th><th>Open slots</th><th>Verdict</th><th>Best streamer that day</th></tr></thead><tbody>{"".join(crow)}</tbody></table></div></section>''')
    return "".join(STR)
STRD=[STREAM]+[n for n in sorted(R,key=lambda n:tot(MV[n],REG)+tot(MV[n],PO)) if n!=STREAM and n not in KEEP and not (n in out and out[n]>TODAY+dt.timedelta(30))][:3]
STRV=[strblock(D) for D in STRD]
STRSEL=(f'<label class="dropsel">If I drop <select id="strsel">'+''.join(f'<option value="{i}">{html.escape(short(D))} ({INFO[D]["pos"]} · worth {tot(MV[D],REG):.0f} reg. season + {tot(MV[D],PO):.0f} playoffs{", stream slot" if D==STREAM else ""})</option>' for i,D in enumerate(STRD))+'</select></label>'
        '<p class="small" style="margin:-4px 0 0">Switch who a stream claim replaces: every plan, gain and table below updates instantly. Worth = points your lineups lose without him.</p>')
# the other "If I drop" choices are compressed (ztpl) and unpacked the first time they're picked; then the 🛌 / + Watch buttons sync
STRJS='<script>(function(){var s=document.getElementById("strsel");if(!s)return;function show(){var v=s.value;if(!document.querySelector(".strv[data-i=\\""+v+"\\"]")){window.__tpl("strv-"+v).then(function(t){if(!t||document.querySelector(".strv[data-i=\\""+v+"\\"]"))return;var d=document.createElement("div");d.className="strv";d.dataset.i=v;d.hidden=true;d.appendChild(t.content.cloneNode(true));var l=document.querySelectorAll(".strv");l[l.length-1].after(d);document.dispatchEvent(new Event("bbl-rest"));document.dispatchEvent(new Event("bbl-sync"));if(s.value===v)show()});return}[].forEach.call(document.querySelectorAll(".strv"),function(x){x.hidden=x.dataset.i!==v});[].forEach.call(document.querySelectorAll(".strname"),function(x){x.textContent=s.options[s.selectedIndex].text.split(" (")[0]})}try{var v=localStorage.getItem("bblstrsel");if(v)for(var i=0;i<s.options.length;i++)if(s.options[i].value===v)s.value=v}catch(e){}s.addEventListener("change",function(){try{localStorage.setItem("bblstrsel",s.value)}catch(e){}show()});show()})();</script>'
# season-long insights
RD=[d for p in REG for d in P[p] if d>=SFIRST]
TT=defaultdict(int)
for t in G:
    TT[t]=sum(1 for d in RD if d in G[t] and ngames(d)<=8 and openslots(d)>0)
lteams=sorted(TT.items(),key=lambda x:-x[1])[:6]
wdn=defaultdict(list)
for d in RD: wdn[d.strftime('%a')].append(ngames(d))
wdl=sorted(((sum(v)/len(v),k) for k,v in wdn.items()))
nprime=sum(1 for d in RD if ngames(d)<=8 and openslots(d)>0)
pofa=sorted(((tot(GA[n],PO),n) for n in FA if healthy(n)),reverse=True)[:3]
ins=[f'<li><b>Lightest nights:</b> {", ".join(f"{k} ({a:.1f} games)" for a,k in wdl[:3])}; heaviest: {wdl[-1][1]} ({wdl[-1][0]:.1f}). Streamers who play {wdl[0][1]}s and {wdl[1][1]}s fill your empty slots most often.</li>',
     f'<li><b>{nprime} Prime/Good nights</b> left in the regular season where you also have an open slot. Those are the nights a streamer is guaranteed to start.</li>',
     '<li><b>Teams with the most light-night games on your open days</b> (rest of the regular season): '+' · '.join(f'<span class="nbat" data-t="{t}">{t}</span> {c}' for t,c in lteams)+'. Free agents on these teams make the best long-term stream slot.</li>',
     f'<li><b>Claims are waiver-only:</b> they run nightly at about 11:09 PM Calgary, so a player you want for Thursday must be claimed by Wednesday night. You get <b>2 waiver offers per period</b>, and the waiver order is rolling, so every stream you win sends you down the order for the next breakout.</li>',
     '<li><b>Lineups lock per player</b> (5 min before his own game), so a streamer in a late game lets you wait for injury news before you set him.</li>',
     '<li><b>Dropped players sit on waivers for 2 days</b>, so you can&#39;t drop a streamer and re-claim him the next night.</li>',
     '<li><b>Streaming ends after P21:</b> add/drops are restricted in the playoffs. By the end of P21, park the stream slot on the best playoff-schedule free agent'+(': '+', '.join(f'{html.escape(short(n))} (+{g:.0f} P22–P24)' for g,n in pofa if g>0) if pofa and pofa[0][0]>0 else '')+'.</li>']
STRCSS='<style>.gt{display:inline-block;font:700 .66rem var(--mono);letter-spacing:.04em;padding:2px 7px;border-radius:999px;white-space:nowrap}.gt.prime{background:#1e3a8a;color:#fff}.gt.good{background:#3b82f6;color:#fff}.gt.med{background:var(--pobg);color:var(--fg)}.gt.heavy{background:none;color:var(--muted);border:1px solid var(--line)}.sv{font:700 .78rem var(--mono);white-space:nowrap}.sv.full,.sv.maybe{color:var(--muted)}.sh{font:600 1rem var(--display);text-transform:uppercase;letter-spacing:.03em;margin:16px 0 6px}.strp{display:grid;gap:4px}.strp table{min-width:760px}</style>'
strpane=f'''{STRCSS}<section class="brief"><h2>Streaming</h2>
<p style="margin:0 0 8px">A stream claim drops <b class="strname">{html.escape(short(STREAM))}</b> (or the last streamer) for a free agent who plays on nights you have open lineup slots.</p>
{STRSEL}
<h3>How nights are rated</h3>
<p class="small" style="margin:0">This season averages about {sum(ngames(d) for d in RD)/max(1,len(RD)):.1f} NBA games a night, so "10 or fewer" covers almost every night. The tiers are tightened to: <span class="gt prime">◆◆◆ Prime</span> 5 or fewer games · <span class="gt good">◆◆ Good</span> 6–8 · <span class="gt med">◆ Medium</span> 9–10 · <span class="gt heavy">Heavy</span> 11+. The deciding factor is your own lineup: <b>🎯 Stream</b> = you have an open slot on a Prime/Good night, or 2+ open slots on any night; <b>◐ Maybe</b> = 1 open slot on a Medium/Heavy night (your bench may fill it); <b>— Full</b> = all 5 slots are already covered, so a streamer adds nothing.</p>
<h3>What matters for your schedule</h3><ul>{"".join(ins)}</ul></section>
{"".join(f'<div class="strv" data-i="{i}">{v}</div>' if i==0 else ztpl(f'strv-{i}',v,False) for i,v in enumerate(x or "<p class=muted>No regular-season periods left to stream.</p>" for x in STRV))}{STRJS}
<p class="small">Gains are points added to your best daily lineups versus holding the player you drop (<span class="strname">{html.escape(short(STREAM))}</span>), using CBS projections and the league scoring. Each period is planned separately starting from him. Free agents projected to miss many games are left out. Claims shown are the night before the player's first game; waivers run at about 11:09 PM Calgary.</p>'''
# ---- Start/Sit (This period → Start/Sit): opponent defense vs position, matchup-adjusted daily lineups
EMAP={'UTAH':'UTA','WSH':'WAS','PHX':'PHO','GSW':'GS','NOP':'NO','NYK':'NY','SAS':'SA'}
em=lambda t: EMAP.get(t,t)
OPPD=defaultdict(dict)
if os.path.exists('opp.txt'):
    for l in open('opp.txt'):
        f=l.strip().split('|')
        if len(f)>=3 and f[0].isdigit():
            d=dt.date(int(f[0][:4]),int(f[0][4:6]),int(f[0][6:])); a,h=em(f[1]),em(f[2])
            OPPD[d][a]=(h,False); OPPD[d][h]=(a,True)
DV0={}
if os.path.exists('dvp_2026.txt'):
    for l in open('dvp_2026.txt'):
        if l.startswith('#'): continue
        f=l.strip().split('|')
        if len(f)>=8: DV0[(em(f[0]),f[1])]=tuple(float(x) for x in f[2:8])
DVC=defaultdict(lambda:[0.0,0.0,set()])
if os.path.exists('dvp_cur.txt'):
    for l in open('dvp_cur.txt'):
        f=l.strip().split('|')
        if len(f)>=6 and f[0].isdigit():
            a=DVC[(em(f[1]),f[2])]; a[0]+=float(f[3]); a[1]+=float(f[4]); a[2].add(f[5])
KPRIOR=15  # games of current-season data before it outweighs last season
def drate(t,p):
    if (t,p) not in DV0: return None
    fp,mn,g,fl,ml,gl=DV0[(t,p)]
    r0=(fp+fl)/max(1,mn+ml)  # last season, with the post-Feb-15 stretch counted twice
    c=DVC.get((t,p))
    if not c or not c[1]: return r0
    mpg=mn/max(1,g); w=KPRIOR*mpg
    return (r0*w+c[0])/(w+c[1])
DTEAMS=sorted({t for t,_ in DV0})
LAVG={p:(sum(drate(t,p) for t in DTEAMS)/len(DTEAMS)) for p in 'GFC'} if DTEAMS else {}
SHRINK=0.6
def dmult(t,p):
    r=drate(t,p)
    return 1.0 if r is None or not LAVG else 1+SHRINK*(r/LAVG[p]-1)
DRANK={p:{t:i+1 for i,t in enumerate(sorted(DTEAMS,key=lambda t:drate(t,p)))} for p in 'GFC'}  # 1 = toughest
def pgroups(n): return [x for x in INFO[n]['pos'].split(',') if x in 'GFC'] or ['F']
def pmult(n,opp): 
    gs=pgroups(n); return sum(dmult(opp,g) for g in gs)/len(gs)
def tteam(n,r): return r[n][0]
def bestlu(pl):
    bv,bl=0,[]
    for k in range(1,min(5,len(pl))+1):
        for combo in itertools.combinations(pl,k):
            for asg in itertools.product(*[list(s.items()) for _,s in combo]):
                if k+len({'G','F','C'}-{a[0] for a in asg})>5: continue
                v=sum(a[1] for a in asg)
                if v>bv: bv,bl=v,[(c[0],a[0],a[1]) for c,a in zip(combo,asg)]
    return bv,bl
def adjday(r,d):
    pl=avail(r,d); adj=[]
    for n,s in pl:
        o=OPPD.get(d,{}).get(r[n][0])
        m=pmult(n,o[0]) if o else 1.0
        adj.append((n,{k:v*m for k,v in s.items()}))
    return pl,adj
def mtag(m):
    if m>=1.04: return f'<span class="tag">▲ soft D {100*(m-1):+.0f}%</span>'
    if m<=0.96: return f'<span class="tag">▼ tough D {100*(m-1):+.0f}%</span>'
    return f'<span class="muted small">{100*(m-1):+.0f}%</span>'
def b2b(t,d): return (d-dt.timedelta(days=1)) in G[t]
def b2b1(t,d): return (d+dt.timedelta(days=1)) in G[t] and not b2b(t,d)
def b2bany(t,d): return b2b(t,d) or b2b1(t,d)
MUP2={m['p']:m for m in MU}; MUADJ={}
def okey(p):
    if p>21: return None
    on=OPP[p-1].lstrip('@'); return next((k for k in OTH if k==on or (on=='TINOLA' and 'ɪɴᴏʟᴀ' in k)),None)
def musec(p,open_=True):
    """Returns (summary_html, [(date, panel_html)]) for period p."""
    ds=[d for d in P[p] if d in OPPD]
    if not ds: return '',[]
    tb=ta=0; panels=[]; swaps=[]; b2bs=[]; faces=[]
    for d in ds:
        pl,adj=adjday(R,d)
        bv,bl=bestlu(pl); av,al=bestlu(adj)
        tb+=bv; ta+=av
        start={n:(sl,v) for n,sl,v in al}; bstart={n for n,_,_ in bl}
        info={}
        for n,s in adj:
            t=R[n][0]; o=OPPD[d].get(t); m=pmult(n,o[0]) if o else 1.0
            gs=pgroups(n); rk=min(DRANK[g].get(o[0],15) for g in gs) if o else None
            fl=[]
            if b2b(t,d): fl.append('<span class="b2bw" title="His team played yesterday: rest or a minutes limit is possible tonight">⚠ B2B · 2nd night</span>'); b2bs.append((d,n,2))
            elif b2b1(t,d): fl.append('<span class="b2bw" title="His team plays again tomorrow: he could be rested tonight instead of tomorrow">⚠ B2B · 1st night</span>'); b2bs.append((d,n,1))
            if n in start and n not in bstart: fl.append('<span class="tag ok">🔁 in by matchup</span>')
            if n not in start and n in bstart: fl.append('<span class="tag">🔁 out by matchup</span>')
            if o: faces.append((m,n,o[0],d))
            info[n]=dict(t=t,o=o,m=m,rk=rk,gs=gs,base=max(dict(pl)[n].values()),adj=max(s.values()),fl=' '.join(fl))
        def opptxt(i): return (('vs ' if i['o'][1] else '@ ')+i['o'][0]) if i['o'] else '—'
        order={'C':0,'F':1,'G':2}
        def lrow(n,cls,slot):
            i=info[n]; rk=(f' · #{i["rk"]} vs {"/".join(i["gs"])}' if i['rk'] else '')
            return (f'<tr class="{cls}"><td class="luslot">{slot}</td><td><b>{html.escape(short(n))}</b> <span class="nbat" data-t="{i["t"]}">{i["t"]}</span> <span class="tm">{INFO[n]["pos"]}</span>'
                    f'<div class="luo">{opptxt(i)}<span class="tm">{rk}</span> <span class="mobm">{mtag(i["m"])}</span>{(" "+i["fl"]) if i["fl"] else ""}</div></td>'
                    f'<td class="mcol">{mtag(i["m"])}</td><td class="num"><b>{i["adj"]:.1f}</b><div class="luo">proj {i["base"]:.1f}</div></td></tr>')
        st_rows=''.join(lrow(n,'mstart',sl) for n,(sl,v) in sorted(start.items(),key=lambda kv:(order.get(kv[1][0],3),-kv[1][1])))
        st_rows+=''.join('<tr class="mstart"><td class="luslot">—</td><td colspan="3" class="muted small">Open slot · nobody else plays</td></tr>' for _ in range(5-len(start)))
        bench=sorted([n for n in info if n not in start],key=lambda n:-info[n]['adj'])
        bn_rows=(''.join(lrow(n,'mbench','Bench') for n in bench) if bench else '<tr><td></td><td colspan="3" class="muted small">Nobody: everyone playing starts.</td></tr>')
        off=[n for n in R if n not in info]
        off_html=', '.join(html.escape(short(n))+(' (IR)' if n in out and d<out[n] else '') for n in sorted(off,key=lambda n:-INFO[n]['best']))
        _bb=[n for n in info if b2bany(info[n]['t'],d)]
        def _bbn(n): return ('<b>'+html.escape(short(n))+'</b>' if n in start else html.escape(short(n)))+(' (2nd night)' if b2b(info[n]['t'],d) else ' (1st night)')
        b2bban=(f'<div class="b2bban"><b>⚠ Back-to-back for {len(_bb)} of your player{"s" if len(_bb)!=1 else ""}</b>: '+', '.join(_bbn(n) for n in sorted(_bb,key=lambda n:(n not in start,-info[n]['adj'])))
                +'. Teams usually rest players on one night of a back-to-back, and it isn&#39;t always the 2nd. Check the injury report before each game locks and have a bench swap ready.</div>') if _bb else ''
        table=(b2bban+f'<div class="scroll"><table class="lutab"><thead><tr><th>Slot</th><th>Player · opponent · D rank</th><th class="mcol">Matchup</th><th>Points</th></tr></thead>'
               f'<tbody>{st_rows}<tr class="lusep"><td colspan="4">Bench</td></tr>{bn_rows}</tbody></table></div>')
        sw=[n for n in start if n not in bstart]
        if sw: swaps.append((d,[short(n) for n in sw],[short(n) for n in bstart if n not in start]))
        panels.append((d,f'''<div class="ssday" data-d="{d.isoformat()}" hidden>
<div class="sshead"><b>{d.strftime("%A, %b %-d")}</b> · {len(pl)} of your players play · lineup <b>{av:.0f}</b> pts <span class="muted small">(projection only {bv:.0f})</span></div>
{table}
<div class="ssbench"><span class="sslab">No game</span> <span class="muted">{off_html or "—"}</span></div>
</div>'''))
    k=okey(p); ohead=''
    if k and p in MUP2:
        ob=oa=0
        for d in ds:
            pl,adj=adjday(OTH[k],d); ob+=bestlu(pl)[0]; oa+=bestlu(adj)[0]
        m=MUP2[p]
        me_adj=m['mine']+(ta-tb); op_adj=m['opp_p']+(oa-ob)
        sdd=0.11*math.sqrt(me_adj**2+op_adj**2) or 1
        wpa=0.5*(1+math.erf((me_adj-op_adj)/(sdd*math.sqrt(2))))
        MUADJ[p]=dict(mine=me_adj,opp_p=op_adj,wp=wpa,dme=ta-tb,dop=oa-ob,base_wp=m['wp'])
        tn="TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in k else k
        ohead=(f'<p style="margin:0 0 6px"><b>P{p} vs {html.escape(tn)}:</b> you <b>{me_adj:,.0f}</b> ({ta-tb:+.0f} from matchups) vs <b>{op_adj:,.0f}</b> ({oa-ob:+.0f}) → <b>{wpa*100:.0f}%</b> win odds '
               f'<span class="muted">(projection only {m["wp"]*100:.0f}%)</span></p>')
    faces.sort()
    tough=', '.join(f'{html.escape(short(n))} vs {o} {d.strftime("%a")} ({100*(m-1):+.0f}%)' for m,n,o,d in faces[:3] if m<1)
    soft=', '.join(f'{html.escape(short(n))} vs {o} {d.strftime("%a")} ({100*(m-1):+.0f}%)' for m,n,o,d in faces[::-1][:3] if m>1)
    ins=[]
    ins.append('<li><b>Matchup changes your lineup:</b> '+'; '.join(f'{d.strftime("%a")}: start {", ".join(a)} over {", ".join(b) or "—"}' for d,a,b in swaps)+'.</li>' if swaps else '<li>No lineup call changes because of matchups: start your highest projections.</li>')
    if soft: ins.append(f'<li><b>Best matchups:</b> {soft}.</li>')
    if tough: ins.append(f'<li><b>Toughest:</b> {tough}.</li>')
    if b2bs: ins.append('<li><b>Back-to-backs:</b> '+', '.join(f'{short(n)} ({d.strftime("%a")} {"2nd" if k==2 else "1st"})' for d,n,k in sorted(set(b2bs)))+'. Either night can be a rest day: check before each game locks.</li>')
    return (ohead,f'<ul class="muins">{"".join(ins)}</ul>'), panels
def dvtable():
    rows=''.join(f'<tr><td><span class="nbat" data-t="{t}">{t}</span></td>'+''.join(f'<td class="num">{100*(dmult(t,p)-1):+.0f}% <span class="tm">#{DRANK[p][t]}</span></td>' for p in 'GFC')+'</tr>' for t in DTEAMS)
    return (f'<details class="rep"><summary>Defense vs position · all 30 teams</summary><div class="brief"><div class="scroll"><table><thead><tr><th>Team</th><th>vs guards</th><th>vs forwards</th><th>vs centers</th></tr></thead><tbody>{rows}</tbody></table></div>'
            '<p class="small">% = how much more (+) or less (−) than average a team gives up in BBL fantasy points per minute to that position; #1 = toughest. Already regressed 40% toward average.</p></div></details>')
ncur=len({g for v in DVC.values() for g in v[2]})//2 if DVC else 0
MUCSS=('<style>.mutab{min-width:760px}.mutab tr.mstart td{background:var(--pobg)}.muins{margin:4px 0 0;padding-left:18px}.muins li{margin:3px 0}'
       '.ssnav{display:flex;flex-wrap:nowrap;gap:6px;align-items:center;overflow-x:auto;padding:2px 2px 6px;-webkit-overflow-scrolling:touch}.ssnav>*{flex:0 0 auto}.ssnav .sslab{margin-right:2px}.ssnav button{font:600 .8rem var(--mono);padding:7px 10px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--fg);cursor:pointer;min-height:40px;line-height:1.15;text-align:center}'
       '.ssnav button small{display:block;font-weight:600;color:var(--muted);font-size:.66rem}.ssnav button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}.ssnav button[aria-pressed=true] small{color:var(--bg);opacity:.8}.ssnav .today{outline:2px solid var(--accent);outline-offset:1px}'
       '.sslab{font:600 .68rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}.sshead{margin:4px 0 10px}'
       '.lu{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px}@media (max-width:560px){.lu{grid-template-columns:repeat(2,minmax(0,1fr))}.luc{padding:8px 10px}.lun{font-size:.92rem}}.luc{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--panel);display:grid;gap:3px;min-width:0}'
       '.lus{font:700 .7rem var(--mono);letter-spacing:.08em;color:var(--accent)}.lun{font-size:1rem}.luo{font-size:.82rem;color:var(--muted)}.lup{font:600 1.1rem var(--display)}.luempty{border-style:dashed;opacity:.7}'
       '.lutab td{vertical-align:middle}.lutab tr.mstart td{background:var(--pobg)}.lutab .luslot{font:700 .72rem var(--mono);letter-spacing:.06em;color:var(--accent);width:52px}.lutab tr.mbench .luslot{color:var(--muted);font-weight:600}.lutab .lusep td{font:600 .68rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);background:var(--bg);padding-top:10px}.lutab .luo{font-size:.8rem;color:var(--muted);margin-top:2px}.lutab .mobm{display:none}@media (max-width:560px){.lutab th,.lutab td{padding:7px 6px}.lutab{font-size:.9rem}.lutab .mcol{display:none}.lutab .mobm{display:inline}.lutab .luslot{width:40px;font-size:.66rem}}'
       '.b2bw{display:inline-block;font:700 .66rem var(--mono);letter-spacing:.04em;padding:2px 7px;border-radius:999px;background:#b45309;color:#fff;white-space:nowrap}.b2bban{border:2px solid #b45309;border-radius:10px;padding:10px 14px;margin:0 0 10px;background:color-mix(in srgb,#b45309 10%,var(--panel))}'
       '.ssbench{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}.bch{border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:.85rem;background:var(--panel)}.ssdet{margin-top:10px}</style>')
_s0,_p0=musec(PER[0]) if PER else (('',''),[])
_s1,_p1=musec(PER[1]) if len(PER)>1 else (('',''),[])
_pan=_p0+_p1
_first=next((d for d,_ in _pan if d>=TODAY),_pan[0][0] if _pan else None)
def _btn(d,p):
    nb=sum(1 for n in R if d in G[R[n][0]] and b2bany(R[n][0],d) and not (n in out and d<out[n]))
    return f'<button type="button" data-d="{d.isoformat()}" data-p="{p}" aria-pressed="false"{" class=today" if d==TODAY else ""}>{d.strftime("%a")}<small>{d.strftime("%b %-d")}{(" · ⚠"+str(nb)) if nb else ""}</small></button>'
_nav=''
if _p0: _nav+=f'<span class="sslab">P{PER[0]}</span>'+''.join(_btn(d,PER[0]) for d,_ in _p0)
if _p1: _nav+=f'<span class="sslab" style="margin-left:8px">P{PER[1]}</span>'+''.join(_btn(d,PER[1]) for d,_ in _p1)
SSJS=('<script>(function(){var nav=document.querySelector(".ssnav");if(!nav)return;function show(v){var pp=null;[].forEach.call(nav.querySelectorAll("button"),function(b){var on=b.dataset.d===v;b.setAttribute("aria-pressed",on?"true":"false");if(on)pp=b.dataset.p});[].forEach.call(document.querySelectorAll(".ssper"),function(x){x.hidden=x.dataset.p!==pp});'
      '[].forEach.call(document.querySelectorAll(".ssday"),function(p){p.hidden=p.dataset.d!==v})}'
      '[].forEach.call(nav.querySelectorAll("button"),function(b){b.addEventListener("click",function(){show(b.dataset.d)})});show(nav.dataset.first)})();</script>')
startsit_pane=(MUCSS+(f'''<section class="brief"><h2>Start/Sit</h2><div class="ssper" data-p="{PER[0]}">{_s0[0]}</div>{f'<div class="ssper" data-p="{PER[1]}" hidden>{_s1[0]}</div>' if len(PER)>1 else ''}
<div class="ssnav" data-first="{_first.isoformat() if _first else ""}" role="group" aria-label="Pick a day">{_nav}</div></section>
<section>{"".join(h for _,h in _pan)}</section>
<section class="brief ssper" data-p="{PER[0]}"><h3 style="margin-top:0">P{PER[0]} notes</h3>{_s0[1]}</section>{f'<section class="brief ssper" data-p="{PER[1]}" hidden><h3 style="margin-top:0">P{PER[1]} notes</h3>{_s1[1]}</section>' if len(PER)>1 and _s1[1] else ''}''' if _pan else '<p class="muted">No upcoming games found.</p>')
    +dvtable()
    +f'''<details class="rep"><summary>How this works</summary><div class="brief"><p style="margin:0 0 6px">Your best 5 each day, adjusted for who each player faces. Each opponent&#39;s defense is rated by how many BBL fantasy points per minute it gave up to guards, forwards and centers (our scoring with the slot bonus). Players with two positions use the average of both.</p>
<p class="small" style="margin:0">Data: every 2025-26 regular-season game (ESPN box scores), with Feb 15 onward counted twice{f", blended with {ncur} games this season" if ncur else ""}. This season&#39;s games take over as they pile up (about 15 games per team). Ratings are pulled 40% toward average so one-season noise doesn&#39;t swing your lineup. Lineups lock 5 minutes before each player&#39;s own game, so check late scratches. B2B = his team played the night before.</p></div></details>'''+SSJS)
# ---- Roster (This period → Roster): CBS's roster columns, with ranks and fantasy points from our own box scores
# (CBS's Total lags a night; here slot points are summed straight from every box score, last night included)
_TZ=_zi.ZoneInfo('America/Edmonton')
TIPS={}
if os.path.exists('opp.txt'):
    for l in open('opp.txt'):
        f=l.strip().split('|')
        if len(f)>=4 and f[0].isdigit():
            try: _t=dt.datetime.strptime(f[3][:16],'%Y-%m-%dT%H:%M').replace(tzinfo=dt.timezone.utc).astimezone(_TZ)
            except ValueError: continue
            for x in (em(f[1]),em(f[2])): TIPS[(f[0],x)]=_t
def _rk(n): k=nk(n); return NKALIAS.get(k,k)
ACT=defaultdict(dict)   # name key -> {YYYYMMDD: BBL points with his slot bonus, as CBS's game log} for games he played
BOXP={}                 # name key -> (ESPN name, team, position) for players outside the CBS pool
_EPOS={'PG':'G','SG':'G','G':'G','SF':'F','PF':'F','F':'F','C':'C','G-F':'G,F','F-G':'G,F','F-C':'F,C','C-F':'F,C'}
POSK={_rk(n):i['pos'] for n,i in INFO.items()}   # CBS eligibility; players outside the pool fall back to ESPN's position
for n,t,pos,f in EXTRA: POSK.setdefault(_rk(n),pos)
# CBS's game log gives a two-position player the bonus of his CBS primary position every game (cbs_primary.txt, read
# from his CBS page: Braun SF -> F, Davis PF -> F, Sengun C -> C), not his best slot. Until his primary is known: best slot.
PRIMK={}
if os.path.exists('cbs_primary.txt'):
    for l in open('cbs_primary.txt',encoding='utf-8'):
        f=l.rstrip('\n').split('|')
        if len(f)==2 and _EPOS.get(f[1]) in ('G','F','C'): PRIMK[_rk(f[0])]=_EPOS[f[1]]
ADAYS=[]; FULLD=set()     # FULLD: nights where every game was final when the box score was read
ACTB=defaultdict(dict)    # name key -> {YYYYMMDD: (base pts, reb, ast, 3pm)}, to tell which slot bonus CBS used
STL=defaultdict(dict)     # name key -> {YYYYMMDD: (min, pts, fgm, fga, 3pm, 3pa, ftm, fta, reb, ast, to, stl, blk, pf, team)}: the player card's stats
GOPP={}                   # (YYYYMMDD, team) -> opponent as CBS shows it ('@MEM' away, 'MEM' home): a box file lists each game's teams away, home
for bf in sorted(glob.glob('box_*.txt')):
    d=os.path.basename(bf)[4:12]
    ln=open(bf,encoding='utf-8').read().strip().splitlines()
    try: _h=[int(x) for x in ln[0].lstrip('#').split('|')[:2]]; fin=_h[1]
    except (IndexError,ValueError): _h=[0,0]; fin=0
    if not d.isdigit() or not fin: continue
    ADAYS.append(d)
    _to=[]
    if _h[0] and _h[1]>=_h[0]: FULLD.add(d)
    for l in ln[1:]:
        q=l.split('|')
        if len(q)<16: continue
        try: mi,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,to,stl,blk,pf=[float(x or 0) for x in q[2:16]]
        except ValueError: continue
        if mi<=0: continue   # DNP rows
        k=_rk(q[0]); BOXP.setdefault(k,(q[0],em(q[1]),_EPOS.get((q[16] if len(q)>16 else '').upper(),'')))
        bon={'G':reb,'F':ast,'C':tpm}; el=[x for x in (POSK.get(k) or BOXP[k][2]).split(',') if x in bon]
        sb=bon[PRIMK[k]] if len(el)>1 and k in PRIMK else max([bon[x] for x in el] or [0])
        b=pts+2*fgm-fga+ftm-fta+reb+2*ast+4*stl+4*blk-2*to-pf; ACT[k][d]=b+sb; ACTB[k][d]=(b,reb,ast,tpm)
        STL[k][d]=(mi,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,to,stl,blk,pf,em(q[1]))
        if not _to or _to[-1]!=em(q[1]): _to.append(em(q[1]))
    for _i in range(0,len(_to)-1,2): GOPP[(d,_to[_i])]='@'+_to[_i+1]; GOPP[(d,_to[_i+1])]=_to[_i]
# ---- CBS check: every game of each of your players, ours vs his CBS game log (#GLOG lines from the CBS read).
# Nights not yet final in our box scores are skipped. A miss says which slot bonus would explain it, or that CBS's stats
# differ from ESPN's (usually a stat correction).
def cbs_check():
    if not GLOG: return None
    ok=0; bad=[]
    for n,gl in GLOG.items():
        if INFO.get(n,{}).get('own')!='MINE': continue
        k=_rk(n)
        for md,v in gl:
            try: mo,da=map(int,md.split('/')); cbs=float(v)
            except ValueError: continue
            dd=f'{2026 if mo>=10 else 2027}{mo:02d}{da:02d}'
            if dd not in FULLD: continue
            ours=ACT.get(k,{}).get(dd)
            if ours is not None and abs(ours-cbs)<0.5: ok+=1; continue
            why='not in our box scores'
            if ours is not None:
                b,rb,asx,tp=ACTB[k][dd]; fit=[x for x,y in (('G',rb),('F',asx),('C',tp)) if abs(b+y-cbs)<0.5]
                why=(f'CBS used the {"/".join(fit)} bonus' if fit else 'CBS stats differ from ESPN (likely a stat correction)')
            bad.append(dict(n=n,pos=INFO[n]['pos'],d=dd,ours=ours,cbs=cbs,why=why))
    return dict(ok=ok,bad=bad)
CBSCHK=cbs_check()
if CBSCHK:
    with open('cbs_check.txt','w',encoding='utf-8') as _fh:
        _fh.write(f"{CBSCHK['ok']}|{len(CBSCHK['bad'])}\n")   # games matching|not matching, then one line per miss
        for x in CBSCHK['bad']:
            _fh.write(f"{x['n']}|{x['pos']}|{x['d']}|{'' if x['ours'] is None else format(x['ours'],'g')}|{x['cbs']:g}|{x['why']}\n")
elif os.path.exists('cbs_check.txt'): os.remove('cbs_check.txt')
LASTN=ADAYS[-1] if ADAYS else None
_ld=dt.date(int(LASTN[:4]),int(LASTN[4:6]),int(LASTN[6:])) if LASTN else None
APER=period(_ld) if _ld else CUR
_pd={d for d in ADAYS if period(dt.date(int(d[:4]),int(d[4:6]),int(d[6:])))==APER}
ATOT={k:sum(v.values()) for k,v in ACT.items()}
_tv=sorted(ATOT.values(),reverse=True)
def arank(n):
    v=ATOT.get(_rk(n))
    return None if v is None else 1+sum(1 for x in _tv if x>v)
_pv=sorted([i['best'] for i in INFO.values()]+[e[3] for e in EXTRA],reverse=True)
def prank(n): return 1+sum(1 for x in _pv if x>INFO[n]['best']) if INFO[n]['best'] else None
SDAY=TODAY+dt.timedelta(1) if TODAY in SCD else TODAY   # tonight's games already final -> the next slate
_r0=SDAY+dt.timedelta(1); _r1=pend(period(_r0))
def _md(d): return f'{d.month}/{d.day}'
def _tip(t): return f'{t.hour%12 or 12}:{t:%M}{"am" if t.hour<12 else "pm"} {t.tzname()}'
def ro_today(t):
    o=OPPD.get(SDAY,{}).get(t)
    if not o: return '<span class="muted">No Game</span>'
    tp=TIPS.get((SDAY.strftime('%Y%m%d'),t))
    return f'{"" if o[1] else "@"}{o[0]}'+(f'<br><span class="tm">{_tip(tp)}</span>' if tp else '')
def ro_rest(t):
    g=[OPPD[d][t] for d in sorted(OPPD) if _r0<=d<=_r1 and t in OPPD[d]]
    h=[o for o,hm in g if hm]; a=['@'+o for o,hm in g if not hm]
    return f'Home: {len(h)}{" ("+",".join(h)+")" if h else ""}<br>Away: {len(a)}{" ("+",".join(a)+")" if a else ""}'
def _f(x): return f'{x:.0f}' if x is not None else '—'
RKC=((10,4,'top 10'),(25,3,'11–25'),(50,2,'26–50'),(100,1,'51–100'))   # (rank up to, chevrons, label)
def chevs(c): return '<span class="rkc">'+''.join(f'<i{" class=on" if j<c else ""}></i>' for j in range(4))+'</span>'
def rkcell(r):  # top-100 rank in the tier colour with military-style chevrons (4 = top 10 ... 1 = 51-100); lower stays plain
    c=next((x[1] for x in RKC if r and r<=x[0]),None)
    if not c: return f'<td class="num">{_f(r)}</td>'
    return f'<td class="num"><span class="rkv rk{c}"><b>{r}</b>{chevs(c)}</span></td>'
TIERCSS=('<style>.rk4{--c:#d97706}.rk3{--c:#8b5cf6}.rk2{--c:#3b82f6}.rk1{--c:#0d9488}'
         '@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .rk4{--c:#fbbf24}:root:not([data-theme=light]) .rk3{--c:#a78bfa}:root:not([data-theme=light]) .rk2{--c:#60a5fa}:root:not([data-theme=light]) .rk1{--c:#2dd4bf}}'
         ':root[data-theme=dark] .rk4{--c:#fbbf24}:root[data-theme=dark] .rk3{--c:#a78bfa}:root[data-theme=dark] .rk2{--c:#60a5fa}:root[data-theme=dark] .rk1{--c:#2dd4bf}'
         '.rkv{display:inline-flex;align-items:center;gap:6px}.rkv b{color:var(--c);font-variant-numeric:tabular-nums}'
         '.rkc{display:inline-flex;flex-direction:column-reverse;gap:1px}.rkc i{display:block;width:13px;height:5px;background:color-mix(in srgb,var(--fg) 12%,transparent);'
         'clip-path:polygon(0 100%,50% 0,100% 100%,82% 100%,50% 40%,18% 100%)}.rkc i.on{background:var(--c)}'
         '.tierkey .rkv{margin:0 2px 0 10px;vertical-align:middle}</style>')
TIERKEY='<span class="tierkey">'+''.join(f'<span class="rkv rk{c}">{chevs(c)}</span>{t}' for _,c,t in RKC)+'</span>'
def ro_row(n):
    i=INFO[n]; k=_rk(n); v=ACT.get(k,{})
    slot=i.get('slot') or i['pos'].split(',')[0]
    oflag=f' <span class="tag bad">out until {_md(out[n])}</span>' if n in out and out[n]>TODAY else ''
    pr,ar=prank(n),arank(n)
    pct=lambda x: f'{x}%' if x else '—'
    return (f'<tr><td>{slot}</td><td><b>{html.escape(n)}</b> <span class="tm">{i["pos"]} · {i["team"]}</span>{oflag}</td>'
            f'<td>{ro_today(i["team"])}</td><td class="small">{ro_rest(i["team"])}</td>'
            +f'<td class="num" title="{i["best"]:.1f} projected FP/G (CBS, best slot)">{_f(pr)}</td>'+rkcell(ar)+
            f'<td class="num">{pct(i.get("rost"))}</td><td class="num">{pct(i.get("start"))}</td>'
            f'<td class="num">{_f(sum(v.get(d,0) for d in _pd))}</td><td class="num">{_f(v.get(LASTN,0))}</td><td class="num"><b>{_f(ATOT.get(k,0))}</b></td></tr>')
_SO={'G':0,'F':1,'C':2}
def _ro_sec(sec,label):
    ns=sorted([n for n in R if (INFO[n].get('sec') or 'R')==sec],key=lambda n:(_SO.get(INFO[n].get('slot') or INFO[n]['pos'].split(',')[0],3),-INFO[n]['best']))
    return (f'<tr class="irhead"><td colspan="11">{label}</td></tr>' if label else '')+''.join(ro_row(n) for n in ns) if ns else ''
_rsec=[('A',''),('R','Reserves'),('I','Injured')]
def _chkline():  # result of the CBS check (cbs_check above), under the Roster table
    if not CBSCHK: return ''
    if not CBSCHK['bad']: return f'<p class="small">✔ <b>Checked against CBS:</b> all {CBSCHK["ok"]} games of your players match their CBS game logs.</p>'
    li=''.join(f'<li><b>{html.escape(x["n"])}</b> <span class="tm">{x["pos"]}</span> {_md(dt.date(int(x["d"][:4]),int(x["d"][4:6]),int(x["d"][6:])))}: '
               f'ours {"—" if x["ours"] is None else format(x["ours"],"g")}, CBS {x["cbs"]:g} · {html.escape(x["why"])}</li>' for x in CBSCHK['bad'])
    return (f'<p class="small">⚠ <b>Checked against CBS:</b> {len(CBSCHK["bad"])} of {CBSCHK["ok"]+len(CBSCHK["bad"])} games of your players '
            f'don&#39;t match their CBS game logs:</p><ul class="small" style="margin:0 0 8px 18px;padding:0">{li}</ul>')
CHKLINE=_chkline()
roster_pane=(TIERCSS+f'''<section><h2>Roster · P{period(SDAY)}</h2><p class="small" style="margin:0 0 8px">Actual rank, top 100: {TIERKEY}</p><div class="scroll"><table class="rostab"><thead>
<tr class="rsup"><th colspan="2"></th><th colspan="2">Schedule</th><th colspan="2">Rankings</th><th colspan="2">Trends</th><th colspan="3">Actual FPTS</th></tr>
<tr><th>Pos</th><th>Players</th><th>{_md(SDAY)}</th><th>{_md(_r0)}–{_md(_r1)}</th><th>Proj</th><th>Actual</th><th>Rost</th><th>Start</th><th>Prd. {APER}</th><th>{_md(_ld) if _ld else "Last"}</th><th>Total</th></tr></thead>
<tbody>{"".join(_ro_sec(s,lb) for s,lb in _rsec)}</tbody></table></div>
<p class="small">Same columns as your CBS roster page. <b>Schedule</b>: the next slate ({_md(SDAY)}, Calgary tip times) and the rest of P{period(_r0)}. <b>Proj</b> = rank among all NBA players by CBS projected FP/G in his best slot. <b>Actual</b> = rank by this season&#39;s points. <b>Rost/Start</b> = % of all CBS leagues (from CBS, as of the last run). <b>Actual FPTS</b> are league points with the slot bonus (G +REB, F +AST, C +3PM; two-position players get their CBS primary position&#39;s bonus every game), like CBS&#39;s game log, recomputed from ESPN box scores: unlike CBS, <b>Total</b> includes last night.</p>{CHKLINE}</section>'''
 +'<style>.rostab{min-width:980px}.rostab th,.rostab td{vertical-align:middle}.rostab td .tm{white-space:nowrap}.rostab .rsup th{font:600 .66rem var(--mono);letter-spacing:.08em;text-align:center;border-bottom:1px solid var(--line)}</style>') if R else '<p class="muted">No roster yet.</p>'
# ---- Thin days (Season → Thin days): the thin days (THIN: fewer than 5 of your players playing) each of your players plays, per period
def _thcov(n,p):
    t=R[n][0]; return [d for d in THIN.get(p,[]) if d in G[t] and not (n in out and d<out[n]) and not sits(n,t,d)]
def _thcell(n,p):
    th=THIN.get(p,[])
    if not th: return '<td class="thx">—</td>'
    c=_thcov(n,p); cls=' all' if len(c)==len(th) else (' none' if not c else '')
    return (f'<td class="thc{cls}"><b>{len(c)}</b><small>/{len(th)}</small>'
            +(f'<span>{" · ".join(d.strftime("%a %-m/%-d") for d in c)}</span>' if c else '')+'</td>')
_THR=sum(len(THIN.get(p,[])) for p in REG); _THP=sum(len(THIN.get(p,[])) for p in PO); _THT=_THR+_THP
_thn={n:(sum(len(_thcov(n,p)) for p in REG),sum(len(_thcov(n,p)) for p in PO)) for n in R}
def _thgl(n): t=R[n][0]; return sum(1 for p in PER for d in P[p] if d in G[t] and not (n in out and d<out[n]) and not sits(n,t,d))   # games left
_THE={p:sum(5-len(avail(RON(d),d)) for d in THIN.get(p,[])) for p in PER}   # empty lineup slots on thin days
_THZ=sum(1 for p in PER for d in THIN.get(p,[]) if not avail(RON(d),d))      # thin days nobody covers
def _thsum(x,y): return f'<td class="num ths{" all" if y and x==y else ""}"><b>{x}</b><small>/{y}</small></td>' if y else '<td class="num thx">—</td>'
def _thtot(n):
    c=sum(_thn[n]); pc=c/_THT*100 if _THT else 0
    return (f'<td class="thtot"><div class="thbar"><span style="width:{pc:.1f}%"></span></div>'
            f'<b>{c}</b><small>/{_THT} · {pc:.0f}%</small></td>')
def _thshare(n):
    g=_thgl(n); c=sum(_thn[n])
    if not g: return '<td class="num thx">—</td><td class="num thx">—</td>'
    return f'<td class="num">{g}</td><td class="num thsh{" hi" if c/g>=1.25*_THA else ""}"><b>{c/g*100:.0f}%</b><small>{c} of {g}</small></td>'
_THA=sum(sum(_thn[n]) for n in R)/max(1,sum(_thgl(n) for n in R))   # roster average share of games on thin days
def _thpts(n):
    v=sum(_thn[n])*INFO[n]['best']; return f'<td class="num">{v:,.0f}</td>' if v else '<td class="num thx">—</td>'
_throws=''.join(f'<tr><td><b>{html.escape(short(n))}</b> <span class="tm">{INFO[n]["pos"]} · {INFO[n]["team"]}</span>'
                +(' <span class="tag bad">IR</span>' if INFO[n].get('sec')=='I' else '')+(f' <span class="tag warn">out to {out[n].strftime("%b %-d")}</span>' if n in out and out[n]>TODAY else '')+'</td>'
                +_thtot(n)+_thsum(*(_thn[n][0],_THR))+_thsum(*(_thn[n][1],_THP))+_thshare(n)+_thpts(n)+''.join(_thcell(n,p) for p in PER)+'</tr>'
                for n in sorted(R,key=lambda n:(-sum(_thn[n]),short(n))))
_thfoot=('<tr class="thfoot"><td>Empty slots<small>streamers can fill</small></td>'
         f'<td><b>{sum(_THE.values())}</b></td><td class="num">{sum(_THE[p] for p in REG)}</td><td class="num">{sum(_THE[p] for p in PO)}</td><td colspan="3"></td>'
         +''.join(f'<td class="{"thx" if not _THE[p] else ("bad" if _THE[p]>=5 else "")}">{_THE[p] or "—"}</td>' for p in PER)+'</tr>')
_thhead=''.join(f'<th class="{"po" if p>=22 else ""}">P{p}<small>{len(THIN.get(p,[]))} thin</small></th>' for p in PER)
_thtop=max(R,key=lambda n:sum(_thn[n])) if R else None
_thkeys=(f'<div class="thkeys"><div class="thk"><span>Thin days left</span><b>{_THT}</b><small>{_THR} regular season · {_THP} playoffs</small></div>'
         f'<div class="thk"><span>Empty lineup slots</span><b>{sum(_THE.values())}</b><small>on those days{f" · {_THZ} with none of your players" if _THZ else ""}</small></div>'
         +(f'<div class="thk"><span>Top coverer</span><b>{html.escape(short(_thtop))}</b><small>{sum(_thn[_thtop])} of {_THT} thin days</small></div>' if _thtop and _THT else '')
         +'</div>')
thin_pane=(f'''<section><h2>Thin days · who covers them</h2>
<p class="small" style="margin:0 0 8px">A <b>thin day</b> is a day fewer than 5 of your players play, so every one of your players with a game that day starts. You have <b>{_THR}</b> thin day{"s" if _THR!=1 else ""} left in the regular season{f" (P{REG[0]}–P21)" if REG else ""} and <b>{_THP}</b> in the playoffs (P22–P24).</p>
{_thkeys}
<div class="scroll"><table class="thintab"><thead><tr><th>Player</th><th>Thin days covered</th><th>Reg. season</th><th>Playoffs</th><th>Games left</th><th>On thin days</th><th>Thin-day pts</th>{_thhead}</tr></thead><tbody>{_throws}</tbody><tfoot>{_thfoot}</tfoot></table></div>
<p class="small"><b>Thin days covered</b> = all the thin days he plays this season (regular season + playoffs); the bar is his share of all {_THT}. <b>2</b>/3 = he plays 2 of that period&#39;s 3 thin days, listed under the number; green = he plays all of them. <b>On thin days</b> = the share of his remaining games that fall on thin days, where he&#39;s a guaranteed start (green = well above your roster&#39;s average of {_THA*100:.0f}%). <b>Thin-day pts</b> ≈ thin days covered × his CBS FP/G: the points you&#39;d lose on those days without him. <b>Empty slots</b> = lineup spots nobody on your roster fills on thin days (red = 5 or more in a period): those are what a pickup with games on your thin days can add (Waivers → Streaming). Players are sorted by thin days covered. Low numbers mean his games fall on the same nights as your other players&#39;. Injured players count from their return date. {"Current period counts from today." if CUR in PER else ""}</p></section>'''
 +'<style>.thintab{min-width:max-content}.thintab th,.thintab td{text-align:center;vertical-align:top}.thintab th:first-child,.thintab td:first-child{text-align:left;position:sticky;left:0;background:var(--panel);z-index:1;white-space:nowrap}.thintab th small{display:block;font:600 .62rem var(--mono);color:var(--muted);text-transform:none;letter-spacing:0}.thintab th.po{color:var(--accent)}.thc,.ths{min-width:62px}.thc span{display:block;font:500 .68rem var(--mono);color:var(--muted);line-height:1.3;margin-top:2px;max-width:9em;margin-inline:auto}.thintab small{color:var(--muted)}.thc.all,.ths.all{background:var(--okbg)}.thc.all b,.ths.all b{color:var(--ok)}.thc.none b{color:var(--muted);font-weight:400}.thx{color:var(--muted)}'
 '.thtot{min-width:118px}.thtot b{font:700 1.25rem var(--display);font-variant-numeric:tabular-nums}.thtot small{display:block;font:600 .66rem var(--mono)}.thbar{height:6px;background:var(--line);border-radius:3px;overflow:hidden;margin:2px 0 4px}.thbar span{display:block;height:100%;background:var(--accent);border-radius:3px}'
 '.thsh small{display:block;font:500 .66rem var(--mono)}.thsh.hi b{color:var(--ok)}.thfoot td{border-top:2px solid var(--line);font-weight:600;background:var(--bg)}.thfoot td:first-child{background:var(--bg)}.thfoot td small{display:block;font:500 .64rem var(--mono);color:var(--muted)}.thfoot td.bad{color:var(--bad)}'
 '.thkeys{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 10px}.thk{flex:1 1 160px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:0}.thk span{display:block;font:600 .66rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}.thk b{display:block;font:700 1.6rem var(--display);line-height:1.15;overflow-wrap:anywhere}.thk small{font-size:.78rem;color:var(--muted)}</style>') if R else '<p class="muted">No roster yet.</p>'
# ---- Position gaps (Season → Thin days): nights 5+ of your players play but the lineup (G, F, C + 2 Util) can't use 5,
# because nobody playing that night can fill one of the G/F/C slots. Worked out in the browser (PGJS) from each player's
# eligible slots and game nights, so any move can be tried: If I drop / If I activate (an IR player) / If I add (a
# recommended free agent) and, for the add, who to drop to make room.
def _irw(n): return f'{short(n)} (back ~{out[n].strftime("%b %-d")})' if n in out and out[n]>TODAY else short(n)
_RA=[n for n in R if n not in IRP]   # your active roster: IR players aren't in your lineup until you activate them
_PGDAYS=[d for p in PER for d in P[p]]
_PGIX={d:i for i,d in enumerate(_PGDAYS)}
def _pgp(n,t,s):   # one player for the browser: short name, positions, team, eligible slots, game nights (index), FP/G
    return {'s':short(n),'pos':INFO[n]['pos'],'t':t,'sl':''.join(x for x in 'GFC' if x in s),'fp':round(INFO[n]['best'],1),
            'g':[_PGIX[d] for d in _PGDAYS if d in G[t] and not (n in out and d<out[n]) and not sits(n,t,d)]}
_PGDATA={'days':[[period(d),d.strftime('%a %b %-d'),d.strftime('%a %-m/%-d'),ngames(d),*gtier(ngames(d))] for d in _PGDAYS],
         'pl':{**{n:_pgp(n,*R[n]) for n in R},**{n:_pgp(n,*FA[n]) for n in FA if FA[n][1] and (healthy(n) or n in watch)}},
         'ra':_RA,'ir':IRP,'irw':{n:_irw(n) for n in IRP},'drops':[d for d in DROPS if d in _RA],'stream':STREAM,
         'fa':[n for n in FA if healthy(n) and FA[n][1]],'wl':watch}
_PGSEL=('<div class="pgsel"><label class="dropsel">If I drop <select id="pgdrop"><option value="">Nobody</option>'
        +''.join(f'<option value="{html.escape(d)}">{html.escape(short(d))} ({INFO[d]["pos"]}{", stream slot" if d==STREAM else ""})</option>' for d in _PGDATA['drops'])+'</select></label>'
        +('<label class="dropsel">If I activate <select id="pgact"><option value="">Nobody (keep IR as is)</option>'
          +''.join(f'<option value="{html.escape(n)}">{html.escape(_irw(n))} ({INFO[n]["pos"]})</option>' for n in IRP)+'</select></label>' if IRP else '')
        +'</div><div class="pgsel"><label class="dropsel">If I add <select id="pgadd"></select></label>'
        +'<label class="dropsel">…to make room, drop <select id="pgdrop2"></select></label>'
        +'<button type="button" id="pgreset" class="pgreset" title="Set every box back to Nobody">Reset all</button></div>')
_PGJS=r'''<script>(function(){var D=__PGD__,P=D.pl,DAYS=D.days,COVER=[[],["G"],["F"],["C"],["G","F"],["G","C"],["F","C"],["G","F","C"]];
var $=function(i){return document.getElementById(i)},S={drop:$("pgdrop"),act:$("pgact"),add:$("pgadd"),drop2:$("pgdrop2")},out=$("pgout");if(!out||!S.drop)return;
var GS={};Object.keys(P).forEach(function(n){var s={};P[n].g.forEach(function(i){s[i]=1});GS[n]=s});
function esc(t){var d=document.createElement("div");d.textContent=t;return d.innerHTML}
// most G/F/C slots distinct players can fill, and every slot set that reaches it (same as the lineup engine)
function fits(sl,S_,i,used){if(i===S_.length)return true;for(var j=0;j<sl.length;j++)if(!used[j]&&sl[j].indexOf(S_[i])>=0){used[j]=1;if(fits(sl,S_,i+1,used))return true;used[j]=0}return false}
function cover(sl){var bk=-1,bs=[];COVER.forEach(function(S_){if(!fits(sl,S_,0,[]))return;if(S_.length>bk){bk=S_.length;bs=[S_]}else if(S_.length===bk)bs.push(S_)});return [bk,bs]}
// roster r (names) -> gap nights {i: [playing, usable, fix slots, label]}, thin days {i: usable}, thin days a position costs a slot
function scan(r){var gap={},thin={},pgt=0,ks=[],us=[];for(var i=0;i<DAYS.length;i++){var sl=[];r.forEach(function(n){if(GS[n][i])sl.push(P[n].sl)});var k=sl.length,c=cover(sl),u=c[0]+Math.min(2,k-c[0]);ks[i]=k;us[i]=Math.min(5,u);
if(k<5){thin[i]=u;if(u<k)pgt++;continue}if(u>=5)continue;var un={},it={G:1,F:1,C:1};c[1].forEach(function(S_){S_.forEach(function(x){un[x]=1});["G","F","C"].forEach(function(x){if(S_.indexOf(x)<0)delete it[x]})});
var sure=["G","F","C"].filter(function(x){return !un[x]}),either=["G","F","C"].filter(function(x){return un[x]&&!it[x]});
gap[i]=[k,u,sure.concat(either),sure.concat(either.length?[either.join(" or ")]:[]).join(" + ")]}return {gap:gap,thin:thin,pgt:pgt,ks:ks,us:us}}
function empt(x){var e=0;for(var i in x.gap)e+=5-x.gap[i][1];for(var j in x.thin)e+=5-x.thin[j];return e}
function n_(o){return Object.keys(o).length}
function plays(n,i,fx){return GS[n][i]&&fx.some(function(x){return P[n].sl.indexOf(x)>=0})}
// free agents on your watchlist (the live list from the Watchlist tab once it loads, else tonight's snapshot)
var FAS={};D.fa.concat(D.wl).forEach(function(n){if(P[n]&&D.ra.indexOf(n)<0&&D.ir.indexOf(n)<0)FAS[n.toLowerCase()]=n});
function wlfa(){var o=[];(window.__bblwl||D.wl).forEach(function(n){var k=FAS[(n||"").toLowerCase()];if(k&&o.indexOf(k)<0)o.push(k)});return o}
var X0=scan(D.ra),ST={};try{ST=JSON.parse(localStorage.getItem("bbl-pg")||"{}")||{}}catch(e){}
function opt(sel,list,lab,v){sel.innerHTML=list.map(function(x){return '<option value="'+esc(x[0])+'">'+esc(x[1])+'</option>'}).join("");sel.value=list.some(function(x){return x[0]===v})?v:list[0][0]}
function tile(cls,h,b,s){return '<div class="thk'+(cls?" "+cls:"")+'"><span>'+h+'</span><b>'+b+'</b><small>'+s+'</small></div>'}
function chg(a,b){return '<i class="'+(b>a?"pgw":(b<a?"pgb":""))+'">'+a+" → "+b+'</i>'}   // lower is better: red if it goes up, green if down
// the move's verdict: fewer empty lineup slots is better
function verdict(a,b){var d=b-a;return d>0?["pgm-bad",'<i class="pgpill bad">▲ '+d+' more empty slot'+(d!==1?"s":"")+'</i>']:(d<0?["pgm-good",'<i class="pgpill good">▼ '+(-d)+' fewer empty slot'+(d!==-1?"s":"")+'</i>']:["pgm-even",'<i class="pgpill">no change</i>'])}
function render(save){
var drop=S.drop.value,act=S.act?S.act.value:"",pre=D.ra.filter(function(n){return n!==drop});if(act)pre.push(act);
var XP=scan(pre);
// free agents for the gaps before the add: eligible for a missing slot, by gap nights they play, then FP/G
var fa=D.fa.map(function(n){var c=0;for(var i in XP.gap)if(plays(n,+i,XP.gap[i][2]))c++;return [c,n]}).filter(function(x){return x[0]}).sort(function(a,b){return b[0]-a[0]||P[b[1]].fp-P[a[1]].fp}).slice(0,6);
var ng=n_(XP.gap),wl=wlfa(),fn=fa.map(function(x){return x[1]});
// If I add: the recommended free agents, then the free agents on your watchlist (★ = on both)
function fl(n){var c=0;for(var i in XP.gap)if(plays(n,+i,XP.gap[i][2]))c++;return c}
function ao(n,c,st){return '<option value="'+esc(n)+'">'+(st?"★ ":"")+esc(P[n].s+" ("+P[n].pos+" · "+P[n].t+" · "+(ng?(c?"fills "+c+" of "+ng:"fills none"):P[n].fp.toFixed(1)+" FP/G")+")")+'</option>'}
var wo=wl.filter(function(n){return fn.indexOf(n)<0}).map(function(n){return [fl(n),n]}).sort(function(a,b){return b[0]-a[0]||P[b[1]].fp-P[a[1]].fp});
S.add.innerHTML='<option value="">Nobody</option>'+(fa.length?'<optgroup label="Recommended free agents">'+fa.map(function(x){return ao(x[1],x[0],wl.indexOf(x[1])>=0)}).join("")+'</optgroup>':"")
+(wo.length?'<optgroup label="Your watchlist">'+wo.map(function(x){return ao(x[1],x[0])}).join("")+'</optgroup>':"");
S.add.value=ST.add&&(fn.indexOf(ST.add)>=0||wl.indexOf(ST.add)>=0)?ST.add:"";
var add=S.add.value,room=D.drops.filter(function(n){return pre.indexOf(n)>=0});
opt(S.drop2,[["","Nobody (open roster spot)"]].concat(room.map(function(n){return [n,P[n].s+" ("+P[n].pos+(n===D.stream?", stream slot":"")+")"]})),"",ST.drop2==null?(room.indexOf(D.stream)>=0?D.stream:(room[0]||"")):ST.drop2);
S.drop2.disabled=!add;var drop2=add?S.drop2.value:"";
var fin=pre.filter(function(n){return n!==drop2});if(add)fin.push(add);var XF=add?scan(fin):XP;
if(save){ST={drop:drop,act:act,add:add,drop2:S.drop2.value};try{localStorage.setItem("bbl-pg",JSON.stringify(ST))}catch(e){}}
var irl=D.ir.filter(function(n){return n!==act}),IRF={},IRT={};
irl.forEach(function(n){var x=scan(fin.concat([n]));IRF[n]={};for(var i in XF.gap)if(!x.gap[i]||x.gap[i][1]>XF.gap[i][1])IRF[n][i]=1;var t=0;for(var j in XF.thin)if(x.thin[j]==null||x.thin[j]>XF.thin[j])t++;IRT[n]=t});
var mv=[];if(drop)mv.push("drop "+esc(P[drop].s));if(act)mv.push("activate "+esc(D.irw[act]));if(add)mv.push("add "+esc(P[add].s)+(drop2?" for "+esc(P[drop2].s):""));
var ids=Object.keys(XF.gap).map(Number).sort(function(a,b){return a-b}),cnt={G:0,F:0,C:0};ids.forEach(function(i){XF.gap[i][2].forEach(function(x){cnt[x]++})});
var mx=["G","F","C"].sort(function(a,b){return cnt[b]-cnt[a]})[0],nreg=ids.filter(function(i){return DAYS[i][0]<=21}).length,warn=[];
if(act&&!drop)warn.push("Activating "+esc(P[act].s)+" needs a roster spot: pick who you&#39;d drop in “If I drop” (unless you have an open spot).");
if(add&&!drop2)warn.push("Adding "+esc(P[add].s)+" with nobody dropped only works if you have an open roster spot.");
var e0=empt(X0),e1=empt(XF),vd=verdict(e0,e1);
var h='<div class="thkeys">'+(mv.length?tile("thdr "+vd[0],"If you "+mv.join(" · "),e0+" → "+e1+" "+vd[1],"empty lineup slots · gap nights "+chg(n_(X0.gap),ids.length)+" · thin days "+chg(n_(X0.thin),n_(XF.thin))):"")
+tile("","Position-gap nights left",ids.length,nreg+" regular season · "+(ids.length-nreg)+" playoffs")
+(ids.length?tile("","Slot you&#39;re missing most",{G:"Guard",F:"Forward",C:"Center"}[mx],cnt[mx]+" of "+ids.length+" nights"+["G","F","C"].filter(function(x){return x!==mx&&cnt[x]}).map(function(x){return " · "+x+": "+cnt[x]}).join(""))
 +tile("","Next one",DAYS[ids[0]][1],"P"+DAYS[ids[0]][0]+" · no "+XF.gap[ids[0]][3]+" · "+XF.gap[ids[0]][0]+" of yours playing"):"")
+irl.map(function(n){return tile("thir","If you activate "+esc(D.irw[n]),ids.length?"fixes "+n_(IRF[n])+" of "+ids.length:"no gaps left",(ids.length?"gap nights":"to fix")+(IRT[n]?" · adds a player on "+IRT[n]+" thin day"+(IRT[n]!==1?"s":""):""))}).join("")+'</div>'
+warn.map(function(w){return '<p class="pgwarn">⚠️ '+w+'</p>'}).join("")
+(XF.pgt?'<p class="small" style="margin:0">On <b>'+XF.pgt+'</b> of your thin days a position also costs you one more slot (e.g. 4 playing, only 3 fit).</p>':"");
// table: gaps after the whole move; with an add, the nights he fills stay listed as ✓ filled
var rows=ids.map(function(i){return [i,XF.gap[i],0]});if(add)Object.keys(XP.gap).forEach(function(i){if(!XF.gap[i])rows.push([+i,XP.gap[i],1])});rows.sort(function(a,b){return a[0]-b[0]});
function row(r_){var i=r_[0],g=r_[1],f=r_[2],d=DAYS[i],nw="";
if(!f&&add&&!XP.gap[i])nw=' <span class="tag warn">new with '+esc(P[add].s)+'</span>';else if(!f&&mv.length&&!X0.gap[i])nw=' <span class="tag warn">new</span>';
var fx=irl.filter(function(n){return IRF[n][i]}).map(function(n){return '<span class="tag ok">'+esc(D.irw[n])+'</span>'}).join(" ")||'<span class="thx">—</span>';
return '<tr data-p="'+d[0]+'" class="'+(d[0]>=22?"po":"")+(f?" pgfixed":"")+'"><td>P'+d[0]+'</td><td><b>'+d[1]+'</b>'+nw+'</td><td class="num">'+g[0]+'</td><td class="num"><b>'+g[1]+'</b><small>/5</small></td><td><span class="tag bad">no '+g[3]+'</span>'+(f?'<span class="tag ok">✓ filled by '+esc(P[add].s)+'</span>':"")+'</td><td><span class="gt '+d[4]+'">'+d[5]+'</span> <small>'+d[3]+' games</small></td>'+(irl.length?'<td>'+(f?"":fx)+'</td>':"")+'</tr>'}
h+=rows.length?'<div class="scroll"><table class="pgtab"><thead><tr><th>P</th><th>Night</th><th>Playing</th><th>Usable</th><th>Missing</th><th>NBA slate</th>'+(irl.length?"<th>Fixed if activated</th>":"")+'</tr></thead><tbody>'+rows.map(row).join("")+'</tbody></table></div>':'<p class="muted">None: every night 5+ of your players play, they can fill all 5 slots.</p>';
// thin days the move changes: nights under 5 playing (before or after) where the lineup slots you can fill go up or down; gap nights are in the table above
if(mv.length){var ins=fin.filter(function(n){return D.ra.indexOf(n)<0}),outs=D.ra.filter(function(n){return fin.indexOf(n)<0}),mvs=ins.concat(outs),tc=[],tg=0,tl=0,tsame=0;
for(var i=0;i<DAYS.length;i++){var a=X0.us[i],b=XF.us[i];if(X0.ks[i]>=5&&XF.ks[i]>=5)continue;if(a===b){if(mvs.some(function(n){return GS[n][i]})){tsame++;tc.push(i)}continue}if(b>a)tg++;else tl++;tc.push(i)}
h+='<h3 class="sh">Thin days this move changes</h3><p class="small" style="margin:0 0 6px">Nights fewer than 5 of your players play (before or after the move) where the lineup slots you can fill change: <i class="pgb">'+tg+' better</i> · <i class="pgw">'+tl+' worse</i>'+(tsame?' · '+tsame+' no change (the player coming in and the one going out both play)':'')+'.</p>';
h+=tc.length?'<div class="scroll"><table class="pgtab"><thead><tr><th>P</th><th>Night</th><th>Playing</th><th>Usable</th><th>Why</th><th>NBA slate</th></tr></thead><tbody>'+tc.map(function(i){var d=DAYS[i],a=X0.us[i],b=XF.us[i],up=b>a,eq=a===b,
who=ins.filter(function(n){return GS[n][i]}).map(function(n){return '<span class="tag ok">+ '+esc(P[n].s)+' plays</span>'}).concat(outs.filter(function(n){return GS[n][i]}).map(function(n){return '<span class="tag bad">− '+esc(P[n].s)+'&#39;s game lost</span>'})).join(" ");
return '<tr data-p="'+d[0]+'" class="'+(d[0]>=22?"po ":"")+(eq?"pgtheq":(up?"pgthup":"pgthdn"))+'"><td>P'+d[0]+'</td><td><b>'+d[1]+'</b></td><td class="num">'+X0.ks[i]+' → '+XF.ks[i]+'</td><td class="num"><b>'+a+' → '+b+'</b><small>/5</small> <i class="pgpill'+(eq?"":(up?" good":" bad"))+'">'+(eq?"±0":(up?"+":"−")+Math.abs(b-a))+'</i></td><td>'+who+'</td><td><span class="gt '+d[4]+'">'+d[5]+'</span> <small>'+d[3]+' games</small></td></tr>'}).join("")+'</tbody></table></div>':'<p class="muted">No thin day changes with this move.</p>'}
if(fa.length)h+='<h3 class="sh">Free agents who fill these gaps</h3><div class="scroll"><table class="pgtab"><thead><tr><th>Free agent</th><th>FP/G</th><th>Gap nights he fills</th><th>Nights</th></tr></thead><tbody>'
+fa.map(function(x){var n=x[1],q=P[n],ds=Object.keys(XP.gap).map(Number).sort(function(a,b){return a-b}).filter(function(i){return plays(n,i,XP.gap[i][2])});
return '<tr'+(n===add?' class="pgon"':'')+'><td><b>'+esc(q.s)+'</b> <span class="nbat" data-t="'+esc(q.t)+'">'+esc(q.t)+'</span> <span class="tm">'+esc(q.pos)+'</span></td><td class="num">'+q.fp.toFixed(1)+'</td><td class="num"><b>'+x[0]+'</b><small>/'+ng+'</small></td><td class="pgd">'+ds.slice(0,6).map(function(i){return DAYS[i][2]}).join(" · ")+(ds.length>6?" …":"")+'</td></tr>'}).join("")+'</tbody></table></div>';
out.innerHTML=h}
if(ST.drop&&[].some.call(S.drop.options,function(o){return o.value===ST.drop}))S.drop.value=ST.drop;
if(S.act&&ST.act&&[].some.call(S.act.options,function(o){return o.value===ST.act}))S.act.value=ST.act;
[S.drop,S.act,S.add,S.drop2].forEach(function(e){if(e)e.addEventListener("change",function(){ST.add=S.add.value;ST.drop2=S.drop2.value;render(true)})});
document.addEventListener("bbl-wl",function(){render(false)});
var rb=$("pgreset");if(rb)rb.addEventListener("click",function(){S.drop.value="";if(S.act)S.act.value="";ST={drop:"",act:"",add:"",drop2:""};render(true)});
render(false)})();</script>'''.replace('__PGD__',json.dumps(_PGDATA).replace('</','<\\/'))
_pgsec=(f'''<section><h2>Position gaps · nights you can&#39;t fill 5</h2>
<p class="small" style="margin:0 0 8px">Your lineup is <b>G, F, C + 2 Util</b>. On these nights <b>5 or more</b> of your players have games, but none of them can play one of the G/F/C slots, so a lineup spot sits empty anyway. Thin days (fewer than 5 playing) are in the table below; these are the extra nights you lose to positions. Counts your <b>active roster</b>: IR players aren&#39;t in your lineup until you activate them (which costs a drop), so the gaps they&#39;d fix are shown separately.</p>
{_PGSEL}<div id="pgout" class="pgv"></div>
<p class="small"><b>Try a move</b>: <b>If I drop</b> takes a player off (or makes room to activate an IR player), <b>If I activate</b> puts an IR player in your lineup from his return date, <b>If I add</b> picks one of the free agents recommended for that roster or one on your watchlist (★ = both), and <b>…to make room, drop</b> is who goes for him (your stream slot by default; “Nobody” only if you have an open roster spot). The orange tile sums up the move in <b>empty lineup slots</b> on gap nights and thin days together, since a drop can lower the gap nights only by turning some into thin days. Nights marked <span class="tag warn">new</span> aren&#39;t gaps today; <span class="tag ok">✓ filled</span> ones are gaps the added player fills. <b>Playing</b> = your active players with a game (injured ones from their return date). <b>Usable</b> = how many of them fit the lineup. <b>Missing</b> = the slot nobody playing can fill; “F or C” means one F/C player can cover either, not both. <b>NBA slate</b> = how light the night is: on ◆◆◆ Prime and ◆◆ Good nights few teams play, so a streamer for that slot is harder to find and worth more. <b>Fixed if activated</b> = IR players who&#39;d fill the open slot that night once back. <b>Free agents</b>: healthy, eligible for a missing slot, by how many of these nights they play, then CBS FP/G; check Waivers → Best adds for what he adds overall.</p></section>'''
 +_PGJS
 +'<style>.pgtab th,.pgtab td{vertical-align:middle}.pgtab small{color:var(--muted);font:500 .68rem var(--mono)}.pgtab tr.po{background:var(--pobg)}.pgd{font:500 .72rem var(--mono);color:var(--muted)}.thk.thir{border-left:4px solid var(--ok)}.thk.thdr{border-left:4px solid var(--warn)}.thk.pgm-bad{border-left-color:var(--bad);background:var(--badbg)}.thk.pgm-good{border-left-color:var(--ok);background:var(--okbg)}.thk.pgm-bad>b{color:var(--bad)}.thk.pgm-good>b{color:var(--ok)}'
 '.thk i{font-style:normal}.pgpill{display:inline-block;white-space:nowrap;vertical-align:middle;font:700 .68rem var(--mono);letter-spacing:.02em;padding:2px 8px;border-radius:999px;background:var(--line);color:var(--fg);margin-left:6px}.pgpill.bad{background:var(--bad);color:#fff}.pgpill.good{background:var(--ok);color:#fff}.pgw{color:var(--bad);font-weight:700}.pgb{color:var(--ok);font-weight:700}.pgv{display:grid;gap:10px;min-width:0}'
 '.pgsel{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0 0 8px}.pgsel .dropsel{margin:0}.pgsel select:disabled{opacity:.5}.pgwarn{margin:0;padding:8px 12px;border-radius:8px;background:var(--warnbg);color:var(--fg);font-size:.88rem}'
 '.pgtab tr.pfirst:not(:first-child) td{border-top:2px solid color-mix(in srgb,var(--fg) 35%,transparent)}.pgtab tr.prest td:first-child{color:transparent}'
 '.pgtab tr.pfirst td:first-child{font-weight:700}.pgtab tr.pbodd td:first-child{box-shadow:inset 4px 0 0 color-mix(in srgb,var(--fg) 70%,transparent)}.pgtab tr.pbeven td:first-child{box-shadow:inset 4px 0 0 color-mix(in srgb,var(--muted) 35%,transparent)}'
 'tr.pgthup td{background:var(--okbg)}tr.pgthdn td{background:var(--badbg)}tr.pgtheq td{color:var(--muted)}tr.pgfixed td{background:var(--okbg)}tr.pgfixed .tag.bad{text-decoration:line-through;opacity:.55;margin-right:4px}tr.pgon td{background:var(--okbg)}tr.pgon td:first-child{box-shadow:inset 4px 0 0 #2563eb}</style>')
if R: thin_pane=_pgsec+thin_pane   # position gaps first: the priority on this page
# ---- Draft results (Season → Draft results): every BBL draft, this season's from draft.txt (points from the box scores, so they
# keep up) and past ones from draft_history.txt (cc/draft_history.py, read once from CBS). A team keeps its id when it's renamed,
# so a past pick shows the name that year and who that team is now. Drawn in the browser: pick a draft, group, manager or player.
def _build_draft():
    T={}; TN={}; S=[]; PP=defaultdict(list)
    if os.path.exists('draft_history.txt'):
        for l in open('draft_history.txt',encoding='utf-8'):
            f=l.rstrip('\n').split('|')
            if f[0]=='T' and len(f)>=4: T[int(f[1])]=[f[2],f[3]]; TN[f[2]]=int(f[1])
            elif f[0]=='S' and len(f)>=3: S.append([int(f[1]),f[2]])
            elif f[0]=='P' and len(f)>=13:   # f[8] is empty where CBS has no player for the pick (2024 rounds 10-13)
                PP[int(f[1])].append([int(f[2]),int(f[3]),int(f[4]),f[5],int(f[6]),f[7],f[8],f[9],f[10],int(f[11] or 0),int(f[12] or 0)])
    byk={_rk(n):n for n in INFO}
    cur=[]
    if os.path.exists('draft.txt'):
        for l in open('draft.txt',encoding='utf-8'):
            f=l.rstrip('\n').split('|')
            if len(f)<5 or not f[1].isdigit(): continue
            k=_rk(f[0]); n=byk.get(k); i=TN.get(f[4],0)
            cur.append([int(f[1]),int(f[2]),int(f[3]),f[4],i,T[i][1] if i else '',short(n) if n else f[0],INFO[n]['pos'] if n else '',INFO[n]['team'] if n else '',round(sum(ACT[k].values())) if k in ACT else 0,None])
    out=[]
    if cur: out.append(dict(y='2026-27',t='BBL 2026-2027 DRAFT',cur=1,p=cur))
    for y,t in sorted(S,reverse=True):
        for r in PP[y]:   # a player the page knows opens his card, whatever CBS's spelling
            n=byk.get(_rk(r[6]))
            if n: r[6]=short(n)
        out.append(dict(y=f'{y}-{(y+1)%100:02d}',t=t,cur=0,p=PP[y]))
    if not out: return ''
    tm={i:[dname(v[0]) if 'ɪɴᴏʟᴀ' not in v[0] else "TINOLA JO'CHIĆK",v[1],lgi(LOGO[v[0]]) if v[0] in LOGO else None,int(v[0] in LOGO)] for i,v in T.items()}
    data=dict(d=out,t=tm,me=TN.get(ME,0))
    return ('''<section id="drs"><h2>Draft results</h2>
<p class="small" style="margin:0 0 8px">Every BBL draft, so you don&#39;t need CBS for it. A past pick shows the team&#39;s name that year, and who that team is now if it was renamed. <b>Rank</b> is where the player finished by total FPTS among that draft&#39;s picks. This season&#39;s points update each night from the box scores; past seasons are CBS&#39;s final totals, and <b>Active</b> is what he scored in that manager&#39;s active lineup. A player&#39;s NBA team and positions are today&#39;s.</p>
<div class="pgsel drsel"><label class="dropsel">Draft <select id="drd"></select></label><label class="dropsel">Group by <select id="drv"><option value="r">Round</option><option value="m">Manager</option><option value="p">Position</option></select></label><label class="dropsel">Manager <select id="drm"></select></label><label class="dropsel">Player <input id="drq" type="search" placeholder="Search" autocomplete="off"></label></div>
<div id="drout"></div></section>'''
    +r'''<style>#drs .drsel input{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg);width:11em}#drs tr.drg td{font:700 .78rem var(--mono);letter-spacing:.06em;text-transform:uppercase;background:var(--pobg);padding-top:9px;padding-bottom:7px}#drs tr.drg .mlogo{display:inline-block;vertical-align:middle;margin-right:7px}#drs tr.drg small{font:400 .78rem var(--body);letter-spacing:normal;text-transform:none;color:var(--muted);margin-left:8px}
#drs .drw{display:flex;align-items:center;gap:7px;white-space:nowrap}#drs .drw .mlogo{flex:none}#drs .drw small{display:block;color:var(--muted);line-height:1.2}#drs tr.drme>td{background:color-mix(in srgb,var(--accent) 9%,transparent)}#drs tr.drme>td:first-child{box-shadow:inset 3px 0 0 var(--accent)}#drs .drpl small{color:var(--muted);margin-left:5px}</style>
<script>(function(){var A=__DRD__,T=A.t,$=function(i){return document.getElementById(i)},S=$("drd"),V=$("drv"),M=$("drm"),Q=$("drq"),O=$("drout");if(!S||!O)return;
function esc(t){var d=document.createElement("div");d.textContent=t==null?"":t;return d.innerHTML}
var ST={};try{ST=JSON.parse(localStorage.getItem("bbl-dr")||"{}")||{}}catch(e){}
S.innerHTML=A.d.map(function(d,i){return '<option value="'+i+'">'+esc(d.y+" · "+d.t)+'</option>'}).join("");S.value=A.d[+ST.d]?String(+ST.d):"0";V.value=/^[rmp]$/.test(ST.v||"")?ST.v:"r";
function logo(i,sz){var x=T[i];return x&&x[2]!=null?'<img data-lg="'+x[2]+'" width="'+sz+'" height="'+sz+'" alt="" class="mlogo">':'<span class="mlogo ph" style="width:'+sz+'px;height:'+sz+'px"></span>'}
function now(p){var x=T[p[4]];return x&&x[3]&&x[0]!==p[3]&&!(x[0].indexOf("TINOLA")===0&&p[3].indexOf("ɪɴᴏʟᴀ")>=0)?x[0]:""}
function nm(p){return p[3].indexOf("ɪɴᴏʟᴀ")>=0?"TINOLA JO'CHIĆK":p[3]}
function mans(d){var o={},L=[];d.p.forEach(function(p){var k=p[4]+"|"+p[3];if(!o[k]){o[k]=1;L.push([k,nm(p),now(p)])}});return L.sort(function(a,b){return a[1].toLowerCase()<b[1].toLowerCase()?-1:1})}
function fillm(d,v){M.innerHTML='<option value="">All managers</option>'+mans(d).map(function(x){return '<option value="'+esc(x[0])+'">'+esc(x[1]+(x[2]?" (now "+x[2]+")":""))+'</option>'}).join("");M.value=[].some.call(M.options,function(o){return o.value===v})?v:""}
function draw(save){var d=A.d[+S.value],v=V.value,m=M.value,q=Q.value.trim().toLowerCase(),rk={};
d.p.filter(function(p){return p[6]}).sort(function(a,b){return b[9]-a[9]}).forEach(function(p,i){rk[p[2]]=i+1});var nop=d.p.filter(function(p){return !p[6]}).length;
if(save)try{localStorage.setItem("bbl-dr",JSON.stringify({d:+S.value,v:v}))}catch(e){}
var P=d.p.filter(function(p){return (!m||p[4]+"|"+p[3]===m)&&(!q||p[6].toLowerCase().indexOf(q)>=0)}).sort(function(a,b){return a[2]-b[2]});
if(!P.length){O.innerHTML='<p class="muted">No picks match.</p>';return}
var G=[],ix={};P.forEach(function(p){var k=v==="r"?"r"+p[0]:(v==="m"?p[4]+"|"+p[3]:"p"+(p[7].split(",")[0]||"?"));if(!ix[k]){ix[k]={k:k,p:p,r:[]};G.push(ix[k])}ix[k].r.push(p)});
if(v==="m")G.sort(function(a,b){return a.p[2]-b.p[2]});if(v==="p")G.sort(function(a,b){return a.k<b.k?-1:1});
var n=d.cur?7:8,h='<div class="scroll"><table class="drt"><thead><tr><th>Pick</th><th>Overall</th><th>Manager</th><th>Player</th><th>Elig</th><th>FPTS</th>'+(d.cur?'':'<th>Active</th>')+'<th>Rank</th></tr></thead>';
G.forEach(function(g){var t=g.p,ti="";if(v==="r")ti="Round "+t[0];else if(v==="p")ti=t[7].split(",")[0]||"Unknown";else{var w=now(t);ti=logo(t[4],22)+esc(nm(t))+(w?' <small>now '+esc(w)+'</small>':'')+(t[5]?' <small>'+esc(t[5])+'</small>':'')}
var fs=0;g.r.forEach(function(p){fs+=p[9]});h+='<tbody><tr class="drg"><td colspan="'+n+'">'+ti+' <small>'+g.r.length+' pick'+(g.r.length!==1?'s':'')+' · '+fs.toLocaleString()+' FPTS</small></td></tr>'
+g.r.map(function(p){var w=now(p);return '<tr'+(p[4]===A.me?' class="drme"':'')+'><td>'+p[0]+'.'+(p[1]<10?'0':'')+p[1]+'</td><td class="num">'+p[2]+'</td><td><div class="drw">'+logo(p[4],22)+'<div>'+esc(nm(p))+(w?'<small>now '+esc(w)+'</small>':'')+'</div></div></td><td class="drpl">'+(p[6]?'<b>'+esc(p[6])+'</b>'+(p[8]?'<small>'+esc(p[8])+'</small>':''):'<span class="muted">Not on CBS</span>')+'</td><td>'+esc(p[7])+'</td><td class="num">'+(p[6]?p[9].toLocaleString():'—')+'</td>'+(d.cur?'':'<td class="num">'+(p[6]?p[10].toLocaleString():'—')+'</td>')+'<td class="num">'+(rk[p[2]]||'—')+'</td></tr>'}).join("")+'</tbody>'});
O.innerHTML=(nop?'<p class="pgwarn" style="margin:0 0 8px">CBS has no player for '+nop+' of this draft&#39;s picks (the manager and pick are there, the player is blank), so they show as “Not on CBS”.</p>':'')+h+'</table></div>'}
S.addEventListener("change",function(){fillm(A.d[+S.value],"");draw(true)});V.addEventListener("change",function(){draw(true)});M.addEventListener("change",function(){draw(false)});Q.addEventListener("input",function(){draw(false)});
fillm(A.d[+S.value],"");draw(false)})();</script>'''.replace('__DRD__',json.dumps(data).replace('</','<\\/')))
draftsec=_build_draft()
# ---- Top 150 (Season → Top 150): every NBA player ranked by this season's slot points, with who owns him
_CB={_rk(n):n for n in INFO}
def _t150row(i,k):
    n=_CB.get(k); bn,bt,bp=BOXP.get(k,(k,'',''))
    name,team,pos=(n,INFO[n]['team'],INFO[n]['pos']) if n else (bn,bt,bp)
    o=INFO[n]['own'] if n else 'FA'; v=ACT[k]; gp=len(v); tot_=ATOT[k]
    if o=='MINE': who,cls=f'{lg(ME,20)} <span class="yours">YOURS</span>','t150me'
    elif o.startswith('TAKEN:'): who,cls=f'{lg(o[6:],20)} {html.escape(tdn(o[6:]))}',''
    else: who,cls='<span class="fa">FREE AGENT</span>'+(wbtn(n) if n else ''),'t150fa'
    return (f'<tr class="{cls}"><td class="num">{i}</td><td><b>{html.escape(name)}</b> <span class="tm">{pos} · {team}</span></td><td class="who">{who}</td>'
            f'<td class="num">{gp}</td><td class="num"><b>{_f(tot_)}</b></td><td class="num">{tot_/max(1,gp):.1f}</td>'
            f'<td class="num">{_f(sum(v.get(d,0) for d in _pd))}</td><td class="num">{_f(v.get(LASTN)) if LASTN in v else "—"}</td>'
            +f'<td class="num">{_f(prank(n)) if n else "—"}</td></tr>')
_t150=sorted(ATOT,key=lambda k:(-ATOT[k],k))
_t150=[(1+sum(1 for x in _tv if x>ATOT[k]),k) for k in _t150 if 1+sum(1 for x in _tv if x>ATOT[k])<=150]
_nfa=sum(1 for _,k in _t150 if not (_CB.get(k) and INFO[_CB[k]]['own']!='FA'))
top150_pane=(f'''<section><h2>Top 150 players · season</h2>
<p class="small" style="margin:0 0 8px">Every NBA player ranked by this season&#39;s BBL points with the slot bonus (like CBS&#39;s game log), through {_md(_ld) if _ld else "—"}. {_nfa} of the top 150 are <span class="fa">FREE AGENTS</span>. Click a header to sort, e.g. FP/G.</p>
<div class="scroll"><table class="t150"><thead><tr><th>Rank</th><th>Player</th><th>Manager</th><th>GP</th><th>Total</th><th>FP/G</th><th>Prd. {APER}</th><th>{_md(_ld) if _ld else "Last"}</th><th>Proj rank</th></tr></thead>
<tbody>{"".join(_t150row(i,k) for i,k in _t150)}</tbody></table></div>
<p class="small">Points are recomputed from ESPN box scores with the league scoring. Proj rank = CBS projected FP/G (best slot) among all players; — means CBS doesn&#39;t project him.</p></section>'''
 +'<style>.t150{min-width:760px}.t150 td{vertical-align:middle}.t150 .who{white-space:nowrap}.t150 .who .mlogo{display:inline-block;vertical-align:middle;margin-right:4px}'
 '.fa{display:inline-block;font:700 .66rem var(--mono);letter-spacing:.06em;color:#fff;background:#15803d;border-radius:4px;padding:2px 6px;vertical-align:middle}'
 '.t150 tr.t150fa td{background:color-mix(in srgb,#15803d 9%,transparent)}.t150 tr.t150me td{background:color-mix(in srgb,var(--accent) 10%,transparent)}</style>') if _t150 else '<p class="muted">No games played yet.</p>'
if MU and MU[0]['p'] in MUADJ:
    _m0=MU[0]; _a=MUADJ[_m0['p']]; _old=mcard(_m0,True)
    _m1=dict(_m0); _m1.update(mine=_a['mine'],opp_p=_a['opp_p'],wp=_a['wp'])
    if _m0.get('add'):
        _sd=0.11*math.sqrt(_a['mine']**2+_a['opp_p']**2) or 1; _g=_m0['add'][1]
        _m1['add']=(_m0['add'][0],_g,0.5*(1+math.erf((_a['mine']+_g-_a['opp_p'])/(_sd*math.sqrt(2)))))
    _new=mcard(_m1,True)+(f'<p class="small" style="margin:6px 0 0">Matchup-adjusted: opponent defenses add {_a["dme"]:+.0f} for you and {_a["dop"]:+.0f} for them '
          f'(projection only: {_m0["mine"]:,.0f}–{_m0["opp_p"]:,.0f}, {_a["base_wp"]*100:.0f}%). Day-by-day lineups: <a href="#startsit" class="mulink">This period → Start/Sit</a>.</p>'
          '<script>[].forEach.call(document.querySelectorAll(".mulink"),function(a){a.addEventListener("click",function(e){e.preventDefault();if(window.__sub)window.__sub("pmu")})});</script>')
    if _old in thisp: thisp=thisp.replace(_old,_new,1)
# click any table header to sort (numbers start high-to-low, text A–Z); tables with their own sorter (.sortbtn) are skipped,
# rows spanning several columns (group headers, "none" notes) stay put and the rows between them sort as a block
TABSORT=r"""<script>(function(){var CO=window.Intl&&Intl.Collator?new Intl.Collator(undefined,{numeric:true,sensitivity:'base'}):null;
function txt(c){return c?c.textContent.replace(/\s+/g,' ').trim():''}
function num(t){var m=t.replace(/−/g,'-').replace(/,/g,'').match(/^[^\d+\-.]{0,3}([+\-]?\d*\.?\d+)/);return m?parseFloat(m[1]):null}
function blank(t){return t===''||t==='—'||t==='–'||t==='-'}
function head(tb){var h=tb.tHead,r=h&&h.rows.length?h.rows[h.rows.length-1]:null;if(!r&&tb.rows.length&&[].every.call(tb.rows[0].cells,function(c){return c.tagName==='TH'}))r=tb.rows[0];return r}
function segs(tb,hr){var n=hr.cells.length,out=[];[].forEach.call(tb.tBodies,function(b){var cur=[];[].forEach.call(b.rows,function(r){if(r===hr)return;if(r.cells.length===n&&![].some.call(r.cells,function(c){return c.colSpan>1}))cur.push(r);else{if(cur.length)out.push(cur);cur=[]}});if(cur.length)out.push(cur)});return out}
function isnum(ss,i){var v=[].concat.apply([],ss).map(function(r){return txt(r.cells[i])}).filter(function(t){return !blank(t)});return v.length>0&&v.filter(function(t){return num(t)!==null}).length>=v.length*0.6}
function sort(ss,i,d,nn){ss.forEach(function(seg){var p=seg[0].parentNode,at=seg[seg.length-1].nextSibling;seg.map(function(r,k){var t=txt(r.cells[i]);return {r:r,k:k,v:blank(t)?null:(nn?num(t):t)}}).sort(function(a,b){if(a.v===null||b.v===null)return a.v===b.v?a.k-b.k:(a.v===null?1:-1);var c=nn?a.v-b.v:(CO?CO.compare(a.v,b.v):(a.v<b.v?-1:a.v>b.v?1:0));return c*d||a.k-b.k}).forEach(function(x){p.insertBefore(x.r,at)})})}
function prep(tb){tb.setAttribute('data-xs','');var hr=head(tb);if(!hr||hr.querySelector('.sortbtn')||[].some.call(hr.cells,function(c){return c.colSpan>1||c.rowSpan>1}))return;var st={i:-1,d:1};
[].forEach.call(hr.cells,function(th,i){if(!txt(th))return;var b=document.createElement('button');b.type='button';b.className='sortbtn';while(th.firstChild)b.appendChild(th.firstChild);var a=document.createElement('span');a.className='arr';a.textContent=' ↕';b.appendChild(a);th.appendChild(b);th.setAttribute('aria-sort','none');
b.addEventListener('click',function(){var ss=segs(tb,hr),nn=isnum(ss,i);st.d=st.i===i?-st.d:(nn?-1:1);st.i=i;sort(ss,i,st.d,nn);[].forEach.call(hr.cells,function(c,j){if(!c.hasAttribute('aria-sort'))return;c.setAttribute('aria-sort',j===i?(st.d>0?'ascending':'descending'):'none');var x=c.querySelector('.sortbtn>.arr');if(x)x.textContent=j===i?(st.d>0?' ▲':' ▼'):' ↕'})})})}
// rows with data-p (one per night): each run of the same period is one band: a line above it, the P shown once, alternating shades
function band(tb){var last=null,k=0;[].forEach.call(tb.querySelectorAll('tbody tr'),function(r){var p=r.getAttribute('data-p');if(p==null)return;var nw=p!==last;if(nw){k++;last=p}r.classList.toggle('pfirst',nw);r.classList.toggle('prest',!nw);r.classList.toggle('pbodd',k%2===1);r.classList.toggle('pbeven',k%2===0)})}
function scan(){[].forEach.call(document.querySelectorAll('table:not([data-xs])'),prep);[].forEach.call(document.querySelectorAll('table'),function(t){if(t.querySelector('tr[data-p]'))band(t)})}
scan();var q=0;new MutationObserver(function(){if(q)return;q=1;setTimeout(function(){q=0;scan()},0)}).observe(document.body,{childList:true,subtree:true})})();</script>"""
# ---- Player card: click a player's name (any <b>Name</b> on the page) for one panel with his schedule, form, usage, owner,
# value to you and news. Data (PCD) for every rostered player and the top free agents; drawn by PCJS (added after the tag passes).
# ---- Buy low · sell high (Trades tab, and a line on the player card): this season's FP/G (box scores, CBS game-log points)
# against CBS's projection, explained by shooting luck vs his last full season (careers.txt) with steady minutes. A hot player
# shooting far above his norm is a sell-high (yours) or "may not last" (anyone else's); a cold one shooting far below it with
# his minutes intact is a buy-low (a rival's) or "don't sell low" (yours). Bigger minutes = a real role change, not luck.
BLS={}   # name -> (kind: sell / hold / buy / fade, headline, [reasons])
def _build_bls():
    global blsec
    today=TODAY.strftime('%Y%m%d')
    for n in list(R)+[m for ro in OTH.values() for m in ro]+[m for m in FA if INFO[m]['best']>=20]:
        k=_rk(n); ds=[d for d in STL.get(k,{}) if '20261020'<=d<today]
        cbs=CBSFP.get(n,0); g=len(ds)
        if g<4 or cbs<=0: continue
        s=[sum(STL[k][d][j] for d in ds) for j in range(6)]; mi,_,fgm,fga,tpm,tpa=s
        fpg=sum(ACT[k][d] for d in ds)/g; diff=fpg-cbs
        last=[c for c in CAR.get(ESPNID.get(_ek(n)),[]) if c[2]>=20]
        if not last or abs(diff)<4 or abs(diff)<0.12*cbs: continue
        _,_,lg,lm,lfgm,lfga,ltpm,ltpa=last[-1][:8]; se=last[-1][0]
        if not lfga: continue
        mpg,lmpg=mi/g,lm/lg; fg,lfg=(fgm/fga if fga else 0),lfgm/lfga
        tp=tpm/tpa if tpa else None; ltp=ltpm/ltpa if ltpa else None
        shoot3=tpa/g>=3 and ltpa/lg>=2 and tp is not None and ltp is not None
        why=[f'{fpg:.1f} FP/G in {g} games vs CBS {cbs:.1f}']
        hot=[];cold=[]
        if fga/g>=6 and fg-lfg>=0.05: hot.append(f'FG {fg:.0%} vs {lfg:.0%} in {se}')
        if fga/g>=6 and lfg-fg>=0.05: cold.append(f'FG {fg:.0%} vs {lfg:.0%} in {se}')
        if shoot3 and tp-ltp>=0.08: hot.append(f'3PT {tp:.0%} vs {ltp:.0%}')
        if shoot3 and ltp-tp>=0.08: cold.append(f'3PT {tp:.0%} vs {ltp:.0%}')
        mins=f'{mpg:.0f} min vs {lmpg:.0f} in {se}'
        role=mpg>=1.15*lmpg; steady=mpg>=0.9*lmpg
        mine=n in R
        if diff>0 and hot and not role:
            BLS[n]=('sell' if mine else 'fade','Sell-high candidate' if mine else 'Hot shooting: may not last',why+hot+[mins])
        elif diff<0 and cold and steady:
            BLS[n]=('hold' if mine else 'buy',"Don't sell low" if mine else ('Buy-low target' if n not in FA else 'Likely to bounce back'),why+cold+[mins+' (steady)'])
    _tn=lambda k:"TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in k else k
    def row(n,who):
        kind,_,w=BLS[n]; fpg=w[0].split(' ')[0]
        return (f'<tr><td><b>{html.escape(short(n))}</b> <span class="nbat" data-t="{INFO[n]["team"]}">{INFO[n]["team"]}</span> <span class="tm">{INFO[n]["pos"]}</span></td>'
                +(f'<td>{html.escape(who)}</td>' if who is not None else '')
                +f'<td class="num"><b>{fpg}</b></td><td class="num">{CBSFP[n]:.1f}</td><td class="small">{html.escape(" · ".join(w[1:]))}</td></tr>')
    gap=lambda n:abs(float(BLS[n][2][0].split(' ')[0])-CBSFP[n])
    sell=sorted((n for n,v in BLS.items() if v[0]=='sell'),key=lambda n:-gap(n))
    hold=sorted((n for n,v in BLS.items() if v[0]=='hold'),key=lambda n:-gap(n))
    buy=sorted((n for n,v in BLS.items() if v[0]=='buy' and INFO[n]['own'].startswith('TAKEN:')),key=lambda n:-gap(n))[:12]
    H='<th>This season FP/G</th><th>CBS FP/G</th><th>Why it may not last</th>'
    yours=''.join(row(n,'Sell high') for n in sell)+''.join(row(n,"Don't sell low") for n in hold)
    blsec=('<section id="buysell"><h2>Buy low · sell high</h2>'
           +('<h3>Your players</h3><div class="scroll"><table class="blstab"><thead><tr><th>Player</th><th>Move</th>'+H+'</tr></thead><tbody>'+yours+'</tbody></table></div>' if yours else
             '<p class="muted">None of your players is running hot or cold on shooting luck right now.</p>')
           +('<h3>Buy-low targets on rival rosters</h3><div class="scroll"><table class="blstab"><thead><tr><th>Player</th><th>Manager</th>'+H.replace('Why it may not last','Why he should bounce back')+'</tr></thead><tbody>'
             +''.join(row(n,_tn(INFO[n]['own'][6:])) for n in buy)+'</tbody></table></div>' if buy else '<p class="muted">No buy-low targets on rival rosters right now.</p>')
           +'<p class="small">This season&#39;s FP/G (CBS game-log points) against CBS&#39;s projection, 4+ games and at least 4 points (and 12%) off it. '
           '<b>Sell high</b>: your player is scoring above his projection mostly because he&#39;s shooting far better than last season (FG +5 points or 3PT +8) without more minutes, so his value may be at its peak. '
           '<b>Don&#39;t sell low / buy low</b>: scoring below projection because of cold shooting while his minutes held up (90%+ of last season&#39;s), so he should recover. '
           'More minutes than last season means a real role change and isn&#39;t flagged. Early in the season the samples are small: treat these as leads, not verdicts. '
           'The player card shows the same flag for any player.</p></section>'
           '<style>.blstab td:last-child{min-width:260px}</style>')
_build_bls()
tradepane=tradepane.replace('<section id="ttargets">',blsec+'<section id="ttargets">',1)
def _build_pcard():
    global PCJS
    cols=[(f'P{p}'+(' · now' if p==CUR else ''),[p]) for p in REG]+([('Rest of reg.',REG)] if REG else [])+([('Playoffs',PO)] if PO else [])
    CX=[int(3<=k<len(REG)) for k in range(len(cols))]   # periods after the next 3: shown with Show all periods
    fa=sorted([n for n in FA if n in INFO],key=lambda n:-INFO[n]['best'])[:120]
    names=list(dict.fromkeys(list(R)+[n for ro in OTH.values() for n in ro]+fa+[n for n in watch if n in INFO]+[n for n,i_ in INFO.items() if i_['own'].startswith('TAKEN:') and i_['sec']=='I']))
    news=defaultdict(list)
    for (w,src,txt),(_,ns) in sorted(STORY.items(),key=lambda kv:-kv[0][0].timestamp()):
        for n in ns: news[n].append([(w-dt.timedelta(hours=6)).strftime('%a %-I:%M %p'),src,txt[:400]])
    # stats table like CBS's player page: this season, last 3 games, on pace (82 team games), CBS projection.
    # FPTS = base + slot bonus as CBS's game log (ACT); regular-season games only (from Oct 20)
    def statrows(n,t):
        k=_rk(n); ds=sorted(d for d in STL.get(k,{}) if d>='20261020' and d<TODAY.strftime('%Y%m%d'))
        el=[x for x in INFO[n]['pos'].split(',') if x in ('G','F','C')]
        def fpts(pts,fgm,fga,ftm,fta,reb,ast,stl,blk,to,pf,tpm):   # BBL points from totals (linear, so exact per season)
            bon={'G':reb,'F':ast,'C':tpm}
            sb=bon[PRIMK[k]] if len(el)>1 and k in PRIMK else max([bon[x] for x in el] or [0])
            return pts+2*fgm-fga+ftm-fta+reb+2*ast+4*stl+4*blk-2*to-pf+sb
        def fmt(lab,T,scale=None,gl=None):   # T: games, min, fgm, fga, 3pm, 3pa, ftm, fta, reb, ast, stl, blk, to, pts, fpts
            g,mi,fgm,fga,tpm,tpa,ftm,fta,reb,ast,stl,blk,to,pts,fp=T
            if not g: return None
            pg=lambda x:f'{x/g:.1f}'; pc=lambda a,b:f'{100*a/b:.1f}' if b else '0.0'; sc=scale or 1
            cnt=(lambda x:str(int(x*sc))) if scale else (lambda x:f'{x:.0f}')   # CBS rounds pace down
            return [lab,gl or str(round(g*sc)),pg(mi),cnt(fgm),pc(fgm,fga),cnt(ftm),pc(ftm,fta),cnt(tpm),pc(tpm,tpa),
                    pg(reb),pg(ast),pg(stl),pg(to),pg(blk),pg(pts),f'{fp/g:.2f}',f'{fp*sc:,.0f}']
        def box(dl):
            s=[sum(STL[k][d][j] for d in dl) for j in range(14)]; mi,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,to,stl,blk,pf=s
            return (len(dl),mi,fgm,fga,tpm,tpa,ftm,fta,reb,ast,stl,blk,to,pts,sum(ACT[k].get(d,0) for d in dl))
        out_=[]
        if ds:
            out_.append(fmt('2026-27',box(ds)))
            if len(ds)>3: out_.append(fmt('Last 3 games',box(ds[-3:])))
            tg=sum(1 for d in G.get(t,()) if dt.date(2026,10,20)<=d<TODAY)   # his team's games so far
            if tg: out_.append(fmt('On pace',box(ds),82/tg))
        cf,cg=CBSFP.get(n,0),CBSGP.get(n,0)
        if cf: out_.append(['CBS projection',f'{cg:.1f}']+['—']*13+[f'{cf:.2f}',f'{cf*cg:,.0f}'])
        if n in proj: out_.append(['Your projection',f'{INFO[n]["gp"]:.1f}']+['—']*13+[f'{INFO[n]["best"]:.2f}',f'{INFO[n]["best"]*INFO[n]["gp"]:,.0f}'])
        # past seasons (careers.txt, ESPN): the last 3, their average per season, and career including this season
        past=[]
        for se,tm,gp,mi,fgm,fga,tpm,tpa,ftm,fta,reb,ast,stl,blk,to,pf,pts in CAR.get(ESPNID.get(_ek(n)),[]):
            past.append((se,tm,(gp,mi,fgm,fga,tpm,tpa,ftm,fta,reb,ast,stl,blk,to,pts,fpts(pts,fgm,fga,ftm,fta,reb,ast,stl,blk,to,pf,tpm))))
        if past:
            l3=past[-3:]
            if len(l3)>=2:
                s=[sum(x[2][j] for x in l3) for j in range(15)]
                r=fmt(f'{len(l3)}-season avg',s,gl=f'{s[0]/len(l3):.0f}')
                if r: r[-1]=f'{s[14]/len(l3):,.0f}'; r[3],r[5],r[7]=(f'{s[j]/len(l3):.0f}' for j in (2,6,4)); out_.append(r)
            for se,tm,T in reversed(l3): out_.append(fmt(f'{se} · {tm}',T))
            s=[sum(x[2][j] for x in past) for j in range(15)]
            if ds: s=[a+b for a,b in zip(s,box(ds))]
            out_.append(fmt(f'Career ({len(past)+(1 if ds else 0)} seasons)',s))
        return [r for r in out_ if r]
    def bonk(n):   # the stat his slot bonus counts (G: REB, F: AST, C: 3PM), as ACT: CBS primary for a two-position player, else his best
        k=_rk(n); el=[x for x in INFO[n]['pos'].split(',') if x in ('G','F','C')]
        return [PRIMK[k]] if len(el)>1 and k in PRIMK else el
    def gamelog(n,t):   # newest first, like CBS's Game Log: DATE OPP MIN FG FGA 3PT 3PTA FT FTA REB AST ST BK TO PF PTS FPTS
        # plus his team's games he sat out (DNP: [date, opp]); his team on a date = the one of his nearest game before it (after a trade), else his team now
        k=_rk(n); r=[]; gs=STL.get(k,{}); pd=sorted(gs)
        def team(d):
            b=[x for x in pd if x<=d]; return gs[b[-1]][-1] if b else (gs[pd[0]][-1] if pd else t)
        for d in sorted({d for d in gs if d>='20261020'}|{d for d in ADAYS if d>='20261020' and d not in gs and (d,team(d)) in GOPP},reverse=True):
            if d not in gs: r.append([f'{int(d[4:6])}/{d[6:]}',GOPP[(d,team(d))]]); continue
            mi,pts,fgm,fga,tpm,tpa,ftm,fta,reb,ast,to,stl,blk,pf,tm=gs[d]
            r.append([f'{int(d[4:6])}/{d[6:]}',GOPP.get((d,tm),'')]+[f'{x:.0f}' for x in (mi,fgm,fga,tpm,tpa,ftm,fta,reb,ast,stl,blk,to,pf,pts)]+[f'{ACT[k].get(d,0):g}'])
        return r
    D={}
    for n in names:
        i=INFO[n]; t=i['team']; o=i['own']
        own='yours' if o=='MINE' else (("TINOLA JO'CHIĆK" if 'ɪɴᴏʟᴀ' in o else o[6:]) if o.startswith('TAKEN:') else 'FA')
        # the manager who rosters him: name and logo (an index into the page's logos, so each is embedded once)
        _mt=ME if o=='MINE' else (o[6:] if o.startswith('TAKEN:') else None)
        _ml=next((u for k,u in LOGO.items() if k==_mt or (_mt and 'ɪɴᴏʟᴀ' in k and 'ɪɴᴏʟᴀ' in _mt)),None)
        av=lambda ps:sum(1 for p in ps for d in P[p] if d in G.get(t,()) and not (n in out and d<out[n]) and not sits(n,t,d))
        if n in R: vk,vv='Worth to your lineups',MV.get(n)
        elif n in GA: vk,vv='If you add him (drop '+short(STREAM)+')',GA[n]
        elif n in GT: vk,vv='If he took your stream slot',GT[n]
        else: vk,vv=None,None
        f3,fs=form(n,3),form(n); u=usg(n)
        # % of all CBS leagues: rostered/started from his CBS team page (players on a roster here); free agents from CBS trends
        _dl=lambda d:f'▲{d:g}' if d>0 else (f'▼{-d:g}' if d<0 else '±0')   # (_a is reused later in the file)
        _ro,_st=i.get('rost',''),i.get('start','')
        if _ro: ro=f'{_ro}% of CBS leagues'+(f' · started in {_st}%' if _st else '')+(f' · {_dl(RT[n][2])} this week' if n in RT else '')
        elif n in RT: ro=f'{RT[n][1]}% of CBS leagues · {_dl(RT[n][2])} this week'
        else: ro=''
        D[short(n)]=dict(ro=ro,h=ESPNID.get(_ek(n)),t=t,p=i['pos'],o=own,on=MEDISP if o=='MINE' else own,ol=lgi(_ml) if _ml else None,ij=[injk(i['inj']),i['inj']] if i.get('inj') else (['none','No injury listed on CBS'] if i['sec']=='I' and HASINJ else None),fp=round(CBSFP.get(n,0),1),yf=round(i['best'],1) if n in proj else None,gp=round(i['gp']),f3=f3,fs=fs,ir=i['sec']=='I',
            out=out[n].strftime('%b %-d') if n in out and out[n]>TODAY else None,rest=n in REST,N=n,
            g=[av(ps) for _,ps in cols],b2b=b2bn(t),
            vk=vk,v=[round(sum(vv.get(p,0) for p in ps)) for _,ps in cols] if vv else None,
            tt=[round(TTGAIN[n][0]),round(TTGAIN[n][1])] if n in TTGAIN else None,
            u=[round(u['season'],1),round(u['l3'],1)] if u and u.get('season') is not None and u.get('l3') is not None else None,
            bs=list(BLS[n]) if n in BLS else None,nw=news.get(n,[])[:3],st=statrows(n,t),gl=gamelog(n,t),bio=bioline(n),
            ps=[[se,str(int(se[:4])+1)] for se in reversed([c[0] for c in CAR.get(ESPNID.get(_ek(n)),[])])],bk=bonk(n))
    PCJS=(r'''<style>#pcard{position:fixed;top:0;right:0;bottom:0;width:min(720px,100%);z-index:60;background:var(--panel);border-left:1px solid var(--line);box-shadow:-8px 0 24px rgba(0,0,0,.25);overflow:auto;padding:18px 20px 28px}
#pcard h2{margin:0 30px 2px 0}#pcard .pch{display:flex;gap:14px;align-items:center;margin:0 30px 10px 0}#pcard .pch h2{margin:0 0 4px}#pcard .pch p{margin:0}#pcard .pcbio{margin:4px 0 0;color:var(--muted)}#pcard .pcf{position:relative;flex:none;width:84px;height:84px;border-radius:50%;overflow:hidden;background:var(--pobg);border:2px solid var(--line);display:grid;place-items:center;font:700 1.6rem var(--display);color:var(--muted)}#pcard .pcf img{position:absolute;left:50%;bottom:0;height:100%;transform:translateX(-50%)}#pcard .x{position:absolute;top:10px;right:12px;font:600 1.2rem var(--body);background:none;border:0;color:var(--muted);cursor:pointer;padding:6px}
#pcard table{width:100%;margin:6px 0 12px}#pcard td,#pcard th{padding:5px 6px}#pcard h3{font:600 .95rem var(--display);text-transform:uppercase;letter-spacing:.03em;margin:14px 0 4px;color:var(--accent)}
#pcard .pcst{font-size:.78rem;min-width:640px;margin:4px 0 0}#pcard .pcst th,#pcard .pcst td{padding:4px 5px;text-align:right;white-space:nowrap}#pcard .pcst th:first-child,#pcard .pcst td:first-child{text-align:left}#pcard .pcst td.fp{font-weight:700}#pcard .pcglsc{overflow:auto}#pcard .pcglsc thead th{position:sticky;top:0;z-index:1;background:var(--panel);box-shadow:0 1px 0 var(--line)}#pcard .pcgls{font:600 .8rem var(--body);margin-left:8px;padding:2px 6px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--fg);text-transform:none;letter-spacing:normal;vertical-align:middle}#pcard .pcgl tr.pcdnp td{color:var(--muted);font-style:italic}#pcard .pcgl tr.pcdnp td[colspan]{text-align:center;letter-spacing:.04em}#pcard .fh2{--h:#14b8a6}#pcard .fh3{--h:#22c55e}#pcard .fh4{--h:#f97316}#pcard .fh5{--h:#eab308}#pcard td[class*=fh],#pcard .fhleg span{color:color-mix(in srgb,var(--h) 80%,var(--fg))}#pcard .fhleg span{font:700 .75rem var(--mono)}#pcard .pcst tr.cur{background:color-mix(in srgb,#2563eb 9%,transparent);box-shadow:inset 0 2px 0 #2563eb,inset 0 -2px 0 #2563eb}#pcard .pcst tr.cur td{border-bottom-color:transparent}#pcard .pcgl{min-width:660px}#pcard .pcgl th:nth-child(2),#pcard .pcgl td:nth-child(2){text-align:left}#pcard .kv{display:grid;grid-template-columns:auto 1fr;gap:2px 14px;font-size:.92rem}#pcard .kv b{font-weight:600}#pcard li{margin:4px 0;font-size:.88rem}#pcard .pcbs{margin:10px 0 0;padding:7px 10px;border-radius:8px;font-size:.88rem;background:var(--warnbg)}#pcard .pcbs.sell,#pcard .pcbs.buy{background:var(--okbg)}
.injt{display:inline-block;white-space:nowrap;vertical-align:middle;font:700 .68rem var(--mono);letter-spacing:.02em;padding:1px 7px;border-radius:999px;background:var(--badbg);color:var(--bad)}.injt.gtd{background:var(--warnbg);color:var(--warn)}.injt.irno{background:#facc15;color:#1c1917}#pcard p.pcinj{margin:4px 0 0}
#pcard .pcown{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:6px 0 0;font-size:.9rem}#pcard .pcown .mlogo{flex:none}#pcard .pcfa{font:700 .78rem var(--mono);padding:2px 9px;border-radius:999px;background:var(--okbg);color:var(--ok)}
#pcard .pcact{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 0}#pcard .pcact button{font:600 .8rem var(--body);text-transform:none;letter-spacing:normal;padding:4px 12px;border-radius:999px;border:1px solid var(--accent);background:none;color:var(--accent);cursor:pointer}
#pcard .pcact .wq.on{border-color:var(--ok);color:var(--ok);cursor:default;opacity:1}#pcard .pcact .wq:disabled:not(.on){opacity:.5;cursor:default}#pcard .pcfav{border-color:#eab308!important;color:#b45309!important}#pcard .pcfav.on{background:#eab308!important;color:#fff!important}
.pcn{cursor:pointer;text-decoration:underline dotted color-mix(in srgb,currentColor 35%,transparent);text-underline-offset:3px}.pcn:hover{color:var(--accent)}</style>
<div id="pcard" class="xwrap" hidden role="dialog" aria-label="Player card"></div><script>(function(){var D=__PCD__,C=__PCC__,box=document.getElementById("pcard");
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function sg(v){return v==null?"—":(v>0?"+":"")+v.toLocaleString()}
function hb(v){v=parseFloat(String(v).replace(/,/g,""));if(isNaN(v))return "";return v<30?"":" fh"+(v<40?2:v<50?3:v<60?4:5)}   // FP/G bands: under 30 plain, 30s, 40s, 50s, 60+
var SKIP="label,button,a,summary,select,option,#pcard,.pcn";
// a player name is clickable wherever it's in the page text: a <b> that is just his name, or the name inside any other text
// (lists, table cells, notes, archive tables). Not in headings, buttons, links, dropdowns, checkbox labels or .dropname (JS rewrites it).
var RX=new RegExp("(?<![\\w'’.-])("+Object.keys(D).sort(function(a,b){return b.length-a.length}).map(function(s){return s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}).join("|")+")(?![\\w-])(?!['’](?!s\\b))","g");   // a possessive ('s) still counts
var NOSCAN="script,style,template,textarea,input,h1,h2,h3,.dropname,"+SKIP;
function scan(r){var w=document.createTreeWalker(r,NodeFilter.SHOW_TEXT,{acceptNode:function(t){var p=t.parentElement;return t.nodeValue.length>3&&p&&!p.closest(NOSCAN)?1:2}}),L=[],t;while((t=w.nextNode()))L.push(t);
L.forEach(function(t){var s=t.nodeValue;RX.lastIndex=0;if(!RX.test(s))return;RX.lastIndex=0;var f=document.createDocumentFragment(),i=0,m;
while((m=RX.exec(s))){if(m.index>i)f.appendChild(document.createTextNode(s.slice(i,m.index)));var sp=document.createElement("span");sp.className="pcn";sp.textContent=m[1];f.appendChild(sp);i=m.index+m[1].length}
if(i<s.length)f.appendChild(document.createTextNode(s.slice(i)));t.parentNode.replaceChild(f,t)})}
function mark(r){if(!r||r.nodeType!==1||r.closest(NOSCAN))return;var l=r.tagName==="B"?[r]:r.querySelectorAll("b");[].forEach.call(l,function(b){if(!b.closest(NOSCAN)&&D.hasOwnProperty(b.textContent.trim()))b.classList.add("pcn")});scan(r);tags(r)}
function ijl(x){var k=x.ij[0];return k==="out"?[x.ir?"🚑 OUT · on IR":"🚑 OUT · IR eligible","injt"]:(k==="gtd"?[x.ir?"⚠️ GTD · not IR eligible":"🚑 GTD","injt gtd"+(x.ir?" irno":"")]:["⚠️ Not injured · not IR eligible","injt gtd irno"])}
function ijb(x){var l=ijl(x);return '<span class="'+l[1]+'" title="'+esc("CBS: "+x.ij[1])+'">'+l[0]+'</span>'}
function tags(r){var l=[].slice.call(r.querySelectorAll(".pcn"));if(r.classList.contains("pcn"))l.push(r);l.forEach(function(e){var x=D[e.textContent.trim()];if(!x||!x.ij||e.dataset.ij||e.parentElement.closest(".tag,.small,.gt,.brief,.irban,h1,h2,h3,button,a,select,option,.dropname,#pcard"))return;e.dataset.ij="1";e.insertAdjacentHTML("afterend"," "+ijb(x))})}
document.addEventListener("DOMContentLoaded",function(){mark(document.body);new MutationObserver(function(ms){var s=new Set();ms.forEach(function(m){[].forEach.call(m.addedNodes,function(x){s.add(x.nodeType===1?x:x.parentNode)})});s.forEach(mark)}).observe(document.body,{childList:true,subtree:true})});
function open(n){var x=D[n];if(!x)return;var ini=n.split(" ").slice(0,2).map(function(w){return w.charAt(0)}).join("").toUpperCase();
var h='<button class="x" type="button" aria-label="Close">✕</button><div class="pch"><span class="pcf" aria-hidden="true">'+esc(ini)+(x.h?'<img src="https://a.espncdn.com/i/headshots/nba/players/full/'+x.h+'.png" alt="" onerror="this.remove()">':'')+'</span><div><h2>'+esc(n)+'</h2><p><span class="nbat" data-t="'+esc(x.t)+'">'+esc(x.t)+'</span> <span class="tm">'+esc(x.p)+'</span>'+(x.ij?' '+ijb(x):(x.ir?' · <span class="tag bad">IR</span>':''))+(x.out?' · out until '+esc(x.out):'')+(x.rest?' · 🛌 rests B2Bs':'')+'</p>'+(x.ij?'<p class="small pcinj">'+esc(x.ij[1])+' <span class="muted">(CBS, last nightly read)</span></p>':'')+'<p class="pcown">'+(x.o==='FA'?'<span class="pcfa">Free agent</span>':(x.ol!=null?'<img data-lg="'+x.ol+'" width="24" height="24" alt="" class="mlogo">':'')+'<span>Rostered by <b>'+esc(x.on)+'</b></span>'+(x.o==='yours'?'<span class="yours">★ Yours</span>':''))+'</p><p class="pcact"><button type="button" class="wq" data-n="'+esc(x.N)+'">+ Watch</button>'+fbt(x.N)+'</p>'+(x.bio?'<p class="small pcbio">'+[x.bio[0]?'#'+esc(x.bio[0]):'',x.bio[1]?esc(x.bio[1]):'',x.bio[2]?esc(x.bio[2])+' lbs':'',x.bio[3]!==''?esc(x.bio[3])+' years old':''].filter(Boolean).join(' · ')+(x.bio[4]||x.bio[5]?'<br>'+[x.bio[4]?esc(x.bio[4]):'',x.bio[5]?'Drafted '+esc(x.bio[5]):'Undrafted'].filter(Boolean).join(' · '):'')+'</p>':'')+'</div></div>';
h+='<div class="kv"><span>CBS FP/G</span><b>'+(x.fp?x.fp.toFixed(1):'—')+(x.yf!=null?' <span class="small" style="font-weight:400">· your FP/G '+x.yf.toFixed(1)+' (used for projections)</span>':'')+'</b><span>CBS projected games</span><b>'+Math.round(x.gp)+' <span class="small" style="font-weight:400">('+Math.min(100,Math.round(x.gp/78.5*100))+'% of a full season: his gains are scaled by it)</span></b>'+(x.ro?'<span>CBS rostered</span><b>'+esc(x.ro)+'</b>':'')+''+(x.u?'<span>Usage rate</span><b>'+x.u[0]+'% season · '+x.u[1]+'% last 3</b>':'')+'</div>'+(x.bs?'<p class="pcbs '+x.bs[0]+'"><b>'+(x.bs[0]==='sell'||x.bs[0]==='fade'?'📈 ':'📉 ')+esc(x.bs[1])+'</b> · '+esc(x.bs[2].join(' · '))+'</p>':'');
if(x.st&&x.st.length)h+='<h3>Stats</h3><div class="scroll"><table class="pcst" data-xs><thead><tr>'+['Season','G','MPG','FG','FG%','FT','FT%','3PT','3P%','RPG','APG','SPG','TPG','BPG','PPG','FPTS/G','FPTS'].map(function(c){return '<th>'+c+'</th>'}).join('')+'</tr></thead><tbody>'+x.st.map(function(r){var cur=r[0]==='2026-27';return '<tr'+(cur?' class="cur"':'')+'>'+r.map(function(v,j){return '<td'+(j===15?' class="fp'+(cur?hb(v):'')+'"':j===16?' class="fp"':'')+'>'+esc(v)+'</td>'}).join('')+'</tr>'}).join('')+'</tbody></table></div><p class="small" style="margin:4px 0 0">FG, FT and 3PT are makes. FPTS = BBL points with the slot bonus, as on CBS&#39;s game log. On pace = his rate over 82 games at his team&#39;s games so far. Past seasons: ESPN regular-season totals (a traded season is both teams combined); avg = per season over the last 3.</p><p class="small fhleg" style="margin:6px 0 0">This season&#39;s FPTS/G colour: 0–29 plain · <span class="fh2">30–39</span> <span class="fh3">40–49</span> <span class="fh4">50–59</span> <span class="fh5">60+</span></p>';
if((x.gl&&x.gl.length)||(x.h&&x.ps&&x.ps.length)){CX_=x;h+='<h3>Game log'+(x.h&&x.ps&&x.ps.length?' <select class="pcgls" aria-label="Season"><option value="">2026-27</option>'+x.ps.map(function(p){return '<option value="'+p[1]+'">'+esc(p[0])+'</option>'}).join('')+'</select>':'')+'</h3><div class="pcglbox">'+glwrap(x.gl||[])+'</div>'}
h+='<h3>Games left '+xb()+'</h3><div class="scroll"><table data-xs><thead><tr>'+C.map(function(c){return '<th'+(c[1]?' class="wx"':'')+'>'+esc(c[0])+'</th>'}).join("")+'</tr></thead><tbody><tr>'+x.g.map(function(v,i){return '<td class="num'+(C[i][1]?' wx':'')+'">'+v+'</td>'}).join("")+'</tr></tbody></table></div><p class="small" style="margin:-6px 0 0">Back-to-backs left: '+x.b2b[0]+' regular season · '+x.b2b[1]+' playoffs. Games count out-until dates'+(x.rest?' and his B2B rests':'')+'.</p>';
if(x.v)h+='<h3>'+esc(x.vk)+'</h3><div class="scroll"><table data-xs><thead><tr>'+C.map(function(c){return '<th'+(c[1]?' class="wx"':'')+'>'+esc(c[0])+'</th>'}).join("")+'</tr></thead><tbody><tr>'+x.v.map(function(v,i){return '<td class="num'+(C[i][1]?' wx':'')+'"><b>'+sg(v)+'</b></td>'}).join("")+'</tr></tbody></table></div>';
if(x.tt)h+='<h3>If you traded for him (your stream slot)</h3><p style="margin:0">'+sg(x.tt[0])+' regular season · '+sg(x.tt[1])+' playoffs. Try packages in Trades → Trade analyzer.</p>';
h+='<h3>News · last 48 hours</h3>'+(x.nw.length?'<ul style="margin:0;padding-left:18px">'+x.nw.map(function(z){return '<li>'+esc(z[2])+' <span class="small">· '+esc(z[1])+', '+esc(z[0])+'</span></li>'}).join("")+'</ul>':'<p class="muted" style="margin:0">None.</p>');
box.innerHTML=h;box.hidden=false;fitgl();box.scrollTop=0;document.dispatchEvent(new Event("bbl-sync"));box.querySelector(".x").focus()}
function close(){box.hidden=true}
// Game log: this season from the box scores (with DNP rows); a past season is read from ESPN's game log when picked
var CX_=null,GLC={},GH=['Date','Opp','MIN','FG','FGA','3PT','3PTA','FT','FTA','REB','AST','ST','BK','TO','PF','PTS','FPTS'];
function glwrap(rows,note){return (note?'<p class="small" style="margin:2px 0 4px">'+note+'</p>':'')+'<div class="scroll pcglsc"><table class="pcst pcgl" data-xs><thead><tr>'+GH.map(function(c){return '<th>'+c+'</th>'}).join('')+'</tr></thead><tbody>'
+rows.map(function(r,i){if(r.length===2)return '<tr class="pcdnp"><td>'+esc(r[0])+'</td><td>'+esc(r[1])+'</td><td colspan="14">Did not play</td><td class="fp">—</td></tr>';return '<tr>'+r.map(function(v,j){return '<td'+(j===16?' class="fp"':'')+'>'+esc(v)+'</td>'}).join('')+'</tr>'}).join('')
+'</tbody></table></div>'+(rows.length>10?'<p class="small muted" style="margin:2px 0 0">'+rows.length+' team games · scroll the table for more</p>':'')}
// the log shows 10 games, the rest scroll inside it (header stays put)
function fitgl(){[].forEach.call(box.querySelectorAll(".pcglsc"),function(w){var r=w.querySelectorAll("tbody tr");w.style.maxHeight="";if(r.length>10){w.style.maxHeight="300px";var c=w.getBoundingClientRect(),d=r[9].getBoundingClientRect().bottom-(c.top+w.clientTop+w.clientHeight);w.style.maxHeight=(300+Math.ceil(d))+"px"}})}
function espngl(id,se,bk){var key=id+'/'+se;if(GLC[key])return Promise.resolve(GLC[key]);
return fetch('https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/'+id+'/gamelog?region=us&lang=en&season='+se).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){
var ix={};(j.names||[]).forEach(function(n,i){ix[n]=i});var rows=[],tm={};
(j.seasonTypes||[]).forEach(function(st){if(!/Regular Season$/.test(st.displayName||'')||/Play.?In/i.test(st.displayName))return;(st.categories||[]).forEach(function(c){(c.events||[]).forEach(function(e){var m=(j.events||{})[e.eventId],v=e.stats||[];if(!m)return;
function g(n){return v[ix[n]]||'0'}function two(n){var a=g(n).split('-');return [+a[0]||0,+a[1]||0]}
var fg=two('fieldGoalsMade-fieldGoalsAttempted'),tp=two('threePointFieldGoalsMade-threePointFieldGoalsAttempted'),ft=two('freeThrowsMade-freeThrowsAttempted'),
reb=+g('totalRebounds'),ast=+g('assists'),stl=+g('steals'),blk=+g('blocks'),to=+g('turnovers'),pf=+g('fouls'),pts=+g('points'),bon={G:reb,F:ast,C:tp[0]},sb=0;
(bk||[]).forEach(function(x){sb=Math.max(sb,bon[x]||0)});
var fp=pts+2*fg[0]-fg[1]+ft[0]-ft[1]+reb+2*ast+4*stl+4*blk-2*to-pf+sb,d=new Date(Date.parse(m.gameDate)-6*3600e3);
tm[e.eventId]=[d.toISOString(),(m.team||{}).id];rows.push([d.toISOString(),(d.getUTCMonth()+1)+'/'+('0'+d.getUTCDate()).slice(-2),(m.atVs==='@'?'@':'')+((m.opponent||{}).abbreviation||''),g('minutes'),fg[0],fg[1],tp[0],tp[1],ft[0],ft[1],reb,ast,stl,blk,to,pf,pts,fp].map(String))})})});
// his team on a date = the team of his nearest game on or before it (after a trade), else his first team
var nos=0,pg=Object.keys(tm).map(function(k){return tm[k]}).sort(function(a,b){return a[0]<b[0]?-1:1}),ids=[];pg.forEach(function(x){if(x[1]&&ids.indexOf(x[1])<0)ids.push(x[1])});
function teamOn(iso){var t=pg.length?pg[0][1]:null;pg.forEach(function(x){if(x[0]<=iso)t=x[1]});return t}
return Promise.all(ids.map(function(tid){return fetch('https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/teams/'+tid+'/schedule?season='+se+'&seasontype=2').then(function(r){if(!r.ok)throw 0;return r.json()}).catch(function(){nos=1;return {}}).then(function(sj){
(sj.events||[]).forEach(function(ev){var c=(ev.competitions||[])[0]||{};if(tm[ev.id]||((c.status||{}).type||{}).name!=='STATUS_FINAL')return;var d=new Date(Date.parse(ev.date)-6*3600e3),iso=d.toISOString();if(teamOn(iso)!==tid)return;
var me=null,op=null;(c.competitors||[]).forEach(function(x){if(String((x.team||{}).id)===String(tid))me=x;else op=x});if(!me||!op)return;
rows.push([iso,(d.getUTCMonth()+1)+'/'+('0'+d.getUTCDate()).slice(-2),(me.homeAway==='away'?'@':'')+((op.team||{}).abbreviation||'')])})})})).then(function(){
rows.sort(function(a,b){return a[0]<b[0]?1:-1});rows=rows.map(function(r){return r.slice(1)});if(ids.length>1)rows.tr=1;if(nos)rows.nos=1;else GLC[key]=rows;return rows})})}
box.addEventListener("change",function(e){var sel=e.target.closest(".pcgls");if(!sel||!CX_)return;var x=CX_,v=sel.value,bx=box.querySelector(".pcglbox"),lab=sel.options[sel.selectedIndex].text;if(!bx)return;
if(!v){bx.innerHTML=glwrap(x.gl||[]);fitgl();return}bx.innerHTML='<p class="muted">Loading '+esc(lab)+' from ESPN…</p>';
espngl(x.h,v,x.bk).then(function(r){if(sel.value!==v||CX_!==x)return;var n=0,f=0;r.forEach(function(q){if(q.length>2){n++;f+=+q[16]}});
bx.innerHTML=r.length?glwrap(r,'<b>'+esc(lab)+'</b> regular season from ESPN: '+(r.nos?n+' games played':'played '+n+' of '+(r.tr?'about ':'')+r.length+' team games')+', '+(n?(f/n).toFixed(1):'0')+' FP/G. FPTS use his slot bonus today ('+esc((x.bk||[]).map(function(b){return {G:'REB',F:'AST',C:'3PM'}[b]}).join(' or ')||'none')+').'+(r.nos?' Couldn&#39;t load his team&#39;s schedule, so games he missed aren&#39;t shown. Pick the season again to retry.':(n<r.length?' Games he missed show as Did not play.':'')+(r.tr?' He was traded that season and ESPN doesn&#39;t give the date, so missed games between his last game for one team and his first for the next are listed under the old team, and the total can be a few off.':''))):'<p class="muted">ESPN has no regular-season games for him in '+esc(lab)+'.</p>';fitgl()})
.catch(function(){if(sel.value===v)bx.innerHTML='<p class="muted">Couldn&#39;t reach ESPN for '+esc(lab)+'. Check your connection and pick it again.</p>'})});
function xb(){var o=box.classList.contains("xall");return '<button type="button" class="xper" data-x="pcard" data-l0="Show all periods ▸" data-l1="◂ Next 3 periods" aria-pressed="'+o+'">'+(o?'◂ Next 3 periods':'Show all periods ▸')+'</button>'}
// ☆ Favourite: same list as the Watchlist's stars (pinned to the top there); starring a player who isn't watched also adds him
function favs(){try{return JSON.parse(localStorage.getItem("bbl-wfav")||"{}")||{}}catch(e){return {}}}
function fbt(n){var o=!!favs()[n];return '<button type="button" class="pcfav'+(o?' on':'')+'" data-n="'+esc(n)+'" aria-pressed="'+o+'" title="'+(o?'Pinned to the top of your Watchlist. Click to unpin':'Pin him to the top of your Watchlist (adds him to it if needed)')+'">'+(o?'★ Favourite':'☆ Favourite')+'</button>'}
box.addEventListener("click",function(e){var b=e.target.closest(".pcfav");if(!b)return;var n=b.dataset.n,F=favs();if(F[n])delete F[n];else F[n]=1;try{localStorage.setItem("bbl-wfav",JSON.stringify(F))}catch(er){}
b.outerHTML=fbt(n);document.dispatchEvent(new CustomEvent("bbl-wfav",{detail:"pc"}));var w=box.querySelector(".wq");if(F[n]&&w&&!w.disabled&&!w.classList.contains("on"))w.click()});
document.addEventListener("click",function(e){var b=e.target.closest(".pcn");if(b&&D[b.textContent.trim()]){e.preventDefault();open(b.textContent.trim());return}if(!box.hidden&&(e.target.closest(".x")||!e.target.closest("#pcard")))close()});
document.addEventListener("keydown",function(e){if(e.key==="Escape"&&!box.hidden)close()});box.addEventListener("click",function(e){var b=e.target.closest(".pcglall");if(!b)return;[].forEach.call(box.querySelectorAll(".pcgl tr[hidden]"),function(r){r.hidden=false});b.remove()});window.__pcard=open;window.__pcnames=D})();</script>'''
          .replace('__PCD__',json.dumps(D,separators=(',',':'),ensure_ascii=False).replace('</','<\\/')).replace('__PCC__',json.dumps([[c,x] for (c,_),x in zip(cols,CX)])))
_build_pcard()
body=f'''{headtxt}
<div class="wrap">
<header>
<div class="eyebrow">BBL · {html.escape(MEDISP)} · 2026–27 · Updated {TODAY.strftime("%a %b %-d")}</div>
<h1>BBL Command Center <span style="color:var(--muted);font-weight:600">· {html.escape(MEDISP)}</span></h1>
<p class="lede">Projections use the league's scoring and your best legal lineup each day, refreshed nightly after the waiver run. <b>Today</b> = what to do now · <b>Waivers</b> = who to add · <b>Trades</b> = who to trade for · <b>This period</b> = this week's matchup · <b>Season</b> = the long view · <b>Playoffs</b> = P22–P24 schedule and playoff rules.</p>
{streamsel}{streamjs}
</header>
<nav class="tabs" role="tablist" aria-label="Report sections"><button role="tab" data-t="today" aria-selected="true">Today</button><button role="tab" data-t="waivers" aria-selected="false">Waivers</button><button role="tab" data-t="trades" aria-selected="false">Trades</button><button role="tab" data-t="period" aria-selected="false">This period</button><button role="tab" data-t="season" aria-selected="false">Season</button><button role="tab" data-t="playoffs" aria-selected="false">Playoffs</button></nav>
<div class="pane" id="today" role="tabpanel">{today}</div>
<div class="pane" id="waivers" role="tabpanel" hidden>
<nav class="subtabs" data-g="waivers" aria-label="Waiver views"><button type="button" data-s="wpick" aria-pressed="true">Best adds</button><button type="button" data-s="wstr" aria-pressed="false">Streaming</button><button type="button" data-s="wriv" aria-pressed="false">Rivals</button><button type="button" data-s="wwatch" aria-pressed="false">Watchlist</button></nav>
<div id="wpick" class="subpane">{mymoves_w}{usgsec}<details class="rep" id="breakouts"><summary>🚀 Breakout alerts{(" · "+html.escape(BOLAB)) if BOLAB else ""}</summary>{bosec}</details>{boardsec}{teamadds}</div>
<div id="wwatch" class="subpane" hidden>{wlpane}</div>
<div id="wstr" class="subpane" hidden>{strpane}</div>
<div id="wriv" class="subpane" hidden>{denysec}{rivsec}</div>
</div>
<div class="pane" id="trades" role="tabpanel" hidden>{tradepane}</div>
<div class="pane" id="period" role="tabpanel" hidden>
<nav class="subtabs" data-g="period" aria-label="This period views"><button type="button" data-s="pov" aria-pressed="true">Overview</button><button type="button" data-s="pmu" aria-pressed="false">Start/Sit</button><button type="button" data-s="prost" aria-pressed="false">Roster</button></nav>
<div id="pov" class="subpane">{thisp}</div>
<div id="pmu" class="subpane" hidden>{startsit_pane}</div>
<div id="prost" class="subpane" hidden>{roster_pane}</div>
</div>
<div class="pane" id="playoffs" role="tabpanel" hidden>{posec}</div>
<div class="pane" id="season" role="tabpanel" hidden>
<nav class="subtabs" data-g="season" aria-label="Season views"><button type="button" data-s="sov" aria-pressed="true">Overview</button><button type="button" data-s="sthin" aria-pressed="false">Thin days</button><button type="button" data-s="smu" aria-pressed="false">H2H schedule</button><button type="button" data-s="srep" aria-pressed="false">Reports</button><button type="button" data-s="stop" aria-pressed="false">Top 150</button><button type="button" data-s="sprz" aria-pressed="false">Side prizes</button><button type="button" data-s="sben" aria-pressed="false">Bench</button><button type="button" data-s="sdraft" aria-pressed="false">Draft results</button></nav>
<div id="sprz" class="subpane" hidden>{prizesec}
{PLAN}</div>
<div id="sben" class="subpane" hidden>{benchsec}</div>
<div id="sdraft" class="subpane" hidden>{draftsec or '<section><h2>Draft results</h2><p class="muted">No draft data saved yet.</p></section>'}</div>
<div id="sthin" class="subpane" hidden>{thin_pane}</div>
<div id="smu" class="subpane" hidden>{h2h_pane}</div>
<div id="stop" class="subpane" hidden>{top150_pane}</div>
<div id="srep" class="subpane" hidden>{nightsec}<section><h2>Period reports</h2><p class="small">Top 10 performers and the worst performances for each finished period, with trends and outlook. A new one is added every Sunday night.</p>{repane}</section></div>
<div id="sov" class="subpane">
<section class="keys">
{keys}
</section>
<section>
<h2>Period by period <a class="curjump" href="#curp">→ P{CUR} now</a></h2>
{dropsel_ov}{WLALL}
<div class="scroll"><table class="ledger">
<thead><tr><th>P</th><th>Dates · opponent</th><th>Scoring preview</th><th>Slots used</th><th>Thin days · players playing</th><th>Best adds if you drop <span class="dropname">{html.escape(short(STREAM))}</span> · your watchlist <button type="button" class="wlall wlallth" data-o="0">★ Expand all</button></th><th>Best teams to stream · thin days covered / games</th></tr></thead>
<tbody id="pastrows" hidden>{PASTROWS}</tbody>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>
{IRNOTE}
<div class="legend"><span><span class="chip c2">1–2</span> 3+ empty slots</span><span><span class="chip c3">3</span> 2 empty</span><span><span class="chip c4">4</span> 1 empty</span><span>POR <b>2</b>/3 = plays 2 of the thin days, 3 games total that period</span><span><b class="oslot better">Opp slots 28/35 · you +5</b> = opponent's slots used on their current roster; green when you fill more, red when they do</span><span>Win % compares projected lineup totals (yours vs your opponent's current roster) with typical week-to-week swing; it updates nightly as rosters change</span><span>Shaded rows are playoffs (P22–24)</span><span>Trade deadline: Thu Feb 25, 11:59 PM ET (P19)</span></div>
{insights}
</section>
<section class="two">
<div>
<h2>Your roster by value</h2>
<div class="scroll"><table>
<thead><tr><th>Player</th><th>Rest of reg. season</th><th>Playoffs</th></tr></thead>
<tbody>
{pv}
</tbody></table></div>
<p class="small">These are the points you lose if the player is removed and the rest of the roster fills in. Players on teams that share game days bench each other, which lowers their value. <b>Rd · #</b> = your BBL draft pick; 💰 <b>sell-high chip</b> = a round-7-or-later pick now projecting 3+ rounds better, so other managers may pay more than you did.</p>
</div>
<div class="small">
<h2>How to read this</h2>
<p>Schedule from Hashtag Basketball's full-season grid, mapped to the league's period dates. Championship week (P24) runs Mon Mar 29 to Fri Apr 2, with Apr 3 cut and the NBA's final week not used. Projections are CBS season FPTS/G per slot, with manual adjustments: {html.escape('; '.join(f'{short(k)} set to {v:g}' for k,v in proj.items()) or 'none')}. {html.escape(' '.join(f'{short(k)} counted from {v.strftime("%b %-d")}.' for k,v in out.items() if v>TODAY))} Streaming teams show which NBA teams play on your thin days. Players CBS projects for under 60 games are left out of "Best adds" and flagged on the waiver wire. In P7–P8 the NBA has not yet set the Cup knockout games; the league will adjust those weeks, and the Cup championship game does not count.</p>
</div>
</section>
</div>
</div>
</div>
{OVJS}
{SCRIPT}
{TABSORT}'''

# ---- NBA team colour tags everywhere a player's team is shown (CSS in NBATCSS)
TEAMRE='|'.join(sorted(TEAMCOL,key=len,reverse=True))
def teamtags(h):
    h=re.sub(r'<span class="tm">([CFG](?:,[CFG])*) · ('+TEAMRE+r')</span>',r'<span class="nbat" data-t="\2">\2</span> <span class="tm">\1</span>',h)
    # Best & Worst nightly tables (templates nt-*) keep plain team text; period reports (rt-*) get tags
    h=re.sub(r'(<template id="rt-[^"]*"(?: data-z)?>)(.*?)(</template>)',lambda m:m.group(1)+re.sub(r'<span style="font-size:1[01]px;color:#667085">('+TEAMRE+r')</span>',r'<span class="nbat sm" data-t="\1">\1</span>',m.group(2))+m.group(3),h,flags=re.S)
    h=re.sub(r'\(([CFG](?:,[CFG])*) · ('+TEAMRE+r')\)',r'<span class="nbat" data-t="\2">\2</span> <span class="tm">\1</span>',h)
    return h
body=teamtags(body)
# ---- 🛌 B2B toggles in every player table (rests on back-to-backs): after a player's name and team tag, when that pair
# is one player. Not in the settings panel (it has its own column), the Watchlist (its rows add their own) or history
# (Best & Worst nights, period reports). Clicks and syncing for all of them: RBJS
_RBK=defaultdict(list)
for n_,i_ in INFO.items(): _RBK[(short(n_),i_['team'])].append(n_)
def _rbtn(n):
    b=_B2B.setdefault(INFO[n]['team'],b2bn(INFO[n]['team'])); on=n in REST
    return (f' <button type="button" class="rb2b{" on" if on else ""}" data-n="{html.escape(n)}" data-s="{int(on)}" disabled '
            f'title="{"Rests on back-to-backs" if on else "Mark as resting on back-to-backs"}: sits the 2nd night of each, {b[0]} left in the regular season + {b[1]} in the playoffs. Then Apply &amp; rebuild at the top.">🛌 B2B</button>')
_RBRE=re.compile(r'(<b>([^<]{2,40})</b> <span class="nbat" data-t="([A-Z]{2,4})">[A-Z]{2,4}</span>(?: <span class="tm">[CFG,]+</span>)?)(?! <button type="button" class="rb2b)')
def b2btags(h):
    def one(m):
        n=html.unescape(m.group(2))   # short name (D. Murray), or the full name in Roster and Top 150
        c=[n] if n in INFO and INFO[n]['team']==m.group(3) else _RBK.get((n,m.group(3)),[])
        return m.group(1)+_rbtn(c[0]) if len(c)==1 else m.group(1)
    parts=re.split(r'(<template id="(?:nt|rt)-.*?</template>|<div class="streamsel">.*?<div id="ssbar")',h,flags=re.S)
    return ''.join(x if i%2 else _RBRE.sub(one,x) for i,x in enumerate(parts))
RBJS=r'''<script>(function(){var RS=window.__bblrest;if(!RS)return;   // every 🛌 B2B toggle: on = in RS, dashed = changed, not applied
function sync(){[].forEach.call(document.querySelectorAll(".rb2b"),function(e){var on=RS.has(e.dataset.n);e.classList.toggle("on",on);e.classList.toggle("pend",(e.dataset.s==="1")!==on);e.disabled=!window.__bblsetok})}
document.addEventListener("bbl-rest",sync);new MutationObserver(function(){if(window.__bblsetok)sync()}).observe(document.getElementById("wwatch")||document.body,{childList:true,subtree:true});
document.addEventListener("click",function(e){var b=e.target.closest(".rb2b");if(!b||b.disabled)return;e.stopPropagation();e.preventDefault();var n=b.dataset.n;if(RS.has(n))RS.delete(n);else RS.add(n);document.dispatchEvent(new Event("bbl-rest"))},true);
if(window.__bblsetok)sync()})();</script>'''   # the header may have switched editing on before this script loaded
body=b2btags(body).replace('</body>',RBJS+'</body>') if '</body>' in body else b2btags(body)+RBJS
body+=PCJS
# Show all periods (Best adds, Trade analyzer, player card): .wx cells hide unless the .xwrap around them has .xall
body+=(r'''<style>.xwrap:not(.xall) .wx{display:none}.xper{font:600 .78rem var(--body);letter-spacing:normal;text-transform:none;margin-left:10px;padding:2px 10px;border:1px solid var(--accent);border-radius:999px;background:none;color:var(--accent);cursor:pointer;white-space:nowrap;vertical-align:middle}.xper[aria-pressed="true"]{background:var(--accent);color:#fff}
#xbo.xall .scroll table td:first-child,#xbo.xall .scroll table th:first-child{position:sticky;left:0;z-index:1;background:var(--panel);min-width:230px}#xbo.xall tr.irhead td:first-child{position:static}#tana.xall #taout td:first-child,#tana.xall #taout th:first-child{position:sticky;left:0;z-index:1;background:var(--panel)}</style>
<script>(function(){function set(id,o,save){var t=document.getElementById(id);if(t)t.classList.toggle("xall",o);[].forEach.call(document.querySelectorAll('.xper[data-x="'+id+'"]'),function(b){b.setAttribute("aria-pressed",String(o));b.textContent=o?b.dataset.l1:b.dataset.l0});if(save)try{localStorage.setItem("bbl-x-"+id,o?"1":"")}catch(e){}}
document.addEventListener("click",function(e){var b=e.target.closest(".xper");if(!b)return;e.preventDefault();var t=document.getElementById(b.dataset.x);set(b.dataset.x,!(t&&t.classList.contains("xall")),true)},true);
["xbo","tana","pcard"].forEach(function(id){var v="";try{v=localStorage.getItem("bbl-x-"+id)}catch(e){}set(id,v==="1",false)})})();</script>''')   # player card (after the tag passes: its data has names in <b> that they'd otherwise tag)
# ---- logos: each data URI once (window.__LG); every <img data-lg> gets its src as it's parsed or inserted (tabs, templates, JS tables)
body=re.sub(r'src="(data:image/[^"]+)"',lgsub,body)
# older archive nights/reports (ztpl data-z): deflate+base64, ~12x smaller; window.__tpl(id) unpacks one when it's picked
body=re.sub(r'<template id="([^"]+)" data-z>(.*?)</template>',lambda m:f'<script type="application/x-bbl-z" id="{m.group(1)}">'
            +base64.b64encode(zlib.compress(m.group(2).encode('utf-8'),9)).decode()+'</script>',body,flags=re.S)
LGJS=('<script>window.__LG='+json.dumps(LG)+';(function(){var L=window.__LG;function f(i){if(!i.hasAttribute("src"))i.src=L[+i.dataset.lg]}'
      'function g(r){if(r.nodeType!==1)return;if(r.matches("img[data-lg]"))f(r);[].forEach.call(r.querySelectorAll("img[data-lg]"),f)}'
      'new MutationObserver(function(ms){ms.forEach(function(m){[].forEach.call(m.addedNodes,g)})}).observe(document.documentElement,{childList:true,subtree:true});'
      'document.addEventListener("DOMContentLoaded",function(){g(document.body)})})();'
      # archive nights/reports (ztpl): a <template> as is, or unpack the compressed one into a <template> the first time it's picked
      'window.__tpl=function(id){var e=document.getElementById(id);if(!e)return Promise.resolve(null);if(e.tagName==="TEMPLATE")return Promise.resolve(e);'
      'if(!window.DecompressionStream){var t0=document.createElement("template");t0.innerHTML="<p class=\\"muted\\">This browser can&#39;t open older nights. Use a current Chrome, Edge or Safari.</p>";return Promise.resolve(t0)}'
      'var s=atob(e.textContent.trim()),u=new Uint8Array(s.length);for(var i=0;i<s.length;i++)u[i]=s.charCodeAt(i);'
      'return new Response(new Blob([u]).stream().pipeThrough(new DecompressionStream("deflate"))).text().then(function(h){'
      'var e2=document.getElementById(id);if(!e2||e2.tagName==="TEMPLATE")return e2;var t=document.createElement("template");t.id=id;t.innerHTML=h;e2.replaceWith(t);return t})};</script>')
body=LGJS+body
open('season_plan.html','w').write(body)
print('built',TODAY,'stream=',STREAM,'periods',PER[0],'-',PER[-1])
