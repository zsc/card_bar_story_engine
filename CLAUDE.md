# 变量卡 + 状态栏 的 AI 剧情游戏引擎（MVP）软件规格说明书（可直接交给 Gemini-cli / Codex 实现）

> **目标**：实现一个“AI 剧情游戏引擎”，核心交互由 **状态栏（Status Bar）** + **变量卡（Variable Cards）** 驱动。引擎用 LLM 生成剧情与建议选项，但**状态更新必须结构化、可验证、可追溯**。并提供一个可玩的 **示例游戏**（内容文件 + 开场 + 变量与触发器）。

---

## 0. 项目概览

### 0.1 名称

* 引擎代号：**CardBar Story Engine（CBSE）**
* 版本：**v1.0（MVP）**

### 0.2 核心卖点

1. **状态栏**：始终展示关键资源（如生命、精力、时间、金钱等）。
2. **变量卡**：以“卡片”形式展示世界状态与人物关系等变量；每回合显示变化（Δ）。
3. **AI 叙事**：LLM 负责叙事与提出“建议选项”；但**所有变量变化必须由结构化 diff 表达**并通过引擎规则校验后才生效。
4. **可做内容（Mod）**：游戏内容以 YAML/JSON + Markdown 配置；无需改引擎代码即可添加新游戏。

---

## 1. 术语与概念

* **Turn（回合）**：玩家一次输入 → AI 生成叙事/选项/状态变更 → 引擎应用变更并渲染 UI。
* **State（运行时状态）**：所有变量的当前值集合（含资源、关系、旗标、库存、已知事实等）。
* **Status Bar（状态栏）**：横向紧凑展示 3–8 个最关键数值。
* **Variable Card（变量卡）**：以卡片组件展示变量（数值/枚举/列表/对象），包含说明、当前值、范围、变化、历史。
* **Trigger（触发器）**：基于条件（变量阈值、旗标、回合数、地点等）自动触发的事件/约束/剧情钩子。
* **LLM Output Contract（AI 输出协议）**：LLM 必须输出符合 JSON Schema 的结构化结果（叙事文本、选项数组、状态更新 ops、日志事件等）。
* **Rules Engine（规则引擎）**：负责验证/裁剪/拒绝非法状态更新，并执行触发器。

---

## 2. 用户体验（玩家视角）

### 2.1 界面布局（推荐：TUI；可后续扩展 Web）

* 顶部：**状态栏**
* 左侧/下方：**变量卡面板**（可滚动/折叠）
* 中央：**剧情叙事区**（Markdown 渲染、带分段）
* 右侧/底部：**建议选项区**（编号 1–6）
* 底部输入框：玩家输入（可直接输入“1”选择，也可输入自由动作）

### 2.2 回合流程

1. 玩家阅读当前剧情 + 状态栏/变量卡
2. 玩家选择一个建议选项（输入数字）或输入自由指令
3. 引擎将当前状态摘要 + 世界设定 + 玩家输入 发给 LLM
4. LLM 返回结构化 JSON：

   * narrative（叙事）
   * choices（建议选项）
   * state_updates（状态更新 ops）
   * events（用于日志/回放）
5. 引擎校验 JSON → 校验状态更新 → 应用更新 → 运行触发器 → 渲染下一回合界面

---

## 3. 需求范围

### 3.1 MVP 必做（Must Have）

* 内容加载：从 `game.yaml` + `world.md` + 可选资源加载
* 运行回合：玩家输入 → LLM → 状态更新 → UI 渲染
* 状态栏 + 变量卡渲染（含 Δ 变化）
* 存档/读档：保存当前 state、回合记录、摘要
* LLM 输出严格校验（JSON schema + 规则引擎）
* 失败重试机制：LLM 输出不合规时自动纠错/重试（有上限）
* 示例游戏可玩：至少 20–40 回合内容量的“开放式”体验（AI 生成，规则控制）

### 3.2 MVP 不做（Non-goals）

* 多人联机
* 复杂战斗系统（可通过变量与触发器“拟态”）
* 图形化资产/动画（MVP 不要求）
* 语音输入/输出

---

## 4. 技术栈建议（给实现者的默认选择）

