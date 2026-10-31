"""The browser side: a private Chromium profile that remembers your CBS sign-in, used to run the read-only fetch scripts.

The fetch scripts in cc/fetch are the same ones the Claude version ran in your browser. They only READ pages
(ESPN's public feeds and your CBS league pages). Nothing here clicks, submits or changes anything on CBS.
"""
import os
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.path.join(ROOT, "data", "browser-profile")
FETCH = os.path.join(ROOT, "cc", "fetch")
LEAGUE = "https://bblbombasticbaketballleague.basketball.cbssports.com"
ESPN = "https://www.espn.com/nba/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def script(name, **subs):
    src = open(os.path.join(FETCH, name + ".js"), encoding="utf-8").read()
    for k, v in subs.items():
        src = src.replace(f"__{k}__", v)
    return src


SHIM = r"""(() => {
  if (window.__shimmed) return; window.__shimmed = true;
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const u = new URL(typeof input === 'string' ? input : input.url, location.href.startsWith('http') ? location.href : 'https://www.espn.com/');
    if (location.protocol.startsWith('http') && u.host === location.host) return nativeFetch(input, init);
    const r = await window.__pyfetch(u.href);
    const bin = atob(r.b64), bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Response(bytes, {status: r.status, headers: {'Content-Type': r.type}});
  };
})()"""


class Browser:
    """with Browser(show=False) as b: b.espn('fetch_news')"""

    def __init__(self, show=False):
        self.show = show

    def __enter__(self):
        self.pw = sync_playwright().start()
        args = ["--window-position=-2400,-2400"] if self.show == "offscreen" else []
        self.ctx = self.pw.chromium.launch_persistent_context(
            PROFILE, headless=not self.show, args=args, viewport={"width": 1280, "height": 900})
        self.pages = {}
        return self

    def __exit__(self, *a):
        try:
            self.ctx.close()
        finally:
            self.pw.stop()

    @staticmethod
    def _pyfetch(url):
        """Fetch a public URL from Python (browser CORS rules don't apply)."""
        import gzip
        import urllib.error
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                                                   "Accept-Encoding": "gzip"})
        import base64
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data, status, ctype = r.read(), r.status, r.headers.get("Content-Type", "")
                if r.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
        except urllib.error.HTTPError as e:
            data, status, ctype = e.read(), e.code, e.headers.get("Content-Type", "")
        if status == 200 and not data and "api.espn.com" in url and "lang=en" not in url:
            # ESPN's cache sometimes holds an empty answer for one exact address (Oct 27: the 10/26 scoreboard);
            # the same feed under a slightly different address comes back whole
            return Browser._pyfetch(url + ("&" if "?" in url else "?") + "lang=en&region=us")
        return {"status": status, "b64": base64.b64encode(data).decode(), "type": ctype or "application/octet-stream"}

    def _page(self, key, url):
        pg = self.pages.get(key)
        if pg is None:
            pg = self.ctx.new_page()
            pg.set_default_timeout(60000)
            pg.expose_function("__pyfetch", self._pyfetch)
            # ESPN's data feeds are public APIs: run those scripts on a blank page and fetch through Python.
            # On CBS, same-site requests use the page's own sign-in; anything off-site goes through Python too.
            pg.goto("about:blank" if key == "espn" else url, wait_until="domcontentloaded")
            self.pages[key] = pg
        pg.evaluate(SHIM)
        return pg

    def run(self, key, url, src, timeout=180):
        """Run a fetch script like the browser console would (top-level await, last expression returned).
        ESPN's feeds now and then send an empty or cut-off answer, so ESPN scripts get two more tries."""
        for wait in ((5, 20, None) if key == "espn" else (None,)):
            try:
                return self._run(key, url, src, timeout)
            except RuntimeError:
                if wait is None:
                    raise
                time.sleep(wait)

    def _run(self, key, url, src, timeout):
        pg = self._page(key, url)
        cdp = self.ctx.new_cdp_session(pg)
        r = cdp.send("Runtime.evaluate", {"expression": src, "awaitPromise": True, "replMode": True,
                                          "returnByValue": True, "timeout": timeout * 1000})
        cdp.detach()
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError((d.get("exception") or {}).get("description") or d.get("text") or "script error")
        v = (r.get("result") or {}).get("value")
        return "" if v is None else str(v)

    def espn(self, name, **subs):
        try:
            return self.run("espn", ESPN, script(name, **subs))
        except Exception as e:
            raise RuntimeError(f"ESPN step {name} failed: {e}") from None

    def cbs(self, name, **subs):
        try:
            return self.run("cbs", LEAGUE, script(name, **subs))
        except Exception as e:
            raise RuntimeError(f"CBS step {name} failed: {e}") from None

    def cbs_signed_in(self):
        pg = self._page("cbs", LEAGUE)
        url = pg.url.lower()
        if "login" in url or "signin" in url:
            return False
        return self.run("cbs", LEAGUE, "!!document.querySelector('a[href*=\"/teams/\"]')") == "True"


def sign_in():
    """Opens a visible browser on the CBS sign-in page. You sign in yourself; the profile remembers it."""
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, headless=False, viewport={"width": 1200, "height": 900})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(LEAGUE)
        print("A browser window opened on your CBS league.")
        print("Sign in there if it asks (type your password into CBS yourself),")
        print("check that you can see the league, then CLOSE THAT BROWSER WINDOW to finish.")
        try:
            pg.wait_for_event("close", timeout=0)
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
    print("Saved. The nightly run will use this sign-in.")


if __name__ == "__main__":
    sign_in()
