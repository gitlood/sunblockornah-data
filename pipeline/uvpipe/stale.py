"""Alarm: exit 1 when the live cities.json was generated more than MAX_AGE_H ago.

`gen` (when the job wrote the file) is used, not `run`: a CAMS run is 9-10 h old when it
lands, so run age legitimately reaches ~22 h. gen is refreshed twice a day.
--simulate-stale ignores the live file and treats it as 100 h old, to prove the alarm.
Usage: python -m uvpipe.stale [--url URL] [--max-age-h 18] [--simulate-stale]
"""
import argparse
import datetime as dt
import json
import sys
import time
import urllib.request

URL = "https://gitlood.github.io/sunblockornah-data/v1/cities.json"
MAX_AGE_H = 18
SIMULATED_AGE_H = 100


def parse_gen(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def check(doc, now, max_age_h=MAX_AGE_H):
    """Return (ok, message) for a parsed cities.json."""
    try:
        gen = parse_gen(doc["gen"])
        run = doc["run"]
    except (KeyError, TypeError, ValueError):
        return False, "live cities.json has no valid gen/run"
    age = (now - gen).total_seconds() / 3600
    msg = f"live data run {run}, generated {doc['gen']} ({age:.1f} h ago, limit {max_age_h} h)"
    if age < 0:
        return False, msg + ": generated in the future"
    return age <= max_age_h, msg


def fetch_live(url, attempts=3):
    last = None
    for n in range(attempts):
        try:
            req = urllib.request.Request(f"{url}?t={int(time.time())}",
                                         headers={"Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(5 * (n + 1))
    raise RuntimeError(f"cannot fetch {url}: {type(last).__name__}")


def main(argv=None, now=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    ap.add_argument("--max-age-h", type=float, default=MAX_AGE_H)
    ap.add_argument("--simulate-stale", action="store_true")
    a = ap.parse_args(argv)
    now = now or dt.datetime.now(dt.timezone.utc)
    if a.simulate_stale:
        gen = (now - dt.timedelta(hours=SIMULATED_AGE_H)).strftime("%Y-%m-%dT%H:%M:%SZ")
        doc = {"run": "simulated", "gen": gen}
    else:
        try:
            doc = fetch_live(a.url)
        except RuntimeError as e:
            print(f"STALE: {e}", file=sys.stderr)
            return 1
    ok, msg = check(doc, now, a.max_age_h)
    print(("OK: " if ok else "STALE: ") + msg, file=None if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
