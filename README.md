# Hermes Lite — 最小 Agent 教案

> 这不是一个框架，是一份**可运行的教案**。~1,300 行 Python，9 个文件，讲清楚一个 Agent 的最小内核。

---

## 5 分钟快速跟读

**目标**：理解一个 Agent 如何从"收到用户消息"走到"调用工具并返回结果"。

**阅读顺序**（按依赖链，从底向上）：

```
registry.py  →  "工具长什么样？怎么找？"
deck.py      →  "一次对话，LLM 只能用哪些工具？"
agent.py     →  "怎么和 LLM 说话？怎么让它调用工具？"
main.py      →  "程序怎么启动？怎么交互？"
skills.py    →  "用户说一句话，怎么知道该加载什么工具？"
tools/       →  "一个工具到底怎么写？"
```

**跑起来**：

```bash
pip install anthropic openai
export HERMES_API_KEY=sk-...
export HERMES_PROVIDER=openai   # 或 anthropic
export HERMES_MODEL=gpt-4o      # 或 claude-sonnet-4
export HERMES_BASE_URL=         # 可选，第三方 API 需要

python main.py -m "hello"   # 连通测试
python main.py              # 进入交互模式
```

---

## 核心概念（按依赖链）

### 1. registry.py — 工具注册表

**一句话**：Agent 的所有工具都存在一个字典里，key 是名字，value 是"长什么样 + 怎么执行"。

**为什么需要它**：

没有注册表，你的工具就是散落在各处的函数。LLM 不知道有哪些工具可用，你也不知道该传哪些工具的 schema 给 LLM。注册表是**人和 LLM 之间的翻译层**。

```python
registry.register(
    name="fs_read_file",
    description="Read a file from disk",
    parameters={
        "properties": {
            "path": {"type": "string", "description": "Absolute file path"}
        },
        "required": ["path"]
    },
    handler=read_file_handler,
    category="filesystem"
)
```

**关键设计**：
- `generation` 计数器：每注册/注销一个工具就 +1，让 agent.py 的 schema 缓存知道" registry 变了，该刷新了"
- `get_schemas(enabled=[...])`：只返回指定名字的工具的 schema，这是 Deck 的基础
- `call(name, args)`：根据名字找到 handler，传参执行，返回字符串结果

**思考题**：为什么 `register()` 要把 schema 和 handler 绑在一起？如果分开存会有什么麻烦？

---

### 2. deck.py — 工具边界

**一句话**：每次对话前，从注册表里**挑出一部分工具**组成一个不可变的列表，LLM 只能从这个列表里选。

**为什么需要它**：

如果你把全部 50 个工具都塞给 LLM，它会糊涂——"用户让我写代码，我可以用发邮件的工具吗？" Deck 就是**约束条件**：这次对话，你只准用这些工具。

这是 Hermes Lite 最核心的设计决策之一：**工具不是全局可用的，是按上下文采购的**。

```python
# 从技能声明的工具 + 3 个冗余基础工具，构建一个 Deck
deck = build_deck(
    skill_tools=["net_web_search", "net_web_extract"],
    registry=registry,
    redundancy=3   # 固定 +3 个基础工具槽
)
```

**关键设计**：
- `Deck` 是不可变的：构建后不能增删，防止对话中途工具集突变
- `redundancy=3`：除了 skill 声明的工具，再从基础池子里按顺序填 3 个（比如 `fs_read_file`, `fs_search_files`, `sys_terminal`）。这是**保守的兜底**——万一 skill 漏声明了某个工具，常用的基础工具还在
- `get_schemas_for_protocol(protocol)`：同一个 Deck， Anthropic 协议和 OpenAI 协议的 schema 格式不同，在这里转换

**思考题**：`redundancy` 为什么要固定为 3，而不是动态计算？（提示：想想"可预测性 vs 灵活性"）

---

### 3. agent.py — 对话循环

**一句话**：把用户消息和工具 schema 发给 LLM，LLM 决定是**直接回答**还是**调用工具**；如果调用工具，执行工具并把结果塞回对话历史，再发一轮——直到 LLM 不再调用工具为止。

**核心循环**（伪代码）：

```python
for i in range(max_iterations):
    response = llm.chat(messages, tools=deck.schemas())
    
    if response 没有 tool_calls:
        return response.text          # 直接回答，结束
    
    # 有 tool_calls，逐个执行
    for tc in response.tool_calls:
        result = registry.call(tc.name, tc.arguments)
        messages.append({
            role: "tool",
            tool_call_id: tc.id,
            content: result
        })
    
    # 继续循环，把工具结果发回 LLM
```

**关键设计**：
- **双协议支持**：Anthropic 的 `messages.create(tools=...)` 和 OpenAI 的 `chat.completions.create(tools=...)` 格式不同，`_to_api_messages()` 负责统一转换
- **reasoning_content**：支持 thinking 模式的模型（如 kimi-k2.6）。如果 LLM 在 tool_calls 前输出了思考过程，必须把这个过程也传回给 LLM，否则会报 400 错误
- **max_iterations**：安全刹车。防止 LLM 无限循环调用工具

**思考题**：为什么工具执行结果要 append 到 `messages` 里，而不是覆盖上一轮？（提示：想想 LLM 的上下文窗口）

---

### 4. main.py — 入口和交互

**一句话**：读环境变量拿到配置，创建 Agent，然后要么 ping 一下模型，要么进入交互循环。

