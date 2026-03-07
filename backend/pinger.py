"""Simple keep-alive ping utility for free-tier hosts.

Run this script on a separate machine or cron job to regularly hit the
API's /health endpoint. This can delay (but not guarantee) sleeping on
platforms like Heroku/Render.

Usage example:
    python backend/pinger.py https://myapp.herokuapp.com/health 25

The second argument is the interval in minutes (default: 25).
"""

import sys
import time
import requests


def ping(url: str, interval_minutes: float = 25):
    print(f"Starting keep-alive pinger to {url} every {interval_minutes} minutes")
    sec = interval_minutes * 60
    while True:
        try:
            r = requests.get(url, timeout=10)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {url} -> {r.status_code}")
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ping failed: {e}")
        time.sleep(sec)


def main():
    if len(sys.argv) < 2:
        print("Usage: python backend/pinger.py <url> [interval_minutes]")
        sys.exit(1)
    url = sys.argv[1]
    interval = float(sys.argv[2]) if len(sys.argv) >= 3 else 25
    ping(url, interval)


if __name__ == '__main__':
    main()
