# Worker Bee

> Worker bee, not swiss army knife. **One Agent + One Board.**

A minimal AI agent framework. ~1,300 lines of Python. 9 files.

## What's inside

```
agent.py       Dual-protocol agent loop (Anthropic / OpenAI)
registry.py    Tool registry — name, description, parameters, handler
skills.py      Skill loader — YAML frontmatter + trigger matching
deck.py        Immutable tool boundary — the Deck
main.py        CLI — ping and interactive chat
tools/         read, write, search files · terminal · web search
skills/        Add your skill .md files here
```

## 30 seconds

```bash
pip install anthropic openai
export HERMES_API_KEY=sk-...
python main.py -m "hello world"   # ping
python main.py                     # chat
```

## Concepts

### Skill

A skill declares **when** to activate and **what** tools it needs:

```yaml
---
name: web-research
description: Search the web and summarize.
trigger: search, look up, research
tools:
  - net_web_search
  - net_web_extract
---
```

### Deck

The Deck is an immutable, pre-procured tool set. Before each turn, Worker Bee matches skills against your input, collects their declared tools, and builds a Deck. The LLM can only use tools in the Deck — no cross-domain mistakes.

```
your input → trigger match → collect tools → build Deck → LLM runs inside the Deck
```

## Design

- **Human-in-loop**: Worker bee executes; you supervise. No autonomous orchestration.
- **Exogenous pheromone**: All state is human-readable text (Markdown). No hidden databases.
- **Fixed patterns over dynamic config**: The Deck adds a fixed +3 redundancy slot. Predictable beats flexible.

## Config

All via environment variables:

| Variable | Required | Default |
|----------|----------|---------|
| `HERMES_API_KEY` | yes | — |
| `HERMES_PROVIDER` | no | `anthropic` |
| `HERMES_MODEL` | no | `claude-sonnet-4-20250514` |
| `HERMES_BASE_URL` | no | — |

## License

MIT
