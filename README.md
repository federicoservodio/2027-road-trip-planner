# Family Road Trip Planner

Streamlit app for the Sep 6 - Oct 11, 2027 US road trip (Atlanta -> Martinez CA,
36 days, route synced with the "Revised Itinerary" tab of the trip Google Sheet).

## Setup

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Create a `.env` file in this directory with:

    OPENAI_API_KEY=...      # for the AI destination guides and route fixes
    RAPIDAPI_KEY=...        # for live hotel price checks
    RAPIDAPI_HOST=booking-com.p.rapidapi.com
    RAPIDAPI_ENDPOINT=/v1/hotels/search

Never commit real keys - keep them only in `.env`.

## Run

    .venv/bin/streamlit run app.py

## Tests

    .venv/bin/pip install pytest
    .venv/bin/python -m pytest

Note: `test_stovepipe.py` (Furnace Creek / Death Valley price probe) makes live
RapidAPI calls and only runs when `RAPIDAPI_KEY` is set. `test_route_selection.py`
is fully offline.

## What changed (Aug 2026 sync)
- Route synced to the 36-day Revised Itinerary sheet tab (adds Birmingham AL,
  Springfield MO, Omaha, Cody, West Yellowstone, Gardiner, Moab, Blanding,
  Kanab, Springdale, Furnace Creek, Tehachapi, Lee Vining; replaces Stovepipe
  Wells, Toadstool/Sage Creek/Creston detours, Hulett, Monterey-era stops).
- REST_DAYS covers all two-night stops incl. the new Atlanta jet-lag day and
  Cody rest day; names must match route_list exactly.
- Date logic: Day 1 = arrival night in Atlanta, first drive on Day 2; dates now
  align with the sheet's day numbers (verified against all 27 destination dates).
- Fuel model: minivan-class 26 mpg default (editable in sidebar; hybrid Sienna
  ~36 mpg), gas-price fallback ~$4.07, added AL/NE/MT state prices.
- Lodging default lowered to ~£95/night (blended Airbnb/points/cash plan).
