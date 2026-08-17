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

# Load secret keys
load_dotenv()
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

if RAPIDAPI_KEY is None:
    raise RuntimeError("Missing RAPIDAPI_KEY environment variable. Add it to your .env file.")

# Initialize OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="2027 Road Trip Planner", page_icon="🚗", layout="centered", initial_sidebar_state="collapsed")

# ==============================================================================
# 🎨 MOBILE-FIRST STYLING
# ==============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="st-"] { font-family: 'Inter', system-ui, -apple-system, sans-serif; }

/* Tighten default Streamlit padding */
.block-container { padding-top: 0.8rem !important; padding-bottom: 1rem !important; }
[data-testid="stHeader"] { height: 0.5rem; }
header[data-testid="stHeader"] { background: transparent; }

/* Sticky trip header */
.sticky-header {
  position: sticky; top: -0.5rem; z-index: 999;
  background: #ffffffee; backdrop-filter: blur(6px);
  border-bottom: 1px solid #e2e8f0; padding: 8px 12px; margin: -8px -12px 12px -12px;
  font-size: 0.88rem; font-weight: 600; color: #1e293b;
}
.sticky-header small { font-weight: 500; color: #475569; }

/* Metric tweaks */
[data-testid="stMetricValue"] { font-size: 1.35rem !important; font-weight: 700 !important; color: #1E3A8A !important; }
[data-testid="stMetricLabel"] { font-size: 0.82rem !important; font-weight: 500 !important; color:#475569 !important; }

/* Make tables horizontally scrollable */
[data-testid="stDataFrame"] { overflow-x: auto; }

/* Tighter containers on mobile */
div[data-testid="stContainer"] { border-radius: 12px !important; border:1px solid #e2e8f0 !important; background:#fff !important;}

/* Tabs bigger tap targets */
button[data-baseweb="tab"] { font-size: 0.95rem !important; padding: 10px 12px !important; }

/* Expanders */
details summary { font-size: 0.96rem !important; }

/* Mobile media query */
@media (max-width: 600px){
  .block-container { padding-left: 0.9rem !important; padding-right: 0.9rem !important; }
  h1 { font-size: 1.45rem !important; }
  h2 { font-size: 1.18rem !important; }
  h3 { font-size: 1.02rem !important; }
  [data-testid="stMetricValue"] { font-size: 1.15rem !important; }
}
</style>
""", unsafe_allow_html=True)

# === Hotel price fetcher ===
def fetch_live_hotel_price(city, checkin_iso, checkout_iso, min_review_score=None, min_hotel_class=None, lat=None, lon=None):
    rapidapi_host = os.getenv("RAPIDAPI_HOST")
    rapidapi_endpoint = os.getenv("RAPIDAPI_ENDPOINT")
    if RAPIDAPI_KEY and rapidapi_host:
        try:
            headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": rapidapi_host}
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
                            "dest_id": dest_id, "dest_type": dest_type, "locale": "en-gb",
                            "checkin_date": checkin_iso, "checkout_date": checkout_iso,
                            "filter_by_currency": "GBP", "units": "metric",
                            "room_number": 1, "adults_number": 2, "page_size": 3, "order_by": "price",
                        }
                        resp = requests.get(search_url, headers=headers, params=search_params, timeout=8)
                        if resp.status_code == 200:
                            data = resp.json()
                            candidate = None
                            if isinstance(data, dict):
                                for key in ("result", "results", "search_results", "hotels", "data", "properties"):
                                    if key in data and isinstance(data[key], (list, tuple)) and len(data[key]) > 0:
                                        candidate = data[key][0]; break
                            if candidate is None and isinstance(data, (list, tuple)) and len(data) > 0:
                                candidate = data[0]
                            if candidate:
                                name = candidate.get("hotel_name") or candidate.get("hotel_name_trans") or candidate.get("name") or candidate.get("title")
                                price = None
                                for p in ("min_total_price", "min_price", "price", "price_breakdown", "composite_price_breakdown"):
                                    if p in candidate:
                                        val = candidate[p]
                                        if isinstance(val, (int, float)): price=int(val); break
                                        if isinstance(val, dict):
                                            gross = val.get("gross_amount") or val.get("all_inclusive_amount") or val.get("all_inclusive_amount_hotel_currency")
                                            if isinstance(gross, dict):
                                                v = gross.get("value") or gross.get("amount")
                                                try: price=int(float(v)); break
                                                except: pass
                                            for subk in ("value","amount","amount_rounded","gross_price"):
                                                v = val.get(subk) if isinstance(val, dict) else None
                                                if v is not None:
                                                    try: price=int(float(v)); break
                                                    except: pass
                                            if price is not None: break
                                if price is None:
                                    comp = candidate.get("composite_price_breakdown") or {}
                                    gross = comp.get("gross_amount") or comp.get("all_inclusive_amount")
                                    if isinstance(gross, dict):
                                        v = gross.get("value")
                                        try: price=int(float(v))
                                        except: price=None
                                review = candidate.get("review_score") or candidate.get("review_nr")
                                hotel_class = candidate.get("class") or candidate.get("class_is_estimated") or candidate.get("hotel_class") or candidate.get("stars")
                                if price is not None and name:
                                    return {"status":"success","price":int(price),"name":name,"review_score":float(review) if review is not None else None,"hotel_class":float(hotel_class) if hotel_class is not None else None,"is_fallback":False,"raw":candidate}
            else:
                endpoint = rapidapi_endpoint or "/v1/hotels/search"
                url = f"https://{rapidapi_host}{endpoint}"
                params = {"checkin_date": checkin_iso, "checkout_date": checkout_iso, "currency":"GBP","locale":"en-gb","order_by":"price","page_size":1,"city_name":city}
                if lat is not None and lon is not None:
                    params["latitude"]=lat; params["longitude"]=lon
                resp = requests.get(url, headers=headers, params=params, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    candidate=None
                    if isinstance(data, dict):
                        for key in ("result","results","search_results","hotels","data","properties"):
                            if key in data and isinstance(data[key], (list, tuple)) and len(data[key])>0:
                                candidate=data[key][0]; break
                    if candidate is None and isinstance(data, list) and len(data)>0:
                        candidate=data[0]
                    if candidate:
                        name = candidate.get("name") or candidate.get("hotel_name") or candidate.get("property_name") or candidate.get("title")
                        price=None
                        for pkey in ("price","min_total_price","min_price","price_breakdown","price_raw"):
                            if pkey in candidate:
                                val=candidate[pkey]
                                if isinstance(val, dict): price=val.get("amount") or val.get("value") or price
                                elif isinstance(val, (int,float,str)):
                                    try: price=int(float(val))
                                    except: pass
                                if price is not None: break
                        review = candidate.get("review_score") or candidate.get("review") or candidate.get("rating")
                        hotel_class = candidate.get("class") or candidate.get("stars") or candidate.get("hotel_class")
                        if price is not None and name:
                            return {"status":"success","price":int(price),"name":name,"review_score":float(review) if review is not None else None,"hotel_class":float(hotel_class) if hotel_class is not None else None,"is_fallback":False}
        except Exception:
            pass
    try:
        base=40; hc=float(min_hotel_class) if min_hotel_class is not None else 3.0
        seed=abs(hash(city)) % 100
        price=int(base + hc*25 + seed)
        name=f"{city} Lodge"
        review=round(6.5 + (seed % 35)/10.0,1); review=min(review,9.9)
        return {"status":"success","price":price,"name":name,"review_score":review,"hotel_class":hc,"is_fallback":True,"nearby_city":city}
    except Exception as exc:
        return {"status":"error","message":str(exc)}

def geocode_place(query):
    try:
        url="https://nominatim.openstreetmap.org/search"
        res=requests.get(url, params={"q":query,"format":"json","limit":1}, headers={"User-Agent":"road-trip-planner/1.0"}, timeout=6)
        if res.status_code==200:
            data=res.json()
            if isinstance(data,list) and len(data)>0:
                item=data[0]; return float(item.get("lat")), float(item.get("lon")), item.get("display_name")
    except: pass
    return None

# Session keys
if "run_analysis" not in st.session_state: st.session_state.run_analysis=False
if "selected_leg_idx" not in st.session_state: st.session_state.selected_leg_idx=0
if "last_map_click" not in st.session_state: st.session_state.last_map_click=None

def safe_rerun():
    try:
        if hasattr(st,"experimental_rerun"): st.experimental_rerun(); return
        if hasattr(st,"rerun"): st.rerun(); return
    except: pass
    st.session_state["_needs_manual_refresh"]=True
    try: st.stop()
    except: raise RuntimeError("Please refresh")

AVG_US_GAS_PRICE=4.07
STATE_GAS_PRICES={"GA":3.78,"AL":3.62,"TN":3.66,"MO":3.78,"NE":3.80,"SD":4.00,"WY":4.25,"MT":4.10,"UT":4.34,"AZ":4.46,"NV":4.94,"CA":5.78}

# Sidebar
st.sidebar.markdown("## 🛠️ Trip Settings")
scenic_mode=st.sidebar.checkbox("Bypass Highways (Scenic Mode)", value=False, help="Routes via byways; alters distance/duration mathematically.")
st.sidebar.markdown("---"); st.sidebar.markdown("### 💰 Budget & Costs (£)")
st.sidebar.markdown("**🚗 Rental Vehicle**")
rental_rate=st.sidebar.number_input("Daily Rental Rate (£)", value=55.0)
one_way_fee=st.sidebar.number_input("One-Way Drop-off Fee (£)", value=275.0)
fuel_mpg=st.sidebar.number_input("Fuel economy (mpg)", value=26.0, help="Minivan class ~26 mpg; hybrid Sienna ~36 mpg.")
st.sidebar.markdown("**🏡 Lodging & Food**")
lodging_rate=st.sidebar.number_input("Nightly Lodging (£)", value=95.0, help="Blended avg across Airbnb/points/cash.")
food_rate=st.sidebar.number_input("Daily Family Food Budget (£)", value=85.0)
min_review_score=st.sidebar.slider("Minimum Booking.com review score",0.0,10.0,7.0,0.1)
min_hotel_class=st.sidebar.slider("Minimum hotel star rating",0.0,5.0,3.0,0.5)
st.sidebar.markdown("**🎈 Activities**")
activity_allowance=st.sidebar.number_input("Activity Budget Per Stop (£)", value=30.0)
buffer_percentage=st.sidebar.slider("Emergency Cushion Buffer (%)",0,25,10)
st.sidebar.markdown("---"); st.sidebar.markdown("### 📅 Trip Dates")
trip_start_date=st.sidebar.date_input("Trip Start Date", value=date(2027,9,6))
if st.sidebar.button("🧹 Clear Cache", width='stretch'):
    st.session_state.run_analysis=False; st.session_state.selected_leg_idx=0; st.session_state.last_map_click=None
    st.cache_data.clear(); safe_rerun()

# ==============================================================================
# Waypoints - synced with Revised Itinerary sheet (27 stops)
# ==============================================================================
class Waypoint:
    def __init__(self, name, latitude, longitude, state, is_national_park=False):
        self.name=name; self.latitude=latitude; self.longitude=longitude; self.state=state; self.is_national_park=is_national_park

route_list=[
    Waypoint("Atlanta, Georgia",33.7501,-84.3885,"GA"),
    Waypoint("Birmingham, Alabama",33.5207,-86.8025,"AL"),
    Waypoint("Memphis, Tennessee",35.1486,-90.0519,"TN"),
    Waypoint("Springfield, Missouri",37.2090,-93.2923,"MO"),
    Waypoint("Kansas City, Missouri",39.0997,-94.5786,"MO"),
    Waypoint("Omaha, Nebraska",41.2565,-95.9345,"NE"),
    Waypoint("Sioux Falls, South Dakota",43.5476,-96.7294,"SD"),
    Waypoint("Pinnacles Overlook, Badlands SD",43.8697,-102.2331,"SD",is_national_park=True),
    Waypoint("Mount Rushmore, SD",43.8803,-103.4538,"SD"),
    Waypoint("Sheridan, Wyoming",44.7972,-106.9562,"WY"),
    Waypoint("Cody, Wyoming",44.5263,-109.0565,"WY"),
    Waypoint("West Yellowstone, Montana",44.6632,-111.1012,"MT",is_national_park=True),
    Waypoint("Gardiner, Montana",45.0351,-110.7127,"MT",is_national_park=True),
    Waypoint("Jackson, Wyoming",43.4799,-110.7624,"WY",is_national_park=True),
    Waypoint("Salt Lake City, Utah",40.7606,-111.8881,"UT"),
    Waypoint("Moab, Utah",38.5738,-109.5462,"UT",is_national_park=True),
    Waypoint("Blanding, Utah",37.6240,-109.4780,"UT"),
    Waypoint("Grand Canyon Village, AZ",36.0544,-112.1401,"AZ",is_national_park=True),
    Waypoint("Kanab, Utah",37.0475,-112.5263,"UT"),
    Waypoint("Springdale, Utah",37.1945,-112.9570,"UT",is_national_park=True),
    Waypoint("Las Vegas, Nevada",36.1716,-115.1391,"NV"),
    Waypoint("Furnace Creek (Death Valley), CA",36.4344,-116.8628,"CA",is_national_park=True),
    Waypoint("Tehachapi, California",35.1322,-118.4490,"CA"),
    Waypoint("General Sherman Tree, CA (Sequoia)",36.5817,-118.7514,"CA",is_national_park=True),
    Waypoint("Yosemite Valley, CA",37.7456,-119.5936,"CA",is_national_park=True),
    Waypoint("Lee Vining, California",37.9628,-119.1207,"CA"),
    Waypoint("South Lake Tahoe, California",38.9399,-119.9772,"CA"),
    Waypoint("Martinez, California",38.0194,-122.1341,"CA")
]
all_route_list=route_list.copy()
if "custom_route_stops" in st.session_state:
    for custom_stop in st.session_state.custom_route_stops:
        all_route_list.append(Waypoint(custom_stop["name"],custom_stop["latitude"],custom_stop["longitude"],custom_stop.get("state",""),custom_stop.get("is_national_park",False)))

if "selected_route_names" not in st.session_state:
    st.session_state.selected_route_names=[wp.name for wp in all_route_list]

st.sidebar.markdown("---"); st.sidebar.markdown("### 🧭 Route Builder")
new_stop_query=st.sidebar.text_input("Add stop by place name", value="", placeholder="e.g. Yosemite Valley")
if st.sidebar.button("Add Stop", key="add_stop_btn") and new_stop_query.strip():
    geo=geocode_place(new_stop_query.strip())
    if geo:
        lat,lon,display=geo; name=display or new_stop_query.strip()
        if "custom_route_stops" not in st.session_state: st.session_state.custom_route_stops=[]
        st.session_state.custom_route_stops.append({"name":name,"latitude":lat,"longitude":lon,"state":"","is_national_park":False})
        all_route_list.append(Waypoint(name,lat,lon,"",False))
        cur=st.session_state.get("selected_route_names",[wp.name for wp in all_route_list])
        if name not in cur: cur.append(name)
        st.session_state.selected_route_names=cur; safe_rerun()
    else: st.sidebar.warning("Could not geocode place.")

selected_route_names=st.sidebar.multiselect("Select stops", options=[wp.name for wp in all_route_list], key="selected_route_names")

if selected_route_names != st.session_state.get("_selected_route_names_prev", None):
    st.session_state.run_analysis=False; st.session_state.selected_leg_idx=0; st.session_state.last_map_click=None
    st.session_state._selected_route_names_prev=selected_route_names
if "selected_route_names" in st.session_state: selected_route_names=st.session_state.selected_route_names

if st.session_state.get('selected_route_names'):
    move_choice=None
    try: move_choice=st.sidebar.selectbox("Move stop", options=st.session_state['selected_route_names'], key='move_choice')
    except: move_choice=None
    def _move_up_cb():
        mc=st.session_state.get('move_choice'); lst=st.session_state.get('selected_route_names',[])[:]
        if mc in lst:
            idx=lst.index(mc)
            if idx>0: lst[idx],lst[idx-1]=lst[idx-1],lst[idx]; st.session_state['selected_route_names']=lst; st.session_state['move_choice']=mc; safe_rerun()
    def _move_down_cb():
        mc=st.session_state.get('move_choice'); lst=st.session_state.get('selected_route_names',[])[:]
        if mc in lst:
            idx=lst.index(mc)
            if idx < len(lst)-1: lst[idx],lst[idx+1]=lst[idx+1],lst[idx]; st.session_state['selected_route_names']=lst; st.session_state['move_choice']=mc; safe_rerun()
    c1,c2=st.sidebar.columns(2); c1.button("Up", on_click=_move_up_cb); c2.button("Down", on_click=_move_down_cb)

route_list=build_route_selection(all_route_list, selected_route_names)
if len(route_list)<2: st.sidebar.warning("Choose at least two stops.")
else: st.sidebar.caption(f"{len(route_list)} stops selected")

REST_DAYS={
    "Atlanta, Georgia":1,
    "Memphis, Tennessee":1,
    "Kansas City, Missouri":1,
    "Cody, Wyoming":1,
    "Jackson, Wyoming":1,
    "Grand Canyon Village, AZ":1,
    "Yosemite Valley, CA":1,
    "South Lake Tahoe, California":1,
}

def generate_pdf_itinerary(rows, grand_total):
    pdf=FPDF(); pdf.add_page()
    pdf.set_font("Arial",'B',16); pdf.cell(200,10,txt="Family Road Trip Itinerary",ln=True,align='C')
    pdf.set_font("Arial",'I',10); pdf.cell(200,10,txt=f"Estimated Total Budget: £{grand_total:,.2f}",ln=True,align='C'); pdf.ln(10)
    for row in rows:
        pdf.set_font("Arial",'B',12); pdf.cell(200,8,txt=f"Leg {row['Leg']}: {row['Route Stretch']}",ln=True)
        pdf.set_font("Arial",'',10)
        pdf.cell(200,6,txt=f"Start Date: {row['Start Date']} | Check-in: {row['Check-in Date'][:10]}",ln=True)
        pdf.cell(200,6,txt=f"Distance: {row['Distance']} | Driving Time: {row['Driving Time']}",ln=True)
        pdf.cell(200,6,txt=f"Pace: {row['Pace & Status']}",ln=True); pdf.ln(5)
    pdf_output=pdf.output(dest="S")
    if isinstance(pdf_output,str): return pdf_output.encode('latin-1')
    if isinstance(pdf_output,bytearray): return bytes(pdf_output)
    return pdf_output

def render_google_maps_export(waypoints):
    if len(waypoints)<2: return
    MAX_STOPS=10; STEP=MAX_STOPS-1; st.markdown("### 🗺️ Export Routes to Google Maps")
    for leg_num, start_idx in enumerate(range(0,len(waypoints)-1,STEP), start=1):
        chunk=waypoints[start_idx:start_idx+MAX_STOPS]; origin=chunk[0]; destination=chunk[-1]
        maps_url=f"https://www.google.com/maps/dir/?api=1&origin={origin.latitude},{origin.longitude}&destination={destination.latitude},{destination.longitude}&travelmode=driving"
        if len(chunk)>2:
            intermediate_stops=[f"{wp.latitude},{wp.longitude}" for wp in chunk[1:-1]]
            maps_url+="&waypoints="+urllib.parse.quote("|".join(intermediate_stops))
        st.link_button(f"Open Route Segment {leg_num} ({origin.state} -> {destination.state})", maps_url, width='stretch')

@st.cache_data
def get_cached_distance(o_name,o_lat,o_lon,d_name,d_lat,d_lon,scenic_mode_active):
    try:
        url=f"http://router.project-osrm.org/route/v1/driving/{o_lon},{o_lat};{d_lon},{d_lat}?overview=false"
        res=requests.get(url,timeout=5).json()
        if res.get("code")=="Ok":
            base_miles=res["routes"][0]["distance"]*0.000621371; base_hours=res["routes"][0]["duration"]/3600
            if scenic_mode_active: base_miles*=1.15; base_hours*=1.35
            return round(base_miles,1), round(base_hours,1)
    except: pass
    return (230.0 if scenic_mode_active else 200.0), (4.0 if scenic_mode_active else 3.0)

@st.cache_data
def get_detailed_route_track(o_lat,o_lon,d_lat,d_lon,scenic_mode_active):
    try:
        url=f"http://router.project-osrm.org/route/v1/driving/{o_lon},{o_lat};{d_lon},{d_lat}?overview=full&geometries=geojson&alternatives=true"
        res=requests.get(url,timeout=5).json()
        if res.get("code")=="Ok":
            routes=res.get("routes",[])
            if scenic_mode_active and len(routes)>1: coords=routes[1]["geometry"]["coordinates"]
            elif len(routes)>0: coords=routes[0]["geometry"]["coordinates"]
            else: return [[o_lat,o_lon],[d_lat,d_lon]]
            return [[point[1],point[0]] for point in coords]
    except: pass
    return [[o_lat,o_lon],[d_lat,d_lon]]

@st.cache_data
def calculate_approx_daylight(latitude,day_of_year=260):
    p=math.asin(0.39795*math.cos(0.2163108+2*math.asin(0.39795*math.sin(2*math.pi*(day_of_year-80)/365))))
    daylight_denom=math.cos(latitude*math.pi/180)*math.cos(p)
    if daylight_denom==0: return 12.0
    val=(-0.01454-math.sin(latitude*math.pi/180)*math.sin(p))/daylight_denom
    val=max(-1.0,min(1.0,val)); return round(24-(24/math.pi)*math.acos(val),1)

@st.cache_data(show_spinner=False)
def get_cached_location_insights(city_name,scenic_mode_active):
    scenic_context="Scenic detour parameters are prioritized." if scenic_mode_active else ""
    optimized_prompt=f"""You are an expert family travel concierge. Provide a local, actionable field guide for {city_name}
optimized for parents traveling with a 2-year-old toddler on an affordable budget. {scenic_context}
Format with clear Markdown headers. Provide exactly 2-3 specific recommendations:

### 🏃‍♂️ Free Areas for Toddler Activity
### 🍕 Toddler-Tolerant Value Dining
### 🏨 Affordable Basecamp Alternatives
"""
    try:
        response=client.chat.completions.create(model="gpt-4o-mini",messages=[{"role":"system","content":"You are a travel assistant"},{"role":"user","content":optimized_prompt}],temperature=0.7)
        return response.choices[0].message.content
    except Exception as e: return f"❌ AI Concierge Error."

@st.cache_data(show_spinner=False)
def get_cached_seasonal_hazards(o_name,d_name,current_date_str):
    prompt=f"Analyze high-altitude weather risks, pass closures, or seasonal hazards between {o_name} and {d_name} for {current_date_str}, 2027. Provide 2 bullets. If clear, state Passes clear."
    try:
        response=client.chat.completions.create(model="gpt-4o-mini",messages=[{"role":"user","content":prompt}],temperature=0.3)
        return response.choices[0].message.content
    except: return "Verify conditions via local state DOT portals."

@st.cache_data(show_spinner=False)
def get_cached_park_rules(park_name,date_str):
    prompt=f"Identify entry parameters or reservation updates for {park_name} on {date_str}, 2027. Provide 2 concise bullets."
    try:
        response=client.chat.completions.create(model="gpt-4o-mini",messages=[{"role":"user","content":prompt}],temperature=0.2)
        return response.choices[0].message.content
    except: return "Standard park entry and pass rules apply."

@st.cache_data(show_spinner=False)
def get_cached_scenic_alignment(o_name,d_name):
    prompt=f"Identify official names of scenic byways or route numbers between {o_name} and {d_name}. Limit to two sentences."
    try:
        response=client.chat.completions.create(model="gpt-4o-mini",messages=[{"role":"user","content":prompt}])
        return response.choices[0].message.content
    except: return "Scenic alternative routes map parallel to the primary highway."

@st.cache_data(show_spinner=False)
def get_cached_ai_overnight_fix(o_name,d_name,hours):
    prompt=f"You are a routing assistant. Driving {o_name} to {d_name} ({hours}h) with 2yo. Identify primary highway. Suggest midway town directly on that highway. Provide 1 hotel and 1 toddler park. Keep concise."
    try:
        response=client.chat.completions.create(model="gpt-4o",messages=[{"role":"user","content":prompt}],temperature=0.0)
        return response.choices[0].message.content
    except: return "Intermediate overnight stop recommended along the primary highway."

@st.cache_data(show_spinner=False)
def get_cached_ai_midday_break(o_name,d_name,hours):
    prompt=f"You are a routing assistant. Driving {o_name} to {d_name} ({hours}h) with 2yo. Identify primary highway. Suggest midway town for lunch directly on route. 1 quick restaurant + 1 playground. Keep concise."
    try:
        response=client.chat.completions.create(model="gpt-4o",messages=[{"role":"user","content":prompt}],temperature=0.0)
        return response.choices[0].message.content
    except: return "Midday break recommended along the primary highway."

@st.cache_data(show_spinner=False)
def get_historical_weather_proxy(lat,lon,target_date_str):
    try:
        target_date=date.fromisoformat(target_date_str) if isinstance(target_date_str,str) else target_date_str
        proxy_year=target_date.year-4; proxy_date=date(proxy_year,target_date.month,target_date.day).isoformat()
        url=f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={proxy_date}&end_date={proxy_date}&daily=temperature_2m_max,temperature_2m_min&timezone=auto&temperature_unit=fahrenheit"
        res=requests.get(url,timeout=5).json()
        if "daily" in res:
            high=round(res["daily"]["temperature_2m_max"][0]); low=round(res["daily"]["temperature_2m_min"][0])
            return f"🌡️ **Expected Climate:** High **{high}°F** / Low **{low}°F** *(Based on historical data for this exact week)*"
    except: pass
    return "🌡️ Expected Climate: Data temporarily unavailable."

@st.cache_data(show_spinner=False)
def get_cached_safety_alerts(city_name):
    prompt=f"""You are an expert travel safety analyst. Provide a brief, objective safety advisory for a family road-tripping to {city_name}.
- General Safety Level:
- Areas to Avoid or Use Caution:
- Vehicle & Parking Tips:
Keep factual, reassuring but realistic, tailored to family with young child."""
    try:
        response=client.chat.completions.create(model="gpt-4o-mini",messages=[{"role":"user","content":prompt}],max_tokens=400,temperature=0.3)
        return response.choices[0].message.content.strip()
    except: return f"⚠️ Safety data temporarily unavailable for {city_name}."

# ========== STICKY HEADER ==========
st.markdown('<div class="sticky-header">🚗 36-day Atlanta → Martinez (Sept 6 – Oct 11 2027) <small>| 27 stops | 8 rest days | Toddler-paced</small></div>', unsafe_allow_html=True)
st.markdown("# 2027 Road Trip Planner")
st.caption("Tap a tab below. Itinerary is your daily view — map and budget live in their own spots.")

# Timeline compute button - above tabs for access anywhere
if st.button("▶️ Calculate Trip Timeline", type="primary", width='stretch'):
    st.session_state.run_analysis=True

# ========== COMPUTE TIMELINE (shared across tabs) ==========
total_miles=0.0; total_fuel=0.0; np_count=0; itinerary_rows=[]; current_date=trip_start_date; grand_total=0.0; total_days=1; subtotal_rental=0.0; subtotal_lodging=0.0; subtotal_food=0.0; subtotal_activities=0.0; subtotal_parks=0.0; buffer_amount=0.0
scenario_summary=None; recommendation=None

if st.session_state.run_analysis and len(route_list)>=2:
    start_date=trip_start_date
    current_date=start_date
    origin_rest_days=REST_DAYS.get(route_list[0].name,0)
    current_date+=timedelta(days=origin_rest_days)
    for i in range(len(route_list)-1):
        orig,dest=route_list[i],route_list[i+1]
        miles,hours=get_cached_distance(orig.name,orig.latitude,orig.longitude,dest.name,dest.latitude,dest.longitude,scenic_mode)
        avg_price_for_leg=((STATE_GAS_PRICES.get(orig.state,AVG_US_GAS_PRICE)+STATE_GAS_PRICES.get(dest.state,AVG_US_GAS_PRICE))/2.0)*0.79
        total_fuel+=(miles/fuel_mpg)*avg_price_for_leg; total_miles+=miles
        if dest.is_national_park: np_count+=1
        current_date+=timedelta(days=1)
        date_label=current_date.strftime("%b %d")
        drive_status="Split Drive" if hours>5 else ("Steady Drive" if hours>3.0 else "Short Stretch")
        arrival_date=current_date
        rest_days_count=REST_DAYS.get(dest.name,0)
        if rest_days_count>0: drive_status+=f" + Extended Stay ({rest_days_count}d)"; current_date+=timedelta(days=rest_days_count)
        itinerary_rows.append({"Leg":f"#{i+1}","Start Date":date_label,"Check-in Date":arrival_date.isoformat(),"Day of Year":arrival_date.timetuple().tm_yday,"Route Stretch":f"{orig.name} -> {dest.name}","Destination":dest.name,"Origin":orig.name,"OriginObj":orig,"DestObj":dest,"Distance":f"{miles:,.1f} mi","DistMiles":miles,"Driving Time":f"{hours:.1f} hrs","DriveHours":hours,"Pace & Status":drive_status,"Rest Days":rest_days_count})
    total_days=max(1,(current_date-start_date).days)
    subtotal_rental=(total_days*rental_rate)+one_way_fee
    subtotal_lodging=total_days*lodging_rate
    subtotal_food=total_days*food_rate
    subtotal_activities=len(route_list)*activity_allowance
    subtotal_parks=(80.0 if (np_count*35.0)>80.0 else (np_count*35.0))*0.79
    calculated_subtotal=subtotal_rental+total_fuel+subtotal_lodging+subtotal_food+subtotal_activities+subtotal_parks
    buffer_amount=calculated_subtotal*(buffer_percentage/100.0)
    grand_total=calculated_subtotal+buffer_amount
    scenario_summary=build_scenario_comparison(route_list, lambda o_name,o_lat,o_lon,d_name,d_lat,d_lon,scenic_mode_active: get_cached_distance(o_name,o_lat,o_lon,d_name,d_lat,d_lon,scenic_mode_active))
    recommendation=recommend_route_style(scenario_summary, budget_tolerance=max(1000.0, grand_total*0.8))

# ========== TABS ==========
tab_itinerary, tab_map, tab_budget = st.tabs(["Itinerary", "Map", "Budget"])

with tab_itinerary:
    if not st.session_state.run_analysis:
        st.info("👆 Tap **Calculate Trip Timeline** up top to populate the day-by-day view.")
        if len(route_list)>=2:
            st.markdown("#### Stops (tap to edit in sidebar)")
            for idx, wp in enumerate(route_list):
                badge=" 🛌 Extended" if wp.name in REST_DAYS else ""
                st.markdown(f"{idx+1}. **{wp.name}**{badge} — {wp.state}{' 🏞️' if wp.is_national_park else ''}")
    else:
        if not itinerary_rows:
            st.warning("Add at least 2 stops.")
        else:
            st.markdown(f"**{total_days} days** • **{total_miles:,.0f} mi** • **£{grand_total:,.0f} est.**")
            st.progress(min(1.0, st.session_state.selected_leg_idx / max(1,len(route_list)-2)))

            # Quick nav
            nav1, nav2 = st.columns(2)
            with nav1:
                if st.button("⬅️ Prev", disabled=(st.session_state.selected_leg_idx==0), width='stretch'):
                    st.session_state.selected_leg_idx=max(0,st.session_state.selected_leg_idx-1); safe_rerun()
            with nav2:
                if st.button("Next ➡️", disabled=(st.session_state.selected_leg_idx>=len(route_list)-2), width='stretch'):
                    st.session_state.selected_leg_idx=min(len(route_list)-2,st.session_state.selected_leg_idx+1); safe_rerun()

            # Day expanders
            for idx, row in enumerate(itinerary_rows):
                dest=row["DestObj"]; orig=row["OriginObj"]
                is_rest=row["Rest Days"]>0
                badge=" 🛌 Extended Stay" if is_rest else ""
                title=f"Day {idx+1+REST_DAYS.get(route_list[0].name,0)}: {dest.name}{badge} ({row['Start Date']})"
                # Auto-open current leg
                with st.expander(title, expanded=(idx==st.session_state.selected_leg_idx)):
                    c1,c2=st.columns([1,1])
                    with c1: st.metric("Distance", row["Distance"])
                    with c2: st.metric("Drive", row["Driving Time"])
                    st.caption(f"From {orig.name} → {dest.name} • {row['Pace & Status']}")
                    if row["Rest Days"]>0:
                        st.success(f"🛌 Two-night stay — recovery + explore {dest.name}")

                    # Inland guide
                    with st.container(border=True):
                        st.markdown(f"**🏡 {dest.name}**")
                        if st.button(f"Load guide for {dest.name}", key=f"guide_{idx}"):
                            with st.spinner("Fetching guide..."):
                                insights=get_cached_location_insights(dest.name, scenic_mode)
                                st.session_state[f"insights_{idx}"]=insights
                        if f"insights_{idx}" in st.session_state:
                            st.markdown(st.session_state[f"insights_{idx}"])

                    # Collapsed details - keep inside expander as sub-expanders for mobile brevity
                    with st.expander("☀️ Daylight + Weather", expanded=False):
                        target_yday=row.get("Day of Year",260)
                        daylight=calculate_approx_daylight(dest.latitude, target_yday)
                        st.markdown(f"~**{daylight} hrs daylight** on {row['Start Date']}.")
                        climate=get_historical_weather_proxy(dest.latitude,dest.longitude,row["Check-in Date"][:10])
                        st.info(climate)
                        hazards=get_cached_seasonal_hazards(orig.name,dest.name,row["Start Date"])
                        st.markdown(hazards)

                    with st.expander("👶 Toddler routing", expanded=False):
                        h_time=row["DriveHours"]
                        if h_time<=3.0: st.info("⏰ **8:30 AM** (arrive lunch) or **1:00 PM** (nap window).")
                        elif h_time<=7.0: st.info(f"⏰ **8:00 AM** start — splits {h_time} hr drive around midday break.")
                        else: st.info(f"⏰ **6:30-7:00 AM** start — marathon day.")
                        if scenic_mode:
                            scenic_info=get_cached_scenic_alignment(orig.name,dest.name); st.caption(scenic_info)
                        if orig.is_national_park or dest.is_national_park:
                            target_park=dest.name if dest.is_national_park else orig.name
                            st.markdown(f"**🏞️ Park: {target_park}**")
                            st.markdown(get_cached_park_rules(target_park,row["Start Date"]))
                        if h_time>7.0: st.markdown(get_cached_ai_overnight_fix(orig.name,dest.name,h_time))
                        elif h_time>3.0: st.markdown(get_cached_ai_midday_break(orig.name,dest.name,h_time))
                        else: st.markdown("Fits single nap window.")

                    with st.expander("⚠️ Safety", expanded=False):
                        st.warning("Packed out-of-state plates attract break-ins — hide valuables.")
                        st.markdown(get_cached_safety_alerts(dest.name))

                    # Lodging quick check inside day
                    with st.container(border=True):
                        dc=date.fromisoformat(row["Check-in Date"]).strftime("%b %d, %Y")
                        cols=st.columns([3,1])
                        with cols[0]: st.markdown(f"**Check-in:** {dc}")
                        with cols[1]:
                            if st.button("Price", key=f"price_itin_{idx}"):
                                with st.spinner(f"Checking {dest.name}..."):
                                    checkin=date.fromisoformat(row["Check-in Date"]); checkout=(checkin+timedelta(days=1)).isoformat()
                                    res=fetch_live_hotel_price(dest.name,checkin.isoformat(),checkout,min_review_score,min_hotel_class,dest.latitude,dest.longitude)
                                    if res["status"]=="success":
                                        tags=[]; 
                                        if res.get("review_score") is not None: tags.append(f"{res['review_score']:.1f}★")
                                        if res.get("hotel_class") is not None: tags.append(f"{res['hotel_class']:.1f}*")
                                        tag_text=f" ({', '.join(tags)})" if tags else ""
                                        if res.get("is_fallback"): st.info(f"Fallback: £{res['price']:,} at {res['name']} in {res.get('nearby_city','area')}{tag_text}")
                                        else: st.success(f"£{res['price']:,} at {res['name']}{tag_text}")
                                    else: st.error(f"Price fetch failed: {res.get('message','')}")

            if itinerary_rows:
                st.markdown("---")
                pdf_bytes=generate_pdf_itinerary(itinerary_rows, grand_total)
                st.download_button(label="📥 Download PDF Itinerary", data=pdf_bytes, file_name="Family_Road_Trip_2027.pdf", mime="application/pdf", width='stretch')

with tab_map:
    if len(route_list)<2:
        st.info("Add at least 2 stops to see a map.")
    else:
        m=folium.Map(location=[39.8283,-98.5795], tiles="CartoDB positron", zoom_start=4, zoom_control=False, dragging=True, scrollWheelZoom=False, doubleClickZoom=False, boxZoom=False, touchZoom=True, control_scale=False)
        waypoint_coords=[[wp.latitude,wp.longitude] for wp in route_list]; m.fit_bounds(waypoint_coords)
        active_leg_idx=st.session_state.selected_leg_idx
        for i in range(len(route_list)-1):
            orig,dest=route_list[i],route_list[i+1]
            if abs(i-active_leg_idx)<=1: leg_track=get_detailed_route_track(orig.latitude,orig.longitude,dest.latitude,dest.longitude,scenic_mode)
            else: leg_track=[[orig.latitude,orig.longitude],[dest.latitude,dest.longitude]]
            if i==active_leg_idx:
                folium.PolyLine(locations=leg_track,color="#4F46E5",weight=6,opacity=1.0,z_index=999).add_to(m)
            else:
                color="#10B981" if scenic_mode else "#2563EB"; dash_array="4, 6" if scenic_mode else None
                folium.PolyLine(locations=leg_track,color=color,weight=3,opacity=0.75,dash_array=dash_array).add_to(m)
        for idx,wp in enumerate(route_list):
            border_color,fill_color,radius=("#0F766E","#2DD4BF",7) if wp.is_national_park else ("#1E3A8A","#60A5FA",5)
            folium.CircleMarker(location=[wp.latitude,wp.longitude],radius=radius,color=border_color,weight=1.5,fill=True,fill_color=fill_color,fill_opacity=0.95,popup=folium.Popup(f"<div style='font-family:sans-serif;font-size:12px;'><b>{wp.name}</b></div>",max_width=200)).add_to(m)
        map_data=st_folium(m,width="100%",height=420,key=f"master_trip_map_mobile_{scenic_mode}")
        if map_data and map_data.get("last_object_clicked"):
            click_coords=map_data["last_object_clicked"]
            if click_coords != st.session_state.last_map_click:
                st.session_state.last_map_click=click_coords; lat,lon=click_coords.get("lat"),click_coords.get("lng")
                for idx,wp in enumerate(route_list):
                    if abs(wp.latitude-lat)<0.008 and abs(wp.longitude-lon)<0.008:
                        st.session_state.selected_leg_idx=max(0,idx-1); safe_rerun()
        # progress
        total_legs_count=len(route_list)-1; active_leg=st.session_state.selected_leg_idx; progress_percent=(active_leg/total_legs_count) if total_legs_count>0 else 0
        st.progress(progress_percent); st.caption(f"Leg {active_leg+1} of {total_legs_count} • {int(progress_percent*100)}% complete")
        with st.expander("🔗 Mobile GPS Links", expanded=False):
            render_google_maps_export(route_list)

with tab_budget:
    if not st.session_state.run_analysis:
        st.info("Tap **Calculate Trip Timeline** in Itinerary tab to see budget.")
    else:
        st.markdown("### 💰 Budget Snapshot")
        c1,c2,c3=st.columns(3)
        with c1: st.metric("Total Est.", f"£{grand_total:,.0f}")
        with c2: st.metric("Avg / Day", f"£{(grand_total/max(1,total_days)):,.0f}")
        with c3: st.metric("Distance", f"{total_miles:,.0f} mi")
        c4,c5,c6=st.columns(3)
        with c4: st.metric("Nights", f"{total_days}")
        with c5: st.metric("Avg Drive", f"{sum([r['DriveHours'] for r in itinerary_rows])/max(1,len(itinerary_rows)):.1f}h")
        with c6: st.metric("Park Pass", f"£{subtotal_parks:,.0f}")

        # compact pie still but smaller
        with st.container(border=True):
            st.markdown("#### Allocation")
            labels=['Vehicle Rental','Fuel','Lodging','Food','Activities','Park Admissions','Buffer']
            values=[subtotal_rental,total_fuel,subtotal_lodging,subtotal_food,subtotal_activities,subtotal_parks,buffer_amount]
            colors=['#1E3A8A','#2563EB','#3B82F6','#60A5FA','#93C5FD','#0F766E','#94A3B8']
            fig=go.Figure(data=[go.Pie(labels=labels,values=values,hole=.45,marker=dict(colors=colors),hoverinfo="label+value+percent",textinfo="percent")])
            fig.update_layout(showlegend=True,legend=dict(orientation="h",yanchor="bottom",y=-0.35,xanchor="center",x=0.5),margin=dict(t=10,b=10,l=10,r=10),height=300)
            st.plotly_chart(fig,width='stretch')

        if scenario_summary and recommendation:
            st.info(f"💡 Best fit: **{recommendation['recommendation']}** — {recommendation['reason']}")
            with st.columns(2)[0]: st.metric("Fast", f"{scenario_summary['Fast']['miles']:,.1f} mi", f"{scenario_summary['Fast']['hours']:,.1f} hrs")
            with st.columns(2)[1]: st.metric("Scenic", f"{scenario_summary['Scenic']['miles']:,.1f} mi", f"{scenario_summary['Scenic']['hours']:,.1f} hrs")

        # compact dataframe
        st.markdown("#### Daily Breakdown")
        df_rows=[]
        for r in itinerary_rows:
            df_rows.append({"Day":r["Start Date"],"Route":r["Route Stretch"],"Mi":r["DistMiles"],"Hrs":r["DriveHours"],"Pace":r["Pace & Status"],"Rest":r["Rest Days"]})
        df=pd.DataFrame(df_rows)
        st.dataframe(df, width='stretch', hide_index=True)

        # live prices hidden
        with st.expander("🏨 Show live lodging prices (check one by one in Itinerary)", expanded=False):
            st.caption("Hotel sniping uses the same pricing engine. Quick checks live inside each day on the Itinerary tab.")
            if itinerary_rows:
                origin=route_list[0]; start_checkin_label=trip_start_date.strftime("%b %d, %Y")
                with st.container(border=True):
                    s1,s2=st.columns([3,1])
                    with s1: st.markdown(f"**Starting Night: {origin.name}**\n\nCheck-in: {start_checkin_label}")
                    with s2:
                        if st.button("Check Price", key="price_btn_start_budget"):
                            with st.spinner(f"Sniping {origin.name}..."):
                                res=fetch_live_hotel_price(origin.name,trip_start_date.isoformat(),(trip_start_date+timedelta(days=1)).isoformat(),min_review_score,min_hotel_class,origin.latitude,origin.longitude)
                                if res["status"]=="success": st.success(f"£{res['price']:,} at {res['name']}")
                                else: st.error(res.get("message","Failed"))
                for idx,row in enumerate(itinerary_rows):
                    dest=row["DestObj"]; destination_label=dest.name; checkin_label=date.fromisoformat(row["Check-in Date"]).strftime("%b %d, %Y")
                    with st.container(border=True):
                        c1,c2,c3=st.columns([1.2,2,1])
                        with c1: st.error("🚨 Park") if dest.is_national_park else st.success("✅ Stop")
                        with c2: st.markdown(f"**{destination_label}**\n\n{checkin_label}"); 
                        with c3:
                            if st.button("Price", key=f"price_budget_{idx}"):
                                with st.spinner(f"Checking {destination_label}..."):
                                    checkin=date.fromisoformat(row["Check-in Date"]); checkout=(checkin+timedelta(days=1)).isoformat()
                                    res=fetch_live_hotel_price(destination_label,checkin.isoformat(),checkout,min_review_score,min_hotel_class,dest.latitude,dest.longitude)
                                    if res["status"]=="success": st.success(f"£{res['price']:,} at {res['name']}")
                                    else: st.error("Failed")

        pdf_bytes=generate_pdf_itinerary(itinerary_rows, grand_total)
        st.download_button(label="📥 PDF Itinerary", data=pdf_bytes, file_name="Family_Road_Trip_2027.pdf", mime="application/pdf", width='stretch')

