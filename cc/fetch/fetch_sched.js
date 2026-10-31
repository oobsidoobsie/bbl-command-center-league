// Upcoming NBA games with opponents (read-only). Run in a tab on espn.com. Replace __FROM__ with YYYYMMDD (today, Calgary date).
// Output: one line per regular-season game for the next 21 days: date|away|home|tip (UTC ISO)
const FROM='__FROM__', N=21; const out=[];
const d0=new Date(FROM.slice(0,4)+'-'+FROM.slice(4,6)+'-'+FROM.slice(6)+'T12:00:00Z');
const ds=[...Array(N)].map((_,i)=>{const d=new Date(d0);d.setUTCDate(d.getUTCDate()+i);return d.toISOString().slice(0,10).replace(/-/g,'')});
const rs=await Promise.all(ds.map(dt=>fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+dt).then(r=>r.json()).then(j=>({dt,j})).catch(()=>({dt,j:{}}))));
for(const {dt,j} of rs) for(const e of (j.events||[])){ if(!e.season||e.season.type!==2) continue; const c=e.competitions[0]; const h=c.competitors.find(x=>x.homeAway==='home'), a=c.competitors.find(x=>x.homeAway==='away'); out.push([dt,a.team.abbreviation,h.team.abbreviation,e.date].join('|'))}
out.join('\n')
