#!/usr/bin/env python3
import requests
import json
import sys

URL = "https://www.wattpad.com/v5/comments/namespaces/parts/resources/447548916/comments?after=447548916%23daba3461fe1f77c43b6d2b46b5433912%231721898944%23d67d15d464"

def main():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    })
    try:
        print(f"Fetching: {URL}")
        r = s.get(URL, timeout=15)
        print(f"Status: {r.status_code}")
        ct = r.headers.get('Content-Type','')
        print(f"Content-Type: {ct}")
        # Try JSON
        try:
            j = r.json()
            print("JSON keys:", list(j.keys()) if isinstance(j, dict) else type(j))
            print(json.dumps(j if isinstance(j, dict) else j, ensure_ascii=False, indent=2)[:2000])
        except Exception:
            print("Response text (first 1000 chars):")
            print(r.text[:1000])
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
