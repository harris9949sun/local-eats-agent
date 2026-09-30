import json

import pytest

from local_eats.memory import PreferenceStore
from local_eats.providers import SampleDataProvider
from local_eats.tools import ToolRunner


@pytest.fixture
def runner(tmp_path):
    return ToolRunner(SampleDataProvider(), PreferenceStore(tmp_path / "p.db"))


def test_preferences_persist_and_update(tmp_path):
    db = tmp_path / "p.db"
    PreferenceStore(db).save("dietary", "vegetarian")
    store = PreferenceStore(db)
    store.save("dietary", "vegan")
    assert store.get_all() == {"dietary": "vegan"}


def test_unknown_preference_key_rejected(tmp_path):
    with pytest.raises(ValueError):
        PreferenceStore(tmp_path / "p.db").save("shoe_size", "10")


def test_tool_errors_are_returned_not_raised(runner):
    output, is_error = runner.run("search_restaurants", {"bad_arg": 1})
    assert is_error and "error" in json.loads(output)

    output, is_error = runner.run("no_such_tool", {})
    assert is_error


def test_save_then_read_preferences_through_tools(runner):
    runner.run("save_user_preference", {"key": "budget", "value": "under $20"})
    output, is_error = runner.run("get_user_preferences", {})
    assert not is_error and json.loads(output) == {"budget": "under $20"}
