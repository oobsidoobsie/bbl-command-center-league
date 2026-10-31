# 🏀 BBL Command Center: League Edition

A nightly fantasy dashboard for your BBL team. It runs on your own Windows PC and needs no paid services.

It builds your team's page: projections and best lineups, Best adds, Streaming, Rivals, Watchlist, Trades, Start/Sit, Season, Playoffs and the nightly Best & Worst.

## Whose data you get

- **One team only.** The page is always for the team your CBS sign-in manages. There's no setting to choose a team, and it can't build pages for other managers.
- **Your settings stay on your PC.** Your watchlist, your settings, your CBS sign-in and your Gmail app password are never uploaded.
- **Other managers' private notes are never included.** Each manager's watchlist and settings stay on that manager's own PC.
- **League information still appears.** Rosters, lineups, transactions and standings of other teams feed Rivals, Trades and win odds. Any league member can already see these on CBS.

It only reads CBS and ESPN. It never changes your lineup, roster, claims or trades. You type your password into CBS yourself, and the code doesn't store it.

## Setup (once, about 15 minutes)

1. **Install Python 3.13** from <https://www.python.org/downloads/windows/>. On the first screen, tick **"Add python.exe to PATH"**.
2. **Put this folder somewhere permanent**, such as `Documents\bbl-command-center-league`. If you downloaded a zip, unzip it first.
3. **Double-click `1 - Setup`.** If Windows shows *"Windows protected your PC"*, click **More info → Run anyway**. It downloads about 200 MB.
4. **Double-click `2 - Sign in to CBS`.** Sign in with your own CBS account, check that you can see the league, then close that window.
5. **Double-click `3 - Run now`.** It takes a few minutes, then your Command Center opens.
6. **Double-click `4 - Schedule nightly`** to build it every night (11:25 PM by default). Your PC must be on or asleep, and you must be signed in to Windows.

`4 - Schedule nightly` also adds a pre-lock lineup check: a Windows notification about an hour before lineups lock if your CBS lineup can be better.

### Email (optional)

Emails are off until you set them up. They go through your own Gmail, using an app password you can revoke at any time:

1. Create an app password called "BBL" at <https://myaccount.google.com/apppasswords>. This needs 2-Step Verification on your Google account.
2. Paste it into `secret.txt` in this folder.
3. In `config.txt`, set `email=yes`, `email_to=` (where the reports go) and `gmail_address=` (your Gmail).

## Every day

Double-click **`6 - Open Command Center`**. It opens your page from a small server that only your PC can reach, so you can edit the Watchlist and your roster settings. Close its window when you're done.

Opening `BBL Command Center.html` directly also works, but the page is then read-only.

## What to expect at first

- **History starts when you install.** It backfills up to the last 7 nights, so older nights are missing from the archive and from anything built on them.
- **Draft results show this season only.**
- **Some text is automatic.** The page fills in its own short notes, with no written briefing.

## Files

| File | What it does |
|---|---|
| `1 - Setup` | One-time setup |
| `2 - Sign in to CBS` | Saves your CBS sign-in |
| `3 - Run now` | Builds your page now |
| `4 - Schedule nightly` / `5 - Remove schedule` | Starts or stops the nightly run and lineup check |
| `6 - Open Command Center` | Opens your page, with editing on |
| `7 - Check my lineup now` | Runs the lineup check now |
| `config.txt` | Your options: email, notifications, run time. Created on the first run |
| `managers\` | Your `settings.txt` and `watchlist.txt` |

## Troubleshooting

- **"CBS couldn't be read" or "CBS didn't show a team"**: run `2 - Sign in to CBS` again with your own account. If it keeps happening, set `show_browser=offscreen` in `config.txt`.
- **The page shows the wrong team**: the sign-in saved here belongs to someone else. Run `2 - Sign in to CBS`, sign out, sign in as yourself, then run `3 - Run now`.
- **The nightly run didn't happen**: the PC was off or you were signed out of Windows. Run `3 - Run now`.
- **Setup says it needs Python 3.12**: install Python 3.13, then run `1 - Setup` again.
- **Anything else**: every run writes `output\last run log.txt`.
