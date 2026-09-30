"""The agent loop.

1. Send the conversation + tool definitions to the model.
2. If the model asks for tools, run them and send the results back.
3. Repeat until the model gives a final answer (or we hit a step limit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .tools import TOOL_DEFINITIONS, ToolRunner

SYSTEM_PROMPT = """You are a local restaurant guide for {location}. Today is {now}.

How to work:
- Start by calling get_user_preferences and respect what's saved (dietary needs, budget, dislikes).
- Use search_restaurants to find options. Only recommend restaurants that came back from a tool.
  Never invent restaurants, hours, or prices.
- If a search returns nothing, loosen one filter and try again before giving up.
- Use get_restaurant_details when hours or specifics matter to the user's request.
- If the user states a lasting preference ("I'm vegetarian", "I hate spicy food"), save it.
- If the request is too vague to search well, ask one short clarifying question.

Answer format:
- Recommend 2-3 places. For each: name, price ($-$$$$), rating, and one line on
  why it fits THIS request.
- Mention if a place is closed right now or needs a reservation.
- Keep it short and friendly."""


@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stopped_early: bool = False


class RestaurantAgent:
    def __init__(self, client, tools: ToolRunner, model: str, location: str,
                 max_steps: int = 8, max_tokens: int = 1024, clock=datetime.now):
        self.client = client  # anthropic.Anthropic() or a fake in tests
        self.tools = tools
        self.model = model
        self.location = location
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.clock = clock
        self.history: list[dict[str, Any]] = []

    def _system(self) -> str:
        now = self.clock().strftime("%A %B %d, %Y, %I:%M %p")
        return SYSTEM_PROMPT.format(location=self.location, now=now)

    def ask(self, user_message: str) -> AgentResult:
        self.history.append({"role": "user", "content": user_message})
        tool_log: list[dict[str, Any]] = []

        for _ in range(self.max_steps):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self._system(),
                tools=TOOL_DEFINITIONS,
                messages=self.history,
            )
            self.history.append({"role": "assistant", "content": _to_params(response.content)})

            if response.stop_reason != "tool_use":
                text = "".join(b.text for b in response.content if b.type == "text").strip()
                return AgentResult(text=text, tool_calls=tool_log)

            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                output, is_error = self.tools.run(block.name, block.input)
                tool_log.append({"name": block.name, "input": block.input, "error": is_error})
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                    "is_error": is_error,
                })
            self.history.append({"role": "user", "content": results})

        # Step limit reached: close the turn so user/assistant roles keep alternating.
        text = "Sorry, I couldn't finish that search. Could you try a simpler request?"
        self.history.append({"role": "assistant", "content": [{"type": "text", "text": text}]})
        return AgentResult(text=text, tool_calls=tool_log, stopped_early=True)

    def reset(self) -> None:
        self.history.clear()


def _to_params(blocks) -> list[dict[str, Any]]:
    """Convert response blocks into plain dicts we can send back next turn."""
    params = []
    for b in blocks:
        if b.type == "text":
            params.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            params.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return params
