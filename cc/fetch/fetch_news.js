// Run in a built-in-browser tab on https://www.espn.com. ESPN NBA news feed (public API), player-tagged.
// Output lines: ISO time|ESPN|headline — description|athlete1,athlete2
const j=await (await fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news?limit=100&_='+Date.now())).json();
(j.articles||[]).filter(a=>!/Game Highlights/i.test(a.headline)).map(a=>[a.published.slice(0,16),'ESPN',(a.headline+(a.description?' — '+a.description:'')).replace(/\|/g,'/').replace(/\s+/g,' '),(a.categories||[]).filter(c=>c.type==='athlete').map(c=>c.description).join(',')].join('|')).join('\n')