**交互循环的关键**（不是简单的 `while True`）：

```
用户输入 → skill 匹配 → 收集工具 → 构建 Deck → 注入 skill 上下文 → Agent.run() → 输出
```

每一轮对话都是**独立的 Deck 采购**。用户前一句说"搜索 AI 新闻"，Deck 里只有 web 工具；下一句说"读这个文件"，Deck 里换成文件工具。

**命令**：
- `/exit` — 退出
- `/tools` — 查看当前注册表里的所有工具
- `/skills` — 查看加载的所有 skill
- `/clear` — 清空对话历史

**思考题**：为什么 Deck 是每轮重新构建，而不是一开始就定死？（提示：想想"上下文相关性"）

---

### 5. skills.py — Skill 匹配和上下文注入

**一句话**：Skill 是一个 Markdown 文件，声明了"什么关键词触发我"和"我需要哪些工具"。SkillManager 负责加载这些文件、匹配用户输入、收集工具。

**一个 Skill 长什么样**（`skills/web-search.md`）：

```markdown
---
name: web-research
description: Search the web and summarize.
trigger: search, look up, research
tools:
  - net_web_search
  - net_web_extract
---

# Web Research

When the user wants to search for information...
```

**匹配逻辑**（简单但够用）：

```python
user_input = "帮我搜索一下最近的 AI 新闻"
triggers = ["search", "look up", "research"]

# 只要 triggers 中有任何一个词出现在 user_input 里，就匹配
if any(t in user_input.lower() for t in triggers):
    matched = True
```

**上下文注入**：匹配到 skill 后，把 skill 文件的正文（frontmatter 之后的内容）追加到 system prompt 里。这样 LLM 就知道"我现在扮演 web-research 专家，应该这样搜索、这样总结"。

**思考题**：trigger 匹配是字符串包含，不是语义理解。这有什么优势和劣势？什么时候会不够用？

---

### 6. tools/ — 写一个自己的工具

**一个最小工具只需要 3 样东西**：

```python
# tools/my_tool.py
from registry import registry

def my_handler(name: str) -> str:
    return f"Hello, {name}!"

registry.register(
    name="my_greeting",
    description="Greet someone by name",
    parameters={
        "properties": {
            "name": {"type": "string", "description": "Person's name"}
        },
        "required": ["name"]
    },
    handler=my_handler,
    category="demo"
)
```

**规则**：
- 文件放在 `tools/` 下，导入时自动注册
- `handler` 必须返回 `str`（会被截断到 8000 字符）
- `parameters` 遵循 JSON Schema，LLM 靠这个知道怎么填参数

**现有工具参考**：
- `tools/file.py` — 读、写、搜索文件（filesystem）
- `tools/terminal.py` — 执行 shell 命令（system）
- `tools/web.py` — 搜索网页、提取内容（network）

---

## 动手实验

### 实验 1：改 Deck 的冗余数

打开 `deck.py`，把 `redundancy=3` 改成 `redundancy=0` 或 `redundancy=6`。观察同样的输入，LLM 能用的工具有什么变化。

### 实验 2：加一个工具

在 `tools/` 下新建一个 `calculator.py`：

```python
from registry import registry

def calc(expr: str) -> str:
    try:
        return str(eval(expr))
    except Exception as e:
        return f"Error: {e}"

registry.register(
    name="calculator",
    description="Evaluate a math expression",
    parameters={
        "properties": {"expr": {"type": "string"}},
        "required": ["expr"]
    },
    handler=calc,
    category="math"
)
```

在 `main.py` 里 `import tools.calculator`，然后问 LLM "2+3*4 等于多少"。观察它是否调用了 `calculator`。

### 实验 3：写一个 Skill

在 `skills/` 下新建 `math-helper.md`：

```markdown
---
name: math-helper
description: Help with math problems
trigger: math, calculate, 计算
tools:
  - calculator
---

You are a math assistant. When users ask math questions, always use the calculator tool to verify your answer.
```

重启程序，输入"帮我计算一下 100 的阶乘"。观察 skill 是否被匹配，calculator 是否在 Deck 里。

---

## 设计原则（为什么这样设计）

| 原则 | 解释 |
|------|------|
| **注册表分离** | 工具的定义（schema）和执行（handler）在一起，但调用方（agent.py）只通过注册表交互，不直接 import 工具函数 |
| **Deck 边界** | 不是"给 LLM 全部工具让它自己选"，而是"根据上下文只给相关工具"——这降低了幻觉和跨域错误 |
| **不可变 Deck** | 一次对话的工具集在启动时就确定，中途不变，行为可预测 |
| **固定冗余** | +3 槽是硬编码的，不是动态的。简单、可预测，不需要配置系统 |
| **Skill = Markdown** | 触发条件、工具声明、系统提示都在一个文件里，人可读、git 可追踪、LLM 可解析 |
| **无数据库** | 所有状态都在文件里（环境变量、Markdown、文本输出）。没有隐藏的持久层 |

---

## 从 Hermes Lite 到 Worker Bee

Hermes Lite 是**教案**——理解原理后，你可以：
- 在 Hermes Lite 上修改、实验、验证想法
- 如果需要更多功能（cron、job board、多 skill 生态），去看 [Worker Bee](https://github.com/JuliaHZhu/worker-bee)

Worker Bee 不是 Hermes Lite 的升级版，它是**同一套原理的工程实现**。

---

## License

MIT