> 你可以改栈，但接口与文件格式需保持一致。

* 语言：**Python 3.11+**
* UI：**Textual（TUI 框架）** 或备选 **Rich（简化版）**
* 数据校验：**Pydantic v2**（或 jsonschema）
* YAML：PyYAML / ruamel.yaml
* HTTP：httpx
* LLM Provider：抽象接口，支持：

  * OpenAI Chat Completions / Responses（可选）
  * Gemini（可选）
  * 本地模型（可选，作为 stub）

---

## 5. 引擎架构

### 5.1 模块划分

1. **ContentLoader**

   * 读取 `game.yaml`、`world.md`、可选 `scenes/`、`npcs.yaml`、`items.yaml`
   * 输出 `GameDefinition`（结构化对象）
2. **StateStore**

   * 管理当前 `GameState`
   * 记录历史 `StateHistory`（用于 Δ 与回放）
3. **PromptBuilder**

   * 将世界设定、当前状态摘要、最近对话、触发器提示、玩家输入拼成 prompt
4. **LLMClient**

   * provider-agnostic
   * 支持“要求输出为 JSON”模式
5. **SchemaValidator**

   * 校验 AI 输出 JSON 结构
6. **RulesEngine**

   * 校验并应用 `state_updates`（op 列表）
   * clamp 数值范围、拒绝非法路径、拒绝类型不匹配
   * 执行 triggers（可能追加系统事件、追加必须发生的状态变化）
7. **Renderer（UI）**

   * 状态栏渲染
   * 变量卡渲染（含 Δ、高亮最新变化）
   * 剧情渲染
   * 选项渲染
8. **SaveSystem**

   * 存档为 JSON（包含 game_id、版本、state、history 摘要、日志）
9. **Telemetry/Logging（本地）**

   * 记录每回合 prompt、LLM raw output、修复过程、最终应用的 diff（便于调试）

---

## 6. 数据模型与内容格式（Game Definition）

### 6.1 目录结构（建议）

```
cbse/
  engine/
    __init__.py
    app.py                 # Textual 应用入口
    content_loader.py
    models.py              # Pydantic models
    prompt_builder.py
    llm/
      base.py
      openai_provider.py
      gemini_provider.py
      mock_provider.py
    rules_engine.py
    schema.py              # JSON schema 或 Pydantic output model
    save_system.py
    utils.py
  games/
    mist_harbor/
      game.yaml
      world.md
      npcs.yaml
      items.yaml
      intro.md
      endings.md
      triggers.yaml
  saves/
  README.md
  pyproject.toml
```

### 6.2 `game.yaml`（核心清单）

**字段（MVP）**：

* `game_id`：字符串（唯一）
* `title`：游戏名
* `version`：内容版本
* `language`：`zh-CN`
* `tone`：如 `noir`, `cozy`, `grim`（给 prompt 用）
* `content_rating`：默认 `PG-13`
* `status_bar`：状态栏配置（见 6.4）
* `variables`：变量定义数组（见 6.3）
* `initial_state`：初始状态（符合变量定义）
* `win_conditions` / `lose_conditions`：胜负条件（规则引擎可判定）
* `llm`：推荐模型、温度、最大 tokens 等（可被环境变量覆盖）
* `prompt_rules`：叙事限制与风格（注入 prompt）

---

## 6.3 变量定义（Variable Definition）

每个变量定义为一张“卡”的数据基础，UI 与 prompt 由此生成。

**字段：**

* `id`：如 `hp`, `energy`, `gold`, `suspicion`
* `label`：显示名
* `type`：`number | integer | boolean | enum | string | list | object`
* `min` / `max`：数值范围（number/integer）
* `enum_values`：枚举列表（enum）
* `default`：缺省值
* `card`：

  * `visible`: bool
  * `order`: int
  * `format`: `bar | plain | list | chips | keyvalue`
  * `description`: 一句话解释（UI hover/详情）
  * `prompt_weight`: `high | medium | low | hidden`（决定进入 prompt 的优先级）
* `rules`（可选）：

  * `clamp`: bool（默认 true）
  * `readonly`: bool（若 true，LLM 不能改，只能由触发器/系统改）
  * `update_policy`: `any | inc_dec_only | set_only`
