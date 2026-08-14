#!/usr/bin/env python3
import os
import requests
import sys
from dotenv import load_dotenv

load_dotenv()
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
RAPIDAPI_HOST = os.getenv('RAPIDAPI_HOST')

if len(sys.argv) < 4:
    print('Usage: sample_booking_fetch.py CITY CHECKIN CHECKOUT')
    sys.exit(2)
city, checkin, checkout = sys.argv[1], sys.argv[2], sys.argv[3]

headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
# resolve location
loc = requests.get(f"https://{RAPIDAPI_HOST}/v1/hotels/locations", headers=headers, params={"name": city, "locale": "en-gb"}, timeout=6)
print('locations status', loc.status_code)
if loc.status_code != 200:
    print(loc.text)
    sys.exit(1)
loc_data = loc.json()
first_loc = loc_data[0]
print('location sample:', first_loc.get('name'), first_loc.get('dest_id'))

search_params = {
    "dest_id": first_loc.get('dest_id'),
    "dest_type": first_loc.get('dest_type'),
    "locale": "en-gb",
    "checkin_date": checkin,
    "checkout_date": checkout,
    "filter_by_currency": "GBP",
    "units": "metric",
    "room_number": 1,
    "adults_number": 2,
    "page_size": 3,
    "order_by": "price",
}
resp = requests.get(f"https://{RAPIDAPI_HOST}/v1/hotels/search", headers=headers, params=search_params, timeout=8)
print('search status', resp.status_code)
if resp.status_code != 200:
    print(resp.text)
    sys.exit(1)

data = resp.json()
# pick first candidate
candidate = None
if isinstance(data, dict):
    for key in ("result", "results", "search_results", "hotels", "data", "properties"):
        if key in data and isinstance(data[key], (list, tuple)) and len(data[key]) > 0:
            candidate = data[key][0]
            break
if candidate is None and isinstance(data, (list, tuple)) and len(data) > 0:
    candidate = data[0]

print('candidate keys:', list(candidate.keys())[:20])
# extract price
price = None
for p in ("min_total_price", "min_price", "price", "price_breakdown", "composite_price_breakdown"):
    if p in candidate:
        val = candidate[p]
        if isinstance(val, (int, float)):
            price = int(val)
            break
        if isinstance(val, dict):
            gross = val.get("gross_amount") or val.get("all_inclusive_amount") or val.get("all_inclusive_amount_hotel_currency")
            if isinstance(gross, dict):
                v = gross.get("value") or gross.get("amount")
                try:
                    price = int(float(v))
                    break
                except Exception:
                    pass
            for subk in ("value", "amount", "amount_rounded", "gross_price"):
                v = val.get(subk) if isinstance(val, dict) else None
                if v is not None:
                    try:
                        price = int(float(v))
                        break
                    except Exception:
                        pass
            if price is not None:
                break

if price is None:
    comp = candidate.get('composite_price_breakdown') or {}
    gross = comp.get('gross_amount') or comp.get('all_inclusive_amount')
    if isinstance(gross, dict):
        v = gross.get('value')
        try:
            price = int(float(v))
        except Exception:
            price = None

print('extracted price:', price)
print('hotel name:', candidate.get('hotel_name') or candidate.get('hotel_name_trans') or candidate.get('name'))
