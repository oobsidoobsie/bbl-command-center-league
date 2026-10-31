#!/usr/bin/env python3
"""Weekly (period) best/worst performers in BBL scoring.
Usage: python3 weekly.py "<label>" pool.txt box_YYYYMMDD.txt [box_...txt ...] [email]
   or: python3 weekly.py "<label>" pool.txt --agg agg.txt [email]
Daily box format (from fetch_box.js): name|team|min|pts|fgm|fga|tpm|tpa|ftm|fta|reb|ast|to|stl|blk|pf|espnpos
Writes weekly.html (page, with logos) or weekly_email.html (email, no images). If summary.html exists
(written by the nightly agent: outlook for the top players), it is included under the tables."""
import sys, html, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
args=sys.argv[1:]; EMAIL='email' in args; args=[a for a in args if a!='email']
label, poolf = args[0], args[1]; rest=args[2:]
owner={}; LOGO={}; CBSPOS={}
for l in open(poolf):
    p=l.rstrip('\n').split('|')
    if p[0]=='#LOGO' and len(p)>=3: LOGO[p[1]]=p[2]; continue
    if len(p)>=4:
        CBSPOS[p[0]]=p[2]; owner[p[0]]='Yours' if p[3]=='MINE' else (p[3][6:] if p[3].startswith('TAKEN:') else 'FA')
K=['min','pts','fgm','fga','tpm','tpa','ftm','fta','reb','ast','to','stl','blk','pf']
mp={'PG':'G','SG':'G','G':'G','SF':'F','PF':'F','F':'F','C':'C','G-F':'GF','F-G':'GF','F-C':'FC','C-F':'FC'}
def base(s): return s['pts']+2*s['fgm']-s['fga']+s['ftm']-s['fta']+s['reb']+2*s['ast']+4*s['stl']+4*s['blk']-2*s['to']-s['pf']
def elig(n,ep): return set(CBSPOS[n].split(',')) if n in CBSPOS else set(mp.get((ep or '').upper(),''))
def bonus(n,ep,s):
    o=[({'G':s['reb'],'F':s['ast'],'C':s['tpm']}[x],x) for x in 'GFC' if x in elig(n,ep)]
    return max(o) if o else (0,'')
P={}; days=set()
if rest and rest[0]=='--agg':
    for l in open(rest[1]):
        f=l.rstrip('\n').split('|')
        if len(f)<20: continue
        s=dict(zip(K,map(int,f[2:16]))); n=f[0]
        log=[(d.split(':')[0],int(d.split(':')[1])) for d in f[19].split(',') if d]
        b,sl=bonus(n,f[17],s)
        P[n]=dict(n=n,t=f[1],s=s,gp=int(f[18]),log=[v for _,v in log],bon=b,slot=sl,ep=f[17])
else:
    for fn in rest:
        lines=open(fn).read().strip().splitlines()
        for l in lines[1:]:
            f=l.split('|')
            try: s=dict(zip(K,[int(float(x or 0)) for x in f[2:16]]))
            except ValueError: continue
            n=f[0]; ep=f[16] if len(f)>16 else ''
            b,sl=bonus(n,ep,s)
            q=P.setdefault(n,dict(n=n,t=f[1],s={k:0 for k in K},gp=0,log=[],bon=0,slot=sl,ep=ep))
            for k in K: q['s'][k]+=s[k]
            q['gp']+=1; q['log'].append(base(s)+b); q['bon']+=b
            if sl: q['slot']=sl
for q in P.values():
    q['base']=base(q['s']); q['fp']=q['base']+q['bon']; q['avg']=q['fp']/max(1,q['gp']); q['mpg']=q['s']['min']/max(1,q['gp'])
def logo(team,sz=18):
    if EMAIL: return ''
    u=LOGO.get(team)
    return f'<img src="{u if u.startswith('data:') else u+'?width=48&height=48'}" width="{sz}" height="{sz}" alt="" style="border-radius:4px;vertical-align:middle;margin-right:3px">' if u else ''