* `tags`：如 `resource`, `relationship`, `knowledge`, `flag`

---

## 6.4 状态栏定义（Status Bar Definition）

* `items`：数组，每项：

  * `var_id`：绑定变量 id
  * `style`：`meter`（显示条）或 `text`
  * `label`：短标签
  * `show_delta`：是否显示 Δ
  * `critical_threshold`：低于/高于显示警告（UI 用）

---

## 7. AI 输出协议（LLM Output Contract）

### 7.1 返回 JSON 顶层结构（必须严格符合）

```json
{
  "narrative_markdown": "string",
  "choices": [
    {
      "id": "string",
      "label": "string",
      "hint": "string",
      "risk": "low|medium|high",
      "tags": ["string"]
    }
  ],
  "state_updates": [
    {
      "op": "set|inc|dec|push|remove|toggle",
      "path": "string",
      "value": 0,
      "reason": "string"
    }
  ],
  "new_facts": ["string"],
  "events": [
    {
      "type": "string",
      "message": "string"
    }
  ],
  "end": {
    "is_game_over": false,
    "ending_id": "",
    "reason": ""
  }
}
```

### 7.2 `path` 语法与约束

* `path` 使用点号路径，如：

  * `hp`
  * `inventory.items`（若 inventory 为 object）
  * `relationships.lian`（对象字段）
* **必须在允许的 state 根节点内**；任何未定义变量路径：

  * MVP 策略：**拒绝并触发纠错重试**
* `op` 规则：

  * `inc/dec` 只能用于 number/integer
  * `push/remove` 只能用于 list
  * `toggle` 只能用于 boolean
  * `set` 需类型匹配

### 7.3 状态更新的“可信边界”

* LLM **只提出** `state_updates`
* 引擎必须：

  1. 校验结构
  2. 校验路径合法
  3. 校验类型
  4. 应用 clamp（若启用）
  5. 记录变更历史（用于 Δ 与回放）
* 若 LLM 试图越权（如篡改世界设定、改写只读变量）：

  * 该 update **被丢弃**
  * 记录到日志 `events`（类型 `rejected_update`）

---

## 8. Prompt 设计（关键）

### 8.1 Prompt 构成

每回合向 LLM 发送消息数组（chat style），建议结构：

1. **System**：硬规则（输出 JSON；不得扮演玩家；不得修改协议）
2. **Developer**：世界设定使用方式 + 变量机制 + 内容分级与禁区
3. **User**：本回合上下文：

   * 世界摘要（world.md 的压缩版）
   * 当前关键变量（按 prompt_weight 过滤）
   * 最近 N 回合对话/叙事简要（或摘要）
   * 触发器提示（例如“嫌疑>80 会被追捕”）
   * 玩家输入
   * 当前可见的建议选项（供 AI 延续一致性）

### 8.2 内存与上下文压缩（MVP）

* 保存：

  * `memory_summary`：每 5–10 回合用规则/模型生成一次摘要（或规则引擎自己摘要）
  * `last_messages`：保留最近 4–8 回合的叙事与玩家输入原文
* PromptBuilder 逻辑：

  * 优先放 `memory_summary`
  * 再放关键变量（high/medium）
  * 再放最近对话

### 8.3 输出约束提示要点（System/Developer 中必须出现）

* 必须输出**可解析 JSON**
* JSON 必须匹配协议（字段齐全）
* choices 数量 3–6
* state_updates 数量建议 0–6（避免过度“数值化”）
* 叙事：

  * 二人称/现在时可选（内容里明确）
  * 不能替玩家做决定
  * 每回合推进一个“具体变化”（线索、关系、时间、风险等）

---

## 9. 规则引擎（RulesEngine）

### 9.1 校验顺序

1. 校验 AI JSON schema
2. 遍历 state_updates：

   * path 存在？
   * 变量 readonly？
   * op 合法？
   * value 类型匹配？
3. 应用 updates（产生 `applied_updates`）
4. 对数值变量 clamp 到 min/max（若 clamp=true）
5. 执行 triggers（可产生额外 updates 与 events）
6. 判定胜负条件（win/lose）
7. 输出本回合最终结果给 UI

