# Hermes Lite

> From Hermes we took skills. We added Deck. That's it.

A minimal AI agent framework. ~1,300 lines of Python. 9 files.

## 是什么

```
agent.py      225 行   双协议 Agent 循环（Anthropic / OpenAI）
registry.py   190 行   工具注册中心
skills.py     256 行   Skill 加载 + trigger 匹配
deck.py       106 行   不可变工具栈
main.py       137 行   CLI 入口
tools/                fs_read_file, fs_write_file, fs_search_files,
                      sys_terminal, net_web_search, net_web_extract
skills/               （空目录，用户自己写 skill 文件）
```

## 不是什么

- 不是 Worker Bee（没有 cron、没有 job supervisor、没有飞书推送）
- 不是 Claude Code（没有 sandbox、没有 TUI、没有 MCP）
- 不是 LangChain（没有 chain、没有 prompt template、没有 RAG 抽象）

就一个 Agent + 工具注册 + Skill 匹配 + Deck 装填。

## 30 秒跑起来

```bash
pip install anthropic openai

export HERMES_API_KEY=sk-...
export HERMES_MODEL=claude-sonnet-4-20250514  # optional

python main.py -m "hello world"   # ping 测试
python main.py                     # 开始对话
```

## 核心概念

### Skill = 契约

```yaml
---
name: web-research
description: Search the web and summarize findings.
trigger: search, look up, research, find online
tools:
  - net_web_search
  - net_web_extract
---
```

### Deck = 运行时工具边界

```
用户输入 → trigger 匹配 → 收集 skills 声明的 tools → Deck 装填 → LLM 只能从 Deck 里抽工具
```

所有工具都在 Registry 里，但 LLM 每次任务只能看到 Deck 里的那几个。不会用写文件工具去查天气。

## 架构

```
main.py (CLI)
    │
    ├─ SkillManager.match_skills(user_input)
    │       │
    │       └─ matched skills → get_tools_for_skills()
    │               │
    │               └─ skill_tools → build_deck() → Deck
    │
    └─ AIAgent.run(messages, deck=deck)
            │
            ├─ LLM API call (Anthropic or OpenAI)
            ├─ tool_calls? → registry.call(name, args) → loop
            └─ text → return to user
```

## License

MIT
