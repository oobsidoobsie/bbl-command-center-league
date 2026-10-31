// Read-only: the name of the team this CBS sign-in manages. /teams opens on your own team, marked selected in the team list.
const d = new DOMParser().parseFromString(await (await fetch('/teams', {credentials: 'include'})).text(), 'text/html');
const o = [...d.querySelectorAll('select option[selected]')].find(x => /^\/teams\/\d+$/.test(x.value || ''));
o ? o.textContent.split(' (')[0].trim() : '';