### 9.2 Trigger 格式（建议 `triggers.yaml`）

每个 trigger：

* `id`
* `when`：条件表达式（MVP 用简单表达式 DSL）
* `effects`：state_updates ops
* `events`：日志信息
* `once`：是否仅触发一次
* `priority`：触发顺序（数值越小越先）

**MVP 条件 DSL 示例**：

* `hp <= 0`
* `suspicion >= 80`
* `flags.met_lian == true and time.hour >= 22`

实现方式：

* MVP 可用一个安全表达式解析器（不 eval 任意代码）
* 或用手写解析：支持 `== != >= <= > < and or not`、括号、数字、布尔、字符串

---

## 10. 存档与回放

### 10.1 SaveGame JSON（MVP）

* `save_version`
* `game_id`
* `game_content_version`
* `timestamp`
* `turn_index`
* `state`（完整当前 state）
* `history`：

  * 每回合：player_input、narrative、choices、applied_updates、events
* `memory_summary`

### 10.2 便捷功能（建议但非必须）

* 快速存档/快速读档
* 导出“剧情文本稿”（把 narrative 按回合拼接成 Markdown）

---

## 11. 失败重试策略（LLM 输出不合规时）

当出现以下情况之一：

* JSON 无法解析
* 缺字段/字段类型不对
* choices 为空或过多
* state_updates 出现非法 path/op/type

引擎执行：

1. 记录 raw 输出（日志）
2. 发送 “repair prompt”（只包含错误摘要 + 要求重新输出完整 JSON）
3. 最多重试 `N=2` 次
4. 若仍失败：

   * 进入降级模式：仅展示一段“系统提示：AI 输出异常” + 提供 3 个固定选项（重试/回滚/退出）
   * 不应用任何 state_updates

---

## 12. 内容安全与边界（MVP 默认）

* 默认 content_rating：PG-13
* prompt_rules 中写明：

  * 禁止露骨性内容
  * 禁止仇恨/歧视
  * 暴力可出现但不血腥细节
  * 不提供现实违法操作指南
* 若玩家输入触发风险（可选实现）：

  * UI 给出提示并建议改写输入
  * 或直接继续但系统提示 AI 保持分级

---

# 13. 示例游戏：**《雾港回声》**（Mist Harbor Echoes）

> 题材：新黑色 / 悬疑 / 城市阴谋
> 核心机制：时间压力 + 嫌疑值 + 线索拼图 + 关系变量
> 目标：在午夜前找出“停电真凶”并决定公开/交易/毁灭证据

下面给出完整内容配置（可直接作为 `games/mist_harbor/` 的初始文件）。

---

## 13.1 `game.yaml`（示例）

