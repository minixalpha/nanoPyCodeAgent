# 设计 Spec — 配置文件支持（`~/.nanoPyCodeAgent/settings.json`）

- **日期**: 2026-06-29
- **分支**: `claude/agent_loop`
- **状态**: 待审阅

> 正文用中文便于审阅（沿用本目录已有 spec 的惯例）；交付物（`src/` 代码、测试、英文文档）一律英文。

---

## 1. 背景与目标

`agent.run()` 目前的配置来源只有两处：真实环境变量，以及通过
`load_dotenv(find_dotenv(usecwd=True))` 从项目 `.env` 加载进环境变量的值。
`anthropic.Anthropic()` 与模型解析（`os.environ.get("ANTHROPIC_MODEL")`）都直接读
`os.environ`。

`docs/dev_notes/zh-CN/0.2.x.md` 描述了第三种配置来源：用户级配置文件
`~/.nanoPyCodeAgent/settings.json`，其 `env` 字段与 Claude Code settings 约定一致，可配
`ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` / `ANTHROPIC_MODEL`。

**目标**：实现对该配置文件的支持，明确三方优先级，并新增一篇面向用户的「如何配置」使用文档。

## 2. 优先级（已确认）

**真实环境变量 > 项目 `.env` > `~/.nanoPyCodeAgent/settings.json`**

- 真实 shell 环境变量最高；
- 项目级 `.env` 次之；
- 全局 `settings.json` 作为兜底默认值，只填补前两者未设置的键。

dev notes 原文「环境变量优先级高于配置文件」是这条规则的简写，本次将其补全为完整三级。

## 3. 方案

**方案 A —— 注入 `os.environ`（采用）**：新增 `load_settings_env()`，读取
`settings.json` 的 `env` 字段，用 `os.environ.setdefault(k, v)` 写入；在 `load_dotenv()`
**之后**调用。靠「先 `load_dotenv` 后 `load_settings_env` + `setdefault`」天然得到既定优先级。
下游 `anthropic.Anthropic()` 与模型解析逻辑**完全不改**。

方案 B（显式配置对象，把 `api_key/base_url/model` 显式传给 `Anthropic(...)`）改动更多、
偏离现有「从环境变量读取」风格；方案 C（Pydantic 类型化模型）对 nano 项目过度设计。均不采用。

## 4. 详细设计

文件：`src/nanopycodeagent/agent.py`

```python
SETTINGS_PATH = Path.home() / ".nanoPyCodeAgent" / "settings.json"

def load_settings_env(path: Path = SETTINGS_PATH) -> None:
    """Apply the `env` mapping from settings.json into os.environ.

    Fills only keys not already set, so real environment variables and values
    loaded from .env take precedence. A missing file is fine (silent). A
    malformed JSON file or a non-object `env` prints a warning and is otherwise
    ignored. Empty / whitespace-only / non-string values are skipped.
    """
```

`run()` 接入顺序（顺序即优先级）：

```python
load_dotenv(find_dotenv(usecwd=True))   # real env > .env
load_settings_env()                      # settings.json fills remaining gaps
client = anthropic.Anthropic()           # reads os.environ, unchanged
```

`SETTINGS_PATH` 作为模块级常量，便于测试 monkeypatch。

## 5. 边界与错误处理

- **文件不存在** → 静默跳过（无配置文件是正常情况）。
- **JSON 解析失败 / `env` 不是对象** → `print` 一行警告后继续（优雅降级，绝不中断启动）。
- **单个值为空串、纯空白或非字符串** → 跳过。关键原因：空 `ANTHROPIC_BASE_URL` 会破坏请求，
  空 `ANTHROPIC_API_KEY` 会让 `client.api_key is None` 凭据检查误判；且 dev notes 的示例
  里这些字段就是空串占位。
- `model` 解析行 `os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL` 无需改动。

## 6. 测试（TDD，沿用现有 mock 风格）

文件：`tests/test_agent.py`（必要时拆分 settings 相关用例）

1. settings.json 提供 `ANTHROPIC_MODEL` 且 env 未设 → 该模型到达 API 调用（`messages.kwargs`）。
2. 真实 env 的 `ANTHROPIC_MODEL` 覆盖 settings.json。
3. 模拟 `load_dotenv` 写入 `os.environ` → 验证 `.env` 覆盖 settings.json（优先级顺序）。
4. 缺失文件 → 不报错、行为如常。
5. 非法 JSON → 打印警告且仍能进入循环。
6. 直接单测 `load_settings_env`：空串 / 纯空白 / 非字符串值不写入 `os.environ`。

测试需复位相关环境变量（`monkeypatch.delenv` / `setenv`）并对 `agent.SETTINGS_PATH` 打桩，
避免读到用户真实配置文件。

## 7. 文档

- 更新 `docs/dev_notes/zh-CN/0.2.x.md`：把「环境变量优先级高于配置文件」补全为完整三级优先级
  （真实环境变量 > `.env` > `settings.json`）。
- **新增用户使用文档目录 `docs/user_guide/`**（双语，沿用 `docs/dev_notes/` 的 `en/` 与
  `zh-CN/` 子目录风格）：
  - `docs/user_guide/en/configuration.md`（英文）
  - `docs/user_guide/zh-CN/configuration.md`（中文）

  内容覆盖「如何配置」主题：三种配置来源（真实环境变量 / 项目 `.env` / 用户级
  `~/.nanoPyCodeAgent/settings.json`）、三个键（`ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` /
  `ANTHROPIC_MODEL`）、完整优先级、`settings.json` 的 `env` 字段示例、空值会被忽略等注意事项。
  英文为面向用户的主文档；中文版置于 `zh-CN/` 目录（符合项目对 zh-CN 文件的例外规则）。两份均手写、
  内容对等。

README / CHANGELOG / 英文 dev note 的同步按项目惯例（`land-pr` skill）在合并阶段处理，本次不动。

## 8. 不在范围内

- 不引入新依赖。
- 不支持 `env` 之外的配置字段（YAGNI；loader 对未知字段天然忽略，为将来留口）。
- 不改 `release.yml` / 发布流程。
