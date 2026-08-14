from datetime import date
from typing import List
import requests
import os
import time
from openai import OpenAI

from models import Waypoint, RouteSegment, CostConstraints, ToddlerConstraints
from agents import ToddlerWelfareAgent, BudgetOptimizerAgent

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class RoadTripPlannerAI:
    def __init__(self, start_date: date, end_date: date):
        self.start_date = start_date
        self.end_date = end_date
        self.toddler_agent = ToddlerWelfareAgent(ToddlerConstraints())
        self.budget_agent = BudgetOptimizerAgent(CostConstraints())
        
        # Global Budget Trackers
        self.total_miles = 0.0
        self.total_fuel_cost = 0.0
        self.total_accommodation_savings = 0.0

    def get_real_driving_data(self, origin: Waypoint, destination: Waypoint) -> tuple:
        try:
            url = f"http://router.project-osrm.org/route/v1/driving/{origin.longitude},{origin.latitude};{destination.longitude},{destination.latitude}?overview=false"
            response = requests.get(url, timeout=10).json()
            if response.get("code") == "Ok":
                route = response["routes"][0]
                miles = round(route["distance"] * 0.000621371, 1)
                hours = round(route["duration"] / 3600, 1)
                return miles, hours
        except Exception:
            pass
        return 200.0, 3.0

    def ask_ai_for_buffer_town(self, origin: Waypoint, destination: Waypoint, current_hours: float) -> str:
        prompt = f"""
        We are on a road trip with a 2-year-old. The drive from {origin.name} to {destination.name} takes {current_hours} hours.
        Provide a specific intermediate town roughly halfway between them where we should stop for the night.
        Include:
        1. Town name and state.
        2. One specific public park/playground for a toddler.
        3. A budget suite hotel chain recommendation.
        Keep it brief and actionable.
        """
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"AI Brain offline. Error: {e}"

    def optimize_itinerary(self, waypoints: List[Waypoint]):
        print(f"\n🚀 --- RUNNING MASTER LOGISTICS & BUDGET OPTIMIZER --- 🚀\n")
        
        # Minivan class average packed with luggage: ~26 mpg.
        # A hybrid Toyota Sienna would return ~36 mpg — adjust if he lands one.
        mpg = 26.0
        fuel_price = self.budget_agent.constraints.estimated_fuel_price_per_gallon

        for i in range(len(waypoints) - 1):
            origin = waypoints[i]
            destination = waypoints[i+1]
            time.sleep(1)
            real_miles, real_hours = self.get_real_driving_data(origin, destination)
            
            # Update running mileage
            self.total_miles += real_miles
            
            # Calculate fuel cost for this leg
            leg_fuel_cost = (real_miles / mpg) * fuel_price
            self.total_fuel_cost += leg_fuel_cost
            
            segment = RouteSegment(origin=origin, destination=destination, distance_miles=real_miles, drive_time_hours=real_hours)
            welfare_check = self.toddler_agent.evaluate_segment(segment)
            
            print(f"📍 Leg {i+1}: {origin.name} ➡️ {destination.name}")
            print(f"   [Map Data] {real_miles} miles | ~{real_hours} hours driving")
            print(f"   [Fuel Est] ${leg_fuel_cost:.2f} (Est. at ${fuel_price}/gal)")
            
            # If it's a National Park, invoke the Budget Agent to check lodging strategy
            if destination.is_national_park:
                # Mock costs: In-park lodges are pricey ($320), gateway Airbnbs are cheaper ($180)
                lodging_analysis = self.budget_agent.evaluate_accommodation(destination, in_park_cost=320.0, gateway_town_cost=180.0)
                self.total_accommodation_savings += lodging_analysis["savings"]
                print(f"   💰 [Budget Agent]: {lodging_analysis['reason']}")
            
            # Safety Check Validation
            if not welfare_check.approved:
                print(f"   ⚠️ [TODDLER ALERT] Drive exceeds threshold!")
                ai_solution = self.ask_ai_for_buffer_town(origin, destination, real_hours)
                print(f"\n   === AI ROUTE MODIFICATION ===\n{ai_solution}\n   =============================\n")
            else:
                print(f"   ✅ Itinerary Cleared.")
            print("-" * 60)
            
        # PRINT FINAL FINANCIAL TRIP SUMMARIES
        print(f"\n📊 === TOTAL TRIP FINANCIAL & LOGISTICAL SUMMARY ===")
        print(f"🚗 Total Driving Distance: {self.total_miles:,.1f} miles")
        print(f"⛽ Total Estimated Fuel Cost: ${self.total_fuel_cost:,.2f}")
        print(f"🏠 Total Lodging Savings Identified: ${self.total_accommodation_savings:,.2f}")
        print(f"====================================================\n")