```yaml
game_id: mist_harbor
title: "雾港回声"
version: "1.0.0"
language: "zh-CN"
tone: "noir_mystery"
content_rating: "PG-13"

llm:
  recommended_model: "gpt-4.1-mini-or-gemini-1.5"   # 仅提示；运行时可用 env 覆盖
  temperature: 0.8
  max_output_tokens: 900

status_bar:
  items:
    - var_id: hp
      label: "生命"
      style: meter
      show_delta: true
      critical_threshold: 25
    - var_id: energy
      label: "精力"
      style: meter
      show_delta: true
      critical_threshold: 20
    - var_id: gold
      label: "币"
      style: text
      show_delta: true
      critical_threshold: 0
    - var_id: time
      label: "时间"
      style: text
      show_delta: false

variables:
  - id: hp
    label: "生命"
    type: integer
    min: 0
    max: 100
    default: 80
    card: { visible: false, order: 0, format: plain, description: "你还能撑多久。", prompt_weight: high }
    rules: { clamp: true, readonly: false, update_policy: any }
    tags: ["resource"]

  - id: energy
    label: "精力"
    type: integer
    min: 0
    max: 100
    default: 70
    card: { visible: false, order: 0, format: plain, description: "行动效率与判断力的底盘。", prompt_weight: high }
    rules: { clamp: true, readonly: false, update_policy: any }
    tags: ["resource"]

  - id: gold
    label: "硬币"
    type: integer
    min: 0
    max: 999
    default: 12
    card: { visible: false, order: 0, format: plain, description: "买消息、坐车、塞封口费。", prompt_weight: medium }
    rules: { clamp: true, readonly: false, update_policy: any }
    tags: ["resource"]

  - id: time
    label: "时间"
    type: object
    default:
      day: 1
      hour: 20
      minute: 10
    card:
      visible: true
      order: 10
      format: keyvalue
      description: "雾港的夜会把所有人吞掉。午夜前必须做出结论。"
      prompt_weight: high
    rules: { clamp: false, readonly: false, update_policy: any }
    tags: ["resource"]

  - id: suspicion
    label: "嫌疑"
    type: integer
    min: 0
    max: 100
    default: 10
    card:
      visible: true
      order: 20
      format: bar
      description: "你被盯上的程度。越高越危险。"
      prompt_weight: high
    rules: { clamp: true, readonly: false, update_policy: any }
    tags: ["risk"]

  - id: clues
    label: "线索"
    type: integer
    min: 0
    max: 12
    default: 0
    card:
      visible: true
      order: 30
      format: bar
      description: "你已拼到的关键拼图数量。"
      prompt_weight: high
    rules: { clamp: true, readonly: false, update_policy: any }
    tags: ["progress"]

  - id: truth_map
    label: "真相拼图"
    type: list
    default: []
    card:
      visible: true
      order: 40
      format: list
      description: "用一句话记录确认过的事实。"
      prompt_weight: medium
    rules: { clamp: false, readonly: false, update_policy: any }
    tags: ["knowledge"]

  - id: location
    label: "所在地点"
    type: enum
    enum_values: ["码头", "灯塔", "旧电厂", "钟楼街", "鸦巢酒吧", "报社"]
    default: "鸦巢酒吧"
    card:
      visible: true
      order: 50
      format: plain
      description: "你当前所处的位置。"
      prompt_weight: high
    rules: { clamp: false, readonly: false, update_policy: set_only }
    tags: ["world"]

  - id: relationships
    label: "关系"
    type: object
    default:
      lian: 35
      mayor: -10
      dockmaster: 5
    card:
      visible: true
      order: 60
      format: keyvalue
      description: "人脉会决定你拿到真相还是被沉海。范围 -100..100。"
      prompt_weight: medium
    rules: { clamp: false, readonly: false, update_policy: any }
    tags: ["relationship"]

  - id: inventory
    label: "随身物品"
    type: list
    default: ["旧怀表", "纸烟", "折叠小刀"]
    card:
      visible: true
      order: 70
      format: list
      description: "能用就用，别逞强。"
      prompt_weight: low
    rules: { clamp: false, readonly: false, update_policy: any }
    tags: ["items"]

  - id: flags
    label: "旗标"
    type: object
    default:
      met_lian: false
      power_sabotage_confirmed: false
      chased: false
    card:
      visible: true
      order: 80
      format: keyvalue
      description: "引擎内部的剧情开关。"
      prompt_weight: low
    rules: { clamp: false, readonly: false, update_policy: any }
    tags: ["flag"]

initial_state:
  hp: 80
  energy: 70
  gold: 12
  time: { day: 1, hour: 20, minute: 10 }
  suspicion: 10
  clues: 0
  truth_map: []
  location: "鸦巢酒吧"
  relationships: { lian: 35, mayor: -10, dockmaster: 5 }
  inventory: ["旧怀表", "纸烟", "折叠小刀"]
  flags: { met_lian: false, power_sabotage_confirmed: false, chased: false }

win_conditions:
  - "flags.power_sabotage_confirmed == true and clues >= 8"
lose_conditions:
  - "hp <= 0"
  - "suspicion >= 100"
  - "time.hour >= 24"

prompt_rules:
  style_notes:
    - "新黑色：潮湿、霓虹、雾、短句、暗喻克制。"
    - "推动调查：每回合推进一个线索/关系/风险。"
  boundaries:
    - "PG-13：不写露骨性内容，不描写血腥细节。"
    - "不输出真实世界违法操作指南。"
```

