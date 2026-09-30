# Local Eats Agent

An AI agent that recommends local restaurants. You chat with it in plain English ("cheap vegetarian lunch near Midtown, open now"), and it searches real restaurant data with tool calls, remembers your lasting preferences, and explains why each pick fits your request.

Built with Python and the Anthropic Messages API (tool use). Runs offline on sample data out of the box, or on live data from the Google Places API.

```
You: somewhere good for a family dinner tonight, nothing too pricey

Agent: Here are two good fits:
1. Nonna's Kitchen ($$, 4.2) in Land Park: pasta and wood-oven pizza, kid-friendly,
   and it handles big groups well. Open until 9 PM.
2. Casa Marisol ($$, 4.4) in Midtown: big patio and a kid-friendly menu.
   Note: closed on Mondays.
```

## How it works

```
User message
    │
    ▼
┌──────────────────────────┐   tool_use    ┌────────────────────────────┐
│  RestaurantAgent (loop)  │ ────────────▶ │ ToolRunner                 │
│  - sends history + tools │               │  search_restaurants        │──▶ Provider
│  - runs requested tools  │ ◀──────────── │  get_restaurant_details    │    (sample JSON
│  - repeats until answer  │  tool_result  │  get_user_preferences      │     or Google Places)
└──────────────────────────┘               │  save_user_preference      │──▶ SQLite
    │                                      └────────────────────────────┘
    ▼
Final answer (2-3 picks, each with a reason)
```

1. The user's message and the tool definitions go to the model.
2. If the model asks for tools, the agent runs them and sends the results back.
3. This repeats until the model gives a final answer, with a hard step limit so it can't loop forever.

## Quick start

```bash
git clone https://github.com/harris9949sun/local-eats-agent.git
cd local-eats-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your ANTHROPIC_API_KEY

python -m local_eats.cli --verbose                  # offline sample data
python -m local_eats.cli --provider google \
    --location "Sacramento, CA" --verbose            # live data (needs GOOGLE_PLACES_API_KEY)
```

`--verbose` prints every tool call, which is the easiest way to see the agent reasoning step by step.

Chat commands: `/prefs` shows saved preferences, `/forget` clears them, `/reset` starts a new chat, `/quit` exits.

## Project layout

```
local_eats/
  agent.py      # agent loop, system prompt, step limit
  tools.py      # tool schemas the model sees + the code that runs them
  providers.py  # data sources: SampleDataProvider, GooglePlacesProvider
  memory.py     # SQLite preference store
  config.py     # settings from environment / .env
  cli.py        # interactive chat
data/sample_restaurants.json   # 12 fictional restaurants for offline use
tests/                         # unit tests, no API key needed
```

## Design decisions

**The model only recommends what the tools return.** The system prompt forbids inventing restaurants, hours, or prices. Every recommendation is grounded in a tool result, which is the main defense against hallucinated places.

**Data sources sit behind one interface.** The agent only knows `search()` and `details()`. Switching from sample data to Google Places is a flag, and adding Yelp or an internal database means writing one new class.

**Tool errors go back to the model instead of crashing.** A bad argument or an unknown restaurant id is returned as an error result, so the model can correct itself and try again.

**Preferences are saved only when stated.** "I'm vegetarian" is saved; "I feel like tacos tonight" isn't. Keys are limited to a fixed list (`dietary`, `budget`, `dislikes`, ...) so the model can't write arbitrary data.

**Plain code where plain code works.** Filtering, sorting by rating, and open-now checks are ordinary Python, not model calls. The model decides what to search for and explains the results; it doesn't do arithmetic on opening hours.

**Testable without an API key.** The model client is injected, so tests use a fake client with scripted responses. They cover the tool loop, tool-result ordering, error handling, and the step limit.

## Tests

```bash
pytest -q
```

GitHub Actions runs the tests on every push.

## Limitations and next steps

- Sample data is fictional and small. Use `--provider google` for real places.
- Google Places results are not cached. If you add caching, check Google's terms on storing Places data.
- Location is a fixed setting. A next step is geocoding the user's address and ranking by distance.
- No evaluation set yet. A good next step is a set of test requests with expected properties (e.g. "never recommends a closed place when the user says 'now'") scored automatically.
- Could add a small web UI (FastAPI + a simple frontend) on top of the same agent.

## License

MIT
