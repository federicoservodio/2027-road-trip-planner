import streamlit as st
import folium
from streamlit_folium import st_folium
from datetime import date, timedelta
import requests
import os
from dotenv import load_dotenv
import time
import json
from openai import OpenAI
import urllib.parse
import pandas as pd
import plotly.graph_objects as go
import math
from fpdf import FPDF
import io
from route_utils import build_route_selection, build_scenario_comparison, recommend_route_style, recommend_overnight_stop, recommend_toddler_break, recommend_activity_stop, recommend_lunch_break, recommend_diaper_break

# Load your secret key
load_dotenv()
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

if RAPIDAPI_KEY is None:
    raise RuntimeError("Missing RAPIDAPI_KEY environment variable. Add it to your .env file.")

# Initialize OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Family Road Trip Planner 🚗", layout="wide")

# ==============================================================================
# 🎨 HIGH-FIDELITY PREMIUM STYLING (CUSTOM CSS)
# ==============================================================================
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght=400;500;600;700&display=swap');
        html, body, [data-testid="stSidebar"] {
            font-family: 'Inter', sans-serif !important;
        }
        
        /* Modern Typography & Metrics */

        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: #1E3A8A !important;
            letter-spacing: -0.01em;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.9rem !important;
            font-weight: 500 !important;
            color: #475569 !important;
        }
        
        /* Premium Action Buttons */
        div.stButton > button[type="primary"] {
            background-color: #2563EB !important;
            border-color: #2563EB !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
            transition: all 0.2s ease;
        }
        
        /* Elevated Shadow Containers */
        div[data-testid="stContainer"] {
            border-radius: 12px !important;
            border: 1px solid #E2E8F0 !important;
            background-color: #FFFFFF !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
            padding: 20px !important;
            margin-bottom: 16px !important;
        }
        
        /* Custom Progress Card */
        .progress-card {
            background: linear-gradient(90deg, #F8FAFC 0%, #EFF6FF 100%);
            border: 1px solid #BFDBFE;
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# === Hotel price fetcher (moved outside CSS to avoid syntax errors) ===
def fetch_live_hotel_price(city, checkin_iso, checkout_iso, min_review_score=None, min_hotel_class=None, lat=None, lon=None):
    """Attempt to fetch a live hotel price; if external APIs are not available, return a deterministic fallback.

    Returns a dict with fields similar to earlier implementation.
    """
    rapidapi_host = os.getenv("RAPIDAPI_HOST")
    rapidapi_endpoint = os.getenv("RAPIDAPI_ENDPOINT")
    if RAPIDAPI_KEY and rapidapi_host:
        try:
            headers = {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": rapidapi_host,
            }

            if "booking-com" in rapidapi_host:
                loc_url = f"https://{rapidapi_host}/v1/hotels/locations"
                loc_params = {"name": city, "locale": "en-gb"}
                lo = requests.get(loc_url, headers=headers, params=loc_params, timeout=6)
                if lo.status_code == 200:
                    loc_data = lo.json()
                    if isinstance(loc_data, (list, tuple)) and len(loc_data) > 0:
                        first_loc = loc_data[0]
                        dest_id = first_loc.get("dest_id")
                        dest_type = first_loc.get("dest_type") or "city"

                        search_url = f"https://{rapidapi_host}/v1/hotels/search"
                        search_params = {
                            "dest_id": dest_id,
                            "dest_type": dest_type,
                            "locale": "en-gb",
                            "checkin_date": checkin_iso,
                            "checkout_date": checkout_iso,
                            "filter_by_currency": "GBP",
                            "units": "metric",
                            "room_number": 1,
                            "adults_number": 2,
                            "page_size": 3,
                            "order_by": "price",
                        }
                        resp = requests.get(search_url, headers=headers, params=search_params, timeout=8)
                        if resp.status_code == 200:
                            data = resp.json()
                            candidate = None
                            if isinstance(data, dict):
                                for key in ("result", "results", "search_results", "hotels", "data", "properties"):
                                    if key in data and isinstance(data[key], (list, tuple)) and len(data[key]) > 0:
                                        candidate = data[key][0]
                                        break
                            if candidate is None and isinstance(data, (list, tuple)) and len(data) > 0:
                                candidate = data[0]

                            if candidate:
                                name = candidate.get("hotel_name") or candidate.get("hotel_name_trans") or candidate.get("name") or candidate.get("title")
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
                                    comp = candidate.get("composite_price_breakdown") or {}
                                    gross = comp.get("gross_amount") or comp.get("all_inclusive_amount")
                                    if isinstance(gross, dict):
                                        v = gross.get("value")
                                        try:
                                            price = int(float(v))
                                        except Exception:
                                            price = None

                                review = candidate.get("review_score") or candidate.get("review_nr")
                                hotel_class = candidate.get("class") or candidate.get("class_is_estimated") or candidate.get("hotel_class") or candidate.get("stars")

                                if price is not None and name:
                                    return {
                                        "status": "success",
                                        "price": int(price),
                                        "name": name,
                                        "review_score": float(review) if review is not None else None,
                                        "hotel_class": float(hotel_class) if hotel_class is not None else None,
                                        "is_fallback": False,
                                        "raw": candidate,
                                    }

            else:
                endpoint = rapidapi_endpoint or "/v1/hotels/search"
                url = f"https://{rapidapi_host}{endpoint}"
                params = {
                    "checkin_date": checkin_iso,
                    "checkout_date": checkout_iso,
                    "currency": "GBP",
                    "locale": "en-gb",
                    "order_by": "price",
                    "page_size": 1,
                    "city_name": city,
                }
                if lat is not None and lon is not None:
                    params["latitude"] = lat
                    params["longitude"] = lon
                resp = requests.get(url, headers=headers, params=params, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    candidate = None
                    if isinstance(data, dict):
                        for key in ("result", "results", "search_results", "hotels", "data", "properties"):
                            if key in data and isinstance(data[key], (list, tuple)) and len(data[key]) > 0:
                                candidate = data[key][0]
                                break
                    if candidate is None and isinstance(data, list) and len(data) > 0:
                        candidate = data[0]
                    if candidate:
                        name = candidate.get("name") or candidate.get("hotel_name") or candidate.get("property_name") or candidate.get("title")
                        price = None
                        for pkey in ("price", "min_total_price", "min_price", "price_breakdown", "price_raw"):
                            if pkey in candidate:
                                val = candidate[pkey]
                                if isinstance(val, dict):
                                    price = val.get("amount") or val.get("value") or price
                                elif isinstance(val, (int, float, str)):
                                    try:
                                        price = int(float(val))
                                    except Exception:
                                        pass
                                if price is not None:
                                    break
                        review = candidate.get("review_score") or candidate.get("review") or candidate.get("rating")
                        hotel_class = candidate.get("class") or candidate.get("stars") or candidate.get("hotel_class")
                        if price is not None and name:
                            return {
                                "status": "success",
                                "price": int(price),
                                "name": name,
                                "review_score": float(review) if review is not None else None,
                                "hotel_class": float(hotel_class) if hotel_class is not None else None,
                                "is_fallback": False,
                            }

        except Exception:
            pass

    # Fallback
    try:
        base = 40
        hc = float(min_hotel_class) if min_hotel_class is not None else 3.0
        seed = abs(hash(city)) % 100
        price = int(base + hc * 25 + seed)
        name = f"{city} Lodge"
        review = round(6.5 + (seed % 35) / 10.0, 1)
        review = min(review, 9.9)

        return {
            "status": "success",
            "price": price,
            "name": name,
            "review_score": review,
            "hotel_class": hc,
            "is_fallback": True,
            "nearby_city": city,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# --- Geocoding helper for adding stops by name ---
def geocode_place(query):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        res = requests.get(url, params={"q": query, "format": "json", "limit": 1}, headers={"User-Agent": "road-trip-planner/1.0"}, timeout=6)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                return float(item.get("lat")), float(item.get("lon")), item.get("display_name")
    except Exception:
        pass
    return None

# Initialize state management keys
if "run_analysis" not in st.session_state:
    st.session_state.run_analysis = False
if "selected_leg_idx" not in st.session_state:
    st.session_state.selected_leg_idx = 0
if "last_map_click" not in st.session_state:
    st.session_state.last_map_click = None


def safe_rerun():
    """Attempt to programmatically rerun the Streamlit app across versions.

    If Streamlit exposes `experimental_rerun` or `rerun` we call it.
    Otherwise, set a session flag so the UI can indicate a manual refresh is needed and stop execution.
    """
    try:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
            return
        if hasattr(st, "rerun"):
            st.rerun()
            return
    except Exception:
        pass

    # Last-resort: ask user to refresh — store flag and stop execution cleanly
    st.session_state["_needs_manual_refresh"] = True
    try:
        st.stop()
    except Exception:
        # If even st.stop() is unavailable, raise a RuntimeError to avoid silent failure
        raise RuntimeError("Please refresh the page to see updated UI")

# Rough 2026 state-average gas prices ($/gal). AVG_US_GAS_PRICE is used for
# any state not listed here (e.g. Birmingham AL).
AVG_US_GAS_PRICE = 4.07
STATE_GAS_PRICES = {
    "GA": 3.78, "AL": 3.62, "TN": 3.66, "MO": 3.78, "NE": 3.80, "SD": 4.00,
    "WY": 4.25, "MT": 4.10, "UT": 4.34, "AZ": 4.46, "NV": 4.94, "CA": 5.78
}

# ==============================================================================
# ⚙️ SIDEBAR CONFIGURATION LAYOUT (GBP REWIRED)
# ==============================================================================
st.sidebar.markdown("## 🛠️ Trip Settings")
scenic_mode = st.sidebar.checkbox(
    "Bypass Highways (Scenic Mode)", 
    value=False, 
    help="Routes via state byways rather than interstate highways. This alters distance, duration, and fuel metrics mathematically."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 💰 Budget & Costs (£)")

st.sidebar.markdown("**🚗 Rental Vehicle**")
rental_rate = st.sidebar.number_input("Daily Rental Rate (£)", value=55.0)
one_way_fee = st.sidebar.number_input("One-Way Drop-off Fee (£)", value=275.0)
# Minivan class averages ~26 mpg; a hybrid Toyota Sienna gets ~36.
fuel_mpg = st.sidebar.number_input("Fuel economy (mpg)", value=26.0, help="Minivan class ~26 mpg; hybrid Toyota Sienna ~36 mpg.")

st.sidebar.markdown("**🏡 Lodging & Food**")
lodging_rate = st.sidebar.number_input("Nightly Lodging (£)", value=95.0, help="Blended average across the Airbnb/points/cash lodging plan.")
food_rate = st.sidebar.number_input("Daily Family Food Budget (£)", value=85.0)
min_review_score = st.sidebar.slider("Minimum Booking.com review score", 0.0, 10.0, 7.0, 0.1)
min_hotel_class = st.sidebar.slider("Minimum hotel star rating", 0.0, 5.0, 3.0, 0.5)

st.sidebar.markdown("**🎈 Activities & Contingency**")
activity_allowance = st.sidebar.number_input("Activity Budget Per Stop (£)", value=30.0)
buffer_percentage = st.sidebar.slider("Emergency Cushion Buffer (%)", 0, 25, 10)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📅 Trip Dates")
trip_start_date = st.sidebar.date_input("Trip Start Date", value=date(2027, 9, 6))
if st.sidebar.button("🧹 Clear Dashboard Cache", width='stretch'):
    st.session_state.run_analysis = False
    st.session_state.selected_leg_idx = 0
    st.session_state.last_map_click = None
    st.cache_data.clear()
    safe_rerun()

# ==============================================================================
# 🗺️ MAIN HEADER & WAYPOINTS CONFIGURATION
# ==============================================================================
st.markdown("# 🗺️ Family Road Trip Planner")
st.markdown("#### Travel Window: **Sept 6 – Oct 11, 2027**")
st.caption("Select any coordinate node on the map below to view local toddler recommendations and driving details for that specific leg.")

class Waypoint:
    def __init__(self, name, latitude, longitude, state, is_national_park=False):
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.state = state
        self.is_national_park = is_national_park

# Route synced with the "Revised Itinerary" tab of the trip spreadsheet
# (36 days, Sep 6 - Oct 11, 2027). Two-night stops get an entry in REST_DAYS.
route_list = [
    Waypoint("Atlanta, Georgia", 33.7501, -84.3885, "GA"),
    Waypoint("Birmingham, Alabama", 33.5207, -86.8025, "AL"),
    Waypoint("Memphis, Tennessee", 35.1486, -90.0519, "TN"),
    Waypoint("Springfield, Missouri", 37.2090, -93.2923, "MO"),
    Waypoint("Kansas City, Missouri", 39.0997, -94.5786, "MO"),
    Waypoint("Omaha, Nebraska", 41.2565, -95.9345, "NE"),
    Waypoint("Sioux Falls, South Dakota", 43.5476, -96.7294, "SD"),
    Waypoint("Pinnacles Overlook, Badlands SD", 43.8697, -102.2331, "SD", is_national_park=True),
    Waypoint("Mount Rushmore, SD", 43.8803, -103.4538, "SD"),
    Waypoint("Sheridan, Wyoming", 44.7972, -106.9562, "WY"),
    Waypoint("Cody, Wyoming", 44.5263, -109.0565, "WY"),
    Waypoint("West Yellowstone, Montana", 44.6632, -111.1012, "MT", is_national_park=True),
    Waypoint("Gardiner, Montana", 45.0351, -110.7127, "MT", is_national_park=True),
    Waypoint("Jackson, Wyoming", 43.4799, -110.7624, "WY", is_national_park=True),
    Waypoint("Salt Lake City, Utah", 40.7606, -111.8881, "UT"),
    Waypoint("Moab, Utah", 38.5738, -109.5462, "UT", is_national_park=True),
    Waypoint("Blanding, Utah", 37.6240, -109.4780, "UT"),
    Waypoint("Grand Canyon Village, AZ", 36.0544, -112.1401, "AZ", is_national_park=True),
    Waypoint("Kanab, Utah", 37.0475, -112.5263, "UT"),
    Waypoint("Springdale, Utah", 37.1945, -112.9570, "UT", is_national_park=True),
    Waypoint("Las Vegas, Nevada", 36.1716, -115.1391, "NV"),
    Waypoint("Furnace Creek (Death Valley), CA", 36.4344, -116.8628, "CA", is_national_park=True),
    Waypoint("Tehachapi, California", 35.1322, -118.4490, "CA"),
    Waypoint("General Sherman Tree, CA (Sequoia)", 36.5817, -118.7514, "CA", is_national_park=True),
    Waypoint("Yosemite Valley, CA", 37.7456, -119.5936, "CA", is_national_park=True),
    Waypoint("Lee Vining, California", 37.9628, -119.1207, "CA"),
    Waypoint("South Lake Tahoe, California", 38.9399, -119.9772, "CA"),
    Waypoint("Martinez, California", 38.0194, -122.1341, "CA")
]

all_route_list = route_list.copy()

# preserve any previously added custom stops (if present) so they remain selectable
if "custom_route_stops" in st.session_state:
    for custom_stop in st.session_state.custom_route_stops:
        all_route_list.append(
            Waypoint(
                custom_stop["name"],
                custom_stop["latitude"],
                custom_stop["longitude"],
                custom_stop.get("state", ""),
                custom_stop.get("is_national_park", False),
            )
        )

if "selected_route_names" not in st.session_state:
    st.session_state.selected_route_names = [wp.name for wp in all_route_list]

st.sidebar.markdown("---")
st.sidebar.markdown("### 🧭 Route Builder")

# Text input to add a stop (geocoded where possible)
new_stop_query = st.sidebar.text_input("Add stop by place name", value="", placeholder="e.g. Yosemite Valley or Bristol, UK")
if st.sidebar.button("Add Stop", key="add_stop_btn") and new_stop_query.strip():
    geo = geocode_place(new_stop_query.strip())
    if geo:
        lat, lon, display = geo
        name = display or new_stop_query.strip()
        wp = Waypoint(name, lat, lon, "", False)
        if "custom_route_stops" not in st.session_state:
            st.session_state.custom_route_stops = []
        st.session_state.custom_route_stops.append({"name": name, "latitude": lat, "longitude": lon, "state": "", "is_national_park": False})
        all_route_list.append(wp)
        cur = st.session_state.get("selected_route_names", [wp.name for wp in all_route_list])
        if name not in cur:
            cur.append(name)
        st.session_state.selected_route_names = cur
        safe_rerun()
    else:
        st.sidebar.warning("Could not geocode place. Try a different query.")

selected_route_names = st.sidebar.multiselect(
    "Select stops to include",
    options=[wp.name for wp in all_route_list],
    key="selected_route_names",
    help="Choose which stopovers stay in the itinerary. Drag to reorder below.",
)

if selected_route_names != st.session_state.get("_selected_route_names_prev", None):
    st.session_state.run_analysis = False
    st.session_state.selected_leg_idx = 0
    st.session_state.last_map_click = None
    st.session_state._selected_route_names_prev = selected_route_names

# Ensure session state's selected list is authoritative; fall back to the local widget value
if "selected_route_names" in st.session_state:
    selected_route_names = st.session_state.selected_route_names

st.sidebar.markdown("---")

# Provide Up/Down reorder controls directly under the multiselect as a reliable fallback
if st.session_state.get('selected_route_names'):
    st.sidebar.markdown(f"{len(st.session_state['selected_route_names'])} stops selected")
    move_choice = None
    try:
        move_choice = st.sidebar.selectbox("Select stop to move", options=st.session_state['selected_route_names'], key='move_choice')
    except Exception:
        move_choice = None

    def _move_up_cb():
        mc = st.session_state.get('move_choice')
        lst = st.session_state.get('selected_route_names', [])[:]
        if mc in lst:
            idx = lst.index(mc)
            if idx > 0:
                lst[idx], lst[idx-1] = lst[idx-1], lst[idx]
                st.session_state['selected_route_names'] = lst
                st.session_state['move_choice'] = mc
                safe_rerun()

    def _move_down_cb():
        mc = st.session_state.get('move_choice')
        lst = st.session_state.get('selected_route_names', [])[:]
        if mc in lst:
            idx = lst.index(mc)
            if idx < len(lst)-1:
                lst[idx], lst[idx+1] = lst[idx+1], lst[idx]
                st.session_state['selected_route_names'] = lst
                st.session_state['move_choice'] = mc
                safe_rerun()

    col1, col2 = st.sidebar.columns(2)
    col1.button("Move Up", on_click=_move_up_cb)
    col2.button("Move Down", on_click=_move_down_cb)

route_list = build_route_selection(all_route_list, selected_route_names)

if len(route_list) < 2:
    st.sidebar.warning("Choose at least two stops to build a route.")
else:
    st.sidebar.caption(f"{len(route_list)} stops selected")

# Extra rest days per stop. NOTE: names here must match route_list entries EXACTLY
# (exact string match) or the rest day silently won't apply.
# Each value = 1 extra night, turning the stop into a two-night stay.
# Synced with the "Revised Itinerary" tab: Atlanta (arrival + jet-lag day),
# Memphis, Kansas City, Cody, Jackson, Grand Canyon (South Rim), Yosemite, Lake Tahoe.
REST_DAYS = {
    "Atlanta, Georgia": 1,
    "Memphis, Tennessee": 1,
    "Kansas City, Missouri": 1,
    "Cody, Wyoming": 1,
    "Jackson, Wyoming": 1,
    "Grand Canyon Village, AZ": 1,
    "Yosemite Valley, CA": 1,
    "South Lake Tahoe, California": 1,
}

def generate_pdf_itinerary(rows, grand_total):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Family Road Trip Itinerary", ln=True, align='C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, txt=f"Estimated Total Budget: £{grand_total:,.2f}", ln=True, align='C')
    pdf.ln(10)
    
    for row in rows:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 8, txt=f"Leg {row['Leg']}: {row['Route Stretch']}", ln=True)
        
        pdf.set_font("Arial", '', 10)
        pdf.cell(200, 6, txt=f"Start Date: {row['Start Date']} | Check-in: {row['Check-in Date'][:10]}", ln=True)
        pdf.cell(200, 6, txt=f"Distance: {row['Distance']} | Driving Time: {row['Driving Time']}", ln=True)
        pdf.cell(200, 6, txt=f"Pace: {row['Pace & Status']}", ln=True)
        pdf.ln(5)
        
    pdf_output = pdf.output(dest="S")
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin-1')
    if isinstance(pdf_output, bytearray):
        return bytes(pdf_output)
    return pdf_output

def render_google_maps_export(waypoints):
    if len(waypoints) < 2:
        return
    MAX_STOPS = 10
    STEP = MAX_STOPS - 1
    st.markdown("### 🗺️ Export Routes to Google Maps")
    for leg_num, start_idx in enumerate(range(0, len(waypoints) - 1, STEP), start=1):
        chunk = waypoints[start_idx:start_idx + MAX_STOPS]
        origin = chunk[0]
        destination = chunk[-1]
        maps_url = f"https://www.google.com/maps/dir/?api=1&origin={origin.latitude},{origin.longitude}&destination={destination.latitude},{destination.longitude}&travelmode=driving"
        if len(chunk) > 2:
            intermediate_stops = [f"{wp.latitude},{wp.longitude}" for wp in chunk[1:-1]]
            maps_url += "&waypoints=" + urllib.parse.quote("|".join(intermediate_stops))
        st.link_button(f"🚗 Open Route Segment {leg_num} ({origin.state} ➔ {destination.state})", maps_url, width='stretch')

# ==============================================================================
# 🔄 CACHED BACKEND UTILITY FUNCTIONS
# ==============================================================================
@st.cache_data
def get_cached_distance(o_name, o_lat, o_lon, d_name, d_lat, d_lon, scenic_mode_active):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{o_lon},{o_lat};{d_lon},{d_lat}?overview=false"
        res = requests.get(url, timeout=5).json()
        if res.get("code") == "Ok":
            base_miles = res["routes"][0]["distance"] * 0.000621371
            base_hours = res["routes"][0]["duration"] / 3600
            
            if scenic_mode_active:
                base_miles *= 1.15
                base_hours *= 1.35
                
            return round(base_miles, 1), round(base_hours, 1)
    except Exception:
        pass
    
    default_miles = 230.0 if scenic_mode_active else 200.0
    default_hours = 4.0 if scenic_mode_active else 3.0
    return default_miles, default_hours

@st.cache_data
def get_detailed_route_track(o_lat, o_lon, d_lat, d_lon, scenic_mode_active):
    """Fetches high-fidelity road geometry from OSRM and switches to alternative pathways if scenic."""
    try:
        # Request full overview geometry and alternative options from the engine
        url = f"http://router.project-osrm.org/route/v1/driving/{o_lon},{o_lat};{d_lon},{d_lat}?overview=full&geometries=geojson&alternatives=true"
        res = requests.get(url, timeout=5).json()
        
        if res.get("code") == "Ok":
            routes = res.get("routes", [])
            # If scenic mode is on and a secondary highway/byway alternative exists, grab it
            if scenic_mode_active and len(routes) > 1:
                coords = routes[1]["geometry"]["coordinates"]
            elif len(routes) > 0:
                coords = routes[0]["geometry"]["coordinates"]
            else:
                return [[o_lat, o_lon], [d_lat, d_lon]]
            
            # OSRM serves [longitude, latitude], Folium requires [latitude, longitude]
            return [[point[1], point[0]] for point in coords]
    except Exception:
        pass
    # Fallback to straight line if API times out
    return [[o_lat, o_lon], [d_lat, d_lon]]

@st.cache_data
def calculate_approx_daylight(latitude, day_of_year=260):
    p = math.asin(0.39795 * math.cos(0.2163108 + 2 * math.asin(0.39795 * math.sin(2 * math.pi * (day_of_year - 80) / 365))))
    daylight_denom = math.cos(latitude * math.pi / 180) * math.cos(p)
    if daylight_denom == 0:
        return 12.0
    val = (-0.01454 - math.sin(latitude * math.pi / 180) * math.sin(p)) / daylight_denom
    val = max(-1.0, min(1.0, val))
    return round(24 - (24 / math.pi) * math.acos(val), 1)

@st.cache_data(show_spinner=False)
def get_cached_location_insights(city_name, scenic_mode_active):
    scenic_context = "Scenic detour parameters are prioritized." if scenic_mode_active else ""
    optimized_prompt = f"""
    You are an expert family travel concierge. Provide a local, actionable field guide for {city_name} 
    optimized for parents traveling with a 2-year-old toddler on an affordable budget. {scenic_context}
    Format the output using clear Markdown headers with clean iconography. Provide exactly 2-3 specific recommendations for each section:

    ### 🏃‍♂️ Free Areas for Toddler Activity
    (List real fenced-in playgrounds, splash pads, or walking paths in {city_name} where a 2-year-old can safely play for free.)

    ### 🍕 Toddler-Tolerant Value Dining
    (List real casual local restaurants or pizza patios in {city_name} that feature quick service, an environment suitable for families, and meals under £15 per person.)

    ### 🏨 Affordable Basecamp Alternatives
    (If {city_name} is expensive, name a specific town 20-30 minutes away where lodging options are more economical. If it's already affordable, explain why.)
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a travel assistant specialized in family-friendly trip logistics."},
                {"role": "user", "content": optimized_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ **AI Concierge Error:** Unable to retrieve location details."

@st.cache_data(show_spinner=False)
def get_cached_seasonal_hazards(o_name, d_name, current_date_str):
    prompt = f"Analyze high-altitude weather risks, pass closures, or seasonal hazards between {o_name} and {d_name} for {current_date_str}, 2027. Focus on autumn weather transitions or mountain passes. Provide 2 bullet points. If clear, state 'Passes clear'."
    try:
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.3)
        return response.choices[0].message.content
    except:
        return "Verify conditions via local state DOT portals."

@st.cache_data(show_spinner=False)
def get_cached_park_rules(park_name, date_str):
    prompt = f"Identify entry parameters or reservation updates for {park_name} on {date_str}, 2027. Provide 2 concise bullets."
    try:
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], temperature=0.2)
        return response.choices[0].message.content
    except:
        return "Standard park entry and pass rules apply."

@st.cache_data(show_spinner=False)
def get_cached_scenic_alignment(o_name, d_name):
    prompt = f"Identify official names of scenic byways or route numbers between {o_name} and {d_name}. Limit to two sentences."
    try:
        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content
    except:
        return "Scenic alternative routes map parallel to the primary highway."

@st.cache_data(show_spinner=False)
def get_cached_ai_overnight_fix(o_name, d_name, hours):
    prompt = f"""
    You are a strict routing assistant. I am driving directly from {o_name} to {d_name} ({hours} hours) with a 2-year-old. 
    Identify the primary interstate or highway connecting them. 
    Then, suggest a midway town that is physically located directly on that exact highway route. Do not suggest towns that require a detour. 
    Provide 1 hotel option and 1 toddler-friendly park/playground in that specific midway town. Keep the response concise.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        return response.choices[0].message.content
    except Exception:
        return "Intermediate overnight stop recommended along the primary highway."

@st.cache_data(show_spinner=False)
def get_cached_ai_midday_break(o_name, d_name, hours):
    prompt = f"""
    You are a strict routing assistant. I am driving directly from {o_name} to {d_name} ({hours} hours) with a 2-year-old. 
    Identify the primary interstate or highway connecting them. 
    Then, suggest a midway town for a lunch break that is physically located directly on that exact highway route. Do not suggest towns that require a detour. 
    Suggest 1 quick casual restaurant and 1 playground. Keep the response concise.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        return response.choices[0].message.content
    except Exception:
        return "Midday break recommended along the primary highway."

@st.cache_data(show_spinner=False)
def get_historical_weather_proxy(lat, lon, target_date_str):
    try:
        target_date = date.fromisoformat(target_date_str) if isinstance(target_date_str, str) else target_date_str
        proxy_year = target_date.year - 4
        proxy_date = date(proxy_year, target_date.month, target_date.day).isoformat()
        
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={proxy_date}&end_date={proxy_date}&daily=temperature_2m_max,temperature_2m_min&timezone=auto&temperature_unit=fahrenheit"
        res = requests.get(url, timeout=5).json()
        
        if "daily" in res:
            high = round(res["daily"]["temperature_2m_max"][0])
            low = round(res["daily"]["temperature_2m_min"][0])
            return f"🌡️ **Expected Climate:** High of **{high}°F** / Low of **{low}°F** *(Based on historical data for this exact week)*"
    except Exception:
        pass
    return "🌡️ Expected Climate: Data temporarily unavailable."

@st.cache_data(show_spinner=False)
def get_cached_safety_alerts(city_name):
    """Uses OpenAI to provide objective travel safety metrics and local precautions."""
    prompt = f"""
    You are an expert travel safety analyst. Provide a brief, objective safety advisory for a family road-tripping to or through {city_name}.
    Include the following structured sections using clear markdown:
    
    - **General Safety Level:** (e.g., Safe, Moderate Caution, High Caution)
    - **Areas/Neighborhoods to Avoid or Use Caution:** Mention specific districts, neighborhoods, or transit hubs where property crime or safety issues are higher, particularly after dark.
    - **Vehicle & Parking Tips:** Provide advice on preventing vehicle break-ins (especially common for packed road-trip cars in this city).
    
    Keep the tone factual, reassuring but realistic, and tailored to a family traveling with a young child. Do not use generic fluff.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return f"⚠️ Safety data temporarily unavailable for {city_name}."

# ==============================================================================
# 🗺️ FULL-WIDTH PROMINENT MAP INTERFACE
# ==============================================================================
m = folium.Map(
    location=[39.8283, -98.5795], tiles="CartoDB positron", zoom_start=4,
    zoom_control=False, dragging=True, scrollWheelZoom=False,
    doubleClickZoom=False, boxZoom=False, touchZoom=True, control_scale=False
)

# Set up raw bounding boxes based on destination nodes
waypoint_coords = [[wp.latitude, wp.longitude] for wp in route_list]
m.fit_bounds(waypoint_coords)

active_leg_idx = st.session_state.selected_leg_idx

# Stitch together actual street/highway coordinate tracks for each leg
# To avoid long startup delays from many remote OSRM calls, only fetch
# the detailed route geometry for the active leg and its immediate neighbors.
for i in range(len(route_list) - 1):
    orig, dest = route_list[i], route_list[i+1]

    # Only perform the potentially slow OSRM call for the active leg and nearby legs.
    if abs(i - active_leg_idx) <= 1:
        leg_track = get_detailed_route_track(orig.latitude, orig.longitude, dest.latitude, dest.longitude, scenic_mode)
    else:
        # Fast fallback: straight-line between nodes (instant)
        leg_track = [[orig.latitude, orig.longitude], [dest.latitude, dest.longitude]]

    if i == active_leg_idx:
        folium.PolyLine(
            locations=leg_track,
            color="#4F46E5",
            weight=6,
            opacity=1.0,
            z_index=999,
        ).add_to(m)
    else:
        color = "#10B981" if scenic_mode else "#2563EB"
        dash_array = "4, 6" if scenic_mode else None
        folium.PolyLine(
            locations=leg_track,
            color=color,
            weight=3,
            opacity=0.75,
            dash_array=dash_array,
        ).add_to(m)

# Plot the destination waypoint nodes
for idx, wp in enumerate(route_list):
    border_color, fill_color, radius = ("#0F766E", "#2DD4BF", 7) if wp.is_national_park else ("#1E3A8A", "#60A5FA", 5)
    folium.CircleMarker(
        location=[wp.latitude, wp.longitude], radius=radius, color=border_color, weight=1.5,
        fill=True, fill_color=fill_color, fill_opacity=0.95,
        popup=folium.Popup(f"<div style='font-family:sans-serif; font-size:12px;'><b>{wp.name}</b></div>", max_width=200)
    ).add_to(m)

# Map key updates cleanly based on the chosen mode
map_data = st_folium(m, width="100%", height=460, key=f"master_trip_map_{scenic_mode}")

if map_data and map_data.get("last_object_clicked"):
    click_coords = map_data["last_object_clicked"]
    if click_coords != st.session_state.last_map_click:
        st.session_state.last_map_click = click_coords
        lat, lon = click_coords.get("lat"), click_coords.get("lng")
        for idx, wp in enumerate(route_list):
            if abs(wp.latitude - lat) < 0.005 and abs(wp.longitude - lon) < 0.005:
                st.session_state.selected_leg_idx = max(0, idx - 1)
                safe_rerun()

# ==============================================================================
# 📈 VISUAL ROUTE PROGRESS TRACKER COMPONENT
# ==============================================================================
total_legs_count = len(route_list) - 1
active_leg = st.session_state.selected_leg_idx
progress_percent = (active_leg / total_legs_count)

st.markdown(f"""
    <div class="progress-card">
        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 600; color: #334155; margin-bottom: 4px;">
            <span>Route Progress: Leg {active_leg + 1} of {total_legs_count}</span>
            <span>{int(progress_percent * 100)}% Complete</span>
        </div>
    </div>
""", unsafe_allow_html=True)
st.progress(progress_percent)

with st.expander("🔗 Mobile GPS Navigation Links", expanded=False):
    render_google_maps_export(route_list)

st.write("---")

# ==============================================================================
# 🖥️ SIDE-BY-SIDE ANALYTICS & DASHBOARD LAYOUT UNDERNEATH MAP
# ==============================================================================
col1, col2 = st.columns([1.4, 1.6], gap="large")

with col1:
    st.markdown("### 📊 Financial & Route Analytics")
    metrics_container = st.empty()
    chart_placeholder = st.empty()
    sniper_placeholder = st.empty()
    
    if not st.session_state.run_analysis:
        st.info("Select 'Calculate Trip Timeline' to populate cost matrices and distance analytics.")

with col2:
    st.markdown("### ✨ Trip Dashboard")
    if st.button("Calculate Trip Timeline", type="primary", width='stretch'):
        st.session_state.run_analysis = True

    if st.session_state.run_analysis:
        total_miles, total_fuel, np_count = 0.0, 0.0, 0
        start_date = trip_start_date
        # Reserve the first night at the origin city; begin driving the following day
        # Day 1 = arrival night at the origin (no driving). Each leg is then
        # driven the morning after the current night, with same-day check-in at
        # the destination; rest days add extra nights BEFORE moving on.
        current_date = start_date

        # Rest days at the origin itself (e.g. Atlanta jet-lag day) come first
        origin_rest_days = REST_DAYS.get(route_list[0].name, 0)
        current_date += timedelta(days=origin_rest_days)

        itinerary_rows = []

        for i in range(len(route_list) - 1):
            orig, dest = route_list[i], route_list[i+1]
            miles, hours = get_cached_distance(orig.name, orig.latitude, orig.longitude, dest.name, dest.latitude, dest.longitude, scenic_mode)

            # Rough proxy calculation adjusted into GBP metrics
            avg_price_for_leg = ((STATE_GAS_PRICES.get(orig.state, AVG_US_GAS_PRICE) + STATE_GAS_PRICES.get(dest.state, AVG_US_GAS_PRICE)) / 2.0) * 0.79
            total_fuel += (miles / fuel_mpg) * avg_price_for_leg
            total_miles += miles
            if dest.is_national_park: np_count += 1

            # Drive this leg the morning after the current night; arrive same day
            current_date += timedelta(days=1)
            date_label = current_date.strftime("%b %d")
            drive_status = "Split Drive (Exceeds single nap window)" if hours > 5 else ("Steady Drive" if hours > 3.0 else "Short Stretch")

            # arrival_date is the check-in date (record it before applying rest days)
            arrival_date = current_date
            rest_days_count = REST_DAYS.get(dest.name, 0)
            if rest_days_count > 0:
                drive_status += f" + Extended Stay ({rest_days_count}d)"
                current_date += timedelta(days=rest_days_count)

            itinerary_rows.append({
                "Leg": f"#{i+1}", 
                "Start Date": date_label, 
                "Check-in Date": arrival_date.isoformat(),
                "Day of Year": arrival_date.timetuple().tm_yday,
                "Route Stretch": f"{orig.name} -> {dest.name}",
                "Distance": f"{miles:,.1f} mi", 
                "Driving Time": f"{hours:.1f} hrs", 
                "Pace & Status": drive_status,
                "Rest Days": rest_days_count
            })

        total_days = max(1, (current_date - start_date).days)
        subtotal_rental = (total_days * rental_rate) + one_way_fee
        subtotal_lodging = total_days * lodging_rate
        subtotal_food = total_days * food_rate
        subtotal_activities = len(route_list) * activity_allowance
        subtotal_parks = (80.0 if (np_count * 35.0) > 80.0 else (np_count * 35.0)) * 0.79

        calculated_subtotal = subtotal_rental + total_fuel + subtotal_lodging + subtotal_food + subtotal_activities + subtotal_parks
        buffer_amount = calculated_subtotal * (buffer_percentage / 100.0)
        grand_total = calculated_subtotal + buffer_amount

        # Populate Analytics Metrics Container
        with metrics_container.container(border=True):
            st.caption(f"🗓️ Duration: {total_days} Days | Estimated Completion: {current_date.strftime('%b %d, %Y')}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Estimated Total Cost", f"£{grand_total:,.2f}")
            m2.metric("Average Daily Cost", f"£{(grand_total / total_days):,.2f}")
            m3.metric("Total Distance", f"{total_miles:,.1f} miles")

            scenario_summary = build_scenario_comparison(route_list, lambda o_name, o_lat, o_lon, d_name, d_lat, d_lon, scenic_mode_active: get_cached_distance(o_name, o_lat, o_lon, d_name, d_lat, d_lon, scenic_mode_active))
            recommendation = recommend_route_style(scenario_summary, budget_tolerance=max(1000.0, grand_total * 0.8))
            leg_hours = [
                get_cached_distance(
                    route_list[idx].name,
                    route_list[idx].latitude,
                    route_list[idx].longitude,
                    route_list[idx + 1].name,
                    route_list[idx + 1].latitude,
                    route_list[idx + 1].longitude,
                    scenic_mode,
                )[1]
                for idx in range(len(route_list) - 1)
            ]
            overnight_stop = recommend_overnight_stop(route_list, leg_hours)
            toddler_break = recommend_toddler_break(route_list)
            activity_stop = recommend_activity_stop(route_list)
            lunch_break = recommend_lunch_break(route_list)
            diaper_break = recommend_diaper_break(route_list)
            st.markdown("#### 🔄 Scenario Comparison")
            comp_col1, comp_col2 = st.columns(2)
            with comp_col1:
                st.metric("Fast Route", f"{scenario_summary['Fast']['miles']:,.1f} mi", f"{scenario_summary['Fast']['hours']:,.1f} hrs")
            with comp_col2:
                st.metric("Scenic Route", f"{scenario_summary['Scenic']['miles']:,.1f} mi", f"{scenario_summary['Scenic']['hours']:,.1f} hrs")

            st.info(f"💡 Best fit for this trip: **{recommendation['recommendation']}** — {recommendation['reason']}")
            if overnight_stop:
                st.success(f"🛏️ Suggested overnight break: **{overnight_stop}**")
            if toddler_break:
                st.success(f"🧒 Suggested toddler-friendly pause: **{toddler_break}**")
            if activity_stop:
                st.success(f"🌲 Suggested activity stop: **{activity_stop}**")
            if lunch_break:
                st.success(f"🍽️ Suggested lunch break: **{lunch_break}**")
            if diaper_break:
                st.success(f"👶 Suggested diaper/stretch reset: **{diaper_break}**")

        # ==============================================================================
        # 📊 PLOTLY CHART
        # ==============================================================================
        with chart_placeholder.container(border=True):
            st.markdown("#### Cost Allocation Breakdown (£)")
            labels = ['Vehicle Rental', 'Fuel (Indexed)', 'Lodging', 'Food & Provisions', 'Activities', 'Park Admissions', 'Emergency Buffer']
            values = [subtotal_rental, total_fuel, subtotal_lodging, subtotal_food, subtotal_activities, subtotal_parks, buffer_amount]
            colors = ['#1E3A8A', '#2563EB', '#3B82F6', '#60A5FA', '#93C5FD', '#0F766E', '#94A3B8']
            
            fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.45, marker=dict(colors=colors), hoverinfo="label+value+percent", textinfo="percent")])
            fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5), margin=dict(t=10, b=10, l=10, r=10), height=320)
            st.plotly_chart(fig, width='stretch')

        # ==============================================================================
        # 📥 EXPORT ITINERARY
        # ==============================================================================
        st.markdown("<br>", unsafe_allow_html=True)
        pdf_bytes = generate_pdf_itinerary(itinerary_rows, grand_total)
        st.download_button(
            label="📥 Download PDF Itinerary",
            data=pdf_bytes,
            file_name="Family_Road_Trip_2027.pdf",
            mime="application/pdf",
            width='stretch'
        )

        # ==============================================================================
        # 🎯 LODGING PRICE SNIPER (GBP FORMATTED)
        # ==============================================================================
        with sniper_placeholder.container():
            st.markdown("### 🎯 Lodging Price Sniper")

            def handle_search(city, date_str, lat=None, lon=None):
                with st.spinner(f"Sniping prices for {city}..."):
                    checkin_date = date.fromisoformat(date_str)
                    checkout_date = (checkin_date + timedelta(days=1)).isoformat()
                    result = fetch_live_hotel_price(
                        city,
                        checkin_date.isoformat(),
                        checkout_date,
                        min_review_score,
                        min_hotel_class,
                        lat,
                        lon
                    )
                    if result["status"] == "success":
                        tags = []
                        if result.get("review_score") is not None:
                            tags.append(f"{result['review_score']:.1f} review")
                        if result.get("hotel_class") is not None:
                            tags.append(f"{result['hotel_class']:.1f}-star")
                        tag_text = f" ({', '.join(tags)})" if tags else ""
                        
                        if result.get("is_fallback"):
                            nearby = result.get("nearby_city", "nearby area")
                            st.info(f"No filtered options at {city}. Nearby alternative: £{result['price']:,} at {result['name']} in {nearby}{tag_text}")
                        else:
                            st.success(f"Best Rate: £{result['price']:,} at {result['name']}{tag_text}")
                    else:
                        st.error(f"Could not fetch price. {result.get('message', 'Check API status.')}")

            if itinerary_rows:
                # Offer a lodging check for the starting night at the origin
                origin = route_list[0]
                start_checkin_label = start_date.strftime("%b %d, %Y")
                with st.container(border=True):
                    s1, s2 = st.columns([3, 1])
                    with s1:
                        st.markdown(f"**Starting Night: {origin.name}**\n\nCheck-in: {start_checkin_label}")
                    with s2:
                        if st.button("Check Price", key="price_btn_start"):
                            handle_search(origin.name, start_date.isoformat(), origin.latitude, origin.longitude)
                for idx, row in enumerate(itinerary_rows):
                    dest = route_list[idx + 1]
                    destination_label = dest.name
                    checkin_label = date.fromisoformat(row["Check-in Date"]).strftime("%b %d, %Y")

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([1.2, 2, 1])
                        with c1:
                            if dest.is_national_park:
                                st.error("🚨 **Park**")
                            else:
                                st.success("✅ **Stop**")
                        with c2:
                            st.markdown(f"**{destination_label}**\n\nCheck-in: {checkin_label}")
                            if row.get("Rest Days", 0) > 0:
                                st.markdown(f"**🛌 Rest Day: {row['Rest Days']} day(s)**")
                        with c3:
                            if st.button("Check Price", key=f"price_btn_{idx}"):
                                handle_search(destination_label, row["Check-in Date"], dest.latitude, dest.longitude)
            else:
                st.info("Run analysis to generate itinerary dates before checking lodging prices.")

    # ==============================================================================
    # 🎯 STRUCTURALLY UPGRADED DEEP-DIVE INTERFACE (EXPANDERS FIXED)
    # ==============================================================================
    if st.session_state.get("run_analysis", False) and 'itinerary_rows' in locals():   
        leg_idx = st.session_state.selected_leg_idx
        orig, dest = route_list[leg_idx], route_list[leg_idx + 1]
        active_schedule = itinerary_rows[leg_idx]
        
        st.markdown(f"## 📍 Driving Leg Details (#{leg_idx+1})")
        st.markdown(f"### From **{orig.name}** to **{dest.name}**")
        
        btn_col1, btn_col2 = st.columns(2)
        if btn_col1.button("⬅️ Previous Leg", disabled=(leg_idx == 0), width='stretch'):
            st.session_state.selected_leg_idx -= 1
            safe_rerun()
        if btn_col2.button("Next Leg ➡️", disabled=(leg_idx >= len(route_list) - 2), width='stretch'):
            st.session_state.selected_leg_idx += 1
            safe_rerun()
            
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**📅 Date**\n\n{active_schedule['Start Date']}, 2027")
            c2.markdown(f"**🚗 Distance & Time**\n\n{active_schedule['Distance']} ({active_schedule['Driving Time']})")
            c3.markdown(f"**⏱️ Driving Pace**\n\n{active_schedule['Pace & Status']}")

        # 🏡 1. DESTINATION GUIDE RENDERED PROMINENTLY FIRST
        with st.container(border=True):
            st.markdown(f"## 🏡 Destination Guide: {dest.name}")
            local_insights = get_cached_location_insights(dest.name, scenic_mode)
            st.markdown(local_insights)

        # ☀️ EXPANDER A: Daylight Window (Closed by Default)
        with st.expander("☀️ Active Seasonal Daylight Window", expanded=False):
            target_yday = active_schedule.get("Day of Year", 260)
            daylight_hours = calculate_approx_daylight(dest.latitude, target_yday)
            st.markdown(f"This region will experience approximately **{daylight_hours} hours** of daylight on {active_schedule['Start Date']}. Planning departures early guarantees all driving happens within comfortable daylight windows to optimize toddler comfort.")

        # ❄️ EXPANDER B: Weather Alerts (Closed by Default)
        with st.expander("❄️ Weather & Environmental Alerts", expanded=False):
            climate_data = get_historical_weather_proxy(dest.latitude, dest.longitude, active_schedule['Check-in Date'][:10])
            st.info(climate_data)
            hazard_alerts = get_cached_seasonal_hazards(orig.name, dest.name, active_schedule['Start Date'])
            st.markdown(hazard_alerts)

       # 👶 EXPANDER C: Toddler & Routing Constraints (Closed by Default)
        with st.expander("👶 Toddler Routing & Rest Constraints", expanded=False):
            h_time = float(active_schedule['Driving Time'].split()[0])
            
            # ==================================================================
            # ⏰ TODDLER-OPTIMIZED DEPARTURE SCHEDULER
            # ==================================================================
            if h_time <= 3.0:
                start_time_tip = "⏰ **Recommended Departure:** **8:30 AM** *(arrive by lunch)* OR **1:00 PM** *(syncs perfectly with their afternoon nap window)*."
            elif h_time <= 7.0:
                start_time_tip = f"⏰ **Recommended Departure:** **8:00 AM**. This splits the {h_time} hr drive cleanly around a midday meal/playground break and gets you checked in before the pre-dinner meltdown zone."
            else:
                start_time_tip = f"⏰ **Recommended Departure:** **6:30 AM – 7:00 AM**. Marathon drives require wheels moving while energy is high, leaving plenty of cushion for decompression stops."
            
            st.info(start_time_tip)
            st.markdown("---")

            # ==================================================================
            # ROUTING & REST BREAK LOGIC
            # ==================================================================
            if scenic_mode:
                st.markdown("##### 🌿 Scenic Route Alternative Byways")
                scenic_info = get_cached_scenic_alignment(orig.name, dest.name)
                st.caption(scenic_info)
                st.markdown("---")

            if orig.is_national_park or dest.is_national_park:
                target_park = dest.name if dest.is_national_park else orig.name
                st.markdown(f"##### 🏞️ National Park Entry Requirements: {target_park}")
                park_rules = get_cached_park_rules(target_park, active_schedule['Start Date'])
                st.markdown(park_rules)
                st.markdown("---")
                
            if h_time > 7.0:
                overnight_guide = get_cached_ai_overnight_fix(orig.name, dest.name, h_time)
                st.markdown(overnight_guide)
            elif h_time > 3.0:
                midday_guide = get_cached_ai_midday_break(orig.name, dest.name, h_time)
                st.markdown(midday_guide)
            else:
                st.markdown("This drive fits within a standard single-nap window. No intermediate stops are required.")

        # ⚠️ EXPANDER D: Safety Awareness Guide (Closed by Default)
        with st.expander("⚠️ Safety & Awareness Guide", expanded=False):
            st.warning(
                "ℹ️ **Road Trip Intelligence:** Packed vehicles with out-of-state license plates are natural targets for opportunistic property crime. Always secure valuables."
            )
            safety_info = get_cached_safety_alerts(dest.name)
            st.markdown(safety_info)
    else:
        st.info("👆 Click 'Calculate Trip Timeline' above to unlock the Deep-Dive Route Interface!")