// Run in a browser tab on the league domain (signed in). Reads CBS "Roster Trends": the 50 most-added and
// 50 most-dropped players with their rostered % across all CBS leagues last week and this week.
// Output: name|pos|nba_team|prev%|cur%|change|added|dropped (one line per player)
const d=new DOMParser().parseFromString(await (await fetch('/players/roster-trends')).text(),'text/html');
const out=[];
for(const t of d.querySelectorAll('table')){
  const rows=[...t.querySelectorAll('tr')].map(r=>[...r.cells].map(c=>c.textContent.trim().replace(/\s+/g,' ')));
  if(!rows.length||rows.length>80) continue;
  const kind=/Most Added/i.test(rows[0].join(' '))?'added':(/Most Dropped/i.test(rows[0].join(' '))?'dropped':'');
  if(!kind) continue;
  for(const c of rows){ if(c.length<4) continue; const m=c[0].match(/^(.*?) ([CFG](?:,[CFG])*) • (\w+)$/); if(!m) continue;
    out.push([m[1],m[2],m[3],c[1],c[2],c[3],kind].join('|')); }
}
out.join('\n')
