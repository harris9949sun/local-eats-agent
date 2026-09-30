from datetime import datetime

from local_eats.providers import SampleDataProvider, is_open

# A Tuesday at 12:30 PM and a Monday at 12:30 PM
TUE_LUNCH = datetime(2026, 9, 29, 12, 30)
MON_LUNCH = datetime(2026, 9, 28, 12, 30)


def provider(now=TUE_LUNCH):
    return SampleDataProvider(clock=lambda: now)


def test_is_open_handles_closed_days_and_midnight():
    hours = {"mon": "closed", "fri": "08:00-24:00"}
    assert not is_open(hours, MON_LUNCH)
    assert is_open(hours, datetime(2026, 10, 2, 23, 45))  # Friday 11:45 PM


def test_filters_by_cuisine_and_price():
    results = provider().search(cuisine="mexican", max_price=1)
    assert [r["name"] for r in results] == ["Taqueria El Sol"]


def test_results_sorted_by_rating():
    ratings = [r["rating"] for r in provider().search(limit=10)]
    assert ratings == sorted(ratings, reverse=True)


def test_open_now_excludes_closed_places():
    names = {r["name"] for r in provider(MON_LUNCH).search(open_now=True, limit=20)}
    assert "Casa Marisol" not in names  # closed Mondays
    assert "Golden Lotus Noodle House" in names


def test_tags_must_all_match():
    results = provider().search(tags=["vegetarian_friendly", "vegan_options"], limit=10)
    assert {r["name"] for r in results} == {"Green Table", "Spice Route"}


def test_details_unknown_id_returns_none():
    assert provider().details("nope") is None
