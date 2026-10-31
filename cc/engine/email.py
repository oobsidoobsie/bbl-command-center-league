#!/usr/bin/env python3
"""Compose the daily email from brief.html, moves_email.html, nightly_short.html.
Usage: python3 email.py "<Weekday Mon D>"  -> email.html, email.txt, subject.txt"""
import sys, os, re, html
os.chdir(os.path.dirname(os.path.abspath(__file__)))
label=sys.argv[1]; rd=lambda f: open(f).read() if os.path.exists(f) else ''
URL='local-page'
br=rd('brief.html')
H3='style="font-family:Arial,sans-serif;font-size:15px;margin:16px 0 4px;color:#c2410c;text-transform:uppercase;letter-spacing:.03em"'
def sty(x): return x.replace('<h3>',f'<h3 {H3}>').replace('<ul>','<ul style="margin:0;padding-left:18px">').replace('<li>','<li style="margin:3px 0">')
action='⚠️ Action needed' in br
lk=rd('lock.txt').strip().split('|')
parts=[]
if len(lk)>=4:
    parts.append(f'<div style="border:3px solid #b45309;padding:12px 14px;margin:0 0 12px;font-family:Arial,sans-serif"><div style="color:#b45309;font-size:13px;font-weight:bold;letter-spacing:1px">⏰ EARLY LOCK · {html.escape(lk[0]).upper()}</div><div style="color:#b45309;font-size:24px;font-weight:bold;margin:4px 0">Lineups &amp; IR lock at {html.escape(lk[3])} Calgary</div><div style="color:#1b2230;font-size:13px">First game {html.escape(lk[1])} tips at {html.escape(lk[2])}, earlier than the usual 5:00 PM. Set your lineup and make sure everyone on IR is ruled Out before then.</div></div>')
mi=rd('news_flag.txt').strip()
if mi: parts.append(f'<div style="border:3px solid #991b1b;padding:10px 14px;margin:0 0 12px;font-family:Arial,sans-serif"><div style="color:#991b1b;font-size:18px;font-weight:bold">🚑 Your player injured: {html.escape(mi)}</div><div style="color:#1b2230;font-size:13px">Details under Player news. Check his status before lineup lock, and move him to IR only if he is ruled Out.</div></div>')
parts.append(sty(br))
if rd('moves_email.html'): parts.append(f'<h3 {H3}>Moves to consider</h3>'+rd('moves_email.html'))
if rd('news_email.html'): parts.append(f'<h3 {H3}>Player news</h3>'+rd('news_email.html'))
if rd('nightly_short.html'): parts.append(f'<h3 {H3}>Around the league last night</h3>'+rd('nightly_short.html'))
parts.append(f'<p style="margin-top:16px"><a href="{URL}" style="color:#c2410c;font-weight:bold">Open BBL Command Center →</a><br><span style="font-size:12px;color:#667085">Today · Waivers · This period · Season</span></p>')
open('email.html','w').write('<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.45;color:#1b2230;max-width:620px">'+''.join(parts)+'</div>')
def txt(h):
    h=re.sub(r'<h3[^>]*>(.*?)</h3>',lambda m:'\n'+m.group(1).upper()+'\n',h); h=re.sub(r'<li[^>]*>','- ',h); h=re.sub(r'</li>|</p>','\n',h)
    return html.unescape(re.sub(r'<[^>]+>','',h))
t=(f'*** YOUR PLAYER INJURED: {mi} ***\n' if mi else '')+(f'*** EARLY LOCK {lk[0]}: lineups & IR lock at {lk[3]} Calgary (first game {lk[1]} at {lk[2]}) ***\n\n' if len(lk)>=4 else '')+txt(br)+'\nMOVES TO CONSIDER\n'+rd('moves.txt')+('\nPLAYER NEWS\n'+rd('news.txt.out') if rd('news.txt.out') else '')+('\nAROUND THE LEAGUE LAST NIGHT\n'+rd('nightly_short.txt') if rd('nightly_short.txt') else '')+f'\nFull report: {URL}\n'
t=re.sub(r'\n\s*\n- ','\n- ',t); open('email.txt','w').write(re.sub(r'\n{3,}','\n\n',t).strip()+'\n')
bo=os.path.exists('breakout.tsv') and (open('breakout_label.txt').read().strip() if os.path.exists('breakout_label.txt') else label)==label and any(len(l.split('|'))>4 and l.split('|')[1]=='BREAKOUT' and l.split('|')[4]=='FA' for l in open('breakout.tsv'))
open('subject.txt','w').write((f'🚑 {mi} hurt · ' if mi else '')+(f'⏰ Early lock {lk[3]} · ' if len(lk)>=4 else '')+f'🏀 BBL daily — {label}'+(' · ⚠️ action needed' if action else '')+(' · 🚀 breakout' if bo else ''))
print(open('subject.txt').read())
