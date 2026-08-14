import requests
import os
from dotenv import load_dotenv
from datetime import date, timedelta
import math

load_dotenv()
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# This probe makes live RapidAPI calls; skip cleanly (e.g. in CI) when no key.
try:
    import pytest
    if not RAPIDAPI_KEY:
        pytest.skip("RAPIDAPI_KEY not set — skipping live Furnace Creek price probe", allow_module_level=True)
except ImportError:
    if not RAPIDAPI_KEY:
        import sys
        print("RAPIDAPI_KEY not set — add it to .env to run this live probe.")
        sys.exit(2)

headers = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "booking-com.p.rapidapi.com"
}

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two coordinates"""
    R = 3959  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# Test date: October 4, 2027
test_date = date(2027, 10, 4)
checkout_date = test_date + timedelta(days=1)

loc_url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
search_url = "https://booking-com.p.rapidapi.com/v1/hotels/search"

# Furnace Creek (Death Valley) coordinates — the trip's Death Valley stop
# (replaces the old Furnace Creek stop from the pre-revision itinerary)
furnace_creek_coords = (36.4344, -116.8628)

nearby_cities_db = [
    ("Atlanta, Georgia", 33.7501, -84.3885),
    ("Decatur, Georgia", 33.7749, -84.2989),
    ("Marietta, Georgia", 33.9526, -84.5535),
    ("Memphis, Tennessee", 35.1486, -90.0519),
    ("Germantown, Tennessee", 35.1051, -89.8158),
    ("Collierville, Tennessee", 35.0754, -89.6633),
    ("Kansas City, Missouri", 39.0997, -94.5786),
    ("Overland Park, Kansas", 38.9813, -94.6769),
    ("Leawood, Kansas", 38.9674, -94.6001),
    ("Sioux Falls, South Dakota", 43.5476, -96.7294),
    ("Brandon, South Dakota", 43.6007, -96.5638),
    ("Brookings, South Dakota", 44.3683, -96.7899),
    ("Wall, South Dakota", 43.9947, -102.2384),
    ("Interior, South Dakota", 43.8341, -102.4076),
    ("Keystone, South Dakota", 43.9314, -103.4082),
    ("Hill City, South Dakota", 43.9776, -103.5712),
    ("Gillette, Wyoming", 44.2998, -105.5018),
    ("Ranchester, Wyoming", 44.9238, -106.6841),
    ("West Yellowstone, Montana", 44.4624, -111.1037),
    ("Gardiner, Montana", 45.0351, -110.7127),
    ("Jackson, Wyoming", 43.4799, -110.7624),
    ("Teton Village, Wyoming", 43.3736, -110.8274),
    ("Driggs, Idaho", 43.7299, -111.1169),
    ("Provo, Utah", 40.2338, -111.6585),
    ("Orem, Utah", 40.2969, -111.6946),
    ("Kayenta, Arizona", 36.7129, -110.2335),
    ("Chinle, Arizona", 36.1505, -109.6126),
    ("Williams, Arizona", 35.2491, -112.1890),
    ("Tusayan, Arizona", 35.9705, -112.1119),
    ("Springdale, Utah", 37.1945, -112.9570),
    ("Hurricane, Utah", 37.1789, -113.3018),
    ("Henderson, Nevada", 36.0395, -115.0267),
    ("North Las Vegas, Nevada", 36.1989, -115.1176),
    ("Furnace Creek, California", 36.4549, -116.8581),
    ("Ridgecrest, California", 35.6236, -120.6443),
    ("Visalia, California", 36.3302, -119.2944),
    ("Three Rivers, California", 36.4305, -118.8833),
    ("Mariposa, California", 37.4909, -119.7727),
    ("Lee Vining, California", 37.9628, -119.1207),
    ("South Lake Tahoe, California", 38.9557, -119.9789),
    ("Lake Tahoe, Nevada", 38.9557, -119.9789),
    ("Concord, California", 37.9735, -122.0310),
    ("Vacaville, California", 38.3567, -121.9847),
]

print("=" * 80)
print(f"Testing Furnace Creek area on {test_date.strftime('%B %d, %Y')}")
print(f"Filters: Review Score >= 6.0, Star Rating >= 3.0")
print("=" * 80)

# Find nearby cities within 20 miles
nearby_cities = [
    (name, lat, lon) for name, lat, lon in nearby_cities_db
    if haversine_distance(furnace_creek_coords[0], furnace_creek_coords[1], lat, lon) <= 20
]
nearby_cities_sorted = sorted(
    nearby_cities,
    key=lambda x: haversine_distance(furnace_creek_coords[0], furnace_creek_coords[1], x[1], x[2])
)

print(f"\n📍 Nearby cities within 20 miles:")
for name, lat, lon in nearby_cities_sorted:
    dist = haversine_distance(furnace_creek_coords[0], furnace_creek_coords[1], lat, lon)
    print(f"  {name}: {dist:.1f} miles away")

# Try to search Furnace Creek directly first
print(f"\n🔍 Searching 'Furnace Creek'...")
loc_response = requests.get(loc_url, headers=headers, params={"name": "Furnace Creek", "locale": "en-us"}, timeout=10)
data = loc_response.json()
if data:
    print(f"  Found: {data[0]['name']} ({data[0].get('region', 'unknown')})")
    dest = data[0]
    
    search_params = {
        "checkin_date": test_date.isoformat(),
        "checkout_date": checkout_date.isoformat(),
        "adults_number": "2",
        "room_number": "1",
        "dest_id": dest.get('dest_id'),
        "dest_type": dest.get('dest_type'),
        "locale": "en-us",
        "filter_by_currency": "USD",
        "order_by": "price",
        "units": "imperial"
    }
    search_response = requests.get(search_url, headers=headers, params=search_params, timeout=10)
    print(f"  Search status: {search_response.status_code}")
    
    if search_response.status_code == 200:
        hotels = search_response.json().get("result", [])
        print(f"  Total hotels found: {len(hotels)}")
        
        # Apply filters
        filtered = [h for h in hotels if float(h.get("review_score", 0) or 0) >= 6.0 and float(h.get("class", 0) or 0) >= 3.0]
        print(f"  Filtered (review >= 6.0, stars >= 3.0): {len(filtered)}")
        if filtered:
            for h in filtered[:5]:
                print(f"    - {h['name']}: ${h.get('price')}, {h.get('review_score')} review, {h.get('class')} stars")
    else:
        print(f"  Error: {search_response.text[:200]}")
else:
    print(f"  Location not found")

# Try nearby cities
print(f"\n🔍 Searching nearby cities:")
for name, lat, lon in nearby_cities_sorted:
    dist = haversine_distance(furnace_creek_coords[0], furnace_creek_coords[1], lat, lon)
    print(f"\n  {name} ({dist:.1f} miles):")
    
    loc_response = requests.get(loc_url, headers=headers, params={"name": name, "locale": "en-us"}, timeout=10)
    data = loc_response.json()
    if not data:
        print(f"    Location lookup failed")
        continue
    
    dest = data[0]
    search_params = {
        "checkin_date": test_date.isoformat(),
        "checkout_date": checkout_date.isoformat(),
        "adults_number": "2",
        "room_number": "1",
        "dest_id": dest.get('dest_id'),
        "dest_type": dest.get('dest_type'),
        "locale": "en-us",
        "filter_by_currency": "USD",
        "order_by": "price",
        "units": "imperial"
    }
    search_response = requests.get(search_url, headers=headers, params=search_params, timeout=10)
    
    if search_response.status_code == 200:
        hotels = search_response.json().get("result", [])
        filtered = [h for h in hotels if float(h.get("review_score", 0) or 0) >= 6.0 and float(h.get("class", 0) or 0) >= 3.0]
        print(f"    Total: {len(hotels)}, Filtered: {len(filtered)}")
        if filtered:
            for h in filtered[:2]:
                print(f"      - {h['name']}: ${h.get('price')}, {h.get('review_score')} review, {h.get('class')} stars")
    else:
        print(f"    Search failed: {search_response.status_code}")

print("\n" + "=" * 80)
