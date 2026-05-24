#!/usr/bin/env python3
"""Hermes Lite — minimal AI agent with Skill + Deck.

Usage:
    python main.py              Start interactive session
    python main.py -m "hello"   Quick model ping test

Config via env vars:
    HERMES_API_KEY              API key (required)
    HERMES_PROVIDER             anthropic (default) or openai
    HERMES_MODEL                model name
    HERMES_BASE_URL             optional base URL override
"""

import argparse, os, sys

import tools.file, tools.terminal, tools.web  # auto-register on import

from agent import AIAgent
from registry import registry
from skills import SkillManager
from deck import build_deck

VERSION = "0.1.0"


def load_config():
    key = os.environ.get("HERMES_API_KEY")
    if not key:
        return None
    return {
        "provider": os.environ.get("HERMES_PROVIDER", "anthropic"),
        "model": os.environ.get("HERMES_MODEL", "claude-sonnet-4-20250514"),
        "api_key": key,
        "base_url": os.environ.get("HERMES_BASE_URL"),
        "max_iterations": 20,
        "system_prompt": (
            "You are a helpful assistant with tool access. "
            "Think step by step. Prefer reading before editing."
        ),
    }


def ping(message):
    config = load_config()
    if not config:
        sys.exit("❌ Set HERMES_API_KEY first.")
    print(f"→ Pinging {config['model']}...")
    agent = AIAgent(config)
    try:
        print("← " + agent.run([{"role": "user", "content": message}]))
    except Exception as e:
        sys.exit(f"❌ {e}")


def run_session():
    config = load_config()
    if not config:
        sys.exit("❌ Set HERMES_API_KEY env var.\n"
                 "  export HERMES_API_KEY=sk-...\n"
                 "  export HERMES_MODEL=claude-sonnet-4-20250514  # optional")

    agent = AIAgent(config)
    skill_mgr = SkillManager()
    base_prompt = agent.system_prompt

    loaded = skill_mgr.load_all()
    print(f"✨ Hermes Lite — {config['model']} ({config['provider']})")
    print(f"   {len(loaded)} skill(s), {len(registry.list_tools())} tools")
    print("   /exit /tools /skills /clear /help")
    print("-" * 50)

    messages = []
    while True:
        try:
            ui = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!"); break

        if not ui: continue
        if ui.lower() in ("/exit", "exit", "quit"): break
        if ui.lower() == "/help":
            print("Commands: /exit, /tools, /skills, /clear, /help"); continue
        if ui.lower() == "/tools":
            for cat, names in sorted(registry.list_by_category().items()):
                print(f"  [{cat}] {', '.join(names)}"); continue
        if ui.lower() == "/skills":
            skills = skill_mgr.list_skills()
            if skills:
                for name, meta in skills.items():
                    t = f"  triggers: {', '.join(meta.get('triggers',[]))}" if meta.get("triggers") else ""
                    tl = f"  tools: {', '.join(meta.get('tools',[]))}" if meta.get("tools") else ""
                    print(f"  • {name}: {meta.get('description','')}{t}{tl}")
            else:
                print("No skills. Add .md files to skills/"); continue
        if ui.lower() == "/clear":
            messages = []; print("Cleared."); continue

        # Deck procurement
        matched = skill_mgr.match_skills(ui) or list(skill_mgr.list_skills().keys())
        skill_tools = skill_mgr.get_tools_for_skills(matched)
        deck = build_deck(skill_tools, registry, redundancy=3)

        # Skill context
        ctx = skill_mgr.build_context_for_skills(matched)
        if ctx:
            agent.system_prompt = f"{base_prompt}\n\n{ctx}"

        messages.append({"role": "user", "content": ui})
        print("\nAgent: ", end="", flush=True)
        try:
            resp = agent.run(messages, deck=deck)
        except Exception as e:
            resp = f"Error: {e}"
        finally:
            agent.system_prompt = base_prompt

        if resp == "(reached max iterations)":
            print(f"{resp}\n⚠️  Deck may be insufficient.")
            messages.append({"role": "assistant", "content": resp}); continue

        print(resp)
        messages.append({"role": "assistant", "content": resp})


def main():
    p = argparse.ArgumentParser(prog="hermes-lite", add_help=False)
    p.add_argument("-m", "--ping", metavar="MSG")
    p.add_argument("-v", "--version", action="store_true")
    p.add_argument("-h", "--help", action="store_true")
    args = p.parse_args()

    if args.version:      print(f"hermes-lite {VERSION}")
    elif args.help:       print(__doc__)
    elif args.ping:       ping(args.ping)
    else:                 run_session()


if __name__ == "__main__":
    main()
