// Read-only: one team's CBS lineup for one date (__TEAM__ = fantasy team name, __DATE__ = YYYYMMDD, __PERIOD__ = fantasy period),
// for the pre-lock lineup check (cc/lineup_check.py). JSON list of players:
//   n name, sec A (active) / R (reserve) / I (injured reserve), pos CBS eligibility, nba team,
//   tip (game start, Unix seconds; 0 = no game that day), inj (CBS injury note, e.g. "Hamstring: Expected to be out until at least Nov 13"),
//   out (true when the note rules him out; CBS shows its red cross on Game Time Decisions too, so this reads the note)
const page = async (u) => new DOMParser().parseFromString(await (await fetch(u, {credentials: 'include'})).text(), 'text/html');
const home = await page('/teams');
const want = '__TEAM__'.toLowerCase();
let id = null;
for (const o of home.querySelectorAll('select option')) {
  const m = (o.value || '').match(/^\/teams\/(\d+)$/);
  if (m && o.textContent.split(' (')[0].trim().toLowerCase() === want) id = m[1];
}
if (!id) for (const a of home.querySelectorAll('a[href*="/teams/"]')) {
  const m = (a.getAttribute('href') || '').match(/\/teams\/(\d+)$/);
  if (m && a.textContent.trim().toLowerCase() === want) id = m[1];
}
if (!id) throw new Error('team not found: __TEAM__');
const d = await page('/teams/' + id + '/__PERIOD__/__DATE__');
const out = [];
let sec = 'A';   // rows run Active, then a "Reserves" subtitle row, then an "Injured" one
for (const tr of d.querySelectorAll('tr.playerRow')) {
  if (tr.classList.contains('subtitle')) { sec = /injur/i.test(tr.textContent) ? 'I' : 'R'; continue; }
  const a = tr.querySelector('a.playerLink[href*="/players/playerpage/"]');
  if (!a || tr.classList.contains('empty')) continue;
  const pt = (tr.querySelector('.playerPositionAndTeam') || {}).textContent || '';
  const [pos, nba] = pt.split('•').map(x => x.trim());
  const sc = [...tr.querySelectorAll('script')].map(s => s.textContent).join(' ');
  const m = sc.match(/formatTime\([^,]+,\s*(\d{9,})/);
  const ij = tr.querySelector('a[subtab="Injury Report"]');
  const note = ij ? (ij.closest('[title]') || {}).title || '' : '';
  out.push({n: a.textContent.trim(), sec: tr.classList.contains('benchPlayer') ? (sec === 'A' ? 'R' : sec) : sec, pos: pos || '', nba: nba || '',
            tip: m ? +m[1] : 0, inj: note, out: !!note && !/game time decision/i.test(note)});
}
JSON.stringify(out)
