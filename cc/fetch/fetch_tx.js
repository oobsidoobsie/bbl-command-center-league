// League transactions (read-only). Run in a tab on the league domain.
// Output: one line per player move, newest first: when (ET text)|fantasy team|player|pos|NBA team|action
const h=await (await fetch('/transactions',{credentials:'include'})).text();
const d=new DOMParser().parseFromString(h,'text/html'); const out=[];
for(const r of d.querySelectorAll('tr')){
  if(r.cells.length<3) continue;
  const when=r.cells[0].textContent.replace(/\s+/g,' ').trim(); if(!/\d+\/\d+\/\d+/.test(when)) continue;
  const team=r.cells[1].textContent.replace(/\s+/g,' ').trim();
  const c=r.cells[2]; const items=[]; let cur=null;
  for(const n of c.childNodes){
    if(n.nodeType===1&&n.matches('a.playerLink')&&!n.hasAttribute('subtab')){ cur={name:n.textContent.trim(),pt:'',act:''}; items.push(cur); continue; }
    if(!cur) continue;
    if(n.nodeType===1&&n.matches('span.playerPositionAndTeam')){ cur.pt=n.textContent.trim(); continue; }
    if(n.nodeType===1&&n.matches('.playerIconsWrapper')) continue;
    cur.act+=' '+n.textContent;
  }
  for(const it of items){ const [pos,nt]=it.pt.split('•').map(x=>x.trim()); out.push([when,team,it.name,pos||'',nt||'',it.act.replace(/\s+/g,' ').replace(/^\s*-\s*/,'').trim()].join('|')); }
}
out.join('\n')
