# Family Road Trip Planner — Mobile Edition

Streamlit app for the Sep 6 – Oct 11, 2027 US road trip (Atlanta -> Martinez CA, 36 days, 27 stops, route synced with the "Revised Itinerary" tab of the trip Google Sheet).

## What's new in mobile edition
- **layout="centered"**, reduced top padding, media-query font tweaks for phones.
- **Top-level tabs**: Itinerary (default), Map, Budget — no more endless scroll.
- **Sticky header**: `36-day Atlanta → Martinez (Sept 6 – Oct 11 2027) | 27 stops | 8 rest days`.
- **Itinerary tab**: Each day is an `st.expander` titled `Day N: Destination (date)`. Two-night stops marked `🛌 Extended Stay`. Inside: drive metrics, destination guide loader, daylight/weather, toddler routing, safety, and price check.
- **Map tab**: Folium map moved here, with progress bar and GPS export.
- **Budget tab**: Metric cards for Total/Avg/Day/Nights/Distance/Avg Drive, compact Plotly pie, dataframe with horizontal scroll, and live hotel prices behind "Show live lodging prices" expander.
- Secrets-free: reads `os.getenv("OPENAI_API_KEY")`, `RAPIDAPI_KEY`, etc.

## Setup

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Create a `.env` file:

    OPENAI_API_KEY=sk-...
    RAPIDAPI_KEY=...
    RAPIDAPI_HOST=booking-com.p.rapidapi.com
    RAPIDAPI_ENDPOINT=/v1/hotels/search

Never commit `.env` — it's already in `.gitignore`.

## Run

    .venv/bin/streamlit run app.py

## Streamlit Cloud

Push this folder flat to GitHub (no nested folder). In Streamlit Cloud Secrets, paste:

```
OPENAI_API_KEY="sk-..."
RAPIDAPI_KEY="..."
RAPIDAPI_HOST="booking-com.p.rapidapi.com"
RAPIDAPI_ENDPOINT="https://booking-com.p.rapidapi.com/v1/hotels/search"
```

## Tests

    .venv/bin/python -m pytest -q --ignore=tools

`test_stovepipe.py` skips politely without `RAPIDAPI_KEY`.

## Route sync (Aug 2026)
- 27 stops from Revised Itinerary sheet tab, 8 REST_DAYS (Atlanta jet-lag, Memphis, KC, Cody, Jackson, Grand Canyon, Yosemite, South Lake Tahoe)
- Date logic: Day 1 = arrival night in Atlanta, first drive Day 2, matches sheet dates.
- Fuel: 26 mpg minivan default (editable sidebar, hybrid Sienna ~36 mpg), gas fallback $4.07, AL/NE/MT state prices.

## Mobile UX notes
- Tabs have large tap targets; tables scroll horizontally on <600px.
- Expanders lazy-load OpenAI guides only on button press to save data.
- Map touchZoom enabled, scrollWheelZoom disabled for phone scroll safety.
