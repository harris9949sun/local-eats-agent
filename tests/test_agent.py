"""Agent loop tests with a fake model client, so no API key is needed."""

import copy
from types import SimpleNamespace as NS

from local_eats.agent import RestaurantAgent
from local_eats.memory import PreferenceStore
from local_eats.providers import SampleDataProvider
from local_eats.tools import ToolRunner


def tool_use(id_, name, input_):
    return NS(type="tool_use", id=id_, name=name, input=input_)


def text(t):
    return NS(type="text", text=t)


class FakeClient:
    """Returns scripted responses and records what it was sent."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        # Deep copy: the agent keeps appending to the same history list.
        self.calls.append(copy.deepcopy(kwargs))
        return self.responses.pop(0)


def make_agent(client, tmp_path, max_steps=8):
    tools = ToolRunner(SampleDataProvider(), PreferenceStore(tmp_path / "p.db"))
    return RestaurantAgent(client, tools, model="test-model", location="Sacramento, CA",
                           max_steps=max_steps)


def test_runs_tools_then_returns_answer(tmp_path):
    client = FakeClient([
        NS(stop_reason="tool_use", content=[
            text("Let me check."),
            tool_use("t1", "get_user_preferences", {}),
            tool_use("t2", "search_restaurants", {"cuisine": "Vietnamese"}),
        ]),
        NS(stop_reason="end_turn", content=[text("Try Pho Saigon Corner.")]),
    ])
    agent = make_agent(client, tmp_path)
    result = agent.ask("cheap pho?")

    assert result.text == "Try Pho Saigon Corner."
    assert [c["name"] for c in result.tool_calls] == ["get_user_preferences", "search_restaurants"]

    # Second request must include both tool results, matched by id.
    tool_results = client.calls[1]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in tool_results] == ["t1", "t2"]
    assert "Pho Saigon Corner" in tool_results[1]["content"]


def test_step_limit_stops_loop_and_keeps_roles_alternating(tmp_path):
    looping = NS(stop_reason="tool_use", content=[tool_use("t", "get_user_preferences", {})])
    client = FakeClient([looping] * 3)
    agent = make_agent(client, tmp_path, max_steps=3)
    result = agent.ask("anything")

    assert result.stopped_early
    roles = [m["role"] for m in agent.history]
    assert all(a != b for a, b in zip(roles, roles[1:]))
    assert roles[-1] == "assistant"


def test_tool_error_is_sent_back_to_model(tmp_path):
    client = FakeClient([
        NS(stop_reason="tool_use", content=[tool_use("t1", "get_restaurant_details", {"restaurant_id": "x"})]),
        NS(stop_reason="end_turn", content=[text("I couldn't find that one.")]),
    ])
    make_agent(client, tmp_path).ask("details for x")
    result_block = client.calls[1]["messages"][-1]["content"][0]
    assert result_block["is_error"] is True
