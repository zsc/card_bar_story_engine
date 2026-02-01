# CardBar Story Engine (CBSE) - 卡牌叙事引擎

基于 Python + Textual 的 AI 叙事游戏引擎（MVP）。

核心特色：**状态栏（Status Bar）+ 变量卡（Variable Cards）** 驱动的 AI 剧情游戏引擎。LLM 负责生成叙事与建议选项，但所有状态更新必须经过结构化校验后才生效。

---

## 快速开始

```bash
python -m cbse
```

默认使用 Mock LLM（离线可用）。

运行特定游戏：

```bash
python -m cbse --game polish_solider
```

---

## 核心算法与机制

### 1. 回合循环（Turn Loop）

```
玩家输入 → Prompt 构建 → LLM 生成 → Schema 校验 → 规则引擎处理 → 状态更新 → UI 渲染
```

每回合引擎执行以下步骤：

1. **Prompt 构建**：将世界设定、当前状态摘要、最近对话、触发器提示、玩家输入拼接成结构化 prompt
2. **LLM 生成**：AI 返回符合 JSON Schema 的结构化输出（叙事、选项、状态更新）
3. **Schema 校验**：验证 AI 输出是否符合 `LLMOutput` 结构
4. **规则引擎校验**：
   - 验证状态更新路径是否合法
   - 检查只读变量保护
   - 校验操作类型匹配（`inc/dec` 仅用于数字、`push/remove` 仅用于列表等）
5. **数值裁剪（Clamp）**：将数值变量限制在 `min/max` 范围内
6. **时间进位处理**：分钟 ≥60 自动进位到小时
7. **触发器执行**：检查所有触发器条件，执行副作用
8. **胜负判定**：检查 `win_conditions` / `lose_conditions`
9. **状态应用**：将变更写入 `StateStore`，记录历史

### 2. 状态更新协议（State Update Protocol）

LLM 必须通过 `state_updates` 数组表达所有变量变更：

```json
{
  "state_updates": [
    { "op": "set", "path": "location", "value": "旧电厂", "reason": "移动" },
    { "op": "inc", "path": "clues", "value": 1, "reason": "发现线索" },
    { "op": "push", "path": "truth_map", "value": "有人动过手脚", "reason": "记录事实" }
  ]
}
```

**操作符（op）规则**：

| 操作符 | 适用类型 | 说明 |
|--------|----------|------|
| `set` | 任意 | 直接设置值，需类型匹配 |
| `inc` | number/integer | 增加数值 |
| `dec` | number/integer | 减少数值 |
| `push` | list | 向列表末尾添加元素 |
| `remove` | list | 从列表移除元素（按值） |
| `toggle` | boolean | 布尔值取反 |

**可信边界**：LLM 只负责"提议"更新，引擎负责校验和执行。任何非法路径、越权操作都会被拒绝并记录到日志。

### 3. 触发器系统（Trigger System）

触发器基于条件表达式自动执行：

```yaml
triggers:
  - id: chased_when_suspicion_high
    priority: 10           # 优先级，数值越小越先执行
    once: false            # 是否仅触发一次
    when: "suspicion >= 80 and flags.chased == false"
    effects:
      - op: set
        path: "flags.chased"
        value: true
        reason: "嫌疑过高，开始被尾随"
    events:
      - type: "danger"
        message: "你感觉有人在雾里跟着你。"
```

**条件表达式 DSL** 支持：
- 比较运算符：`==`, `!=`, `>=`, `<=`, `>`, `<`
- 逻辑运算符：`and`, `or`, `not`
- 括号分组
- 点号路径访问嵌套变量：`relationships.lian`, `time.hour`

### 4. 上下文压缩与内存管理

为避免 LLM 上下文溢出，引擎采用分层内存策略：

- **memory_summary**：每 5-10 回合生成一次历史摘要
- **last_messages**：保留最近 4-8 回合的完整对话
- **关键变量**：按 `prompt_weight`（high/medium/low/hidden）过滤进入 prompt 的变量

### 5. 失败重试机制

当 LLM 输出不合规时：

1. 记录原始输出到日志
2. 发送 "repair prompt" 要求重新生成
3. 最多重试 2 次
4. 若仍失败，进入降级模式：显示系统提示并提供固定选项（重试/回滚/退出）

---

## LLM 提供商配置

通过环境变量选择：

- `CBSE_LLM_PROVIDER=mock|openai|gemini|ollama`
- `CBSE_MODEL` - 覆盖模型名称（可选）
- `OPENAI_API_KEY` 或 `GEMINI_API_KEY`
- `OLLAMA_BASE_URL`（可选，默认 `http://localhost:11434`）
- `CBSE_OLLAMA_NUM_CTX`（可选，默认 `4096`）
- `CBSE_OLLAMA_FORMAT`（`json` 或 `json_schema`，默认 `json`）

> OpenAI/Gemini 提供商是最小化实现，可能随上游 API 变化。  
> Ollama 使用本地 HTTP API，prompt 会自动压缩以提高小模型的 JSON 合规率。

---

## 存档/读档

在输入框中使用命令：

- `/save <名称>` - 保存当前进度
- `/load <名称>` - 读取存档
- `/replay <路径>` - 回放录制的输入
- `/replay stop` - 停止回放
- `/quit` - 退出游戏
- `/help` - 显示帮助

存档文件保存在 `saves/` 目录。

---

## 游戏内容

默认游戏：`games/mist_harbor/`（《雾港回声》）

通过以下文件扩展游戏内容：

- `game.yaml` - 游戏配置、变量定义、初始状态
- `world.md` - 世界设定文档
- `triggers.yaml` - 触发器定义
- `intro.md` - 开场文本（可选）

---

## 回放功能

回放预录制的输入序列：

```bash
python -m cbse --replay replays/mist_harbor_demo.jsonl
```

支持的格式：

- JSON 数组：`["四处看看", "询问停电情况"]`
- JSON 对象：`{"inputs": ["四处看看", "询问停电情况"]}`
- JSONL：每行一个 `{"input": "..."}`
- 纯文本：每行一个输入，`#` 开头为注释

---

## 项目结构

```
cbse/
  engine/           # 引擎核心代码
    app.py          # Textual 应用入口
    content_loader.py   # 内容加载器
    models.py       # Pydantic 数据模型
    prompt_builder.py   # Prompt 构建
    llm/            # LLM 提供商实现
    rules_engine.py # 规则引擎
    schema.py       # JSON Schema 定义
    save_system.py  # 存档系统
  games/            # 游戏内容
    mist_harbor/    # 《雾港回声》示例游戏
  saves/            # 存档目录
  replays/          # 回放文件
  logs/             # 运行日志
```

---

## 技术栈

- **Python 3.11+**
- **Textual** - TUI 框架
- **Pydantic v2** - 数据校验
- **PyYAML** - YAML 解析
