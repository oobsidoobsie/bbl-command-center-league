// Run in a browser tab on espn.com. Replace __DATE__ with YYYYMMDD (the night's games, ET date).
// Output first line: #games|completed|inprogress ; then one line per player who played:
// name|team|min|pts|fgm|fga|tpm|tpa|ftm|fta|reb|ast|to|stl|blk|pf|espnpos
const sb=await (await fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=__DATE__')).json();
const ev=sb.events||[]; const done=ev.filter(e=>e.status&&e.status.type&&e.status.type.completed);
const out=[];
for(const e of done){
  const g=await (await fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+e.id)).json();
  for(const t of (g.boxscore&&g.boxscore.players)||[]){
    const ab=t.team.abbreviation; const st=t.statistics[0]; const k=st.keys;
    for(const a of st.athletes){ if(a.didNotPlay||!a.stats||!a.stats.length) continue;
      const v=Object.fromEntries(k.map((x,i)=>[x,a.stats[i]]));
      const sp=s=>(s||'0-0').split('-');
      const [fgm,fga]=sp(v['fieldGoalsMade-fieldGoalsAttempted']),[tpm,tpa]=sp(v['threePointFieldGoalsMade-threePointFieldGoalsAttempted']),[ftm,fta]=sp(v['freeThrowsMade-freeThrowsAttempted']);
      out.push([a.athlete.displayName,ab,v.minutes,v.points,fgm,fga,tpm,tpa,ftm,fta,v.rebounds,v.assists,v.turnovers,v.steals,v.blocks,v.fouls,(a.athlete.position&&a.athlete.position.abbreviation)||'',a.athlete.id||''].join('|'));
    }
  }
}
`#${ev.length}|${done.length}|${ev.length-done.length}\n`+out.join('\n')
