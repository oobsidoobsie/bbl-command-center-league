// Your finished periods, from the league's /schedule page (the signed-in team's schedule; read-only).
// Output: period|opponent (@ = away)|Won/Lost/Tied|your points|their points|your record after it
const h=await (await fetch('/schedule',{credentials:'include'})).text();
const d=new DOMParser().parseFromString(h,'text/html'); const out=[];
for(const r of d.querySelectorAll('tr')){
  const c=[...r.cells].map(x=>x.textContent.replace(/\s+/g,' ').trim());
  if(c.length<3||!/^\d+$/.test(c[0])) continue;
  const m=c.join(' ').match(/\b(Won|Lost|Tied)\s+([\d.]+)\s*-\s*([\d.]+)/); if(!m) continue;
  const rec=(c.join(' ').match(/(\d+-\d+-\d+)\s*$/)||['',''])[1];
  out.push([c[0],c[1],m[1],m[2],m[3],rec].join('|'));
}
out.join('\n')
