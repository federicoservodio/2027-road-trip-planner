def build_route_selection(waypoints, selected_names):
    if not selected_names:
        return []

    selected = {name for name in selected_names if name}
    return [wp for wp in waypoints if wp.name in selected]


def build_scenario_comparison(waypoints, distance_fn):
    if len(waypoints) < 2:
        return {
            "Fast": {"miles": 0.0, "hours": 0.0},
            "Scenic": {"miles": 0.0, "hours": 0.0},
        }

    scenarios = {}
    for label, scenic_mode in (("Fast", False), ("Scenic", True)):
        total_miles = 0.0
        total_hours = 0.0
        for origin, destination in zip(waypoints, waypoints[1:]):
            miles, hours = distance_fn(
                origin.name,
                origin.latitude,
                origin.longitude,
                destination.name,
                destination.latitude,
                destination.longitude,
                scenic_mode,
            )
            total_miles += miles
            total_hours += hours

        scenarios[label] = {
            "miles": round(total_miles, 1),
            "hours": round(total_hours, 1),
        }

    return scenarios


def recommend_route_style(scenarios, budget_tolerance=1500):
    fast = scenarios.get("Fast", {})
    scenic = scenarios.get("Scenic", {})

    fast_hours = fast.get("hours", 0.0)
    scenic_hours = scenic.get("hours", 0.0)
    scenic_miles = scenic.get("miles", 0.0)
    fast_miles = fast.get("miles", 0.0)

    extra_hours = round(scenic_hours - fast_hours, 1)
    extra_miles = round(scenic_miles - fast_miles, 1)

    if budget_tolerance >= 2000:
        return {
            "recommendation": "Scenic",
            "reason": "Budget is comfortable enough to prioritize the more memorable route.",
            "extra_hours": extra_hours,
            "extra_miles": extra_miles,
        }

    if extra_miles > 80.0:
        return {
            "recommendation": "Fast",
            "reason": "The scenic detour adds too much distance for a tighter budget.",
            "extra_hours": extra_hours,
            "extra_miles": extra_miles,
        }

    return {
        "recommendation": "Fast",
        "reason": "A shorter route keeps fuel and day-to-day costs lower.",
        "extra_hours": extra_hours,
        "extra_miles": extra_miles,
    }


def recommend_overnight_stop(waypoints, leg_hours):
    if len(waypoints) < 2:
        return None

    if not leg_hours:
        return waypoints[1].name

    longest_leg_index = max(range(len(leg_hours)), key=lambda index: (leg_hours[index], index))
    return waypoints[longest_leg_index + 1].name


def recommend_toddler_break(waypoints):
    if not waypoints:
        return None

    toddler_friendly = [
        "Kansas City, Missouri",
        "Omaha, Nebraska",
        "Sioux Falls, South Dakota",
        "Mount Rushmore, SD",
        "Cody, Wyoming",
        "Jackson, Wyoming",
        "Salt Lake City, Utah",
        "Grand Canyon Village, AZ",
        "Las Vegas, Nevada",
        "Yosemite Valley, CA",
        "South Lake Tahoe, California",
    ]

    for waypoint in waypoints:
        if waypoint.name in toddler_friendly:
            return waypoint.name

    return waypoints[0].name


def recommend_activity_stop(waypoints):
    if not waypoints:
        return None

    park_like = [
        "Pinnacles Overlook, Badlands SD",
        "Mount Rushmore, SD",
        "West Yellowstone, Montana",
        "Gardiner, Montana",
        "Moab, Utah",
        "Grand Canyon Village, AZ",
        "Springdale, Utah",
        "Yosemite Valley, CA",
        "South Lake Tahoe, California",
    ]

    candidates = [
        (index, waypoint)
        for index, waypoint in enumerate(waypoints)
        if waypoint.name in park_like
    ]

    if candidates:
        midpoint = (len(waypoints) - 1) / 2.0

        def candidate_score(index, name):
            # Prefer stops closest to the trip midpoint, and if two are equally central,
            # choose the later one so the suggested activity stop remains on the second half
            # of the journey rather than the first.
            return (abs(index - midpoint), -index)

        best_index, best_waypoint = min(
            candidates, key=lambda item: candidate_score(item[0], item[1].name)
        )
        return best_waypoint.name

    return waypoints[len(waypoints) // 2].name


def recommend_lunch_break(waypoints):
    if not waypoints:
        return None

    lunch_friendly = [
        "Memphis, Tennessee",
        "Kansas City, Missouri",
        "Sioux Falls, South Dakota",
        "Jackson, Wyoming",
        "Salt Lake City, Utah",
        "Las Vegas, Nevada",
        "South Lake Tahoe, California",
    ]

    candidates = [
        (index, waypoint)
        for index, waypoint in enumerate(waypoints)
        if waypoint.name in lunch_friendly
    ]

    if candidates:
        midpoint = (len(waypoints) - 1) / 2.0

        def candidate_score(index):
            return (abs(index - midpoint), -index)

        best_index, best_waypoint = min(
            candidates, key=lambda item: candidate_score(item[0])
        )
        return best_waypoint.name

    return waypoints[len(waypoints) // 2].name


def recommend_diaper_break(waypoints):
    if not waypoints:
        return None

    diaper_friendly = [
        "Kansas City, Missouri",
        "Omaha, Nebraska",
        "Mount Rushmore, SD",
        "Cody, Wyoming",
        "Jackson, Wyoming",
        "Salt Lake City, Utah",
        "Grand Canyon Village, AZ",
        "Yosemite Valley, CA",
    ]

    candidates = [
        (index, waypoint)
        for index, waypoint in enumerate(waypoints)
        if waypoint.name in diaper_friendly
    ]

    if candidates:
        midpoint = (len(waypoints) - 1) / 2.0

        def candidate_score(index):
            return (abs(index - midpoint), -index)

        best_index, best_waypoint = min(
            candidates, key=lambda item: candidate_score(item[0])
        )
        return best_waypoint.name

    return waypoints[len(waypoints) // 2].name
