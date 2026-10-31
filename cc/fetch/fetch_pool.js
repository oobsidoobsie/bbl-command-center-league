// Run in a browser tab on the league domain. Replace the WATCH placeholder below with a JSON array of watchlist names.
// Output: name|team|pos|own|gp|G|F|C|sec|slot|rost|start   own = MINE | FA | TAKEN:<fantasy team>; sec = A/R/I roster section;
// slot = CBS lineup slot (G/F/C, blank on the bench), rost/start = % rostered/started in all CBS leagues (rostered players only)
// #PRIM|name|PG = CBS primary position of a two-position player (CBS's game log gives him that slot's bonus every game);
// blank when the page shows none. Only players not in KNOWN (already saved) and your own players are looked up. #GLOG|name|M/D:fpts,... = CBS game log of each of your players.
const ME=__ME__, WATCH=__WATCH__, KNOWN=new Set(__KNOWN__);
const sd=new DOMParser().parseFromString(await (await fetch('/standings/overall')).text(),'text/html');
const TEAMS={};for(const a of sd.querySelectorAll('a[href*="/teams/"]')){const id=(a.getAttribute('href').match(/\/teams\/(\d+)/)||[])[1];const t=a.innerText.trim();if(id&&t&&!TEAMS[id])TEAMS[id]=t}
const OWN={}; const LOGO={};
for(const [id,tn] of Object.entries(TEAMS)){
  const d=new DOMParser().parseFromString(await (await fetch('/teams/'+id)).text(),'text/html'); let sec='A';
  const lg=[...d.querySelectorAll('img')].map(i=>i.getAttribute('src')||'').find(s=>s.includes('/team_logo/'+id+'-')); if(lg) LOGO[tn]=lg.split('?')[0];
  for(const tr of d.querySelectorAll('tr')){const t=tr.innerText.trim(); if(/^Reserves/.test(t))sec='R'; else if(/^Injured/.test(t))sec='I';
    const c=[...tr.cells].map(x=>x.innerText.trim().replace(/\s+/g,' ')); const m=c.join(' | ').match(/([A-Z][^|•]*?) ([CFG](?:,[CFG])*) • (\w+)/);
    const pct=c.filter(x=>/^\d+%$/.test(x));  // Trends: Rost %, Start % (across all CBS leagues)
    if(m&&c.length>4&&!OWN[m[1].trim()]) OWN[m[1].trim()]={tn,sec,slot:/^[CFG]$/.test(c[1])?c[1]:'',rost:(pct[0]||'').replace('%',''),start:(pct[1]||'').replace('%','')};}
}
const P={};
for(const pos of ['G','F','C']){
  const d=new DOMParser().parseFromString(await (await fetch('/stats/stats-main/all:'+pos+'/restofseason:p/standard/projections?print_rows=9999')).text(),'text/html');
  for(const r of d.querySelectorAll('tr')){
    const c=[...r.cells].map(x=>x.innerText.trim().replace(/\s+/g,' ')); if(c.length<19) continue;
    const m=c[2].match(/^(.*?) ([CFG](?:,[CFG])*) • (\w+)/); if(!m) continue;
    const v=parseFloat(c[17]); if(isNaN(v)) continue;
    const a=r.querySelector('a[href*="/players/playerpage/"]'), id=a?(a.getAttribute('href').match(/playerpage\/(\d+)/)||[])[1]:'';
    const k=m[1]; P[k]=P[k]||{team:m[3],pos:m[2],gp:parseFloat(c[3])||0,id}; P[k][pos]=v;
    const ij=r.querySelector('a[subtab="Injury Report"]'); if(ij) P[k].inj=((ij.closest('[title]')||{}).title||'').replace(/\|/g,'/');   // e.g. "Knee: Game Time Decision"
  }
}
// Player pages: primary position (the "#0 PG • Indiana" line) and the game log, 8 pages at a time
const page=async id=>{try{return await (await fetch('/players/playerpage/'+id)).text()}catch(e){return ''}};
const prim=t=>(t.match(/#\d+\s+([A-Z]{1,2})\s+(?:&#149;|•)/)||[])[1]||'';
const glog=t=>{const d=new DOMParser().parseFromString(t,'text/html');let hd=null;const out=[];
  for(const tr of d.querySelectorAll('tr')){const c=[...tr.cells].map(x=>x.innerText.trim());
    if(/^date$/i.test(c[0]||'')&&c.includes('FPTS')){hd=c;continue}
    if(hd&&/^\d+\/\d+$/.test(c[0]||'')&&c.length===hd.length)out.push(c[0]+':'+c[hd.indexOf('FPTS')])}
  return out.join(',')};
const PRIM={}, GLOG={};
const jobs=Object.entries(P).filter(([n,p])=>p.id&&((p.pos.includes(',')&&!KNOWN.has(n))||(OWN[n]&&OWN[n].tn===ME)));
for(let i=0;i<jobs.length;i+=8) await Promise.all(jobs.slice(i,i+8).map(async([n,p])=>{const t=await page(p.id);
  if(p.pos.includes(','))PRIM[n]=prim(t); if(OWN[n]&&OWN[n].tn===ME)GLOG[n]=glog(t)}));
// Embed logos as small data: URIs (the artifact viewer blocks images from other sites)
for(const [t,u] of Object.entries(LOGO)){try{const bm=await createImageBitmap(await (await fetch(u)).blob());const c=new OffscreenCanvas(48,48);const s=Math.min(bm.width,bm.height);c.getContext('2d').drawImage(bm,(bm.width-s)/2,(bm.height-s)/2,s,s,0,0,48,48);const b=await c.convertToBlob({type:'image/webp',quality:0.85});LOGO[t]=await new Promise(r=>{const f=new FileReader();f.onload=()=>r(f.result);f.readAsDataURL(b)})}catch(e){}}
const own=n=>{const o=OWN[n]; if(!o) return 'FA'; return o.tn===ME?'MINE':'TAKEN:'+o.tn};
Object.entries(P).filter(([n,p])=>{const o=own(n);return o!=='FA'||WATCH.includes(n)||(Math.max(p.G||0,p.F||0,p.C||0)>=12&&p.gp>=40)})
 .map(([n,p])=>{const o=OWN[n]||{};return [n,p.team,p.pos,own(n),p.gp,p.G??'',p.F??'',p.C??'',o.sec||'',o.slot||'',o.rost||'',o.start||'',p.inj||''].join('|')}).join('\n')
 +'\n'+Object.entries(PRIM).map(([n,v])=>'#PRIM|'+n+'|'+v).join('\n')
 +'\n'+Object.entries(GLOG).map(([n,v])=>'#GLOG|'+n+'|'+v).join('\n')
 +'\n'+Object.entries(LOGO).map(([t,u])=>'#LOGO|'+t+'|'+u).join('\n')
 +'\n'+Object.entries(P).filter(([n,p])=>{const o=own(n);return !(o!=='FA'||WATCH.includes(n)||(Math.max(p.G||0,p.F||0,p.C||0)>=12&&p.gp>=40))}).map(([n,p])=>'#ALL|'+[n,p.team,p.pos,Math.max(p.G||0,p.F||0,p.C||0)].join('|')).join('\n')