if __name__ == "__main__":
    # Synced with the "Revised Itinerary" tab of the trip spreadsheet
    # (36 days, Sep 6 - Oct 11, 2027). Must match route_list in app.py.
    route_list = [
        Waypoint(name="Atlanta, Georgia", latitude=33.7501, longitude=-84.3885),
        Waypoint(name="Birmingham, Alabama", latitude=33.5207, longitude=-86.8025),
        Waypoint(name="Memphis, Tennessee", latitude=35.1486, longitude=-90.0519),
        Waypoint(name="Springfield, Missouri", latitude=37.2090, longitude=-93.2923),
        Waypoint(name="Kansas City, Missouri", latitude=39.0997, longitude=-94.5786),
        Waypoint(name="Omaha, Nebraska", latitude=41.2565, longitude=-95.9345),
        Waypoint(name="Sioux Falls, South Dakota", latitude=43.5476, longitude=-96.7294),
        Waypoint(name="Pinnacles Overlook, Badlands SD", latitude=43.8697, longitude=-102.2331, is_national_park=True),
        Waypoint(name="Mount Rushmore, SD", latitude=43.8803, longitude=-103.4538),
        Waypoint(name="Sheridan, Wyoming", latitude=44.7972, longitude=-106.9562),
        Waypoint(name="Cody, Wyoming", latitude=44.5263, longitude=-109.0565),
        Waypoint(name="West Yellowstone, Montana", latitude=44.6632, longitude=-111.1012, is_national_park=True),
        Waypoint(name="Gardiner, Montana", latitude=45.0351, longitude=-110.7127, is_national_park=True),
        Waypoint(name="Jackson, Wyoming", latitude=43.4799, longitude=-110.7624),
        Waypoint(name="Salt Lake City, Utah", latitude=40.7606, longitude=-111.8881),
        Waypoint(name="Moab, Utah", latitude=38.5738, longitude=-109.5462, is_national_park=True),
        Waypoint(name="Blanding, Utah", latitude=37.6240, longitude=-109.4780),
        Waypoint(name="Grand Canyon Village, AZ", latitude=36.0544, longitude=-112.1401, is_national_park=True),
        Waypoint(name="Kanab, Utah", latitude=37.0475, longitude=-112.5263),
        Waypoint(name="Springdale, Utah", latitude=37.1945, longitude=-112.9570, is_national_park=True),
        Waypoint(name="Las Vegas, Nevada", latitude=36.1716, longitude=-115.1391),
        Waypoint(name="Furnace Creek (Death Valley), CA", latitude=36.4344, longitude=-116.8628, is_national_park=True),
        Waypoint(name="Tehachapi, California", latitude=35.1322, longitude=-118.4490),
        Waypoint(name="General Sherman Tree, CA (Sequoia)", latitude=36.5817, longitude=-118.7514, is_national_park=True),
        Waypoint(name="Yosemite Valley, CA", latitude=37.7456, longitude=-119.5936, is_national_park=True),
        Waypoint(name="Lee Vining, California", latitude=37.9628, longitude=-119.1207),
        Waypoint(name="South Lake Tahoe, California", latitude=38.9399, longitude=-119.9772),
        Waypoint(name="Martinez, California", latitude=38.0194, longitude=-122.1341)
    ]

    ai_engine = RoadTripPlannerAI(start_date=date(2027, 9, 6), end_date=date(2027, 10, 11))
    ai_engine.optimize_itinerary(route_list)