def own(n):
    o=owner.get(n,'FA')
    if o=='Yours': return f' {logo(os.environ.get("BBL_ME","Oobsidoobsie"))}<span style="font-size:11px;color:#c2410c;font-weight:600">★ yours</span>'
    if o=='FA': return ' <span style="font-size:11px;color:#667085">FA</span>'
    return f' {logo(o)}<span style="font-size:11px;color:#667085">{html.escape(o)}</span>'
def trend(log):
    if len(log)<2: return '—'
    h=len(log)//2; a=sum(log[:h])/h; b=sum(log[h:])/(len(log)-h)
    arrow='<span style="color:#1f9d55">▲</span>' if b>a*1.15 else ('<span style="color:#d64545">▼</span>' if b<a*0.85 else '<span style="color:#9fb3bd">▬</span>')
    return arrow+' <span style="font-size:11px;color:#667085">'+' · '.join(str(v) for v in log)+'</span>'
TH='style="text-align:left;padding:4px 6px;border-bottom:2px solid #dfe3ea;font-size:12px"'
TD='style="padding:4px 6px;border-bottom:1px solid #eef0f4;font-size:13px;white-space:nowrap"'
def table(rows,col):
    cols=['#','Player','Best slot','Base','GP','Avg','MIN/G','PTS','REB','AST','STL','BLK','TO','Game by game']
    h='<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif"><tr>'+''.join(f'<th {TH}>{c}</th>' for c in cols)+'</tr>'
    for i,q in enumerate(rows,1):
        s=q['s']; g=max(1,q['gp']); c='#d64545' if q['fp']<0 else col
        tag=f' <span style="font-size:10px;color:#9fb3bd">{q["slot"]} +{q["bon"]}</span>' if q['bon'] else ''
        pg=lambda k:f'{s[k]/g:.1f}'
        vals=[i,f'<b>{html.escape(q["n"])}</b> <span style="font-size:11px;color:#667085">{q["t"]}</span>'+own(q['n']),
              f'<b style="color:inherit;font-size:15px;font-weight:800;font-variant-numeric:tabular-nums">{("\u2212"+str(abs(q["fp"]))) if q["fp"]<0 else q["fp"]}</b>{tag}',q['base'],q['gp'],f'{q["avg"]:.1f}',f'{q["mpg"]:.0f}',pg('pts'),pg('reb'),pg('ast'),pg('stl'),pg('blk'),pg('to'),trend(q['log'])]
        h+='<tr>'+''.join(f'<td {TD}>{v}</td>' for v in vals)+'</tr>'
    return h+'</table>'
L=list(P.values())
best=sorted(L,key=lambda q:(-q['fp'],-q['avg']))
worst=sorted([q for q in L if q['gp']>=2 and q['mpg']>=20],key=lambda q:(q['avg'],-q['mpg']))
hm=lambda Q:', '.join(html.escape(q['n'])+f' ({q["fp"]}{", "+("yours" if owner[q["n"]]=="Yours" else html.escape(owner[q["n"]])) if owner.get(q["n"],"FA")!="FA" else ""})' for q in Q)
summ=open('summary.html').read() if os.path.exists('summary.html') else ''
out=('<div style="overflow-x:auto">'
 f'<h3>🏆 Top 10 performers · {html.escape(label)}</h3>'+table(best[:10],'#1f9d55')+f'<p><b>Honorable mentions:</b> {hm(best[10:15])}</p>'
 +(f'<h3>📈 Trending &amp; outlook</h3>{summ}' if summ else '')
 +f'<h3>🥶 Top 10 worst performers · {html.escape(label)}</h3>'+table(worst[:10],'inherit')+f'<p><b>Honorable mentions:</b> {hm(worst[10:15])}</p>'
 +'<p style="font-size:12px;color:#667085">Ranked by total Best-slot BBL points (each game scored in the player\'s best eligible slot: G rebounds ×2, F assists ×3, C 3PM +1); Base = without slot bonuses. Avg = best-slot points per game. Game by game shows each game\'s points; ▲/▼ compares the second half of his games with the first. Worst list: per-game average, minimum 2 games and 20 minutes a game. ★ = your player; otherwise the fantasy team that owns him, or FA.</p></div>')
open('weekly_email.html' if EMAIL else 'weekly.html','w').write(out)
print('ok',len(P),'players')