---

## 13.2 `world.md`（示例世界设定）

```md
# 雾港回声：世界设定（供 AI 使用）

雾港是一座被海雾与霓虹缠住的港城。三小时前全城大停电，只有零星的发电机在喘气。
午夜之前如果无法恢复主网，港口的冷库会坏、医院会停、外海的船会撞进礁区。

你是“写过新闻、也做过脏活”的调查者。你不属于任何派系，但每个派系都觉得你欠他们。

关键势力：
- 市政厅：市长办公室想把停电定性为“意外”，而且很急。
- 码头工会：他们说这是资本的报复；也有人说工会里出了内鬼。
- 旧电厂：早该报废，却仍是城市电力的骨架。有人在里面动过手脚。
- 报社：真相能救人，也能让你消失。

重要 NPC（名字可用但不要一次塞太多）：
- 黎安：街头情报贩子，嘴硬心软，知道“谁在买消息”。
- 码头总管：两边都不得罪的人，最会撒谎。
- 市长顾问：擅长用“更大的危机”压住你的小问题。

叙事原则：
- 玩家永远有选择；AI 不能替玩家决定。
- “嫌疑”越高，尾随与追捕越频繁；“精力”低会失误；“线索/真相拼图”累积可触发关键结论。
- 时间会流逝：大多数行动应推进 time（分钟或小时）。
```

---

## 13.3 `triggers.yaml`（示例触发器）

```yaml
triggers:
  - id: chased_when_suspicion_high
    priority: 10
    once: false
    when: "suspicion >= 80 and flags.chased == false"
    effects:
      - op: set
        path: "flags.chased"
        value: true
        reason: "嫌疑过高，开始被尾随"
      - op: dec
        path: "energy"
        value: 10
        reason: "你不得不绕路甩尾巴"
    events:
      - type: "danger"
        message: "你感觉有人在雾里跟着你。"

  - id: game_over_midnight
    priority: 1
    once: false
    when: "time.hour >= 24"
    effects: []
    events:
      - type: "end"
        message: "午夜钟声吞掉了整座城市的嗡鸣。"

  - id: confirm_sabotage_when_enough_truth
    priority: 20
    once: true
    when: "clues >= 8 and flags.power_sabotage_confirmed == false"
    effects:
      - op: set
        path: "flags.power_sabotage_confirmed"
        value: true
        reason: "线索已足以确认：这是人为破坏"
      - op: push
        path: "truth_map"
        value: "停电并非事故：有人针对旧电厂做了手脚。"
        reason: "关键结论"
    events:
      - type: "breakthrough"
        message: "你把碎片拼成一张能致命的图。"
```

---

## 13.4 开场 `intro.md`（可选）

```md
鸦巢酒吧的灯是靠发电机撑着的，像一口喘不上气的肺。

你坐在吧台阴影里，手指摩挲着旧怀表。滴答声在停电后的城市里格外刺耳。
有人说这只是事故，但你知道：事故没有这么“准时”。

门口风铃响了一下，雾被带进来。你抬头，看见一个熟悉的侧影——黎安。
```

---

## 13.5 示例：第一回合建议输出（给实现者做联调用）

> 注意：这段是“AI 应该输出的 JSON”的示例，用于你做解析/校验与 UI 渲染联调。

