#!/usr/bin/env python3
"""Quick test script to call the configured RapidAPI hotel search endpoint.

Usage:
  .venv/bin/python tools/test_hotel_api.py "City Name" 2026-08-01 2026-08-02

It reads RAPIDAPI_KEY and RAPIDAPI_HOST (optionally RAPIDAPI_ENDPOINT) from the environment or .env.
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
RAPIDAPI_ENDPOINT = os.getenv("RAPIDAPI_ENDPOINT") or "/v1/hotels/search"

if not RAPIDAPI_KEY or not RAPIDAPI_HOST:
    print("Missing RAPIDAPI_KEY or RAPIDAPI_HOST in environment. Set them in .env or export them.")
    sys.exit(2)

if len(sys.argv) < 4:
    print("Usage: tools/test_hotel_api.py \"City Name\" CHECKIN_ISO CHECKOUT_ISO")
    print("Example: tools/test_hotel_api.py \"London\" 2026-09-01 2026-09-02")
    sys.exit(2)

city = sys.argv[1]
checkin = sys.argv[2]
checkout = sys.argv[3]

url = f"https://{RAPIDAPI_HOST}{RAPIDAPI_ENDPOINT}"
headers = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
}
params = {
    "checkin_date": checkin,
    "checkout_date": checkout,
    "currency": "GBP",
    "locale": "en-gb",
    "order_by": "price",
    "page_size": 3,
    "city_name": city,
}
print(f"Calling RapidAPI {RAPIDAPI_HOST} -> {RAPIDAPI_ENDPOINT}")
print("URL:", url)
try:
    resp = requests.get(url, headers=headers, params=params, timeout=12)
    print("Status:", resp.status_code)
    j = resp.json()
    # print a compact summary
    if isinstance(j, dict):
        for k in ("results", "hotels", "data", "properties", "search_results"):
            if k in j:
                print(f"Found key '{k}' with {len(j[k])} entries")
                print(j[k][:2])
                break
        else:
            # no common list key
            print(j)
    else:
        print(j)
except Exception as e:
    print("Request failed:", e)
    sys.exit(1)
