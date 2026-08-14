from types import SimpleNamespace

from route_utils import (
    build_route_selection,
    build_scenario_comparison,
    recommend_route_style,
    recommend_overnight_stop,
    recommend_toddler_break,
    recommend_activity_stop,
    recommend_lunch_break,
    recommend_diaper_break,
)


def test_build_route_selection_filters_to_selected_names():
    stops = [
        SimpleNamespace(name="Atlanta"),
        SimpleNamespace(name="Memphis"),
        SimpleNamespace(name="Kansas City"),
    ]

    selected = build_route_selection(stops, ["Atlanta", "Kansas City"])

    assert [item.name for item in selected] == ["Atlanta", "Kansas City"]


def test_build_route_selection_returns_empty_when_nothing_selected():
    stops = [SimpleNamespace(name="Atlanta")]

    selected = build_route_selection(stops, [])

    assert selected == []


def test_build_scenario_comparison_returns_fast_and_scenic_totals():
    stops = [
        SimpleNamespace(name="A", latitude=0.0, longitude=0.0),
        SimpleNamespace(name="B", latitude=1.0, longitude=1.0),
        SimpleNamespace(name="C", latitude=2.0, longitude=2.0),
    ]

    def distance_fn(o_name, o_lat, o_lon, d_name, d_lat, d_lon, scenic_mode):
        return (100.0 if not scenic_mode else 120.0, 2.0 if not scenic_mode else 3.0)

    comparison = build_scenario_comparison(stops, distance_fn)

    assert comparison["Fast"] == {"miles": 200.0, "hours": 4.0}
    assert comparison["Scenic"] == {"miles": 240.0, "hours": 6.0}


def test_recommend_route_style_prefers_scenic_when_budget_is_comfortable():
    scenarios = {"Fast": {"miles": 200.0, "hours": 8.0}, "Scenic": {"miles": 220.0, "hours": 10.0}}

    recommendation = recommend_route_style(scenarios, budget_tolerance=3000)

    assert recommendation["recommendation"] == "Scenic"
    assert recommendation["extra_hours"] == 2.0


def test_recommend_route_style_prefers_fast_when_budget_is_tight():
    scenarios = {"Fast": {"miles": 200.0, "hours": 8.0}, "Scenic": {"miles": 260.0, "hours": 12.0}}

    recommendation = recommend_route_style(scenarios, budget_tolerance=900)

    assert recommendation["recommendation"] == "Fast"
    assert recommendation["extra_miles"] == 60.0


def test_recommend_overnight_stop_uses_the_longest_leg():
    stops = [
        SimpleNamespace(name="A"),
        SimpleNamespace(name="B"),
        SimpleNamespace(name="C"),
        SimpleNamespace(name="D"),
    ]

    recommendation = recommend_overnight_stop(stops, [2.0, 6.0, 3.0])

    assert recommendation == "C"


def test_recommend_overnight_stop_chooses_latest_longest_leg_when_tied():
    stops = [
        SimpleNamespace(name="A"),
        SimpleNamespace(name="B"),
        SimpleNamespace(name="C"),
        SimpleNamespace(name="D"),
    ]

    recommendation = recommend_overnight_stop(stops, [5.0, 5.0, 4.0])

    assert recommendation == "C"


def test_recommend_toddler_break_prefers_family_friendly_stop():
    stops = [
        SimpleNamespace(name="Memphis, Tennessee"),
        SimpleNamespace(name="Kansas City, Missouri"),
        SimpleNamespace(name="Sheridan, Wyoming"),
    ]

    recommendation = recommend_toddler_break(stops)

    assert recommendation == "Kansas City, Missouri"


def test_recommend_activity_stop_prefers_nature_destination():
    stops = [
        SimpleNamespace(name="Memphis, Tennessee"),
        SimpleNamespace(name="Mount Rushmore, SD"),
        SimpleNamespace(name="Sheridan, Wyoming"),
    ]

    recommendation = recommend_activity_stop(stops)

    assert recommendation == "Mount Rushmore, SD"


def test_recommend_activity_stop_prefers_central_park_like_destination():
    stops = [
        SimpleNamespace(name="Memphis, Tennessee"),
        SimpleNamespace(name="Pinnacles Overlook, Badlands SD"),
        SimpleNamespace(name="Mount Rushmore, SD"),
        SimpleNamespace(name="Jackson, Wyoming"),
    ]

    recommendation = recommend_activity_stop(stops)

    assert recommendation == "Mount Rushmore, SD"


def test_recommend_lunch_break_prefers_midday_stop():
    stops = [
        SimpleNamespace(name="Memphis, Tennessee"),
        SimpleNamespace(name="Sheridan, Wyoming"),
        SimpleNamespace(name="Yosemite Valley, CA"),
    ]

    recommendation = recommend_lunch_break(stops)

    assert recommendation == "Memphis, Tennessee"


def test_recommend_lunch_break_prefers_central_midday_stop():
    stops = [
        SimpleNamespace(name="Memphis, Tennessee"),
        SimpleNamespace(name="Kansas City, Missouri"),
        SimpleNamespace(name="Sioux Falls, South Dakota"),
        SimpleNamespace(name="Jackson, Wyoming"),
    ]

    recommendation = recommend_lunch_break(stops)

    assert recommendation == "Sioux Falls, South Dakota"


def test_recommend_diaper_break_prefers_toddler_reset_stop():
    stops = [
        SimpleNamespace(name="Memphis, Tennessee"),
        SimpleNamespace(name="Jackson, Wyoming"),
        SimpleNamespace(name="Sheridan, Wyoming"),
    ]

    recommendation = recommend_diaper_break(stops)

    assert recommendation == "Jackson, Wyoming"


def test_recommend_diaper_break_prefers_central_diaper_reset_stop():
    stops = [
        SimpleNamespace(name="Memphis, Tennessee"),
        SimpleNamespace(name="Kansas City, Missouri"),
        SimpleNamespace(name="Mount Rushmore, SD"),
        SimpleNamespace(name="Sheridan, Wyoming"),
    ]

    recommendation = recommend_diaper_break(stops)

    assert recommendation == "Mount Rushmore, SD"