```json
{
  "narrative_markdown": "黎安把外套上的雾水抖进灯光里，像抖掉一段不愿承认的过去。\n\n她没有坐下，只把一张折角的纸推到你手边：上面是旧电厂的巡检表复印件，墨迹还没干透。\n\n“有人在停电前半小时进过电厂，走的是维修通道。”她压低声音，“而且付钱的人不想留下名字。”\n\n你能感觉到酒吧里有人在偷听——也许只是酒精让你多疑，但雾港的夜从不白给。",
  "choices": [
    { "id": "ask_lian_more", "label": "追问黎安：是谁付的钱？", "hint": "可能加线索，也可能惹怒某人。", "risk": "medium", "tags": ["investigate", "relationship"] },
    { "id": "go_power_plant", "label": "立刻去旧电厂（走维修通道）", "hint": "抢时间，但风险很高。", "risk": "high", "tags": ["travel", "risk"] },
    { "id": "bribe_bartender", "label": "用钱买酒保的耳朵：今晚谁来过？", "hint": "花钱换情报，嫌疑可能上升。", "risk": "low", "tags": ["social", "resource"] },
    { "id": "lay_low", "label": "先按兵不动，观察酒吧里的目光", "hint": "降低风险，可能错过窗口期。", "risk": "low", "tags": ["stealth"] }
  ],
  "state_updates": [
    { "op": "inc", "path": "clues", "value": 1, "reason": "获得巡检表线索" },
    { "op": "push", "path": "truth_map", "value": "停电前半小时有人走维修通道进入旧电厂。", "reason": "记录事实" },
    { "op": "set", "path": "flags.met_lian", "value": true, "reason": "与黎安接触" },
    { "op": "inc", "path": "time.minute", "value": 10, "reason": "交谈与确认细节花费时间" }
  ],
  "new_facts": [
    "旧电厂存在一条“维修通道”，可避开正门。",
    "有人在停电前半小时进入旧电厂。"
  ],
  "events": [
    { "type": "info", "message": "你拿到了巡检表复印件。" }
  ],
  "end": { "is_game_over": false, "ending_id": "", "reason": "" }
}
```

> 实现注意：上面 `time.minute inc 10` 会让分钟溢出（>=60）——规则引擎需处理进位（minute→hour）。这是 **MVP 的必测点**。

---

## 13.6 《雾港回声》设计要点（让 AI 不发散）

在 prompt_rules 或 developer prompt 里强调：

* 关键地点有限：码头 / 灯塔 / 旧电厂 / 钟楼街 / 鸦巢酒吧 / 报社
* 关键人物有限：黎安、码头总管、市长顾问（可再扩 2–3 个）
* 关键压力：

  * 时间推进到 24:00 就结束（不一定死亡，但失败或“坏结局”）
  * 嫌疑到 100 触发被捕/被沉海（失败）
* 线索到 8 触发“确认人为破坏”，再引导玩家选择结局路线：

  1. 把证据交给报社（真相公开）
  2. 交给市长顾问（交易、好处、但城市被掩盖）
  3. 交给码头工会（街头正义，风险极高）
  4. 自己销毁（保命但内疚/后果）

---

# 14. 验收标准（Acceptance Criteria）

实现完成后，满足以下即视为 MVP 达标：

1. **可以运行**：启动后进入《雾港回声》开场，看到状态栏 + 变量卡 + 叙事区 + 选项区 + 输入框。
2. **每回合可推进**：输入选项编号或自由文本都能推进回合。
3. **变量卡与状态栏更新正确**：展示 Δ；历史可追溯（至少保存上一回合）。
4. **AI 输出严格校验**：故意让 mock 输出坏 JSON 时能触发 repair/降级，不崩溃。
5. **规则引擎生效**：数值 clamp、minute 进位、触发器可以触发并显示事件。
6. **可存档读档**：读档后状态一致。
7. **胜负可判定**：达到 win/lose 条件会进入 end.is_game_over=true 并展示 ending。

---

# 15. 给 Gemini-cli / Codex 的实现任务拆解（直接可用）

按顺序实现（每步可提交并自测）：

1. **Pydantic Models**：GameDefinition、VariableDefinition、GameState、LLMOutput、StateUpdateOp、Trigger
2. **ContentLoader**：加载 YAML/MD，校验完整性，生成默认 state
3. **StateStore + History**：apply_ops、compute_delta、snapshot
4. **RulesEngine**：

   * validate op
   * clamp
   * time 进位（minute/hour）
   * trigger evaluator（条件 DSL）
   * win/lose evaluator
5. **LLMClient 抽象 + MockProvider**：先用 mock JSON 固定输出跑通
6. **SchemaValidator + Repair Loop**：坏输出→repair→降级
7. **Textual UI**：状态栏、变量卡面板、叙事区、选项区、输入框
8. **真实 LLM Provider（可选）**：gemini/openai；环境变量配置
9. **SaveSystem**：save/load JSON
10. **示例游戏联调**：确保《雾港回声》可玩
