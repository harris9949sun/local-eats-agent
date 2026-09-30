"""Interactive command-line chat.

    python -m local_eats.cli                    # offline sample data
    python -m local_eats.cli --provider google  # live Google Places data
"""

from __future__ import annotations

import argparse
import sys

from anthropic import Anthropic

from .agent import RestaurantAgent
from .config import Settings
from .memory import PreferenceStore
from .providers import GooglePlacesProvider, SampleDataProvider
from .tools import ToolRunner

HELP = "Commands: /prefs (show saved preferences), /forget (clear them), /reset (new chat), /quit"


def build_agent(settings: Settings, provider_name: str, location: str):
    if provider_name == "google":
        if not settings.google_api_key:
            sys.exit("GOOGLE_PLACES_API_KEY is not set. Use --provider sample or add the key to .env.")
        provider = GooglePlacesProvider(settings.google_api_key, location)
    else:
        provider = SampleDataProvider()
    prefs = PreferenceStore(settings.db_path)
    agent = RestaurantAgent(Anthropic(), ToolRunner(provider, prefs), settings.model, location)
    return agent, prefs


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(description="Chat with a local restaurant agent.")
    parser.add_argument("--provider", choices=["sample", "google"], default=settings.provider)
    parser.add_argument("--location", default=settings.location)
    parser.add_argument("--verbose", action="store_true", help="Show which tools the agent calls.")
    args = parser.parse_args()

    agent, prefs = build_agent(settings, args.provider, args.location)
    print(f"Local Eats Agent ({args.provider} data, {args.location})")
    print(HELP)

    while True:
        try:
            user = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user == "/quit":
            break
        if user == "/prefs":
            print(prefs.get_all() or "No saved preferences.")
            continue
        if user == "/forget":
            prefs.clear()
            print("Preferences cleared.")
            continue
        if user == "/reset":
            agent.reset()
            print("Started a new chat.")
            continue

        result = agent.ask(user)
        if args.verbose:
            for call in result.tool_calls:
                flag = " (error)" if call["error"] else ""
                print(f"  [tool] {call['name']} {call['input']}{flag}")
        print(f"\nAgent: {result.text}")


if __name__ == "__main__":
    main()
