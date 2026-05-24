# Worker Bee

> Worker bee, not swiss army knife. **One Agent + One Board。**

最小 AI Agent 框架。~1,300 行 Python。9 个文件。

## 里面有什么

```
agent.py       Agent 循环（Anthropic / OpenAI 双协议）
registry.py    工具注册中心 — name、description、parameters、handler
skills.py      Skill 加载 — YAML frontmatter + trigger 匹配
deck.py        不可变工具边界 — Deck
main.py        CLI — ping 测试 + 交互对话
tools/         文件读写搜索 · 终端 · 网页搜索
skills/        在这里放你的 skill .md 文件
```

## 30 秒跑起来

```bash
pip install anthropic openai
export HERMES_API_KEY=sk-...
python main.py -m "hello world"   # 测试连通
python main.py                     # 开始对话
```

## 概念

### Skill

一个 Skill 声明了**什么时候激活**、**需要什么工具**：

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

Deck 是一个不可变的、预先装填的工具集。每次对话前，Worker Bee 用 trigger 匹配你的输入，收集匹配到的 skill 声明的工具，装填成 Deck。LLM 只能用 Deck 里的工具——不会用写文件工具去查天气，不会用终端工具去发消息。

```
你的输入 → trigger 匹配 → 收集工具 → 装填 Deck → LLM 在 Deck 边界内执行
```

## 设计思想

- **监工模型**：Worker bee 干活，你来监督。不自动编排，人在回路中。
- **外源信息素**：所有状态都是人类可读的文本（Markdown），没有隐藏的数据库。
- **固定优先于动态**：Deck 冗余只有固定的 +3 卡槽。可预测比灵活更重要。

## 配置

全部通过环境变量：

| 变量 | 必须 | 默认值 |
|------|------|--------|
| `HERMES_API_KEY` | 是 | — |
| `HERMES_PROVIDER` | 否 | `anthropic` |
| `HERMES_MODEL` | 否 | `claude-sonnet-4-20250514` |
| `HERMES_BASE_URL` | 否 | — |

## License

MIT
