// BBL defense-vs-position: run in a browser tab on espn.com. Replace __FROM__ and __TO__ with YYYYMMDD (inclusive).
// For every completed regular-season game, outputs one line per defending team and position group:
// date|defense|pos(G/F/C)|fantasy points allowed (BBL scoring + natural slot bonus)|minutes|game id
const FROM='__FROM__', TO='__TO__';
const d0=new Date(FROM.slice(0,4)+'-'+FROM.slice(4,6)+'-'+FROM.slice(6)+'T12:00:00Z'), d1=new Date(TO.slice(0,4)+'-'+TO.slice(4,6)+'-'+TO.slice(6)+'T12:00:00Z');
const dates=[]; for(let d=new Date(d0); d<=d1; d.setUTCDate(d.getUTCDate()+1)) dates.push(d.toISOString().slice(0,10).replace(/-/g,''));
const grp=p=>/C/.test(p)?'C':(/F/.test(p)?'F':(/G/.test(p)?'G':''));
const ev=[];
for(let i=0;i<dates.length;i+=8){
  const rs=await Promise.all(dates.slice(i,i+8).map(dt=>fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+dt).then(r=>r.json()).then(j=>({dt,j})).catch(()=>({dt,j:{}}))));
  for(const {dt,j} of rs) for(const e of (j.events||[])) if(e.status&&e.status.type&&e.status.type.completed&&e.season&&e.season.type===2) ev.push({dt,id:e.id});
}
const out=[];
for(let i=0;i<ev.length;i+=8){
  const gs=await Promise.all(ev.slice(i,i+8).map(x=>fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+x.id).then(r=>r.json()).then(g=>({x,g})).catch(()=>null)));
  for(const it of gs){ if(!it) continue; const {x,g}=it; const tp=(g.boxscore&&g.boxscore.players)||[]; if(tp.length!==2) continue;
    const abs=tp.map(t=>t.team.abbreviation);
    tp.forEach((t,ti)=>{ const def=abs[1-ti]; const st=t.statistics[0]; const k=st.keys; const acc={G:[0,0],F:[0,0],C:[0,0]};
      for(const a of st.athletes){ if(a.didNotPlay||!a.stats||!a.stats.length) continue;
        const v=Object.fromEntries(k.map((y,j)=>[y,a.stats[j]])); const sp=s=>(s||'0-0').split('-').map(Number);
        const [fgm,fga]=sp(v['fieldGoalsMade-fieldGoalsAttempted']),[tpm]=sp(v['threePointFieldGoalsMade-threePointFieldGoalsAttempted']),[ftm,fta]=sp(v['freeThrowsMade-freeThrowsAttempted']);
        const n=s=>Number(s)||0; const reb=n(v.rebounds),ast=n(v.assists);
        const pos=grp((a.athlete.position&&a.athlete.position.abbreviation)||''); if(!pos) continue;
        let fp=n(v.points)+2*fgm-fga+ftm-fta+reb+2*ast+4*n(v.steals)+4*n(v.blocks)-2*n(v.turnovers)-n(v.fouls);
        fp+= pos==='G'?reb:(pos==='F'?ast:tpm);
        acc[pos][0]+=fp; acc[pos][1]+=n(v.minutes);
      }
      for(const p of ['G','F','C']) out.push([x.dt,def,p,acc[p][0],acc[p][1],x.id].join('|'));
    });
  }
}
out.join('\n')
