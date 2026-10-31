// Every player's stat line for one night, as CBS scored it (read-only). Run in a tab on the league domain.
// CBS fills this page in the morning after the games, so it is empty for a night that just ended.
// Output: name|pos|team|pts|fgm|fgp|ftm|ftp|tpm|tpp|reb|ast|stl|to|blk|fpts  (players who played)
const h=await (await fetch('/stats/stats-main/all:G:F:C/__DATE__:p/standard/stats?print_rows=9999',{credentials:'include'})).text();
const d=new DOMParser().parseFromString(h,'text/html'); const out=[]; let col=null;
const tx=c=>c.textContent.replace(/\s+/g,' ').trim();
for(const r of d.querySelectorAll('tr')){
  const c=[...r.cells].map(tx);
  if(c.includes('Player')&&c.includes('FPTS')){ col={}; c.forEach((x,i)=>col[x]=i); continue; }
  if(!col||r.cells.length<col.FPTS+1||c[col.G]!=='1') continue;
  const pc=r.cells[col.Player], a=pc.querySelector('a.playerLink')||pc.querySelector('a');
  const [pos,nt]=(pc.querySelector('.playerPositionAndTeam')?.textContent||tx(pc).split(' ').slice(-3).join(' ')).split('•').map(x=>x.trim());
  out.push([a?tx(a):tx(pc),pos||'',nt||'',...['PPG','FG','FGP','FT','FTP','3PT','3PTP','RPG','APG','SPG','TPG','BPG','FPTS'].map(k=>c[col[k]])].join('|'));
}
out.join('\n')
