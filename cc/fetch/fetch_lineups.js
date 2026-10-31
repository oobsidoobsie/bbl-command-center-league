// Read-only: every team's CBS lineup for one date (__DATE__ = YYYYMMDD, __PERIOD__ = fantasy period).
// Output lines: #STATUS|YYYYMMDD|fantasy team|player|ACTIVE or RESERVE  (reserves include injured reserve)
const page = async (u) => new DOMParser().parseFromString(await (await fetch(u, {credentials: 'include'})).text(), 'text/html');
const home = await page('/teams');
const TEAMS = {};
for (const o of home.querySelectorAll('select option')) {
  const m = (o.value || '').match(/^\/teams\/(\d+)$/);
  if (m) TEAMS[m[1]] = o.textContent.split(' (')[0].trim();
}
if (!Object.keys(TEAMS).length) for (const a of home.querySelectorAll('a[href*="/teams/"]')) {
  const m = (a.getAttribute('href') || '').match(/\/teams\/(\d+)$/);
  if (m && a.textContent.trim()) TEAMS[m[1]] = a.textContent.trim();
}
const out = [];
for (const [id, tn] of Object.entries(TEAMS)) {
  const d = await page('/teams/' + id + '/__PERIOD__/__DATE__');
  for (const tr of d.querySelectorAll('tr.playerRow')) {
    const a = tr.querySelector('a[href*="/players/playerpage/"]');
    if (a) out.push(['#STATUS', '__DATE__', tn, a.textContent.trim(), tr.classList.contains('benchPlayer') ? 'RESERVE' : 'ACTIVE'].join('|'));
  }
}
out.join('\n')
